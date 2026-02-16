import os
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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

# Conversation states
SELECT_GROUP, ENTER_NAME, SEARCH_GROUP, CONFIRM_GROUP = range(4)

# Keyboard layouts
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("📅 Сегодня"), KeyboardButton("📆 Завтра")],
    [KeyboardButton("🗓 Неделя"), KeyboardButton("🔍 Поиск группы")],
    [KeyboardButton("⚙️ Сменить группу"), KeyboardButton("❓ Помощь")]
], resize_keyboard=True)

SEARCH_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("❌ Отменить поиск")]
], resize_keyboard=True)

CANCEL_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("❌ Отмена")]
], resize_keyboard=True)

REMOVE_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("🗑 Убрать клавиатуру")]
], resize_keyboard=True)


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
                "❌ Для использования бота необходимо подписаться на наш канал!\n\n"
                "Подпишитесь на канал и нажмите /start снова.",
                reply_markup=reply_markup
            )
            return False
    return True


def get_welcome_text(user_name: str) -> str:
    return (
        f"👋 Добро пожаловать, {user_name}!\n\n"
        "📚 <b>STTEC Schedule</b> — ваш помощник в просмотре расписания занятий.\n\n"
        "✨ <b>Что умеет бот:</b>\n"
        "• Показывать расписание на сегодня, завтра и неделю\n"
        "• Учитывать замены и отмены пар\n"
        "• Отправлять уведомления об изменениях\n\n"
        "📝 <b>Для начала работы выберите свою группу</b>\n\n"
        "Вы можете:\n"
        "1️⃣ Ввести название группы (например: <code>СА1-11</code>)\n"
        "2️⃣ Использовать команду /search для поиска\n\n"
        "💡 <b>Подсказка:</b> Если не знаете точное название группы, просто введите часть названия (например, <code>СА</code> или <code>11</code>)"
    )


