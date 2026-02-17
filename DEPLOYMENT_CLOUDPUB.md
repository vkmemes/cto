# Деплой ЯГК Schedule через SSH с туннелированием Cloudflare Tunnel

> 💡 **Нужен бесплатный доступ без привязки карты?** Смотрите [DEPLOYMENT_ALTERNATIVES.md](DEPLOYMENT_ALTERNATIVES.md) для бесплатных альтернатив: LocalTunnel, ngrok, serveo.net, SSH tunnels и других решений.

## 📋 Общая схема

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   GitHub    │────▶│  Ваш ПК     │────▶│ Cloudflare  │────▶│ Локальный   │
│  (код)      │     │  (деплой)   │     │  (туннель)  │     │   сервер    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                                              │
                           │                                              │
                           ▼                                              ▼
                    ┌─────────────┐                              ┌─────────────┐
                    │   SSH ключ  │                              │  systemd    │
                    │  (для подкл)│                              │  сервисы    │
                    └─────────────┘                              └─────────────┘
```

## 🔧 Подготовка

### 1. Установка Cloudflare Tunnel на локальном сервере

На вашем локальном сервере (например, домашний ПК или Raspberry Pi):

```bash
# Скачать и установить cloudflared (официальный клиент Cloudflare)

# Для Debian/Ubuntu:
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Для Raspberry Pi (ARM):
wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared-linux-arm64.deb

# Или через скачивание бинарника:
# wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
# chmod +x cloudflared-linux-amd64
# sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
```

### 2. Аутентификация в Cloudflare

```bash
# Логин в Cloudflare (откроет браузер для авторизации)
cloudflared tunnel login

# После авторизации будет создан сертификат:
# ~/.cloudflared/cert.pem
# Сохраните его — он понадобится для управления туннелями
```

**Требования:**
- Аккаунт Cloudflare (бесплатный)
- Домен, делегированный на Cloudflare (DNS записи)

### 3. Создание туннеля для SSH

```bash
# Создание туннеля (замените ygk-ssh на любое имя)
cloudflared tunnel create ygk-ssh

# Получите Tunnel ID (UUID), например:
# Tunnel credentials written to /home/user/.cloudflared/<UUID>.json
# Your tunnel credentials will be located in:
# /home/user/.cloudflared/<UUID>.json

# Сохраните UUID — он понадобится для настройки
```

### 4. Настройка конфигурации туннеля

Создайте файл `~/.cloudflared/config.yml`:

```yaml
tunnel: <YOUR_TUNNEL_UUID>
credentials-file: /home/user/.cloudflared/<YOUR_TUNNEL_UUID>.json

# SSH доступ через туннель
ingress:
  # SSH на порт 22
  - hostname: ssh.yourdomain.com
    service: ssh://localhost:22
  
  # Веб-интерфейс (опционально)
  - hostname: ygk.yourdomain.com
    service: http://localhost:8000
  
  # Fallback
  - service: http_status:404
```

Замените:
- `<YOUR_TUNNEL_UUID>` — UUID из шага 3
- `ssh.yourdomain.com` — ваш поддомен для SSH
- `ygk.yourdomain.com` — ваш поддомен для веб

### 5. Настройка DNS записей в Cloudflare

```bash
# Автоматическое создание DNS записей
cloudflared tunnel route dns ygk-ssh ssh.yourdomain.com
cloudflared tunnel route dns ygk-ssh ygk.yourdomain.com

# Или вручную в панели Cloudflare:
# Тип: CNAME
# Имя: ssh
# Цель: <UUID>.cfargotunnel.com
# 
# Тип: CNAME
# Имя: ygk
# Цель: <UUID>.cfargotunnel.com
```

### 6. Запуск туннеля как службы

```bash
# Установка службы systemd
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

# Проверка статуса
sudo systemctl status cloudflared
cloudflared tunnel info ygk-ssh
```

### 7. Настройка SSH для подключения через туннель

На вашей локальной машине (с которой будете деплоить):

```bash
# Установка cloudflared на клиентскую машину
# macOS:
brew install cloudflared

# Linux:
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared-linux-amd64
sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared

# Windows:
# Скачайте .exe с GitHub релизов
```

Добавьте в `~/.ssh/config`:

```
Host ygk-local
    HostName ssh.yourdomain.com
    User ygk
    IdentityFile ~/.ssh/ygk_deploy_key
    ProxyCommand cloudflared access ssh --hostname %h
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

