#!/bin/bash
set -e

echo "[prometheus/install.sh] Installing Prometheus on Ubuntu 22.04..."

# Update package list and install required dependencies.
echo "$ASKHELPER_PASS" | sudo -S apt-get update
echo "$ASKHELPER_PASS" | sudo -S apt-get install -y wget tar

# Download Prometheus (adjust version if necessary)
PROM_VERSION="2.42.0"
wget https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz

# Extract and install Prometheus
tar -xzf prometheus-${PROM_VERSION}.linux-amd64.tar.gz
cd prometheus-${PROM_VERSION}.linux-amd64

# Move binaries to /usr/local/bin (adjust paths as needed)
echo "$ASKHELPER_PASS" | sudo -S cp prometheus promtool /usr/local/bin/

# Create Prometheus configuration directory and copy config file
echo "$ASKHELPER_PASS" | sudo -S mkdir -p /etc/prometheus
echo "$ASKHELPER_PASS" | sudo -S cp prometheus.yml /etc/prometheus/

# (Optionally) set up Prometheus as a system service here or simply run it in the background.
# For example, to run Prometheus in the background:
nohup ./prometheus --config.file=/etc/prometheus/prometheus.yml > prometheus.log 2>&1 &

echo "[prometheus/install.sh] Prometheus installation complete."
