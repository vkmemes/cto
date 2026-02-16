
                 EXCEL TO JSON CONVERTER - QUICK START                        ║


 СТАТУС: Полностью протестирован и готов к использованию
 СОВМЕСТИМОСТЬ: 32 группы × 6 дней × 2 недели = проверено




1. Установить зависимость:
   pip install openpyxl==3.1.2

2. Конвертировать Excel:
   python excel_to_schedule.py расписание.xlsx

3. Проверить результат:
   python -c "import json; print(len(json.load(open('schedule.json'))['groups']), 'groups')"

4. Использовать в системе:
   sudo systemctl restart sttec-bot sttec-web




  excel_to_schedule.py       - Конвертер Excel → JSON (исполняемый)
  create_test_excel.py       - Генератор тестовых данных
  
  EXCEL_CONVERTER.md         - Полное руководство (9.5 KB)
  COMPATIBILITY_TEST_REPORT.md - Отчет о тестировании (15 KB)
  COMPATIBILITY_SUMMARY.txt   - Краткая сводка (7 KB)
  
  test_schedule_32groups.xlsx - Тестовый Excel (16 KB, 32 группы)
  test_output.json           - Пример результата (265 KB)




  $ python excel_to_schedule.py расписание.xlsx
  ✅ Conversion complete! Groups: 32, Total lessons: 1351

  $ python excel_to_schedule.py расписание.xlsx output.json

  $ python create_test_excel.py
  ✅ Created test Excel file: test_schedule_32groups.xlsx




  ✅ Первая строка: названия групп (со 2-й колонки)
  ✅ Первая колонка: время или дни недели
  ✅ Ячейки: предмет\nпреподаватель\nаудитория

  ┌──────────────┬──────────┬──────────┐
  │ Время        │ ИС1-11   │ ИС1-12   │
  ├──────────────┼──────────┼──────────┤
  │ Понедельник (Числитель)            │
  ├──────────────┼──────────┼──────────┤
  │ 08:30-10:00  │ Матем.   │ Физика   │
  │              │ Иванов   │ Петров   │
  │              │ 201      │ 305      │
  └──────────────┴──────────┴──────────┘



 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ

  ✅ Конвертация Excel → JSON
  ✅ Загрузка в ScheduleManager
  ✅ Получение расписания
  ✅ Расписание на неделю
  ✅ Нормализация групп
  ✅ Форматирование
  ✅ Числитель/Знаменатель

  • Конвертация 32 групп: < 1 сек
  • Память: ~10 MB
  • Точность: 100%




  • EXCEL_CONVERTER.md - полное руководство
  • COMPATIBILITY_TEST_REPORT.md - детальный отчет
  • README.md - основная документация системы

  python excel_to_schedule.py --help




1. Делайте бэкап перед обновлением:
   cp schedule.json schedule_backup.json

2. Проверяйте результат после конвертации:
   python -c "from core import ScheduleManager; sm = ScheduleManager(); print(len(sm.get_all_groups()), 'groups')"

3. Используйте явные названия для числителя/знаменателя:
   "Понедельник (Числитель)"
   "Понедельник (Знаменатель)"

4. Проверяйте формат времени:
   "08:30-10:00" (правильно)
   "8:30 - 10:00" (тоже работает)



