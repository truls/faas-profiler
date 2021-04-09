# Copyright (c) 2019 Princeton University
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import sys
import json
import base64
from textblob import TextBlob

def main(params):

    try:
        analyse_input = json.loads(base64.decodebytes(params["__ow_body"].encode("utf-8")))["analyse"]
        analyse = TextBlob(analyse_input)
    except KeyError:
        return {'Error' : 'Input parameters should include a string to sentiment analyse.'}

    test_id = params["__ow_query"]

    sentences = len(analyse.sentences)

    retVal = {}

    retVal["subjectivity"] = sum([sentence.sentiment.subjectivity for sentence in analyse.sentences]) / sentences
    retVal["polarity"] = sum([sentence.sentiment.polarity for sentence in analyse.sentences]) / sentences
    retVal["sentences"] = sentences

    return {"result": "ok", "response": retVal, "testid": test_id}
