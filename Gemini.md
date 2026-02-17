Это **Финальная сборка проекта ЯГК (v3.0 Ultimate)**.

Здесь собран весь функционал, который мы обсуждали:
1.  **Расписание:** Слияние базы (JSON) и замен (HTML).
2.  **Умный Бот:** Проверка подписки, авторассылка замен, авто-назначение дежурных, кнопка "Я заболел".
3.  **Веб-интерфейс (PWA):** Просмотр расписания, навигация по датам, сохранение группы.
4.  **CRM Старосты (Mini Apps):** Панель управления, назначение дежурных, запись ДЗ по предметам.
5.  **Архитектура:** Оптимизировано для 512 МБ RAM (SQLite + Async).

---

## 📂 Структура проекта
Папка: `/root/ygk_project/`

```text
ygk_project/
├── bot_main.py             # Телеграм бот (Polling, Jobs)
├── web_main.py             # Веб-сервер (Сайт + API)
├── core.py                 # Ядро (Парсинг, Логика расписания)
├── database.py             # База данных (ORM, Модели)
├── schedule.json           # Файл расписания (база)
├── requirements.txt        # Библиотеки
├── migrate.py              # Скрипт создания/обновления БД
└── templates/              # HTML Шаблоны
    ├── group_list_template.html
    ├── schedule_view_template.html
    ├── replacements_view_template.html
    ├── homework_form.html
    └── headman_panel.html
```

---

## 1. `core.py` (Мозг)

