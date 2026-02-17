# Бесплатные альтернативы для туннелирования трафика

Документация описывает бесплатные методы туннелирования локального сервера в интернет без требования привязки банковской карты.

## 🎯 Обзор решений

| Сервис | Бесплатно | Свой домен | HTTPS | Сложность |
|--------|-----------|------------|-------|-----------|
| **LocalTunnel** | ✅ Да | ❌ Нет | ✅ Да | ⭐ Простая |
| **ngrok** | ⚠️ Ограничен | ❌ Нет | ✅ Да | ⭐ Простая |
| **serveo.net** | ✅ Да | ❌ Нет | ❌ Нет | ⭐ Очень простая |
| **Bore** | ✅ Да | ❌ Нет | ❌ Нет | ⭐ Простая |
| **Pagekite** | ✅ Да | ⚠️ Платно | ✅ Да | ⭐⭐ Средняя |
| **SSH Reverse Tunnel** | ✅ Да | ✅ Да* | ⚠️ Нужно настроить | ⭐⭐ Средняя |
| **Tailscale Funnel** | ✅ Да (beta) | ❌ Нет | ✅ Да | ⭐ Средняя |

\* Требуется свой VPS или сервер с публичным IP

---

## 1. LocalTunnel (рекомендуется для быстрого старта)

### Преимущества
- ✅ Полностью бесплатный
- ✅ Не требует регистрации
- ✅ Работает сразу после установки
- ✅ Поддержка поддоменов
- ✅ Поддержка HTTPS

### Установка

```bash
# Через npm (требуется Node.js)
npm install -g localtunnel

# Или через npx (без установки)
npx localtunnel --version
```

### Использование

**Базовое использование:**

```bash
# Туннелирование порта 8000
lt --port 8000

# Вывод:
# your url is: https://random-name.loca.lt
```

**С自定义 поддоменом:**

```bash
lt --port 8000 --subdomain ygk-schedule

# Вывод:
# your url is: https://ygk-schedule.loca.lt
```

**Для ЯГК Schedule:**

```bash
# Веб-интерфейс
lt --port 8000 --subdomain ygk-web

# Для локальной разработки
lt --port 8000 --local-host localhost
```

### Интеграция с systemd

Создайте файл `/etc/systemd/system/localtunnel.service`:

```ini
[Unit]
Description=LocalTunnel for ЯГК Schedule
After=network.target

[Service]
Type=simple
User=ygk
WorkingDirectory=/opt/ygk
ExecStart=/usr/bin/lt --port 8000 --subdomain ygk-schedule
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable localtunnel
sudo systemctl start localtunnel
sudo systemctl status localtunnel
```

### Доступ к боту

LocalTunnel предоставляет публичный URL, который можно использовать для:
- Telegram Mini Apps
- API доступа
- Веб-интерфейса

**Ограничения:**
- Поддомены могут быть заняты другими пользователями
- Нет гарантии постоянства URL (без платной подписки)
- Тайм-аут соединения: может прерываться при неактивности

---

## 2. ngrok (популярный выбор)

### Преимущества
- ✅ Популярный и надёжный сервис
- ✅ Простая настройка
- ✅ HTTPS из коробки
- ✅ Веб-интерфейс для мониторинга

### Бесплатные ограничения
- 🔸 Случайный поддомен
- 🔸 Одно соединение одновременно
- 🔸 Тайм-аут через 2-8 часов неактивности
- 🔸 Ограничение скорости

### Установка

**Linux:**

```bash
# Скачивание
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Или прямая загрузка
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin
```

**macOS:**

```bash
brew install ngrok
```

**Windows:**

Скачайте с https://ngrok.com/download

### Использование

**Базовое использование:**

```bash
ngrok http 8000

# Вывод:
# Session Status                Online
# Account                       (free plan)
# Version                       3.x.x
# Forwarding                    https://abcd-1234.ngrok-free.app -> http://localhost:8000
```

**Фиксированный поддомен (требует регистрации, но бесплатно):**

```bash
# Регистрация на https://ngrok.com/signup (бесплатно)
ngrok config add-authtoken YOUR_AUTH_TOKEN

# Использование фиксированного домена
ngrok http 8000 --domain=your-reserved-domain.ngrok-free.app
```

