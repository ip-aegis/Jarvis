#!/bin/bash
# Generate self-signed SSL certificate for Jarvis

set -e

SSL_DIR="/etc/nginx/ssl"
CERT_FILE="$SSL_DIR/jarvis.crt"
KEY_FILE="$SSL_DIR/jarvis.key"

echo "Creating SSL directory..."
sudo mkdir -p "$SSL_DIR"

echo "Generating self-signed certificate..."
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/C=US/ST=State/L=City/O=Lab/OU=Jarvis/CN=jarvis.local"

echo "Setting permissions..."
sudo chmod 600 "$KEY_FILE"
sudo chmod 644 "$CERT_FILE"

echo "SSL certificate generated successfully!"
echo "  Certificate: $CERT_FILE"
echo "  Private Key: $KEY_FILE"
