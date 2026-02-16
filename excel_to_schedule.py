#!/usr/bin/env python3
"""
Excel to schedule.json converter
Converts Excel schedule to JSON format for STTEC Schedule system.

Expected Excel format:
- First row: Headers (Group names)
- First column: Time slots
- Cells: Subject/Teacher/Room (separated by newlines or commas)
"""

import json
import sys
import re
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("Error: openpyxl not installed. Run: pip install openpyxl")
    sys.exit(1)


def clean_text(text):
    """Clean and normalize text."""
    if text is None:
        return ""
    return str(text).strip()


def parse_lesson_cell(cell_text):
    """
    Parse lesson cell into subject, teacher, room.
    
    Expected formats:
    - "Subject\nTeacher\nRoom"
    - "Subject, Teacher, Room"
    - "Subject"
    """
    if not cell_text or cell_text == "":
        return None
    
    # Split by newline or comma
    parts = []
    if '\n' in cell_text:
        parts = [p.strip() for p in cell_text.split('\n') if p.strip()]
    elif ',' in cell_text:
        parts = [p.strip() for p in cell_text.split(',') if p.strip()]
    else:
        parts = [cell_text.strip()]
    
    # Parse parts
    subject = parts[0] if len(parts) > 0 else ""
    teacher = parts[1] if len(parts) > 1 else ""
    room = parts[2] if len(parts) > 2 else ""
    
    if not subject:
        return None
    
    return {
        "subject": subject,
        "teacher": teacher,
        "room": room
    }


def parse_time_slot(time_text):
    """
    Parse time slot from various formats.
    
    Examples:
    - "08:30-10:00"
    - "1 пара (08:30-10:00)"
    - "08:30 - 10:00"
    """
    time_text = clean_text(time_text)
    
    # Extract time pattern like "08:30-10:00"
    match = re.search(r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})', time_text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    
    # If no pattern found, return as is
    return time_text if time_text else "00:00-00:00"


def detect_layout(sheet):
    """
    Detect Excel layout type.
    
    Returns:
    - 'horizontal': Groups in columns, days/times in rows
    - 'vertical': Groups in rows, days/times in columns
    """
    # Check first row for group names
    first_row = [clean_text(cell.value) for cell in sheet[1]]
    
    # If first row contains typical group patterns, it's horizontal
    group_patterns = [r'[А-Я]{2,4}[-\d]+', r'группа', r'курс']
    for cell in first_row[1:]:  # Skip first column
        if any(re.search(pattern, cell, re.IGNORECASE) for pattern in group_patterns):
            return 'horizontal'
    
    return 'horizontal'  # Default to horizontal


