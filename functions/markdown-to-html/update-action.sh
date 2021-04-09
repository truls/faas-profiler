#!/bin/bash

set -xeuo pipefail

wsk="$(which wsk) -i"

action="markdown2html"

res="$($wsk action list)"
if echo "$res" | grep -q "$action"; then
   $wsk action delete "$action"
fi

wsk action create "$action" markdown2html.py --docker immortalfaas/markdown-to-html --web raw -i

curl -X POST -H "Content-Type: application/json" --data-binary @./openpiton-readme.json "https://localhost/api/v1/web/guest/default/$action?foo" -k -v

#wsk action invoke "$action" -i -P openpiton-readme.json -r -v