### 8. Генерация SSH ключей для деплоя

На локальном сервере:

```bash
# Создание пользователя для деплоя
sudo useradd -m -s /bin/bash ygk

# Генерация ключей
sudo -u ygk mkdir -p /home/ygk/.ssh
sudo -u ygk ssh-keygen -t ed25519 -f /home/ygk/.ssh/deploy_key -N ""

# Добавление публичного ключа в authorized_keys
sudo -u ygk cat /home/ygk/.ssh/deploy_key.pub >> /home/ygk/.ssh/authorized_keys
sudo -u ygk chmod 600 /home/ygk/.ssh/authorized_keys

# Получение приватного ключа (скопируйте вывод)
sudo cat /home/ygk/.ssh/deploy_key
```

Сохраните приватный ключ в `~/.ssh/ygk_deploy_key` на вашем ПК.

## 🚀 Процесс деплоя

### Метод 1: Прямое копирование файлов (SCP)

```bash
# 1. Проверка подключения
ssh ygk-local "echo 'Подключение успешно!'"

# 2. Создание структуры директорий
ssh ygk-local "mkdir -p /opt/ygk/{backups,logs}"

# 3. Копирование файлов проекта
scp -r bot_main.py core.py database.py web_main.py migrate.py ygk-local:/opt/ygk/
scp -r requirements.txt .env schedule.json ygk-local:/opt/ygk/
scp -r templates/ ygk-local:/opt/ygk/
scp ygk-bot.service ygk-web.service ygk-local:/tmp/

# 4. Установка прав
ssh ygk-local "sudo chown -R ygk:ygk /opt/ygk"
```

### Метод 2: Деплой через Git (рекомендуется)

На локальном сервере (один раз):

```bash
# Установка Git
sudo apt update && sudo apt install -y git

# Создание bare-репозитория
sudo mkdir -p /opt/git/ygk.git
sudo git init --bare /opt/git/ygk.git

# Создание hook для автодеплоя
sudo tee /opt/git/ygk.git/hooks/post-receive << 'EOF'
#!/bin/bash
TARGET="/opt/ygk"
GIT_DIR="/opt/git/ygk.git"
BRANCH="main"

while read oldrev newrev ref
do
    if [[ $ref = refs/heads/$BRANCH ]]; then
        echo "Deploying $BRANCH to production..."
        git --work-tree=$TARGET --git-dir=$GIT_DIR checkout -f $BRANCH
        
        # Перезапуск сервисов
        sudo systemctl restart ygk-bot ygk-web
        echo "Deployment complete!"
    fi
done
EOF

sudo chmod +x /opt/git/ygk.git/hooks/post-receive
sudo chown -R ygk:ygk /opt/git/ygk.git
```

На вашем ПК:

```bash
# Добавление remote через туннель
git remote add production ssh://ygk-local/opt/git/ygk.git

# Деплой
ssh ygk-local "sudo chown -R ygk:ygk /opt/ygk"
git push production main
```

## 📦 Скрипт автоматического деплоя

Создайте файл `deploy.sh` на вашем ПК:

