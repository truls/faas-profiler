from enum import Enum, unique
from typing import Any, Dict, List, TypedDict


@unique
class InvocationType(str, Enum):
    WARM = "warm"
    COLD = "cold"
    QUICK = "quick"


class WorkloadGroupSpec(TypedDict):
    """The format of a group specification used as input to the
    benchmarking processes;
    """
    group_name: str
    invocation_type: InvocationType
    repeat_times: int
    benchmarks: List[str]


class InvocationMetadata(TypedDict):
    """The specification of the metadata associated with an individual
benchmarking run.
    """
    start_time: int
    workload_name: str
    test_config: Dict[str, Any]
    event_count: int
    commit_hash: str
    runid: str
    runtime_script: bool
    failures: int
    successes: int
    expected: int

class WorkloadSuiteMetadata(TypedDict):
    """The specification of the metadata associated with a workload suite.

    """
    suiteid: str
    benchmark_name: str
    benchmarks: List[InvocationMetadata]
    mode: InvocationType
    runids: List[str]
    repeats: int
    total_successes: int
    total_failures: int
    total_expected: int
