# utils.py
from datetime import datetime

def format_action_message(action):
    """Форматирует информацию об акции для отправки в Telegram."""
    date_str = action.get('date', 'Дата не указана')
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%d.%m.%Y')
    except ValueError:
        formatted_date = date_str

    return (
        f"✨ *Название:* {action.get('title', 'Не указано')}\n"
        f"🌱 *Описание:* {action.get('description', 'Не указано')}\n"
        f"🗓️ *Дата:* {formatted_date}\n"
        f"📍 *Место:* {action.get('location', 'Не указано')}\n"
    )