**Конфигурационный файл:**

Создайте `~/.ngrok2/ngrok.yml`:

```yaml
tunnels:
  ygk-web:
    proto: http
    addr: 8000
    bind_tls: true
    inspect: true
    web_addr: localhost:4040
```

Запуск:

```bash
ngrok start ygk-web
```

### Интеграция с systemd

Создайте `/etc/systemd/system/ngrok.service`:

```ini
[Unit]
Description=ngrok tunnel
After=network.target

[Service]
Type=simple
User=ygk
ExecStart=/usr/local/bin/ngrok http 8000 --log=stdout
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 3. serveo.net (через SSH)

### Преимущества
- ✅ Полностью бесплатный
- ✅ Не требует установки ничего
- ✅ Работает через SSH
- ✅ Можно настроить свой поддомен

### Установка

Не требуется! Использует встроенный SSH клиент.

### Использование

**Базовое использование:**

```bash
# Простое туннелирование
ssh -R 80:localhost:8000 serveo.net

# Вывод:
# Forwarding HTTP traffic from https://random.serveo.net
# Press g to start a GUI and x to exit.
```

**С自定义 поддоменом:**

```bash
ssh -R ygk-schedule:80:localhost:8000 serveo.net

# Ваш сайт будет доступен по:
# https://ygk-schedule.serveo.net
```

**Постоянное соединение:**

```bash
# Автоматическое переподключение при обрыве
while true; do
    ssh -o ServerAliveInterval=60 -R ygk-schedule:80:localhost:8000 serveo.net
    sleep 5
done
```

**Для ЯГК Schedule:**

```bash
# Веб-интерфейс
ssh -R ygk-web:80:localhost:8000 serveo.net

# В фоне с nohup
nohup ssh -o ServerAliveInterval=60 -R ygk-web:80:localhost:8000 serveo.net > /dev/null 2>&1 &
```

### Интеграция с systemd

Создайте `/etc/systemd/system/serveo-tunnel.service`:

```ini
[Unit]
Description=Serveo.net SSH tunnel
After=network.target

[Service]
Type=simple
User=ygk
ExecStart=/usr/bin/ssh -o ServerAliveInterval=60 -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=no -N -R ygk-schedule:80:localhost:8000 serveo.net
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Примечание:** serveo.net может быть нестабилен или временно недоступен.

---

## 4. Bore (Go-based туннель)

### Преимущества
- ✅ Открытый исходный код
- ✅ Быстрый и лёгкий
- ✅ Не требует регистрации
- ✅ Поддержка собственных серверов

### Установка

**Linux:**

```bash
# Через Go (если установлен)
go install github.com/ekz/bore@latest

# Или прямая загрузка бинарника
wget https://github.com/ekz/bore/releases/latest/download/bore-x86_64-unknown-linux-musl
chmod +x bore-x86_64-unknown-linux-musl
sudo mv bore-x86_64-unknown-linux-musl /usr/local/bin/bore
```

### Использование

**Базовое использование (публичный сервер):**

```bash
# Использование публичного сервера bore.pub
bore local 8000 --to bore.pub

# Вывод:
# bore: forwarding local 8000 to remote 30000
# bore: your tunnel is available at: https://bore.pub:30000
```

**Свой сервер (опционально):**

```bash
# На сервере:
bore server

# На клиенте:
bore local 8000 --to your-server.com --port 9000
```

### Интеграция с systemd

Создайте `/etc/systemd/system/bore-tunnel.service`:

