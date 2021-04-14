#!/bin/bash

set -xeuo pipefail

wsk="$(which wsk) -i"

action="sentiment"

res="$($wsk action list)"
if echo "$res" | grep -q "$action"; then
   $wsk action delete "$action"
fi

wsk action create "$action" sentiment.py --docker immortalfaas/sentiment --web raw -i

curl -X POST -H "Content-Type: application/json" --data-binary @./declaration.json "https://localhost/api/v1/web/guest/default/$action?foo&bar=baz" -k -v

#wsk action invoke "$action" -i -P openpiton-readme.json -r -v
