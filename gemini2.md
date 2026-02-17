Да, это **абсолютно полная и финальная версия** файлов `bot_main.py` и `web_main.py`, в которой исправлены ошибки с `NameError` (отсутствующие функции) и внедрена вся логика с PIN-кодами, предметами и уведомлениями.

Ниже я подготовил **"Пакет для переезда"**. Скопируй **Текст ниже** и отправь его первым сообщением в новом чате. Это мгновенно введет нового AI-агента в курс дела.

---

# 📦 Пакет для нового чата (Project Context)

**Проект:** ЯГК Schedule (ЯГК Расписание)
**Статус:** Level 3 (Production Ready)
**Инфраструктура:** Linux (Ubuntu), 512 MB RAM (строгое ограничение!), SWAP 2GB.
**Стек:** Python 3.8, Starlette (Web), python-telegram-bot v20+ (Bot), SQLAlchemy + aiosqlite (Async DB).

### 🛠 Архитектура и Правила (Не менять!)

1.  **База данных (`database.py`):**
    *   Используем **SQLite** (файл `ygk.db`) в асинхронном режиме.
    *   Таблицы: `users` (подписчики), `homeworks` (ДЗ с привязкой к дате и предмету), `students` (список группы), `group_settings` (настройки), `group_pins` (PIN-коды для входа на сайт).
    *   **Важно:** Не предлагать Docker или PostgreSQL (не хватит ОЗУ).

2.  **Парсинг (`core.py`):**
    *   **Гибридный метод:** Базовое расписание берется из статического `schedule.json`, замены парсятся с сайта колледжа (HTML).
    *   **Логика "Снято":** Если в замене написано "Снято" или "Отмена", но текст длинный (>15 символов) или есть "п/гр" — это считается **ЗАМЕНОЙ** (желтый цвет), а не отменой.
    *   **Поиск групп:** Реализован через пересечение множеств нормализованных имен (чтобы `СА1-11` совпадало с `СА1-11/12`).

3.  **Веб-интерфейс (Starlette + Jinja2):**
    *   Работает на порту 5000.
    *   **Mini Apps:** Панель старосты и Форма ДЗ.
    *   **Auth:** Используется **PIN-код** (хранится в БД `group_pins`), так как проверка подписи Telegram (initData) была отключена для упрощения.
    *   **ДЗ:** Привязывается к *предмету*. Есть режим "Перезаписать" и "Добавить".

4.  **Бот (`bot_main.py`):**
    *   **Middleware:** Блокирует доступ, если нет подписки на канал. В беседах (группах) не блокирует.
    *   **Уведомления:** Рассылка замен происходит 1 раз в день на пользователя (защита от спама).
    *   **CRM:** Староста назначает дежурных, дежурные получают уведомление. Кнопка "Я заболел" ищет замену автоматически.

---

### 💻 Актуальный код файлов

#### 1. `bot_main.py` (Финальный)
*Включает: Обертки команд, Jobs, Middleware, поиск группы, диалоги.*

