import os
import random
import time

from GenConfigs import *

def ensure_directory_exists(d: str) -> str:
    if not os.path.isdir(d):
        if os.path.exists(d):
            raise Exception("Path %s exists but is not a directory" % d)
        os.mkdir(d)
    return d

def gen_random_hex_string(l: int) -> str:
    st = random.getstate()
    random.seed(time.time())
    val = "%10x" % random.getrandbits(l * 8)
    random.setstate(st)
    return val

def get_suite_metadata_file(suiteid: str) -> str:
    return os.path.join(
        ensure_directory_exists(
            os.path.join(DATA_DIR, "suite_%s" % suiteid)),
        "metadata.json")
