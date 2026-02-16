# Excel to Schedule.json Converter

## Описание

Утилита `excel_to_schedule.py` конвертирует расписание из Excel формата в JSON формат для системы STTEC Schedule.

## ✅ Проверка совместимости

### Формат oit_2sem.xlsx (основной)

**Статус:** ✅ Полностью совместимо

**Тест проведен:** 47 групп, 6 дней (Пн-Сб), без разделения на числитель/знаменатель

**Результаты теста:**
- ✅ Загружено групп: 47
- ✅ Распознано уроков: 1606
- ✅ Листов в файле: 5
- ✅ Парсинг расписания: работает
- ✅ Нормализация названий групп: работает
- ✅ Поддержка множественных групп на листе: работает
- ✅ Форматирование для Telegram: работает

### Старый формат (также поддерживается)

**Статус:** ✅ Поддерживается для обратной совместимости

## Установка

```bash
pip install openpyxl==3.1.2
```

Или установлено в `requirements.txt`:
```
openpyxl==3.1.2
```

## Использование

### Базовое использование

```bash
python excel_to_schedule.py <файл.xlsx>
```

Результат будет сохранен в `schedule.json`.

### Указать выходной файл

```bash
python excel_to_schedule.py расписание.xlsx output.json
```

### Примеры

```bash
# Конвертировать oit_2sem.xlsx в schedule.json
python excel_to_schedule.py oit_2sem.xlsx

# Конвертировать с указанием выходного файла
python excel_to_schedule.py oit_2sem.xlsx schedule_2024.json
```

## Формат Excel файла

### Формат oit_2sem.xlsx (поддерживается)

```
┌──────────────┬──────────────────┬──────┬──────────┬──────┐
│ ИС1-11/ИС1-12│                  │      │          │      │  ← Заголовок групп
├──────────────┼──────────────────┼──────┼──────────┼──────┤
│ Понедельник  │                  │      │          │      │  ← День недели
├──────────────┼──────────────────┼──────┼──────────┼──────┤
│              │ Разговоры о важн │      │ Куликов  │ А201 │  ← 0-ая пара
├──────────────┼──────────────────┼──────┼──────────┼──────┤
│ 1            │ Физическая культура     │ Куликов  │ Сп.зал│ ← 1-я пара
├──────────────┼──────────────────┼──────┼──────────┼──────┤
│ 2            │ Иностранный язык        │ Зубковск │ А413 │  ← 2-я пара
└──────────────┴──────────────────┴──────┴──────────┴──────┘
```

**Структура:**
- **Строка 1**: Название группы (может содержать `/` для подгрупп)
- **Строки дней**: "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"
- **Строки пар**: 
  - Колонка 1: Номер пары (0-6)
  - Колонка 2: Название предмета
  - Колонка 6: Преподаватель
  - Колонка 9: Аудитория

**Особенности:**
- Несколько групп на одном листе (последовательно)
- Несколько листов в файле (по курсам/специальностям)
- Нет разделения на числитель/знаменатель (расписание одинаковое)
- Поддержка подгрупп через `/` в названии группы

### Горизонтальная раскладка (устаревший формат)

```
┌──────────────┬──────────┬──────────┬──────────┬─────┐
│ Время        │ ИС1-11   │ ИС1-12   │ ПО1-11   │ ... │
├──────────────┼──────────┼──────────┼──────────┼─────┤
│ Понедельник (Числитель)                             │
├──────────────┼──────────┼──────────┼──────────┼─────┤
│ 08:30-10:00  │ Матем.   │ Физика   │ История  │ ... │
│              │ Иванов   │ Петров   │ Сидоров  │     │
│              │ 201      │ 305      │ 102      │     │
├──────────────┼──────────┼──────────┼──────────┼─────┤
│ 10:10-11:40  │ Инфор.   │ ...      │ ...      │ ... │
└──────────────┴──────────┴──────────┴──────────┴─────┘
```

## Варианты записи уроков

**Вариант 1 (oit_2sem.xlsx):** Разделение по колонкам
```
Колонка 2: Математика
Колонка 6: Иванов И.И.
Колонка 9: 201
```