```bash
#!/bin/bash

# Конфигурация
REMOTE_USER="ygk"
REMOTE_HOST="ygk-local"
REMOTE_DIR="/opt/ygk"
SERVICE_NAME_BOT="ygk-bot"
SERVICE_NAME_WEB="ygk-web"

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Начало деплоя ЯГК Schedule...${NC}"

# Проверка доступности сервера
echo -e "${YELLOW}📡 Проверка подключения...${NC}"
if ! ssh $REMOTE_HOST "echo 'OK'" > /dev/null 2>&1; then
    echo -e "${RED}❌ Ошибка: Не удалось подключиться к серверу через Cloudflare Tunnel${NC}"
    echo -e "${RED}   Убедитесь, что туннель активен: cloudflared tunnel info ygk-ssh${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Сервер доступен через туннель${NC}"

# Проверка изменений в Git
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}⚠️  Есть незакоммиченные изменения:${NC}"
    git status --short
    read -p "Продолжить деплой? (y/N): " confirm
    if [[ $confirm != [yY] ]]; then
        echo -e "${RED}❌ Деплой отменен${NC}"
        exit 0
    fi
fi

# Создание архива с проектом
echo -e "${YELLOW}📦 Создание архива...${NC}"
tar czf /tmp/ygk-deploy.tar.gz \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='venv' \
    --exclude='.venv' \
    --exclude='*.log' \
    --exclude='*.db' \
    --exclude='backups' \
    .

# Отправка файлов
echo -e "${YELLOW}📤 Отправка файлов на сервер...${NC}"
scp /tmp/ygk-deploy.tar.gz $REMOTE_HOST:/tmp/

# Распаковка и установка
echo -e "${YELLOW}🔧 Установка на сервере...${NC}"
ssh $REMOTE_HOST << 'REMOTE_COMMANDS'
    cd /opt/ygk
    
    # Остановка сервисов
    echo "Остановка сервисов..."
    sudo systemctl stop ygk-bot ygk-web || true
    
    # Резервная копия
    echo "Создание резервной копии..."
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p $BACKUP_DIR
    cp -r *.py *.json .env templates $BACKUP_DIR/ 2>/dev/null || true
    
    # Распаковка новой версии
    echo "Обновление файлов..."
    tar xzf /tmp/ygk-deploy.tar.gz -C /opt/ygk --overwrite
    
    # Установка зависимостей
    echo "Установка зависимостей..."
    source venv/bin/activate
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    
    # Проверка конфигурации
    echo "Проверка конфигурации..."
    python -c "from dotenv import load_dotenv; load_dotenv(); print('OK')" || exit 1
    
    # Запуск сервисов
    echo "Запуск сервисов..."
    sudo systemctl start ygk-bot ygk-web
    
    # Проверка статуса
    sleep 2
    sudo systemctl is-active --quiet ygk-bot && echo "✅ Бот запущен" || echo "❌ Ошибка запуска бота"
    sudo systemctl is-active --quiet ygk-web && echo "✅ Веб-сервер запущен" || echo "❌ Ошибка запуска веб-сервера"
    
    # Очистка
    rm -f /tmp/ygk-deploy.tar.gz
REMOTE_COMMANDS

# Очистка локальных временных файлов
rm -f /tmp/ygk-deploy.tar.gz

# Проверка работоспособности
echo -e "${YELLOW}🧪 Проверка работоспособности...${NC}"
sleep 3
if ssh $REMOTE_HOST "curl -s http://localhost:8000/ | grep -q 'ЯГК'"; then
    echo -e "${GREEN}✅ Веб-интерфейс отвечает${NC}"
else
    echo -e "${RED}❌ Веб-интерфейс не отвечает${NC}"
fi

echo -e "${GREEN}🎉 Деплой завершен!${NC}"
```

Сделайте скрипт исполняемым:

```bash
chmod +x deploy.sh
```

## 🔒 Настройка systemd сервисов для локального сервера

Файл `ygk-bot.service`:

```ini
[Unit]
Description=ЯГК Schedule Bot
After=network.target

[Service]
Type=simple
User=ygk
WorkingDirectory=/opt/ygk
Environment="PATH=/opt/ygk/venv/bin"
EnvironmentFile=/opt/ygk/.env
ExecStart=/opt/ygk/venv/bin/python bot_main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Файл `ygk-web.service`:

```ini
[Unit]
Description=ЯГК Schedule Web Server
After=network.target

[Service]
Type=simple
User=ygk
WorkingDirectory=/opt/ygk
Environment="PATH=/opt/ygk/venv/bin"
EnvironmentFile=/opt/ygk/.env
ExecStart=/opt/ygk/venv/bin/uvicorn web_main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Установка сервисов:

```bash
# Копирование через туннель
scp ygk-bot.service ygk-web.service ygk-local:/tmp/

# Установка на сервере
ssh ygk-local << 'EOF'
    sudo mv /tmp/ygk-*.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable ygk-bot ygk-web
    sudo systemctl start ygk-bot ygk-web
EOF
```

## 🌐 Настройка веб-доступа через Cloudflare Tunnel

Если в `config.yml` настроен веб-ингресс, ваше приложение будет доступно по:

```
https://ygk.yourdomain.com
```

**Бесплатные возможности Cloudflare:**
- HTTPS с автоматическими сертификатами
- DDoS защита
- CDN кэширование (для статики)
- WAF (Web Application Firewall)
- Analytics

### Дополнительная настройка в config.yml

