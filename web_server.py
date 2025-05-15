# web_server.py
from flask import Flask, request, jsonify
import json
import os
import logging
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

DATA_DIR = "data"
ACTIONS_FILE = os.path.join(DATA_DIR, "actions.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

# --- Настройка Логгирования ---
logging.basicConfig(filename='web_server.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Вспомогательные функции ---

def load_data(filename):
    """Загружает данные из JSON-файла."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        logging.error(f"Ошибка при чтении JSON из файла: {filename}")
        return []
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при загрузке данных из {filename}: {e}")
        return []

def save_data(filename, data):
    """Сохраняет данные в JSON-файл."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)  # Создаем директорию, если ее нет
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Ошибка при записи в файл: {filename}, {e}")
        return False

def get_next_action_id():
    actions = load_data(ACTIONS_FILE)
    return max((int(action.get('id', 0)) for action in actions), default=0) + 1 if actions else 1

# --- API Endpoints ---

@app.route('/actions', methods=['GET', 'POST'])
def handle_actions():
    """Обрабатывает запросы на получение и создание акций."""
    if request.method == 'GET':
        return jsonify(load_data(ACTIONS_FILE))

    elif request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({"error": "Неверный формат JSON"}), 400

        try:
            datetime.strptime(data.get('date'), '%Y-%m-%d')
        except (ValueError, TypeError):
            return jsonify({"error": "Неверный формат даты. Используйте YYYY-MM-DD"}), 400

        data['id'] = str(get_next_action_id())
        data['ratings'] = []  # Инициализируем ratings
        actions = load_data(ACTIONS_FILE)
        actions.append(data)

        return jsonify(data), 201 if save_data(ACTIONS_FILE, actions) else (jsonify({"error": "Не удалось сохранить акцию"}), 500)

@app.route('/actions/<action_id>/register', methods=['POST'])
def register_for_action(action_id):
    """Регистрирует пользователя на акцию."""
    data = request.get_json()
    if not data or 'user_id' not in data:
        return jsonify({"error": "Не указан user_id"}), 400

    user_id = data['user_id']

    actions = load_data(ACTIONS_FILE)
    for action in actions:
        if action.get('id') == action_id:  # Use .get() to avoid KeyError
            participants = action.get('participants', [])
            if user_id not in participants:
                action['participants'] = participants + [user_id]
                if save_data(ACTIONS_FILE, actions):
                    return jsonify({"message": "Успешная регистрация"}), 200
                else:
                    return jsonify({"error": "Не удалось сохранить изменения"}), 500
            else:
                return jsonify({"message": "Вы уже зарегистрированы"}), 200
    return jsonify({"error": "Акция не найдена"}), 404

@app.route('/users', methods=['POST'])
def create_user():
    """Создает нового пользователя."""
    data = request.get_json()
    if not data or not all(key in data for key in ['user_id', 'name', 'city', 'grade', 'username']):
        return jsonify({"error": "Неверные данные пользователя"}), 400

    users = load_data(USERS_FILE)
    users.append(data)
    return jsonify(data), 201 if save_data(USERS_FILE, users) else (jsonify({"error": "Не удалось сохранить пользователя"}), 500)

@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Получает данные пользователя."""
    users = load_data(USERS_FILE)
    for user in users:
        if str(user.get('user_id')) == str(user_id):
            return jsonify(user)
    return jsonify({"error": "Пользователь не найден"}), 404

@app.route('/statistics', methods=['GET'])
def get_statistics():
    """Возвращает статистику."""
    users = load_data(USERS_FILE)
    actions = load_data(ACTIONS_FILE)
    return jsonify({"total_users": len(users), "total_actions": len(actions)})

@app.route('/users/check_username/<username>', methods=['GET'])
def check_username_availability(username):
    """Проверяет, свободен ли username."""
    users = load_data(USERS_FILE)
    for user in users:
        if user.get('username') == username:
            return jsonify({'available': False})
    return jsonify({'available': True})

@app.route('/actions/<action_id>/rate', methods=['POST'])
def rate_action(action_id):
    """Сохраняет оценку и отзыв об акции."""
    data = request.get_json()
    if not data or not all(key in data for key in ['user_id', 'rating', 'review']) or not 1 <= int(data['rating']) <= 5:
        return jsonify({"error": "Неверные данные для оценки"}), 400

    user_id = data['user_id']
    rating = int(data['rating'])
    review = data['review']

    actions = load_data(ACTIONS_FILE)
    for action in actions:
        if action.get('id') == action_id:
            action['ratings'] = action.get('ratings', []) + [{"user_id": user_id, "rating": rating, "review": review}]
            if save_data(ACTIONS_FILE, actions):
                return jsonify({"message": "Оценка сохранена"}), 200
            else:
                return jsonify({"error": "Не удалось сохранить оценку"}), 500

    return jsonify({"error": "Акция не найдена"}), 404

# --- Запуск веб-сервера ---
if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)  # Создаем директорию, если ее нет
    logging.info("Запуск веб-сервера...")
    app.run(debug=True, port=5000)