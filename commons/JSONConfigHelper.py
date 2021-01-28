# Copyright (c) 2019 Princeton University
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import json
import os

# Local imports
from GenConfigs import *


def check_json_config(json_file):
    """
    Checks whether a correct json file is provided.
    """
    if json_file is None:
        return False
    if not os.path.isfile(json_file):
        return False
    return True


def read_json_config(json_file):
    """
    Reads the JSON config file and returns a list.
    """
    workload = None
    try:
        with open(json_file) as f:
            workload = json.load(f)
    except:
        raise Exception("The JSON config file cannot be read")

    return workload


def WriteJSONConfig(workload, json_file):
    """
    Writes the workload description to a json file.
    """
    with open(FAAS_ROOT + '/' + json_file, 'w') as outfile:
        json.dump(workload, outfile)
