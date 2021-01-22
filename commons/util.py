import os
import random
import time

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
