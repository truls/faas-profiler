#!/usr/bin/env bash

set -euo pipefail

# This script sets some universal parameters.
# It should be run oly once.

# Installing some dependencies if needed
sudo apt-get install -y moreutils
sudo python3.6 -m pip install -r requirements.txt

# Configure path variables used by the platform 
ROOTLINE="FAAS_ROOT=\"$(echo $PWD)\""
echo "$ROOTLINE" >> GenConfigs.py
echo "WSK_PATH = \"$(which wsk)\"" >> GenConfigs.py
echo "OPENWHISK_PATH = \"CHANGE_ME\"" >> GenConfig.py

# Configure root path
echo $ROOTLINE | cat - invocation-scripts/monitoring.sh | sponge invocation-scripts/monitoring.sh
echo $ROOTLINE | cat - monitoring/RuntimeMonitoring.sh | sponge monitoring/RuntimeMonitoring.sh

# Make local directories
mkdir -p logs
mkdir -p data_archive
