import telebot
from telebot import types
import time
import logging
import json
import os
from datetime import datetime
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==================== КОНФИГУРАЦИЯ ====================

TOKEN = '8691261964:AAEo9vhPdNcF60t101dlagLOgS0wce4w6ZY'

# НАСТРОЙКА ПРОКСИ (если нужно)
# Раскомментируйте и укажите свои прокси
# PROXY = {
#     'https': 'socks5://user:pass@host:port'  # или 'http://user:pass@host:port'
# }

# СПИСОК КАНАЛОВ ДЛЯ ПОДПИСКИ
CHANNELS = {
    '-1001853765926': 'https://t.me/+p-4YEe7H7603YmEy',

}

# ID админов
ADMIN_IDS = [5273499795, 5717125360, 8841085619]
PROXY = None
# Создаем бота с настройками
if 'PROXY' in locals():
    from telebot import apihelper
    apihelper.proxy = PROXY

bot = telebot.TeleBot(TOKEN)

# Файлы для хранения данных
STATS_FILE = 'stats.json'
PHOTOS_FILE = 'photos.json'

# Временное хранилище для админа
temp_photo_data = {}


# ==================== ПРОВЕРКА ПОДКЛЮЧЕНИЯ ====================

def check_bot_connection():
    """Проверяет соединение с Telegram API"""
    try:
        bot.get_me()
        return True
    except Exception as e:
        logging.error(f"Connection error: {e}")
        return False


# ==================== РАБОТА С ФОТО ====================

def init_photos():
    if not os.path.exists(PHOTOS_FILE):
        photos = {}
        save_photos(photos)
    return load_photos()


