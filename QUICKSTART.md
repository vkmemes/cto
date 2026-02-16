# STTEC Schedule - Quick Start Guide

## 🚀 Быстрый запуск (5 минут)

### 1. Установка зависимостей

```bash
# Создайте виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или venv\Scripts\activate для Windows

# Установите пакеты
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

```bash
# Скопируйте шаблон
cp .env.example .env

# Отредактируйте файл .env
nano .env
```

Минимальная конфигурация:
```
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz  # От @BotFather
CHANNEL_USERNAME=@your_channel_name
REPLACEMENT_URL=https://example.com/replacements.html
```

### 3. Инициализация базы данных

```bash
python migrate.py
```

Вы увидите:
```
Starting database migration...
✅ Database schema created/updated successfully!

Tables created:
  - users
  - group_settings
  - group_pins
  - students
  - homework
```

### 4. Настройка расписания

Отредактируйте `schedule.json`:

```json
{
  "groups": {
    "ИС1-11": {
      "numerator": {
        "monday": [
          {
            "time": "08:30-10:00",
            "subject": "Математика",
            "teacher": "Иванов И.И.",
            "room": "201"
          }
        ]
      },
      "denominator": {
        "monday": [...]
      }
    }
  }
}
```

### 5. Запуск системы

**Терминал 1 - Бот:**
```bash
python bot_main.py
```

**Терминал 2 - Веб-сервер:**
```bash
python web_main.py
```

### 6. Тестирование

1. Откройте Telegram и найдите вашего бота
2. Отправьте команду `/start`
3. Выберите группу из списка
4. Введите ФИО
5. Используйте команды:
   - `/today` - расписание на сегодня
   - `/tomorrow` - расписание на завтра
   - `/week` - расписание на неделю

Веб-интерфейс доступен по адресу:
- http://localhost:8000/ - просмотр расписания
- http://localhost:8000/homework - форма домашнего задания
- http://localhost:8000/headman - панель старосты

## 📋 Чек-лист перед запуском

- [ ] Python 3.8+ установлен
- [ ] Виртуальное окружение создано
- [ ] Зависимости установлены (`pip install -r requirements.txt`)
- [ ] Файл `.env` создан и заполнен
- [ ] Получен BOT_TOKEN от @BotFather
- [ ] Канал для подписки создан
- [ ] База данных инициализирована (`python migrate.py`)
- [ ] Файл `schedule.json` заполнен расписанием
- [ ] Директория `logs/` создана

## 🔧 Настройка Telegram бота

1. Откройте [@BotFather](https://t.me/BotFather)
2. Создайте нового бота: `/newbot`
3. Введите имя: `STTEC Schedule`
4. Введите username: `sttec_schedule_bot`
5. Скопируйте токен в `.env`
6. Настройте команды:

```
/setcommands

start - Начать работу и выбрать группу
today - Расписание на сегодня
tomorrow - Расписание на завтра
week - Расписание на неделю
setpin - Установить PIN-код группы (староста)
```

7. Опционально: настройте Mini App

```
/newapp
/setappdomain - https://your-domain.com
```

## 📱 Настройка канала

1. Создайте публичный канал в Telegram
2. Установите username канала (например, `@sttec_channel`)
3. Добавьте бота как администратора канала
4. Укажите username в `.env`: `CHANNEL_USERNAME=@sttec_channel`

## 🔐 Настройка PIN-кодов

PIN-коды используются для доступа к панели старосты.

**Через бота:**
1. Зарегистрируйте студента как старосту в БД:
   ```python
   import asyncio
   from database import Database
   
   async def set_headman():
       db = Database()
       await db.init_db()
       await db.upsert_student("ИС1-11", 123456789, "Иванов Иван", is_headman=True)
       await db.close()
   
   asyncio.run(set_headman())
   ```

2. Староста использует команду: `/setpin 1234`

**Напрямую через БД:**
```python
import asyncio
from database import Database

async def set_pin():
    db = Database()
    await db.init_db()
    await db.set_group_pin("ИС1-11", "1234", created_by=123456789)
    await db.close()

asyncio.run(set_pin())
```

## 🌐 API Endpoints

### Получить расписание
```bash
curl "http://localhost:8000/api/schedule?group=ИС1-11&date=15.02.2026"
```

### Добавить домашнее задание
```bash
curl -X POST "http://localhost:8000/api/homework" \
  -H "Content-Type: application/json" \
  -d '{
    "group": "ИС1-11",
    "pin": "1234",
    "subject": "Математика",
    "text": "Задачи 1-10",
    "mode": "overwrite"
  }'
