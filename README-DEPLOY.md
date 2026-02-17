# Быстрый деплой STTEC

## Первая настройка сервера (делается один раз)

1. Зайди на сервер по SSH:
   ```bash
   ssh root@IP-СЕРВЕРА
   ```

2. Скачай и выполни скрипт настройки:
   ```bash
   curl -O https://raw.githubusercontent.com/твой-репозиторий/server-setup.sh
   bash server-setup.sh
   ```

3. Скопируй файлы проекта в `/opt/sttec`:
   ```bash
   # С локальной машины
   rsync -avz . root@IP-СЕРВЕРА:/opt/sttec/
   ```

4. Запусти сервисы:
   ```bash
   systemctl start sttec-bot sttec-web sttec-tunnel
   ```

---

## Обновление (деплой) - делается с локальной машины

Просто запусти:
```bash
./deploy.sh
```

Всё! Скрипт сам:
- ✅ Скопирует файлы
- ✅ Установит зависимости
- ✅ Перезапустит сервисы

---

## Управление на сервере

Посмотреть статус:
```bash
systemctl status sttec-bot sttec-web sttec-tunnel
```

Просмотр логов:
```bash
# Бот
journalctl -u sttec-bot -f

# Веб
journalctl -u sttec-web -f

# Туннель
journalctl -u sttec-tunnel -f

# Все сразу
journalctl -u sttec-* -f
```

Перезапуск:
```bash
systemctl restart sttec-bot sttec-web sttec-tunnel
```

---

## Доступ

- **Бот:** @имя_бота
- **Веб:** https://sttec.loca.lt
- **Mini Apps:** работают через бота

---

## Файлы для деплоя

В корне проекта должно быть:
- `deploy.sh` - скрипт деплоя (на локальной машине)
- `bot_main.py` - бот
- `web_main.py` - веб-сервер
- `core.py` - ядро
- `database.py` - БД
- `requirements.txt` - зависимости
- `templates/` - HTML шаблоны

---

## Изменить настройки

Отредактируй `deploy.sh` и укажи:
```bash
SERVER_USER="root"              # пользователь на сервере
SERVER_IP="192.168.1.100"       # IP адрес сервера
SERVER_PATH="/opt/sttec"        # папка на сервере
```
