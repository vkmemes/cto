# 🚀 Полный гайд по автодеплою ЯГК Schedule

## 📋 Содержание

1. [Обзор вариантов автодеплоя](#обзор-вариантов)
2. [GitHub Actions + Systemd (рекомендуется)](#github-actions--systemd)
3. [GitHub Actions + Docker](#github-actions--docker)
4. [Автодеплой через Webhook](#webhook-автодеплой)
5. [GitLab CI/CD](#gitlab-cicd)
6. [Альтернативы: Self-hosted runners](#self-hosted-runners)
7. [Мониторинг и откат](#мониторинг-и-откат)
8. [Безопасность](#безопасность)

---

## Обзор вариантов

| Метод | Сложность | Стоимость | Надёжность | Время деплоя |
|-------|-----------|-----------|------------|--------------|
| **GitHub Actions + SSH** | ⭐⭐ Средняя | Бесплатно | ⭐⭐⭐⭐⭐ | 30-60 сек |
| **GitHub Actions + Docker** | ⭐⭐⭐ Сложная | Бесплатно | ⭐⭐⭐⭐⭐ | 60-120 сек |
| **Webhook автодеплой** | ⭐ Простая | Бесплатно | ⭐⭐⭐ | 10-20 сек |
| **GitLab CI/CD** | ⭐⭐ Средняя | Бесплатно | ⭐⭐⭐⭐⭐ | 30-60 сек |

---

## GitHub Actions + Systemd

### Архитектура

```
┌──────────────┐     push      ┌──────────────────┐
│  Developer   │ ─────────────→ │  GitHub Actions  │
└──────────────┘                └────────┬─────────┘
                                         │
                              SSH + rsync │
                                         ▼
                              ┌──────────────────┐
                              │  Production VPS  │
                              │  (systemd)       │
                              │  • ygk-bot       │
                              │  • ygk-web       │
                              └──────────────────┘
```

### Шаг 1: Настройка сервера

```bash
# На сервере создайте пользователя для деплоя
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG www-data deploy

# Создайте SSH ключ для GitHub Actions
sudo -u deploy ssh-keygen -t ed25519 -f /home/deploy/.ssh/github_actions
sudo -u deploy cat /home/deploy/.ssh/github_actions.pub >> /home/deploy/.ssh/authorized_keys

# Покажите приватный ключ (добавьте в GitHub Secrets)
sudo -u deploy cat /home/deploy/.ssh/github_actions

# Настройте права на директорию проекта
sudo mkdir -p /opt/ygk
sudo chown deploy:www-data /opt/ygk
sudo chmod 775 /opt/ygk

# Разрешите пользователю deploy перезапускать сервисы
sudo visudo
# Добавьте строку:
deploy ALL=(ALL) NOPASSWD: /bin/systemctl restart ygk-bot, /bin/systemctl restart ygk-web, /bin/systemctl daemon-reload
```

### Шаг 2: Скрипт деплоя на сервере

Создайте `/opt/ygk/deploy.sh`:

```bash
#!/bin/bash
set -e

PROJECT_DIR="/opt/ygk"
VENV_DIR="$PROJECT_DIR/venv"
LOG_FILE="/var/log/ygk-deploy.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

cd "$PROJECT_DIR"

# Backup database перед деплоем
if [ -f "ygk.db" ]; then
    BACKUP_NAME="ygk_$(date +%Y%m%d_%H%M%S).db"
    cp ygk.db "backups/$BACKUP_NAME"
    log "Database backed up to backups/$BACKUP_NAME"
fi

# Backup .env
if [ -f ".env" ]; then
    cp .env .env.backup
    log ".env backed up"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Install/update dependencies
log "Installing dependencies..."
pip install -r requirements.txt --quiet

# Run database migrations
log "Running migrations..."
python migrate.py

# Check for syntax errors
log "Checking Python syntax..."
python -m py_compile bot_main.py web_main.py core.py database.py

# Reload systemd if service files changed
if [ -f "ygk-bot.service" ] && [ "ygk-bot.service" -nt /etc/systemd/system/ygk-bot.service ]; then
    log "Updating systemd service files..."
    sudo cp ygk-bot.service /etc/systemd/system/
    sudo cp ygk-web.service /etc/systemd/system/
    sudo systemctl daemon-reload
fi

# Restart services
log "Restarting services..."
sudo systemctl restart ygk-bot
sudo systemctl restart ygk-web

# Wait for services to start
sleep 3

# Check service status
if ! systemctl is-active --quiet ygk-bot; then
    log "ERROR: ygk-bot failed to start!"
    sudo journalctl -u ygk-bot -n 20
    exit 1
fi

if ! systemctl is-active --quiet ygk-web; then
    log "ERROR: ygk-web failed to start!"
    sudo journalctl -u ygk-web -n 20
    exit 1
fi

log "Deployment completed successfully!"
```

Сделайте исполняемым:
```bash
sudo chmod +x /opt/ygk/deploy.sh
sudo chown deploy:deploy /opt/ygk/deploy.sh
```

### Шаг 3: GitHub Actions Workflow

Создайте `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches: [main, master]
  workflow_dispatch:

concurrency:
  group: production
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run syntax check
        run: |
          python -m py_compile bot_main.py web_main.py core.py database.py

      - name: Test imports
        run: |
          python -c "import core; import database; print('Imports OK')"

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/master'

    steps:
      - uses: actions/checkout@v4

      - name: Setup SSH
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.SSH_PRIVATE_KEY }}
          log-public-key: false

      - name: Add host to known hosts
        run: |
          mkdir -p ~/.ssh
          ssh-keyscan -H ${{ secrets.SERVER_HOST }} >> ~/.ssh/known_hosts

      - name: Deploy to server
        env:
          SERVER_HOST: ${{ secrets.SERVER_HOST }}
          SERVER_USER: ${{ secrets.SERVER_USER }}
        run: |
          # Sync files (excluding sensitive data)
          rsync -avz --delete \
            --exclude='.git' \
            --exclude='venv' \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            --exclude='.env' \
            --exclude='ygk.db' \
            --exclude='logs/*.log' \
            --exclude='backups/' \
            --exclude='.github/' \
            ./ $SERVER_USER@$SERVER_HOST:/opt/ygk/

          # Run deployment script
          ssh $SERVER_USER@$SERVER_HOST 'cd /opt/ygk && ./deploy.sh'

      - name: Verify deployment
        env:
          SERVER_HOST: ${{ secrets.SERVER_HOST }}
          SERVER_USER: ${{ secrets.SERVER_USER }}
        run: |
          ssh $SERVER_USER@$SERVER_HOST '
            echo "=== Service Status ==="
            systemctl is-active ygk-bot && echo "✓ ygk-bot running" || echo "✗ ygk-bot failed"
            systemctl is-active ygk-web && echo "✓ ygk-web running" || echo "✗ ygk-web failed"
            
            echo "=== Recent Logs ==="
            journalctl -u ygk-bot -n 5 --no-pager
            journalctl -u ygk-web -n 5 --no-pager
          '

      - name: Notify on success
        if: success()
        run: |
          echo "✅ Deployment successful!"
          echo "Commit: ${{ github.sha }}"
          echo "Author: ${{ github.actor }}"

      - name: Notify on failure
        if: failure()
        run: |
          echo "❌ Deployment failed!"
          echo "Check logs for details"
```

### Шаг 4: GitHub Secrets

Добавьте в Settings → Secrets → Actions:

| Secret | Описание |
|--------|----------|
| `SSH_PRIVATE_KEY` | Приватный SSH ключ (`cat /home/deploy/.ssh/github_actions`) |
| `SERVER_HOST` | IP или домен сервера |
| `SERVER_USER` | Имя пользователя (`deploy`) |

---

## GitHub Actions + Docker

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command (override in docker-compose)
CMD ["python", "bot_main.py"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  bot:
    build: .
    container_name: ygk-bot
    command: python bot_main.py
    env_file: .env
    volumes:
      - ./ygk.db:/app/ygk.db
      - ./logs:/app/logs
      - ./schedule.json:/app/schedule.json
    restart: unless-stopped
    networks:
      - ygk-network

  web:
    build: .
    container_name: ygk-web
    command: python web_main.py
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./ygk.db:/app/ygk.db
      - ./logs:/app/logs
      - ./schedule.json:/app/schedule.json
      - ./templates:/app/templates
    restart: unless-stopped
    networks:
      - ygk-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  ygk-network:
    driver: bridge
```

### GitHub Actions для Docker

```yaml
name: Docker Deploy

on:
  push:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=sha,prefix={{branch}}-
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest

    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@v1.0.0
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/ygk
            
            # Login to GHCR
            echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io -u ${{ github.actor }} --password-stdin
            
            # Backup database
            mkdir -p backups
            if [ -f ygk.db ]; then
              cp ygk.db backups/ygk_$(date +%Y%m%d_%H%M%S).db
            fi
            
            # Pull and deploy
            docker-compose pull
            docker-compose up -d
            
            # Cleanup
            docker system prune -f
            
            # Verify
            docker-compose ps
```

---

## Webhook автодеплой

### Простой webhook сервер на Python

Создайте `webhook_server.py` на сервере:

```python
#!/usr/bin/env python3
"""
Simple webhook server for auto-deployment
Run this alongside main services or separately
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import subprocess
from datetime import datetime

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from uvicorn import Config, Server

# Configuration
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "9000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your-secret-key")
PROJECT_DIR = os.getenv("PROJECT_DIR", "/opt/ygk")
DEPLOY_BRANCH = os.getenv("DEPLOY_BRANCH", "main")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook")


async def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature"""
    if not signature:
        return False
    
    expected = "sha256=" + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


async def run_deployment():
    """Run deployment commands"""
    commands = [
        ["git", "-C", PROJECT_DIR, "fetch", "origin"],
        ["git", "-C", PROJECT_DIR, "reset", "--hard", f"origin/{DEPLOY_BRANCH}"],
        ["sudo", "systemctl", "restart", "ygk-bot"],
        ["sudo", "systemctl", "restart", "ygk-web"],
    ]
    
    results = []
    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=PROJECT_DIR
            )
            results.append({
                "cmd": " ".join(cmd),
                "returncode": result.returncode,
                "stdout": result.stdout[-500:] if result.stdout else "",
                "stderr": result.stderr[-500:] if result.stderr else ""
            })
            
            if result.returncode != 0:
                logger.error(f"Command failed: {' '.join(cmd)}")
                logger.error(result.stderr)
                break
        except Exception as e:
            logger.error(f"Exception running command: {e}")
            results.append({"cmd": " ".join(cmd), "error": str(e)})
            break
    
    return results


async def github_webhook(request: Request):
    """Handle GitHub webhook"""
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    event = request.headers.get("X-GitHub-Event", "")
    
    # Verify signature
    if not await verify_signature(payload, signature, WEBHOOK_SECRET):
        logger.warning("Invalid webhook signature")
        return JSONResponse({"error": "Invalid signature"}, status_code=401)
    
    # Parse payload
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    
    # Handle push event
    if event == "push":
        branch = data.get("ref", "").replace("refs/heads/", "")
        
        if branch != DEPLOY_BRANCH:
            return JSONResponse({
                "message": f"Ignoring push to {branch}, waiting for {DEPLOY_BRANCH}"
            })
        
        logger.info(f"Received push to {branch}, starting deployment...")
        
        # Run deployment
        results = await run_deployment()
        
        return JSONResponse({
            "status": "deployed",
            "branch": branch,
            "timestamp": datetime.now().isoformat(),
            "results": results
        })
    
    return JSONResponse({"message": f"Event {event} received but not processed"})


async def health_check(request: Request):
    """Health check endpoint"""
    return JSONResponse({
        "status": "ok",
        "service": "webhook-server",
        "timestamp": datetime.now().isoformat()
    })


# Create app
app = Starlette(
    routes=[
        Route("/webhook/github", github_webhook, methods=["POST"]),
        Route("/health", health_check),
    ]
)


async def main():
    config = Config(app=app, host="0.0.0.0", port=WEBHOOK_PORT)
    server = Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
```

### Systemd сервис для webhook

```ini
[Unit]
Description=Webhook Auto-Deploy Server
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/ygk
Environment="PATH=/opt/ygk/venv/bin"
Environment="WEBHOOK_PORT=9000"
Environment="WEBHOOK_SECRET=your-webhook-secret"
Environment="PROJECT_DIR=/opt/ygk"
Environment="DEPLOY_BRANCH=main"
ExecStart=/opt/ygk/venv/bin/python webhook_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Настройка GitHub Webhook

1. В репозитории: Settings → Webhooks → Add webhook
2. Payload URL: `http://your-server:9000/webhook/github`
3. Content type: `application/json`
4. Secret: тот же что в `WEBHOOK_SECRET`
5. Events: Push events

---

## GitLab CI/CD

### .gitlab-ci.yml

```yaml
stages:
  - test
  - deploy

variables:
  PROJECT_DIR: "/opt/ygk"
  SERVER_HOST: "$SERVER_HOST"
  SERVER_USER: "$SERVER_USER"

# Cache pip dependencies
cache:
  paths:
    - .cache/pip
  key: "$CI_COMMIT_REF_SLUG"

# Test stage
test:
  stage: test
  image: python:3.11-slim
  before_script:
    - pip install -r requirements.txt
  script:
    - python -m py_compile bot_main.py web_main.py core.py database.py
    - python -c "import core; import database; print('Imports OK')"
  only:
    - main
    - merge_requests

# Deploy stage
deploy:
  stage: deploy
  image: alpine:latest
  before_script:
    - apk add --no-cache openssh-client rsync
    - mkdir -p ~/.ssh
    - echo "$SSH_PRIVATE_KEY" | tr -d '\r' > ~/.ssh/id_ed25519
    - chmod 600 ~/.ssh/id_ed25519
    - ssh-keyscan -H "$SERVER_HOST" >> ~/.ssh/known_hosts
  script:
    # Sync files
    - rsync -avz --delete
        --exclude='.git'
        --exclude='venv'
        --exclude='__pycache__'
        --exclude='.env'
        --exclude='ygk.db'
        --exclude='logs/'
        --exclude='backups/'
        ./ "$SERVER_USER@$SERVER_HOST:$PROJECT_DIR/"
    
    # Run deployment
    - ssh "$SERVER_USER@$SERVER_HOST" "cd $PROJECT_DIR && ./deploy.sh"
    
    # Verify
    - ssh "$SERVER_USER@$SERVER_HOST" "systemctl is-active ygk-bot && systemctl is-active ygk-web"
  only:
    - main
  environment:
    name: production
    url: http://$SERVER_HOST:8000
```

### GitLab CI/CD Variables

Settings → CI/CD → Variables:

| Variable | Protected | Masked |
|----------|-----------|--------|
| `SSH_PRIVATE_KEY` | ✅ | ✅ |
| `SERVER_HOST` | ✅ | ❌ |
| `SERVER_USER` | ✅ | ❌ |

---

## Self-hosted runners

### GitHub Self-hosted Runner

```bash
# На сервере
cd /opt
mkdir actions-runner && cd actions-runner

# Скачайте последнюю версию
curl -o actions-runner-linux-x64-2.311.0.tar.gz \
  -L https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz

# Распакуйте
tar xzf ./actions-runner-linux-x64-2.311.0.tar.gz

# Настройте
./config.sh --url https://github.com/YOUR_ORG/YOUR_REPO --token YOUR_TOKEN

# Установите как сервис
sudo ./svc.sh install
sudo ./svc.sh start
```

### Преимущества self-hosted:
- Деплой без SSH (runner на том же сервере)
- Доступ к локальным ресурсам
- Быстрее (нет загрузки артефактов)

---

## Мониторинг и откат

### Скрипт проверки здоровья

```bash
#!/bin/bash
# health_check.sh

WEB_URL="http://localhost:8000"
BOT_PID=$(pgrep -f "bot_main.py")
WEB_PID=$(pgrep -f "web_main.py")
ERRORS=0

# Check bot process
if [ -z "$BOT_PID" ]; then
    echo "❌ Bot process not running"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Bot running (PID: $BOT_PID)"
fi

# Check web process
if [ -z "$WEB_PID" ]; then
    echo "❌ Web process not running"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Web running (PID: $WEB_PID)"
    
    # Check HTTP response
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$WEB_URL" || echo "000")
    if [ "$HTTP_CODE" != "200" ]; then
        echo "❌ Web returned HTTP $HTTP_CODE"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ Web responding (HTTP 200)"
    fi
fi

# Check database
if [ -f "/opt/ygk/ygk.db" ]; then
    echo "✅ Database exists"
else
    echo "❌ Database missing"
    ERRORS=$((ERRORS + 1))
fi

exit $ERRORS
```

### Автоматический откат

Добавьте в `deploy.sh`:

```bash
#!/bin/bash
set -e

PROJECT_DIR="/opt/ygk"
GIT_DIR="$PROJECT_DIR/.git"

# Сохраняем текущий коммит
BEFORE_DEPLOY=$(git -C "$PROJECT_DIR" rev-parse HEAD)
echo "Current commit: $BEFORE_DEPLOY"

# Функция отката
rollback() {
    echo "❌ Deployment failed, rolling back to $BEFORE_DEPLOY..."
    git -C "$PROJECT_DIR" reset --hard "$BEFORE_DEPLOY"
    sudo systemctl restart ygk-bot ygk-web
    
    # Отправка уведомления (опционально)
    curl -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
        -d "chat_id=$ADMIN_CHAT_ID" \
        -d "text=🚨 Deployment failed! Rolled back to $BEFORE_DEPLOY"
    
    exit 1
}

# Устанавливаем trap для отката при ошибке
trap rollback ERR

# Основной деплой
# ... (ваш код деплоя)

# Проверка здоровья
sleep 5
if ! "$PROJECT_DIR/health_check.sh"; then
    rollback
fi

echo "✅ Deployment successful!"
```

---

## Безопасность

### Чеклист безопасности

- [ ] SSH ключи без пароля (passphrase) для CI
- [ ] Ограниченные права пользователя deploy
- [ ] Файрвол: порт webhook только для GitHub/GitLab IPs
- [ ] .env файл никогда не коммитится
- [ ] База данных в .gitignore
- [ ] Логи ротируются
- [ ] Регулярное обновление зависимостей

### Ограничение доступа по IP

```bash
# Для webhook сервера (iptables)
# GitHub webhook IPs: https://api.github.com/meta
sudo iptables -A INPUT -p tcp --dport 9000 -s 192.30.252.0/22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 9000 -s 185.199.108.0/22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 9000 -j DROP
```

### Secrets management

```bash
# Используйте ansible-vault или SOPS для шифрования secrets
# Пример с SOPS:
sops -e .env > .env.enc
sops -d .env.enc > .env
```

---

## Заключение

### Рекомендуемый выбор

| Сценарий | Рекомендуемый метод |
|----------|---------------------|
| Простой сервер (VPS) | GitHub Actions + SSH |
| Микросервисы | GitHub Actions + Docker |
| Частые обновления | Webhook автодеплой |
| Приватный репозиторий | Любой метод |
| Публичный репозиторий | GitHub Actions (безопаснее) |

### Быстрый старт

```bash
# 1. Создайте deploy пользователя
sudo useradd -m deploy

# 2. Сгенерируйте SSH ключ
sudo -u deploy ssh-keygen -t ed25519

# 3. Добавьте ключ в GitHub Secrets
sudo -u deploy cat /home/deploy/.ssh/id_ed25519

# 4. Скопируйте workflow
mkdir -p .github/workflows
cp docs/deploy.yml .github/workflows/

# 5. Push на main
git add .
git commit -m "Add auto-deploy"
git push origin main
```

---

**Автор:** ЯГК Schedule Team  
**Последнее обновление:** February 2026  
**Версия:** 1.0