```python
import logging
import asyncio
import datetime
import time 
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, TypeHandler, ApplicationHandlerStop, CallbackQueryHandler
from telegram.error import Forbidden, BadRequest

# Импортируем модули проекта
from core import core, LessonType
from database import db

# --- КОНФИГУРАЦИЯ ---
TOKEN = "8195041032:AAGvHDGKzOnLYCL-TksT63znzieji9cRvdk"
ADMIN_ID = 1045927105
REQUIRED_CHANNELS = ["@ygkschedule"]

# Настройка логгера
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

SELECTING_GROUP = 1
SETTING_NAME = 2 
MAIN_KB = ReplyKeyboardMarkup([["Сегодня", "Завтра", "Неделя"], ["Группа", "Настройки"]], resize_keyboard=True)

# =======================
#      MIDDLEWARES
# =======================

async def pre_process_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['start_time'] = time.monotonic()
    if update.effective_user:
        try:
            ct = update.effective_chat.type if update.effective_chat else "private"
            cnt = "text"
            if ct != "private" and not (update.message and update.message.text and update.message.text.startswith('/')): return
            if update.message and update.message.text and update.message.text.startswith('/'): cnt = "command"
            await db.log_message(user_id=update.effective_user.id, chat_type=ct, content_type=cnt)
        except: pass

async def check_subscription_status(user_id: int, bot) -> list:
    try:
        if await db.is_subscription_cached(user_id, ttl_minutes=10): return [] 
    except: pass 
    missing = []
    for channel in REQUIRED_CHANNELS:
        try:
            m = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if m.status in ['left', 'kicked']: missing.append(channel)
        except: pass
    if not missing:
        try: await db.update_sub_check(user_id)
        except: pass
    return missing

async def subscription_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if not user: return 
    if chat.type != "private": return
    if update.callback_query and update.callback_query.data == "check_sub": return
    if user.id == ADMIN_ID: return

    try: missing = await check_subscription_status(user.id, context.bot)
    except: return 

    if missing:
        btns = []
        for ch in missing:
            url = f"https://t.me/{ch.replace('@', '')}"
            btns.append([InlineKeyboardButton(f"👉 Подписаться", url=url)])
        btns.append([InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")])
        text = "🔒 **Доступ ограничен!**\nПодпишись на канал:"
        try:
            if update.callback_query: await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")
            elif update.message: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")
        except: pass
        raise ApplicationHandlerStop

async def sub_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    missing = await check_subscription_status(update.effective_user.id, context.bot)
    if not missing:
        await query.edit_message_text("✅ **Доступ открыт!**", parse_mode="Markdown")
        await start(update, context)
    else:
        url = f"https://t.me/{missing[0].replace('@', '')}"
        btns = [[InlineKeyboardButton(f"👉 Подписаться", url=url)], [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]]
        await query.edit_message_text("❌ Не подписались.", reply_markup=InlineKeyboardMarkup(btns))

async def post_process_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = context.user_data.get('start_time')
    if st:
        try: await db.log_latency((time.monotonic() - st) * 1000)
        except: pass

# =======================
#      LOGIC & UTILS
# =======================

async def get_user_group(user_id: int) -> str:
    async with db.session_factory() as session:
        from database import User; from sqlalchemy import select
        stmt = select(User).where(User.telegram_id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        return user.group_name if user else None

def format_schedule_msg(schedule, group_name: str, homework: dict = None) -> str:
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    d_str = days[schedule.date.weekday()]
    date_str = schedule.date.strftime('%d.%m')
    h = f"📅 {d_str} ({date_str} | {schedule.week_type})\n"
    if not schedule.lessons: return h + "\n🎉 Пар нет!"
    b = ""; nums = {0:"0️⃣",1:"1️⃣",2:"2️⃣",3:"3️⃣",4:"4️⃣",5:"5️⃣",6:"6️⃣",7:"7️⃣"}
    for l in schedule.lessons:
        icon = nums.get(l.pair_num, str(l.pair_num))
        if l.type == LessonType.CANCELLATION: line = f"🚫 {icon} {l.original_subject} (ОТМЕНА)"
        else:
            p = "🔄 " if l.type == LessonType.REPLACEMENT else ("➕ " if l.type == LessonType.ADDED else "")
            txt = f"{l.subject}"
            if l.room: txt += f" - {l.room}"
            line = f"{p}{icon} {txt}"
        b += "\n" + line
    if homework:
        b += "\n\n📚 **ДЗ:**"
        for subj, text in homework.items(): b += f"\n▪️ **{subj}:** {text}"
    return h + b

async def send_schedule_response(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    uid = update.effective_user.id
    group = await get_user_group(uid)
    if not group: await update.message.reply_text("❌ Сначала выберите группу.", reply_markup=MAIN_KB); return
    await core.update_replacements()
    today = datetime.date.today(); dates = []
    if mode == "today": dates = [today]
    elif mode == "tomorrow": dates = [today + datetime.timedelta(days=1)]
    elif mode == "week": dates = [today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(days=i) for i in range(6)]
    for d in dates:
        if d.weekday() == 6 and mode != "week": await update.message.reply_text("📅 **Воскресенье**\nВыходной!", parse_mode="Markdown"); continue
        s = core.get_schedule(group, d)
        hw = await db.get_homework(group, d)
        await update.message.reply_text(format_schedule_msg(s, group, homework=hw), parse_mode="Markdown")

# --- COMMAND WRAPPERS ---
async def cmd_today(u, c): await send_schedule_response(u, c, "today")
async def cmd_tomorrow(u, c): await send_schedule_response(u, c, "tomorrow")
async def cmd_week(u, c): await send_schedule_response(u, c, "week")

# --- HANDLERS ---
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text; uid = update.effective_user.id
    if update.effective_chat.type != "private" and text not in ["Сегодня", "Завтра", "Неделя"]: return
    
    if text == "Сегодня": await send_schedule_response(update, context, "today"); return
    if text == "Завтра": await send_schedule_response(update, context, "tomorrow"); return
    if text == "Неделя": await send_schedule_response(update, context, "week"); return

    if text == "Настройки":
        role = await db.get_user_role(uid)
        kb_list = [["Сменить группу"], ["👤 Представиться"], ["Назад"]]
        if role == "headman" or uid == ADMIN_ID:
            wa_hw = WebAppInfo(url="https://gradygk.ru/homework")
            wa_panel = WebAppInfo(url="https://gradygk.ru/headman")
            kb_list.insert(0, [KeyboardButton("👥 Управление", web_app=wa_panel)])
            kb_list.insert(0, [KeyboardButton("📝 Заполнить ДЗ", web_app=wa_hw)])
        await update.message.reply_text("⚙️ Настройки:", reply_markup=ReplyKeyboardMarkup(kb_list, resize_keyboard=True))
        return
    if text == "Назад": await update.message.reply_text("Меню:", reply_markup=MAIN_KB); return
    if text == "Сменить группу" or text == "Группа": await update.message.reply_text("Напишите новую группу (например ИС1-21):"); return

    # Search
    norm = core._normalize_name(text)
    found = []
    for g in core._base_schedule.keys():
        if norm in core._normalize_name(g): found.append(g)
    if found:
        if len(found) == 1:
            await db.set_group(uid, found[0])
            await update.message.reply_text(f"✅ Группа **{found[0]}** сохранена!", reply_markup=MAIN_KB, parse_mode="Markdown")
        else:
            kb = ReplyKeyboardMarkup([[KeyboardButton(g)] for g in found[:6]], resize_keyboard=True)
            await update.message.reply_text(f"🔎 Выберите группу:", reply_markup=kb)
    else: 
        if update.effective_chat.type == "private": await update.message.reply_text("❌ Не понял. Используйте меню.")

# --- DIALOGS ---
async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; group = await get_user_group(uid)
    if not group: await update.message.reply_text("❌ Выберите группу."); return ConversationHandler.END
    await update.message.reply_text(f"Введи ФИО для {group}:", reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True))
    return SETTING_NAME

async def set_name_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip(); user = update.effective_user
    if text == "Отмена": await update.message.reply_text("Отменено.", reply_markup=MAIN_KB); return ConversationHandler.END
    if len(text) < 3: await update.message.reply_text("⚠️ Введите ФИО."); return SETTING_NAME
    group = await get_user_group(user.id)
    if not group: await update.message.reply_text("❌ Нет группы.", reply_markup=MAIN_KB); return ConversationHandler.END
    await db.register_student_self(user.id, group, text, user.username)
    await update.message.reply_text(f"✅ Записан: **{text}**", reply_markup=MAIN_KB, parse_mode="Markdown")
    return ConversationHandler.END

async def group_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Группа:", reply_markup=ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)); return SELECTING_GROUP

async def group_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip(); uid = update.effective_user.id
    if t=="Отмена": return await cancel_op(update, context)
    norm = core._normalize_name(t)
    found = next((g for g in core._base_schedule if core._normalize_name(g)==norm), None)
    if found: await db.set_group(uid, found); await update.message.reply_text(f"✅ {found}", reply_markup=MAIN_KB); return ConversationHandler.END
    await update.message.reply_text("❌ Нет такой"); return SELECTING_GROUP
async def cancel_op(u, c): await u.message.reply_text("Отмена", reply_markup=MAIN_KB); return ConversationHandler.END

# --- ADMIN CMDS ---
async def set_headman(u, c):
    if u.effective_user.id != ADMIN_ID: return
    try: await db.set_user_role(int(c.args[0]), "headman"); await u.message.reply_text("✅ OK")
    except: pass
async def hw_enable(u, c):
    role = await db.get_user_role(u.effective_user.id); g = await get_user_group(u.effective_user.id)
    if (role=="headman" or u.effective_user.id==ADMIN_ID) and g: await db.toggle_hw_system(g, True); await u.message.reply_text("✅ ON")
async def hw_disable(u, c):
    role = await db.get_user_role(u.effective_user.id); g = await get_user_group(u.effective_user.id)
    if (role=="headman" or u.effective_user.id==ADMIN_ID) and g: await db.toggle_hw_system(g, False); await u.message.reply_text("✅ OFF")
async def admin_stat(u, c):
    if u.effective_user.id != ADMIN_ID: return
    s = await db.get_detailed_stats(); await u.message.reply_text(f"📊 {s}")
async def admin_broadcast(u, c):
    if u.effective_user.id != ADMIN_ID or not c.args: return
    t = await db.get_users_for_broadcast(c.args[0]); await u.message.reply_text(f"🚀 {len(t)}")
    for i in t: 
        try: await c.bot.send_message(i, " ".join(c.args[1:]), parse_mode="Markdown")
        except: pass
    await u.message.reply_text("Готово.")
async def set_pin_cmd(u, c):
    if u.effective_user.id != ADMIN_ID: return
    await db.set_group_pin(c.args[0], c.args[1]); await u.message.reply_text(f"🔑 {c.args[1]}")
async def get_pin_cmd(u, c):
    if u.effective_user.id != ADMIN_ID: return
    p = await db.get_group_pin(c.args[0]); await u.message.reply_text(f"🔑 {p}")
async def force_update_cmd(u, c):
    if u.effective_user.id != ADMIN_ID: return
    await u.message.reply_text("🔄"); res = await core.update_replacements(True)
    await u.message.reply_text(f"✅ {len(res[0])}")
async def cmd_duty(u, c):
    g = await get_user_group(u.effective_user.id)
    if not g: await u.message.reply_text("❌"); return
    # Используем метод сдвига очереди или чтения? Для просмотра лучше readonly, но его нет в db
    # Используем get_students_by_group
    st = await db.get_students_by_group(g)
    msg = "\n".join([f"{x.queue_order+1}. {x.full_name}" for x in st])
    await u.message.reply_text(f"🧹 Очередь:\n{msg}" if msg else "Пусто")

async def start(u, c):
    args = c.args; src = args[0] if args else "organic"; grp = None
    if src.startswith("setgroup_"): grp = src.replace("setgroup_", ""); src = "webapp"
    await db.register_user(u.effective_user.id, u.effective_user.username, u.effective_user.full_name, src)
    if grp:
        norm = core._normalize_name(grp)
        found = next((g for g in core._base_schedule if core._normalize_name(g)==norm), None)
        if found: await db.set_group(u.effective_user.id, found); await u.message.reply_text(f"✅ {found}", reply_markup=MAIN_KB); return
    await u.message.reply_text("Привет!", reply_markup=MAIN_KB)

# --- JOBS ---
async def broadcast_updates(context, replacements):
    affected = set(); [affected.add(g) for r in replacements for g in r['groups']]
    affected_norms = set(core._normalize_name(g) for g in affected)
    if not affected_norms: return
    all_db_groups = await db.get_all_unique_groups(); groups_to_notify = []
    for db_g in all_db_groups:
        db_norm = core._normalize_name(db_g)
        for aff in affected_norms:
            if aff in db_norm or db_norm in aff: groups_to_notify.append(db_g); break
            
    for group in groups_to_notify:
        users = await db.get_users_to_notify(group)
        if not users: continue
        td = core._cache_date; sched = core.get_schedule(group, td); hw = await db.get_homework(group, td)
        txt = format_schedule_msg(sched, group, hw)
        msg = f"🔔 **ИЗМЕНЕНИЯ {td.strftime('%d.%m')}!**\n\n{txt}\n\n/tomorrow"
        for uid in users:
            try: await context.bot.send_message(uid, msg, parse_mode="Markdown"); await db.update_notify_date(uid); await asyncio.sleep(0.05)
            except: pass

async def job_smart_poll(context):
    res = await core.update_replacements()
    data, is_changed = res if isinstance(res, tuple) else (res, True)
    if is_changed and core._cache_date >= datetime.date.today():
        await broadcast_updates(context, data); await context.bot.send_message(ADMIN_ID, "✅ Рассылка")
    elif datetime.datetime.now().hour < 19: context.job_queue.run_once(job_smart_poll, 600)

async def job_autoset_duty(context):
    for g in await db.get_autoset_groups():
        s = await db.get_next_duty_students(g, 2); hm = await db.get_headman_id(g)
        if s and hm: await context.bot.send_message(hm, f"📅 Дежурные: {', '.join([x.full_name for x in s])}")
        for x in s:
            if x.telegram_id:
                try: await context.bot.send_message(x.telegram_id, "👋 Ты дежурный!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤒 Болею", callback_data=f"sick_{x.id}")]]))
                except: pass

async def job_check_duty(context):
    for g in await db.get_active_hw_groups():
        if not await db.check_homework_exists(g, datetime.date.today()+datetime.timedelta(days=1)):
            hm = await db.get_headman_id(g)
            if hm: await context.bot.send_message(hm, "😡 Нет ДЗ!")

async def job_reset_sick(context): await db.reset_sick_flags()

async def sick_callback(u, c):
    q=u.callback_query; await q.answer()
    try: sid = int(q.data.split("_")[1])
    except: return
    s = await db.get_student_by_tg_id(u.effective_user.id)
    if not s or s.id != sid: await q.answer("Не твое", show_alert=True); return
    await db.set_student_sick(sid, True)
    rep = await db.get_next_duty_students(s.group_name, 1)
    msg = "✅ Ок"
    if rep:
        ng = rep[0]; msg += f"\n🔄 {ng.full_name}"
        if ng.telegram_id: 
            try: await c.bot.send_message(ng.telegram_id, f"🆘 Замена!\n{s.full_name} заболел.", parse_mode="Markdown")
            except: pass
    await q.edit_message_text(msg)
    hm = await db.get_headman_id(s.group_name)
    if hm: await c.bot.send_message(hm, f"🚑 {s.full_name} заболел")

async def start_polling_trigger(context): context.job_queue.run_once(job_smart_poll, 1)
async def post_init(app): await db.init_db(); await core.update_replacements(True)

def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(TypeHandler(Update, pre_process_update), group=-1)
    app.add_handler(CallbackQueryHandler(sub_callback_handler, pattern="^check_sub$"))
    app.add_handler(TypeH