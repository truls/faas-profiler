# Copyright (c) 2019 Princeton University
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from markdown import markdown
import base64
import json
import base64

def main(params):
    try:
        md = json.loads(base64.decodebytes(params["__ow_body"].encode("utf-8")))["markdown"].encode("utf-8")
        md_text = base64.decodebytes(md).decode("utf-8")
    except KeyError:
        return {'Error' : 'Possibly lacking markdown parameter in request.'}

    test_id = params["__ow_query"]

    html = markdown(md_text)

    return {"result": "ok", "html_response": html, "testid": test_id}
