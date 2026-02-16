# Excel to Schedule.json Converter

## Описание

Утилита `excel_to_schedule.py` конвертирует расписание из Excel формата в JSON формат для системы STTEC Schedule.

## ✅ Проверка совместимости

**Статус:** Полностью совместимо с парсером

**Тест проведен:** 32 группы, 6 дней, 2 недели (числитель/знаменатель)

**Результаты теста:**
- ✅ Загружено групп: 32
- ✅ Распознано уроков: 1351
- ✅ Парсинг расписания: работает
- ✅ Нормализация названий групп: работает
- ✅ Поддержка числителя/знаменателя: работает
- ✅ Форматирование для Telegram: работает

## Установка

```bash
pip install openpyxl==3.1.2
```

Или добавлена в `requirements.txt`:
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
python excel_to_schedule.py расписание_2024.xlsx schedule_2024.json
```

## Формат Excel файла

### Горизонтальная раскладка (рекомендуется)

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

### Требования к формату

1. **Первая строка:** названия групп (начиная со 2-й колонки)
2. **Первая колонка:** время или название дня недели
3. **Ячейки уроков:** должны содержать:
   - Предмет (обязательно)
   - Преподаватель (опционально)
   - Аудитория (опционально)
   
   Разделители: перенос строки (`\n`) или запятая

4. **Дни недели:** должны содержать ключевые слова:
   - Понедельник, Вторник, Среда, Четверг, Пятница, Суббота
   - Или сокращения: Пн, Вт, Ср, Чт, Пт, Сб

5. **Недели:** должны содержать:
   - Числитель или Чис
   - Знаменатель или Знам

### Варианты записи уроков

**Вариант 1 (рекомендуется):** Разделение переносом строки
```
Математика
Иванов И.И.
201
```

**Вариант 2:** Разделение запятыми
```
Математика, Иванов И.И., 201
```

**Вариант 3:** Только предмет
```
Математика
```

### Названия групп

Поддерживаются любые форматы:
- `ИС1-11`
- `ИС1-12/ИС1-13` (слэш-нотация для объединенных групп)
- `ПО2-14`
- `СА1-11`
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
            "room": "201"
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
python excel_to_schedule.py новое_расписание.xlsx schedule.json

# Перезапустить сервисы
sudo systemctl restart sttec-bot sttec-web
```

## Проверка результата

### Быстрая проверка

```bash
# Проверить количество групп
python -c "import json; d=json.load(open('schedule.json')); print(f'Groups: {len(d[\"groups\"])}')"
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
    
    # Проверить расписание для первой группы
    schedule = await sm.get_schedule_for_date(groups[0], date.today())
    print(f'Schedule: {len(schedule.lessons)} lessons')

asyncio.run(test())
```

## Распространенные проблемы

### Проблема: Группы не распознаются

**Причина:** Неправильный формат заголовков

**Решение:** Убедитесь, что:
- Первая строка содержит названия групп
- Названия групп соответствуют паттерну: буквы + цифры + дефис + цифры
- Нет лишних пробелов

### Проблема: Пустое расписание

**Причина:** Не распознаются дни недели или время

**Решение:** Проверьте:
- Первая колонка содержит дни недели на русском
- Время в формате `ЧЧ:ММ-ЧЧ:ММ`
- Нет опечаток в названиях дней

### Проблема: Уроки объединяются неправильно

**Причина:** Неправильное распознавание числителя/знаменателя

**Решение:** Добавьте явные заголовки:
- "Понедельник (Числитель)"
- "Понедельник (Знаменатель)"

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

## Поддержка

При возникновении проблем:

1. Проверьте формат Excel файла
2. Убедитесь, что установлена библиотека openpyxl
3. Проверьте логи конвертации
4. Валидируйте результат с помощью приведенных скриптов

## Changelog

### v1.0 (2026-02-16)
- ✅ Первая версия
- ✅ Поддержка горизонтальной раскладки
- ✅ Автоматическое определение числителя/знаменателя
- ✅ Нормализация названий групп
- ✅ Поддержка 32+ групп
- ✅ Тестовый генератор расписания
- ✅ Полная совместимость с core.py

---

**Версия:** 1.0  
**Дата:** 16 февраля 2026  
**Автор:** STTEC Schedule Team