def save_photos(photos):
    with open(PHOTOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(photos, f, ensure_ascii=False, indent=2)


def load_photos():
    try:
        with open(PHOTOS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def add_photo(code, file_id, caption=""):
    photos = load_photos()
    photos[code] = {
        'file_id': file_id,
        'caption': caption,
        'created_at': datetime.now().isoformat(),
        'used_by': []
    }
    save_photos(photos)
    return True


def get_photo_by_code(code):
    photos = load_photos()
    return photos.get(code)


def mark_code_used(code, user_id):
    photos = load_photos()
    if code in photos:
        if user_id not in photos[code]['used_by']:
            photos[code]['used_by'].append(user_id)
        save_photos(photos)
        return True
    return False


def is_code_used_by_user(code, user_id):
    photos = load_photos()
    if code in photos:
        return user_id in photos[code]['used_by']
    return False


def get_all_photos():
    return load_photos()


def delete_photo(code):
    photos = load_photos()
    if code in photos:
        del photos[code]
        save_photos(photos)
        return True
    return False


# ==================== РАБОТА СО СТАТИСТИКОЙ ====================

def init_stats():
    if not os.path.exists(STATS_FILE):
        stats = {
            'total_clicks': 0,
            'unique_clicks': [],
            'total_subscribed': 0,
            'unique_subscribed': [],
            'total_unsubscribed': 0,
            'unique_unsubscribed': [],
            'daily_stats': {},
            'last_check': None
        }
        save_stats(stats)
    return load_stats()


def save_stats(stats):
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def load_stats():
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return init_stats()


def update_stats(user_id, action_type):
    stats = load_stats()
    today = datetime.now().strftime('%Y-%m-%d')

    if today not in stats['daily_stats']:
        stats['daily_stats'][today] = {
            'clicks': 0,
            'subscribed': 0,
            'unsubscribed': 0
        }

    if action_type == 'click':
        if user_id not in stats['unique_clicks']:
            stats['unique_clicks'].append(user_id)
            stats['total_clicks'] += 1
            stats['daily_stats'][today]['clicks'] += 1

    elif action_type == 'subscribe':
        if user_id not in stats['unique_subscribed']:
            stats['unique_subscribed'].append(user_id)
            stats['total_subscribed'] += 1
            stats['daily_stats'][today]['subscribed'] += 1

    elif action_type == 'unsubscribe':
        if user_id not in stats['unique_unsubscribed']:
            stats['unique_unsubscribed'].append(user_id)
            stats['total_unsubscribed'] += 1
            stats['daily_stats'][today]['unsubscribed'] += 1

    save_stats(stats)


# ==================== ПРОВЕРКА ПОДПИСКИ ====================

def check_subscription(user_id, update_stats_flag=False):
    """Проверяет подписку на ВСЕ каналы из списка"""
    all_subscribed = True
    subscribed_channels = []
    unsubscribed_channels = []

    for channel_id, invite_link in CHANNELS.items():
        try:
            status = bot.get_chat_member(channel_id, user_id).status
            is_subscribed = status in ['member', 'creator', 'administrator']

            if is_subscribed:
                subscribed_channels.append(channel_id)
            else:
                unsubscribed_channels.append(channel_id)
                all_subscribed = False

        except Exception as e:
            logging.error(f"Error checking subscription for user {user_id} in channel {channel_id}: {e}")
            if "chat not found" in str(e).lower():
                logging.warning(f"Channel {channel_id} not found! Skipping...")
                continue
            unsubscribed_channels.append(channel_id)
            all_subscribed = False

    if not CHANNELS:
        return True, [], []

    if update_stats_flag:
        if all_subscribed:
            update_stats(user_id, 'subscribe')
        else:
            update_stats(user_id, 'unsubscribe')

    return all_subscribed, subscribed_channels, unsubscribed_channels


def check_all_subscribers():
    """Проверяет всех подписчиков (для админ-панели)"""
    stats = load_stats()
    all_users = set(stats['unique_subscribed'] + stats['unique_unsubscribed'])
    current_subscribers = []
    for user_id in all_users:
        try:
            is_subscribed, _, _ = check_subscription(user_id)
            if is_subscribed:
                current_subscribers.append(user_id)
        except:
            continue
    return current_subscribers


def get_unsubscribed_channels_text(unsubscribed_channels):
    """Формирует текст со списком каналов, на которые нужно подписаться"""
    if not unsubscribed_channels:
        return ""

    text = "❌ **Чтобы получить фото, подпишись на каналы:**\n\n"
    for i, channel_id in enumerate(unsubscribed_channels, 1):
        invite_link = CHANNELS.get(channel_id, '')
        try:
            chat = bot.get_chat(channel_id)
            channel_name = chat.title or "Канал"
        except:
            channel_name = "Канал"
        text += f"{i}. [{channel_name}]({invite_link})\n"

    text += "\nПосле подписки нажми кнопку '✅ Проверить подписку'!"
    return text


def get_subscription_markup(unsubscribed_channels):
    """Создает клавиатуру с кнопками подписки на все каналы"""
    markup = types.InlineKeyboardMarkup(row_width=1)

    for channel_id in unsubscribed_channels:
        invite_link = CHANNELS.get(channel_id, '')
        try:
            chat = bot.get_chat(channel_id)
            channel_name = chat.title or "Канал"
        except:
            channel_name = "Канал"

        markup.add(types.InlineKeyboardButton(f"📢 Подписаться: {channel_name}", url=invite_link))

    markup.add(types.InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub"))
    return markup


# ==================== КОМАНДЫ БОТА ====================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    if user_id in ADMIN_IDS:
        show_admin_panel(message.chat.id)
        return

    try:
        is_subscribed, subscribed, unsubscribed = check_subscription(user_id, True)
    except Exception as e:
        logging.error(f"Error in start: {e}")
        bot.send_message(
            message.chat.id,
            "⚠️ **Ошибка подключения к Telegram API!**\n\n"
            "Пожалуйста, попробуйте позже или обратитесь к администратору.",
            parse_mode='Markdown'
        )
        return

    if is_subscribed:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🖼 Получить фото по коду", callback_data="enter_code"))

        for channel_id, invite_link in CHANNELS.items():
            try:
                chat = bot.get_chat(channel_id)
                channel_name = chat.title or "Канал"
            except:
                channel_name = "Канал"
            markup.add(types.InlineKeyboardButton(f"📢 {channel_name}", url=invite_link))

        bot.send_message(
            message.chat.id,
            f"👋 Привет, {user_name}!\n\n"
            f"✅ Ты подписан на все каналы!\n"
            f"🖼 Нажми кнопку и введи 4-значный код, чтобы получить фото!",
            reply_markup=markup
        )
    else:
        markup = get_subscription_markup(unsubscribed)

        text = f"👋 Привет, {user_name}!\n\n"
        text += get_unsubscribed_channels_text(unsubscribed)
        text += "\n\n🔥 После подписки нажми 'Проверить подписку' и введи код! 🖼"

        bot.send_message(
            message.chat.id,
            text,
            reply_markup=markup,
            parse_mode='Markdown'
        )


# ==================== ОБРАБОТЧИКИ КНОПОК ====================

@bot.callback_query_handler(func=lambda call: call.data == "enter_code")
def enter_code_prompt(call):
    user_id = call.from_user.id

    try:
        is_subscribed, subscribed, unsubscribed = check_subscription(user_id, True)
    except:
        bot.answer_callback_query(call.id, "⚠️ Ошибка проверки подписки!", show_alert=True)
        return

    if not is_subscribed:
        bot.answer_callback_query(call.id, "❌ Ты отписался от каналов!", show_alert=True)

        markup = get_subscription_markup(unsubscribed)
        text = "❌ **Ты отписался от каналов!**\n\n"
        text += get_unsubscribed_channels_text(unsubscribed)

        try:
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            if "message is not modified" in str(e):
                bot.send_message(
                    call.message.chat.id,
                    text,
                    reply_markup=markup,
                    parse_mode='Markdown'
                )
            else:
                raise e
        return

    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        "🔑 **Введи 4-значный код для получения фото:**\n\n"
        "Пример: `1234`\n\n"
        "Код можно получить у администратора.",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_code)


@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def main_menu(call):
    bot.answer_callback_query(call.id)
    start(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    user_id = call.from_user.id
    try:
        is_subscribed, subscribed, unsubscribed = check_subscription(user_id, True)
    except:
        bot.answer_callback_query(call.id, "⚠️ Ошибка проверки!", show_alert=True)
        return

    if is_subscribed:
        bot.answer_callback_query(call.id, "✅ Подписка на все каналы подтверждена!")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🖼 Получить фото по коду", callback_data="enter_code"))

        for channel_id, invite_link in CHANNELS.items():
            try:
                chat = bot.get_chat(channel_id)
                channel_name = chat.title or "Канал"
            except:
                channel_name = "Канал"
            markup.add(types.InlineKeyboardButton(f"📢 {channel_name}", url=invite_link))

        text = "✅ Отлично! Ты подписался на все каналы!\n\n🖼 Нажми кнопку и введи код для получения фото!"

        try:
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        except Exception as e:
            if "message is not modified" in str(e):
                bot.send_message(call.message.chat.id, text, reply_markup=markup)
            else:
                raise e
    else:
        bot.answer_callback_query(call.id, "❌ Ты еще не подписался на все каналы!", show_alert=True)

        markup = get_subscription_markup(unsubscribed)
        text = "❌ **Ты еще не подписался на все каналы!**\n\n"
        text += get_unsubscribed_channels_text(unsubscribed)

        try:
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            if "message is not modified" in str(e):
                bot.send_message(
                    call.message.chat.id,
                    text,
                    reply_markup=markup,
                    parse_mode='Markdown'
                )
            else:
                raise e


# ==================== ОБРАБОТКА КОДА ====================

def process_code(message):
    user_id = message.from_user.id

    try:
        is_subscribed, subscribed, unsubscribed = check_subscription(user_id, True)
    except:
        bot.send_message(
            message.chat.id,
            "⚠️ **Ошибка проверки подписки!**\n\nПопробуйте позже.",
            parse_mode='Markdown'
        )
        return

    if not is_subscribed:
        markup = get_subscription_markup(unsubscribed)
        text = "❌ **Ты отписался от каналов!**\n\n"
        text += get_unsubscribed_channels_text(unsubscribed)

        bot.send_message(
            message.chat.id,
            text,
            reply_markup=markup,
            parse_mode='Markdown'
        )
        return

    code = message.text.strip()

    if not code.isdigit() or len(code) != 4:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔑 Попробовать снова", callback_data="enter_code"))
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

        bot.send_message(
            message.chat.id,
            "❌ **Неверный формат кода!**\n\n"
            "Код должен состоять из 4 цифр.\n"
            "Пример: `1234`",
            reply_markup=markup,
            parse_mode='Markdown'
        )
        return

    photo_data = get_photo_by_code(code)

    if not photo_data:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔑 Попробовать снова", callback_data="enter_code"))
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

        bot.send_message(
            message.chat.id,
            f"❌ **Код {code} не найден!**\n\n"
            "Проверь правильность кода или обратись к администратору.",
            reply_markup=markup,
            parse_mode='Markdown'
        )
        return

    if is_code_used_by_user(code, user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔑 Другой код", callback_data="enter_code"))
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

        bot.send_message(
            message.chat.id,
            f"❌ **Ты уже использовал код {code}!**\n\n"
            "Каждый код можно использовать только один раз.\n"
            "Попроси новый код у администратора.",
            reply_markup=markup,
            parse_mode='Markdown'
        )
        return

    try:
        file_id = photo_data['file_id']
        caption = photo_data.get('caption', '🖼 Вот твое фото!')

        bot.send_photo(
            message.chat.id,
            file_id,
            caption=f"{caption}\n\n🔑 Код: {code}\n🔥 Наслаждайся!"
        )

        mark_code_used(code, user_id)

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🖼 Еще фото", callback_data="enter_code"))
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))

        for channel_id, invite_link in CHANNELS.items():
            try:
                chat = bot.get_chat(channel_id)
                channel_name = chat.title or "Канал"
            except:
                channel_name = "Канал"
            markup.add(types.InlineKeyboardButton(f"📢 {channel_name}", url=invite_link))

        bot.send_message(
            message.chat.id,
            f"✅ **Фото получено!**\n\n"
            "Хочешь еще? Введи новый код!",
            reply_markup=markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        logging.error(f"Error sending photo: {e}")
        bot.send_message(
            message.chat.id,
            f"❌ **Ошибка при отправке фото!**\n\n"
            f"Попробуй позже или обратись к администратору.",
            parse_mode='Markdown'
        )


# ==================== АДМИН-ПАНЕЛЬ ====================

def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")
    btn2 = types.InlineKeyboardButton("👥 Подписчики", callback_data="admin_subscribers")
    btn3 = types.InlineKeyboardButton("📈 Детальная статистика", callback_data="admin_detailed")
    btn4 = types.InlineKeyboardButton("🖼 Управление фото", callback_data="admin_photos")
    btn5 = types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")
    btn6 = types.InlineKeyboardButton("🗑 Очистить статистику", callback_data="admin_clear")
    btn7 = types.InlineKeyboardButton("📋 Список каналов", callback_data="admin_channels")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)

    stats = load_stats()
    photos = get_all_photos()

    text = (
        "🔐 **Админ-панель**\n\n"
        f"📊 **Общая статистика:**\n"
        f"├ Переходов по ссылке: {stats['total_clicks']}\n"
        f"├ Подписалось: {stats['total_subscribed']}\n"
        f"└ Отписалось: {stats['total_unsubscribed']}\n\n"
        f"🖼 **Фото в базе:** {len(photos)}\n"
        f"👥 **Активных подписчиков:** {len(check_all_subscribers())}\n"
        f"📢 **Каналов в списке:** {len(CHANNELS)}\n"
        f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        "Выберите действие:"
    )

    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


# ==================== СПИСОК КАНАЛОВ (АДМИН) ====================

@bot.callback_query_handler(func=lambda call: call.data == "admin_channels")
def admin_channels_list(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    text = "📋 **Список каналов для подписки:**\n\n"

    if not CHANNELS:
        text += "⚠️ Каналы не добавлены!\n"
        text += "Добавьте каналы в список CHANNELS в коде."
    else:
        for i, (channel_id, invite_link) in enumerate(CHANNELS.items(), 1):
            try:
                chat = bot.get_chat(channel_id)
                channel_name = chat.title or "Неизвестный"
                channel_type = "Приватный" if chat.username is None else f"@{chat.username}"
                status = "✅ Доступен"
            except Exception as e:
                channel_name = "Неизвестный"
                channel_type = "ID: " + channel_id
                status = f"❌ Ошибка: {str(e)[:30]}..."

            text += f"{i}. **{channel_name}**\n"
            text += f"   ├ ID: `{channel_id}`\n"
            text += f"   ├ Тип: {channel_type}\n"
            text += f"   └ Статус: {status}\n\n"

    text += f"\nВсего каналов: {len(CHANNELS)}"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_admin"))

    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except:
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode='Markdown')


# ==================== СТАТИСТИКА (АДМИН) ====================

def show_stats(chat_id, message_id=None):
    stats = load_stats()
    subscribers = check_all_subscribers()

    text = (
        "📊 **Статистика бота**\n\n"
        f"🔗 **Переходы по ссылке:**\n"
        f"├ Всего: {stats['total_clicks']}\n"
        f"└ Уникальных: {len(stats['unique_clicks'])}\n\n"
        f"✅ **Подписки:**\n"
        f"├ Всего: {stats['total_subscribed']}\n"
        f"└ Уникальных: {len(stats['unique_subscribed'])}\n\n"
        f"❌ **Отписки:**\n"
        f"├ Всего: {stats['total_unsubscribed']}\n"
        f"└ Уникальных: {len(stats['unique_unsubscribed'])}\n\n"
        f"👥 **Активных подписчиков:** {len(subscribers)}\n"
        f"📈 **Конверсия:** {round((len(stats['unique_subscribed']) / max(len(stats['unique_clicks']), 1)) * 100, 1)}%\n"
        f"📢 **Каналов в списке:** {len(CHANNELS)}"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_admin"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        except Exception as e:
            if "message is not modified" in str(e):
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
            else:
                raise e
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


def show_subscribers(chat_id, message_id=None):
    subscribers = check_all_subscribers()

    text = "👥 **Список подписчиков:**\n\n"

    if subscribers:
        for i, user_id in enumerate(subscribers[:20], 1):
            try:
                user = bot.get_chat(user_id)
                name = user.first_name or "Неизвестный"
                text += f"{i}. {name} (ID: {user_id})\n"
            except:
                text += f"{i}. ID: {user_id}\n"

        if len(subscribers) > 20:
            text += f"\n... и еще {len(subscribers) - 20} подписчиков"

        text += f"\n\nВсего: {len(subscribers)} подписчиков"
    else:
        text += "Пока нет подписчиков 😢"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_admin"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        except Exception as e:
            if "message is not modified" in str(e):
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
            else:
                raise e
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


def show_detailed_stats(chat_id, message_id=None):
    stats = load_stats()

    text = "📈 **Детальная статистика по дням:**\n\n"

    days = sorted(stats['daily_stats'].keys(), reverse=True)[:10]

    if days:
        for day in days:
            data = stats['daily_stats'][day]
            text += f"📅 {day}:\n"
            text += f"├ Переходов: {data['clicks']}\n"
            text += f"├ Подписок: {data['subscribed']}\n"
            text += f"└ Отписок: {data['unsubscribed']}\n\n"
    else:
        text += "Данных пока нет 📭"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_admin"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        except Exception as e:
            if "message is not modified" in str(e):
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
            else:
                raise e
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


def refresh_stats(chat_id, message_id=None):
    try:
        bot.edit_message_text(
            "🔄 Обновление статистики...",
            chat_id,
            message_id
        )
    except:
        bot.send_message(chat_id, "🔄 Обновление статистики...")

    stats = load_stats()
    all_users = set(stats['unique_clicks'] + stats['unique_subscribed'] + stats['unique_unsubscribed'])

    new_subscribed = 0
    for user_id in all_users:
        try:
            is_subscribed, _, _ = check_subscription(user_id)
            if is_subscribed:
                new_subscribed += 1
        except:
            continue

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_admin"))

    bot.send_message(
        chat_id,
        f"✅ Статистика обновлена!\n\n"
        f"👥 Активных подписчиков: {new_subscribed}\n"
        f"📊 Всего в базе: {len(all_users)}",
        reply_markup=markup
    )


def broadcast_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Всем подписчикам", callback_data="broadcast_all"))
    markup.add(types.InlineKeyboardButton("📢 Активным", callback_data="broadcast_active"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_admin"))

    text = "📢 **Меню рассылки**\n\nВыберите группу для рассылки:"

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


def clear_stats(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Да, очистить", callback_data="confirm_clear"))
    markup.add(types.InlineKeyboardButton("❌ Нет, отмена", callback_data="back_admin"))

    text = "⚠️ **ВНИМАНИЕ!**\n\nВы уверены, что хотите очистить всю статистику?\nЭто действие нельзя отменить!"

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='Markdown')
        except:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')


# ==================== УПРАВЛЕНИЕ ФОТО (АДМИН) ====================

@bot.callback_query_handler(func=lambda call: call.data == "admin_photos")
def admin_photos_menu(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("➕ Добавить фото", callback_data="admin_add_photo"))
    markup.add(types.InlineKeyboardButton("📋 Список фото", callback_data="admin_list_photos"))
    markup.add(types.InlineKeyboardButton("🗑 Удалить фото", callback_data="admin_delete_photo"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_admin"))

    photos = get_all_photos()

    text = f"🖼 **Управление фото**\n\nВсего фото: {len(photos)}\n\nВыберите действие:"

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup,
                          parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == "admin_add_photo")
def admin_add_photo(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    msg = bot.send_message(
        call.message.chat.id,
        "🖼 **Добавление фото**\n\n"
        "1️⃣ **Сначала отправь фото** (как фото, не документ)\n"
        "2️⃣ Затем я попрошу ввести название (подпись) для фото\n"
        "3️⃣ После этого введи 4-значный код для этого фото\n\n"
        "❗️ Один код = одно фото!",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_first_photo)


def process_first_photo(message):
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        return

    if not message.photo:
        bot.send_message(
            message.chat.id,
            "❌ **Это не фото!**\n\nОтправь фото как изображение.",
            parse_mode='Markdown'
        )
        msg = bot.send_message(
            message.chat.id,
            "📤 Отправь фото",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_first_photo)
        return

    file_id = message.photo[-1].file_id

    temp_photo_data[user_id] = {
        'file_id': file_id
    }

    msg = bot.send_message(
        message.chat.id,
        "📝 **Введи название (подпись) для этого фото:**\n\n"
        "Например: 'Красивый закат' или 'Мой кот'\n\n"
        "Это название будет отображаться под фото.",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_photo_caption)


def process_photo_caption(message):
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        return

    caption = message.text.strip()

    if not caption:
        caption = "🖼 Фото"

    temp_photo_data[user_id]['caption'] = caption

    msg = bot.send_message(
        message.chat.id,
        f"📝 Название: **{caption}**\n\n"
        "🔑 **Теперь введи 4-значный код для этого фото:**\n\n"
        "Например: `1234`\n\nКод должен быть уникальным!",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_code_for_photo)


def process_code_for_photo(message):
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        return

    if user_id not in temp_photo_data:
        bot.send_message(message.chat.id, "❌ Ошибка! Начни заново через /start")
        return

    code = message.text.strip()

    if not code.isdigit() or len(code) != 4:
        bot.send_message(
            message.chat.id,
            "❌ **Неверный формат!**\n\nКод должен быть 4 цифры. Попробуй снова.",
            parse_mode='Markdown'
        )
        msg = bot.send_message(
            message.chat.id,
            "🔑 Введи 4-значный код:",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_code_for_photo)
        return

    photos = get_all_photos()
    if code in photos:
        bot.send_message(
            message.chat.id,
            f"❌ **Код {code} уже используется!**\n\nВведи другой код.",
            parse_mode='Markdown'
        )
        msg = bot.send_message(
            message.chat.id,
            "🔑 Введи другой 4-значный код:",
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_code_for_photo)
        return

    file_id = temp_photo_data[user_id]['file_id']
    caption = temp_photo_data[user_id]['caption']

    add_photo(code, file_id, caption)

    del temp_photo_data[user_id]

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Добавить еще", callback_data="admin_add_photo"))
    markup.add(types.InlineKeyboardButton("🔙 В управление", callback_data="admin_photos"))

    bot.send_message(
        message.chat.id,
        f"✅ **Фото добавлено!**\n\n"
        f"🔑 Код: `{code}`\n"
        f"📝 Название: {caption}\n\n"
        f"Пользователи введут код {code} и получат это фото!",
        reply_markup=markup,
        parse_mode='Markdown'
    )


@bot.callback_query_handler(func=lambda call: call.data == "admin_list_photos")
def admin_list_photos(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    photos = get_all_photos()

    if not photos:
        text = "📋 **Список фото**\n\nПока нет добавленных фото 😢"
    else:
        text = "📋 **Список фото:**\n\n"
        for code, data in list(photos.items())[:20]:
            used_count = len(data.get('used_by', []))
            caption = data.get('caption', 'Без названия')
            text += f"🔑 **{code}** - '{caption}' - использовано {used_count} раз\n"

        if len(photos) > 20:
            text += f"\n... и еще {len(photos) - 20} фото"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="admin_photos"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup,
                          parse_mode='Markdown')


@bot.callback_query_handler(func=lambda call: call.data == "admin_delete_photo")
def admin_delete_photo(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    msg = bot.send_message(
        call.message.chat.id,
        "🗑 **Удаление фото**\n\nВведи код фото, которое хочешь удалить:",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_admin_delete_photo)


def process_admin_delete_photo(message):
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        return

    code = message.text.strip()

    if delete_photo(code):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 В управление", callback_data="admin_photos"))

        bot.send_message(
            message.chat.id,
            f"✅ **Фото с кодом {code} удалено!**",
            reply_markup=markup,
            parse_mode='Markdown'
        )
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 В управление", callback_data="admin_photos"))

        bot.send_message(
            message.chat.id,
            f"❌ **Код {code} не найден!**",
            reply_markup=markup,
            parse_mode='Markdown'
        )


# ==================== ОСТАЛЬНЫЕ АДМИН-ОБРАБОТЧИКИ ====================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith('admin_') and call.data not in ['admin_photos', 'admin_add_photo',
                                                                           'admin_list_photos', 'admin_delete_photo',
                                                                           'admin_channels'])
def admin_callback(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ У вас нет прав!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    if call.data == 'admin_stats':
        show_stats(call.message.chat.id, call.message.message_id)
    elif call.data == 'admin_subscribers':
        show_subscribers(call.message.chat.id, call.message.message_id)
    elif call.data == 'admin_detailed':
        show_detailed_stats(call.message.chat.id, call.message.message_id)
    elif call.data == 'admin_refresh':
        refresh_stats(call.message.chat.id, call.message.message_id)
    elif call.data == 'admin_broadcast':
        broadcast_menu(call.message.chat.id, call.message.message_id)
    elif call.data == 'admin_clear':
        clear_stats(call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == "confirm_clear")
def confirm_clear_callback(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)
        return

    stats = {
        'total_clicks': 0,
        'unique_clicks': [],
        'total_subscribed': 0,
        'unique_subscribed': [],
        'total_unsubscribed': 0,
        'unique_unsubscribed': [],
        'daily_stats': {},
        'last_check': None
    }
    save_stats(stats)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 В админ-панель", callback_data="back_admin"))

    bot.edit_message_text(
        "✅ Статистика очищена!",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "back_admin")
def back_to_admin(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    show_admin_panel(call.message.chat.id)


# ==================== РАССЫЛКА ====================

@bot.callback_query_handler(func=lambda call: call.data.startswith('broadcast_'))
def broadcast_callback(call):
    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "⛔ Нет прав!", show_alert=True)
        return

    bot.answer_callback_query(call.id)

    broadcast_type = call.data.replace('broadcast_', '')

    msg = bot.send_message(
        call.message.chat.id,
        "📝 **Введи текст для рассылки:**\n\n"
        "Ты можешь использовать обычный текст, эмодзи и ссылки.\n"
        "Для отмены отправь /cancel",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(msg, process_broadcast, broadcast_type)


def process_broadcast(message, broadcast_type):
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ Рассылка отменена.")
        show_admin_panel(message.chat.id)
        return

    bot.send_message(message.chat.id, f"📢 Начинаю рассылку...")

    stats = load_stats()

    if broadcast_type == 'all':
        users = list(set(stats['unique_subscribed'] + stats['unique_unsubscribed']))
    else:  # active
        users = check_all_subscribers()

    if not users:
        bot.send_message(
            message.chat.id,
            "❌ Нет пользователей для рассылки!",
            parse_mode='Markdown'
        )
        show_admin_panel(message.chat.id)
        return

    sent = 0
    failed = 0

    for user_id in users:
        try:
            bot.send_message(user_id, message.text, parse_mode='Markdown')
            sent += 1
            time.sleep(0.05)
        except Exception as e:
            logging.error(f"Failed to send to {user_id}: {e}")
            failed += 1

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 В админ-панель", callback_data="back_admin"))

    bot.send_message(
        message.chat.id,
        f"✅ **Рассылка завершена!**\n\n"
        f"├ Отправлено: {sent}\n"
        f"└ Ошибок: {failed}\n"
        f"📊 Всего пользователей: {len(users)}",
        reply_markup=markup,
        parse_mode='Markdown'
    )


# ==================== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ====================

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id

    if user_id in ADMIN_IDS and message.text == '/admin':
        show_admin_panel(message.chat.id)
        return

    try:
        is_subscribed, subscribed, unsubscribed = check_subscription(user_id)
    except:
        bot.send_message(
            message.chat.id,
            "⚠️ **Ошибка подключения!**\n\nПопробуйте позже.",
            parse_mode='Markdown'
        )
        return

    if not is_subscribed:
        markup = get_subscription_markup(unsubscribed)
        text = "❌ **Подпишись на каналы и получи фото!**\n\n"
        text += get_unsubscribed_channels_text(unsubscribed)

        bot.send_message(
            message.chat.id,
            text,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🖼 Получить фото по коду", callback_data="enter_code"))

        for channel_id, invite_link in CHANNELS.items():
            try:
                chat = bot.get_chat(channel_id)
                channel_name = chat.title or "Канал"
            except:
                channel_name = "Канал"
            markup.add(types.InlineKeyboardButton(f"📢 {channel_name}", url=invite_link))

        bot.send_message(
            message.chat.id,
            "✅ Ты подписан на все каналы!\n\n🖼 Нажми кнопку и введи код для получения фото!",
            reply_markup=markup
        )


# ==================== ЗАПУСК БОТА ====================

if __name__ == "__main__":
    init_stats()
    init_photos()

    print("🤖 Бот запущен...")
    print(f"📢 Каналов в списке: {len(CHANNELS)}")
    for channel_id, invite_link in CHANNELS.items():
        try:
            chat = bot.get_chat(channel_id)
            channel_name = chat.title or "Неизвестный"
            print(f"   ├ ✅ {channel_name} (ID: {channel_id})")
        except Exception as e:
            print(f"   ├ ❌ ID: {channel_id} - Ошибка: {str(e)[:50]}")
    print(f"👑 Админы: {ADMIN_IDS}")
    print("📊 Статистика сохраняется в stats.json")
    print("🖼 Фото сохраняются в photos.json")
    print("Нажмите Ctrl+C для остановки")

    # Бесконечный цикл с переподключением
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except Exception as e:
            logging.error(f"Polling error: {e}")
            print(f"⚠️ Ошибка подключения: {e}")
            print("🔄 Переподключение через 10 секунд...")
            time.sleep(10)
            continue