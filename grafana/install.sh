#!/usr/bin/env bash
set -e

if [ -z "$ASKHELPER_PASS" ]; then
  echo "[grafana/install.sh] ASKHELPER_PASS is not set. Exiting..."
  exit 1
fi

echo "[grafana/install.sh] Installing Grafana on Ubuntu 22.04..."

# 1) Update & install dependencies
echo "$ASKHELPER_PASS" | sudo -S apt-get update -y
echo "$ASKHELPER_PASS" | sudo -S apt-get install -y wget apt-transport-https software-properties-common

# 2) Add GPG key & repo for Grafana
wget -q -O - https://packages.grafana.com/gpg.key | echo "$ASKHELPER_PASS" | sudo -S apt-key add -
echo "$ASKHELPER_PASS" | sudo -S add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"

# 3) Install Grafana
echo "$ASKHELPER_PASS" | sudo -S apt-get update -y
echo "$ASKHELPER_PASS" | sudo -S apt-get install -y grafana

# 4) Start & enable service
echo "$ASKHELPER_PASS" | sudo -S systemctl daemon-reload
echo "$ASKHELPER_PASS" | sudo -S systemctl enable grafana-server
echo "$ASKHELPER_PASS" | sudo -S systemctl start grafana-server

echo "[grafana/install.sh] Grafana installed and started on port 3000 (default admin/admin)."
