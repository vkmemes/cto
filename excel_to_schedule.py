#!/usr/bin/env python3
"""
Excel to schedule.json converter - OIT 2nd Semester Edition
Converts Excel schedule from STTEC format to JSON format for STTEC Schedule system.

Excel format (oit_2sem.xlsx):
- Multiple sheets (one per course/specialty)
- Multiple groups per sheet
- Row structure: [Pair#] [Subject] ... [Teacher] ... [Room]
- No numerator/denominator separation

Optimized for 8GB RAM - processes file efficiently.
"""

import json
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import openpyxl
except ImportError:
    print("Error: openpyxl not installed. Run: pip install openpyxl")
    sys.exit(1)


def clean_text(text) -> str:
    """Clean and normalize text."""
    if text is None:
        return ""
    return str(text).strip()


def parse_group_header(cell_text: str) -> List[str]:
    """
    Parse group header into list of groups.
    If header contains '/', treat it as a single combined group name.
    """
    text = clean_text(cell_text)
    if not text:
        return []

    if '/' in text or '\\' in text:
        groups = [text]
    else:
        groups = re.split(r'[,;|]+', text)

    groups = [g.strip() for g in groups if g.strip()]

    normalized = []
    for group in groups:
        group = re.sub(r'\s+', ' ', group)
        group = re.sub(r'([А-ЯA-Z]+)\s*(\d)', r'\1\2', group)
        normalized.append(group)

    return normalized


def is_day_name(cell_text: str) -> Optional[str]:
    """
    Check if text is a day name and return normalized day name.
    Returns None if not a day.
    """
    text = clean_text(cell_text).lower()
    if not text:
        return None
    
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
        'вс': 'sunday',
    }
    
    for rus, eng in day_names.items():
        if rus in text:
            return eng
    
    return None


def is_group_header(cell_text: str) -> bool:
    """Check if cell contains a group header pattern like 'ИС1-11/ИС1-12'."""
    text = clean_text(cell_text)
    # Pattern: Cyrillic letters + digit + hyphen + digits
    # May contain / for multiple groups
    pattern = r'[А-ЯA-Z]+\d+[-–]\d+.*'
    return bool(re.search(pattern, text))


def is_pair_number(cell_text: str) -> Optional[int]:
    """Check if cell contains a pair number (1-8)."""
    text = clean_text(cell_text)
    if text.isdigit():
        num = int(text)
        if 1 <= num <= 8:
            return num
    return None


def parse_time_for_pair(pair_num: int) -> str:
    """Get standard time for pair number."""
    # Standard schedule times
    times = {
        1: "08:30-10:00",
        2: "10:10-11:40",
        3: "12:00-13:30",
        4: "13:40-15:10",
        5: "15:20-16:50",
        6: "17:00-18:30",
        7: "18:40-20:10",
        8: "20:15-21:45",
    }
    return times.get(pair_num, f"{pair_num} пара")


def split_multi_value(text: str) -> List[str]:
    """Split text by newlines into multiple values."""
    if not text:
        return [""]
    parts = text.split('\n')
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [""]


def parse_lesson(subject: str, teacher: str, room: str, pair_num: int) -> Optional[Dict[str, Any]]:
    """
    Parse lesson data into structured format.
    Handles multiple teachers/rooms separated by newlines.
    """
    subject = clean_text(subject)
    if not subject:
        return None
    
    teacher = clean_text(teacher)
    room = clean_text(room)
    
    # Handle case when subject has multiple lines (subgroup lessons)
    subjects = split_multi_value(subject)
    teachers = split_multi_value(teacher)
    rooms = split_multi_value(room)
    
    # If we have multiple subjects on same pair, create combined entry
    if len(subjects) > 1:
        # Multiple lessons at same time (subgroups)
        return {
            "time": parse_time_for_pair(pair_num),
            "subject": subject,
            "teacher": teacher,
            "room": room,
            "subgroups": True
        }
    
    return {
        "time": parse_time_for_pair(pair_num),
        "subject": subjects[0],
        "teacher": teachers[0] if teachers else "",
        "room": rooms[0] if rooms else "",
        "subgroups": False
    }


def init_schedule_structure() -> Dict[str, Any]:
    """Initialize empty schedule structure for a group."""
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    return {
        "numerator": {day: [] for day in days},
        "denominator": {day: [] for day in days}
    }


