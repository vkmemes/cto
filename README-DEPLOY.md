# Быстрый деплой STTEC с GitHub

## Первая настройка сервера (один раз)

Зайди на сервер по SSH:
```bash
ssh root@IP-СЕРВЕРА
```

Выполни скрипт настройки:
```bash
bash <(curl -s https://raw.githubusercontent.com/твой-юзер/твой-репозиторий/main/server-setup.sh)
```

**Или вручную:**
```bash
# Скопируй server-setup.sh на сервер
# Выполни:
bash server-setup.sh
```

Сервер сам:
- ✅ Клонирует репозиторий с GitHub
- ✅ Установит все зависимости
- ✅ Создаст systemd сервисы
- ✅ Настроит localtunnel
- ✅ Запустит всё

---

## Как обновлять код (деплой)

Просто сделай push в GitHub с локальной машины:

```bash
git add .
git commit -m "новые изменения"
git push origin main
```

Сервер сам:
1. Проверит изменения каждые 5 минут
2. Выполнит `git pull`
3. Установит зависимости
4. Перезапустит сервисы

**Максимальное время ожидания:** 5 минут

---

## Срочное обновление (не ждать 5 минут)

Зайди на сервер и запусти вручную:

```bash
ssh root@IP-СЕРВЕРА
/opt/sttec/update.sh
```

Обновление произойдет мгновенно!

---

## Управление на сервере

**Статус сервисов:**
```bash
systemctl status sttec-bot sttec-web sttec-tunnel
```

**Логи:**
```bash
# Все сервисы
journalctl -u sttec-* -f

# Отдельно
journalctl -u sttec-bot -f
journalctl -u sttec-web -f
journalctl -u sttec-tunnel -f

# Логи автодеплоя
tail -f /opt/sttec/logs/update.log
```

**Перезапуск:**
```bash
systemctl restart sttec-bot sttec-web sttec-tunnel
```

**Стоп/Старт:**
```bash
systemctl stop sttec-bot sttec-web sttec-tunnel
systemctl start sttec-bot sttec-web sttec-tunnel
```

---

## Доступ

- **Бот:** @имя_бота
- **Веб:** https://sttec.loca.lt
- **Mini Apps:** работают через бота

---

## Структура репозитория

```
GitHub репозиторий
├── bot_main.py          - бот
├── web_main.py          - веб-сервер
├── core.py              - ядро
├── database.py          - БД
├── requirements.txt     - зависимости
├── migrate.py           - миграции БД
├── update.sh            - скрипт обновления (на сервере)
├── server-setup.sh      - первичная настройка (на сервере)
├── README-DEPLOY.md     - эта инструкция
├── .gitignore           - исключить из git
└── templates/           - HTML шаблоны
```

---

## .gitignore (что НЕ коммитить)

```text
# База данных
*.db
sttec.db

# Логи
logs/
*.log

# Python
__pycache__/
*.pyc
*.pyo
.Python

# Виртуальное окружение
venv/
env/
.venv/

# Окружение
.env
.env.local
.env.localtunnel

# Node.js
node_modules/

# IDE
.vscode/
.idea/
*.swp
```

---

## Что происходит на сервере

**Каждые 5 минут cron запускает:**
1. `/opt/sttec/update.sh`
2. Проверяет есть ли изменения в GitHub
3. Если есть:
   - `git pull`
   - `pip install -r requirements.txt`
   - `python3 migrate.py` (если есть изменения)
   - `systemctl restart sttec-bot sttec-web`

**При перезагрузке сервера:**
- systemd автоматически запускает все сервисы
- localtunnel создает туннель
- бот начинает работу

---

## Изменить настройки

В `server-setup.sh` укажи:
```bash
GITHUB_REPO="https://github.com/твой-юзер/твой-репозиторий.git"
BRANCH="main"
```

В локальном репозитории укажи в `web_main.py`:
```python
BASE_URL = "https://sttec.loca.lt"
```

---

## Частые вопросы

**Q: Как изменить поддомен localtunnel?**
A: Отредактируй `/etc/systemd/system/sttec-tunnel.service` и поменяй `--subdomain sttec`

**Q: Как изменить интервал проверки обновлений?**
A: Отредактируй cron: `*/5 * * * *` (5 минут) → `*/10 * * * *` (10 минут)

**Q: Можно ли отследить когда был последний деплой?**
A: `tail /opt/sttec/logs/update.log`

**Q: Что если update.sh упадет с ошибкой?**
A: Ошибка будет в логе, сервисы продолжат работать с предыдущей версией
