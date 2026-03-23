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
    from database import Database, User, PromoCode, Ticket, TicketMessage
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
            return False
    
    def send_admin_message(self, message, keyboard=None):
        """Отправка сообщения всем админам"""
        for admin_id in ADMIN_IDS:
            self.send_message(admin_id, message, keyboard)
    
    def handle_message(self, user_id, message, payload=None):
        """Обработка входящих сообщений"""
        log_error(f"Получено сообщение от {user_id}: '{message}', payload={payload}")
        
        try:
            # ===== 1. ПРОВЕРЯЕМ PAYLOAD (КНОПКИ) =====
            if payload:
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except:
                        pass
                
                if isinstance(payload, dict):
                    command = payload.get('command')
                    log_error(f"🎯 PAYLOAD: command={command}")
                    
                    if command == 'back_to_main':
                        self.send_main_menu(user_id)
                        return
                    elif command == 'create_ticket':
                        self.start_ticket_creation(user_id)
                        return
                    elif command == 'view_tickets':
                        self.show_my_tickets(user_id)
                        return
                    elif command.startswith('view_ticket_'):
                        try:
                            ticket_id = int(command.replace('view_ticket_', ''))
                            self.show_ticket_details(user_id, ticket_id)
                        except:
                            pass
                        return
                    elif command == 'admin_tickets':
                        if user_id in ADMIN_IDS:
                            self.show_admin_tickets(user_id)
                        return
                    elif command.startswith('admin_reply_'):
                        if user_id in ADMIN_IDS:
                            try:
                                ticket_id = int(command.replace('admin_reply_', ''))
                                self.start_admin_reply(user_id, ticket_id)
                            except:
                                pass
                        return
                    elif command.startswith('admin_close_'):
                        if user_id in ADMIN_IDS:
                            try:
                                ticket_id = int(command.replace('admin_close_', ''))
                                self.close_ticket_admin(user_id, ticket_id)
                            except:
                                pass
                        return
                    elif command.startswith('copy_ip_'):
                        server_key = command.replace('copy_ip_', '')
                        self.handle_copy_ip(user_id, server_key)
                        return
            
            # ===== 2. ПРОВЕРЯЕМ СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЯ =====
            if user_id in self.user_states:
                state = self.user_states[user_id]
                log_error(f"📌 Состояние: {state}")
                
                if state == 'waiting_ticket':
                    if len(message.strip()) < 3:
                        self.send_message(user_id, "❌ Слишком короткое описание. Опишите проблему подробнее.", self.keyboards.back_keyboard())
                        return
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
                    try:
                        ticket_id = int(state.replace('ticket_reply_', ''))
                        self.reply_to_ticket(user_id, ticket_id, message)
                    except:
                        pass
                    return
            
            # ===== 3. ПРОВЕРЯЕМ КОМАНДЫ С ! (ДЛЯ АДМИНОВ) =====
            if message.startswith('!') and user_id in ADMIN_IDS:
                parts = message[1:].split()
                if len(parts) >= 2:
                    cmd = parts[0].lower()
                    if cmd == 'ответ' and len(parts) >= 3:
                        try:
                            ticket_id = int(parts[1])
                            reply_text = ' '.join(parts[2:])
                            self.user_states[user_id] = f'ticket_reply_{ticket_id}'
                            self.reply_to_ticket(user_id, ticket_id, reply_text)
                            return
                        except:
                            self.send_message(user_id, "❌ Неверный формат. Используйте: !ответ [ID] [текст]")
                    elif cmd == 'закрыть':
                        try:
                            ticket_id = int(parts[1])
                            self.close_ticket_admin(user_id, ticket_id)
                            return
                        except:
                            self.send_message(user_id, "❌ Неверный формат. Используйте: !закрыть [ID]")
                return
            
            # ===== 4. ПРОВЕРЯЕМ ТЕКСТОВЫЕ КОМАНДЫ =====
            msg = message.lower().strip()
            
            # Специальные команды для кнопок
            if msg in ['начать', 'start', 'меню', 'привет', 'старт']:
                self.register_user(user_id)
                self.send_main_menu(user_id)
                return
            elif msg in ['🎁 промокоды', 'промокоды']:
                self.show_promocodes(user_id)
                return
            elif msg in ['🖥 сервера', 'сервера', 'сервер']:
                self.show_server_info(user_id)
                return
            elif msg in ['📜 правила', 'правила']:
                self.show_rules(user_id)
                return
            elif msg in ['🎫 поддержка', 'поддержка', 'тикеты']:
                self.show_tickets_menu(user_id)
                return
            elif msg in ['🛒 магазин', 'магазин']:
                self.show_shop(user_id)
                return
            elif msg in ['🔄 вайп', 'вайп']:
                self.show_wipe_info(user_id)
                return
            elif msg in ['➕ создать тикет', 'создать тикет']:
                self.start_ticket_creation(user_id)
                return
            elif msg in ['👤 мои тикеты', 'мои тикеты']:
                self.show_my_tickets(user_id)
                return
            
            # Админские команды
            if user_id in ADMIN_IDS:
                if msg in ['админ', 'admin']:
                    self.show_admin_menu(user_id)
                    return
                elif msg in ['📊 статистика', 'статистика']:
                    self.show_stats(user_id)
                    return
                elif msg in ['📨 рассылка', 'рассылка']:
                    self.start_broadcast(user_id)
                    return
                elif msg in ['➕ добавить промо', 'добавить промо']:
                    self.start_add_promo(user_id)
                    return
                elif msg in ['➖ удалить промо', 'удалить промо']:
                    self.start_delete_promo(user_id)
                    return
                elif msg in ['🎫 тикеты админ', 'тикеты админ']:
                    self.show_admin_tickets(user_id)
                    return
                elif msg in ['👥 пользователи', 'пользователи']:
                    self.show_users_list(user_id)
                    return
                elif msg in ['◀️ назад', 'назад']:
                    self.send_main_menu(user_id)
                    return
            
            # ===== 5. ПРОВЕРЯЕМ НА ВВОД ПРОМОКОДА =====
            self.check_promo_code(user_id, message)
            
            # ===== 6. ЕСЛИ НИЧЕГО НЕ ПОДОШЛО - ОТВЕЧАЕМ МЕНЮ =====
            self.register_user(user_id)
            
            try:
                user_info = self.vk_session.users.get(user_ids=user_id)[0]
                name = user_info['first_name']
                welcome = f"🦀 Привет, {name}! 🦀\n\nЯ бот сервера Hostile Rust.\nВот что я умею:"
            except:
                welcome = "🦀 Привет! Я бот сервера Hostile Rust 🦀\n\nВот что я умею:"
            
            self.send_message(user_id, welcome, self.keyboards.main_keyboard())
                
        except Exception as e:
            log_error(f"❌ Ошибка в handle_message: {e}")
            log_error(traceback.format_exc())
            self.send_message(user_id, "❌ Произошла внутренняя ошибка. Попробуйте позже.")
    
    def register_user(self, user_id):
        """Регистрация нового пользователя"""
        try:
            existing_user = self.db.get_user(user_id)
            if existing_user:
                return existing_user
            
            log_error(f"Регистрация нового пользователя {user_id}")
            user_info = self.vk_session.users.get(user_ids=user_id)[0]
            user = self.db.add_user(user_id, user_info['first_name'], user_info['last_name'])
            log_error(f"✅ Пользователь {user_id} зарегистрирован")
            return user
        except Exception as e:
            log_error(f"❌ Ошибка регистрации: {e}")
            return None
    
    def send_main_menu(self, user_id):
        """Главное меню"""
        try:
            try:
                user_info = self.vk_session.users.get(user_ids=user_id)[0]
                name = user_info['first_name']
                welcome = f"🦀 Добро пожаловать, {name}! 🦀\n\nВыберите действие:"
            except:
                welcome = "🦀 Добро пожаловать в Hostile Rust! 🦀\n\nВыберите действие:"
            
            self.send_message(user_id, welcome, self.keyboards.main_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка отправки меню: {e}")
    
    def show_server_info(self, user_id):
        """Информация о серверах"""
        try:
            message = "🖥 СЕРВЕРА HOSTILE RUST 🖥\n\n"
            
            for key, server in SERVERS.items():
                message += f"{server['name']}\n"
                message += f"🟢 ONLINE\n"
                message += f"📌 IP: {server['ip']}\n"
                message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
            
            message += "💡 Как подключиться:\n"
            message += "1. Копируйте IP адрес выше\n"
            message += "2. В игре нажмите F1\n"
            message += "3. Введите: client.connect IP\n"
            message += "4. Нажмите Enter\n\n"
            message += "🔗 Мониторинг: https://hostilerust.gamestores.app/"
            
            keyboard = VkKeyboard(inline=True)
            for key, server in SERVERS.items():
                keyboard.add_button(f'📋 Копировать {server["name"]}', color=VkKeyboardColor.PRIMARY, payload={'command': f'copy_ip_{key}'})
                keyboard.add_line()
            keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY, payload={'command': 'back_to_main'})
            
            self.send_message(user_id, message, keyboard)
        except Exception as e:
            log_error(f"❌ Ошибка show_server_info: {e}")
    
    def handle_copy_ip(self, user_id, server_key):
        try:
            server = SERVERS.get(server_key)
            if server:
                self.send_message(user_id, f"📋 IP адрес сервера {server['name']}:\n{server['ip']}\n\nПросто выделите и копируйте текст выше!", self.keyboards.back_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка handle_copy_ip: {e}")
    
    # ========== ТИКЕТЫ ==========
    
    def show_tickets_menu(self, user_id):
        try:
            tickets = self.db.get_user_tickets(user_id)
            open_tickets = [t for t in tickets if t.status == 'open']
            closed_tickets = [t for t in tickets if t.status == 'closed']
            
            message = f"🎫 ЦЕНТР ПОДДЕРЖКИ 🎫\n\n📊 Всего обращений: {len(tickets)}\n🟢 Открытых: {len(open_tickets)}\n🔴 Закрытых: {len(closed_tickets)}\n\n"
            
            if open_tickets:
                message += "Последние открытые тикеты:\n"
                for ticket in open_tickets[:3]:
                    message += f"• #{ticket.id}: {ticket.title[:50]}...\n"
            
            self.send_message(user_id, message, self.keyboards.tickets_menu_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_tickets_menu: {e}")
    
    def show_my_tickets(self, user_id):
        try:
            tickets = self.db.get_user_tickets(user_id)
            if not tickets:
                self.send_message(user_id, "📭 У вас пока нет обращений в поддержку.", self.keyboards.tickets_menu_keyboard())
                return
            
            message = "📋 МОИ ТИКЕТЫ 📋\n\n"
            for ticket in tickets[-10:]:
                status_emoji = "🟢" if ticket.status == 'open' else "🔴"
                message += f"{status_emoji} #{ticket.id} {ticket.title}\n   📅 {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                
                messages = self.db.get_ticket_messages(ticket.id)
                if messages:
                    last = messages[-1]
                    message += f"   💬 {'Админ' if last.is_admin else 'Вы'}: {last.message[:50]}...\n"
                message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            
            self.send_message(user_id, message, self.keyboards.tickets_menu_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_my_tickets: {e}")
    
    def show_ticket_details(self, user_id, ticket_id):
        try:
            ticket = self.db.get_ticket(ticket_id)
            if not ticket or ticket.user.vk_id != user_id:
                self.send_message(user_id, "❌ Тикет не найден", self.keyboards.back_keyboard())
                return
            
            messages = self.db.get_ticket_messages(ticket_id)
            status_emoji = "🟢" if ticket.status == 'open' else "🔴"
            message = f"{status_emoji} ТИКЕТ #{ticket_id}\n\n📝 {ticket.title}\n📅 {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n\nПереписка:\n"
            
            for msg in messages:
                sender = "👤 Вы" if msg.user_id == user_id else "👑 Админ"
                message += f"{sender}: {msg.message}\n"
            
            if ticket.status == 'closed':
                message += f"\n🔒 Закрыт: {ticket.closed_at.strftime('%d.%m.%Y %H:%M')}"
            
            self.send_message(user_id, message, self.keyboards.back_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_ticket_details: {e}")
    
    def start_ticket_creation(self, user_id):
        self.user_states[user_id] = 'waiting_ticket'
        self.send_message(user_id, "📝 СОЗДАНИЕ ТИКЕТА\n\nОпишите вашу проблему подробно:\n• Что случилось?\n• Когда это произошло?\n• Есть ли доказательства?\n\nАдминистратор ответит в ближайшее время.", self.keyboards.back_keyboard())
    
    def create_ticket(self, user_id, description):
        try:
            ticket_id = self.db.create_ticket(user_id, description[:100])
            if not ticket_id:
                self.send_message(user_id, "❌ Ошибка при создании тикета", self.keyboards.back_keyboard())
                return
            
            self.db.add_ticket_message(ticket_id, user_id, description, is_admin=False)
            if user_id in self.user_states:
                del self.user_states[user_id]
            
            self.send_message(user_id, f"✅ Тикет #{ticket_id} создан!\n\nВаше обращение:\n{description}\n\nАдминистратор скоро ответит.", self.keyboards.tickets_menu_keyboard())
            
            try:
                user_info = self.vk_session.users.get(user_ids=user_id)[0]
                user_name = f"{user_info['first_name']} {user_info['last_name']}"
            except:
                user_name = f"id{user_id}"
            
            admin_message = f"🎫 НОВЫЙ ТИКЕТ #{ticket_id}\n\n👤 От: {user_name} (@id{user_id})\n📝 {description[:100]}\n\n{description}"
            
            for admin_id in ADMIN_IDS:
                keyboard = VkKeyboard(inline=True)
                keyboard.add_button(f'✏️ Ответить на тикет #{ticket_id}', color=VkKeyboardColor.PRIMARY, payload={'command': f'admin_reply_{ticket_id}'})
                keyboard.add_line()
                keyboard.add_button(f'❌ Закрыть тикет', color=VkKeyboardColor.NEGATIVE, payload={'command': f'admin_close_{ticket_id}'})
                self.send_message(admin_id, admin_message, keyboard)
        except Exception as e:
            log_error(f"❌ Ошибка create_ticket: {e}")
    
    def start_admin_reply(self, admin_id, ticket_id):
        session = self.db.get_session()
        try:
            from database import Ticket
            ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket or ticket.status == 'closed':
                self.send_message(admin_id, "❌ Тикет не найден или закрыт")
                return
            
            messages = self.db.get_ticket_messages(ticket_id)
            history = "📋 История тикета:\n\n"
            for msg in messages[-5:]:
                sender = "👤 Пользователь" if not msg.is_admin else "👑 Вы"
                history += f"{sender}: {msg.message[:100]}\n"
            
            self.user_states[admin_id] = f'ticket_reply_{ticket_id}'
            self.send_message(admin_id, f"✏️ ОТВЕТ НА ТИКЕТ #{ticket_id}\n\n{history}\n\n📝 Введите ваш ответ:", self.keyboards.back_keyboard())
        finally:
            session.close()
    
    def reply_to_ticket(self, admin_id, ticket_id, message):
        try:
            session = self.db.get_session()
            try:
                from database import Ticket
                ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket or ticket.status == 'closed':
                    self.send_message(admin_id, "❌ Тикет не найден или закрыт")
                    return
                
                user_vk_id = ticket.user.vk_id
                self.db.add_ticket_message(ticket_id, admin_id, message, is_admin=True)
                
                user_msg = f"📬 НОВЫЙ ОТВЕТ ПО ТИКЕТУ #{ticket_id}\n\n👨‍💼 Администратор:\n{message}\n\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\nЧтобы ответить, создайте новый тикет."
                self.send_message(user_vk_id, user_msg, self.keyboards.tickets_menu_keyboard())
                self.send_message(admin_id, f"✅ Ответ отправлен пользователю @id{user_vk_id}", self.keyboards.admin_keyboard())
            finally:
                session.close()
            
            if admin_id in self.user_states:
                del self.user_states[admin_id]
        except Exception as e:
            log_error(f"❌ Ошибка reply_to_ticket: {e}")
    
    def close_ticket_admin(self, admin_id, ticket_id):
        try:
            session = self.db.get_session()
            try:
                from database import Ticket
                ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
                if not ticket or ticket.status == 'closed':
                    self.send_message(admin_id, "❌ Тикет не найден или уже закрыт")
                    return
                user_vk_id = ticket.user.vk_id
            finally:
                session.close()
            
            if self.db.close_ticket(ticket_id):
                self.send_message(user_vk_id, f"🔒 Тикет #{ticket_id} закрыт администратором\n\nЕсли остались вопросы, создайте новый тикет.", self.keyboards.tickets_menu_keyboard())
                self.send_message(admin_id, f"✅ Тикет #{ticket_id} закрыт", self.keyboards.admin_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка close_ticket_admin: {e}")
    
    def show_admin_tickets(self, admin_id):
        try:
            tickets = self.db.get_open_tickets()
            if not tickets:
                self.send_message(admin_id, "✅ Нет открытых тикетов", self.keyboards.admin_keyboard())
                return
            
            message = "🎫 ОТКРЫТЫЕ ТИКЕТЫ 🎫\n\n"
            for ticket in tickets:
                message += f"#{ticket.id} от @id{ticket.user.vk_id}\n📝 {ticket.title}\n📅 {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
            
            self.send_message(admin_id, message[:4000])
            
            keyboard = VkKeyboard(inline=True)
            for ticket in tickets[:5]:
                keyboard.add_button(f'✏️ Ответить #{ticket.id}', color=VkKeyboardColor.PRIMARY, payload={'command': f'admin_reply_{ticket.id}'})
                keyboard.add_button(f'❌ Закрыть #{ticket.id}', color=VkKeyboardColor.NEGATIVE, payload={'command': f'admin_close_{ticket.id}'})
                keyboard.add_line()
            keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY, payload={'command': 'back_to_main'})
            self.send_message(admin_id, "Выберите действие:", keyboard)
        except Exception as e:
            log_error(f"❌ Ошибка show_admin_tickets: {e}")
    
    # ========== ПРОМОКОДЫ ==========
    
    def show_promocodes(self, user_id):
        try:
            promos = self.db.get_active_promos()
            if not promos:
                self.send_message(user_id, "😔 В данный момент нет активных промокодов.\n\nСледите за новостями в нашей группе!", self.keyboards.back_keyboard())
                return
            
            message = "🎁 ДОСТУПНЫЕ ПРОМОКОДЫ 🎁\n\nВведите код в магазине для активации!\n\n"
            for promo in promos:
                message += f"🔑 {promo.code}\n📝 {promo.description}\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            message += f"\n💡 Промокоды активируются в нашем магазине!\n🛒 {SHOP_URL}"
            
            self.send_message(user_id, message, self.keyboards.back_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_promocodes: {e}")
    
    def check_promo_code(self, user_id, text):
        try:
            text = text.strip().upper()
            for promo in self.db.get_active_promos():
                if promo.code.upper() == text:
                    self.send_message(user_id, f"🎁 Промокод {promo.code}\n\n{promo.description}\n\n💡 Активируйте его в нашем магазине:\n{SHOP_URL}", self.keyboards.back_keyboard())
                    return True
            return False
        except Exception as e:
            log_error(f"❌ Ошибка check_promo_code: {e}")
            return False
    
    def start_add_promo(self, admin_id):
        self.user_states[admin_id] = 'waiting_promo_add'
        self.send_message(admin_id, "➕ ДОБАВЛЕНИЕ ПРОМОКОДА\n\nВведите промокод и описание в формате:\nКОД | Описание\n\nПример: WIPE2024 | Набор ресурсов после вайпа", self.keyboards.back_keyboard())
    
    def add_promo(self, admin_id, text):
        try:
            if '|' in text:
                code, desc = text.split('|', 1)
                code = code.strip().upper()
                desc = desc.strip()
            else:
                code = text.strip().upper()
                desc = "Промокод"
            
            self.db.add_promo(code, desc)
            del self.user_states[admin_id]
            self.send_message(admin_id, f"✅ Промокод добавлен!\n\n🔑 Код: {code}\n📝 Описание: {desc}\n\nИгроки могут активировать его в магазине.", self.keyboards.admin_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка add_promo: {e}")
    
    def start_delete_promo(self, admin_id):
        promos = self.db.get_active_promos()
        if not promos:
            self.send_message(admin_id, "❌ Нет активных промокодов", self.keyboards.admin_keyboard())
            return
        
        message = "➖ УДАЛЕНИЕ ПРОМОКОДА\n\nАктивные промокоды:\n"
        for promo in promos:
            message += f"🔑 {promo.code} — {promo.description}\n"
        message += "\nВведите код для удаления:"
        
        self.user_states[admin_id] = 'waiting_promo_delete'
        self.send_message(admin_id, message, self.keyboards.back_keyboard())
    
    def delete_promo(self, admin_id, code):
        code = code.strip().upper()
        if self.db.delete_promo(code):
            del self.user_states[admin_id]
            self.send_message(admin_id, f"✅ Промокод {code} удален!", self.keyboards.admin_keyboard())
        else:
            self.send_message(admin_id, f"❌ Промокод {code} не найден.", self.keyboards.back_keyboard())
    
    # ========== АДМИНСКИЕ ФУНКЦИИ ==========
    
    def show_admin_menu(self, admin_id):
        self.send_message(admin_id, "👑 АДМИН-ПАНЕЛЬ 👑\n\nВыберите действие:", self.keyboards.admin_keyboard())
    
    def show_stats(self, admin_id):
        try:
            session = self.db.get_session()
            users = session.query(User).count()
            promos = session.query(PromoCode).filter_by(is_active=True).count()
            tickets = session.query(Ticket).filter_by(status='open').count()
            session.close()
            
            message = f"📊 СТАТИСТИКА БОТА 📊\n\n👥 Пользователей: {users}\n🎁 Активных промокодов: {promos}\n🎫 Открытых тикетов: {tickets}"
            self.send_message(admin_id, message, self.keyboards.admin_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_stats: {e}")
    
    def start_broadcast(self, admin_id):
        users = self.db.get_all_users()
        self.user_states[admin_id] = 'waiting_broadcast'
        self.send_message(admin_id, f"📨 РАССЫЛКА\n\nВсего подписчиков: {len(users)}\n\nВведите сообщение (или /cancel):", self.keyboards.back_keyboard())
    
    def send_broadcast(self, admin_id, message):
        if message == '/cancel':
            del self.user_states[admin_id]
            self.show_admin_menu(admin_id)
            return
        
        self.send_message(admin_id, "✅ Рассылка запущена!")
        
        def broadcast_thread():
            users = self.db.get_all_users()
            sent = 0
            for user in users:
                try:
                    self.send_message(user.vk_id, f"📢 РАССЫЛКА\n\n{message}")
                    sent += 1
                except:
                    pass
                time.sleep(0.34)
            self.send_message(admin_id, f"📊 РАССЫЛКА ЗАВЕРШЕНА\n\n✅ Отправлено: {sent}", self.keyboards.admin_keyboard())
        
        threading.Thread(target=broadcast_thread, daemon=True).start()
        del self.user_states[admin_id]
    
    def show_users_list(self, admin_id):
        try:
            users = self.db.get_all_users()
            message = f"👥 ПОЛЬЗОВАТЕЛИ (всего: {len(users)})\n\nПоследние 10:\n"
            for user in sorted(users, key=lambda x: x.registered_at, reverse=True)[:10]:
                message += f"• @id{user.vk_id} ({user.first_name} {user.last_name})\n  📅 {user.registered_at.strftime('%d.%m.%Y')}\n"
            self.send_message(admin_id, message, self.keyboards.admin_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_users_list: {e}")
    
    # ========== ИНФОРМАЦИОННЫЕ ФУНКЦИИ ==========
    
    def show_rules(self, user_id):
        rules_text = "📜 ПРАВИЛА СЕРВЕРА HOSTILE RUST 📜\n\n" + "\n".join(RULES)
        if len(rules_text) > 4000:
            for i in range(0, len(rules_text), 4000):
                self.send_message(user_id, rules_text[i:i+4000], self.keyboards.back_keyboard() if i+4000 >= len(rules_text) else None)
        else:
            self.send_message(user_id, rules_text, self.keyboards.back_keyboard())
    
    def show_shop(self, user_id):
        self.send_message(user_id, f"🛒 МАГАЗИН HOSTILE RUST 🛒\n\n{SHOP_URL}\n\nНажмите кнопку ниже!", self.keyboards.shop_keyboard())
    
    def show_wipe_info(self, user_id):
        self.send_message(user_id, f"🔄 ИНФОРМАЦИЯ О ВАЙПЕ 🔄\n\n📅 Расписание: {WIPE_SCHEDULE}", self.keyboards.back_keyboard())
    
    # ========== ЗАПУСК ==========
    
    def run(self):
        log_error("\n" + "="*50)
        log_error("✅ БОТ ЗАПУЩЕН! Отвечает на ЛЮБОЕ сообщение меню")
        log_error("="*50 + "\n")
        
        while True:
            try:
                for event in self.longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                        payload = None
                        try:
                            if hasattr(event, 'payload'):
                                payload = event.payload
                        except:
                            pass
                        self.handle_message(event.user_id, event.text, payload)
            except Exception as e:
                log_error(f"❌ Ошибка: {e}")
                time.sleep(5)

if __name__ == '__main__':
    try:
        bot = HostileRustBot()
        bot.run()
    except Exception as e:
        log_error(f"❌ ФАТАЛЬНАЯ ОШИБКА: {e}")
