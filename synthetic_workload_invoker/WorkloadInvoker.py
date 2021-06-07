# Copyright (c) 2019 Princeton University
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Standard imports
import json

import os
from synthetic_workload_invoker.datatypes import InvocationMetadata
from requests_futures.sessions import FuturesSession
import concurrent.futures
import subprocess
import math
import time
import threading
import logging
import asyncio
from typing import Any, Tuple, Dict, TypedDict
from mimetypes import MimeTypes

# Local imports
from GenConfigs import *
from .EventGenerator import generic_event_generator
from commons.JSONConfigHelper import check_json_config, read_json_config
from commons.Logger import ScriptLogger
from commons import util
from .WorkloadChecker import check_workload_validity

logging.captureWarnings(True)


class WorkloadInvoker:
   supported_distributions = {'Poisson', 'Uniform'}

   @staticmethod
   def gen_invocation_id(test_name, runid):
      out = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                            cwd=FAAS_ROOT)
      commit_hash = out.decode('utf-8').strip()
      test_dir_name = "{}_{}_{}".format(commit_hash[0:10], test_name, runid)
      return (commit_hash, test_dir_name)

   def __init__(self, config_json):
      # Global variables

      self.logger = None

      APIHOST = subprocess.check_output(WSK_PATH + " property get --apihost", shell=True).split()[3].decode("utf-8")
      APIHOST = APIHOST if APIHOST.lower().startswith("http") else 'https://' + APIHOST
      AUTH_KEY = subprocess.check_output(WSK_PATH + " property get --auth", shell=True).split()[2]
      AUTH_KEY = AUTH_KEY.decode("utf-8")
      self.user_pass = AUTH_KEY.split(':')
      NAMESPACE = subprocess.check_output(WSK_PATH + " property get --namespace", shell=True).split()[2]
      NAMESPACE = NAMESPACE.decode("utf-8")
      self.RESULT = 'false'
      self.base_url = APIHOST + '/api/v1/namespaces/' + NAMESPACE + '/actions/'
      self.base_gust_url = APIHOST + '/api/v1/web/guest/default/'

      # Generate a runid for this instance
      self.runid = util.gen_random_hex_string(8)

      self.param_file_cache = {}   # a cache to keep json of param files
      self.binary_data_cache = {}  # a cache to keep binary data
      # (image files, etc.)

      # Count of function invocations successfully submitted to FaaS queue
      self.invocation_success_tally = 0
      self.invocation_failure_tally = 0
      self.invocation_expected_tally = 0
      self.tally_lock = threading.Lock()

      self.config_json = config_json
      self.workload = WorkloadInvoker.read_json_config(config_json)
      # Set name and commit hash and create destination dir if
      # missing
      self.my_commit_hash, test_result_dir_name =\
         WorkloadInvoker.gen_invocation_id(self.workload["test_name"], self.runid)
      self.test_result_dir_path = util.ensure_directory_exists(
         os.path.join(DATA_DIR, test_result_dir_name))


   @staticmethod
   def read_json_config(config_json: str) -> Dict[Any, Any]:
      if not check_json_config(config_json):
         raise Exception("Invalid or no JSON config file!")

      workload = read_json_config(config_json)
      if not check_workload_validity(workload=workload,
                                     supported_distributions=WorkloadInvoker.supported_distributions):
          # Abort the function if json file not valid
          raise Exception("Workload JSON is invalid")

      return workload



   def handle_futures(self, futures) -> Tuple[int, int]:
       """
       Wait for all futures in futures to complete. Returnes a tuple
       containing the number of succseful and failed requests.
       """
       failures = 0
       successes = 0
       for future in concurrent.futures.as_completed(futures):
           try:
               res = future.result()
           except Exception as e:
               self.logger.info("Request failed: " + str(e))
               failures += 1
           else:
               prefix = ""
               if res.status_code >= 200 and res.status_code <= 299 :
                   prefix = "Request successful: "
                   successes += 1
               else:
                   prefix = "Request failed:     "
                   failures += 1
                   self.logger.info(prefix + str(res.status_code) + " " + res.url)

       return (successes, failures)

   # @staticmethod
   # def PROCESSInstanceGenerator(instance, instance_script, instance_times, blocking_cli):
   #     if len(instance_times) == 0:
   #         return False
   #     after_time, before_time = 0, 0

   #     if blocking_cli:
   #         pass
   #     else:
   #         instance_script = instance_script + ' &'

   #     for t in instance_times:
   #         time.sleep(max(0, t - (after_time - before_time)))
   #         before_time = time.time()
   #         os.system(instance_script)
   #         after_time = time.time()

   #     return True

   #class InstanceGenerator(

   def http_instance_generator(self, action, instance_times,
                               blocking_cli, query_file=None, param_file=None) -> None:
       if len(instance_times) == 0:
          raise Exception("http_instance_generator called without instance times")
       session = FuturesSession(max_workers=100)
       url = f"{self.base_url}{action}?{self.runid}"
       assert(self.runid)
       parameters = {'blocking': blocking_cli, 'result': self.RESULT}
       args = { 'testid': self.runid,
                'body': None }
       authentication = (self.user_pass[0], self.user_pass[1])

       futures = []

       if (not param_file is None) and (not query_file is None):
          raise Exception("Only one of param_file and query_stirng can be set")


       if param_file:
          try:
             param_file_body = self.param_file_cache[param_file]
          except:
             with open(param_file, 'r') as f:
                param_file_body = json.load(f)
                args['body'] = param_file_body
                param_file_body = args
                self.param_file_cache[param_file] = param_file_body

       if query_file:
          try:
             query_file_body = self.param_file_cache[query_file]
          except:
             with open(query_file, 'r') as f:
                query_file_body = json.load(f)
                self.param_file_cache[query_file] = query_file_body

          print("Updating paramters", str(parameters), str(query_file_body))
          parameters.update(query_file_body)


       print("Final parameters", str(parameters))
       st = 0
       after_time, before_time = 0, 0
       for t in instance_times:
          st = st + t - (after_time - before_time)
          before_time = time.time()
          if st > 0:
             time.sleep(st)

          # self.logger.info("Url " + url)
          # self.logger.info("Setting params" + str(parameters))
          future = session.post(url, params=parameters, auth=authentication,
                                json=args, verify=False)
          futures.append(future)
          #print(future.result())
          after_time = time.time()

       (successes, failures) = self.handle_futures(futures)

       with self.tally_lock:
          self.invocation_success_tally += successes
          self.invocation_failure_tally += failures
          self.invocation_expected_tally += len(instance_times)


   def binary_data_http_instance_generator(self, action, instance_times, blocking_cli, data_file):
      """
      TODO: Automate content type
      """
      url = f"{self.base_gust_url}{action}?{self.runid}"
      session = FuturesSession(max_workers=100)
      if len(instance_times) == 0:
         return False
      after_time, before_time = 0, 0

      futures = []

      if not data_file in self.binary_data_cache:
         data = open(data_file, 'rb').read()
         self.binary_data_cache[data_file] = {}
         self.binary_data_cache[data_file]["body"] = data
         self.binary_data_cache[data_file]["mime"] = MimeTypes().guess_type(data_file)[0]

      file_body = self.binary_data_cache[data_file]["body"]
      file_mime = self.binary_data_cache[data_file]["mime"]

      for t in instance_times:
         st = t - (after_time - before_time)
         if st > 0:
            time.sleep(st)
         before_time = time.time()
         #self.logger.info("Url " + url)
         assert(self.runid)
         future = session.post(url=url, headers={'Content-Type':
                                                 file_mime},
                               params={'blocking': blocking_cli,
                                       'result': self.RESULT,
                                       'payload': {'testid': self.runid}},
                               data=file_body, auth=(self.user_pass[0],
                                                     self.user_pass[1]), verify=False)
         futures.append(future)
         after_time = time.time()

      (successes, failures) = self.handle_futures(futures)

      with self.tally_lock:
         self.invocation_success_tally += successes
         self.invocation_failure_tally += failures
         self.invocation_expected_tally += len(instance_times)


   @staticmethod
   def write_test_metadata(metadata, destdir):
      destfile = os.path.join(destdir, "test_metadata.json")
      with open(destfile, 'w') as f:
         f.write(json.dumps(metadata))

   async def maybe_start_runtime_script(self, workload, destdir):
      if workload['perf_monitoring']['runtime_script']:
          runtime_script_cmdline = [ os.path.join(FAAS_ROOT,
                                                  workload['perf_monitoring']['runtime_script']),
                                     str(int(workload['test_duration_in_seconds'])),
                                     destdir]
          runtime_script = await asyncio.create_subprocess_exec(*runtime_script_cmdline)
          self.logger.info("Invoked runtime monitoring script pid=%s" %
                           runtime_script.pid)
          return runtime_script
      return None



   async def invoke_benchmark_async(self) -> InvocationMetadata:
       """
       The main function.
       """

       workload = self.workload
       #self.logger.info("Workload Invoker started")
       #print("Log file -> ../profiler_results/logs/SWI.log")


       # log_path = os.path.join(
       #                               util.ensure_directory_exists(
       #                                  os.path.join(self.test_result_dir_path, 'log')),
       #                               'SWI.log')
       self.logger = ScriptLogger('workload_invoker', "SWI.log")

       (all_events, event_count) = generic_event_generator(workload)

       threads = []

       for (instance, instance_times) in all_events.items():
           action = workload['instances'][instance]['application']
           if action == "long_run":
              print("Invoking long_run")
           try:
               param_file = os.path.join(FAAS_ROOT,  workload['instances'][instance]['param_file'])
           except:
               param_file = None

           try:
               query_file = os.path.join(FAAS_ROOT,  workload['instances'][instance]['query_string'])
           except:
               query_file = None

           blocking_cli = workload['blocking_cli']
           if 'data_file' in workload['instances'][instance].keys():
               data_file = workload['instances'][instance]['data_file']
               threads.append(threading.Thread(target=self.binary_data_http_instance_generator, args=[
                              action, instance_times, blocking_cli, data_file]))
           else:
               threads.append(threading.Thread(target=self.http_instance_generator, args=[
                              action, instance_times, blocking_cli, query_file, param_file]))

       # Dump Test Metadata
       test_metadata: InvocationMetadata = {
          'start_time':  math.ceil(time.time() * 1000),
          'workload_name': self.workload["test_name"],
          'test_config': self.config_json,
          'event_count': event_count,
          'commit_hash': self.my_commit_hash,
          'runid': self.runid,
          'runtime_script': False,
          "failures": 0,
          "successes": 0,
          "expected": 0
       }

       runtime_script = await self.maybe_start_runtime_script(workload,
                                                              self.test_result_dir_path)


       self.logger.info("Test started")
       for thread in threads:
           thread.start()

       if runtime_script:
          _, _ = await runtime_script.communicate()

          if runtime_script.returncode > 0:
             raise Exception("Runtime script failed")
          else:
             self.logger.info("Runtime script completed successfully")
             test_metadata['runtime_script'] = True

       for thread in threads:
          thread.join()

       # Save post-benchmark stats to metadata
       test_metadata["failures"] = self.invocation_failure_tally
       test_metadata["successes"] = self.invocation_success_tally
       test_metadata["expected"] = self.invocation_expected_tally

       self.write_test_metadata(test_metadata, self.test_result_dir_path)

       self.logger.info("Test ended")

       return test_metadata

   def invoke_benchmark(self) -> InvocationMetadata:
      return asyncio.run(self.invoke_benchmark_async())
