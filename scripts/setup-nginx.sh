#!/bin/bash
# Setup Nginx as reverse proxy for Jarvis

set -e

echo "=== Nginx Setup Script ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or with sudo"
    exit 1
fi

# Install Nginx
echo "Installing Nginx..."
if command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y nginx
elif command -v dnf &> /dev/null; then
    dnf install -y nginx
elif command -v yum &> /dev/null; then
    yum install -y nginx
else
    echo "Unsupported package manager"
    exit 1
fi

# Generate SSL certificate
echo "Generating SSL certificate..."
./generate-ssl.sh

# Copy Nginx configuration
echo "Copying Nginx configuration..."
cp ../nginx/jarvis.conf /etc/nginx/conf.d/jarvis.conf

# Remove default site if it exists
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
rm -f /etc/nginx/conf.d/default.conf 2>/dev/null || true

# Test Nginx configuration
echo "Testing Nginx configuration..."
nginx -t

# Enable and restart Nginx
echo "Starting Nginx..."
systemctl enable nginx
systemctl restart nginx

echo ""
echo "=== Setup Complete ==="
echo "Nginx is now running with HTTPS on port 443"
echo "Access Jarvis at: https://$(hostname -I | awk '{print $1}')"