```ini
[Unit]
Description=Bore tunnel
After=network.target

[Service]
Type=simple
User=ygk
ExecStart=/usr/local/bin/bore local 8000 --to bore.pub
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 5. SSH Reverse Tunnel (свой VPS)

### Преимущества
- ✅ Полный контроль
- ✅ Можно использовать свой домен
- ✅ Настраиваемый HTTPS (через nginx)
- ✅ Без ограничений по времени

### Требования
- VPS или сервер с публичным IP (DigitalOcean, Hetzner, и т.д.)
- Свой домен

### Настройка на VPS

**1. Настройка SSH для обратных туннелей:**

Добавьте в `/etc/ssh/sshd_config` на VPS:

```bash
# Разрешить обратные туннели
GatewayPorts yes
AllowTcpForwarding yes
PermitTunnel yes
```

Перезапустите SSH:

```bash
sudo systemctl restart sshd
```

**2. Настройка nginx для HTTPS:**

Создайте `/etc/nginx/sites-available/ygk`:

```nginx
server {
    listen 80;
    server_name ygk.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включите сайт и настройте HTTPS через Let's Encrypt:

```bash
sudo ln -s /etc/nginx/sites-available/ygk /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Установка certbot
sudo apt install certbot python3-certbot-nginx

# Получение сертификата
sudo certbot --nginx -d ygk.yourdomain.com
```

### Настройка на локальном сервере

**Создание SSH ключей:**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/vps_tunnel_key -N ""
```

**Копирование публичного ключа на VPS:**

```bash
ssh-copy-id -i ~/.ssh/vps_tunnel_key.pub user@your-vps.com
```

**Настройка автоматического туннеля:**

Создайте `/etc/systemd/system/ssh-reverse-tunnel.service`:

```ini
[Unit]
Description=SSH Reverse Tunnel to VPS
After=network.target

[Service]
Type=simple
User=ygk
ExecStart=/usr/bin/ssh -i /home/ygk/.ssh/vps_tunnel_key -o ServerAliveInterval=60 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=no -N -R 8000:localhost:8000 user@your-vps.com
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ssh-reverse-tunnel
sudo systemctl start ssh-reverse-tunnel
```

**Теперь ваш сайт доступен по:** `https://ygk.yourdomain.com`

### Стоимость

- VPS: от $4/мес (DigitalOcean, Hetzner, и т.д.)
- Домен: от $10/год
- Итого: ~$5-6/мес за полный контроль

---

## 6. Tailscale Funnel (Beta)

### Преимущества
- ✅ Бесплатный личный тариф
- ✅ HTTPS из коробки
- ✅ Безопасный (WireGuard)
- ✅ Публичный доступ без авторизации

### Установка

```bash
# Linux
curl -fsSL https://tailscale.com/install.sh | sh

# После установки
sudo tailscale up
```

### Настройка Funnel

**Активация Funnel (бесплатная, но в бета):**

```bash
sudo tailscale funnel --help
sudo tailscale funnel 8000
```

Tailscale предоставит публичный URL типа:
```
https://node-name.tailnet-name.ts.net
```

**Ограничения:**
- Требуется аккаунт Tailscale (бесплатный)
- Функция в бета-режиме
- Публичный домен не меняется

### Интеграция с systemd

Tailscale автоматически устанавливается как служба. Funnel также может быть добавлен как служба.

---

## 📊 Сравнительная таблица

| Характеристика | LocalTunnel | ngrok (free) | serveo.net | Bore | SSH Tunnel | Tailscale |
|---------------|-------------|--------------|------------|------|------------|-----------|
| **Стоимость** | Бесплатно | Бесплатно* | Бесплатно | Бесплатно | ~$5/мес | Бесплатно |
| **Связка карты** | ❌ Нет | ❌ Нет | ❌ Нет | ❌ Нет | ⚠️ Для VPS | ❌ Нет |
| **Свой домен** | ❌ Нет | ❌ Нет | ❌ Нет | ⚠️ Свой сервер | ✅ Да | ❌ Нет |
| **HTTPS** | ✅ Да | ✅ Да | ❌ Нет | ❌ Нет | ✅ Да (nginx) | ✅ Да |
| **Постоянный URL** | ⚠️ Нет | ⚠️ Случайный | ⚠️ Нет | ⚠️ Нет | ✅ Да | ✅ Да |
| **Мониторинг** | Базовый | ✅ Веб UI | ❌ Нет | ❌ Нет | Самостоятельно | ✅ Веб UI |
| **Ограничения** | Тайм-ауты | 2-8 часов | Нестабилен | Публичный сервер | Нет | Бета |

---

## 🎯 Рекомендации по выбору

### Для разработки и тестирования
**LocalTunnel** или **ngrok**
- Просты в использовании
- Не требуют настройки
- Работают сразу

### Для постоянного деплоя (без карты)
**SSH Reverse Tunnel на VPS**
- Полный контроль
- Свой домен
- Стабильная работа
- Примерно $5/мес

### Для быстрых демо
**serveo.net**
- Не требует установки
- Работает через SSH
- Но может быть нестабилен

### Для личных проектов (beta)
**Tailscale Funnel**
- Безопасно
- Постоянный URL
- Но в бета-режиме

---

## 🔧 Настройка ЯГК Schedule с альтернативами

### LocalTunnel

```bash
# На сервере
cd /opt/ygk
source venv/bin/activate

# Запуск веб-сервера
python web_main.py &

# В другом терминале
lt --port 8000 --subdomain ygk-schedule

# В Telegram BotFather установите URL Mini App:
# https://ygk-schedule.loca.lt/homework
```

### ngrok

```bash
# На сервере
cd /opt/ygk

# Запуск
ngrok http 8000

# Используйте полученный URL в настройках Mini App
```

### SSH Reverse Tunnel (VPS)

```bash
# На локальном сервере
sudo systemctl start ssh-reverse-tunnel

# Ваш сайт доступен по вашему домену:
# https://ygk.yourdomain.com

# В Telegram Mini Apps используйте этот URL
```

### systemd конфигурация для ЯГК

Создайте `/etc/systemd/system/ygk-with-tunnel.service`:

```ini
[Unit]
Description=ЯГК Schedule with LocalTunnel
After=network.target

[Service]
Type=forking
User=ygk
WorkingDirectory=/opt/ygk
Environment="PATH=/opt/ygk/venv/bin"
EnvironmentFile=/opt/ygk/.env

# Запуск веб-сервера
ExecStart=/opt/ygk/venv/bin/python web_main.py

# Запуск туннеля (добавьте после запуска веб-сервера)
ExecStartPost=/usr/bin/lt --port 8000 --subdomain ygk-schedule

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 🔒 Безопасность

### Общие рекомендации

1. **Используйте HTTPS** везде, где это возможно
2. **Ограничьте доступ** по IP, если возможно
3. **Используйте firewall** на сервере
4. **Мониторьте логи** на предмет подозрительной активности
5. **Регулярно обновляйте** инструменты

### Для публичных туннелей

- Не exposing чувствительные данные без аутентификации
- Используйте PIN-коды (уже реализовано в ЯГК)
- Рассмотрите rate-limiting

### Для SSH туннелей

- Используйте ключи вместо паролей
- Ограничьте пользователей в `.ssh/authorized_keys`
- Используйте `fail2ban` для защиты от брутфорса

---

## 📝 Мониторинг и логи

### LocalTunnel

```bash
# Просмотр логов systemd
sudo journalctl -u localtunnel -f

# Проверка доступности
curl https://ygk-schedule.loca.lt/
```

### ngrok

```bash
# Логи
sudo journalctl -u ngrok -f

# Веб-интерфейс
http://localhost:4040
```

### SSH туннель

```bash
# Проверка соединения
sudo journalctl -u ssh-reverse-tunnel -f

# Проверка порта
netstat -tlnp | grep 8000
```

---

## 🚀 Быстрый старт (без карты)

### Выберите и настройте за 5 минут:

**LocalTunnel:**
```bash
npm install -g localtunnel
lt --port 8000 --subdomain my-unique-name
```

**serveo.net:**
```bash
ssh -R my-unique-name:80:localhost:8000 serveo.net
```

**Bore:**
```bash
# Скачайте и запустите
bore local 8000 --to bore.pub
```

---

## 📚 Дополнительные ресурсы

- [LocalTunnel GitHub](https://github.com/localtunnel/localtunnel)
- [ngrok Documentation](https://ngrok.com/docs)
- [serveo.net](https://serveo.net/)
- [Bore GitHub](https://github.com/ekz/bore)
- [Tailscale Funnel](https://tailscale.com/kb/1183/funnel/)
- [SSH Reverse Tunnel Guide](https://www.digitalocean.com/community/tutorials/how-to-set-up-ssh-tunneling-on-linux)

---

**Обновлено:** February 2026
**Статус:** Бесплатные решения без привязки банковской карты
