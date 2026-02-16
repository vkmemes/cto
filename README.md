# STTEC Schedule System

Система управления расписанием для Ярославского строительного колледжа, включающая Telegram бота, парсер расписания и веб-интерфейс с поддержкой Telegram Mini Apps.

## Основные возможности

### Telegram Bot
- 📅 Просмотр расписания на сегодня/завтра/неделю
- 🔔 Автоматические уведомления о заменах
- 👥 Регистрация студентов с выбором группы
- 📌 Система дежурств с автоматической ротацией
- 🤒 Отметки о болезни студентов
- 🔐 PIN-коды для групп (устанавливаются старостами)

### Web Interface
- 📱 PWA-совместимый интерфейс
- 📝 Форма для добавления домашнего задания
- 👨‍🎓 Панель старосты (управление группой)
- 🔄 REST API для интеграции с Mini Apps
- 📊 API для виджетов (KWGT)

### Core Features
- 🔀 Гибридное расписание (статическое + замены)
- 🔄 Парсинг заменных пар с HTML-страницы
- 📆 Автоматический расчет четности недели
- 🎯 Умное сопоставление групп (поддержка слэш-нотации)
- 💾 Кэширование с TTL 5 минут

## Архитектура

```
project/
├── core.py              # Логика расписания (ScheduleManager)
├── database.py          # База данных (SQLAlchemy + SQLite)
├── bot_main.py          # Telegram бот
├── web_main.py          # Web сервер (Starlette)
├── migrate.py           # Миграция БД
├── schedule.json        # Базовое расписание
├── requirements.txt     # Python зависимости
├── templates/           # HTML шаблоны
│   ├── schedule_view_template.html
│   ├── homework_form.html
│   └── headman_panel.html
└── logs/                # Логи
```

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository_url>
cd project
```

### 2. Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

```bash
cp .env.example .env
nano .env  # Отредактируйте файл
```

Необходимые переменные:
- `BOT_TOKEN` - токен Telegram бота (получите у @BotFather)
- `CHANNEL_USERNAME` - имя канала для обязательной подписки (например, @sttec_channel)
- `REPLACEMENT_URL` - URL страницы с заменами
- `DATABASE_URL` - путь к БД (по умолчанию SQLite)
- `WEB_PORT` - порт веб-сервера (по умолчанию 8000)

### 5. Инициализация базы данных

```bash
python migrate.py
```

### 6. Настройка расписания

#### Вариант 1: Конвертация из Excel (рекомендуется)

Система поддерживает конвертацию расписания из Excel формата `oit_2sem.xlsx`:

```bash
# Конвертировать Excel в JSON
python excel_to_schedule.py oit_2sem.xlsx

# Результат будет сохранен в schedule.json
```

**Поддерживаемый формат:**
- ✅ 47+ групп
- ✅ Множественные листы в файле
- ✅ Множественные группы на одном листе
- ✅ Структура: Номер пары → Предмет → Преподаватель → Кабинет
- ✅ Оптимизировано для сервера с 8GB RAM

Подробнее см. [EXCEL_CONVERTER.md](EXCEL_CONVERTER.md)

#### Вариант 2: Ручное редактирование

Отредактируйте файл `schedule.json` согласно вашему расписанию. Формат:

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

## Запуск

### Режим разработки

**Запуск бота:**
```bash
python bot_main.py
```

**Запуск веб-сервера:**
```bash
python web_main.py
```

### Продакшн (systemd)

> 📚 **Документация по деплою:**
> - [DEPLOYMENT_CLOUDPUB.md](DEPLOYMENT_CLOUDPUB.md) - Деплой через Cloudflare Tunnel (свой домен)
> - [DEPLOYMENT_ALTERNATIVES.md](DEPLOYMENT_ALTERNATIVES.md) - Бесплатные альтернативы без привязки карты

**Создайте файл `/etc/systemd/system/sttec-bot.service`:**

```ini
[Unit]
Description=STTEC Schedule Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/venv/bin"
EnvironmentFile=/path/to/project/.env
ExecStart=/path/to/venv/bin/python bot_main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Создайте файл `/etc/systemd/system/sttec-web.service`:**

