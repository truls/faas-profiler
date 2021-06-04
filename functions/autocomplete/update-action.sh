#!/bin/bash

set -xeuo pipefail

wsk="$(which wsk) -i"

action="autocomplete"

res="$($wsk action list)"
if echo "$res" | grep -q "$action"; then
   $wsk action delete "$action"/uspresidents
fi

bin/acsetup.js data/uspresidents.txt

curl "https://localhost/api/v1/web/guest/$action/uspresidents?runid=foo&term=a" -k -v

# curl -X POST -H "Content-Type: application/json" --data-binary @./declaration.json "https://localhost/api/v1/web/guest/default/$action?foo&bar=baz" -k -v

#wsk action invoke "$action" -i -P openpiton-readme.json -r -v
