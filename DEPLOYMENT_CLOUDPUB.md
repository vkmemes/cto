# Деплой STTEC Schedule через SSH с туннелированием Cloudflare Tunnel

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
# Создание туннеля (замените sttec-ssh на любое имя)
cloudflared tunnel create sttec-ssh

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
  - hostname: sttec.yourdomain.com
    service: http://localhost:8000
  
  # Fallback
  - service: http_status:404
```

Замените:
- `<YOUR_TUNNEL_UUID>` — UUID из шага 3
- `ssh.yourdomain.com` — ваш поддомен для SSH
- `sttec.yourdomain.com` — ваш поддомен для веб

### 5. Настройка DNS записей в Cloudflare

```bash
# Автоматическое создание DNS записей
cloudflared tunnel route dns sttec-ssh ssh.yourdomain.com
cloudflared tunnel route dns sttec-ssh sttec.yourdomain.com

# Или вручную в панели Cloudflare:
# Тип: CNAME
# Имя: ssh
# Цель: <UUID>.cfargotunnel.com
# 
# Тип: CNAME
# Имя: sttec
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
cloudflared tunnel info sttec-ssh
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
Host sttec-local
    HostName ssh.yourdomain.com
    User sttec
    IdentityFile ~/.ssh/sttec_deploy_key
    ProxyCommand cloudflared access ssh --hostname %h
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

### 8. Генерация SSH ключей для деплоя

На локальном сервере:

```bash
# Создание пользователя для деплоя
sudo useradd -m -s /bin/bash sttec

# Генерация ключей
sudo -u sttec mkdir -p /home/sttec/.ssh
sudo -u sttec ssh-keygen -t ed25519 -f /home/sttec/.ssh/deploy_key -N ""

# Добавление публичного ключа в authorized_keys
sudo -u sttec cat /home/sttec/.ssh/deploy_key.pub >> /home/sttec/.ssh/authorized_keys
sudo -u sttec chmod 600 /home/sttec/.ssh/authorized_keys

# Получение приватного ключа (скопируйте вывод)
sudo cat /home/sttec/.ssh/deploy_key
```

Сохраните приватный ключ в `~/.ssh/sttec_deploy_key` на вашем ПК.

## 🚀 Процесс деплоя

### Метод 1: Прямое копирование файлов (SCP)

```bash
# 1. Проверка подключения
ssh sttec-local "echo 'Подключение успешно!'"

# 2. Создание структуры директорий
ssh sttec-local "mkdir -p /opt/sttec/{backups,logs}"

# 3. Копирование файлов проекта
scp -r bot_main.py core.py database.py web_main.py migrate.py sttec-local:/opt/sttec/
scp -r requirements.txt .env schedule.json sttec-local:/opt/sttec/
scp -r templates/ sttec-local:/opt/sttec/
scp sttec-bot.service sttec-web.service sttec-local:/tmp/

# 4. Установка прав
ssh sttec-local "sudo chown -R sttec:sttec /opt/sttec"
```

### Метод 2: Деплой через Git (рекомендуется)

На локальном сервере (один раз):

```bash
# Установка Git
sudo apt update && sudo apt install -y git

# Создание bare-репозитория
sudo mkdir -p /opt/git/sttec.git
sudo git init --bare /opt/git/sttec.git

# Создание hook для автодеплоя
sudo tee /opt/git/sttec.git/hooks/post-receive << 'EOF'
#!/bin/bash
TARGET="/opt/sttec"
GIT_DIR="/opt/git/sttec.git"
BRANCH="main"

while read oldrev newrev ref
do
    if [[ $ref = refs/heads/$BRANCH ]]; then
        echo "Deploying $BRANCH to production..."
        git --work-tree=$TARGET --git-dir=$GIT_DIR checkout -f $BRANCH
        
        # Перезапуск сервисов
        sudo systemctl restart sttec-bot sttec-web
        echo "Deployment complete!"
    fi
done
EOF

sudo chmod +x /opt/git/sttec.git/hooks/post-receive
sudo chown -R sttec:sttec /opt/git/sttec.git
```

На вашем ПК:

```bash
# Добавление remote через туннель
git remote add production ssh://sttec-local/opt/git/sttec.git

# Деплой
ssh sttec-local "sudo chown -R sttec:sttec /opt/sttec"
git push production main
```

## 📦 Скрипт автоматического деплоя

Создайте файл `deploy.sh` на вашем ПК:

```bash
#!/bin/bash

# Конфигурация
REMOTE_USER="sttec"
REMOTE_HOST="sttec-local"
REMOTE_DIR="/opt/sttec"
SERVICE_NAME_BOT="sttec-bot"
SERVICE_NAME_WEB="sttec-web"

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Начало деплоя STTEC Schedule...${NC}"

# Проверка доступности сервера
echo -e "${YELLOW}📡 Проверка подключения...${NC}"
if ! ssh $REMOTE_HOST "echo 'OK'" > /dev/null 2>&1; then
    echo -e "${RED}❌ Ошибка: Не удалось подключиться к серверу через Cloudflare Tunnel${NC}"
    echo -e "${RED}   Убедитесь, что туннель активен: cloudflared tunnel info sttec-ssh${NC}"
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
tar czf /tmp/sttec-deploy.tar.gz \
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
scp /tmp/sttec-deploy.tar.gz $REMOTE_HOST:/tmp/

# Распаковка и установка
echo -e "${YELLOW}🔧 Установка на сервере...${NC}"
ssh $REMOTE_HOST << 'REMOTE_COMMANDS'
    cd /opt/sttec
    
    # Остановка сервисов
    echo "Остановка сервисов..."
    sudo systemctl stop sttec-bot sttec-web || true
    
    # Резервная копия
    echo "Создание резервной копии..."
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p $BACKUP_DIR
    cp -r *.py *.json .env templates $BACKUP_DIR/ 2>/dev/null || true
    
    # Распаковка новой версии
    echo "Обновление файлов..."
    tar xzf /tmp/sttec-deploy.tar.gz -C /opt/sttec --overwrite
    
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
    sudo systemctl start sttec-bot sttec-web
    
    # Проверка статуса
    sleep 2
    sudo systemctl is-active --quiet sttec-bot && echo "✅ Бот запущен" || echo "❌ Ошибка запуска бота"
    sudo systemctl is-active --quiet sttec-web && echo "✅ Веб-сервер запущен" || echo "❌ Ошибка запуска веб-сервера"
    
    # Очистка
    rm -f /tmp/sttec-deploy.tar.gz
REMOTE_COMMANDS

# Очистка локальных временных файлов
rm -f /tmp/sttec-deploy.tar.gz

# Проверка работоспособности
echo -e "${YELLOW}🧪 Проверка работоспособности...${NC}"
sleep 3
if ssh $REMOTE_HOST "curl -s http://localhost:8000/ | grep -q 'STTEC'"; then
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

Файл `sttec-bot.service`:

```ini
[Unit]
Description=STTEC Schedule Bot
After=network.target

[Service]
Type=simple
User=sttec
WorkingDirectory=/opt/sttec
Environment="PATH=/opt/sttec/venv/bin"
EnvironmentFile=/opt/sttec/.env
ExecStart=/opt/sttec/venv/bin/python bot_main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Файл `sttec-web.service`:

```ini
[Unit]
Description=STTEC Schedule Web Server
After=network.target

[Service]
Type=simple
User=sttec
WorkingDirectory=/opt/sttec
Environment="PATH=/opt/sttec/venv/bin"
EnvironmentFile=/opt/sttec/.env
ExecStart=/opt/sttec/venv/bin/uvicorn web_main:app --host 0.0.0.0 --port 8000
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
scp sttec-bot.service sttec-web.service sttec-local:/tmp/

# Установка на сервере
ssh sttec-local << 'EOF'
    sudo mv /tmp/sttec-*.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable sttec-bot sttec-web
    sudo systemctl start sttec-bot sttec-web
EOF
```

## 🌐 Настройка веб-доступа через Cloudflare Tunnel

Если в `config.yml` настроен веб-ингресс, ваше приложение будет доступно по:

```
https://sttec.yourdomain.com
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
  - hostname: sttec.yourdomain.com
    service: http://localhost:8000
    originRequest:
      connectTimeout: 30s
      tlsDisableVerify: true
      httpHostHeader: sttec.yourdomain.com
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
        Host sttec-server
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
        scp deploy.tar.gz sttec-server:/tmp/
        
        ssh sttec-server '
          cd /opt/sttec
          sudo systemctl stop sttec-bot sttec-web
          tar xzf /tmp/deploy.tar.gz --overwrite
          source venv/bin/activate
          pip install -q -r requirements.txt
          sudo systemctl start sttec-bot sttec-web
          rm /tmp/deploy.tar.gz
        '
        rm deploy.tar.gz
    
    - name: Health Check
      run: |
        sleep 5
        # Проверка через публичный URL
        curl -s "https://${{ secrets.CF_WEB_HOSTNAME }}/" | grep -q 'STTEC' \
          && echo "✅ Deployment successful" \
          || (echo "❌ Health check failed" && exit 1)
```

Добавьте секреты в GitHub Settings → Secrets:
- `SSH_PRIVATE_KEY` — приватный ключ от сервера
- `CF_SSH_HOSTNAME` — SSH хостнейм (например, `ssh.yourdomain.com`)
- `CF_WEB_HOSTNAME` — Веб хостнейм (например, `sttec.yourdomain.com`)
- `SSH_USER` — имя пользователя (например, `sttec`)

## 📊 Мониторинг деплоя

### Проверка логов через туннель

```bash
# Логи бота
ssh sttec-local "sudo journalctl -u sttec-bot -f -n 50"

# Логи веб-сервера
ssh sttec-local "sudo journalctl -u sttec-web -f -n 50"

# Логи туннеля
ssh sttec-local "sudo journalctl -u cloudflared -f -n 50"

# Логи приложения
ssh sttec-local "tail -f /opt/sttec/logs/bot.log"
ssh sttec-local "tail -f /opt/sttec/logs/web.log"
```

