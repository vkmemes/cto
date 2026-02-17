import asyncio
import json
import re
import httpx
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from bs4 import BeautifulSoup

STOP_WORDS_CANCEL = ["снято", "отменено", "нет пары"]

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

class Lesson(BaseModel):
    pair_number: int = 0
    time: str
    subject: str
    teacher: str
    room: str
    is_replaced: bool = False
    is_canceled: bool = False
    color_class: str = "default"

class DaySchedule(BaseModel):
    date_str: str
    lessons: List[Lesson]
    is_weekend: bool = False

class ScheduleManager:
    def __init__(self, schedule_json_path: str = "schedule.json", replacement_url: Optional[str] = None):
        self.schedule_json_path = schedule_json_path
        self.replacement_url = replacement_url or "https://example.com/replacements.html"
        self.base_schedule: Dict[str, Any] = {}
        self.group_lookup: Dict[str, str] = {}
        self.groups: List[str] = []
        self.replacements_cache: Dict[str, Any] = {}
        self.replacements_index: Dict[str, Any] = {}
        self.replacements_cache_time: Optional[datetime] = None
        self.cache_ttl_seconds = 300
        self._replacement_lock = asyncio.Lock()
        self._http_client = httpx.AsyncClient(timeout=10.0, verify=False)
        
        self.load_base_schedule()
    
    async def close(self):
        await self._http_client.aclose()
    
    def load_base_schedule(self):
        try:
            with open(self.schedule_json_path, "r", encoding="utf-8") as f:
                self.base_schedule = json.load(f)
        except FileNotFoundError:
            self.base_schedule = {"groups": {}}
        self._build_group_lookup()
    
    def _build_group_lookup(self):
        groups = self.base_schedule.get("groups", {})
        self.group_lookup = {}
        self.groups = list(groups.keys())
        for key in groups.keys():
            normalized_key = self.normalize_group_name(key)
            self.group_lookup[normalized_key] = key

    def search_groups(self, partial_name: str, limit: int = 20) -> List[str]:
        """Search groups by partial name (case-insensitive substring match)."""
        if not partial_name or len(partial_name.strip()) == 0:
            return []

        normalized_partial = self.normalize_group_name(partial_name)
        matches = []

        # First pass: exact match after normalization
        for group in self.groups:
            normalized_group = self.normalize_group_name(group)
            if normalized_group == normalized_partial:
                matches.append(group)

        # Second pass: starts with the search term (normalized)
        for group in self.groups:
            if group in matches:
                continue
            normalized_group = self.normalize_group_name(group)
            if normalized_group.startswith(normalized_partial):
                matches.append(group)

        # Third pass: contains the search term (normalized)
        for group in self.groups:
            if group in matches:
                continue
            normalized_group = self.normalize_group_name(group)
            if normalized_partial in normalized_group:
                matches.append(group)

        # Fourth pass: original name contains partial (for non-normalized matching)
        lower_partial = partial_name.lower()
        for group in self.groups:
            if group in matches:
                continue
            if lower_partial in group.lower():
                matches.append(group)

        return matches[:limit]

    def suggest_groups(self, partial_name: str, limit: int = 10) -> List[str]:
        """Get group suggestions for autocomplete."""
        return self.search_groups(partial_name, limit)
    
    def get_week_parity(self, target_date: Optional[date] = None) -> str:
        if target_date is None:
            target_date = date.today()
        week_num = target_date.isocalendar()[1]
        return "numerator" if week_num % 2 == 1 else "denominator"
    
    def normalize_group_name(self, group_name: str) -> str:
        return re.sub(r"[\s\-]", "", group_name).upper()
    
    def find_group_key(self, user_group: str) -> Optional[str]:
        return self.group_lookup.get(self.normalize_group_name(user_group))
    
    async def fetch_replacements(self) -> Dict[str, Any]:
        if (
            self.replacements_cache
            and self.replacements_cache_time
            and (datetime.now() - self.replacements_cache_time).total_seconds() < self.cache_ttl_seconds
        ):
            return self.replacements_cache

        async with self._replacement_lock:
            if (
                self.replacements_cache
                and self.replacements_cache_time
                and (datetime.now() - self.replacements_cache_time).total_seconds() < self.cache_ttl_seconds
            ):
                return self.replacements_cache
            try:
                response = await self._http_client.get(self.replacement_url)
                response.raise_for_status()
                html = response.text

                replacements = self.parse_replacements_html(html)
                self.replacements_cache = replacements
                self.replacements_index = self._build_replacements_index(replacements)
                self.replacements_cache_time = datetime.now()
                print(f"Successfully fetched and parsed {len(replacements)} group replacements")
                return replacements
            except httpx.HTTPError as e:
                print(f"[ScheduleManager] HTTP error fetching replacements: {e}")
                return {}
            except Exception as e:
                print(f"[ScheduleManager] Error fetching replacements: {e}")
                return {}
    
    def _build_replacements_index(self, replacements: Dict[str, Any]) -> Dict[str, Any]:
        index: Dict[str, Any] = {}
        for group_name, repl_info in replacements.items():
            index[self.normalize_group_name(group_name)] = repl_info
        return index
    
    def parse_replacements_html(self, html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        replacements = {}

        date_elem = soup.find("div", class_="replacement-date")
        if date_elem:
            date_str = date_elem.get_text(strip=True)
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")

        groups_divs = soup.find_all("div", class_="group-schedule")

        for group_div in groups_divs:
            group_header = group_div.find("h3")
            if not group_header:
                continue

            group_name = group_header.get_text(strip=True)
            lessons_data = []

            lesson_rows = group_div.find_all("div", class_="lesson-row")
            for row in lesson_rows:
                time_elem = row.find("span", class_="time")
                subject_elem = row.find("span", class_="subject")
                teacher_elem = row.find("span", class_="teacher")
                room_elem = row.find("span", class_="room")

                time = time_elem.get_text(strip=True) if time_elem else ""
                subject = subject_elem.get_text(strip=True) if subject_elem else ""
                teacher = teacher_elem.get_text(strip=True) if teacher_elem else ""
                room = room_elem.get_text(strip=True) if room_elem else ""

                # Determine pair number from time
                pair_number = get_pair_number_from_time(time)
                if pair_number == 0:
                    # Fallback to sequential numbering if time parsing fails
                    pair_number = len(lessons_data) + 1

                is_canceled = self.is_cancellation(subject, teacher, room)
                color_class = "red" if is_canceled else "yellow"

                lessons_data.append({
                    "pair_number": pair_number,
                    "time": time,
                    "subject": subject,
                    "teacher": teacher,
                    "room": room,
                    "is_replaced": True,
                    "is_canceled": is_canceled,
                    "color_class": color_class
                })

            replacements[group_name] = {
                "date": date_str,
                "lessons": lessons_data
            }

        return replacements
    
    def is_cancellation(self, subject: str, teacher: str, room: str) -> bool:
        full_text = f"{subject} {teacher} {room}".lower()
        
        if any(word in full_text for word in STOP_WORDS_CANCEL):
            if "п/гр" in full_text or "подгр" in full_text:
                return False
            
            if len(subject) < 15 and teacher == "" and room == "":
                return True
        
        return False
    
    async def get_schedule_for_date(self, group_name: str, target_date: date) -> Optional[DaySchedule]:
        group_key = self.find_group_key(group_name)
        if not group_key:
            return None

        replacements = await self.fetch_replacements()

        date_str = target_date.strftime("%d.%m.%Y")
        normalized_group = self.normalize_group_name(group_name)
        replacement_data = self.replacements_index.get(normalized_group)

        # Get base schedule first
        weekday = target_date.weekday()
        if weekday >= 5:
            return DaySchedule(date_str=date_str, lessons=[], is_weekend=True)

        # Russian day names match the schedule.json structure
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        day_name = weekday_names[weekday]

        week_parity = self.get_week_parity(target_date)

        group_data = self.base_schedule["groups"].get(group_key, {})
        # Schedule data is stored directly under day name (Russian), not under week_parity
        day_schedule = group_data.get(day_name, [])

        # Filter lessons based on type (Еженедельно=every week, Четная=even, Нечетная=odd)
        lessons = []
        for idx, lesson_dict in enumerate(day_schedule):
            lesson_type = lesson_dict.get("type", "Еженедельно")
            
            # Filter by week type
            if lesson_type == "Четная" and week_parity != "denominator":
                continue  # Skip - only for even weeks
            if lesson_type == "Нечетная" and week_parity != "numerator":
                continue  # Skip - only for odd weeks
            
            time_str = lesson_dict.get("time", "")
            pair_number = lesson_dict.get("pair_num", 0)
            if pair_number == 0:
                # Fallback to index-based numbering if parsing fails
                pair_number = idx + 1

            lessons.append(Lesson(
                pair_number=pair_number,
                time=time_str,
                subject=lesson_dict.get("lesson", ""),
                teacher=lesson_dict.get("teacher", ""),
                room=lesson_dict.get("classroom", ""),
                is_replaced=False,
                is_canceled=False,
                color_class="default"
            ))

        # Apply replacements if available for this date
        if replacement_data and replacement_data.get("date") == date_str:
            replacements_lessons = replacement_data.get("lessons", [])
            # Create a mapping of pair_number to replacement lesson
            replacements_map = {r["pair_number"]: r for r in replacements_lessons}

            # Apply replacements to base schedule
            for i, lesson in enumerate(lessons):
                replacement = replacements_map.get(lesson.pair_number)
                if replacement:
                    lessons[i] = Lesson(**replacement)
                # Otherwise keep the base schedule lesson

            # Check if there are any replacements that add new lessons
            max_pair_number = max((l.pair_number for l in lessons), default=0)
            for replacement in replacements_lessons:
                if replacement["pair_number"] > max_pair_number:
                    # This is a new lesson added by replacement
                    lessons.append(Lesson(**replacement))

            # Sort by pair number
            lessons.sort(key=lambda x: x.pair_number)

        return DaySchedule(date_str=date_str, lessons=lessons, is_weekend=False)
    
    async def get_week_schedule(self, group_name: str, start_date: Optional[date] = None) -> List[DaySchedule]:
        if start_date is None:
            start_date = date.today()
        
        start_of_week = start_date - timedelta(days=start_date.weekday())
        
        week_schedule = []
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            day_schedule = await self.get_schedule_for_date(group_name, day)
            if day_schedule:
                week_schedule.append(day_schedule)
        
        return week_schedule
    
    def get_pair_emoji(self, pair_number: int) -> str:
        """Возвращает эмодзи для номера пары."""
        emojis = {
            0: "0️⃣", 1: "1️⃣", 2: "2️⃣", 3: "3️⃣",
            4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣"
        }
        return emojis.get(pair_number, str(pair_number))

    def format_schedule_text(self, day_schedule: DaySchedule, target_date: date) -> str:
        # Получаем название дня недели и четность
        day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        weekday_idx = target_date.weekday()
        day_name = day_names[weekday_idx]
        week_parity = self.get_week_parity(target_date)
        parity_ru = "числитель" if week_parity == "numerator" else "знаменатель"

        header = f"📅 {day_name} ({day_schedule.date_str} | {parity_ru})"

        if day_schedule.is_weekend:
            return f"{header}\n🏖 Выходной день"

        if not day_schedule.lessons:
            return f"{header}\n❌ Нет пар"

        lines = [header, ""]

        for lesson in day_schedule.lessons:
            if lesson.is_canceled:
                # Отмена: 🚫 0️⃣ Литература (ОТМЕНА)
                pair_emoji = self.get_pair_emoji(lesson.pair_number)
                lines.append(f"🚫 {pair_emoji} {lesson.subject} (ОТМЕНА)")
            elif lesson.is_replaced:
                # Замена: 🔄 1️⃣ Информ. Комиссарова ОВ - А409А407
                pair_emoji = self.get_pair_emoji(lesson.pair_number)
                room_info = f" - {lesson.room}" if lesson.room else ""
                teacher_info = f" {lesson.teacher}" if lesson.teacher else ""
                lines.append(f"🔄 {pair_emoji} {lesson.subject}{teacher_info}{room_info}")
            else:
                # Обычная пара: 1️⃣ Математика Петров ИИ - 305
                pair_emoji = self.get_pair_emoji(lesson.pair_number)
                room_info = f" - {lesson.room}" if lesson.room else ""
                teacher_info = f" {lesson.teacher}" if lesson.teacher else ""
                lines.append(f"{pair_emoji} {lesson.subject}{teacher_info}{room_info}")

        return "\n".join(lines)
    
    def get_all_groups(self) -> List[str]:
        return list(self.groups)
