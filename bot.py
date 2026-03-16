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
from monitor import monitor

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
        """Информация о серверах"""
        try:
            info = monitor.format_server_info()
            self.send_message(user_id, info, self.keyboards.server_refresh_keyboard())
        except Exception as e:
            print(f"Ошибка получения информации: {e}")
            self.send_message(
                user_id,
                "❌ Не удалось получить информацию о серверах. Попробуйте позже.",
                self.keyboards.back_keyboard()
            )
    
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
                "❌ Ошиб
