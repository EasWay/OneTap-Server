#!/bin/bash

# Render build script for YouTube downloader with Deno support

echo "🚀 Starting Render build process..."

# Install system dependencies
echo "📦 Installing system dependencies..."
apt-get update
apt-get install -y wget curl unzip xvfb

# Install Chrome
echo "🌐 Installing Google Chrome..."
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt-get install -y ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb

# Install Deno
echo "🦕 Installing Deno JavaScript runtime..."
curl -fsSL https://deno.land/x/install/install.sh | sh
export DENO_INSTALL="/opt/render/.deno"
export PATH="$DENO_INSTALL/bin:$PATH"

# Verify installations
echo "✅ Verifying installations..."
google-chrome --version
deno --version

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip install -r requirements.txt

echo "🎉 Build completed successfully!"