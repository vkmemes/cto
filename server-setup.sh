#!/bin/bash
set -e

echo "🔧 Первичная настройка сервера..."
echo ""

# Установка зависимостей
echo "📦 Установка Python и Git..."
apt update
apt install -y python3 python3-pip git sqlite3

# Установка Node.js для localtunnel
echo "📦 Установка Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# Установка localtunnel
echo "📦 Установка localtunnel..."
npm install -g localtunnel

# Создание папки проекта
mkdir -p /opt/sttec
cd /opt/sttec

# Создание папок
mkdir -p logs templates

# Установка Python зависимостей
echo "📦 Установка Python библиотек..."
if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt
fi

# Создание пустой БД
echo "🗄 Создание базы данных..."
if [ ! -f sttec.db ]; then
    python3 -c "from database import db; import asyncio; asyncio.run(db.init_db())" 2>/dev/null || true
fi

# Создание systemd сервисов
echo "⚙️ Настройка системных сервисов..."

# 1. Сервис бота
cat > /etc/systemd/system/sttec-bot.service << 'EOF'
[Unit]
Description=STTEC Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/sttec
ExecStart=/usr/bin/python3 /opt/sttec/bot_main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 2. Сервис веб-сервера
cat > /etc/systemd/system/sttec-web.service << 'EOF'
[Unit]
Description=STTEC Web Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/sttec
ExecStart=/usr/bin/python3 -m uvicorn web_main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 3. Сервис localtunnel
cat > /etc/systemd/system/sttec-tunnel.service << 'EOF'
[Unit]
Description=STTEC LocalTunnel
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/sttec
ExecStart=/usr/local/bin/lt --port 8000 --subdomain sttec
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Активация сервисов
systemctl daemon-reload
systemctl enable sttec-bot sttec-web sttec-tunnel

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "Теперь скопируй файлы проекта и запусти:"
echo "  cd /opt/sttec"
echo "  systemctl start sttec-bot sttec-web sttec-tunnel"
echo ""
