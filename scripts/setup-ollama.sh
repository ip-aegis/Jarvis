#!/bin/bash
# Setup Ollama on Alpha (10.10.20.62)
# Run this script on the Alpha server

set -e

echo "=== Ollama Setup Script for Alpha ==="
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo"
    exit 1
fi

# Install Ollama
echo "Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh

# Configure Ollama to listen on all interfaces
echo "Configuring Ollama service..."
mkdir -p /etc/systemd/system/ollama.service.d/

cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
EOF

# Reload and restart
systemctl daemon-reload
systemctl enable ollama
systemctl restart ollama

# Wait for Ollama to start
echo "Waiting for Ollama to start..."
sleep 5

# Pull the model
echo "Pulling Llama 3.1 8B model..."
ollama pull llama3.1:8b

echo ""
echo "=== Setup Complete ==="
echo "Ollama is now running on 0.0.0.0:11434"
echo "Model: llama3.1:8b"
echo ""
echo "Test with: curl http://localhost:11434/api/tags"