```ini
[Unit]
Description=STTEC Schedule Web
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/venv/bin"
EnvironmentFile=/path/to/project/.env
ExecStart=/path/to/venv/bin/python web_main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Запуск сервисов:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable sttec-bot sttec-web
sudo systemctl start sttec-bot sttec-web
sudo systemctl status sttec-bot sttec-web
```

## Использование

### Команды бота

- `/start` - Регистрация и выбор группы
- `/today` - Расписание на сегодня
- `/tomorrow` - Расписание на завтра
- `/week` - Расписание на неделю
- `/setpin <PIN>` - Установить PIN-код группы (только староста)

### Deep Linking

```
https://t.me/your_bot?start=ИС1-11
```

Автоматически устанавливает группу пользователю.

### Web API

**Получить расписание:**
```
GET /api/schedule?group=ИС1-11&date=15.02.2026
```

**Получить домашнее задание:**
```
GET /api/homework?group=ИС1-11&pin=1234
```

**Добавить домашнее задание:**
```
POST /api/homework
Content-Type: application/json

{
  "group": "ИС1-11",
  "pin": "1234",
  "subject": "Математика",
  "text": "Задачи 1-10",
  "mode": "overwrite"
}
```

**Управление группой (панель старосты):**
```
GET /api/headman?group=ИС1-11&pin=1234
POST /api/headman
{
  "group": "ИС1-11",
  "pin": "1234",
  "action": "set_duty",
  "user_id": 123456789
}
```

### Telegram Mini Apps

1. Создайте Mini App в @BotFather
2. Установите URL: `https://your-domain.com/homework`
3. Пользователи смогут открывать панель через кнопку в боте

## Scheduled Jobs

Бот автоматически выполняет следующие задачи:

- **12:05** - Проверка заменных пар и рассылка уведомлений
- **14:00** - Автоматическая смена дежурного
- **17:00** - Напоминание дежурному
- **00:00** - Сброс отметок о болезни

## Системные требования

### Рекомендуемая конфигурация (8GB RAM)

Оптимальная конфигурация для работы с большими файлами расписания:

- **RAM:** 8GB
- **CPU:** 2+ ядра
- **Диск:** 10GB SSD
- **OS:** Ubuntu 20.04/22.04 LTS

С такой конфигурацией система:
- ✅ Быстро конвертирует Excel файлы с 50+ группами
- ✅ Обрабатывает множественные листы без проблем с памятью
- ✅ Работает с большой базой пользователей

### Минимальная конфигурация (512MB RAM)

Для тестирования или небольших групп:

- **RAM:** 512MB+
- **CPU:** 1 ядро
- **Диск:** 5GB

**Рекомендации:**
1. **SQLite с пулом соединений** (pool_size=5)
2. **Кэширование заменных пар** (TTL 5 минут)
3. **Асинхронная архитектура** (async/await)
4. **Минимальные зависимости**

Включите swap:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## Логи

Логи записываются в:
- `logs/bot.log` - логи бота
- `logs/web.log` - логи веб-сервера

Просмотр логов systemd:
```bash
sudo journalctl -u sttec-bot -f
sudo journalctl -u sttec-web -f
```

## Безопасность

- ✅ PIN-аутентификация для панели старосты
- ✅ Валидация всех входных данных
- ✅ Параметризованные SQL-запросы (SQLAlchemy ORM)
- ✅ Ограничение CORS
- ✅ Обработка ошибок Telegram API

## Troubleshooting

**Бот не отвечает:**
```bash
sudo systemctl status sttec-bot
sudo journalctl -u sttec-bot -n 50
```

**Ошибки базы данных:**
```bash
python migrate.py  # Пересоздать схему
```

**Замены не парсятся:**
- Проверьте `REPLACEMENT_URL` в `.env`
- Убедитесь, что HTML-структура соответствует коду в `core.py`

## Расширение функционала

### Добавление новой команды бота

1. Создайте функцию-обработчик в `bot_main.py`
2. Зарегистрируйте CommandHandler
3. Обновите middleware при необходимости

### Добавление нового API endpoint

1. Создайте функцию в `web_main.py`
2. Добавьте Route в список `routes`
3. Обновите документацию

### Миграция на PostgreSQL

Измените `DATABASE_URL` в `.env`:
```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/sttec
```

Установите драйвер:
```bash
pip install asyncpg
```

## Лицензия

MIT License

## Поддержка

Для вопросов и предложений создайте Issue в репозитории.