```python
from __future__ import annotations
import json
import re
import logging
import datetime
import httpx
from bs4 import BeautifulSoup
from typing import List, Optional, Dict, Tuple
from pydantic import BaseModel, Field
from enum import Enum

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger("Core")

SCHEDULE_FILE = 'schedule.json'
REPLACEMENTS_URLS = [
    "https://menu.ygk.yar.ru/timetable/rasp_first.html",
    "https://menu.ygk.yar.ru/timetable/rasp_second.html"
]
STOP_WORDS_CANCEL = ["отмена", "нет пары", "самоподготовка", "праздник", "❌", "снято"]

class LessonType(str, Enum):
    REGULAR = "regular"
    REPLACEMENT = "replacement"
    CANCELLATION = "cancellation"
    ADDED = "added"

class Lesson(BaseModel):
    pair_num: int
    subject: str
    teacher: Optional[str] = None
    room: Optional[str] = None
    raw_text: str = ""
    type: LessonType = LessonType.REGULAR
    original_subject: Optional[str] = None 
    is_subgroup: bool = False 

class DaySchedule(BaseModel):
    date: datetime.date
    week_type: str
    lessons: List[Lesson] = []
    has_replacements: bool = False
    last_updated: datetime.datetime = Field(default_factory=datetime.datetime.now)

class ScheduleManager:
    def __init__(self):
        self._base_schedule: Dict[str, Dict] = {}
        self._replacements_cache: List[dict] = []
        self._cache_date: Optional[datetime.date] = None
        self._last_fetch: datetime.datetime = datetime.datetime.min
        self.load_base_schedule()

    def load_base_schedule(self):
        try:
            with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
                self._base_schedule = json.load(f)
        except: self._base_schedule = {}

    def _normalize_name(self, name: str) -> str:
        return name.strip().lower().replace(" ", "").replace("-", "")

    def _parse_replacement_lesson(self, raw_text: str) -> Tuple[str, str]:
        if not raw_text: return "", ""
        clean_text = raw_text.replace('\xa0', ' ').replace('\t', ' ').strip()
        teacher_pattern = r'([A-ZА-ЯЁ][a-zа-яё]+(?:-[A-ZА-ЯЁ][a-zа-яё]+)?\s+[A-ZА-ЯЁ]\.\s?[A-ZА-ЯЁ]\.?)'
        teachers = re.findall(teacher_pattern, clean_text)
        if teachers:
            teacher_str = ", ".join(sorted(list(set(teachers))))
            subject = clean_text
            for t in teachers: subject = subject.replace(t, "")
            subject = re.sub(r'\s+', ' ', subject).strip(' .,;')
            return subject, teacher_str
        match_brackets = re.search(r'\(([^)]+)\)', clean_text)
        if match_brackets:
            content = match_brackets.group(1).strip()
            if len(content) > 2 and not any(w in content.lower() for w in ['каб','ауд','подгр']):
                return clean_text.replace(match_brackets.group(0), "").strip(), content
        return clean_text, "Не указан"

    def _parse_pair_nums(self, raw_num: str) -> List[int]:
        nums = set()
        clean_raw = re.sub(r'[,;&-]', ' ', raw_num)
        for part in clean_raw.split():
            if part.isdigit(): nums.add(int(part))
        return sorted(list(nums))

    def _extract_date(self, text: str) -> Optional[datetime.date]:
        months = {'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12}
        match = re.search(r'(\d{1,2})\s+([а-я]+)(?:\s+(\d{4}))?', text.lower())
        if match:
            day, month_str, year_str = match.groups()
            month = months.get(month_str)
            if month:
                year = int(year_str) if year_str else datetime.date.today().year
                if datetime.date.today().month == 12 and month == 1: year += 1
                return datetime.date(year, month, int(day))
        return None

    async def update_replacements(self, force: bool = False):
        now = datetime.datetime.now()
        if not force and (now - self._last_fetch).total_seconds() < 300:
            return self._replacements_cache, False

        new_cache = []
        parsed_date = None
        is_changed = False

        async with httpx.AsyncClient() as client:
            for url in REPLACEMENTS_URLS:
                try:
                    resp = await client.get(url, timeout=10)
                    if resp.status_code != 200: continue
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    if not parsed_date:
                        for tag in soup.find_all(['div', 'b', 'strong', 'h1']):
                            if tag.text and 'изменения' in tag.text.lower():
                                d = self._extract_date(tag.text)
                                if d: parsed_date = d
                    table = soup.find('table')
                    if not table: continue
                    for row in table.find_all('tr'):
                        cols = row.find_all('td')
                        if len(cols) < 6: continue
                        
                        group_col = 1 if len(cols[0].text) < 3 else 0
                        raw_groups = cols[group_col].text.strip()
                        raw_pair = cols[group_col+1].text.strip()
                        subject_new = cols[group_col+3].text.strip()
                        room = cols[group_col+4].text.strip() if (group_col+4) < len(cols) else ""
                        
                        if not raw_groups or not raw_pair: continue
                        pair_nums = self._parse_pair_nums(raw_pair)
                        for p in pair_nums:
                            for g in raw_groups.split('/'):
                                new_cache.append({"groups": [g.strip()], "pair_num": p, "subject_new": subject_new, "room": room})
                except: pass

        if (self._cache_date != parsed_date) or (len(new_cache) != len(self._replacements_cache)):
            is_changed = True

        self._replacements_cache = new_cache
        self._cache_date = parsed_date or datetime.date.today()
        self._last_fetch = now
        return new_cache, is_changed

    def get_schedule(self, group_name: str, target_date: datetime.date) -> DaySchedule:
        is_numerator = target_date.isocalendar()[1] % 2 == 0
        week = "числитель" if is_numerator else "знаменатель"
        day_idx = target_date.weekday()
        days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        raw = self._base_schedule.get(group_name, {}).get(days_ru[day_idx], [])
        final = {}

        for item in raw:
            pt = item.get('type', 'Еженедельно')
            if (pt == 'Четная' and not is_numerator) or (pt == 'Нечетная' and is_numerator): continue
            s = item.get('lesson', '')
            t = item.get('teacher', '')
            p = int(item.get('pair_num', 0))
            final[p] = Lesson(pair_num=p, subject=s, teacher=t, room=item.get('classroom', ''), raw_text=f"{s} {t}", is_subgroup="подгр" in s.lower())

        has_rep = False
        if self._cache_date == target_date:
            target_parts = set(self._normalize_name(p) for p in group_name.split('/'))
            reps = []
            for r in self._replacements_cache:
                rep_parts = set(self._normalize_name(g) for g in r['groups'])
                if not target_parts.isdisjoint(rep_parts): reps.append(r)
            
            for r in reps:
                p = r['pair_num']
                txt = r['subject_new']
                is_cancel = any(w in txt.lower() for w in STOP_WORDS_CANCEL) and not (len(txt) > 15 or "п/гр" in txt.lower())
                s_new, t_new = self._parse_replacement_lesson(txt)
                l_type = LessonType.CANCELLATION if is_cancel else LessonType.REPLACEMENT
                
                if p in final:
                    final[p].type = l_type
                    final[p].original_subject = final[p].subject
                    if is_cancel: final[p].subject = "ОТМЕНА"; final[p].teacher = ""; final[p].room = ""
                    else: final[p].subject = s_new; final[p].teacher = t_new; final[p].room = r['room']
                    has_rep = True
                elif not is_cancel:
                    final[p] = Lesson(pair_num=p, subject=s_new, teacher=t_new, room=r['room'], type=LessonType.ADDED, original_subject="(Окно)")
                    has_rep = True

        return DaySchedule(date=target_date, week_type=week, lessons=sorted(final.values(), key=lambda x: x.pair_num), has_replacements=has_rep)

core = ScheduleManager()
```

