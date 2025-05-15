# eco_action_bot.py
import telebot
import json
import requests
from telebot import types
import logging
import random
from datetime import datetime
from config import BOT_TOKEN, WEB_SERVER_URL, ADMIN_USER_ID
from utils import format_action_message
from cachetools import TTLCache

# --- Настройка Логгирования ---
logging.basicConfig(filename='eco_action_bot.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s', encoding='utf-8')

# --- Инициализация бота ---
bot = telebot.TeleBot(BOT_TOKEN)

# --- Состояния пользователя ---
user_states = {}

# --- Кеш для данных пользователей и акций (время жизни - 60 секунд) ---
user_cache = TTLCache(maxsize=128, ttl=60)
actions_cache = TTLCache(maxsize=128, ttl=60)

# --- Функции для работы с API веб-сервера ---

def api_request(method, url, json=None):
    """Общая функция для запросов к API с кешированием."""
    try:
        response = requests.request(method, url, json=json)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"API Error: {e}")
        return None

def get_actions():
    """Получает список акций с веб-сервера."""
    if 'actions' not in actions_cache:
        actions_cache['actions'] = api_request("GET", f"{WEB_SERVER_URL}/actions")
    return actions_cache['actions']

def register_for_action(user_id, action_id):
    """Регистрирует пользователя на акцию."""
    return api_request("POST", f"{WEB_SERVER_URL}/actions/{action_id}/register", json={"user_id": user_id})

def create_action(action_data):
    """Создает новую акцию."""
    actions_cache.clear()  # Сбрасываем кеш акций при создании новой
    return api_request("POST", f"{WEB_SERVER_URL}/actions", json=action_data)

def get_user(user_id):
    """Получает данные пользователя с веб-сервера."""
    if user_id not in user_cache:
        user_cache[user_id] = api_request("GET", f"{WEB_SERVER_URL}/users/{user_id}")
    return user_cache.get(user_id)

def create_user(user_data):
    """Создает нового пользователя."""
    user_cache.clear() # Сбрасываем кеш пользователей при создании нового
    return api_request("POST", f"{WEB_SERVER_URL}/users", json=user_data)

def get_statistics():
    """Получает статистику с веб-сервера"""
    return api_request("GET", f"{WEB_SERVER_URL}/statistics")

def check_username_availability(username):
    """Проверяет, свободен ли username."""
    return api_request("GET", f"{WEB_SERVER_URL}/users/check_username/{username}")

def rate_action(action_id, user_id, rating, review):
     return api_request("POST", f"{WEB_SERVER_URL}/actions/{action_id}/rate", json={'user_id': user_id, 'rating': rating, 'review': review})

# --- Обработчики команд ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Отправляет приветственное сообщение и предлагает команды."""
    user_id = message.from_user.id
    user = get_user(user_id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    item1 = types.KeyboardButton("Показать акции 🌳")
    item2 = types.KeyboardButton("Предложить акцию 💡")
    item3 = types.KeyboardButton("Мои данные 👤")
    item4 = types.KeyboardButton("Статистика 📊")
    item5 = types.KeyboardButton("Советы 💡")
    markup.add(item1, item2, item3, item4, item5)

    if user is None:
        bot.send_message(message.chat.id, "👋 Привет! Я - ваш помощник в мире экологичных инициатив.  Давайте вместе сделаем мир лучше!  Для начала, пожалуйста, введите свое имя:")
        user_states[user_id] = {"state": "waiting_for_name", "data": {}}
    else:
        bot.reply_to(message,
                     f"😊 Привет, {user.get('name', 'друг')}! Я бот, который поможет тебе заботиться об окружающей среде.\n\n"
                     "Вот что я умею:\n"
                     "/start - Показать это приветственное сообщение\n"
                     "/actions - Показать список доступных акций 🌳\n"
                     "/propose - Предложить новую акцию 💡\n"
                     "/mydetails - Просмотр личных данных 👤\n"
                     "/statistics - Получить статистику 📊\n"
                     "/tips - Получить советы 💡", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Показать акции 🌳" or message.text == "/actions")
def list_actions(message):
    """Отправляет список доступных акций."""
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        bot.reply_to(message, "🤔 Не удалось получить ваши данные. Попробуйте /start еще раз.")
        return

    user_city = user.get('city')
    if not user_city:
        bot.reply_to(message, "Город не указан. Укажите свой город, используя команду /start.")
        return

    actions = get_actions()
    if actions:
        today = datetime.now().date()
        relevant_actions = []
        for action in actions:
            action_date = valid_date(action.get('date'))
            if action.get('location') == user_city and action_date and action_date >= today:
                relevant_actions.append(action)
        if relevant_actions:
            for action in relevant_actions:
                action_message = format_action_message(action)
                bot.send_message(message.chat.id, action_message, parse_mode="Markdown")
        else:
            bot.reply_to(message, "🌱 В вашем городе пока нет запланированных акций.")
    else:
        bot.reply_to(message, "😔 Не удалось получить список акций. Попробуйте позже.")

def valid_date(date_string):
    """Проверяет и преобразует дату из строки в объект date."""
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None

@bot.message_handler(func=lambda message: message.text == "Мои данные 👤" or message.text == "/mydetails")
def my_details(message):
    """Отправляет данные пользователя."""
    user_id = message.from_user.id
    user = get_user(user_id)

    if user:
        user_details = (
            f"👤 *Имя:* {user.get('name', 'Не указано')}\n"
            f"🏘️ *Город:* {user.get('city', 'Не указано')}\n"
            f"🏫 *Класс:* {user.get('grade', 'Не указано')}\n"
            f"✉️ *Username:* {user.get('username', 'Не указано')}"
        )
        bot.send_message(message.chat.id, user_details, parse_mode="Markdown")
    else:
        bot.reply_to(message, "😔 Не удалось получить данные. Попробуйте /start еще раз.")

@bot.message_handler(func=lambda message: message.text == "Предложить акцию 💡" or message.text == "/propose")
def propose_action(message):
    user_id = message.from_user.id
    user_states[user_id] = {"state": "waiting_for_action_title", "data": {}}
    bot.send_message(message.chat.id, "✍️ Введите название акции:")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get("state") == "waiting_for_action_title", content_types=['text'])
def process_action_title(message):
    user_id = message.from_user.id
    title = message.text
    if not title.strip():
        bot.send_message(message.chat.id, "Название акции не может быть пустым. Введите название:")
        return

    user_states[user_id]["data"]["title"] = title
    bot.send_message(message.chat.id, "🗓️ Введите дату проведения акции в формате YYYY-MM-DD:")
    user_states[user_id]["state"] = "waiting_for_action_date"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get("state") == "waiting_for_action_date", content_types=['text'])