def get_registered_text(group_name: str) -> str:
    return (
        f"👋 С возвращением!\n\n"
        f"🎓 <b>Ваша группа:</b> {group_name}\n\n"
        "Выберите действие в меню ниже или используйте команды:\n"
        "• /today — расписание на сегодня\n"
        "• /tomorrow — расписание на завтра\n"
        "• /week — расписание на неделю\n"
        "• /search — поиск группы\n"
        "• /change_group — сменить группу\n"
        "• /help — справка"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await subscription_middleware(update, context):
        return ConversationHandler.END

    user = update.effective_user
    await db.upsert_user(user.id, user.username)

    # Check if user is already registered with a group
    user_data = await db.get_user(user.id)

    # Handle deep linking with group parameter
    if context.args and len(context.args) > 0:
        group_param = context.args[0]
        group_key = schedule_manager.find_group_key(group_param)
        if group_key:
            await db.upsert_user(user.id, user.username, group_key)
            await db.upsert_student(group_key, user.id, user.full_name or user.username or "")
            await update.message.reply_text(
                f"✅ Группа установлена: <b>{group_key}</b>\n\n"
                "Используйте кнопки меню ниже или команды для просмотра расписания.",
                parse_mode="HTML",
                reply_markup=MAIN_MENU_KEYBOARD
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                f"⚠️ Группа '<code>{group_param}</code>' не найдена.\n\n"
                "Попробуйте найти группу через поиск.",
                parse_mode="HTML",
                reply_markup=SEARCH_KEYBOARD
            )
            return SEARCH_GROUP

    # If user already has a group, show welcome back message
    if user_data and user_data.group_name:
        await update.message.reply_text(
            get_registered_text(user_data.group_name),
            parse_mode="HTML",
            reply_markup=MAIN_MENU_KEYBOARD
        )
        return ConversationHandler.END

    # New user - ask for group input
    await update.message.reply_text(
        get_welcome_text(user.first_name),
        parse_mode="HTML",
        reply_markup=SEARCH_KEYBOARD
    )

    return SELECT_GROUP


async def handle_group_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group name input from user."""
    user_input = update.message.text.strip()

    # Check for cancel
    if user_input == "❌ Отменить поиск" or user_input == "❌ Отмена":
        await update.message.reply_text(
            "❌ Действие отменено.\n\nИспользуйте /start для начала работы.",
            reply_markup=REMOVE_KEYBOARD
        )
        return ConversationHandler.END

    # Check for main menu buttons (if user already registered)
    if user_input in ["📅 Сегодня", "📆 Завтра", "🗓 Неделя", "❓ Помощь"]:
        return await handle_main_menu(update, context)

    if user_input == "🔍 Поиск группы":
        return await search_command(update, context)

    if user_input == "⚙️ Сменить группу":
        return await change_group_command(update, context)

    # Validate input length
    if len(user_input) < 2:
        await update.message.reply_text(
            "⚠️ Название группы слишком короткое.\n\n"
            "Введите минимум 2 символа или используйте /search для поиска.",
            reply_markup=SEARCH_KEYBOARD
        )
        return SELECT_GROUP

    if len(user_input) > 50:
        await update.message.reply_text(
            "⚠️ Название группы слишком длинное.\n\n"
            "Пожалуйста, проверьте правильность ввода.",
            reply_markup=SEARCH_KEYBOARD
        )
        return SELECT_GROUP

    # Try exact match first
    group_key = schedule_manager.find_group_key(user_input)

    if group_key:
        # Exact match found
        context.user_data["selected_group"] = group_key
        await update.message.reply_text(
            f"✅ Найдена группа: <b>{group_key}</b>\n\n"
            "📝 Теперь введите ваше ФИО (например: <b>Иванов Иван Иванович</b>):\n\n"
            "💡 Это нужно для функций старосты и дежурства.",
            parse_mode="HTML",
            reply_markup=CANCEL_KEYBOARD
        )
        return ENTER_NAME

    # No exact match - search for similar groups
    search_results = schedule_manager.search_groups(user_input, limit=15)

    if not search_results:
        await update.message.reply_text(
            f"❌ Группа '<code>{user_input}</code>' не найдена.\n\n"
            "💡 <b>Попробуйте:</b>\n"
            "• Проверить правильность написания\n"
            "• Использовать другую часть названия\n"
            "• Ввести код направления (например: <code>СА</code>, <code>ИС</code>)\n\n"
            "Используйте /search для расширенного поиска.",
            parse_mode="HTML",
            reply_markup=SEARCH_KEYBOARD
        )
        return SELECT_GROUP

    if len(search_results) == 1:
        # Only one result - suggest it
        group = search_results[0]
        context.user_data["selected_group"] = group
        await update.message.reply_text(
            f"🔍 Найдена похожая группа: <b>{group}</b>\n\n"
            "📝 Теперь введите ваше ФИО (например: <b>Иванов Иван Иванович</b>):",
            parse_mode="HTML",
            reply_markup=CANCEL_KEYBOARD
        )
        return ENTER_NAME

    # Multiple results - show list
    context.user_data["search_results"] = search_results

    results_text = "🔍 <b>Найдено несколько групп:</b>\n\n"
    for i, group in enumerate(search_results[:10], 1):
        results_text += f"{i}. {group}\n"

    if len(search_results) > 10:
        results_text += f"\n<i>...и ещё {len(search_results) - 10} групп</i>\n"

    results_text += (
        "\n<b>Введите номер группы из списка (1-{}),</b>\n"
        "<b>полное название или уточните запрос:</b>".format(min(len(search_results), 10))
    )

    await update.message.reply_text(
        results_text,
        parse_mode="HTML",
        reply_markup=CANCEL_KEYBOARD
    )
    return SELECT_GROUP


async def handle_selection_from_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle selection from search results list."""
    user_input = update.message.text.strip()

    # Check for cancel
    if user_input == "❌ Отмена":
        await update.message.reply_text(
            "❌ Действие отменено.\n\nИспользуйте /start для начала работы.",
            reply_markup=REMOVE_KEYBOARD
        )
        return ConversationHandler.END

    # Try to parse as number
    search_results = context.user_data.get("search_results", [])

    if user_input.isdigit() and search_results:
        selection = int(user_input)
        if 1 <= selection <= len(search_results):
            selected_group = search_results[selection - 1]
            context.user_data["selected_group"] = selected_group
            await update.message.reply_text(
                f"✅ Выбрана группа: <b>{selected_group}</b>\n\n"
                "📝 Теперь введите ваше ФИО (например: <b>Иванов Иван Иванович</b>):",
                parse_mode="HTML",
                reply_markup=CANCEL_KEYBOARD
            )
            return ENTER_NAME

    # Not a valid selection - treat as new search
    return await handle_group_input(update, context)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command."""
    if not await subscription_middleware(update, context):
        return

    args = context.args

    if not args:
        await update.message.reply_text(
            "🔍 <b>Поиск группы</b>\n\n"
            "Введите часть названия группы:\n"
            "• Код направления (<code>СА</code>, <code>ИС</code>)\n"
            "• Номер курса (<code>1-</code>, <code>2-</code>)\n"
            "• Номер группы (<code>-11</code>, <code>-12</code>)\n\n"
            "Или просто отправьте название группы.",
            parse_mode="HTML",
            reply_markup=SEARCH_KEYBOARD
        )
        return SEARCH_GROUP

    # Search with provided argument
    search_term = " ".join(args)
    results = schedule_manager.search_groups(search_term, limit=20)

    if not results:
        await update.message.reply_text(
            f"❌ По запросу '<code>{search_term}</code>' ничего не найдено.\n\n"
            "Попробуйте другой запрос или введите /search без параметров.",
            parse_mode="HTML",
            reply_markup=MAIN_MENU_KEYBOARD
        )
        return ConversationHandler.END

    if len(results) == 1:
        group = results[0]
        user = update.effective_user
        await db.upsert_user(user.id, user.username, group)
        await db.upsert_student(group, user.id, user.full_name or "")
        await update.message.reply_text(
            f"✅ Группа найдена и установлена: <b>{group}</b>\n\n"
            "Используйте кнопки меню ниже для просмотра расписания.",
            parse_mode="HTML",
            reply_markup=MAIN_MENU_KEYBOARD
        )
        return ConversationHandler.END

    # Show results
    results_text = f"🔍 <b>Результаты поиска по '{search_term}':</b>\n\n"
    for i, group in enumerate(results[:15], 1):
        results_text += f"{i}. {group}\n"

    if len(results) > 15:
        results_text += f"\n<i>...и ещё {len(results) - 15} групп</i>\n"

    results_text += (
        f"\n<b>Используйте /start &lt;название_группы&gt;</b>\n"
        f"<b>или /change_group &lt;название_группы&gt; для выбора</b>"
    )

    await update.message.reply_text(
        results_text,
        parse_mode="HTML",
        reply_markup=MAIN_MENU_KEYBOARD
    )
    return ConversationHandler.END


async def search_group_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group search input."""
    user_input = update.message.text.strip()

    if user_input == "❌ Отменить поиск":
        await update.message.reply_text(
            "❌ Поиск отменён.\n\nИспользуйте /start для начала работы.",
            reply_markup=REMOVE_KEYBOARD
        )
        return ConversationHandler.END

    return await handle_group_input(update, context)


async def change_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /change_group command - allows changing group without losing data."""
    if not await subscription_middleware(update, context):
        return

    user = update.effective_user
    user_data = await db.get_user(user.id)
    current_group = user_data.group_name if user_data else None

    args = context.args

    if not args:
        # Show current group and ask for new one
        current_text = f"🎓 <b>Текущая группа:</b> {current_group}\n\n" if current_group else ""
        await update.message.reply_text(
            f"{current_text}"
            "🔍 <b>Смена группы</b>\n\n"
            "Введите название новой группы:\n"
            "• Введите часть названия для поиска\n"
            "• Или полное название группы\n\n"
            "💡 <b>Ваши данные (ФИО, статус старосты) сохранятся</b>",
            parse_mode="HTML",
            reply_markup=CANCEL_KEYBOARD
        )
        context.user_data["changing_group"] = True
        return SELECT_GROUP

    # Direct group change with argument
    new_group = " ".join(args)
    group_key = schedule_manager.find_group_key(new_group)

    if not group_key:
        # Try search
        results = schedule_manager.search_groups(new_group, limit=10)
        if not results:
            await update.message.reply_text(
                f"❌ Группа '<code>{new_group}</code>' не найдена.\n\n"
                "Используйте /change_group без параметров для поиска.",
                parse_mode="HTML",
                reply_markup=MAIN_MENU_KEYBOARD
            )
            return ConversationHandler.END

        if len(results) == 1:
            group_key = results[0]
        else:
            results_text = f"🔍 <b>Найдено несколько групп по '{new_group}':</b>\n\n"
            for i, group in enumerate(results[:10], 1):
                results_text += f"{i}. {group}\n"
            results_text += (
                f"\n<b>Используйте:</b>\n"
                f"/change_group &lt;полное_название&gt;"
            )
            await update.message.reply_text(
                results_text,
                parse_mode="HTML",
                reply_markup=MAIN_MENU_KEYBOARD
            )
            return ConversationHandler.END

    # Update user's group
    await db.upsert_user(user.id, user.username, group_key)

    # Update student record if exists
    student = await db.get_student(user.id)
    if student:
        await db.upsert_student(
            group_key,
            user.id,
            student.full_name,
            student.is_headman,
            student.is_sick
        )

    await update.message.reply_text(
        f"✅ Группа успешно изменена!\n\n"
        f"🎓 <b>Новая группа:</b> {group_key}\n"
        f"📊 <b>Предыдущая группа:</b> {current_group or 'не установлена'}\n\n"
        "Используйте кнопки меню ниже для просмотра расписания.",
        parse_mode="HTML",
        reply_markup=MAIN_MENU_KEYBOARD
    )
    return ConversationHandler.END


async def name_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle full name input and complete registration."""
    user = update.effective_user
    full_name = update.message.text.strip()

    # Check for cancel
    if full_name == "❌ Отмена":
        await update.message.reply_text(
            "❌ Регистрация отменена.\n\nИспользуйте /start для начала работы.",
            reply_markup=REMOVE_KEYBOARD
        )
        return ConversationHandler.END

    group_name = context.user_data.get("selected_group")

    if not group_name:
        await update.message.reply_text(
            "❌ Ошибка: группа не выбрана.\n\nИспользуйте /start для начала работы.",
            reply_markup=REMOVE_KEYBOARD
        )
        return ConversationHandler.END

    # Validate name
    if len(full_name) < 3:
        await update.message.reply_text(
            "⚠️ ФИО слишком короткое.\n\n"
            "Пожалуйста, введите полное ФИО (минимум 3 символа):",
            reply_markup=CANCEL_KEYBOARD
        )
        return ENTER_NAME

    if len(full_name) > 100:
        await update.message.reply_text(
            "⚠️ ФИО слишком длинное.\n\n"
            "Пожалуйста, проверьте правильность ввода:",
            reply_markup=CANCEL_KEYBOARD
        )
        return ENTER_NAME

    # Save user data
    await db.upsert_user(user.id, user.username, group_name, full_name)
    await db.upsert_student(group_name, user.id, full_name)

    # Clear temporary data
    context.user_data.pop("selected_group", None)
    context.user_data.pop("search_results", None)
    context.user_data.pop("changing_group", None)

    await update.message.reply_text(
        f"✅ <b>Регистрация завершена!</b>\n\n"
        f"👤 <b>ФИО:</b> {full_name}\n"
        f"🎓 <b>Группа:</b> {group_name}\n\n"
        "📚 Теперь вы можете просматривать расписание!\n\n"
        "Используйте кнопки меню ниже или команды:\n"
        "• /today — расписание на сегодня\n"
        "• /tomorrow — расписание на завтра\n"
        "• /week — расписание на неделю\n"
        "• /help — справка по всем командам",
        parse_mode="HTML",
        reply_markup=MAIN_MENU_KEYBOARD
    )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation."""
    await update.message.reply_text(
        "❌ Действие отменено.\n\nИспользуйте /start для начала работы.",
        reply_markup=REMOVE_KEYBOARD
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message."""
    help_text = (
        "❓ <b>Справка по командам бота</b>\n\n"
        "📅 <b>Расписание:</b>\n"
        "• /today — расписание на сегодня\n"
        "• /tomorrow — расписание на завтра\n"
        "• /week — расписание на неделю\n\n"
        "🔍 <b>Группы:</b>\n"
        "• /start — начало работы, выбор группы\n"
        "• /search [запрос] — поиск группы\n"
        "• /change_group [группа] — сменить группу\n\n"
        "⚙️ <b>Дополнительно:</b>\n"
        "• /setpin — установить PIN для группы (для старосты)\n"
        "• /cancel — отменить текущее действие\n"
        "• /help — показать эту справку\n\n"
        "💡 <b>Подсказки:</b>\n"
        "• Группу можно вводить частично (например, 'СА' найдёт все группы СА)\n"
        "• Бот показывает замены и отмены пар\n"
        "• Уведомления о заменах приходят автоматически\n\n"
        "📢 <b>Канал:</b> " + CHANNEL_USERNAME
    )
    await update.message.reply_text(help_text, parse_mode="HTML", reply_markup=MAIN_MENU_KEYBOARD)


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu button presses."""
    text = update.message.text

    if text == "📅 Сегодня":
        return await today(update, context)
    elif text == "📆 Завтра":
        return await tomorrow(update, context)
    elif text == "🗓 Неделя":
        return await week(update, context)
    elif text == "🔍 Поиск группы":
        return await search_command(update, context)
    elif text == "⚙️ Сменить группу":
        return await change_group_command(update, context)
    elif text == "❓ Помощь":
        return await help_command(update, context)
    elif text == "🗑 Убрать клавиатуру":
        await update.message.reply_text(
            "Клавиатура убрана.\n\nИспользуйте /start для возврата меню.",
            reply_markup=REMOVE_KEYBOARD
        )
        return ConversationHandler.END

    return ConversationHandler.END


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show schedule for today."""
    if not await subscription_middleware(update, context):
        return

    user = update.effective_user
    user_data = await db.get_user(user.id)

    if not user_data or not user_data.group_name:
        await update.message.reply_text(
            "❌ <b>Группа не установлена</b>\n\n"
            "Для просмотра расписания необходимо выбрать группу.\n\n"
            "Используйте: /start для выбора группы",
            parse_mode="HTML",
            reply_markup=REMOVE_KEYBOARD
        )
        return

    target_date = date.today()
    day_schedule = await schedule_manager.get_schedule_for_date(user_data.group_name, target_date)

    if day_schedule:
        text = schedule_manager.format_schedule_text(day_schedule)
        await update.message.reply_text(text, reply_markup=MAIN_MENU_KEYBOARD)
    else:
        await update.message.reply_text(
            "❌ Не удалось получить расписание.\n\n"
            "Попробуйте позже или проверьте настройки группы.",
            reply_markup=MAIN_MENU_KEYBOARD
        )


async def tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show schedule for tomorrow."""
    if not await subscription_middleware(update, context):
        return

    user = update.effective_user
    user_data = await db.get_user(user.id)

    if not user_data or not user_data.group_name:
        await update.message.reply_text(
            "❌ <b>Группа не установлена</b>\n\n"
            "Для просмотра расписания необходимо выбрать группу.\n\n"
            "Используйте: /start для выбора группы",
            parse_mode="HTML",
            reply_markup=REMOVE_KEYBOARD
        )
        return

    target_date = date.today() + timedelta(days=1)
    day_schedule = await schedule_manager.get_schedule_for_date(user_data.group_name, target_date)

    if day_schedule:
        text = schedule_manager.format_schedule_text(day_schedule)
        await update.message.reply_text(text, reply_markup=MAIN_MENU_KEYBOARD)
    else:
        await update.message.reply_text(
            "❌ Не удалось получить расписание.\n\n"
            "Попробуйте позже или проверьте настройки группы.",
            reply_markup=MAIN_MENU_KEYBOARD
        )


async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show schedule for the week."""
    if not await subscription_middleware(update, context):
        return

    user = update.effective_user
    user_data = await db.get_user(user.id)

    if not user_data or not user_data.group_name:
        await update.message.reply_text(
            "❌ <b>Группа не установлена</b>\n\n"
            "Для просмотра расписания необходимо выбрать группу.\n\n"
            "Используйте: /start для выбора группы",
            parse_mode="HTML",
            reply_markup=REMOVE_KEYBOARD
        )
        return

    week_schedule = await schedule_manager.get_week_schedule(user_data.group_name)

    if week_schedule:
        for day_schedule in week_schedule:
            text = schedule_manager.format_schedule_text(day_schedule)
            await update.message.reply_text(text)
            await asyncio.sleep(0.5)
        # Send menu at the end
        await update.message.reply_text(
            "✅ Расписание на неделю показано выше.",
            reply_markup=MAIN_MENU_KEYBOARD
        )
    else:
        await update.message.reply_text(
            "❌ Не удалось получить расписание на неделю.\n\n"
            "Попробуйте позже или проверьте настройки группы.",
            reply_markup=MAIN_MENU_KEYBOARD
        )


async def setpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set PIN for group (headman only)."""
    if not await subscription_middleware(update, context):
        return

    user = update.effective_user
    user_data = await db.get_user(user.id)

    if not user_data or not user_data.group_name:
        await update.message.reply_text(
            "❌ <b>Группа не установлена</b>\n\n"
            "Используйте: /start для выбора группы",
            parse_mode="HTML"
        )
        return

    student = await db.get_student(user.id)
    if not student or not student.is_headman:
        await update.message.reply_text(
            "❌ <b>Доступ запрещён</b>\n\n"
            "Эта команда доступна только старосте группы.",
            parse_mode="HTML"
        )
        return

    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ <b>Неверное использование</b>\n\n"
            "Использование: <code>/setpin &lt;PIN-код&gt;</code>\n\n"
            "Пример: <code>/setpin 1234</code>",
            parse_mode="HTML"
        )
        return

    pin_code = context.args[0]
    if len(pin_code) < 4 or len(pin_code) > 20:
        await update.message.reply_text(
            "⚠️ <b>PIN-код должен содержать от 4 до 20 символов</b>",
            parse_mode="HTML"
        )
        return

    await db.set_group_pin(user_data.group_name, pin_code, user.id)

    await update.message.reply_text(
        f"✅ <b>PIN-код установлен</b>\n\n"
        f"Группа: {user_data.group_name}\n"
        f"PIN: <code>{pin_code}</code>\n\n"
        "Этот PIN будет использоваться для доступа к веб-панели группы.",
        parse_mode="HTML"
    )


async def job_smart_poll(context: ContextTypes.DEFAULT_TYPE):
    """Send notifications about schedule changes."""
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
    """Automatically rotate duty."""
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
    """Send duty reminders."""
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
    """Reset sick flags daily."""
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
            SELECT_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_selection_from_list)],
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_entered)],
            SEARCH_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_group_input)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("search", search_command),
            CommandHandler("change_group", change_group_command),
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("tomorrow", tomorrow))
    application.add_handler(CommandHandler("week", week))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("change_group", change_group_command))
    application.add_handler(CommandHandler("setpin", setpin))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))

    # Handle main menu buttons for registered users
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_main_menu
    ))

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
