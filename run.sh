#!/bin/bash

# TeamCyberOps Web Crawler - Setup & Launch Script for Linux/Mac

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     TeamCyberOps Crawler Dashboard v1.0 - Setup Script         ║"
echo "║              GitHub: @mohidqx                                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed"
    echo "Please install Python 3.8+ from https://www.python.org"
    exit 1
fi

echo "✅ Python found!"
python3 --version

echo ""
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    exit 1
fi

echo ""
echo "✅ Dependencies installed successfully!"
echo ""
echo "🚀 Launching TeamCyberOps Crawler Dashboard..."
echo ""

python3 app_advanced.py