def process_action_date(message):
    user_id = message.from_user.id
    date_str = message.text
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        bot.send_message(message.chat.id, "Неверный формат даты. Пожалуйста, используйте YYYY-MM-DD.")
        return

    user_states[user_id]["data"]["date"] = date_str
    bot.send_message(message.chat.id, "📍 Введите место проведения акции:")
    user_states[user_id]["state"] = "waiting_for_action_location"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get("state") == "waiting_for_action_location", content_types=['text'])
def process_action_location(message):
    user_id = message.from_user.id
    location = message.text
    if not location.strip():
        bot.send_message(message.chat.id, "Место проведения акции не может быть пустым. Введите место:")
        return

    user_states[user_id]["data"]["location"] = location
    bot.send_message(message.chat.id, "🌱 Введите описание акции:")
    user_states[user_id]["state"] = "waiting_for_action_description"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get("state") == "waiting_for_action_description", content_types=['text'])
def process_action_description(message):
    user_id = message.from_user.id
    description = message.text
    if not description.strip():
        bot.send_message(message.chat.id, "Описание акции не может быть пустым. Введите описание:")
        return

    user_states[user_id]["data"]["description"] = description
    action_data = user_states[user_id]["data"]
    action_data["proposer_id"] = user_id

    created_action = create_action(action_data)

    if created_action:
        bot.send_message(message.chat.id, "✅ Отлично! Ваша акция успешно добавлена. Она будет рассмотрена администратором.")
        # После успешного создания акции предлагаем меню
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        item1 = types.KeyboardButton("Показать акции 🌳")
        item2 = types.KeyboardButton("Предложить акцию 💡")
        item3 = types.KeyboardButton("Мои данные 👤")
        item4 = types.KeyboardButton("Статистика 📊")
        item5 = types.KeyboardButton("Советы 💡")
        markup.add(item1, item2, item3, item4, item5)
        bot.send_message(message.chat.id, "Что дальше? 😉", reply_markup=markup)

    else:
        bot.send_message(message.chat.id, "😔 Не удалось отправить предложение. Попробуйте позже.")
    user_states.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith("register_"))
def register_callback(call):
    action_id = call.data.split("_")[1]
    user_id = call.from_user.id
    result = register_for_action(user_id, action_id)
    if result:
        bot.answer_callback_query(call.id, text="✅ Вы успешно зарегистрированы!")
    else:
        bot.answer_callback_query(call.id, text="😔 Не удалось зарегистрироваться на акцию. Попробуйте позже.")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get("state") == "waiting_for_name", content_types=['text'])
def set_name(message):
    """Устанавливает имя пользователя."""
    user_id = message.from_user.id
    name = message.text.strip()  # Remove leading/trailing spaces

    if not name:
        bot.send_message(message.chat.id, "Имя не может быть пустым. Введите имя:")
        return

    user_states[user_id]["data"]["name"] = name
    bot.send_message(message.chat.id, "🏘️ Укажите ваш город:")
    user_states[user_id]["state"] = "waiting_for_city"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get("state") == "waiting_for_city", content_types=['text'])
def set_city(message):
    """Устанавливает город пользователя."""
    user_id = message.from_user.id
    city = message.text.strip() # Remove leading/trailing spaces

    if not city:
        bot.send_message(message.chat.id, "Город не может быть пустым. Введите город:")
        return

    user_states[user_id]["data"]["city"] = city
    bot.send_message(message.chat.id, "🏫 Укажите ваш класс (например, 10А):")
    user_states[user_id]["state"] = "waiting_for_grade"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get("state") == "waiting_for_grade", content_types=['text'])
