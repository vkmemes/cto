import os
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.error import Forbidden, BadRequest

from database import Database
from core import ScheduleManager

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8195041032:AAGvHDGKzOnLYCL-TksT63znzieji9cRvdk"
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@ygkschedule")
REPLACEMENT_URL = os.getenv("REPLACEMENT_URL", "https://example.com/replacements.html")

db = Database()
schedule_manager = ScheduleManager(replacement_url=REPLACEMENT_URL)

SELECT_GROUP, ENTER_NAME = range(2)

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Error checking subscription for {user_id}: {e}")
        return False

async def subscription_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        user_id = update.effective_user.id
        
        if not await check_subscription(user_id, context):
            keyboard = [[InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❌ Для использования бота необходимо подписаться на наш канал!",
                reply_markup=reply_markup
            )
            return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await subscription_middleware(update, context):
        return ConversationHandler.END
    
    user = update.effective_user
    await db.upsert_user(user.id, user.username)
    
    if context.args and len(context.args) > 0:
        group_param = context.args[0]
        group_key = schedule_manager.find_group_key(group_param)
        if group_key:
            await db.upsert_user(user.id, user.username, group_key)
            await update.message.reply_text(
                f"✅ Группа установлена: {group_key}\n\n"
                "Используйте команды:\n"
                "/today - расписание на сегодня\n"
                "/tomorrow - расписание на завтра\n"
                "/week - расписание на неделю"
            )
            return ConversationHandler.END
    
    groups = schedule_manager.get_all_groups()
    if not groups:
        await update.message.reply_text("❌ Список групп пуст. Добавьте группы в schedule.json")
        return ConversationHandler.END
    
    keyboard = []
    for group in groups:
        keyboard.append([InlineKeyboardButton(group, callback_data=f"group_{group}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Добро пожаловать в STTEC Schedule!\n\nВыберите вашу группу:",
        reply_markup=reply_markup
    )
    
    return SELECT_GROUP

async def group_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    group_name = query.data.replace("group_", "")
    context.user_data["selected_group"] = group_name
    
    await query.edit_message_text(
        f"✅ Выбрана группа: {group_name}\n\n"
        "📝 Теперь введите ваше ФИО (например: Иванов Иван Иванович):"
    )
    
    return ENTER_NAME

async def name_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_name = update.message.text.strip()
    group_name = context.user_data.get("selected_group")
    
    if not group_name:
        await update.message.reply_text("❌ Ошибка: группа не выбрана. Начните заново с /start")
        return ConversationHandler.END
    
    await db.upsert_user(user.id, user.username, group_name, full_name)
    await db.upsert_student(group_name, user.id, full_name)
    
    await update.message.reply_text(
        f"✅ Регистрация завершена!\n\n"
        f"👤 ФИО: {full_name}\n"
        f"🎓 Группа: {group_name}\n\n"
        "Используйте команды:\n"
        "/today - расписание на сегодня\n"
        "/tomorrow - расписание на завтра\n"
        "/week - расписание на неделю"
    )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Регистрация отменена. Используйте /start для начала.")
    return ConversationHandler.END

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await subscription_middleware(update, context):
        return
    
    user = update.effective_user
    user_data = await db.get_user(user.id)
    
    if not user_data or not user_data.group_name:
        await update.message.reply_text("❌ Группа не установлена. Используйте /start для регистрации.")
        return
    
    target_date = date.today()
    day_schedule = await schedule_manager.get_schedule_for_date(user_data.group_name, target_date)
    
    if day_schedule:
        text = schedule_manager.format_schedule_text(day_schedule)
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("❌ Не удалось получить расписание.")

async def tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await subscription_middleware(update, context):
        return
    
    user = update.effective_user
    user_data = await db.get_user(user.id)
    
    if not user_data or not user_data.group_name:
        await update.message.reply_text("❌ Группа не установлена. Используйте /start для регистрации.")
        return
    
    target_date = date.today() + timedelta(days=1)
    day_schedule = await schedule_manager.get_schedule_for_date(user_data.group_name, target_date)
    
    if day_schedule:
        text = schedule_manager.format_schedule_text(day_schedule)
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("❌ Не удалось получить расписание.")

async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await subscription_middleware(update, context):
        return
    
    user = update.effective_user
    user_data = await db.get_user(user.id)
    
    if not user_data or not user_data.group_name:
        await update.message.reply_text("❌ Группа не установлена. Используйте /start для регистрации.")
        return
    
    week_schedule = await schedule_manager.get_week_schedule(user_data.group_name)
    
    if week_schedule:
        for day_schedule in week_schedule:
            text = schedule_manager.format_schedule_text(day_schedule)
            await update.message.reply_text(text)
            await asyncio.sleep(0.5)
    else:
        await update.message.reply_text("❌ Не удалось получить расписание на неделю.")

async def setpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await subscription_middleware(update, context):
        return
    
    user = update.effective_user
    user_data = await db.get_user(user.id)
    
    if not user_data or not user_data.group_name:
        await update.message.reply_text("❌ Группа не установлена. Используйте /start для регистрации.")
        return
    
    student = await db.get_student(user.id)
    if not student or not student.is_headman:
        await update.message.reply_text("❌ Эта команда доступна только старосте группы.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ Использование: /setpin <PIN-код>")
        return
    
    pin_code = context.args[0]
    await db.set_group_pin(user_data.group_name, pin_code, user.id)
    
    await update.message.reply_text(f"✅ PIN-код для группы {user_data.group_name} установлен: {pin_code}")

async def job_smart_poll(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running job_smart_poll")
    
    try:
        replacements = await schedule_manager.fetch_replacements()
        
        if not replacements:
            logger.info("No replacements found")
            return
        
        target_date_str = date.today().strftime("%d.%m.%Y")
        schedule_cache = {}
        
        for group_name, repl_data in replacements.items():
            if repl_data.get("date") != target_date_str:
                continue
            
            users = await db.get_users_by_group(group_name)
            if group_name not in schedule_cache:
                schedule_cache[group_name] = await schedule_manager.get_schedule_for_date(group_name, date.today())
            day_schedule = schedule_cache[group_name]
            if not day_schedule:
                continue
            
            for user in users:
                if user.last_notify_date == date.today():
                    continue
                
                try:
                    text = "🔔 Обновление расписания!\n\n" + schedule_manager.format_schedule_text(day_schedule)
                    await context.bot.send_message(chat_id=user.user_id, text=text)
                    await db.mark_user_notified_today(user.user_id)
                    await asyncio.sleep(0.05)
                except (Forbidden, BadRequest) as e:
                    logger.warning(f"Cannot send to user {user.user_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in job_smart_poll: {e}")

async def job_autoset_duty(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running job_autoset_duty")
    
    try:
        groups = schedule_manager.get_all_groups()
        
        for group_name in groups:
            students = await db.get_students_by_group(group_name)
            healthy_students = [s for s in students if not s.is_sick]
            
            if not healthy_students:
                continue
            
            settings = await db.get_group_settings(group_name)
            
            if settings and settings.current_duty_id:
                current_index = None
                for i, s in enumerate(healthy_students):
                    if s.user_id == settings.current_duty_id:
                        current_index = i
                        break
                
                if current_index is not None:
                    next_index = (current_index + 1) % len(healthy_students)
                    next_duty = healthy_students[next_index]
                else:
                    next_duty = healthy_students[0]
            else:
                next_duty = healthy_students[0]
            
            await db.upsert_group_settings(group_name, current_duty_id=next_duty.user_id)
            logger.info(f"Set duty for {group_name}: {next_duty.full_name}")
    
    except Exception as e:
        logger.error(f"Error in job_autoset_duty: {e}")

async def job_check_duty(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running job_check_duty")
    
    try:
        groups = schedule_manager.get_all_groups()
        
        for group_name in groups:
            settings = await db.get_group_settings(group_name)
            
            if not settings or not settings.current_duty_id:
                continue
            
            student = await db.get_student(settings.current_duty_id)
            if not student:
                continue
            
            try:
                await context.bot.send_message(
                    chat_id=settings.current_duty_id,
                    text=f"📢 Напоминание: вы дежурный в группе {group_name}!"
                )
            except (Forbidden, BadRequest) as e:
                logger.warning(f"Cannot send duty reminder to {settings.current_duty_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error in job_check_duty: {e}")

async def job_reset_sick(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running job_reset_sick")
    
    try:
        await db.reset_all_sick_flags()
        logger.info("Reset all sick flags")
    except Exception as e:
        logger.error(f"Error in job_reset_sick: {e}")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_GROUP: [CallbackQueryHandler(group_selected, pattern="^group_")],
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_entered)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("tomorrow", tomorrow))
    application.add_handler(CommandHandler("week", week))
    application.add_handler(CommandHandler("setpin", setpin))
    
    job_queue = application.job_queue
    job_queue.run_daily(job_smart_poll, time=datetime.strptime("12:05", "%H:%M").time())
    job_queue.run_daily(job_autoset_duty, time=datetime.strptime("14:00", "%H:%M").time())
    job_queue.run_daily(job_check_duty, time=datetime.strptime("17:00", "%H:%M").time())
    job_queue.run_daily(job_reset_sick, time=datetime.strptime("00:00", "%H:%M").time())
    
    async def post_init(application: Application):
        await db.init_db()
        logger.info("Database initialized")
    
    async def post_shutdown(application: Application):
        await db.close()
        await schedule_manager.close()
        logger.info("Database closed")
    
    application.post_init = post_init
    application.post_shutdown = post_shutdown
    
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
