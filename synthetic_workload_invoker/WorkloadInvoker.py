# Copyright (c) 2019 Princeton University
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# Standard imports
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
from .WorkloadChecker import CheckWorkloadValidity

logging.captureWarnings(True)


class WorkloadInvoker:

   def __init__(self):
      # Global variables
      self.supported_distributions = {'Poisson', 'Uniform'}

      self.logger = ScriptLogger('workload_invoker', 'SWI.log')

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

      self.param_file_cache = {}   # a cache to keep json of param files
      self.binary_data_cache = {}  # a cache to keep binary data (image files, etc.)

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
               #self.logger.info(prefix + str(res.status_code) + " " + res.url)

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
       session = FuturesSession(max_workers=30)
       url = self.base_url + action
       parameters = {'blocking': blocking_cli, 'result': self.RESULT}
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
               future = session.post(url, params=parameters, auth=authentication, verify=False)
               futures.append(future)
               #print(future.result())
               after_time = time.time()
       else:   # if a parameter file is provided
           try:
               param_file_body = self.param_file_cache[param_file]
           except:
               with open(param_file, 'r') as f:
                   param_file_body = json.load(f)
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

       # self.handleFutures(futures)
       return True


   def BinaryDataHTTPInstanceGenerator(self, action, instance_times, blocking_cli, data_file):
       """
       TODO: Automate content type
       """
       url = self.base_gust_url + action
       session = FuturesSession(max_workers=30)
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
           future = session.post(url=url, headers={'Content-Type': 'image/jpeg'},
                                 params={'blocking': blocking_cli, 'result': self.RESULT},
                                 data=data, auth=(self.user_pass[0], self.user_pass[1]), verify=False)
           futures.append(future)
           after_time = time.time()

       self.handleFutures(futures)
       return True

   def main(self, options):
       """
       The main function.
       """
       self.logger.info("Workload Invoker started")
       print("Log file -> ../profiler_results/logs/SWI.log")

       if not CheckJSONConfig(options.config_json):
           self.logger.error("Invalid or no JSON config file!")
           return False    # Abort the function if json file not valid

       workload = ReadJSONConfig(options.config_json)
       if not CheckWorkloadValidity(workload=workload, supported_distributions=self.supported_distributions):
           return False    # Abort the function if json file not valid

       [all_events, event_count] = GenericEventGenerator(workload)

       threads = []

       for (instance, instance_times) in all_events.items():
           action = workload['instances'][instance]['application']
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
          'event_count': event_count
       }

       with open(os.path.join(DATA_DIR, "test_metadata.out"), 'w') as f:
          f.write(json.dumps(test_metadata))

       try:
           if workload['perf_monitoring']['runtime_script']:
               runtime_script = 'bash ' + FAAS_ROOT + '/' + workload['perf_monitoring']['runtime_script'] + \
                   ' ' + str(int(workload['test_duration_in_seconds'])) + ' &'
               os.system(runtime_script)
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