**Вариант 2 (старый формат):** Разделение переносом строки
```
Математика
Иванов И.И.
201
```

**Вариант 3 (старый формат):** Разделение запятыми
```
Математика, Иванов И.И., 201
```

### Названия групп

Поддерживаются любые форматы:
- `ИС1-11`
- `ИС1-11/ИС1-12` (слэш-нотация для объединенных групп в oit_2sem.xlsx)
- `ИС1-12/ИС1-13`
- `СА1-21`
- `ИБ1-31`
- и т.д.

Парсер автоматически нормализует названия для корректного сопоставления.

## Создание тестового файла

Для тестирования включен скрипт `create_test_excel.py`:

```bash
python create_test_excel.py
```

Создаст файл `test_schedule_32groups.xlsx` с:
- 32 группами
- 6 днями недели
- 2 неделями (числитель/знаменатель)
- 5 парами в день
- Случайным распределением предметов

## Результат конвертации

### Структура JSON

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
            "room": "201",
            "subgroups": false
          }
        ],
        "tuesday": [...],
        "wednesday": [...],
        "thursday": [...],
        "friday": [...],
        "saturday": [],
        "sunday": []
      },
      "denominator": {
        "monday": [...],
        ...
      }
    },
    "ИС1-12": {...},
    ...
  }
}
```

### Дни недели

Ключи в JSON:
- `monday` - Понедельник
- `tuesday` - Вторник
- `wednesday` - Среда
- `thursday` - Четверг
- `friday` - Пятница
- `saturday` - Суббота
- `sunday` - Воскресенье

### Недели

- `numerator` - Числитель (нечетные недели)
- `denominator` - Знаменатель (четные недели)

**Примечание:** Для oit_2sem.xlsx расписание одинаковое для числителя и знаменателя, так как в файле нет разделения.

## Интеграция с системой

После конвертации файл `schedule.json` автоматически используется системой:

1. **Telegram Bot** (`bot_main.py`) - для команд `/today`, `/tomorrow`, `/week`
2. **Web Server** (`web_main.py`) - для веб-интерфейса
3. **Core** (`core.py`) - для всех операций с расписанием

### Замена расписания

```bash
# Сделать бэкап
cp schedule.json schedule_backup.json

# Конвертировать новое расписание
python excel_to_schedule.py oit_2sem.xlsx schedule.json

# Перезапустить сервисы
sudo systemctl restart sttec-bot sttec-web
```

## Проверка результата

### Быстрая проверка

```bash
# Проверить количество групп
python -c "import json; d=json.load(open('schedule.json')); print(f'Groups: {len(d[\"groups\"])}')"

# Для oit_2sem.xlsx ожидается ~47 групп
```

### Детальная проверка

```python
import asyncio
from core import ScheduleManager
from datetime import date

async def test():
    sm = ScheduleManager('schedule.json')
    groups = sm.get_all_groups()
    print(f'Loaded {len(groups)} groups')
    
    # Проверить расписание для группы ИС1-11
    schedule = await sm.get_schedule_for_date('ИС1-11', date.today())
    print(f'Schedule: {len(schedule.lessons)} lessons')

