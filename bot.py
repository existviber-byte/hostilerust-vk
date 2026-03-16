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
            # Проверяем состояния пользователя
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
            
            # Обработка команд с ! (для админов)
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
                elif command == 'view_tickets':
                    self.show_my_tickets(user_id)
                    return
                elif command.startswith('view_ticket_'):
                    ticket_id = int(command.replace('view_ticket_', ''))
                    self.show_ticket_details(user_id, ticket_id)
                    return
                elif command == 'admin_tickets':
                    if user_id in ADMIN_IDS:
                        self.show_admin_tickets(user_id)
                    return
                elif command.startswith('admin_reply_'):
                    if user_id in ADMIN_IDS:
                        ticket_id = int(command.replace('admin_reply_', ''))
                        self.start_admin_reply(user_id, ticket_id)
                    return
                elif command.startswith('admin_close_'):
                    if user_id in ADMIN_IDS:
                        ticket_id = int(command.replace('admin_close_', ''))
                        self.close_ticket_admin(user_id, ticket_id)
                    return
            
            # Обработка текстовых команд
            msg = message.lower().strip()
            log_error(f"Текстовая команда: '{msg}'")
            
            # Специальные команды для кнопок поддержки
            if msg in ['➕ создать тикет', 'создать тикет']:
                self.start_ticket_creation(user_id)
                return
            elif msg in ['👤 мои тикеты', 'мои тикеты']:
                self.show_my_tickets(user_id)
                return
            
            # Основные команды для всех пользователей
            if msg in ['начать', 'start', 'меню', 'привет', 'старт']:
                self.register_user(user_id)
                self.send_main_menu(user_id)
            elif msg in ['🎁 промокоды', 'промокоды']:
                self.show_promocodes(user_id)
            elif msg in ['🖥 сервера', 'сервера', 'сервер']:
                self.show_server_info(user_id)
            elif msg in ['📜 правила', 'правила']:
                self.show_rules(user_id)
            elif msg in ['🎫 поддержка', 'поддержка', 'тикеты']:
                self.show_tickets_menu(user_id)
            elif msg in ['🛒 магазин', 'магазин']:
                self.show_shop(user_id)
            elif msg in ['🔄 вайп', 'вайп']:
                self.show_wipe_info(user_id)
            
            # Админские команды
            elif user_id in ADMIN_IDS:
                if msg in ['админ', 'admin']:
                    self.show_admin_menu(user_id)
                elif msg in ['📊 статистика', 'статистика']:
                    self.show_stats(user_id)
                elif msg in ['📨 рассылка', 'рассылка']:
                    self.start_broadcast(user_id)
                elif msg in ['➕ добавить промо', 'добавить промо']:
                    self.start_add_promo(user_id)
                elif msg in ['➖ удалить промо', 'удалить промо']:
                    self.start_delete_promo(user_id)
                elif msg in ['🎫 тикеты админ', 'тикеты админ']:
                    self.show_admin_tickets(user_id)
                elif msg in ['👥 пользователи', 'пользователи']:
                    self.show_users_list(user_id)
                elif msg in ['◀️ назад', 'назад']:
                    self.send_main_menu(user_id)
            
            # Если ничего не подошло
            else:
                log_error(f"Неизвестная команда: {msg}")
                
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
        except Exception as e:
            log_error(f"❌ Ошибка отправки меню: {e}")
    
    # ========== СИСТЕМА ТИКЕТОВ ==========
    
    def show_tickets_menu(self, user_id):
        """Меню поддержки"""
        try:
            tickets = self.db.get_user_tickets(user_id)
            open_tickets = [t for t in tickets if t.status == 'open']
            closed_tickets = [t for t in tickets if t.status == 'closed']
            
            message = "🎫 ЦЕНТР ПОДДЕРЖКИ 🎫\n\n"
            message += f"📊 Всего обращений: {len(tickets)}\n"
            message += f"🟢 Открытых: {len(open_tickets)}\n"
            message += f"🔴 Закрытых: {len(closed_tickets)}\n\n"
            
            if open_tickets:
                message += "Последние открытые тикеты:\n"
                for ticket in open_tickets[:3]:
                    message += f"• #{ticket.id}: {ticket.title[:50]}...\n"
                message += "\n"
            
            self.send_message(user_id, message, self.keyboards.tickets_menu_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_tickets_menu: {e}")
    
    def show_my_tickets(self, user_id):
        """Показ всех тикетов пользователя"""
        try:
            tickets = self.db.get_user_tickets(user_id)
            
            if not tickets:
                self.send_message(
                    user_id,
                    "📭 У вас пока нет обращений в поддержку.",
                    self.keyboards.tickets_menu_keyboard()
                )
                return
            
            message = "📋 МОИ ТИКЕТЫ 📋\n\n"
            
            for ticket in tickets[-10:]:
                status_emoji = "🟢" if ticket.status == 'open' else "🔴"
                status_text = "Открыт" if ticket.status == 'open' else "Закрыт"
                
                message += f"{status_emoji} #{ticket.id} {ticket.title}\n"
                message += f"   📅 {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                message += f"   Статус: {status_text}\n"
                
                messages = self.db.get_ticket_messages(ticket.id)
                if messages:
                    last_msg = messages[-1]
                    if last_msg.is_admin:
                        message += f"   💬 Админ: {last_msg.message[:50]}...\n"
                    else:
                        message += f"   💬 Вы: {last_msg.message[:50]}...\n"
                message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            
            self.send_message(user_id, message, self.keyboards.tickets_menu_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_my_tickets: {e}")
    
    def show_ticket_details(self, user_id, ticket_id):
        """Показ деталей конкретного тикета"""
        try:
            ticket = self.db.get_ticket(ticket_id)
            
            if not ticket or ticket.user.vk_id != user_id:
                self.send_message(user_id, "❌ Тикет не найден", self.keyboards.back_keyboard())
                return
            
            messages = self.db.get_ticket_messages(ticket_id)
            
            status_emoji = "🟢" if ticket.status == 'open' else "🔴"
            message = f"{status_emoji} ТИКЕТ #{ticket_id}\n\n"
            message += f"📝 Тема: {ticket.title}\n"
            message += f"📅 Создан: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            message += f"📊 Статус: {ticket.status}\n\n"
            
            message += "Переписка:\n"
            for msg in messages:
                sender = "👤 Вы" if msg.user_id == user_id else "👑 Админ"
                time_str = msg.created_at.strftime('%H:%M %d.%m')
                message += f"{sender} [{time_str}]: {msg.message}\n"
            
            if ticket.status == 'closed':
                message += f"\n🔒 Тикет закрыт: {ticket.closed_at.strftime('%d.%m.%Y %H:%M')}"
            
            self.send_message(user_id, message, self.keyboards.back_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_ticket_details: {e}")
    
    def start_ticket_creation(self, user_id):
        """Начало создания тикета"""
        self.user_states[user_id] = 'waiting_ticket'
        self.send_message(
            user_id,
            "📝 СОЗДАНИЕ ТИКЕТА\n\n"
            "Опишите вашу проблему подробно:\n"
            "• Что случилось?\n"
            "• Когда это произошло?\n"
            "• Есть ли доказательства?\n\n"
            "Администратор ответит в ближайшее время.",
            self.keyboards.back_keyboard()
        )
    
    def create_ticket(self, user_id, description):
        """Создание нового тикета"""
        try:
            log_error(f"Создание тикета для {user_id}: {description}")
            
            ticket_id = self.db.create_ticket(user_id, description[:100])
            
            if ticket_id:
                self.db.add_ticket_message(ticket_id, user_id, description, is_admin=False)
                
                del self.user_states[user_id]
                
                self.send_message(
                    user_id,
                    f"✅ Тикет #{ticket_id} создан!\n\n"
                    f"Ваше обращение:\n{description}\n\n"
                    f"Администратор скоро ответит.",
                    self.keyboards.tickets_menu_keyboard()
                )
                
                try:
                    user_info = self.vk_session.users.get(user_ids=user_id)[0]
                    user_name = f"{user_info['first_name']} {user_info['last_name']}"
                except:
                    user_name = f"id{user_id}"
                
                admin_message = (
                    f"🎫 НОВЫЙ ТИКЕТ #{ticket_id}\n\n"
                    f"👤 От: {user_name} (@id{user_id})\n"
                    f"📝 Тема: {description[:100]}\n\n"
                    f"Полное описание:\n{description}\n\n"
                    f"Для ответа нажмите кнопку ниже:"
                )
                
                for admin_id in ADMIN_IDS:
                    keyboard = VkKeyboard(inline=True)
                    keyboard.add_button(
                        f'✏️ Ответить на тикет #{ticket_id}',
                        color=VkKeyboardColor.PRIMARY,
                        payload={'command': f'admin_reply_{ticket_id}'}
                    )
                    keyboard.add_line()
                    keyboard.add_button(
                        f'❌ Закрыть тикет',
                        color=VkKeyboardColor.NEGATIVE,
                        payload={'command': f'admin_close_{ticket_id}'}
                    )
                    
                    self.send_message(admin_id, admin_message, keyboard)
                
                log_error(f"✅ Тикет {ticket_id} создан, админы уведомлены")
            else:
                self.send_message(
                    user_id,
                    "❌ Ошибка при создании тикета",
                    self.keyboards.back_keyboard()
                )
        except Exception as e:
            log_error(f"❌ Ошибка create_ticket: {e}")
            log_error(traceback.format_exc())
            self.send_message(user_id, "❌ Ошибка при создании тикета", self.keyboards.back_keyboard())
    
    def start_admin_reply(self, admin_id, ticket_id):
        """Начало ответа на тикет (админ)"""
        session = self.db.get_session()
        try:
            from database import Ticket
            ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
            
            if not ticket:
                self.send_message(admin_id, "❌ Тикет не найден")
                return
            
            if ticket.status == 'closed':
                self.send_message(admin_id, "❌ Тикет уже закрыт")
                return
            
            messages = self.db.get_ticket_messages(ticket_id)
            history = "История тикета:\n\n"
            for msg in messages[-5:]:
                sender = "Пользователь" if not msg.is_admin else "Вы"
                history += f"{sender}: {msg.message[:100]}\n"
            
            self.user_states[admin_id] = f'ticket_reply_{ticket_id}'
            
            self.send_message(
                admin_id,
                f"✏️ Ответ на тикет #{ticket_id}\n\n"
                f"{history}\n\n"
                f"Введите ваш ответ:",
                self.keyboards.back_keyboard()
            )
        finally:
            session.close()
    
    def reply_to_ticket(self, admin_id, ticket_id, message):
        """Отправка ответа на тикет (админ)"""
        try:
            log_error(f"Админ {admin_id} отвечает на тикет {ticket_id}: {message}")
            
            session = self.db.get_session()
            try:
                from database import Ticket
                ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
                
                if not ticket:
                    self.send_message(admin_id, "❌ Тикет не найден")
                    return
                
                if ticket.status == 'closed':
                    self.send_message(admin_id, "❌ Тикет уже закрыт")
                    return
                
                user_vk_id = ticket.user.vk_id
                
                self.db.add_ticket_message(ticket_id, admin_id, message, is_admin=True)
                
                user_message = (
                    f"📬 Новый ответ по тикету #{ticket_id}\n\n"
                    f"👨‍💼 Администратор:\n{message}\n\n"
                    f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
                    f"Чтобы ответить, создайте новый тикет."
                )
                
                try:
                    self.send_message(user_vk_id, user_message, self.keyboards.tickets_menu_keyboard())
                    self.send_message(
                        admin_id,
                        f"✅ Ответ отправлен пользователю @id{user_vk_id}",
                        self.keyboards.admin_keyboard()
                    )
                    log_error(f"✅ Ответ на тикет {ticket_id} отправлен пользователю {user_vk_id}")
                except Exception as e:
                    log_error(f"❌ Ошибка отправки ответа пользователю: {e}")
                    self.send_message(admin_id, "❌ Не удалось отправить ответ пользователю")
                
            finally:
                session.close()
            
            if admin_id in self.user_states:
                del self.user_states[admin_id]
                
        except Exception as e:
            log_error(f"❌ Ошибка reply_to_ticket: {e}")
            log_error(traceback.format_exc())
            self.send_message(admin_id, "❌ Ошибка при отправке ответа")
    
    def close_ticket_admin(self, admin_id, ticket_id):
        """Закрытие тикета админом"""
        try:
            log_error(f"Админ {admin_id} закрывает тикет {ticket_id}")
            
            session = self.db.get_session()
            try:
                from database import Ticket
                ticket = session.query(Ticket).filter(Ticket.id == ticket_id).first()
                
                if not ticket:
                    self.send_message(admin_id, "❌ Тикет не найден")
                    return
                
                if ticket.status == 'closed':
                    self.send_message(admin_id, "❌ Тикет уже закрыт")
                    return
                
                user_vk_id = ticket.user.vk_id
            finally:
                session.close()
            
            if self.db.close_ticket(ticket_id):
                try:
                    self.send_message(
                        user_vk_id,
                        f"🔒 Тикет #{ticket_id} закрыт администратором\n\n"
                        f"Если у вас остались вопросы, создайте новый тикет.",
                        self.keyboards.tickets_menu_keyboard()
                    )
                except:
                    pass
                
                self.send_message(
                    admin_id,
                    f"✅ Тикет #{ticket_id} успешно закрыт",
                    self.keyboards.admin_keyboard()
                )
                log_error(f"✅ Тикет {ticket_id} закрыт")
            else:
                self.send_message(admin_id, "❌ Не удалось закрыть тикет")
                
        except Exception as e:
            log_error(f"❌ Ошибка close_ticket_admin: {e}")
    
    def show_admin_tickets(self, admin_id):
        """Показ всех открытых тикетов для админа"""
        try:
            tickets = self.db.get_open_tickets()
            
            if not tickets:
                self.send_message(
                    admin_id,
                    "✅ Нет открытых тикетов",
                    self.keyboards.admin_keyboard()
                )
                return
            
            message = "🎫 ОТКРЫТЫЕ ТИКЕТЫ 🎫\n\n"
            
            for ticket in tickets:
                messages = self.db.get_ticket_messages(ticket.id)
                last_msg = messages[-1] if messages else None
                
                message += f"#{ticket.id} от @id{ticket.user.vk_id}\n"
                message += f"📝 {ticket.title}\n"
                message += f"📅 {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                if last_msg:
                    sender = "👤" if not last_msg.is_admin else "👑"
                    message += f"💬 {sender} {last_msg.message[:100]}\n"
                message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
            
            self.send_message(admin_id, message[:4000])
            
            if len(tickets) > 0:
                keyboard = VkKeyboard(inline=True)
                for ticket in tickets[:5]:
                    keyboard.add_button(
                        f'✏️ Ответить #{ticket.id}',
                        color=VkKeyboardColor.PRIMARY,
                        payload={'command': f'admin_reply_{ticket.id}'}
                    )
                    keyboard.add_button(
                        f'❌ Закрыть #{ticket.id}',
                        color=VkKeyboardColor.NEGATIVE,
                        payload={'command': f'admin_close_{ticket.id}'}
                    )
                    keyboard.add_line()
                
                keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY,
                                  payload={'command': 'back_to_main'})
                
                self.send_message(admin_id, "Выберите действие:", keyboard)
                
        except Exception as e:
            log_error(f"❌ Ошибка show_admin_tickets: {e}")
    
    # ========== ПРОМОКОДЫ ==========
    
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
                message += f"📊 Использован: {promo.uses} раз\n"
                message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            
            message += "\n💡 Введите код промокода в чат для активации!"
            
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
    
    def start_add_promo(self, admin_id):
        """Начало добавления промокода"""
        self.user_states[admin_id] = 'waiting_promo_add'
        self.send_message(
            admin_id,
            "➕ ДОБАВЛЕНИЕ ПРОМОКОДА\n\n"
            "Введите промокод и описание в формате:\n"
            "КОД | Описание\n\n"
            "Пример: WIPE2024 | Набор ресурсов после вайпа",
            self.keyboards.back_keyboard()
        )
    
    def add_promo(self, admin_id, text):
        """Добавление промокода"""
        try:
            if '|' in text:
                code, description = text.split('|', 1)
                code = code.strip().upper()
                description = description.strip()
            else:
                code = text.strip().upper()
                description = "Промокод"
            
            self.db.add_promo(code, description)
            del self.user_states[admin_id]
            
            self.send_message(
                admin_id,
                f"✅ Промокод добавлен!\n\n"
                f"🔑 Код: {code}\n"
                f"📝 Описание: {description}",
                self.keyboards.admin_keyboard()
            )
        except Exception as e:
            log_error(f"❌ Ошибка add_promo: {e}")
            self.send_message(admin_id, f"❌ Ошибка: {e}", self.keyboards.back_keyboard())
    
    def start_delete_promo(self, admin_id):
        """Начало удаления промокода"""
        promos = self.db.get_active_promos()
        
        if not promos:
            self.send_message(
                admin_id,
                "❌ Нет активных промокодов для удаления.",
                self.keyboards.admin_keyboard()
            )
            return
        
        message = "➖ УДАЛЕНИЕ ПРОМОКОДА\n\n"
        message += "Активные промокоды:\n"
        for promo in promos:
            message += f"🔑 {promo.code} — {promo.description}\n"
        
        message += "\nВведите код промокода для удаления:"
        
        self.user_states[admin_id] = 'waiting_promo_delete'
        self.send_message(admin_id, message, self.keyboards.back_keyboard())
    
    def delete_promo(self, admin_id, code):
        """Удаление промокода"""
        code = code.strip().upper()
        
        if self.db.delete_promo(code):
            del self.user_states[admin_id]
            self.send_message(
                admin_id,
                f"✅ Промокод {code} удален!",
                self.keyboards.admin_keyboard()
            )
        else:
            self.send_message(
                admin_id,
                f"❌ Промокод {code} не найден.",
                self.keyboards.back_keyboard()
            )
    
    # ========== АДМИНСКИЕ ФУНКЦИИ ==========
    
    def show_admin_menu(self, admin_id):
        """Админ-меню"""
        self.send_message(
            admin_id,
            "👑 АДМИН-ПАНЕЛЬ 👑\n\nВыберите действие:",
            self.keyboards.admin_keyboard()
        )
    
    def show_stats(self, admin_id):
        """Статистика бота"""
        try:
            session = self.db.get_session()
            users_count = session.query(User).count()
            active_promos = session.query(PromoCode).filter_by(is_active=True).count()
            open_tickets = session.query(Ticket).filter_by(status='open').count()
            total_promo_uses = session.query(PromoUsage).count() if hasattr(self.db, 'PromoUsage') else 0
            session.close()
            
            message = "📊 СТАТИСТИКА БОТА 📊\n\n"
            message += f"👥 Пользователей: {users_count}\n"
            message += f"🎁 Активных промокодов: {active_promos}\n"
            message += f"📈 Использований промо: {total_promo_uses}\n"
            message += f"🎫 Открытых тикетов: {open_tickets}\n"
            
            self.send_message(admin_id, message, self.keyboards.admin_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_stats: {e}")
    
    def start_broadcast(self, admin_id):
        """Начало рассылки"""
        users = self.db.get_all_users()
        
        self.user_states[admin_id] = 'waiting_broadcast'
        self.send_message(
            admin_id,
            f"📨 РАССЫЛКА\n\n"
            f"Всего подписчиков: {len(users)}\n\n"
            f"Введите сообщение для рассылки (или /cancel для отмены):",
            self.keyboards.back_keyboard()
        )
    
    def send_broadcast(self, admin_id, message):
        """Отправка рассылки"""
        if message == '/cancel':
            del self.user_states[admin_id]
            self.show_admin_menu(admin_id)
            return
        
        self.send_message(
            admin_id,
            f"✅ Рассылка запущена! Ожидайте завершения...",
            self.keyboards.admin_keyboard()
        )
        
        def broadcast_thread():
            users = self.db.get_all_users()
            sent = 0
            failed = 0
            
            for user in users:
                try:
                    self.send_message(user.vk_id, f"📢 РАССЫЛКА\n\n{message}")
                    sent += 1
                except:
                    failed += 1
                
                time.sleep(0.34)
            
            self.send_message(
                admin_id,
                f"📊 РАССЫЛКА ЗАВЕРШЕНА\n\n"
                f"✅ Отправлено: {sent}\n"
                f"❌ Ошибок: {failed}",
                self.keyboards.admin_keyboard()
            )
        
        thread = threading.Thread(target=broadcast_thread, daemon=True)
        thread.start()
        del self.user_states[admin_id]
    
    def show_users_list(self, admin_id):
        """Список пользователей"""
        try:
            users = self.db.get_all_users()
            
            message = f"👥 ПОЛЬЗОВАТЕЛИ (всего: {len(users)})\n\n"
            message += "Последние 10:\n"
            
            for user in sorted(users, key=lambda x: x.registered_at, reverse=True)[:10]:
                message += f"• @id{user.vk_id} ({user.first_name} {user.last_name})\n"
                message += f"  📅 {user.registered_at.strftime('%d.%m.%Y')}\n"
            
            self.send_message(admin_id, message, self.keyboards.admin_keyboard())
        except Exception as e:
            log_error(f"❌ Ошибка show_users_list: {e}")
    
    # ========== ИНФОРМАЦИОННЫЕ ФУНКЦИИ ==========
    
    def show_server_info(self, user_id):
        """Информация о серверах"""
        info = "🖥 СЕРВЕРА HOSTILE RUST\n\n"
        info += "🔴 Ведутся технические работы\n"
        info += "Скоро информация появится!"
        self.send_message(user_id, info, self.keyboards.back_keyboard())
    
    def show_rules(self, user_id):
        """Правила сервера"""
        rules_text = "📜 ПРАВИЛА СЕРВЕРА HOSTILE RUST 📜\n\n"
        rules_text += "\n".join(RULES)
        
        if len(rules_text) > 4000:
            parts = [rules_text[i:i+4000] for i in range(0, len(rules_text), 4000)]
            for i, part in enumerate(parts):
                keyboard = None if i < len(parts)-1 else self.keyboards.back_keyboard()
                self.send_message(user_id, part, keyboard)
        else:
            self.send_message(user_id, rules_text, self.keyboards.back_keyboard())
    
    def show_shop(self, user_id):
        """Магазин"""
        message = "🛒 МАГАЗИН HOSTILE RUST 🛒\n\n"
        message += f"{SHOP_URL}\n\n"
        message += "Нажмите кнопку ниже, чтобы перейти в магазин!"
        self.send_message(user_id, message, self.keyboards.shop_keyboard())
    
    def show_wipe_info(self, user_id):
        """Информация о вайпе"""
        message = "🔄 ИНФОРМАЦИЯ О ВАЙПЕ 🔄\n\n"
        message += f"📅 Расписание: {WIPE_SCHEDULE}"
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    # ========== ЗАПУСК ==========
    
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
                        payload = None
                        try:
                            if hasattr(event, 'payload'):
                                payload = event.payload
                            elif hasattr(event, 'extra_values') and 'payload' in event.extra_values:
                                payload = event.extra_values['payload']
                        except:
                            pass
                        
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
