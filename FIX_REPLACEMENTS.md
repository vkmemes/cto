# Исправление проблемы с заменами в расписании

## Проблема
Бот не применял замены к расписанию - при наличии замен для группы возвращались только замены, а базовое расписание полностью игнорировалось.

## Причины

### 1. Неправильная логика применения замен
В методе `get_schedule_for_date()` файла `core.py` была следующая логика:
```python
if replacement_data and replacement_data.get("date") == date_str:
    lessons = [Lesson(**lesson_dict) for lesson_dict in replacement_data["lessons"]]
    return DaySchedule(date_str=date_str, lessons=lessons, is_weekend=False)
```

Это означало, что если есть замены для даты, возвращались **только** замены, а всё базовое расписание на этот день игнорировалось.

### 2. Отсутствие определения номера пары по времени
Пары в базовом расписании (`schedule.json`) не имеют поля `pair_number`, только время. Парсер замен назначал номера пар последовательно (`len(lessons_data) + 1`), что не соответствовало номерам пар в базовом расписании.

### 3. Некорректное сопоставление замен
Из-за того, что номера пар определялись по-разному в базовом расписании и заменах, замены не могли корректно примениться к соответствующим парам.

## Решения

### 1. Исправлена логика применения замен
Теперь метод `get_schedule_for_date()`:
1. Сначала загружает базовое расписание для дня
2. Определяет номера пар по времени для базового расписания
3. Если есть замены для этой даты, применяет их к базовому расписанию:
   - Создаёт маппинг по номеру пары
   - Заменяет только те пары, для которых есть замены
   - Оставляет базовые пары без изменений
   - Добавляет новые пары, если они есть только в заменах
   - Сортирует пары по номеру

### 2. Добавлена функция определения номера пары по времени
```python
PAIR_TIMES = {
    1: ("08:30", "10:00"),
    2: ("10:10", "11:40"),
    3: ("12:00", "13:30"),
    4: ("13:40", "15:10"),
    5: ("15:20", "16:50"),
    6: ("17:00", "18:30"),
    7: ("18:40", "20:10"),
}

def get_pair_number_from_time(time_str: str) -> int:
    """Determine pair number from time string (e.g., '08:30-10:00')."""
    if not time_str or "-" not in time_str:
        return 0

    try:
        start_time = time_str.split("-")[0].strip()
        for pair_num, (pair_start, _) in PAIR_TIMES.items():
            if start_time == pair_start:
                return pair_num
    except Exception:
        pass

    return 0
```

### 3. Обновлён парсер HTML для замен
Теперь парсер использует `get_pair_number_from_time()` для определения номера пары по времени:
```python
# Determine pair number from time
pair_number = get_pair_number_from_time(time)
if pair_number == 0:
    # Fallback to sequential numbering if time parsing fails
    pair_number = len(lessons_data) + 1
```

### 4. Обновлено создание пар из базового расписания
Базовое расписание тоже теперь определяет номера пар по времени:
```python
for idx, lesson_dict in enumerate(schedule_data):
    time_str = lesson_dict.get("time", "")
    pair_number = get_pair_number_from_time(time_str)
    if pair_number == 0:
        # Fallback to index-based numbering if time parsing fails
        pair_number = idx + 1
```

### 5. Улучшена обработка ошибок при загрузке замен
Добавлена более детальная обработка ошибок HTTP:
```python
except httpx.HTTPError as e:
    print(f"[ScheduleManager] HTTP error fetching replacements: {e}")
    return {}
except Exception as e:
    print(f"[ScheduleManager] Error fetching replacements: {e}")
    return {}
```

## Тестирование

Созданы тестовые файлы:
- `test_replacements.html` - пример HTML с заменами
- `test_replacements.py` - тесты для проверки логики

Результаты тестов:
- ✓ Определение номера пары по времени работает правильно
- ✓ Парсинг HTML для замен работает правильно
- ✓ Применение замен к базовому расписанию работает правильно

Пример результата:
```
Schedule for МА1-11 on 17.02.2025:
  🟡 Pair 1: Математика (замена) (08:30-10:00) [REPLACED]
  🟡 Pair 2: Физика (10:10-11:40) [REPLACED]
  🔵 Pair 3: Физическая культура (12:00-13:30) [BASE]
  🔵 Pair 4: Индивидуальный проект (13:40-15:10) [BASE]

Summary: 2 replaced lessons, 2 base lessons
```

## Изменённые файлы

1. `core.py` - основные исправления логики
2. `.gitignore` - добавлен шаблон для тестовых HTML файлов
3. `FIX_REPLACEMENTS.md` - этот файл

## Дальнейшие действия

Для работы замен необходимо:
1. Настроить переменную окружения `REPLACEMENT_URL` с правильным URL страницы замен
2. Убедиться, что HTML-структура страницы замен соответствует ожидаемому формату
3. Проверить, что все необходимые поля (время, предмет, преподаватель, аудитория) присутствуют в HTML