def parse_horizontal_layout(sheet):
    """
    Parse horizontal layout: groups in columns, days/times in rows.
    
    Expected structure:
    Row 1: [Time] [Group1] [Group2] [Group3] ...
    Row 2: [08:30-10:00] [Lesson] [Lesson] [Lesson] ...
    ...
    
    Or with day headers:
    Row 1: [Monday]
    Row 2: [Time] [Group1] [Group2] ...
    Row 3: [08:30-10:00] [Lesson] [Lesson] ...
    """
    schedule = {}
    
    # Find header row (with group names)
    header_row_idx = None
    group_columns = {}
    
    for row_idx, row in enumerate(sheet.iter_rows(min_row=1, max_row=5), start=1):
        cells = [clean_text(cell.value) for cell in row]
        
        # Check if this row has group names
        group_count = 0
        for col_idx, cell in enumerate(cells[1:], start=2):  # Skip first column
            if re.search(r'[А-Я]{2,4}[-\d/]+', cell):
                group_count += 1
                group_columns[col_idx] = cell
        
        if group_count >= 2:  # At least 2 groups found
            header_row_idx = row_idx
            break
    
    if not header_row_idx:
        print("Error: Could not find header row with group names")
        return {}
    
    print(f"Found {len(group_columns)} groups in row {header_row_idx}")
    print(f"Groups: {', '.join(group_columns.values())}")
    
    # Initialize schedule structure
    for group_name in group_columns.values():
        schedule[group_name] = {
            "numerator": {
                "monday": [],
                "tuesday": [],
                "wednesday": [],
                "thursday": [],
                "friday": [],
                "saturday": [],
                "sunday": []
            },
            "denominator": {
                "monday": [],
                "tuesday": [],
                "wednesday": [],
                "thursday": [],
                "friday": [],
                "saturday": [],
                "sunday": []
            }
        }
    
    # Parse lessons
    current_day = "monday"
    current_week = "numerator"
    
    day_names = {
        'понедельник': 'monday',
        'вторник': 'tuesday',
        'среда': 'wednesday',
        'четверг': 'thursday',
        'пятница': 'friday',
        'суббота': 'saturday',
        'воскресенье': 'sunday',
        'пн': 'monday',
        'вт': 'tuesday',
        'ср': 'wednesday',
        'чт': 'thursday',
        'пт': 'friday',
        'сб': 'saturday',
        'вс': 'sunday'
    }
    
    week_names = {
        'числитель': 'numerator',
        'знаменатель': 'denominator',
        'чис': 'numerator',
        'знам': 'denominator'
    }
    
    for row in sheet.iter_rows(min_row=header_row_idx + 1):
        first_cell = clean_text(row[0].value).lower()
        
        # Check for day name
        for rus_day, eng_day in day_names.items():
            if rus_day in first_cell:
                current_day = eng_day
                print(f"Day: {current_day}")
                break
        
        # Check for week type
        for rus_week, eng_week in week_names.items():
            if rus_week in first_cell:
                current_week = eng_week
                print(f"Week: {current_week}")
                break
        
        # Check if this is a time slot row
        time_slot = parse_time_slot(first_cell)
        if ':' in time_slot and '-' in time_slot:
            # Parse lessons for each group
            for col_idx, group_name in group_columns.items():
                cell_value = clean_text(row[col_idx - 1].value)
                
                if cell_value:
                    lesson = parse_lesson_cell(cell_value)
                    if lesson:
                        lesson['time'] = time_slot
                        schedule[group_name][current_week][current_day].append(lesson)
    
    return schedule


def parse_vertical_layout(sheet):
    """
    Parse vertical layout: groups in rows, days/times in columns.
    (Alternative layout, less common)
    """
    # TODO: Implement if needed
    print("Vertical layout not yet implemented. Using horizontal parser.")
    return parse_horizontal_layout(sheet)


def convert_excel_to_json(excel_path, output_path='schedule.json'):
    """
    Convert Excel file to schedule.json.
    
    Args:
        excel_path: Path to Excel file
        output_path: Path to output JSON file
    """
    print(f"Reading Excel file: {excel_path}")
    
    try:
        workbook = openpyxl.load_workbook(excel_path, data_only=True)
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return False
    
    # Try first sheet
    sheet = workbook.active
    print(f"Processing sheet: {sheet.title}")
    print(f"Dimensions: {sheet.max_row} rows x {sheet.max_column} columns")
    
    # Detect layout
    layout = detect_layout(sheet)
    print(f"Detected layout: {layout}")
    
    # Parse based on layout
    if layout == 'horizontal':
        schedule = parse_horizontal_layout(sheet)
    else:
        schedule = parse_vertical_layout(sheet)
    
    if not schedule:
        print("Error: No schedule data parsed")
        return False
    
    # Wrap in groups object
    output = {"groups": schedule}
    
    # Save to JSON
    print(f"\nSaving to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # Print statistics
    total_groups = len(schedule)
    total_lessons = 0
    for group_name, group_data in schedule.items():
        for week in ['numerator', 'denominator']:
            for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']:
                total_lessons += len(group_data[week][day])
    
    print(f"\n✅ Conversion complete!")
    print(f"   Groups: {total_groups}")
    print(f"   Total lessons: {total_lessons}")
    print(f"   Output: {output_path}")
    
    return True


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python excel_to_schedule.py <excel_file> [output.json]")
        print("\nExample:")
        print("  python excel_to_schedule.py oit_2sem.xlsx")
        print("  python excel_to_schedule.py oit_2sem.xlsx custom_schedule.json")
        sys.exit(1)
    
    excel_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'schedule.json'
    
    if not Path(excel_path).exists():
        print(f"Error: File not found: {excel_path}")
        sys.exit(1)
    
    success = convert_excel_to_json(excel_path, output_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