```yaml
tunnel: <YOUR_TUNNEL_UUID>
credentials-file: /home/user/.cloudflared/<YOUR_TUNNEL_UUID>.json

# Настройки туннеля
transport-loglevel: info

ingress:
  # SSH доступ
  - hostname: ssh.yourdomain.com
    service: ssh://localhost:22
  
  # Веб с оптимизациями
  - hostname: ygk.yourdomain.com
    service: http://localhost:8000
    originRequest:
      connectTimeout: 30s
      tlsDisableVerify: true
      httpHostHeader: ygk.yourdomain.com
      noTLSVerify: true
  
  # API отдельно (если нужно)
  - hostname: api.yourdomain.com
    service: http://localhost:8000
    path: /api/*
  
  # Fallback
  - service: http_status:404
```

## 🔄 Автоматический деплой через GitHub Actions

Создайте `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Local Server

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup SSH with Cloudflare Tunnel
      run: |
        # Установка cloudflared
        wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
        chmod +x cloudflared-linux-amd64
        sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
        
        # Настройка SSH
        mkdir -p ~/.ssh
        echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/deploy_key
        chmod 600 ~/.ssh/deploy_key
        
        cat >> ~/.ssh/config << EOF
        Host ygk-server
            HostName ${{ secrets.CF_SSH_HOSTNAME }}
            User ${{ secrets.SSH_USER }}
            IdentityFile ~/.ssh/deploy_key
            ProxyCommand cloudflared access ssh --hostname %h
            StrictHostKeyChecking no
        EOF
    
    - name: Deploy
      run: |
        # Создание архива
        tar czf deploy.tar.gz \
            --exclude='.git' \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            --exclude='venv' \
            --exclude='.venv' \
            --exclude='*.log' \
            --exclude='*.db' \
            .
        
        # Отправка и установка
        scp deploy.tar.gz ygk-server:/tmp/
        
        ssh ygk-server '
          cd /opt/ygk
          sudo systemctl stop ygk-bot ygk-web
          tar xzf /tmp/deploy.tar.gz --overwrite
          source venv/bin/activate
          pip install -q -r requirements.txt
          sudo systemctl start ygk-bot ygk-web
          rm /tmp/deploy.tar.gz
        '
        rm deploy.tar.gz
    
    - name: Health Check
      run: |
        sleep 5
        # Проверка через публичный URL
        curl -s "https://${{ secrets.CF_WEB_HOSTNAME }}/" | grep -q 'ЯГК' \
          && echo "✅ Deployment successful" \
          || (echo "❌ Health check failed" && exit 1)
```

Добавьте секреты в GitHub Settings → Secrets:
- `SSH_PRIVATE_KEY` — приватный ключ от сервера
- `CF_SSH_HOSTNAME` — SSH хостнейм (например, `ssh.yourdomain.com`)
- `CF_WEB_HOSTNAME` — Веб хостнейм (например, `ygk.yourdomain.com`)
- `SSH_USER` — имя пользователя (например, `ygk`)

## 📊 Мониторинг деплоя

### Проверка логов через туннель

```bash
# Логи бота
ssh ygk-local "sudo journalctl -u ygk-bot -f -n 50"

# Логи веб-сервера
ssh ygk-local "sudo journalctl -u ygk-web -f -n 50"

# Логи туннеля
ssh ygk-local "sudo journalctl -u cloudflared -f -n 50"

# Логи приложения
ssh ygk-local "tail -f /opt/ygk/logs/bot.log"
ssh ygk-local "tail -f /opt/ygk/logs/web.log"
```

### Скрипт проверки статуса

Создайте `check-status.sh`:

```bash
#!/bin/bash

echo "🔍 Проверка статуса ЯГК Schedule"
echo "==================================="

ssh ygk-local << 'EOF'
    echo "📊 Статус сервисов:"
    sudo systemctl status ygk-bot --no-pager -l
    echo ""
    sudo systemctl status ygk-web --no-pager -l
    echo ""
    sudo systemctl status cloudflared --no-pager -l
    
    echo ""
    echo "🌐 Информация о туннеле:"
    cloudflared tunnel info ygk-ssh 2>/dev/null || echo "Не удалось получить информацию"
    
    echo ""
    echo "💾 Использование ресурсов:"
    free -h
    df -h /opt/ygk
    
    echo ""
    echo "📡 Проверка веб-сервера:"
    curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost:8000/
    
    echo ""
    echo "📁 Размер директории:"
    du -sh /opt/ygk
    
    echo ""
    echo "🗃️  Размер базы данных:"
    ls -lh /opt/ygk/ygk.db 2>/dev/null || echo "База данных не найдена"
    
    echo ""
    echo "👥 Количество пользователей:"
    sqlite3 /opt/ygk/ygk.db "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "Не удалось получить данные"
EOF
```

