# Copyright (c) 2019 Princeton University
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Standard imports
from commons.util import ensure_directory_exists
from genericpath import exists
import json

import os
from requests_futures.sessions import FuturesSession
import concurrent.futures
import subprocess
import math
import time
import threading
import logging

# Local imports
from GenConfigs import *
from .EventGenerator import GenericEventGenerator
from commons.JSONConfigHelper import CheckJSONConfig, ReadJSONConfig
from commons.Logger import ScriptLogger
from commons import util
from .WorkloadChecker import check_workload_validity

logging.captureWarnings(True)



class WorkloadInvoker:

   def __init__(self):
      # Global variables
      self.supported_distributions = {'Poisson', 'Uniform'}

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

      # These variables are set in main
      self.my_commit_hash, self.test_result_dir_name = None, None
      self.test_result_dir_path = None
      self.runid = util.gen_random_hex_string(8)

      self.param_file_cache = {}   # a cache to keep json of param files
      self.binary_data_cache = {}  # a cache to keep binary data (image files, etc.)

   @staticmethod
   def gen_invocation_id(test_name, runid):
      out = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                            cwd=FAAS_ROOT)
      commit_hash = out.decode('utf-8').strip()
      test_dir_name = "{}_{}_{}".format(commit_hash[0:10], test_name, runid)
      return (commit_hash, test_dir_name)

   def handleFutures(self, futures):
       failures = False
       print("In handleFutures", len(futures))
       for future in concurrent.futures.as_completed(futures):
           try:
               res = future.result()
           except Exception as e:
               self.logger.info("Request failed: " + str(e))
               failures = True
           else:
               prefix = ""
               if res.status_code >= 200 and res.status_code <= 299 :
                   prefix = "Request successful: "
               else:
                   prefix = "Request failed:     "
                   failures = True
                   self.logger.info(prefix + str(res.status_code) + " " + res.url)

       return not failures

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

   def HTTPInstanceGenerator(self, action, instance_times, blocking_cli, param_file=None):
       if len(instance_times) == 0:
           return False
       session = FuturesSession(max_workers=100)
       url = self.base_url + action
       print("runid is", str(self.runid))
       assert(self.runid)
       parameters = {'blocking': blocking_cli, 'result': self.RESULT}
       args = { 'testid': self.runid,
                'body': None}
       print("Setting params", parameters)
       authentication = (self.user_pass[0], self.user_pass[1])
       after_time, before_time = 0, 0

       futures = []

       if param_file == None:
           st = 0
           for t in instance_times:
               st = st + t - (after_time - before_time)
               before_time = time.time()
               if st > 0:
                   time.sleep(st)

               #logger.info("Url " + url)
               future = session.post(url, params=parameters, auth=authentication,
                                     json=args, verify=False)
               futures.append(future)
               #print(future.result())
               after_time = time.time()
       else:   # if a parameter file is provided
           try:
               param_file_body = self.param_file_cache[param_file]
           except:
               with open(param_file, 'r') as f:
                   param_file_body = json.load(f)
                   args['body'] = param_file_body
                   param_file_body = args
                   self.param_file_cache[param_file] = param_file_body

           for t in instance_times:
               st = t - (after_time - before_time)
               if st > 0:
                   time.sleep(st)
               before_time = time.time()
               future = session.post(url, params=parameters, auth=authentication,
                                     json=param_file_body, verify=False)
               futures.append(future)
               after_time = time.time()

       self.handleFutures(futures)
       return True


   def BinaryDataHTTPInstanceGenerator(self, action, instance_times, blocking_cli, data_file):
       """
       TODO: Automate content type
       """
       url = self.base_gust_url + action
       session = FuturesSession(max_workers=100)
       if len(instance_times) == 0:
           return False
       after_time, before_time = 0, 0

       futures = []

       try:
           data = self.binary_data_cache[data_file]
       except:
           data = open(data_file, 'rb').read()
           self.binary_data_cache[data_file] = data

       for t in instance_times:
           st = t - (after_time - before_time)
           if st > 0:
               time.sleep(st)
           before_time = time.time()
           self.logger.info("Url " + url)
           assert(self.runid)
           future = session.post(url=url, headers={'Content-Type':
                                                   'image/jpeg'},
                                 params={'blocking': blocking_cli,
                                         'result': self.RESULT,
                                         'payload': {'testid': self.runid}},
                                 data=data, auth=(self.user_pass[0],
                                                  self.user_pass[1]), verify=False)
           futures.append(future)
           after_time = time.time()

       self.handleFutures(futures)
       return True

   def main(self, options):
       """
       The main function.
       """
       #self.logger.info("Workload Invoker started")
       #print("Log file -> ../profiler_results/logs/SWI.log")

       if not CheckJSONConfig(options.config_json):
           raise Exception("Invalid or no JSON config file!")

       workload = ReadJSONConfig(options.config_json)
       if not check_workload_validity(workload=workload,
                                     supported_distributions=self.supported_distributions):
           return False    # Abort the function if json file not valid

       # Set name and commit hash and create destination dir if
       # missing
       self.my_commit_hash, self.test_result_dir_name =\
          WorkloadInvoker.gen_invocation_id(workload["test_name"], self.runid)
       self.test_result_dir_path = util.ensure_directory_exists(
          os.path.join(DATA_DIR, self.test_result_dir_name))

       # log_path = os.path.join(
       #                               util.ensure_directory_exists(
       #                                  os.path.join(self.test_result_dir_path, 'log')),
       #                               'SWI.log')
       self.logger = ScriptLogger('workload_invoker', "SWI.log")

       [all_events, event_count] = GenericEventGenerator(workload)

       threads = []

       for (instance, instance_times) in all_events.items():
           action = workload['instances'][instance]['application']
           if action == "long_run":
              print("Invoking long_run")
           try:
               param_file = os.path.join(FAAS_ROOT,  workload['instances'][instance]['param_file'])
           except:
               param_file = None
           blocking_cli = workload['blocking_cli']
           if 'data_file' in workload['instances'][instance].keys():
               data_file = workload['instances'][instance]['data_file']
               threads.append(threading.Thread(target=self.BinaryDataHTTPInstanceGenerator, args=[
                              action, instance_times, blocking_cli, data_file]))
           else:
               threads.append(threading.Thread(target=self.HTTPInstanceGenerator, args=[
                              action, instance_times, blocking_cli, param_file]))

       # Dump Test Metadata
       test_metadata = {
          'start_time':  math.ceil(time.time() * 1000),
          'test_config': options.config_json,
          'event_count': event_count,
          'commit_hash': self.my_commit_hash,
          'runid': self.runid
       }

       with open(os.path.join(self.test_result_dir_path,
                              "test_metadata.json"), 'w') as f:
          f.write(json.dumps(test_metadata))

       try:
           if workload['perf_monitoring']['runtime_script']:
               runtime_script = ['bash',
                                 os.path.join(FAAS_ROOT,
                                              workload['perf_monitoring']['runtime_script']),
                                 str(int(workload['test_duration_in_seconds'])),
                                 self.test_result_dir_path,
                                 '&']
               # FIXME: os.system
               os.system(' '.join(runtime_script))
               self.logger.info("Runtime monitoring script ran")
       except:
           pass

       self.logger.info("Test started")
       for thread in threads:
           thread.start()

       for thread in threads:
          thread.join()

       self.logger.info("Test ended")

       return True