def parse_sheet(sheet) -> Dict[str, Dict[str, Any]]:
    """
    Parse a single sheet and return schedule for all groups on that sheet.
    
    Structure:
    - Group header row (e.g., "ИС1-11/ИС1-12")
    - Day header (e.g., "Понедельник")
    - Lessons with pair number, subject, teacher, room
    """
    schedules = {}  # group_name -> schedule
    current_groups = []
    current_day = "monday"
    
    print(f"  Parsing sheet: {sheet.title} ({sheet.max_row} rows)")
    
    for row_idx, row in enumerate(sheet.iter_rows(min_row=1, max_row=sheet.max_row), start=1):
        # Get key cell values
        col1 = clean_text(row[0].value)  # Pair number or day or group header
        col2 = clean_text(row[1].value) if len(row) > 1 else ""  # Subject
        col6 = clean_text(row[5].value) if len(row) > 5 else ""  # Teacher
        col9 = clean_text(row[8].value) if len(row) > 8 else ""  # Room
        
        # Check for group header
        if is_group_header(col1) and not is_day_name(col1) and not is_pair_number(col1):
            groups = parse_group_header(col1)
            if groups:
                current_groups = groups
                for group in groups:
                    if group not in schedules:
                        schedules[group] = init_schedule_structure()
                        print(f"    Found group: {group}")
            continue
        
        # Check for day name
        day = is_day_name(col1)
        if day:
            current_day = day
            continue
        
        # Check for pair number and parse lesson
        pair_num = is_pair_number(col1)
        if pair_num and col2 and current_groups:
            lesson = parse_lesson(col2, col6, col9, pair_num)
            if lesson:
                # Add to all current groups
                for group in current_groups:
                    # Add to both numerator and denominator (no separation in this format)
                    if lesson not in schedules[group]["numerator"][current_day]:
                        schedules[group]["numerator"][current_day].append(lesson)
                    if lesson not in schedules[group]["denominator"][current_day]:
                        schedules[group]["denominator"][current_day].append(lesson)
    
    return schedules


def parse_excel_file(excel_path: Path) -> Dict[str, Any]:
    """Parse a single Excel file into schedule data."""
    print(f"Reading Excel file: {excel_path}")

    try:
        workbook = openpyxl.load_workbook(excel_path, data_only=True, read_only=False)
    except Exception as e:
        print(f"Error loading Excel file {excel_path}: {e}")
        return {}

    all_schedules: Dict[str, Any] = {}

    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        sheet_schedules = parse_sheet(sheet)

        for group, schedule in sheet_schedules.items():
            if group in all_schedules:
                print(f"    Warning: Group {group} appears in multiple sheets, merging...")
                for week in ['numerator', 'denominator']:
                    for day, lessons in schedule[week].items():
                        existing = all_schedules[group][week][day]
                        for lesson in lessons:
                            if lesson not in existing:
                                existing.append(lesson)
            else:
                all_schedules[group] = schedule

    workbook.close()
    return all_schedules


def collect_excel_files(source_path: Path) -> List[Path]:
    """Collect Excel files from a file or directory."""
    if source_path.is_file():
        return [source_path]

    excel_files: List[Path] = []
    for extension in ("*.xlsx", "*.xlsm", "*.xls"):
        excel_files.extend(sorted(source_path.glob(extension)))

    return excel_files


def convert_excel_to_json(excel_path: str, output_path: str = 'schedule.json') -> bool:
    """
    Convert Excel file or directory of Excel files to schedule.json.

    Args:
        excel_path: Path to Excel file or directory with Excel files
        output_path: Path to output JSON file
    """
    source_path = Path(excel_path)
    excel_files = collect_excel_files(source_path)

    if not excel_files:
        print(f"Error: No Excel files found in {excel_path}")
        return False

    all_schedules: Dict[str, Any] = {}

    for file_path in excel_files:
        file_schedules = parse_excel_file(file_path)
        for group, schedule in file_schedules.items():
            if group in all_schedules:
                print(f"    Warning: Group {group} appears in multiple files, merging...")
                for week in ['numerator', 'denominator']:
                    for day, lessons in schedule[week].items():
                        existing = all_schedules[group][week][day]
                        for lesson in lessons:
                            if lesson not in existing:
                                existing.append(lesson)
            else:
                all_schedules[group] = schedule

    if not all_schedules:
        print("Error: No schedule data parsed")
        return False

    output = {"groups": all_schedules}

    print(f"\nSaving to {output_path}...")
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving JSON: {e}")
        return False

    total_groups = len(all_schedules)
    total_lessons = 0
    for group_data in all_schedules.values():
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
        print("Usage: python excel_to_schedule.py <excel_file_or_directory> [output.json]")
        print("\nExample:")
        print("  python excel_to_schedule.py oit_2sem.xlsx")
        print("  python excel_to_schedule.py schedules/ custom_schedule.json")
        print("\nSupports oit_2sem.xlsx format with multiple sheets and groups.")
        sys.exit(1)

    excel_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'schedule.json'

    if not Path(excel_path).exists():
        print(f"Error: Path not found: {excel_path}")
        sys.exit(1)

    success = convert_excel_to_json(excel_path, output_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