```

### Получить список студентов
```bash
curl "http://localhost:8000/api/headman?group=ИС1-11&pin=1234"
```

## 📊 Мониторинг

### Просмотр логов
```bash
# Логи бота
tail -f logs/bot.log

# Логи веб-сервера
tail -f logs/web.log
```

### Проверка базы данных
```bash
sqlite3 sttec.db "SELECT * FROM users;"
sqlite3 sttec.db "SELECT * FROM students;"
sqlite3 sttec.db "SELECT * FROM group_settings;"
```

## 🐛 Устранение проблем

### Ошибка: ModuleNotFoundError
```bash
# Убедитесь, что виртуальное окружение активировано
source venv/bin/activate

# Переустановите зависимости
pip install -r requirements.txt
```

### Ошибка: BOT_TOKEN not set
```bash
# Проверьте файл .env
cat .env

# Убедитесь, что переменная установлена
export BOT_TOKEN="your_token_here"
```

### Ошибка: Cannot connect to database
```bash
# Проверьте права доступа
ls -la sttec.db

# Пересоздайте базу данных
rm sttec.db
python migrate.py
```

### Бот не отвечает на команды
1. Проверьте, что бот запущен: `ps aux | grep bot_main.py`
2. Проверьте логи: `tail -f logs/bot.log`
3. Убедитесь, что подписаны на канал
4. Проверьте токен бота

### Замены не парсятся
1. Проверьте URL: `curl $REPLACEMENT_URL`
2. Проверьте HTML-структуру в `core.py`
3. Адаптируйте парсер под вашу структуру HTML

## 🚀 Production Deployment

### Использование systemd (рекомендуется)

1. Отредактируйте пути в сервисных файлах:
   ```bash
   nano sttec-bot.service
   nano sttec-web.service
   ```

2. Скопируйте файлы в systemd:
   ```bash
   sudo cp sttec-bot.service /etc/systemd/system/
   sudo cp sttec-web.service /etc/systemd/system/
   ```

3. Запустите сервисы:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable sttec-bot sttec-web
   sudo systemctl start sttec-bot sttec-web
   ```

4. Проверьте статус:
   ```bash
   sudo systemctl status sttec-bot
   sudo systemctl status sttec-web
   ```

### Использование screen (альтернатива)

```bash
# Запуск бота
screen -S sttec-bot
python bot_main.py
# Нажмите Ctrl+A, затем D для отсоединения

# Запуск веб-сервера
screen -S sttec-web
python web_main.py
# Нажмите Ctrl+A, затем D для отсоединения

# Список сессий
screen -ls

# Подключение к сессии
screen -r sttec-bot
```

## 📈 Масштабирование

### Миграция на PostgreSQL

1. Установите PostgreSQL:
   ```bash
   sudo apt install postgresql postgresql-contrib
   ```

2. Создайте базу данных:
   ```sql
   CREATE DATABASE sttec;
   CREATE USER sttec WITH PASSWORD 'password';
   GRANT ALL PRIVILEGES ON DATABASE sttec TO sttec;
   ```

3. Установите драйвер:
   ```bash
   pip install asyncpg
   ```

4. Обновите `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://sttec:password@localhost/sttec
   ```

5. Выполните миграцию:
   ```bash
   python migrate.py
   ```

## 💡 Полезные команды

```bash
# Проверка версии Python
python3 --version

# Просмотр установленных пакетов
pip list

# Обновление зависимостей
pip install --upgrade -r requirements.txt

# Бэкап базы данных
cp sttec.db sttec.db.backup

# Восстановление бэкапа
cp sttec.db.backup sttec.db

# Очистка логов
> logs/bot.log
> logs/web.log
```

## 📚 Дополнительные ресурсы

- [Python Telegram Bot Documentation](https://python-telegram-bot.readthedocs.io/)
- [Starlette Documentation](https://www.starlette.io/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)

## ✅ Готово!

Ваша система STTEC Schedule должна быть запущена и готова к использованию!

Для получения справки используйте:
```bash
python bot_main.py --help
python web_main.py --help
```

---

**Создано:** 2026  
**Лицензия:** MIT  
**Поддержка:** Создайте Issue в репозитории
