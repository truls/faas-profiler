#!/bin/bash

set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [ $# -ne 2 ]; then
    echo "Usage: ./runtime_monitoring.sh <test duration (s)> <output directory>"
    exit 1
fi

TEST_DURATION="$1"

TEST_OUTDIR="$2"

PERF_SAMPLING_INTERVAL=120  # ms (min = 10ms)
PQOS_SAMPLING_INTERVAL=1    # set sampling interval to Nx100ms

# Clear existing output files
# sudo rm -rf *.out

# Run monitoring scripts
# << Uncomment any or all of the default scripts below to use them. >>
"$DIR/perf.sh" "$TEST_DURATION" "$PERF_SAMPLING_INTERVAL" "$TEST_OUTDIR" &
script1=$!
# bash $FAAS_ROOT'/monitoring/PQOSMon.sh' $TEST_DURATION $PQOS_SAMPLING_INTERVAL &
# bash $FAAS_ROOT'/monitoring/Blktrace.sh' $TEST_DURATION &

wait $script1
