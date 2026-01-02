#!/bin/bash
# Jarvis Agent Installation Script
# This is copied to remote servers during onboarding

set -e

JARVIS_URL="${JARVIS_URL:-http://10.10.20.235:8000}"
SERVER_ID="${SERVER_ID:-$(hostname)}"

echo "=== Jarvis Agent Installation ==="
echo "Jarvis URL: $JARVIS_URL"
echo "Server ID: $SERVER_ID"
echo ""

# Create directory
mkdir -p /opt/jarvis

# Download agent (or it's already copied by Jarvis)
if [ ! -f /opt/jarvis/agent.py ]; then
    echo "Agent script not found. It should be copied by Jarvis during onboarding."
    exit 1
fi

chmod +x /opt/jarvis/agent.py

# Create systemd service
cat > /etc/systemd/system/jarvis-agent.service << EOF
[Unit]
Description=Jarvis Monitoring Agent
After=network.target

[Service]
Type=simple
User=root
Environment="JARVIS_URL=$JARVIS_URL"
Environment="SERVER_ID=$SERVER_ID"
Environment="REPORT_INTERVAL=5"
ExecStart=/usr/bin/python3 /opt/jarvis/agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
systemctl daemon-reload
systemctl enable jarvis-agent
systemctl start jarvis-agent

echo ""
echo "=== Installation Complete ==="
systemctl status jarvis-agent --no-pager
