import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from datetime import datetime
import threading
import time

from config import *
from database import Database
from keyboards import Keyboards
# from monitor import monitor  # ВРЕМЕННО отключаем

class HostileRustBot:
    def __init__(self):
        self.vk = vk_api.VkApi(token=TOKEN)
        self.longpoll = VkLongPoll(self.vk)
        self.vk_session = self.vk.get_api()
        self.db = Database()
        self.keyboards = Keyboards()
        
        # Состояния пользователей
        self.user_states = {}
        
        print("✅ Бот Hostile Rust запущен!")
        print(f"👑 Администраторы: {ADMIN_IDS}")
    
    def send_message(self, user_id, message, keyboard=None, attachment=None):
        """Отправка сообщения пользователю"""
        try:
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
        except Exception as e:
            print(f"Ошибка отправки сообщения {user_id}: {e}")
    
    def send_admin_message(self, message, keyboard=None):
        """Отправка сообщения всем админам"""
        for admin_id in ADMIN_IDS:
            self.send_message(admin_id, message, keyboard)
    
    def handle_message(self, user_id, message, payload=None):
        """Обработка входящих сообщений"""
        
        # Получаем информацию о пользователе для приветствия
        if message.lower() in ['начать', 'start', 'меню', 'привет']:
            self.register_user(user_id)
            self.send_main_menu(user_id)
            return
        
        # Проверка состояний
        if user_id in self.user_states:
            state = self.user_states[user_id]
            
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
        if payload:
            command = payload.get('command')
            
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
        msg = message.lower()
        
        # Основные команды
        if msg == '🎁 промокоды':
            self.show_promocodes(user_id)
        elif msg == '🖥 сервера':
            self.show_server_info(user_id)
        elif msg == '📜 правила':
            self.show_rules(user_id)
        elif msg == '🎫 поддержка':
            self.show_tickets_menu(user_id)
        elif msg == '🛒 магазин':
            self.show_shop(user_id)
        elif msg == '🔄 вайп':
            self.show_wipe_info(user_id)
        
        # Админские команды
        elif user_id in ADMIN_IDS:
            if msg == 'админ':
                self.show_admin_menu(user_id)
            elif msg == '📊 статистика':
                self.show_stats(user_id)
            elif msg == '📨 рассылка':
                self.start_broadcast(user_id)
            elif msg == '➕ добавить промо':
                self.start_add_promo(user_id)
            elif msg == '➖ удалить промо':
                self.start_delete_promo(user_id)
            elif msg == '🎫 тикеты админ':
                self.show_admin_tickets(user_id)
            elif msg == '👥 пользователи':
                self.show_users_list(user_id)
            elif msg == '◀️ назад':
                self.send_main_menu(user_id)
        
        # Проверка на ввод промокода
        else:
            self.check_promo_code(user_id, message)
    
    def register_user(self, user_id):
        """Регистрация нового пользователя"""
        try:
            user_info = self.vk_session.users.get(user_ids=user_id)[0]
            self.db.add_user(
                user_id,
                user_info['first_name'],
                user_info['last_name']
            )
        except Exception as e:
            print(f"Ошибка регистрации: {e}")
    
    def send_main_menu(self, user_id):
        """Главное меню"""
        try:
            user_info = self.vk_session.users.get(user_ids=user_id)[0]
            name = user_info['first_name']
            
            welcome = f"🦀 **Добро пожаловать, {name}!** 🦀\n\n"
            welcome += "Это официальный бот **Hostile Rust**.\n"
            welcome += "Выберите нужный раздел в меню ниже:"
            
            self.send_message(user_id, welcome, self.keyboards.main_keyboard())
        except:
            self.send_message(user_id, "Выберите действие:", self.keyboards.main_keyboard())
    
    def show_server_info(self, user_id):
        # Временная заглушка
        info = "🖥 **СЕРВЕРА HOSTILE RUST**\n\n"
        info += "🔴 Ведутся технические работы\n"
        info += "Скоро информация появится!"
        self.send_message(user_id, info, self.keyboards.back_keyboard())
    
    def show_rules(self, user_id):
        """Правила сервера"""
        rules_text = "📜 **ПРАВИЛА СЕРВЕРА HOSTILE RUST** 📜\n\n"
        rules_text += "\n".join(RULES)
        
        # Разбиваем на части если сообщение слишком длинное
        if len(rules_text) > 4000:
            parts = [rules_text[i:i+4000] for i in range(0, len(rules_text), 4000)]
            for part in parts:
                self.send_message(user_id, part, None if parts.index(part) < len(parts)-1 else self.keyboards.back_keyboard())
        else:
            self.send_message(user_id, rules_text, self.keyboards.back_keyboard())
    
    def show_shop(self, user_id):
        """Магазин"""
        message = "🛒 **МАГАЗИН HOSTILE RUST** 🛒\n\n"
        message += "Нажмите кнопку ниже, чтобы перейти в магазин:\n"
        message += f"{SHOP_URL}\n\n"
        message += "Там вы можете приобрести:\n"
        message += "• 💎 VIP-статусы\n"
        message += "• 🔫 Наборы с оружием\n"
        message += "• 🏠 Приваты и киты\n"
        message += "• И многое другое!"
        
        self.send_message(user_id, message, self.keyboards.shop_keyboard())
    
    def show_wipe_info(self, user_id):
        """Информация о вайпе"""
        message = "🔄 **ИНФОРМАЦИЯ О ВАЙПЕ** 🔄\n\n"
        message += f"📅 **Расписание:** {WIPE_SCHEDULE}\n\n"
        message += "🔹 **Что такое вайп?**\n"
        message += "Вайп — это полное обнуление сервера: все постройки, ресурсы и прогресс игроков удаляются.\n\n"
        message += "🔹 **Зачем это нужно?**\n"
        message += "• Очистка от лагов\n"
        message += "• Равные условия для всех\n"
        message += "• Новый игровой цикл\n\n"
        message += "🔹 **Перед вайпом:**\n"
        message += "• Используйте все ресурсы\n"
        message += "• Заберите вещи из ящиков\n"
        message += "• Сделайте скриншоты своих построек\n\n"
        message += "🔹 **После вайпа:**\n"
        message += "• Все начинают с нуля\n"
        message += "• Акции и бонусы для зашедших"
        
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    def show_promocodes(self, user_id):
        """Показ промокодов"""
        promos = self.db.get_active_promos()
        
        if not promos:
            self.send_message(
                user_id,
                "😔 В данный момент нет активных промокодов.\n\nСледите за новостями!",
                self.keyboards.back_keyboard()
            )
            return
        
        message = "🎁 **ДОСТУПНЫЕ ПРОМОКОДЫ** 🎁\n\n"
        for promo in promos:
            message += f"🔑 **{promo.code}**\n"
            message += f"📝 {promo.description}\n"
            message += f"📊 Использован: {promo.uses} раз\n"
            message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        
        message += "\n💡 Просто введите код промокода в чат!"
        
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    def check_promo_code(self, user_id, text):
        """Проверка введенного промокода"""
        text = text.strip().upper()
        promos = self.db.get_active_promos()
        
        for promo in promos:
            if promo.code.upper() == text:
                success, result = self.db.use_promo(user_id, promo.code)
                
                if success:
                    self.send_message(
                        user_id,
                        f"✅ **Промокод успешно активирован!**\n\n"
                        f"🎁 {promo.description}",
                        self.keyboards.back_keyboard()
                    )
                else:
                    self.send_message(
                        user_id,
                        f"❌ {result}",
                        self.keyboards.back_keyboard()
                    )
                return
    
    def show_tickets_menu(self, user_id):
        """Меню тикетов"""
        tickets = self.db.get_user_tickets(user_id)
        
        message = "🎫 **ЦЕНТР ПОДДЕРЖКИ** 🎫\n\n"
        
        if tickets:
            message += "**Ваши последние обращения:**\n"
            for ticket in tickets[:5]:
                status_emoji = "🟢" if ticket.status == 'open' else "🔴"
                status_text = "Открыт" if ticket.status == 'open' else "Закрыт"
                message += f"{status_emoji} **#{ticket.id}** {ticket.title}\n"
                message += f"   📅 {ticket.created_at.strftime('%d.%m.%Y %H:%M')} | {status_text}\n\n"
        else:
            message += "У вас пока нет обращений в поддержку.\n\n"
        
        message += "Нажмите кнопку ниже, чтобы создать новый тикет.\n"
        message += "Опишите вашу проблему, и администратор скоро ответит!"
        
        self.send_message(user_id, message, self.keyboards.tickets_keyboard())
    
    def start_ticket_creation(self, user_id):
        """Начало создания тикета"""
        self.user_states[user_id] = 'waiting_ticket'
        self.send_message(
            user_id,
            "📝 **СОЗДАНИЕ ТИКЕТА**\n\n"
            "Опишите вашу проблему максимально подробно:\n"
            "• Что случилось?\n"
            "• Когда это произошло?\n"
            "• Есть ли скриншоты/видео?\n\n"
            "Администратор ответит вам в ближайшее время.",
            self.keyboards.back_keyboard()
        )
    
    def create_ticket(self, user_id, description):
        """Создание нового тикета"""
        ticket_id = self.db.create_ticket(user_id, description[:100])  # Обрезаем до 100 символов для заголовка
        
        if ticket_id:
            # Сохраняем первое сообщение
            self.db.add_ticket_message(ticket_id, user_id, description, is_admin=False)
            
            del self.user_states[user_id]
            
            # Уведомляем пользователя
            self.send_message(
                user_id,
                f"✅ **Тикет #{ticket_id} создан!**\n\n"
                f"Ваше обращение:\n{description}\n\n"
                f"Администратор скоро ответит. Ожидайте уведомления.",
                self.keyboards.back_keyboard()
            )
            
            # Уведомляем админов
            user_info = self.vk_session.users.get(user_ids=user_id)[0]
            admin_msg = (
                f"🎫 **НОВЫЙ ТИКЕТ #{ticket_id}**\n\n"
                f"👤 От: @id{user_id} ({user_info['first_name']} {user_info['last_name']})\n"
                f"📝 Описание:\n{description}\n\n"
                f"Для ответа напишите: !ответ {ticket_id} [сообщение]"
            )
            
            for admin_id in ADMIN_IDS:
                self.send_message(admin_id, admin_msg)
        else:
            self.send_message(
                user_id,
                "❌ Ошибка при создании тикета. Попробуйте позже.",
                self.keyboards.back_keyboard()
            )
    
    def reply_to_ticket(self, admin_id, ticket_id, message):
        """Ответ администратора на тикет"""
        ticket = self.db.get_ticket(ticket_id)
        
        if not ticket:
            self.send_message(admin_id, "❌ Тикет не найден.")
            return
        
        if ticket.status == 'closed':
            self.send_message(admin_id, "❌ Тикет уже закрыт.")
            return
        
        # Сохраняем сообщение
        self.db.add_ticket_message(ticket_id, admin_id, message, is_admin=True)
        
        # Отправляем пользователю
        user_msg = (
            f"📬 **Ответ администратора на тикет #{ticket_id}**\n\n"
            f"{message}\n\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"Чтобы ответить, создайте новый тикет или напишите в этот."
        )
        
        try:
            self.send_message(ticket.user.vk_id, user_msg)
            self.send_message(admin_id, f"✅ Ответ отправлен пользователю @id{ticket.user.vk_id}")
        except:
            self.send_message(admin_id, "❌ Не удалось отправить ответ пользователю")
    
    # АДМИНСКИЕ ФУНКЦИИ
    
    def show_admin_menu(self, admin_id):
        """Админ-меню"""
        self.send_message(
            admin_id,
            "👑 **АДМИН-ПАНЕЛЬ HOSTILE RUST** 👑\n\nВыберите действие:",
            self.keyboards.admin_keyboard()
        )
    
    def show_stats(self, admin_id):
        """Статистика бота"""
        session = self.db.get_session()
        try:
            users_count = session.query(User).count()
            active_promos = session.query(PromoCode).filter_by(is_active=True).count()
            open_tickets = session.query(Ticket).filter_by(status='open').count()
            total_promo_uses = session.query(PromoUsage).count()
            
            message = "📊 **СТАТИСТИКА БОТА** 📊\n\n"
            message += f"👥 **Пользователей:** {users_count}\n"
            message += f"🎁 **Активных промокодов:** {active_promos}\n"
            message += f"📈 **Использований промо:** {total_promo_uses}\n"
            message += f"🎫 **Открытых тикетов:** {open_tickets}\n\n"
            
            # Информация о серверах
            online = monitor.get_server_online()
            message += "🖥 **СЕРВЕРА:**\n"
            for key, server in SERVERS.items():
                message += f"• {server['name']}: {online.get(key, 'N/A')}\n"
            
            self.send_message(admin_id, message, self.keyboards.admin_keyboard())
        finally:
            session.close()
    
    def start_add_promo(self, admin_id):
        """Начало добавления промокода"""
        self.user_states[admin_id] = 'waiting_promo_add'
        self.send_message(
            admin_id,
            "➕ **ДОБАВЛЕНИЕ ПРОМОКОДА**\n\n"
            "Введите промокод и описание в формате:\n"
            "`КОД | Описание промокода`\n\n"
            "Пример: `WIPE2024 | Набор ресурсов после вайпа`",
            self.keyboards.back_keyboard()
        )
    
    def add_promo(self, admin_id, text):
        """Добавление промокода"""
        try:
            if '|' not in text:
                raise ValueError("Неверный формат. Используйте: КОД | Описание")
            
            code, description = text.split('|', 1)
            code = code.strip().upper()
            description = description.strip()
            
            self.db.add_promo(code, description)
            del self.user_states[admin_id]
            
            self.send_message(
                admin_id,
                f"✅ **Промокод добавлен!**\n\n"
                f"🔑 Код: `{code}`\n"
                f"📝 Описание: {description}",
                self.keyboards.admin_keyboard()
            )
            
        except Exception as e:
            self.send_message(
                admin_id,
                f"❌ Ошибка: {e}",
                self.keyboards.back_keyboard()
            )
    
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
        
        message = "➖ **УДАЛЕНИЕ ПРОМОКОДА**\n\n"
        message += "**Активные промокоды:**\n"
        for promo in promos:
            message += f"🔑 `{promo.code}` — {promo.description}\n"
        
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
                f"✅ Промокод `{code}` удален!",
                self.keyboards.admin_keyboard()
            )
        else:
            self.send_message(
                admin_id,
                f"❌ Промокод `{code}` не найден.",
                self.keyboards.back_keyboard()
            )
    
    def start_broadcast(self, admin_id):
        """Начало рассылки"""
        users = self.db.get_all_users()
        
        self.user_states[admin_id] = 'waiting_broadcast'
        self.send_message(
            admin_id,
            f"📨 **РАССЫЛКА**\n\n"
            f"Всего подписчиков: **{len(users)}**\n\n"
            f"Введите сообщение для рассылки (или /cancel для отмены):\n\n"
            f"Поддерживается форматирование:\n"
            f"• **жирный**\n"
            f"• *курсив*\n"
            f"• ссылки",
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
                    self.send_message(user.vk_id, message)
                    sent += 1
                except:
                    failed += 1
                    # Отписываем проблемных пользователей
                    session = self.db.get_session()
                    user.subscribed = False
                    session.commit()
                    session.close()
                
                time.sleep(0.34)  # Защита от флуда (3 запроса в секунду)
            
            self.send_message(
                admin_id,
                f"📊 **РАССЫЛКА ЗАВЕРШЕНА**\n\n"
                f"✅ Отправлено: {sent}\n"
                f"❌ Ошибок: {failed}\n"
                f"👥 Всего: {len(users)}",
                self.keyboards.admin_keyboard()
            )
        
        thread = threading.Thread(target=broadcast_thread, daemon=True)
        thread.start()
        
        del self.user_states[admin_id]
    
    def show_admin_tickets(self, admin_id):
        """Показ открытых тикетов для админа"""
        tickets = self.db.get_open_tickets()
        
        if not tickets:
            self.send_message(
                admin_id,
                "✅ Нет открытых тикетов.",
                self.keyboards.admin_keyboard()
            )
            return
        
        message = "🎫 **ОТКРЫТЫЕ ТИКЕТЫ** 🎫\n\n"
        
        for ticket in tickets:
            messages = self.db.get_ticket_messages(ticket.id)
            last_msg = messages[-1] if messages else None
            
            message += f"**#{ticket.id}** от @id{ticket.user.vk_id}\n"
            message += f"📝 **Тема:** {ticket.title}\n"
            message += f"📅 Создан: {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            if last_msg:
                message += f"💬 Последнее: {last_msg.message[:50]}...\n"
            message += f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
        message += "**Для ответа на тикет используйте:**\n"
        message += "`!ответ [ID тикета] [сообщение]`\n"
        message += "**Для закрытия:**\n"
        message += "`!закрыть [ID тикета]`"
        
        # Разбиваем если длинное
        if len(message) > 4000:
            parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for i, part in enumerate(parts):
                keyboard = self.keyboards.admin_keyboard() if i == len(parts)-1 else None
                self.send_message(admin_id, part, keyboard)
        else:
            self.send_message(admin_id, message, self.keyboards.admin_keyboard())
    
    def show_users_list(self, admin_id):
        """Список пользователей"""
        users = self.db.get_all_users()
        
        message = f"👥 **ПОЛЬЗОВАТЕЛИ** (всего: {len(users)})\n\n"
        
        # Последние 10 пользователей
        message += "**Последние 10:**\n"
        for user in sorted(users, key=lambda x: x.registered_at, reverse=True)[:10]:
            message += f"• @id{user.vk_id} ({user.first_name} {user.last_name})\n"
            message += f"  📅 {user.registered_at.strftime('%d.%m.%Y')}\n"
        
        self.send_message(admin_id, message, self.keyboards.admin_keyboard())
    
    def run(self):
        """Запуск бота"""
        for event in self.longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                try:
                    # Проверка на команды админа с ! (для ответов на тикеты)
                    if event.text.startswith('!'):
                        if event.user_id in ADMIN_IDS:
                            parts = event.text[1:].split()
                            if len(parts) >= 2:
                                cmd = parts[0].lower()
                                if cmd == 'ответ' and len(parts) >= 3:
                                    try:
                                        ticket_id = int(parts[1])
                                        reply_msg = ' '.join(parts[2:])
                                        self.reply_to_ticket(event.user_id, ticket_id, reply_msg)
                                    except:
                                        self.send_message(event.user_id, "❌ Неверный формат. Используйте: !ответ [ID] [сообщение]")
                                elif cmd == 'закрыть':
                                    try:
                                        ticket_id = int(parts[1])
                                        if self.db.close_ticket(ticket_id):
                                            self.send_message(event.user_id, f"✅ Тикет #{ticket_id} закрыт")
                                            
                                            # Уведомляем пользователя
                                            ticket = self.db.get_ticket(ticket_id)
                                            if ticket:
                                                self.send_message(
                                                    ticket.user.vk_id,
                                                    f"🔴 Ваш тикет #{ticket_id} был закрыт администратором."
                                                )
                                        else:
                                            self.send_message(event.user_id, "❌ Не удалось закрыть тикет")
                                    except:
                                        self.send_message(event.user_id, "❌ Неверный ID тикета")
                            else:
                                self.send_message(event.user_id, "❌ Неверная команда")
                        else:
                            self.send_message(event.user_id, "❌ У вас нет прав для этой команды")
                    else:
                        # Обычное сообщение
                        self.handle_message(event.user_id, event.text, event.payload)
                        
                except Exception as e:
                    print(f"Ошибка: {e}")
                    self.send_message(
                        event.user_id,
                        "❌ Произошла внутренняя ошибка. Попробуйте позже."
                    )

if __name__ == '__main__':
    bot = HostileRustBot()
    bot.run()