## 🐛 Отладка подключения

### Проблема: Не подключается через туннель

```bash
# Проверка статуса туннеля на сервере
ssh ygk-local "cloudflared tunnel info ygk-ssh"

# Проверка логов туннеля
ssh ygk-local "sudo journalctl -u cloudflared -n 100"

# Перезапуск туннеля
ssh ygk-local "sudo systemctl restart cloudflared"

# Проверка конфигурации
ssh ygk-local "cloudflared tunnel ingress validate ~/.cloudflared/config.yml"
```

### Проблема: cloudflared не найден на клиенте

```bash
# macOS
brew install cloudflared

# Linux
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared-linux-amd64
sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared

# Проверка
which cloudflared
cloudflared --version
```

### Проблема: Ошибка аутентификации

```bash
# Повторная авторизация
cloudflared tunnel login

# Проверка сертификата
ls -la ~/.cloudflared/cert.pem

# Если нужно — пересоздание туннеля
cloudflared tunnel delete ygk-ssh
cloudflared tunnel create ygk-ssh
```

### Проблема: Медленное подключение

```bash
# Использование сжатия
scp -C file.txt ygk-local:/opt/ygk/

# Или в ssh config
Host ygk-local
    Compression yes
    CompressionLevel 6
```

### Проблема: Обрывается соединение

```bash
# Настройка keepalive в ~/.ssh/config
Host ygk-local
    ServerAliveInterval 30
    ServerAliveCountMax 3
    TCPKeepAlive yes
```

## 📝 Чек-лист деплоя

- [ ] Аккаунт Cloudflare создан и домен добавлен
- [ ] DNS записи делегированы на Cloudflare
- [ ] Cloudflare Tunnel создан и настроен
- [ ] DNS записи CNAME созданы (ssh.yourdomain.com, ygk.yourdomain.com)
- [ ] Туннель запущен как служба (systemd)
- [ ] SSH ключи сгенерированы и настроены
- [ ] Пользователь `ygk` создан на сервере
- [ ] Директория `/opt/ygk` создана
- [ ] Файлы проекта скопированы
- [ ] Виртуальное окружение создано (`venv`)
- [ ] Зависимости установлены (`requirements.txt`)
- [ ] Файл `.env` настроен
- [ ] База данных инициализирована (`migrate.py`)
- [ ] Systemd сервисы ygk-bot и ygk-web установлены и запущены
- [ ] Веб-интерфейс доступен по HTTPS
- [ ] Бот отвечает на команды
- [ ] Логи пишутся корректно

## 🎯 Быстрый старт

```bash
# 1. Клонирование репозитория
git clone <repo-url>
cd ygk-schedule

# 2. Настройка SSH config (один раз)
nano ~/.ssh/config
# (добавить конфигурацию из раздела 7)

# 3. Проверка подключения
ssh ygk-local "uname -a"

# 4. Первоначальная настройка сервера
ssh ygk-local << 'EOF'
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip git sqlite3
    sudo useradd -m -s /bin/bash ygk || true
    sudo mkdir -p /opt/ygk
    sudo chown ygk:ygk /opt/ygk
EOF

# 5. Копирование файлов
scp -r * ygk-local:/opt/ygk/

# 6. Установка на сервере
ssh ygk-local << 'EOF'
    cd /opt/ygk
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    # nano .env  # настройте переменные
    python migrate.py
    python test_setup.py
EOF

# 7. Установка сервисов
scp ygk-bot.service ygk-web.service ygk-local:/tmp/
ssh ygk-local "sudo mv /tmp/ygk-*.service /etc/systemd/system/ && sudo systemctl daemon-reload"

# 8. Запуск
ssh ygk-local "sudo systemctl enable ygk-bot ygk-web && sudo systemctl start ygk-bot ygk-web"

# 9. Проверка
ssh ygk-local "sudo systemctl status ygk-bot ygk-web"
```

---

**Документация создана:** February 2026  
**Требования:** Аккаунт Cloudflare (бесплатный), домен, делегированный на Cloudflare, Linux сервер
