#!/usr/bin/env bash
set -e

if [ -z "$ASKHELPER_PASS" ]; then
  echo "[prometheus/install.sh] ASKHELPER_PASS is not set. Exiting..."
  exit 1
fi

echo "[prometheus/install.sh] Installing Prometheus on Ubuntu 22.04..."

# 1) Update & install dependencies
echo "$ASKHELPER_PASS" | sudo -S apt-get update -y
echo "$ASKHELPER_PASS" | sudo -S apt-get install -y wget tar

# 2) Download Prometheus (example version)
PROM_VERSION="2.42.0"
PROM_ARCHIVE="prometheus-${PROM_VERSION}.linux-amd64.tar.gz"

wget https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/${PROM_ARCHIVE}
tar -xzf ${PROM_ARCHIVE}
cd prometheus-${PROM_VERSION}.linux-amd64

# 3) Move binaries
echo "$ASKHELPER_PASS" | sudo -S mv prometheus promtool /usr/local/bin/
echo "$ASKHELPER_PASS" | sudo -S mkdir -p /etc/prometheus
echo "$ASKHELPER_PASS" | sudo -S mkdir -p /var/lib/prometheus

# 4) Basic config (using the included example config)
# If you have a custom config, adapt as needed
echo "$ASKHELPER_PASS" | sudo -S cp prometheus.yml /etc/prometheus/prometheus.yml

# 5) Create a systemd service
echo "$ASKHELPER_PASS" | sudo -S tee /etc/systemd/system/prometheus.service >/dev/null <<EOF
[Unit]
Description=Prometheus Service
After=network.target

[Service]
User=root
ExecStart=/usr/local/bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/var/lib/prometheus \
  --web.listen-address=:9090
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 6) Start service
echo "$ASKHELPER_PASS" | sudo -S systemctl daemon-reload
echo "$ASKHELPER_PASS" | sudo -S systemctl enable prometheus
echo "$ASKHELPER_PASS" | sudo -S systemctl start prometheus

echo "[prometheus/install.sh] Prometheus installed and started on port 9090."
