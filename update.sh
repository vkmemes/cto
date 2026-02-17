#!/bin/bash
set -e

echo "🔄 Проверка обновлений..."
cd /opt/sttec

# Проверяем есть ли обновления
git fetch origin main
if [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ]; then
    echo "✅ Обновлений нет"
    exit 0
fi

echo "📦 Найдены обновления, обновляем..."

# Пролистываем изменения
git pull origin main

# Устанавливаем зависимости
if [ -f requirements.txt ]; then
    echo "📦 Установка зависимостей..."
    pip3 install -r requirements.txt
fi

# Пересоздаем БД если нужно (миграции)
if [ -f migrate.py ]; then
    echo "🗄 Миграция БД..."
    python3 migrate.py 2>/dev/null || true
fi

# Перезапускаем сервисы
echo "🔄 Перезапуск сервисов..."
systemctl restart sttec-bot sttec-web

echo "✅ Обновление завершено!"
echo "🌐 https://sttec.loca.lt"