---

## 2. `database.py` (Память)

```python
import logging
import datetime
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, DateTime, Date, func, select, BigInteger, update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DB")

DATABASE_URL = "sqlite+aiosqlite:///ygk.db"

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    group_name: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="student") 
    referral_source: Mapped[str] = mapped_column(String(50), default="organic")
    is_active: Mapped[bool] = mapped_column(default=True)
    sub_check_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_notify_date: Mapped[datetime.date] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class GroupSettings(Base):
    __tablename__ = "group_settings"
    group_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    hw_enabled: Mapped[bool] = mapped_column(default=False)
    autoset_enabled: Mapped[bool] = mapped_column(default=False)
    last_queue_index: Mapped[int] = mapped_column(default=0)
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

class GroupPin(Base):
    __tablename__ = "group_pins"
    group_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    pin_code: Mapped[str] = mapped_column(String(50))

class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_name: Mapped[str] = mapped_column(String(50), index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    tg_username: Mapped[Optional[str]] = mapped_column(String(100)) 
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    queue_order: Mapped[int] = mapped_column(default=0)
    is_sick: Mapped[bool] = mapped_column(default=False)

class Homework(Base):
    __tablename__ = "homeworks"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_name: Mapped[str] = mapped_column(String(50), index=True)
    target_date: Mapped[datetime.date] = mapped_column()
    subject: Mapped[str] = mapped_column(String(200), nullable=True)
    text: Mapped[str] = mapped_column(String(1000))
    created_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Database:
    def __init__(self):
        self.engine = create_async_engine(DATABASE_URL, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def register_user(self, telegram_id: int, username: str = None, full_name: str = None, source: str = "organic"):
        async with self.session_factory() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if user:
                user.is_active = True
                if username: user.username = username
                if full_name: user.full_name = full_name
                if username:
                    clean = username.replace("@", "")
                    st = (await session.execute(select(Student).where(Student.tg_username == clean))).scalar_one_or_none()
                    if st: st.telegram_id = telegram_id
            else:
                session.add(User(telegram_id=telegram_id, username=username, full_name=full_name, referral_source=source))
            await session.commit()

    async def set_group(self, telegram_id: int, group: str):
        async with self.session_factory() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if user: user.group_name = group
            else: session.add(User(telegram_id=telegram_id, group_name=group))
            await session.commit()

    async def mark_inactive(self, telegram_id: int):
        async with self.session_factory() as session:
            await session.execute(update(User).where(User.telegram_id == telegram_id).values(is_active=False))
            await session.commit()

    async def is_subscription_cached(self, telegram_id: int, ttl_minutes: int = 10) -> bool:
        async with self.session_factory() as session:
            stmt = select(User.sub_check_time).where(User.telegram_id == telegram_id)
            last = (await session.execute(stmt)).scalar_one_or_none()
            if not last: return False
            now = datetime.datetime.now(datetime.timezone.utc) if last.tzinfo else datetime.datetime.now()
            return (now - last).total_seconds() < (ttl_minutes * 60)

    async def update_sub_check(self, telegram_id: int):
        async with self.session_factory() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if user: user.sub_check_time = func.now()
            await session.commit()

    async def get_user_role(self, telegram_id: int) -> str:
        async with self.session_factory() as session:
            res = await session.execute(select(User.role).where(User.telegram_id == telegram_id))
            return res.scalar_one_or_none() or "student"

    async def set_user_role(self, telegram_id: int, role: str):
        async with self.session_factory() as session:
            await session.execute(update(User).where(User.telegram_id == telegram_id).values(role=role))
            await session.commit()

    async def add_homework(self, group_name: str, target_date: datetime.date, subject: str, text: str, author_id: int, mode: str = "append"):
        async with self.session_factory() as session:
            stmt = select(Homework).where(Homework.group_name == group_name, Homework.target_date == target_date, Homework.subject == subject)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                if mode == "overwrite": existing.text = text
                else: existing.text = existing.text + "\n\n" + text
                existing.created_by = author_id
            else:
                session.add(Homework(group_name=group_name, target_date=target_date, subject=subject, text=text, created_by=author_id))
            await session.commit()

    async def get_homework(self, group_name: str, target_date: datetime.date) -> Dict[str, str]:
        async with self.session_factory() as session:
            stmt = select(Homework).where(Homework.group_name == group_name, Homework.target_date == target_date)
            results = (await session.execute(stmt)).scalars().all()
            hw_map = {}
            for hw in results:
                key = hw.subject if hw.subject else "Общее"
                hw_map[key] = hw.text
            return hw_map

    async def check_homework_exists(self, group_name: str, target_date: datetime.date) -> bool:
        async with self.session_factory() as session:
            stmt = select(func.count(Homework.id)).where(Homework.group_name == group_name, Homework.target_date == target_date)
            return (await session.scalar(stmt)) > 0

    async def set_group_pin(self, group_name: str, pin: str):
        async with self.session_factory() as session:
            stmt = select(GroupPin).where(GroupPin.group_name == group_name)
            obj = (await session.execute(stmt)).scalar_one_or_none()
            if obj: obj.pin_code = pin
            else: session.add(GroupPin(group_name=group_name, pin_code=pin))
            await session.commit()

    async def get_group_pin(self, group_name: str) -> Optional[str]:
        async with self.session_factory() as session:
            return await session.scalar(select(GroupPin.pin_code).where(GroupPin.group_name == group_name))

    async def check_pin(self, group_name: str, input_pin: str) -> bool:
        real = await self.get_group_pin(group_name)
        return str(real).strip() == str(input_pin).strip() if real else False

    async def get_headman_id(self, group_name: str) -> Optional[int]:
        async with self.session_factory() as session:
            stmt = select(User.telegram_id).where(User.group_name == group_name, User.role == 'headman')
            return await session.scalar(stmt)

    async def add_or_update_student(self, group: str, name: str, username: str, order: int):
        async with self.session_factory() as session:
            clean = username.replace("@", "").strip() if username else None
            stmt = select(Student).where(Student.group_name == group, Student.full_name == name)
            student = (await session.execute(stmt)).scalar_one_or_none()
            tg_id = None
            if clean:
                u_stmt = select(User.telegram_id).where(User.username == clean)
                tg_id = (await session.execute(u_stmt)).scalar_one_or_none()
            if student:
                student.tg_username = clean; student.queue_order = order; 
                if tg_id: student.telegram_id = tg_id
            else:
                session.add(Student(group_name=group, full_name=name, tg_username=clean, queue_order=order, telegram_id=tg_id))
            await session.commit()

    async def register_s