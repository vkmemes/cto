#!/bin/bash
set -e

# === НАСТРОЙКИ (измени это!) ===
SERVER_USER="root"                    # пользователь на сервере
SERVER_IP="192.168.1.100"             # IP адрес сервера
SERVER_PATH="/opt/sttec"              # папка проекта на сервере
# ==================================

echo "🚀 Деплой STTEC на сервер..."
echo ""

# Копируем файлы
echo "📦 Копирование файлов..."
rsync -avz \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='*.db' \
    --exclude='logs/' \
    --exclude='node_modules/' \
    . ${SERVER_USER}@${SERVER_IP}:${SERVER_PATH}/

# Перезапуск сервисов на сервере
echo "🔄 Перезапуск сервисов..."
ssh ${SERVER_USER}@${SERVER_IP} << 'EOF'
    cd /opt/sttec

    # Установка зависимостей (если изменился requirements.txt)
    if [ -f requirements.txt ]; then
        pip3 install -r requirements.txt
    fi

    # Перезапуск сервисов
    systemctl restart sttec-bot sttec-web sttec-tunnel 2>/dev/null || true

    echo "✅ Сервисы перезапущены"
EOF

echo ""
echo "🎉 Деплой завершен успешно!"
echo "🌐 Веб доступен: https://sttec.loca.lt"
