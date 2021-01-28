"""
Module for managing a benchmark "suite" of workloads. A suite is
the same workload run, for example, 10 times in sequence. The script
reads a YAML file with workload specification (passed via the -c
option) which specifies which benchmark to run and how many times it
should be run and whether the runs should be cold or warm. Warm runs
will trigger a warmup run which is not counted. As output, this script
will write a metadata file containing the runid's of the benchmarks
that were run.

"""
import json
import re
import os
import subprocess
from enum import Enum, unique, auto
from synthetic_workload_invoker.WorkloadInvoker import WorkloadInvoker
from time import sleep
import hashlib
from typing import Dict, List

import docker

from commons import util
from GenConfigs import *

ENCODING = "utf-8"

@unique
class InvocationType(Enum):
    WARM = auto()
    COLD = auto()

    @staticmethod
    def from_string(t: str):
        try:
            return {"warm": InvocationType.WARM,
                    "cold": InvocationType.COLD}[t]
        except KeyError:
            raise ValueError("Value must be either cold or warm, was %s" % t)

def _get_docker_container_by_image(image):
    client = docker.from_env()
    containers = client.containers.list()
    target = list(filter(lambda x: any(map(lambda y: image in y, x.image.tags)), containers))
    if len(target) == 0:
        raise Exception("No docker containers with image matching %s" % image)
    if len(target) > 1:
        raise Exception("Multiple docker containers matches %s" % image)

    return target[0]

def _parse_kafka_output(kafka_output: str) -> List[Dict[str, str]]:
    data_lines = filter(lambda x: not (x.startswith("GROUP") or (x.strip() == "")) ,
                        kafka_output.splitlines())

    return list(map(lambda x: {'group': x[0],
                          'topic': x[1],
                          'partition': x[2],
                          'current-offset': x[3],
                          'log-end-offset': x[4],
                          'lag': x[5],
                          'consumer-id': x[6],
                          'host': x[7],
                          'client-id': x[8]},
                    map(lambda l: re.split(" +", l.strip()),
                        data_lines)))


def _get_kafka_queue_stats(kafka_container) -> Dict[str, int]:
    # TODO: Figure out how to do this using the API
    #(return_code, output) = kafka_container.exec_run(
    output = subprocess.check_output(
        ["docker",
         "exec",
         "-it",
         kafka_container.id,
         "/opt/kafka/bin/kafka-run-class.sh",
         "kafka.admin.ConsumerGroupCommand",
         "--describe",
         "--all-groups",
         "--bootstrap-server",
         "localhost:9093"])

    output_str = output.decode('utf-8')

    # if return_code != 0:
    #     raise Exception("Kafka command failed, exit code %s, output %s",
    #                     return_code, output_str)

    output_parsed = list(filter(lambda x: x["group"] == "completed0" or
                                x["group"] == "invoker0",
                           _parse_kafka_output(output_str)))

    if len(output_parsed) != 2:
        raise Exception("Kafka stats didn't contain data for both invoker0 and completed0 groups")

    res: Dict[str, int] = {}
    for o in output_parsed:
        if o["group"] == "completed0":
            res["completed0"] = int(o["lag"])
        elif o["group"] == "invoker0":
            res["invoker0"] = int(o["lag"])
        else:
            raise Exception("Invalid group name in kafka output")

    return res

def _reset_openwhisk():
    ansible_path = os.path.join(OPENWHISK_PATH, "ansible")
    environment = os.path.join(ansible_path, "environments", "local")
    playbook = os.path.join(ansible_path, "invoker.yml")

    ansible_call = ["ansible-playbook",
                    "-i",
                    environment,
                    "-e",
                    "skip_pull_runtimes=True",
                    playbook]

    subprocess.check_call(ansible_call, cwd = ansible_path)

def _hash_list(ls: List[str]):
    m = hashlib.sha256()
    for l in ls:
        m.update(l.encode(ENCODING))
    return m.hexdigest()

def _wait_for_openwhisk_backlog():
    kafka_container = _get_docker_container_by_image("kafka")
    while True:
        kafka_stats = _get_kafka_queue_stats(kafka_container)
        if kafka_stats["completed0"] == 0 and kafka_stats["invoker0"] == 0:
            break
        sleep(10)


class WorkloadSuite:

    def __init__(self,
                 workload_config: str,
                 invocation_type: InvocationType,
                 repeat_times: int) -> None:
        self.workload_config = workload_config
        self.invocation_type = invocation_type
        self.repeat_times = repeat_times

    @staticmethod
    def _write_suite_metadata(metadata):
        destfile = os.path.join(
            util.ensure_directory_exists(
                os.path.join(DATA_DIR, "suite_%s" % metadata["suiteid"])),
            "metadata.json")
        with open(destfile, 'w') as f:
            f.write(json.dumps(metadata))

    def _run_workload(self, workload):
        invoker = WorkloadInvoker()
        if self.invocation_type is InvocationType.COLD:
            _reset_openwhisk()
        run_metadata = invoker.invoke_benchmark(workload)
        _wait_for_openwhisk_backlog()
        return run_metadata

    def run_suite(self) -> str:
        _reset_openwhisk()

        # Do warmup run
        if self.invocation_type is InvocationType.WARM:
            self._run_workload(self.workload_config)

        invocations = map(self._run_workload,
                          [self.workload_config]*self.repeat_times)
        invocation_stats = map(lambda x: (x["runid"], x["successes"], x["failures"],
                                     x["expected"]), invocations)
        runids, successes, failures, expected = map(list, zip(*invocation_stats))

        suiteid = _hash_list(runids)[0:14]
        total_successes = sum(successes)
        total_failures = sum(failures)
        total_expected = sum(expected)

        metadata = {'suiteid': suiteid,
                    'benchmark': self.workload_config,
                    'total_successes': total_successes,
                    'total_failures': total_failures,
                    'total_expected': total_expected}

        self._write_suite_metadata(metadata)

        print("Finished running suite with runid %s, successes %s, failures %s, expected %s" %
              (suiteid, total_successes, total_failures, total_expected))
        print("runids: %s" % str(runids))
        return suiteid
