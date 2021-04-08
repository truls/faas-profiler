#!/bin/bash

set -xeuo pipefail

wsk="$(which wsk) -i"

res="$($wsk action list)"
if echo "$res" | grep -q img-resize; then
   $wsk action delete img-resize
fi

zip -r action.zip ./* > /dev/null
$wsk action create img-resize --kind nodejs:10 action.zip --web raw -i
curl -X POST -H "Content-Type: image/png" --data-binary @./piton.png https://localhost/api/v1/web/guest/default/img-resize?runid=foobar -k -v