### Скрипт проверки статуса

Создайте `check-status.sh`:

```bash
#!/bin/bash

echo "🔍 Проверка статуса STTEC Schedule"
echo "==================================="

ssh sttec-local << 'EOF'
    echo "📊 Статус сервисов:"
    sudo systemctl status sttec-bot --no-pager -l
    echo ""
    sudo systemctl status sttec-web --no-pager -l
    echo ""
    sudo systemctl status cloudflared --no-pager -l
    
    echo ""
    echo "🌐 Информация о туннеле:"
    cloudflared tunnel info sttec-ssh 2>/dev/null || echo "Не удалось получить информацию"
    
    echo ""
    echo "💾 Использование ресурсов:"
    free -h
    df -h /opt/sttec
    
    echo ""
    echo "📡 Проверка веб-сервера:"
    curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost:8000/
    
    echo ""
    echo "📁 Размер директории:"
    du -sh /opt/sttec
    
    echo ""
    echo "🗃️  Размер базы данных:"
    ls -lh /opt/sttec/sttec.db 2>/dev/null || echo "База данных не найдена"
    
    echo ""
    echo "👥 Количество пользователей:"
    sqlite3 /opt/sttec/sttec.db "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "Не удалось получить данные"
EOF
```

## 🐛 Отладка подключения

### Проблема: Не подключается через туннель

```bash
# Проверка статуса туннеля на сервере
ssh sttec-local "cloudflared tunnel info sttec-ssh"

# Проверка логов туннеля
ssh sttec-local "sudo journalctl -u cloudflared -n 100"

# Перезапуск туннеля
ssh sttec-local "sudo systemctl restart cloudflared"

# Проверка конфигурации
ssh sttec-local "cloudflared tunnel ingress validate ~/.cloudflared/config.yml"
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
cloudflared tunnel delete sttec-ssh
cloudflared tunnel create sttec-ssh
```

### Проблема: Медленное подключение

```bash
# Использование сжатия
scp -C file.txt sttec-local:/opt/sttec/

# Или в ssh config
Host sttec-local
    Compression yes
    CompressionLevel 6
```

### Проблема: Обрывается соединение

```bash
# Настройка keepalive в ~/.ssh/config
Host sttec-local
    ServerAliveInterval 30
    ServerAliveCountMax 3
    TCPKeepAlive yes
```

## 📝 Чек-лист деплоя

- [ ] Аккаунт Cloudflare создан и домен добавлен
- [ ] DNS записи делегированы на Cloudflare
- [ ] Cloudflare Tunnel создан и настроен
- [ ] DNS записи CNAME созданы (ssh.yourdomain.com, sttec.yourdomain.com)
- [ ] Туннель запущен как служба (systemd)
- [ ] SSH ключи сгенерированы и настроены
- [ ] Пользователь `sttec` создан на сервере
- [ ] Директория `/opt/sttec` создана
- [ ] Файлы проекта скопированы
- [ ] Виртуальное окружение создано (`venv`)
- [ ] Зависимости установлены (`requirements.txt`)
- [ ] Файл `.env` настроен
- [ ] База данных инициализирована (`migrate.py`)
- [ ] Systemd сервисы sttec-bot и sttec-web установлены и запущены
- [ ] Веб-интерфейс доступен по HTTPS
- [ ] Бот отвечает на команды
- [ ] Логи пишутся корректно

## 🎯 Быстрый старт

```bash
# 1. Клонирование репозитория
git clone <repo-url>
cd sttec-schedule

# 2. Настройка SSH config (один раз)
nano ~/.ssh/config
# (добавить конфигурацию из раздела 7)

# 3. Проверка подключения
ssh sttec-local "uname -a"

# 4. Первоначальная настройка сервера
ssh sttec-local << 'EOF'
    sudo apt update
    sudo apt install -y python3 python3-venv python3-pip git sqlite3
    sudo useradd -m -s /bin/bash sttec || true
    sudo mkdir -p /opt/sttec
    sudo chown sttec:sttec /opt/sttec
EOF

# 5. Копирование файлов
scp -r * sttec-local:/opt/sttec/

# 6. Установка на сервере
ssh sttec-local << 'EOF'
    cd /opt/sttec
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    # nano .env  # настройте переменные
    python migrate.py
    python test_setup.py
EOF

# 7. Установка сервисов
scp sttec-bot.service sttec-web.service sttec-local:/tmp/
ssh sttec-local "sudo mv /tmp/sttec-*.service /etc/systemd/system/ && sudo systemctl daemon-reload"

# 8. Запуск
ssh sttec-local "sudo systemctl enable sttec-bot sttec-web && sudo systemctl start sttec-bot sttec-web"

# 9. Проверка
ssh sttec-local "sudo systemctl status sttec-bot sttec-web"
```

---

**Документация создана:** February 2026  
**Требования:** Аккаунт Cloudflare (бесплатный), домен, делегированный на Cloudflare, Linux сервер
