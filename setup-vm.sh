#!/usr/bin/env bash
set -e

echo "=== 🚀 Forex Bot Google Cloud VM Setup ==="

# 1. Update packages and install python3-venv & git
echo "📦 Installing system dependencies..."
sudo apt update -y
sudo apt install -y python3-pip python3-venv git

# 2. Setup Virtual Environment
CURRENT_DIR="$(pwd)"
CURRENT_USER="$(whoami)"

echo "🐍 Creating virtual environment in $CURRENT_DIR/venv..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Create .env if not exists
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "⚙️ Creating .env from .env.example..."
        cp .env.example .env
    else
        touch .env
    fi
fi

# 4. Configure systemd service file dynamically with current user and path
SERVICE_FILE="/etc/systemd/system/forex-bot.service"
echo "🛠️ Creating systemd service unit at $SERVICE_FILE..."

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Forex Discord & YouTube Monitor Bot Daemon
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
EnvironmentFile=$CURRENT_DIR/.env
ExecStart=$CURRENT_DIR/venv/bin/python3 app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=forex-bot
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

# 5. Enable and start daemon
echo "🔄 Reloading systemd and enabling forex-bot daemon..."
sudo systemctl daemon-reload
sudo systemctl enable forex-bot.service
sudo systemctl restart forex-bot.service

echo ""
echo "=== ✅ Deployment Complete! ==="
echo "Status check:  sudo systemctl status forex-bot"
echo "Live logs:     sudo journalctl -u forex-bot -f"
echo "Restart bot:   sudo systemctl restart forex-bot"
echo "Stop bot:      sudo systemctl stop forex-bot"
