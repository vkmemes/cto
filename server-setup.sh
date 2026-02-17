#!/bin/bash
set -e

echo "🔧 Первичная настройка сервера..."
echo ""

# === НАСТРОЙКИ (измени!) ===
GITHUB_REPO="https://github.com/твой-юзер/твой-репозиторий.git"
BRANCH="main"
# =================================

# Установка зависимостей
echo "📦 Установка зависимостей..."
apt update
apt install -y python3 python3-pip git sqlite3

# Установка Node.js для localtunnel
echo "📦 Установка Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# Установка localtunnel
echo "📦 Установка localtunnel..."
npm install -g localtunnel

# Клонирование репозитория
echo "📥 Клонирование репозитория..."
git clone ${GITHUB_REPO} /opt/sttec
cd /opt/sttec
git checkout ${BRANCH}

# Установка Python зависимостей
echo "📦 Установка Python библиотек..."
if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt
fi

# Создание папок
mkdir -p logs templates

# Создание пустой БД
echo "🗄 Создание базы данных..."
if [ -f migrate.py ]; then
    python3 migrate.py 2>/dev/null || true
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

# Делаем update.sh исполняемым
if [ -f update.sh ]; then
    chmod +x update.sh
fi

# Активация сервисов
systemctl daemon-reload
systemctl enable sttec-bot sttec-web sttec-tunnel

# Добавление в cron (каждые 5 минут)
echo "⏰ Настройка автодеплоя..."
(crontab -l 2>/dev/null | grep -v "/opt/sttec/update.sh"; echo "*/5 * * * * /opt/sttec/update.sh >> /opt/sttec/logs/update.log 2>&1") | crontab -

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "Запуск сервисов..."
systemctl start sttec-bot sttec-web sttec-tunnel

echo ""
echo "🎉 Сервер готов!"
echo "🌐 Веб доступен: https://sttec.loca.lt"
echo ""
echo "Сервер будет автоматически проверять обновления каждые 5 минут"
