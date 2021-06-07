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
from enum import Enum, unique
from synthetic_workload_invoker.datatypes import InvocationType, WorkloadGroupSpec, WorkloadSuiteMetadata
from synthetic_workload_invoker.WorkloadInvoker import InvocationMetadata, WorkloadInvoker
from time import sleep
import hashlib
import yaml
from typing import Any, Dict, List, TypedDict

import docker

from commons import util
from GenConfigs import *

ENCODING = "utf-8"

def _get_docker_container_by_image(image):

    containers: List[Any]
    # There is probably a race condition within the docker API. Retry
    # until we succeed
    while True:
        try:
            client = docker.from_env()
            containers = client.containers.list()
        except docker.errors.NotFound:
            pass
        else:
            break;

    target = list(filter(lambda x: any(map(lambda y: image in y, x.image.tags)), containers))
    if len(target) == 0:
        raise Exception("No docker containers with image matching %s" % image)
    if len(target) > 1:
        raise Exception("Multiple docker containers matches %s" % image)

    return target[0]

def _parse_kafka_output(kafka_output: str) -> List[Dict[str, str]]:
    data_lines = filter(lambda x: not (x.startswith("GROUP") or (x.strip() == "")) ,
                        kafka_output.splitlines())

    data_lines_split = filter(lambda x: len(x) >= 9,
                             map(lambda l: re.split(" +", l.strip()),
                                 data_lines))

    return list(map(lambda x: {'group': x[0],
                          'topic': x[1],
                          'partition': x[2],
                          'current-offset': x[3],
                          'log-end-offset': x[4],
                          'lag': x[5],
                          'consumer-id': x[6],
                          'host': x[7],
                          'client-id': x[8]},
                    data_lines_split))


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
        destfile = util.get_suite_metadata_file(metadata["suiteid"])
        with open(destfile, 'w') as f:
            f.write(json.dumps(metadata))


    def _run_workload(self, workload) -> InvocationMetadata:
        invoker = WorkloadInvoker()
        if self.invocation_type is InvocationType.COLD:
            _reset_openwhisk()
        run_metadata = invoker.invoke_benchmark(workload)
        _wait_for_openwhisk_backlog()
        return run_metadata

    def run_suite(self) -> WorkloadSuiteMetadata:
        print(f"Invoking suite ")

        if not self.invocation_type is InvocationType.QUICK:
            _reset_openwhisk()

        # Do warmup run
        if self.invocation_type is InvocationType.WARM:
            self._run_workload(self.workload_config)

        invocations = list(map(self._run_workload,
                               [self.workload_config]*self.repeat_times))
        invocation_stats = map(lambda x: (x["runid"], x["successes"], x["failures"],
                                     x["expected"]), invocations)
        runids, successes, failures, expected = map(list, zip(*invocation_stats))

        suiteid = _hash_list(runids)[0:14]
        total_successes = sum(successes)
        total_failures = sum(failures)
        total_expected = sum(expected)

        workload_name = invocations[0]["workload_name"]

        metadata: WorkloadSuiteMetadata = {'suiteid': suiteid,
                                           "benchmark_name": workload_name,
                                           'benchmarks': invocations,
                                           'runids': runids,
                                           'mode': self.invocation_type,
                                           'repeats': self.repeat_times,
                                           'total_successes': total_successes,
                                           'total_failures': total_failures,
                                           'total_expected': total_expected}

        self._write_suite_metadata(metadata)

        return metadata


class WorkloadGroup:

    def __init__(self, workload_group: str):
        path = os.path.join(FAAS_ROOT, workload_group)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        self.workload_group = path

    @staticmethod
    def _write_group_metadata(group: WorkloadGroupSpec,
                              workloads: List[WorkloadSuiteMetadata]) -> None:
        data: Dict[str, Any] = {}
        data["benchmarks"] = list(
            map(lambda x:
                {"test_name": x["benchmark_name"],
                 "suiteid": x["suiteid"]}, workloads)
        )
        data["group_name"] = group["group_name"]
        data["invocation_type"] = group["invocation_type"]

        destfile = os.path.join(
            util.ensure_directory_exists(DATA_DIR),
            "group_%s.json" % group["group_name"])

        with open(destfile, 'w') as f:
            f.write(json.dumps(data))

    def run_group(self) -> List[WorkloadSuiteMetadata]:
        print(f"Opening workload group {self.workload_group}")
        with open(self.workload_group, "r") as f:
            group_config: WorkloadGroupSpec = yaml.safe_load(f)
            group_config["invocation_type"] = InvocationType(group_config["invocation_type"])

        # Ensure that all referenced files exists
        paths = list(map(lambda x: os.path.join(WORKLOAD_SPECS, f"{x}.json"),
                         group_config["benchmarks"]))

        for p in paths:
            if not os.path.exists(p):
                raise FileNotFoundError(f"No such file {p}")

        print("Running group: ", paths)

        suites = list(
            map(lambda p: WorkloadSuite(p, group_config["invocation_type"],
                                   group_config["repeat_times"]).run_suite(),
                paths))

        self._write_group_metadata(group_config, suites)

        return suites
