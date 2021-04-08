#!/bin/bash

set -xeuo pipefail

wsk="$(which wsk) -i"

res="$($wsk action list)"
if echo "$res" | grep -q ocr-img; then
   $wsk action delete ocr-img
fi

wsk action create ocr-img handler.js --docker immortalfaas/nodejs-tesseract --web raw -i

curl -X POST -H "Content-Type: image/png" --data-binary @./pitontable.png https://localhost/api/v1/web/guest/default/ocr-img?foobar -k -v
