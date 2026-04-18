import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from datetime import datetime, timedelta
import json
import logging
import random
import threading
import time
from pathlib import Path

from config import *
from database import Database, User, PromoCode, PromoUsage, Ticket
from keyboards import Keyboards

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('vk_bot.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("vk_bot")

class HostileRustVKBot:
    def __init__(self):
        log.info("="*50)
        log.info("ЗАПУСК VK БОТА HOSTILE RUST")
        log.info("="*50)
        
        # База данных
        self.db = Database()
        
        # VK API
        self.vk = vk_api.VkApi(token=TOKEN)
        self.longpoll = VkLongPoll(self.vk)
        self.vk_api = self.vk.get_api()
        
        # Клавиатуры
        self.keyboards = Keyboards()
        
        # Состояния пользователей
        self.user_states = {}
        
        log.info("✅ VK Бот Hostile Rust запущен!")
        log.info(f"👑 Администраторы: {ADMIN_IDS}")
    
    def send_message(self, user_id, message, keyboard=None, attachment=None):
        """Отправка сообщения"""
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
            
            self.vk_api.messages.send(**params)
            return True
        except Exception as e:
            log.error(f"❌ Ошибка отправки сообщения {user_id}: {e}")
            return False
    
    def send_admin_message(self, message, keyboard=None):
        """Отправка всем админам"""
        for admin_id in ADMIN_IDS:
            self.send_message(admin_id, message, keyboard)
    
    def handle_message(self, user_id, text, payload=None):
        """Обработка сообщений"""
        log.info(f"📨 Сообщение от {user_id}: {text[:50] if text else ''}")
        
        # Регистрируем пользователя
        try:
            user_info = self.vk_api.users.get(user_ids=user_id)[0]
            first_name = user_info.get('first_name', '')
            last_name = user_info.get('last_name', '')
            self.db.add_user(user_id, first_name, last_name)
        except Exception as e:
            log.error(f"❌ Ошибка регистрации пользователя: {e}")
        
        # Обработка payload (inline кнопки)
        if payload:
            try:
                payload = json.loads(payload) if isinstance(payload, str) else payload
                command = payload.get('command', '')
                
                if command == 'back_to_main':
                    self.show_main_menu(user_id)
                    return
                elif command.startswith('copy_ip_'):
                    server = command.replace('copy_ip_', '')
                    self.send_server_ip(user_id, server)
                    return
                elif command.startswith('ticket_answer_'):
                    ticket_id = int(command.replace('ticket_answer_', ''))
                    self.start_ticket_answer(user_id, ticket_id)
                    return
                elif command == 'admin_tickets':
                    self.show_admin_tickets(user_id)
                    return
                elif command.startswith('confirm_delete_promo_'):
                    code = command.replace('confirm_delete_promo_', '')
                    self.delete_promo(user_id, code)
                    return
            except Exception as e:
                log.error(f"❌ Ошибка обработки payload: {e}")
        
        # Обработка состояний
        if user_id in self.user_states:
            state = self.user_states[user_id]
            
            if state == 'waiting_ticket':
                self.create_ticket(user_id, text)
                return
            elif state == 'waiting_promo_add':
                self.add_promo(user_id, text)
                return
            elif state == 'waiting_broadcast':
                self.send_broadcast(user_id, text)
                return
            elif state.startswith('ticket_reply_'):
                ticket_id = int(state.replace('ticket_reply_', ''))
                self.reply_to_ticket(user_id, ticket_id, text)
                return
        
        # Обработка текстовых команд
        if not text:
            return
        
        text_lower = text.lower().strip()
        
        if text_lower in ['начать', 'start', 'меню', 'привет']:
            self.show_main_menu(user_id)
        elif text_lower in ['🎁 промокоды', 'промокоды', 'промокод']:
            self.show_promocodes(user_id)
        elif text_lower in ['🎮 сервера', 'сервера', 'сервер']:
            self.show_servers(user_id)
        elif text_lower in ['📜 правила', 'правила']:
            self.show_rules(user_id)
        elif text_lower in ['🎫 поддержка', 'поддержка', 'тикеты']:
            self.show_tickets_menu(user_id)
        elif text_lower in ['🛒 магазин', 'магазин']:
            self.show_shop(user_id)
        elif text_lower in ['⏳ до вайпа', 'вайп']:
            self.show_wipe_info(user_id)
        elif text_lower in ['📋 ip серверов', 'ip']:
            self.show_server_ips(user_id)
        elif text_lower in ['➕ создать тикет']:
            self.start_ticket_creation(user_id)
        elif text_lower in ['📋 мои тикеты']:
            self.show_my_tickets(user_id)
        elif text_lower in ['◀️ назад в меню', 'назад']:
            self.show_main_menu(user_id)
        
        # Админские команды
        elif user_id in ADMIN_IDS:
            if text_lower in ['админ', 'admin']:
                self.show_admin_menu(user_id)
            elif text_lower in ['➕ добавить промо']:
                self.start_add_promo(user_id)
            elif text_lower in ['➖ удалить промо']:
                self.show_promo_list_for_delete(user_id)
            elif text_lower in ['📋 список промокодов']:
                self.show_promo_list(user_id)
            elif text_lower in ['👥 пользователи']:
                self.show_users_list(user_id)
            elif text_lower in ['📊 статистика']:
                self.show_stats(user_id)
            elif text_lower in ['📩 тикеты']:
                self.show_admin_tickets(user_id)
            elif text_lower in ['📢 рассылка']:
                self.start_broadcast(user_id)
        
        # Проверка на ввод промокода
        elif self.check_promo_code(user_id, text):
            pass
        else:
            self.show_main_menu(user_id)
    
    def show_main_menu(self, user_id):
        """Главное меню"""
        try:
            user_info = self.vk_api.users.get(user_ids=user_id)[0]
            name = user_info['first_name']
            welcome = f"🔥 Привет, {name}!\n\n🎮 Добро пожаловать в Hostile Rust!\nВыберите действие:"
        except:
            welcome = "🔥 Добро пожаловать в Hostile Rust!\n\nВыберите действие:"
        
        self.send_message(user_id, welcome, self.keyboards.main_keyboard())
    
    def show_promocodes(self, user_id):
        """Показ доступных промокодов"""
        # Загружаем промокоды из JSON
        DATA_DIR = Path("data")
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        promos = []
        if DATA_PROMO.exists():
            with open(DATA_PROMO, 'r', encoding='utf-8') as f:
                promos = json.load(f)
        
        if not promos:
            self.send_message(user_id, "😔 Нет активных промокодов", self.keyboards.back_keyboard())
            return
        
        # Выбираем случайный промокод
        promo = random.choice(promos)
        code = promo["code"] if isinstance(promo, dict) else promo
        
        # Сохраняем в историю
        self.db.record_promo_usage(user_id, code)
        
        message = f"🎁 Ваш промокод:\n\n🔑 {code}\n\n💡 Активируйте в магазине:\n{SHOP_URL}"
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    def show_servers(self, user_id):
        """Информация о серверах"""
        message = "🎮 СЕРВЕРА HOSTILE RUST\n\n"
        
        for key, server in SERVERS.items():
            message += f"🟢 {server['name']}\n"
            message += f"📌 IP: {server['ip']}\n"
            message += f"🔗 Мониторинг: {SHOP_URL}\n\n"
        
        message += "💡 Как подключиться:\n"
        message += "1. Скопируйте IP адрес\n"
        message += "2. В игре нажмите F1\n"
        message += "3. Введите: client.connect IP\n"
        
        self.send_message(user_id, message, self.keyboards.servers_keyboard())
    
    def send_server_ip(self, user_id, server_key):
        """Отправка IP сервера"""
        server = SERVERS.get(server_key)
        if server:
            self.send_message(user_id, f"📋 IP {server['name']}:\n{server['ip']}")
    
    def show_server_ips(self, user_id):
        """Показ всех IP для копирования"""
        message = "📋 IP СЕРВЕРОВ\n\n"
        for key, server in SERVERS.items():
            message += f"{server['name']}:\n{server['ip']}\n\n"
        
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    def show_rules(self, user_id):
        """Правила сервера"""
        rules_text = "📜 ПРАВИЛА HOSTILE RUST\n\n"
        
        for part in RULES:
            if len(rules_text) + len(part) + 2 > 4000:
                self.send_message(user_id, rules_text)
                rules_text = part + "\n"
            else:
                rules_text += part + "\n"
        
        if rules_text:
            rules_text += f"\n\n🔗 Discord: {DISCORD_URL}\n🔗 VK: {VK_GROUP_URL}"
            self.send_message(user_id, rules_text, self.keyboards.back_keyboard())
    
    def show_shop(self, user_id):
        """Магазин"""
        message = f"🛒 МАГАЗИН HOSTILE RUST\n\n{SHOP_URL}\n\n💡 Перейдите по ссылке для пополнения баланса!"
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    def show_wipe_info(self, user_id):
        """Информация о вайпе с учетом расписания"""
        now = datetime.now()
        
        # Находим следующий четверг
        days_until_thursday = (3 - now.weekday()) % 7
        if days_until_thursday == 0:
            current_hour = now.hour
            is_first_thursday = now.day <= 7
            
            if is_first_thursday and current_hour >= 22:
                days_until_thursday = 7
            elif not is_first_thursday and current_hour >= 12:
                days_until_thursday = 7
        
        next_wipe = now + timedelta(days=days_until_thursday)
        
        # Определяем время вайпа
        is_first_thursday = next_wipe.day <= 7
        wipe_hour = 22 if is_first_thursday else 12
        
        next_wipe = next_wipe.replace(hour=wipe_hour, minute=0, second=0, microsecond=0)
        
        # Вычисляем оставшееся время
        delta = next_wipe - now
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        
        message = "💣 ДО СЛЕДУЮЩЕГО ВАЙПА\n\n"
        message += f"🗓 {days} дней\n"
        message += f"🕒 {hours} часов\n"
        message += f"⏱ {minutes} минут\n\n"
        message += f"📅 Дата: {next_wipe.strftime('%d.%m.%Y')} в {wipe_hour}:00 МСК\n\n"
        
        if is_first_thursday:
            message += "⚠️ Это первый четверг месяца — вайп в 22:00!"
        else:
            message += "📌 Обычный четверг — вайп в 12:00"
        
        message += f"\n\n📋 Расписание:\n{WIPE_SCHEDULE}"
        
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    # ========== ТИКЕТЫ ==========
    
    def show_tickets_menu(self, user_id):
        """Меню тикетов"""
        tickets = self.db.get_user_tickets(user_id)
        open_tickets = [t for t in tickets if t.status == 'open']
        message = f"🎫 ПОДДЕРЖКА\n\n📊 Всего обращений: {len(tickets)}\n🟢 Открытых: {len(open_tickets)}\n\nВыберите действие:"
        self.send_message(user_id, message, self.keyboards.tickets_keyboard())
    
    def start_ticket_creation(self, user_id):
        """Начало создания тикета"""
        # Проверка кулдауна
        tickets = self.db.get_user_tickets(user_id)
        open_tickets = [t for t in tickets if t.status == 'open']
        
        if open_tickets:
            last_ticket = open_tickets[-1]
            if (datetime.now() - last_ticket.created_at).total_seconds() < TICKET_COOLDOWN_MINUTES * 60:
                self.send_message(user_id, f"⏳ Тикет можно создавать раз в {TICKET_COOLDOWN_MINUTES} минут", 
                                self.keyboards.back_keyboard())
                return
        
        self.user_states[user_id] = 'waiting_ticket'
        self.send_message(user_id, "📝 Опишите ваш вопрос подробно:", self.keyboards.back_keyboard())
    
    def create_ticket(self, user_id, text):
        """Создание тикета"""
        if len(text) < 10:
            self.send_message(user_id, "❌ Слишком короткое описание", self.keyboards.back_keyboard())
            return
        
        ticket_id = self.db.create_ticket(user_id, text)
        
        if user_id in self.user_states:
            del self.user_states[user_id]
        
        self.send_message(user_id, f"✅ Тикет #{ticket_id} создан! Администратор скоро ответит.", 
                        self.keyboards.tickets_keyboard())
        
        # Уведомление админам
        try:
            user_info = self.vk_api.users.get(user_ids=user_id)[0]
            user_name = f"{user_info['first_name']} {user_info['last_name']}"
        except:
            user_name = f"id{user_id}"
        
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button('✏️ Ответить', VkKeyboardColor.PRIMARY, 
                          payload={'command': f'ticket_answer_{ticket_id}'})
        
        admin_msg = f"📩 НОВЫЙ ТИКЕТ #{ticket_id}\n\n👤 {user_name}\n📝 {text[:200]}"
        self.send_admin_message(admin_msg, keyboard)
    
    def show_my_tickets(self, user_id):
        """Мои тикеты"""
        tickets = self.db.get_user_tickets(user_id)
        
        if not tickets:
            self.send_message(user_id, "📭 У вас нет обращений", self.keyboards.tickets_keyboard())
            return
        
        message = "📋 МОИ ТИКЕТЫ\n\n"
        for t in tickets[:10]:
            status = "🟢" if t.status == 'open' else "🔴"
            message += f"{status} #{t.id}: {t.title[:50]}...\n"
        
        self.send_message(user_id, message, self.keyboards.tickets_keyboard())
    
    def show_admin_tickets(self, admin_id):
        """Админ: все открытые тикеты"""
        if admin_id not in ADMIN_IDS:
            return
        
        tickets = self.db.get_open_tickets()
        
        if not tickets:
            self.send_message(admin_id, "✅ Нет открытых тикетов", self.keyboards.admin_keyboard())
            return
        
        keyboard = VkKeyboard(inline=True)
        message = "🎫 ОТКРЫТЫЕ ТИКЕТЫ\n\n"
        
        for t in tickets[:5]:
            user_name = f"{t.user.first_name} {t.user.last_name}" if t.user else f"id{t.user_id}"
            message += f"#{t.id} от {user_name}\n{t.title[:100]}\n\n"
            keyboard.add_button(f'✏️ Ответить #{t.id}', VkKeyboardColor.PRIMARY,
                              payload={'command': f'ticket_answer_{t.id}'})
            keyboard.add_line()
        
        keyboard.add_button('◀️ Назад', VkKeyboardColor.SECONDARY,
                          payload={'command': 'back_to_main'})
        
        self.send_message(admin_id, message, keyboard)
    
    def start_ticket_answer(self, admin_id, ticket_id):
        """Начало ответа на тикет"""
        if admin_id not in ADMIN_IDS:
            return
        
        self.user_states[admin_id] = f'ticket_reply_{ticket_id}'
        self.send_message(admin_id, f"✏️ Введите ответ на тикет #{ticket_id}:", 
                        self.keyboards.back_keyboard())
    
    def reply_to_ticket(self, admin_id, ticket_id, text):
        """Ответ на тикет"""
        if admin_id not in ADMIN_IDS:
            return
        
        ticket = self.db.get_ticket(ticket_id)
        
        if not ticket:
            self.send_message(admin_id, "❌ Тикет не найден")
            return
        
        user_id = ticket.user.vk_id
        
        # Отправляем ответ пользователю
        self.send_message(user_id, f"📩 ОТВЕТ НА ТИКЕТ #{ticket_id}\n\n👑 Администратор:\n{text}")
        
        # Добавляем сообщение в тикет
        self.db.add_ticket_message(ticket_id, admin_id, text, is_admin=True)
        
        if admin_id in self.user_states:
            del self.user_states[admin_id]
        
        self.send_message(admin_id, f"✅ Ответ отправлен!", self.keyboards.admin_keyboard())
    
    # ========== ПРОМОКОДЫ (АДМИН) ==========
    
    def check_promo_code(self, user_id, text):
        """Проверка ввода промокода"""
        # Загружаем промокоды из JSON
        DATA_DIR = Path("data")
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        if not DATA_PROMO.exists():
            return False
        
        with open(DATA_PROMO, 'r', encoding='utf-8') as f:
            promos = json.load(f)
        
        for promo in promos:
            code = promo["code"] if isinstance(promo, dict) else promo
            if code.upper() == text.upper():
                # Проверяем, не использовал ли уже
                session = self.db.get_session()
                try:
                    user = session.query(User).filter_by(vk_id=user_id).first()
                    promo_obj = session.query(PromoCode).filter_by(code=code).first()
                    
                    if user and promo_obj:
                        used = session.query(PromoUsage).filter_by(
                            user_id=user.id, promo_id=promo_obj.id
                        ).first()
                        if used:
                            self.send_message(user_id, "❌ Вы уже использовали этот промокод")
                            return True
                finally:
                    session.close()
                
                # Записываем использование
                self.db.record_promo_usage(user_id, code)
                
                self.send_message(user_id, f"🎁 Промокод активирован!\n\n🔑 {code}\n\n💡 Активируйте в магазине:\n{SHOP_URL}")
                return True
        return False
    
    def start_add_promo(self, admin_id):
        """Начало добавления промокода"""
        if admin_id not in ADMIN_IDS:
            return
        
        self.user_states[admin_id] = 'waiting_promo_add'
        self.send_message(admin_id, "➕ Введите новый промокод:", self.keyboards.back_keyboard())
    
    def add_promo(self, admin_id, code):
        """Добавление промокода"""
        if admin_id not in ADMIN_IDS:
            return
        
        code = code.strip().upper()
        
        DATA_DIR = Path("data")
        DATA_DIR.mkdir(exist_ok=True)
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        promos = []
        if DATA_PROMO.exists():
            with open(DATA_PROMO, 'r', encoding='utf-8') as f:
                promos = json.load(f)
        
        promos.append({"code": code, "date": datetime.now().isoformat()})
        
        with open(DATA_PROMO, 'w', encoding='utf-8') as f:
            json.dump(promos, f, indent=2, ensure_ascii=False)
        
        # Также добавляем в БД
        self.db.add_promo(code, "Промокод")
        
        if admin_id in self.user_states:
            del self.user_states[admin_id]
        
        self.send_message(admin_id, f"✅ Промокод {code} добавлен!", self.keyboards.admin_keyboard())
    
    def show_promo_list(self, admin_id):
        """Список промокодов"""
        if admin_id not in ADMIN_IDS:
            return
        
        DATA_DIR = Path("data")
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        promos = []
        if DATA_PROMO.exists():
            with open(DATA_PROMO, 'r', encoding='utf-8') as f:
                promos = json.load(f)
        
        if not promos:
            self.send_message(admin_id, "📭 Список промокодов пуст", self.keyboards.admin_keyboard())
            return
        
        message = "📋 СПИСОК ПРОМОКОДОВ\n\n"
        for p in promos:
            code = p["code"] if isinstance(p, dict) else p
            message += f"🎫 {code}\n"
        
        self.send_message(admin_id, message, self.keyboards.admin_keyboard())
    
    def show_promo_list_for_delete(self, admin_id):
        """Список промокодов для удаления"""
        if admin_id not in ADMIN_IDS:
            return
        
        DATA_DIR = Path("data")
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        promos = []
        if DATA_PROMO.exists():
            with open(DATA_PROMO, 'r', encoding='utf-8') as f:
                promos = json.load(f)
        
        if not promos:
            self.send_message(admin_id, "📭 Список промокодов пуст", self.keyboards.admin_keyboard())
            return
        
        keyboard = VkKeyboard(inline=True)
        
        for p in promos[:10]:
            code = p["code"] if isinstance(p, dict) else p
            keyboard.add_button(f'🗑 {code}', VkKeyboardColor.NEGATIVE,
                              payload={'command': f'confirm_delete_promo_{code}'})
            keyboard.add_line()
        
        keyboard.add_button('◀️ Назад', VkKeyboardColor.SECONDARY,
                          payload={'command': 'back_to_main'})
        
        self.send_message(admin_id, "➖ Выберите промокод для удаления:", keyboard)
    
    def delete_promo(self, admin_id, code):
        """Удаление промокода"""
        if admin_id not in ADMIN_IDS:
            return
        
        DATA_DIR = Path("data")
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        promos = []
        if DATA_PROMO.exists():
            with open(DATA_PROMO, 'r', encoding='utf-8') as f:
                promos = json.load(f)
        
        new_promos = []
        for p in promos:
            p_code = p["code"] if isinstance(p, dict) else p
            if p_code != code:
                new_promos.append(p)
        
        with open(DATA_PROMO, 'w', encoding='utf-8') as f:
            json.dump(new_promos, f, indent=2, ensure_ascii=False)
        
        self.send_message(admin_id, f"✅ Промокод {code} удален!", self.keyboards.admin_keyboard())
    
    # ========== АДМИНСКИЕ ФУНКЦИИ ==========
    
    def show_admin_menu(self, admin_id):
        """Админ-панель"""
        if admin_id not in ADMIN_IDS:
            return
        
        self.send_message(admin_id, "👑 АДМИН-ПАНЕЛЬ\n\nВыберите действие:", 
                        self.keyboards.admin_keyboard())
    
    def show_stats(self, admin_id):
        """Статистика"""
        if admin_id not in ADMIN_IDS:
            return
        
        session = self.db.get_session()
        try:
            users_count = session.query(User).count()
            promos_count = session.query(PromoCode).filter_by(is_active=True).count()
            tickets_count = session.query(Ticket).filter_by(status='open').count()
            usage_count = session.query(PromoUsage).count()
        finally:
            session.close()
        
        message = f"📊 СТАТИСТИКА\n\n"
        message += f"👥 Пользователей: {users_count}\n"
        message += f"🎁 Активных промокодов: {promos_count}\n"
        message += f"📈 Использований промокодов: {usage_count}\n"
        message += f"🎫 Открытых тикетов: {tickets_count}"
        
        self.send_message(admin_id, message, self.keyboards.admin_keyboard())
    
    def show_users_list(self, admin_id):
        """Список пользователей"""
        if admin_id not in ADMIN_IDS:
            return
        
        users = self.db.get_all_users()
        message = f"👥 ПОЛЬЗОВАТЕЛИ (всего: {len(users)})\n\n"
        
        for user in users[:20]:
            message += f"• @id{user.vk_id} ({user.first_name} {user.last_name})\n"
            message += f"  📅 {user.registered_at.strftime('%d.%m.%Y')}\n"
        
        self.send_message(admin_id, message, self.keyboards.admin_keyboard())
    
    def start_broadcast(self, admin_id):
        """Начало рассылки"""
        if admin_id not in ADMIN_IDS:
            return
        
        users = self.db.get_all_users()
        self.user_states[admin_id] = 'waiting_broadcast'
        self.send_message(admin_id, f"📢 Введите текст рассылки\n(будет отправлено {len(users)} пользователям):", 
                        self.keyboards.back_keyboard())
    
    def send_broadcast(self, admin_id, text):
        """Отправка рассылки"""
        if admin_id not in ADMIN_IDS:
            return
        
        users = self.db.get_all_users()
        
        def broadcast():
            sent = 0
            for user in users:
                try:
                    self.send_message(user.vk_id, f"📢 РАССЫЛКА\n\n{text}")
                    sent += 1
                    time.sleep(0.34)
                except Exception as e:
                    log.error(f"Ошибка отправки {user.vk_id}: {e}")
            
            self.send_message(admin_id, f"✅ Рассылка завершена!\nОтправлено: {sent}", 
                            self.keyboards.admin_keyboard())
        
        threading.Thread(target=broadcast, daemon=True).start()
        
        if admin_id in self.user_states:
            del self.user_states[admin_id]
        
        self.send_message(admin_id, "⏳ Рассылка запущена...")
    
    def run(self):
        """Запуск бота"""
        log.info("✅ БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
        
        while True:
            try:
                for event in self.longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                        payload = None
                        try:
                            if hasattr(event, 'payload') and event.payload:
                                payload = event.payload
                        except:
                            pass
                        
                        threading.Thread(
                            target=self.handle_message,
                            args=(event.user_id, event.text, payload),
                            daemon=True
                        ).start()
            
            except Exception as e:
                log.error(f"❌ Ошибка в главном цикле: {e}")
                time.sleep(5)

if __name__ == '__main__':
    bot = HostileRustVKBot()
    bot.run()