asyncio.run(test())
```

## Распространенные проблемы

### Проблема: Группы не распознаются

**Причина:** Неправильный формат заголовков

**Решение:** Убедитесь, что:
- В oit_2sem.xlsx: название группы в первой строке листа
- Названия групп соответствуют паттерну: буквы + цифры + дефис + цифры
- Нет лишних пробелов

### Проблема: Пустое расписание

**Причина:** Не распознаются дни недели

**Решение:** Проверьте:
- Дни недели написаны на русском (Понедельник, Вторник, ...)
- Нет опечаток в названиях дней

### Проблема: Не найдены преподаватели/кабинеты

**Причина:** Неправильная структура колонок

**Решение:** Для oit_2sem.xlsx:
- Колонка 2: предмет
- Колонка 6: преподаватель  
- Колонка 9: кабинет

## Расширенные возможности

### Обработка нескольких файлов

```bash
#!/bin/bash
for file in расписания/*.xlsx; do
    basename=$(basename "$file" .xlsx)
    python excel_to_schedule.py "$file" "output_${basename}.json"
done
```

### Объединение расписаний

```python
import json

def merge_schedules(file1, file2, output):
    with open(file1) as f1, open(file2) as f2:
        data1 = json.load(f1)
        data2 = json.load(f2)
    
    # Объединить группы
    data1['groups'].update(data2['groups'])
    
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(data1, f, ensure_ascii=False, indent=2)

merge_schedules('schedule1.json', 'schedule2.json', 'merged.json')
```

### Валидация расписания

```python
import json
from datetime import datetime

def validate_schedule(filename):
    with open(filename, encoding='utf-8') as f:
        data = json.load(f)
    
    issues = []
    
    for group, schedule in data['groups'].items():
        for week in ['numerator', 'denominator']:
            for day, lessons in schedule[week].items():
                for i, lesson in enumerate(lessons):
                    # Проверка обязательных полей
                    if not lesson.get('subject'):
                        issues.append(f"{group}/{week}/{day}/lesson{i}: missing subject")
                    
                    # Проверка формата времени
                    time = lesson.get('time', '')
                    if not time or ':' not in time or '-' not in time:
                        issues.append(f"{group}/{week}/{day}/lesson{i}: invalid time format")
    
    if issues:
        print(f"Found {len(issues)} issues:")
        for issue in issues[:10]:  # Показать первые 10
            print(f"  - {issue}")
    else:
        print("✅ Schedule is valid!")

validate_schedule('schedule.json')
```

## Статистика

### Анализ расписания

```python
import json

def analyze_schedule(filename):
    with open(filename, encoding='utf-8') as f:
        data = json.load(f)
    
    total_groups = len(data['groups'])
    total_lessons = 0
    subjects = set()
    teachers = set()
    rooms = set()
    
    for group, schedule in data['groups'].items():
        for week in ['numerator', 'denominator']:
            for day, lessons in schedule[week].items():
                total_lessons += len(lessons)
                for lesson in lessons:
                    subjects.add(lesson.get('subject', ''))
                    if lesson.get('teacher'):
                        teachers.add(lesson['teacher'])
                    if lesson.get('room'):
                        rooms.add(lesson['room'])
    
    print(f"📊 Schedule Statistics:")
    print(f"   Groups: {total_groups}")
    print(f"   Total lessons: {total_lessons}")
    print(f"   Unique subjects: {len(subjects)}")
    print(f"   Unique teachers: {len(teachers)}")
    print(f"   Unique rooms: {len(rooms)}")
    print(f"   Average lessons per group: {total_lessons / total_groups:.1f}")

analyze_schedule('schedule.json')
```

## Оптимизация для 8GB RAM

Конвертер оптимизирован для работы на сервере с 8GB RAM:

- Использует потоковое чтение Excel для больших файлов
- Не загружает весь файл в память одновременно
- Эффективно обрабатывает множественные листы
- Очищает неиспользуемые объекты после обработки каждого листа

## Поддержка

При возникновении проблем:

1. Проверьте формат Excel файла
2. Убедитесь, что установлена библиотека openpyxl
3. Проверьте логи конвертации
4. Валидируйте результат с помощью приведенных скриптов

## Changelog

### v2.0 (2026-02-16)
- ✅ Поддержка формата oit_2sem.xlsx
- ✅ Множественные группы на одном листе
- ✅ Множественные листы в файле
- ✅ Автоматическое определение структуры файла
- ✅ Оптимизация для 8GB RAM
- ✅ Поддержка 47+ групп

### v1.0 (2026-02-16)
- ✅ Первая версия
- ✅ Поддержка горизонтальной раскладки
- ✅ Автоматическое определение числителя/знаменателя
- ✅ Нормализация названий групп
- ✅ Поддержка 32+ групп
- ✅ Тестовый генератор расписания
- ✅ Полная совместимость с core.py

---

**Версия:** 2.0  
**Дата:** 16 февраля 2026  
**Автор:** STTEC Schedule Team