def set_grade(message):
    """Устанавливает класс пользователя."""
    user_id = message.from_user.id
    grade = message.text.strip()  # Remove leading/trailing spaces

    if not grade:
        bot.send_message(message.chat.id, "Класс не может быть пустым. Введите класс:")
        return

    user_states[user_id]["data"]["grade"] = grade
    bot.send_message(message.chat.id, "✍️ Придумайте свой username:")
    user_states[user_id]["state"] = "waiting_for_username"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get("state") == "waiting_for_username", content_types=['text'])
def set_username(message):
    """Устанавливает имя пользователя."""
    user_id = message.from_user.id
    username = message.text.strip()  # Remove leading/trailing spaces
    if not username:
        bot.send_message(message.chat.id, "Username не может быть пустым. Введите username:")
        return

    # Check username availability (using the API)
    username_check = check_username_availability(username)
    if username_check is None:
        bot.send_message(message.chat.id, "😔 Не удалось проверить username. Попробуйте позже.")
        return

    if not username_check.get('available', False):
        bot.send_message(message.chat.id, "Этот username уже занят. Придумайте другой:")
        return

    user_states[user_id]["data"]["username"] = username

    # Create the user in the database/JSON file
    user_data = user_states[user_id]["data"]
    user_data["user_id"] = user_id
    create_user(user_data)

    # Clear user state
    user_states.pop(user_id, None)

    # Respond to the user and offer the menu
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    item1 = types.KeyboardButton("Показать акции 🌳")
    item2 = types.KeyboardButton("Предложить акцию 💡")
    item3 = types.KeyboardButton("Мои данные 👤")
    item4 = types.KeyboardButton("Статистика 📊")
    item5 = types.KeyboardButton("Советы 💡")

    markup.add(item1, item2, item3, item4, item5)
    bot.send_message(message.chat.id, "🎉 Регистрация прошла успешно! Что будем делать дальше?", reply_markup=markup)

@bot.message_handler(commands=['statistics'])
def show_statistics(message):
    """Отправляет статистику с веб-сервера."""
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user:
        bot.reply_to(message, "😔 Не удалось получить ваши данные. Попробуйте /start еще раз.")
        return

    # Получаем все акции
    actions = get_actions()
    if actions is None:
        bot.reply_to(message, "😔 Не удалось получить данные об акциях. Попробуйте позже.")
        return

    # Считаем количество акций, предложенных пользователем
    user_actions_count = sum(1 for action in actions if action.get('proposer_id') == user_id)

    # Считаем количество акций в городе пользователя
    city = user.get('city')
    city_actions_count = sum(1 for action in actions if action.get('location') == city) if city else 0

    # Количество рассмотренных акций (константа)
    considered_actions = 0

    # Формируем сообщение
    msg = (
        f"📊 *Статистика*\n\n"
        f"🌱 *Ваши предложения:* {user_actions_count}\n"
        f"🏘️ *Предложения в вашем городе:* {city_actions_count}\n"
        f"✅ *Рассмотрено администратором:* {considered_actions}"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['tips'])
def send_eco_tips(message):
    """Отправляет советы по экологичному образу жизни."""
    tips = [
        "♻️ Используйте многоразовые сумки вместо пластиковых.",
        "🗑️ Сортируйте мусор и сдавайте его на переработку.",
        "💧 Экономьте воду и электроэнергию.",
        "🚲 Предпочитайте общественный транспорт или велосипед.",
        "🍎 Покупайте продукты местного производства.",
        "🍽️ Откажитесь от одноразовой посуды и упаковки.",
        "📦 Покупайте товары с минимальной упаковкой.",
        "🛠️ Ремонтируйте вещи вместо того, чтобы выбрасывать их.",
        "🤝 Поддерживайте экологически ответственные компании.",
        "🎉 Участвуйте в экологических акциях и мероприятиях.",
        "💡 Используйте энергосберегающие лампы.",
        "🌱 Собирайте дождевую воду для полива растений.",
        "🍂 Компостируйте органические отходы.",
        "🚫 Избегайте использования химических веществ в саду и огороде.",
    ]
    bot.send_message(message.chat.id, random.choice(tips))

@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    """Обрабатывает текстовые сообщения, если они не команды."""
    if message.text == "Привет":
        bot.send_message(message.chat.id, "Привет!")
    elif message.text == "Статистика 📊":
        show_statistics(message)
    elif message.text == "Советы 💡":
        send_eco_tips(message)
    elif message.text == "Показать акции 🌳":
        list_actions(message)
    elif message.text == "Предложить акцию 💡":
        propose_action(message)
    elif message.text == "Мои данные 👤":
        my_details(message)
    else:
        send_welcome(message)

# --- Запуск бота ---
if __name__ == '__main__':
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logging.critical(f"Бот упал! {e}")