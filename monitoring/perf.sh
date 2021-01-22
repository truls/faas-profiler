#!/bin/bash

set -euo pipefail

# This script uses the Linux "perf" tool to gather certain information.

test_duration="$1"
perf_sampling_interval="$2"
test_outdir="$3"
parent_pid="$4"

# Notes:
# 1. The events listed below are just some of the examples. You can find the full list of events by running `perf list`.
# 2. It is usually recommended to go for fewer events to ensure low profiling overhead.

echo "Running perf for $test_duration seconds"

sudo perf stat -a -e cpu-cycles,L1-dcache-loads,L1-dcache-load-misses,L1-icache-load-misses,LLC-load-misses,dTLB-load-misses,dTLB-loads,iTLB-load-misses,iTLB-loads,branch-misses,context-switches,cpu-migrations,page-faults,instructions -I "$perf_sampling_interval" -o "$test_outdir/perf-mon.out" -x ',' wait "$parent_pid"
