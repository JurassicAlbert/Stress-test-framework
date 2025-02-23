#!/bin/bash
set -e

echo "[grafana/install.sh] Installing Grafana on Ubuntu 22.04..."

# Update package list and install required dependencies.
echo "$ASKHELPER_PASS" | sudo -S apt-get update
echo "$ASKHELPER_PASS" | sudo -S apt-get install -y apt-transport-https software-properties-common wget

# Add the Grafana APT repository
echo "$ASKHELPER_PASS" | sudo -S wget -q -O - https://packages.grafana.com/gpg.key | sudo -S apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list

# Install Grafana
echo "$ASKHELPER_PASS" | sudo -S apt-get update
echo "$ASKHELPER_PASS" | sudo -S apt-get install -y grafana

# Start Grafana (as a service, if configured) or run in the background.
# To start as a service:
echo "$ASKHELPER_PASS" | sudo -S systemctl start grafana-server
echo "$ASKHELPER_PASS" | sudo -S systemctl enable grafana-server

echo "[grafana/install.sh] Grafana installation complete."
