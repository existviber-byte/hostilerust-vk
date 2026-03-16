import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from datetime import datetime
import threading
import time
import sys
import os
import traceback
import json

# ==== ПРОСТОЕ ЛОГИРОВАНИЕ В ФАЙЛ ====
log_file = open('bot_errors.log', 'a', encoding='utf-8')
def log_error(text):
    """Запись ошибки в файл"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_file.write(f"[{timestamp}] {text}\n")
    log_file.flush()
    print(text)

log_error("="*50)
log_error("ЗАПУСК БОТА HOSTILE RUST")
log_error("="*50)

try:
    from config import *
    log_error(f"✅ config загружен: TOKEN={'есть' if TOKEN else 'НЕТ'}, GROUP_ID={GROUP_ID}")
except Exception as e:
    log_error(f"❌ Ошибка загрузки config: {e}")
    log_error(traceback.format_exc())
    sys.exit(1)

try:
    from database import Database
    log_error("✅ database загружен")
except Exception as e:
    log_error(f"❌ Ошибка загрузки database: {e}")
    log_error(traceback.format_exc())

try:
    from keyboards import Keyboards
    log_error("✅ keyboards загружен")
except Exception as e:
    log_error(f"❌ Ошибка загрузки keyboards: {e}")
    log_error(traceback.format_exc())

class HostileRustBot:
    def __init__(self):
        try:
            log_error("Инициализация бота...")
            self.vk = vk_api.VkApi(token=TOKEN)
            self.longpoll = VkLongPoll(self.vk)
            self.vk_session = self.vk.get_api()
            
            # Проверка подключения
            test = self.vk_session.users.get()
            log_error(f"✅ Подключение к VK API успешно")
            
            self.db = Database()
            log_error("✅ База данных инициализирована")
            
            self.keyboards = Keyboards()
            log_error("✅ Клавиатуры загружены")
            
            self.user_states = {}
            
            log_error(f"✅ Бот Hostile Rust запущен!")
            log_error(f"👑 Администраторы: {ADMIN_IDS}")
            
        except Exception as e:
            log_error(f"❌ Ошибка инициализации: {e}")
            log_error(traceback.format_exc())
            raise
    
    def send_message(self, user_id, message, keyboard=None, attachment=None):
        """Отправка сообщения пользователю"""
        try:
            log_error(f"Отправка сообщения {user_id}: {message[:50]}...")
            
            params = {
                'user_id': user_id,
                'message': message,
                'random_id': get_random_id(),
                'dont_parse_links': 1
            }
            
            if keyboard:
                params['keyboard'] = keyboard.get_keyboard()
            
            if attachment:
                params['attachment'] = attachment
            
            self.vk_session.messages.send(**params)
            log_error(f"✅ Сообщение отправлено {user_id}")
            return True
        except Exception as e:
            log_error(f"❌ Ошибка отправки сообщения {user_id}: {e}")
            log_error(traceback.format_exc())
            return False
    
    def send_admin_message(self, message, keyboard=None):
        """Отправка сообщения всем админам"""
        for admin_id in ADMIN_IDS:
            self.send_message(admin_id, message, keyboard)
    
    def handle_message(self, user_id, message, payload=None):
        """Обработка входящих сообщений"""
        log_error(f"Получено сообщение от {user_id}: '{message}', payload={payload}")
        
        try:
            # Получаем информацию о пользователе для приветствия
            if message.lower() in ['начать', 'start', 'меню', 'привет', 'старт']:
                log_error("Команда 'начать'")
                self.register_user(user_id)
                self.send_main_menu(user_id)
                return
            
            # Проверка состояний
            if user_id in self.user_states:
                state = self.user_states[user_id]
                log_error(f"Состояние пользователя: {state}")
                
                if state == 'waiting_ticket':
                    self.create_ticket(user_id, message)
                    return
                elif state == 'waiting_promo_add':
                    self.add_promo(user_id, message)
                    return
                elif state == 'waiting_promo_delete':
                    self.delete_promo(user_id, message)
                    return
                elif state == 'waiting_broadcast':
                    self.send_broadcast(user_id, message)
                    return
                elif state.startswith('ticket_reply_'):
                    ticket_id = int(state.replace('ticket_reply_', ''))
                    self.reply_to_ticket(user_id, ticket_id, message)
                    return
            
            # Обработка payload (кнопок)
            if payload and isinstance(payload, dict):
                command = payload.get('command')
                log_error(f"Payload команда: {command}")
                
                if command == 'back_to_main':
                    self.send_main_menu(user_id)
                    return
                elif command == 'create_ticket':
                    self.start_ticket_creation(user_id)
                    return
                elif command == 'refresh_servers':
                    self.show_server_info(user_id)
                    return
            
            # Обработка текстовых команд
            msg = message.lower().strip()
            log_error(f"Текстовая команда: '{msg}'")
            
            # Основные команды
            if msg == '🎁 промокоды' or msg == 'промокоды':
                self.show_promocodes(user_id)
            elif msg == '🖥 сервера' or msg == 'сервера' or msg == 'сервер':
                self.show_server_info(user_id)
            elif msg == '📜 правила' or msg == 'правила':
                self.show_rules(user_id)
            elif msg == '🎫 поддержка' or msg == 'поддержка' or msg == 'тикеты':
                self.show_tickets_menu(user_id)
            elif msg == '🛒 магазин' or msg == 'магазин':
                self.show_shop(user_id)
            elif msg == '🔄 вайп' or msg == 'вайп':
                self.show_wipe_info(user_id)
            
            # Админские команды
            elif user_id in ADMIN_IDS:
                if msg == 'админ':
                    self.show_admin_menu(user_id)
                elif msg == '📊 статистика' or msg == 'статистика':
                    self.show_stats(user_id)
                elif msg == '📨 рассылка' or msg == 'рассылка':
                    self.start_broadcast(user_id)
                elif msg == '➕ добавить промо' or msg == 'добавить промо':
                    self.start_add_promo(user_id)
                elif msg == '➖ удалить промо' or msg == 'удалить промо':
                    self.start_delete_promo(user_id)
                elif msg == '🎫 тикеты админ' or msg == 'тикеты админ':
                    self.show_admin_tickets(user_id)
                elif msg == '👥 пользователи' or msg == 'пользователи':
                    self.show_users_list(user_id)
                elif msg == '◀️ назад' or msg == 'назад':
                    self.send_main_menu(user_id)
            
            # Проверка на ввод промокода
            else:
                self.check_promo_code(user_id, message)
                
        except Exception as e:
            log_error(f"❌ Ошибка в handle_message: {e}")
            log_error(traceback.format_exc())
            self.send_message(
                user_id,
                "❌ Произошла внутренняя ошибка. Попробуйте позже."
            )
    
    def register_user(self, user_id):
        """Регистрация нового пользователя"""
        try:
            log_error(f"Регистрация пользователя {user_id}")
            user_info = self.vk_session.users.get(user_ids=user_id)[0]
            self.db.add_user(
                user_id,
                user_info['first_name'],
                user_info['last_name']
            )
            log_error(f"✅ Пользователь {user_id} зарегистрирован")
        except Exception as e:
            log_error(f"❌ Ошибка регистрации: {e}")
    
    def send_main_menu(self, user_id):
        """Главное меню"""
        try:
            log_error(f"Отправка главного меню {user_id}")
            
            try:
                user_info = self.vk_session.users.get(user_ids=user_id)[0]
                name = user_info['first_name']
                welcome = f"🦀 Добро пожаловать, {name}! 🦀\n\n"
                welcome += "Выберите действие:"
            except:
                welcome = "🦀 Добро пожаловать в Hostile Rust! 🦀\n\nВыберите действие:"
            
            self.send_message(user_id, welcome, self.keyboards.main_keyboard())
            log_error(f"✅ Меню отправлено {user_id}")
        except Exception as e:
            log_error(f"❌ Ошибка отправки меню: {e}")
            self.send_message(user_id, "Выберите действие:", self.keyboards.main_keyboard())
    
    def show_server_info(self, user_id):
        """Временная заглушка для информации о серверах"""
        try:
            info = "🖥 СЕРВЕРА HOSTILE RUST\n\n"
            info += "🔴 Ведутся технические работы\n"
            info += "Скоро информация появится!"
            self.send_message(user_id, info, self.keyboards.back_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_server_info: {e}")
    
    def show_rules(self, user_id):
        """Правила сервера"""
        try:
            rules_text = "📜 ПРАВИЛА СЕРВЕРА HOSTILE RUST 📜\n\n"
            rules_text += "\n".join(RULES)
            
            if len(rules_text) > 4000:
                parts = [rules_text[i:i+4000] for i in range(0, len(rules_text), 4000)]
                for i, part in enumerate(parts):
                    keyboard = None if i < len(parts)-1 else self.keyboards.back_keyboard()
                    self.send_message(user_id, part, keyboard)
            else:
                self.send_message(user_id, rules_text, self.keyboards.back_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_rules: {e}")
    
    def show_shop(self, user_id):
        """Магазин"""
        try:
            message = "🛒 МАГАЗИН HOSTILE RUST 🛒\n\n"
            message += f"{SHOP_URL}\n\n"
            message += "Нажмите кнопку ниже, чтобы перейти в магазин!"
            self.send_message(user_id, message, self.keyboards.shop_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_shop: {e}")
    
    def show_wipe_info(self, user_id):
        """Информация о вайпе"""
        try:
            message = "🔄 ИНФОРМАЦИЯ О ВАЙПЕ 🔄\n\n"
            message += f"📅 Расписание: {WIPE_SCHEDULE}"
            self.send_message(user_id, message, self.keyboards.back_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_wipe_info: {e}")
    
    def show_promocodes(self, user_id):
        """Показ промокодов"""
        try:
            promos = self.db.get_active_promos()
            
            if not promos:
                self.send_message(
                    user_id,
                    "😔 В данный момент нет активных промокодов.",
                    self.keyboards.back_keyboard()
                )
                return
            
            message = "🎁 ДОСТУПНЫЕ ПРОМОКОДЫ 🎁\n\n"
            for promo in promos:
                message += f"🔑 {promo.code}\n"
                message += f"📝 {promo.description}\n"
                message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            
            message += "\n💡 Введите код промокода в чат!"
            
            self.send_message(user_id, message, self.keyboards.back_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_promocodes: {e}")
    
    def check_promo_code(self, user_id, text):
        """Проверка введенного промокода"""
        try:
            text = text.strip().upper()
            promos = self.db.get_active_promos()
            
            for promo in promos:
                if promo.code.upper() == text:
                    success, result = self.db.use_promo(user_id, promo.code)
                    
                    if success:
                        self.send_message(
                            user_id,
                            f"✅ Промокод активирован!\n\n{result}",
                            self.keyboards.back_keyboard()
                        )
                    else:
                        self.send_message(
                            user_id,
                            f"❌ {result}",
                            self.keyboards.back_keyboard()
                        )
                    return
        except Exception as e:
            log_error(f"❌ Ошибка check_promo_code: {e}")
    
    def show_tickets_menu(self, user_id):
        """Меню тикетов"""
        try:
            message = "🎫 ЦЕНТР ПОДДЕРЖКИ 🎫\n\n"
            message += "Нажмите кнопку ниже, чтобы создать тикет."
            self.send_message(user_id, message, self.keyboards.tickets_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_tickets_menu: {e}")
    
    def start_ticket_creation(self, user_id):
        """Начало создания тикета"""
        self.user_states[user_id] = 'waiting_ticket'
        self.send_message(
            user_id,
            "📝 Опишите вашу проблему:",
            self.keyboards.back_keyboard()
        )
    
    def create_ticket(self, user_id, description):
        """Создание нового тикета"""
        try:
            ticket_id = self.db.create_ticket(user_id, description[:100])
            
            if ticket_id:
                self.db.add_ticket_message(ticket_id, user_id, description, is_admin=False)
                del self.user_states[user_id]
                
                self.send_message(
                    user_id,
                    f"✅ Тикет #{ticket_id} создан!",
                    self.keyboards.back_keyboard()
                )
                
                # Уведомляем админов
                for admin_id in ADMIN_IDS:
                    self.send_message(
                        admin_id,
                        f"🎫 Новый тикет #{ticket_id} от @id{user_id}"
                    )
        except Exception as e:
            log_error(f"❌ Ошибка create_ticket: {e}")
    
    # АДМИНСКИЕ ФУНКЦИИ
    
    def show_admin_menu(self, admin_id):
        self.send_message(admin_id, "👑 АДМИН-ПАНЕЛЬ", self.keyboards.admin_keyboard())
    
    def show_stats(self, admin_id):
        self.send_message(admin_id, "📊 Статистика временно недоступна", self.keyboards.admin_keyboard())
    
    def start_add_promo(self, admin_id):
        self.user_states[admin_id] = 'waiting_promo_add'
        self.send_message(admin_id, "Введите промокод:", self.keyboards.back_keyboard())
    
    def add_promo(self, admin_id, text):
        self.db.add_promo(text.upper(), "Промокод")
        del self.user_states[admin_id]
        self.send_message(admin_id, f"✅ Промокод {text} добавлен", self.keyboards.admin_keyboard())
    
    def start_delete_promo(self, admin_id):
        self.user_states[admin_id] = 'waiting_promo_delete'
        self.send_message(admin_id, "Введите код для удаления:", self.keyboards.back_keyboard())
    
    def delete_promo(self, admin_id, code):
        if self.db.delete_promo(code.upper()):
            self.send_message(admin_id, f"✅ Промокод {code} удален", self.keyboards.admin_keyboard())
        else:
            self.send_message(admin_id, "❌ Промокод не найден", self.keyboards.back_keyboard())
        del self.user_states[admin_id]
    
    def start_broadcast(self, admin_id):
        self.user_states[admin_id] = 'waiting_broadcast'
        self.send_message(admin_id, "Введите сообщение для рассылки:", self.keyboards.back_keyboard())
    
    def send_broadcast(self, admin_id, message):
        if message == '/cancel':
            del self.user_states[admin_id]
            self.show_admin_menu(admin_id)
            return
        
        self.send_message(admin_id, "✅ Рассылка запущена")
        del self.user_states[admin_id]
    
    def show_admin_tickets(self, admin_id):
        self.send_message(admin_id, "🎫 Открытых тикетов нет", self.keyboards.admin_keyboard())
    
    def show_users_list(self, admin_id):
        users = self.db.get_all_users()
        self.send_message(admin_id, f"👥 Всего пользователей: {len(users)}", self.keyboards.admin_keyboard())
    
    def run(self):
        """Запуск бота"""
        log_error("\n" + "="*50)
        log_error("✅ БОТ УСПЕШНО ЗАПУЩЕН!")
        log_error("📝 Отправьте 'начать' в сообщения группы")
        log_error("📁 Лог ошибок: bot_errors.log")
        log_error("="*50 + "\n")
        
        while True:
            try:
                for event in self.longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                        # Пробуем получить payload разными способами
                        payload = None
                        try:
                            # Способ 1: прямой атрибут
                            if hasattr(event, 'payload'):
                                payload = event.payload
                            # Способ 2: через extra_values
                            elif hasattr(event, 'extra_values') and 'payload' in event.extra_values:
                                payload = event.extra_values['payload']
                            # Способ 3: парсим из текста если это JSON
                            elif event.text and event.text.startswith('{'):
                                try:
                                    payload_data = json.loads(event.text)
                                    if isinstance(payload_data, dict):
                                        payload = payload_data
                                        # Если это был payload, то текст не нужен
                                        event.text = ''
                                except:
                                    pass
                        except:
                            pass
                        
                        log_error(f"Событие: user={event.user_id}, text='{event.text}', payload={payload}")
                        self.handle_message(event.user_id, event.text, payload)
            except Exception as e:
                log_error(f"❌ Ошибка в главном цикле: {e}")
                log_error(traceback.format_exc())
                time.sleep(5)

if __name__ == '__main__':
    try:
        bot = HostileRustBot()
        bot.run()
    except Exception as e:
        log_error(f"❌ ФАТАЛЬНАЯ ОШИБКА: {e}")
        log_error(traceback.format_exc())
