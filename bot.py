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
from database import Database, User, PromoCode, PromoUsage, Ticket, TicketMessage
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
        
        # Загружаем список админов из файла
        self.admin_ids = self.load_admins()
        
        # Загружаем конфигурацию серверов
        self.servers_config = self.load_servers_config()
        
        log.info("✅ VK Бот Hostile Rust запущен!")
        log.info(f"👑 Администраторы: {self.admin_ids}")
        log.info(f"🎮 Загружено серверов: {len(self.servers_config)}")
    
    def load_admins(self):
        """Загрузка списка админов из файла"""
        DATA_DIR = Path("data")
        ADMIN_FILE = DATA_DIR / "admins.json"
        
        try:
            if ADMIN_FILE.exists() and ADMIN_FILE.stat().st_size > 0:
                with open(ADMIN_FILE, 'r', encoding='utf-8') as f:
                    admins = json.load(f)
                    if isinstance(admins, list) and admins:
                        return admins
        except (json.JSONDecodeError, FileNotFoundError) as e:
            log.error(f"❌ Ошибка загрузки admins.json: {e}")
            if ADMIN_FILE.exists():
                backup_file = ADMIN_FILE.with_suffix('.json.backup')
                ADMIN_FILE.rename(backup_file)
                log.info(f"📁 Поврежденный файл сохранен как {backup_file}")
        
        # Если файла нет или он поврежден, создаем с админами из config
        admins = list(ADMIN_IDS)
        DATA_DIR.mkdir(exist_ok=True)
        with open(ADMIN_FILE, 'w', encoding='utf-8') as f:
            json.dump(admins, f, indent=2, ensure_ascii=False)
        
        log.info("✅ Создан новый список администраторов")
        return admins
    
    def save_admins(self):
        """Сохранение списка админов в файл"""
        DATA_DIR = Path("data")
        ADMIN_FILE = DATA_DIR / "admins.json"
        
        with open(ADMIN_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.admin_ids, f, indent=2, ensure_ascii=False)
        log.info("💾 Список администраторов сохранен")
    
    def load_servers_config(self):
        """Загрузка конфигурации серверов из файла"""
        DATA_DIR = Path("data")
        SERVERS_FILE = DATA_DIR / "servers.json"
        
        try:
            if SERVERS_FILE.exists() and SERVERS_FILE.stat().st_size > 0:
                with open(SERVERS_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if config:
                        log.info("✅ Конфигурация серверов загружена из файла")
                        return config
        except (json.JSONDecodeError, FileNotFoundError) as e:
            log.error(f"❌ Ошибка загрузки servers.json: {e}")
            if SERVERS_FILE.exists():
                backup_file = SERVERS_FILE.with_suffix('.json.backup')
                SERVERS_FILE.rename(backup_file)
                log.info(f"📁 Поврежденный файл сохранен как {backup_file}")
        
        # Если файла нет или он поврежден, создаем с серверами по умолчанию
        servers = {
            "x2": {
                "name": "HOSTILE RUST | x2 | SOLO/DUO",
                "ip": "37.230.137.6:20600",
                "wipe_interval": 2,
                "description": "Сервер x2, вайп раз в 2 недели"
            },
            "x100": {
                "name": "HOSTILE RUST | x100 | CLANS",
                "ip": "5.42.211.191:35000",
                "wipe_interval": 1,
                "description": "Сервер x100, вайп каждую неделю"
            }
        }
        
        DATA_DIR.mkdir(exist_ok=True)
        with open(SERVERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(servers, f, indent=2, ensure_ascii=False)
        
        log.info("✅ Создана новая конфигурация серверов")
        return servers
    
    def save_servers_config(self):
        """Сохранение конфигурации серверов в файл"""
        DATA_DIR = Path("data")
        SERVERS_FILE = DATA_DIR / "servers.json"
        
        with open(SERVERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.servers_config, f, indent=2, ensure_ascii=False)
        log.info("💾 Конфигурация серверов сохранена")
    
    def reload_servers_config(self):
        """Принудительная перезагрузка конфигурации серверов из файла"""
        try:
            self.servers_config = self.load_servers_config()
            log.info("🔄 Конфигурация серверов принудительно перезагружена")
            return True
        except Exception as e:
            log.error(f"❌ Ошибка перезагрузки конфигурации серверов: {e}")
            return False
    
    def is_admin(self, user_id):
        """Проверка, является ли пользователь админом"""
        return user_id in self.admin_ids
    
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
        for admin_id in self.admin_ids:
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
                elif command.startswith('admin_close_'):
                    ticket_id = int(command.replace('admin_close_', ''))
                    self.close_ticket_admin(user_id, ticket_id)
                    return
                elif command == 'admin_tickets':
                    self.show_admin_tickets(user_id)
                    return
                elif command.startswith('confirm_delete_promo_'):
                    code = command.replace('confirm_delete_promo_', '')
                    self.delete_promo(user_id, code)
                    return
                elif command == 'create_ticket_from_unknown':
                    self.start_ticket_creation(user_id)
                    return
                elif command == 'admin_manage_admins':
                    self.show_admin_management(user_id)
                    return
                elif command == 'start_add_admin':
                    self.start_add_admin_flow(user_id)
                    return
                elif command == 'start_remove_admin':
                    self.start_remove_admin_flow(user_id)
                    return
                elif command.startswith('remove_admin_'):
                    remove_admin_id = int(command.replace('remove_admin_', ''))
                    self.remove_admin(user_id, remove_admin_id)
                    return
                elif command == 'admin_edit_servers':
                    self.show_servers_editor(user_id)
                    return
                elif command.startswith('edit_server_'):
                    server_key = command.replace('edit_server_', '')
                    self.start_edit_server(user_id, server_key)
                    return
                elif command.startswith('edit_name_'):
                    server_key = command.replace('edit_name_', '')
                    self.start_edit_server_name(user_id, server_key)
                    return
                elif command.startswith('edit_ip_'):
                    server_key = command.replace('edit_ip_', '')
                    self.start_edit_server_ip(user_id, server_key)
                    return
                elif command.startswith('edit_wipe_'):
                    server_key = command.replace('edit_wipe_', '')
                    self.start_edit_server_wipe(user_id, server_key)
                    return
                elif command == 'admin_promo_stats':
                    self.show_promo_stats(user_id)
                    return
                elif command == 'admin_back':
                    self.show_admin_menu(user_id)
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
            elif state.startswith('edit_server_name_'):
                server_key = state.replace('edit_server_name_', '')
                self.edit_server_name(user_id, server_key, text)
                return
            elif state.startswith('edit_server_ip_'):
                server_key = state.replace('edit_server_ip_', '')
                self.edit_server_ip(user_id, server_key, text)
                return
            elif state.startswith('edit_server_wipe_'):
                server_key = state.replace('edit_server_wipe_', '')
                self.edit_server_wipe(user_id, server_key, text)
                return
            elif state == 'waiting_add_admin':
                self.process_add_admin(user_id, text)
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
        elif self.is_admin(user_id):
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
            elif text_lower in ['❌ закрыть тикет', 'закрыть тикет']:
                self.show_open_tickets_for_close(user_id)
            elif text_lower in ['👑 управление админами']:
                self.show_admin_management(user_id)
            elif text_lower in ['🔧 редактировать сервера']:
                self.show_servers_editor(user_id)
            elif text_lower in ['📈 статистика промокодов']:
                self.show_promo_stats(user_id)
            else:
                self.offer_ticket_creation(user_id)
        
        # Проверка на ввод промокода
        elif self.check_promo_code(user_id, text):
            pass
        else:
            self.offer_ticket_creation(user_id)
    
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
        DATA_DIR = Path("data")
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        promos = []
        if DATA_PROMO.exists():
            with open(DATA_PROMO, 'r', encoding='utf-8') as f:
                promos = json.load(f)
        
        if not promos:
            self.send_message(user_id, "😔 Нет активных промокодов", self.keyboards.back_keyboard())
            return
        
        promo = random.choice(promos)
        code = promo["code"] if isinstance(promo, dict) else promo
        
        self.db.record_promo_usage(user_id, code)
        
        message = f"🎁 Ваш промокод:\n\n🔑 {code}\n\n💡 Активируйте в магазине:\n{SHOP_URL}"
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    def show_servers(self, user_id):
        """Информация о серверах"""
        self.reload_servers_config()
        
        message = "🎮 СЕРВЕРА HOSTILE RUST\n\n"
        
        for key, server in self.servers_config.items():
            message += f"🟢 {server['name']}\n"
            message += f"📌 IP: {server['ip']}\n"
            message += f"🔄 Вайп: раз в {server['wipe_interval']} нед.\n"
            message += f"🔗 Мониторинг: {SHOP_URL}\n\n"
        
        message += "💡 Как подключиться:\n"
        message += "1. Скопируйте IP адрес\n"
        message += "2. В игре нажмите F1\n"
        message += "3. Введите: client.connect IP\n"
        
        self.send_message(user_id, message, self.keyboards.servers_keyboard())
    
    def send_server_ip(self, user_id, server_key):
        """Отправка IP сервера"""
        self.reload_servers_config()
        
        server = self.servers_config.get(server_key)
        if server:
            self.send_message(user_id, f"📋 IP {server['name']}:\n{server['ip']}")
    
    def show_server_ips(self, user_id):
        """Показ всех IP для копирования"""
        self.reload_servers_config()
        
        message = "📋 IP СЕРВЕРОВ\n\n"
        for key, server in self.servers_config.items():
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
    
    def is_first_thursday_of_month(self, date):
        """Проверка, является ли четверг первым в месяце"""
        return date.day <= 7 and date.weekday() == 3
    
    def get_next_wipe_date(self, server_key):
        """Расчет даты следующего вайпа"""
        server = self.servers_config.get(server_key)
        if not server:
            return None
        
        now = datetime.now()
        weeks_interval = server.get('wipe_interval', 1)
        
        # Для x2 сервера (раз в 2 недели)
        if weeks_interval > 1:
            # Первый вайп: 18 июня 2026 года в 12:00 МСК
            first_wipe = datetime(2026, 6, 18, 12, 0, 0)
            
            # Если текущая дата раньше первого вайпа
            if now < first_wipe:
                # Проверяем, является ли дата первым четвергом месяца
                if self.is_first_thursday_of_month(first_wipe):
                    return first_wipe.replace(hour=22, minute=0, second=0, microsecond=0)
                return first_wipe
            
            # Рассчитываем количество прошедших двухнедельных циклов
            days_since_first = (now - first_wipe).days
            cycles_passed = days_since_first // 14
            
            # Следующий вайп
            next_wipe = first_wipe + timedelta(weeks=2 * cycles_passed)
            
            # Если вайп уже прошел сегодня, берем следующий
            if next_wipe <= now:
                next_wipe = first_wipe + timedelta(weeks=2 * (cycles_passed + 1))
            
            # Проверяем, является ли дата первым четвергом месяца
            if self.is_first_thursday_of_month(next_wipe):
                # Если первый четверг месяца - вайп в 22:00
                next_wipe = next_wipe.replace(hour=22, minute=0, second=0, microsecond=0)
            else:
                # Обычный четверг - вайп в 12:00
                next_wipe = next_wipe.replace(hour=12, minute=0, second=0, microsecond=0)
            
            return next_wipe
        
        else:
            # Для x100 сервера (каждую неделю)
            days_until_thursday = (3 - now.weekday()) % 7
            if days_until_thursday == 0 and now.hour >= 12:
                days_until_thursday = 7
            
            next_thursday = now + timedelta(days=days_until_thursday)
            
            if self.is_first_thursday_of_month(next_thursday):
                wipe_hour = 22
            else:
                wipe_hour = 12
            
            next_wipe = next_thursday.replace(hour=wipe_hour, minute=0, second=0, microsecond=0)
            
            if days_until_thursday == 0 and now >= next_wipe:
                next_wipe = next_thursday + timedelta(days=7)
                if self.is_first_thursday_of_month(next_wipe):
                    wipe_hour = 22
                else:
                    wipe_hour = 12
                next_wipe = next_wipe.replace(hour=wipe_hour, minute=0, second=0, microsecond=0)
            
            return next_wipe
    
    def show_wipe_info(self, user_id):
        """Информация о вайпах"""
        self.reload_servers_config()
        
        now = datetime.now()
        
        message = "💣 ИНФОРМАЦИЯ О ВАЙПАХ\n\n"
        message += "📌 Все вайпы проходят по четвергам\n"
        message += "🕐 Обычное время: 12:00 МСК\n"
        message += "🕙 Первый четверг месяца: 22:00 МСК\n\n"
        
        for key, server in self.servers_config.items():
            next_wipe = self.get_next_wipe_date(key)
            if next_wipe:
                delta = next_wipe - now
                days = delta.days
                hours = delta.seconds // 3600
                minutes = (delta.seconds % 3600) // 60
                
                is_first = self.is_first_thursday_of_month(next_wipe)
                wipe_time = "22:00" if is_first else "12:00"
                
                emoji = "🔵" if "x2" in server['name'].lower() else "🔴"
                message += f"{emoji} {server['name']}\n"
                message += f"📅 Дата вайпа: {next_wipe.strftime('%d.%m.%Y')} в {wipe_time} МСК\n"
                message += f"⏳ До вайпа: {days} д. {hours} ч. {minutes} мин.\n"
                message += f"🔄 Периодичность: раз в {server.get('wipe_interval', 1)} нед.\n"
                
                if is_first:
                    message += "⚠️ Это первый четверг месяца — вайп в 22:00!\n"
                
                message += "\n"
        
        message += "🔄 Вайпы x2 сервера проходят строго раз в 14 дней\n"
        message += "🔄 Вайпы x100 сервера проходят строго раз в 7 дней\n"
        
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    def offer_ticket_creation(self, user_id):
        """Предложение создать тикет при неизвестном сообщении"""
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button('🎫 Создать тикет', VkKeyboardColor.POSITIVE, 
                           payload={'command': 'create_ticket_from_unknown'})
        keyboard.add_button('📋 Главное меню', VkKeyboardColor.SECONDARY,
                           payload={'command': 'back_to_main'})
        
        message = "🤔 Я не совсем понял ваш запрос.\n\n"
        message += "Хотите создать тикет для связи с администрацией?\n"
        message += "Администратор ответит вам в ближайшее время."
        
        self.send_message(user_id, message, keyboard)
    
    # ========== ТИКЕТЫ ==========
    
    def show_tickets_menu(self, user_id):
        """Меню тикетов"""
        session = self.db.get_session()
        try:
            user = session.query(User).filter_by(vk_id=user_id).first()
            if user:
                tickets = session.query(Ticket).filter_by(user_id=user.id).all()
                open_tickets = [t for t in tickets if t.status == 'open']
                message = f"🎫 ПОДДЕРЖКА\n\n📊 Всего обращений: {len(tickets)}\n🟢 Открытых: {len(open_tickets)}\n\nВыберите действие:"
            else:
                message = f"🎫 ПОДДЕРЖКА\n\n📊 Всего обращений: 0\n\nВыберите действие:"
        finally:
            session.close()
        
        self.send_message(user_id, message, self.keyboards.tickets_keyboard())
    
    def start_ticket_creation(self, user_id):
        """Начало создания тикета"""
        session = self.db.get_session()
        try:
            user = session.query(User).filter_by(vk_id=user_id).first()
            if user:
                tickets = session.query(Ticket).filter_by(user_id=user.id, status='open').all()
                if tickets:
                    last_ticket = tickets[-1]
                    if (datetime.now() - last_ticket.created_at).total_seconds() < TICKET_COOLDOWN_MINUTES * 60:
                        self.send_message(user_id, f"⏳ Тикет можно создавать раз в {TICKET_COOLDOWN_MINUTES} минут", 
                                        self.keyboards.back_keyboard())
                        return
        finally:
            session.close()
        
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
        
        try:
            user_info = self.vk_api.users.get(user_ids=user_id)[0]
            user_name = f"{user_info['first_name']} {user_info['last_name']}"
        except:
            user_name = f"id{user_id}"
        
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button('✏️ Ответить', VkKeyboardColor.PRIMARY, 
                          payload={'command': f'ticket_answer_{ticket_id}'})
        keyboard.add_button('❌ Закрыть', VkKeyboardColor.NEGATIVE,
                          payload={'command': f'admin_close_{ticket_id}'})
        
        admin_msg = f"📩 НОВЫЙ ТИКЕТ #{ticket_id}\n\n👤 {user_name}\n📝 {text[:200]}"
        self.send_admin_message(admin_msg, keyboard)
    
    def show_my_tickets(self, user_id):
        """Мои тикеты"""
        session = self.db.get_session()
        try:
            user = session.query(User).filter_by(vk_id=user_id).first()
            if not user:
                self.send_message(user_id, "📭 У вас нет обращений", self.keyboards.tickets_keyboard())
                return
            
            tickets = session.query(Ticket).filter_by(user_id=user.id).order_by(Ticket.created_at.desc()).limit(10).all()
            
            if not tickets:
                self.send_message(user_id, "📭 У вас нет обращений", self.keyboards.tickets_keyboard())
                return
            
            message = "📋 МОИ ТИКЕТЫ\n\n"
            for t in tickets:
                status = "🟢" if t.status == 'open' else "🔴"
                message += f"{status} #{t.id}: {t.title[:50]}...\n"
            
            self.send_message(user_id, message, self.keyboards.tickets_keyboard())
        finally:
            session.close()
    
    def show_admin_tickets(self, admin_id):
        """Админ: все открытые тикеты"""
        if not self.is_admin(admin_id):
            return
        
        session = self.db.get_session()
        try:
            tickets = session.query(Ticket).filter_by(status='open').order_by(Ticket.created_at.desc()).all()
            
            if not tickets:
                self.send_message(admin_id, "✅ Нет открытых тикетов", self.keyboards.admin_keyboard())
                return
            
            self.send_message(admin_id, f"🎫 ОТКРЫТЫЕ ТИКЕТЫ (всего: {len(tickets)})\n")
            
            for t in tickets[:10]:
                user_name = f"{t.user.first_name} {t.user.last_name}" if t.user else f"id{t.user_id}"
                
                message = f"🟢 ТИКЕТ #{t.id}\n"
                message += f"👤 От: {user_name}\n"
                message += f"📅 {t.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                message += f"📝 {t.title}\n"
                
                keyboard = VkKeyboard(inline=True)
                keyboard.add_button('✏️ Ответить', VkKeyboardColor.PRIMARY,
                                  payload={'command': f'ticket_answer_{t.id}'})
                keyboard.add_button('❌ Закрыть', VkKeyboardColor.NEGATIVE,
                                  payload={'command': f'admin_close_{t.id}'})
                
                self.send_message(admin_id, message, keyboard)
            
            if len(tickets) > 10:
                self.send_message(admin_id, f"... и еще {len(tickets) - 10} тикетов")
                
        finally:
            session.close()
    
    def show_open_tickets_for_close(self, admin_id):
        """Показ тикетов для закрытия"""
        if not self.is_admin(admin_id):
            return
        
        session = self.db.get_session()
        try:
            tickets = session.query(Ticket).filter_by(status='open').order_by(Ticket.created_at.desc()).limit(10).all()
            
            if not tickets:
                self.send_message(admin_id, "✅ Нет открытых тикетов", self.keyboards.admin_keyboard())
                return
            
            keyboard = VkKeyboard(inline=True)
            
            for t in tickets:
                user_name = f"{t.user.first_name} {t.user.last_name}" if t.user else f"id{t.user_id}"
                keyboard.add_button(f'❌ Закрыть #{t.id} ({user_name[:15]}...)', 
                                  VkKeyboardColor.NEGATIVE,
                                  payload={'command': f'admin_close_{t.id}'})
                keyboard.add_line()
            
            keyboard.add_button('◀️ Назад', VkKeyboardColor.SECONDARY,
                              payload={'command': 'admin_back'})
            
            self.send_message(admin_id, "📋 Выберите тикет для закрытия:", keyboard)
        finally:
            session.close()
    
    def start_ticket_answer(self, admin_id, ticket_id):
        """Начало ответа на тикет"""
        if not self.is_admin(admin_id):
            return
        
        self.user_states[admin_id] = f'ticket_reply_{ticket_id}'
        self.send_message(admin_id, f"✏️ Введите ответ на тикет #{ticket_id}:", 
                        self.keyboards.back_keyboard())
    
    def reply_to_ticket(self, admin_id, ticket_id, text):
        """Ответ на тикет"""
        if not self.is_admin(admin_id):
            return
        
        session = self.db.get_session()
        try:
            ticket = session.query(Ticket).filter_by(id=ticket_id).first()
            
            if not ticket:
                self.send_message(admin_id, "❌ Тикет не найден")
                return
            
            if ticket.status == 'closed':
                self.send_message(admin_id, "❌ Тикет уже закрыт")
                return
            
            user_id = ticket.user.vk_id
            
            msg = TicketMessage(
                ticket_id=ticket_id,
                user_id=admin_id,
                message=text,
                is_admin=True
            )
            session.add(msg)
            session.commit()
            
        finally:
            session.close()
        
        self.send_message(user_id, f"📩 ОТВЕТ НА ТИКЕТ #{ticket_id}\n\n👑 Администратор:\n{text}")
        
        if admin_id in self.user_states:
            del self.user_states[admin_id]
        
        self.send_message(admin_id, f"✅ Ответ отправлен!", self.keyboards.admin_keyboard())
    
    def close_ticket_admin(self, admin_id, ticket_id):
        """Закрытие тикета администратором"""
        if not self.is_admin(admin_id):
            return
        
        session = self.db.get_session()
        try:
            ticket = session.query(Ticket).filter_by(id=ticket_id).first()
            
            if not ticket:
                self.send_message(admin_id, "❌ Тикет не найден")
                return
            
            if ticket.status == 'closed':
                self.send_message(admin_id, "❌ Тикет уже закрыт")
                return
            
            user_id = ticket.user.vk_id
            
            ticket.status = 'closed'
            ticket.closed_at = datetime.now()
            session.commit()
            
        finally:
            session.close()
        
        self.send_message(user_id, f"🔒 Тикет #{ticket_id} закрыт администратором\n\nЕсли остались вопросы, создайте новый тикет.")
        self.send_message(admin_id, f"✅ Тикет #{ticket_id} закрыт!", self.keyboards.admin_keyboard())
    
    # ========== ПРОМОКОДЫ ==========
    
    def check_promo_code(self, user_id, text):
        """Проверка ввода промокода"""
        DATA_DIR = Path("data")
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        if not DATA_PROMO.exists():
            return False
        
        try:
            with open(DATA_PROMO, 'r', encoding='utf-8') as f:
                promos = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return False
        
        for promo in promos:
            code = promo["code"] if isinstance(promo, dict) else promo
            if code.upper() == text.upper():
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
                
                self.db.record_promo_usage(user_id, code)
                
                self.send_message(user_id, f"🎁 Промокод активирован!\n\n🔑 {code}\n\n💡 Активируйте в магазине:\n{SHOP_URL}")
                return True
        return False
    
    def start_add_promo(self, admin_id):
        """Начало добавления промокода"""
        if not self.is_admin(admin_id):
            return
        
        self.user_states[admin_id] = 'waiting_promo_add'
        self.send_message(admin_id, "➕ Введите новый промокод:", self.keyboards.back_keyboard())
    
    def add_promo(self, admin_id, code):
        """Добавление промокода"""
        if not self.is_admin(admin_id):
            return
        
        code = code.strip().upper()
        
        DATA_DIR = Path("data")
        DATA_DIR.mkdir(exist_ok=True)
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        promos = []
        if DATA_PROMO.exists():
            try:
                with open(DATA_PROMO, 'r', encoding='utf-8') as f:
                    promos = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                promos = []
        
        promos.append({"code": code, "date": datetime.now().isoformat()})
        
        with open(DATA_PROMO, 'w', encoding='utf-8') as f:
            json.dump(promos, f, indent=2, ensure_ascii=False)
        
        self.db.add_promo(code, "Промокод")
        
        if admin_id in self.user_states:
            del self.user_states[admin_id]
        
        self.send_message(admin_id, f"✅ Промокод {code} добавлен!", self.keyboards.admin_keyboard())
    
    def show_promo_list(self, admin_id):
        """Список промокодов"""
        if not self.is_admin(admin_id):
            return
        
        DATA_DIR = Path("data")
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        promos = []
        if DATA_PROMO.exists():
            try:
                with open(DATA_PROMO, 'r', encoding='utf-8') as f:
                    promos = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                promos = []
        
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
        if not self.is_admin(admin_id):
            return
        
        DATA_DIR = Path("data")
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        promos = []
        if DATA_PROMO.exists():
            try:
                with open(DATA_PROMO, 'r', encoding='utf-8') as f:
                    promos = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                promos = []
        
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
                          payload={'command': 'admin_back'})
        
        self.send_message(admin_id, "➖ Выберите промокод для удаления:", keyboard)
    
    def delete_promo(self, admin_id, code):
        """Удаление промокода"""
        if not self.is_admin(admin_id):
            return
        
        DATA_DIR = Path("data")
        DATA_PROMO = DATA_DIR / "promocodes.json"
        
        promos = []
        if DATA_PROMO.exists():
            try:
                with open(DATA_PROMO, 'r', encoding='utf-8') as f:
                    promos = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                promos = []
        
        new_promos = []
        for p in promos:
            p_code = p["code"] if isinstance(p, dict) else p
            if p_code != code:
                new_promos.append(p)
        
        with open(DATA_PROMO, 'w', encoding='utf-8') as f:
            json.dump(new_promos, f, indent=2, ensure_ascii=False)
        
        self.send_message(admin_id, f"✅ Промокод {code} удален!", self.keyboards.admin_keyboard())
    
    def show_promo_stats(self, admin_id):
        """Статистика использования промокодов"""
        if not self.is_admin(admin_id):
            return
        
        session = self.db.get_session()
        try:
            recent_usages = session.query(PromoUsage).order_by(
                PromoUsage.used_at.desc()
            ).limit(10).all()
            
            message = "📈 СТАТИСТИКА ПРОМОКОДОВ\n\n"
            message += "🕒 ПОСЛЕДНИЕ АКТИВАЦИИ:\n"
            
            if recent_usages:
                for usage in recent_usages:
                    user = session.query(User).filter_by(id=usage.user_id).first()
                    promo = session.query(PromoCode).filter_by(id=usage.promo_id).first()
                    
                    if user and promo:
                        try:
                            user_info = self.vk_api.users.get(user_ids=user.vk_id)[0]
                            user_name = f"{user_info['first_name']} {user_info['last_name']}"
                        except:
                            user_name = f"id{user.vk_id}"
                        
                        message += f"• {user_name}\n"
                        message += f"  Код: {promo.code}\n"
                        message += f"  Дата: {usage.used_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            else:
                message += "Нет активаций\n"
            
            total_usages = session.query(PromoUsage).count()
            message += f"\n📊 ВСЕГО АКТИВАЦИЙ: {total_usages}"
            
        finally:
            session.close()
        
        self.send_message(admin_id, message, self.keyboards.admin_keyboard())
    
    # ========== УПРАВЛЕНИЕ АДМИНАМИ ==========
    
    def show_admin_management(self, admin_id):
        """Показ меню управления админами"""
        if not self.is_admin(admin_id):
            return
        
        message = "👑 УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ\n\n"
        message += "📋 ТЕКУЩИЕ АДМИНЫ:\n"
        
        for aid in self.admin_ids:
            try:
                user_info = self.vk_api.users.get(user_ids=aid)[0]
                user_name = f"{user_info['first_name']} {user_info['last_name']}"
                message += f"• {user_name} (id{aid})\n"
            except:
                message += f"• id{aid}\n"
        
        keyboard = self.keyboards.admin_management_keyboard()
        
        self.send_message(admin_id, message, keyboard)
    
    def start_add_admin_flow(self, admin_id):
        """Начало процесса добавления админа"""
        if not self.is_admin(admin_id):
            return
        
        self.user_states[admin_id] = 'waiting_add_admin'
        self.send_message(admin_id, "➕ Введите ID пользователя ВК для добавления в админы:", 
                        self.keyboards.back_keyboard())
    
    def process_add_admin(self, admin_id, text):
        """Обработка добавления админа"""
        if not self.is_admin(admin_id):
            return
        
        try:
            new_admin_id = int(text.strip())
            
            try:
                user_info = self.vk_api.users.get(user_ids=new_admin_id)[0]
                user_name = f"{user_info['first_name']} {user_info['last_name']}"
            except:
                self.send_message(admin_id, "❌ Пользователь не найден")
                if admin_id in self.user_states:
                    del self.user_states[admin_id]
                return
            
            if new_admin_id in self.admin_ids:
                self.send_message(admin_id, "❌ Этот пользователь уже администратор")
                if admin_id in self.user_states:
                    del self.user_states[admin_id]
                return
            
            self.admin_ids.append(new_admin_id)
            self.save_admins()
            
            self.send_message(admin_id, f"✅ {user_name} (id{new_admin_id}) добавлен в администраторы!", 
                            self.keyboards.admin_keyboard())
            
            self.send_message(new_admin_id, "🎉 Поздравляем! Вы назначены администратором Hostile Rust!")
            
        except ValueError:
            self.send_message(admin_id, "❌ Неверный ID. Введите числовой ID пользователя")
        finally:
            if admin_id in self.user_states:
                del self.user_states[admin_id]
    
    def start_remove_admin_flow(self, admin_id):
        """Начало процесса удаления админа"""
        if not self.is_admin(admin_id):
            return
        
        keyboard = VkKeyboard(inline=True)
        
        for aid in self.admin_ids:
            if aid != admin_id:
                try:
                    user_info = self.vk_api.users.get(user_ids=aid)[0]
                    user_name = f"{user_info['first_name']} {user_info['last_name']}"
                    keyboard.add_button(f'❌ {user_name}', VkKeyboardColor.NEGATIVE,
                                      payload={'command': f'remove_admin_{aid}'})
                    keyboard.add_line()
                except:
                    pass
        
        keyboard.add_button('◀️ Назад', VkKeyboardColor.SECONDARY,
                          payload={'command': 'admin_manage_admins'})
        
        self.send_message(admin_id, "➖ Выберите админа для удаления:", keyboard)
    
    def remove_admin(self, admin_id, remove_admin_id):
        """Удаление админа"""
        if not self.is_admin(admin_id):
            return
        
        if remove_admin_id not in self.admin_ids:
            self.send_message(admin_id, "❌ Этот пользователь не администратор")
            return
        
        if remove_admin_id == admin_id:
            self.send_message(admin_id, "❌ Нельзя удалить самого себя")
            return
        
        self.admin_ids.remove(remove_admin_id)
        self.save_admins()
        
        try:
            user_info = self.vk_api.users.get(user_ids=remove_admin_id)[0]
            user_name = f"{user_info['first_name']} {user_info['last_name']}"
        except:
            user_name = f"id{remove_admin_id}"
        
        self.send_message(admin_id, f"✅ {user_name} удален из администраторов!", 
                        self.keyboards.admin_keyboard())
        self.send_message(remove_admin_id, "ℹ️ Вы были удалены из администраторов Hostile Rust")
    
    # ========== РЕДАКТИРОВАНИЕ СЕРВЕРОВ ==========
    
    def show_servers_editor(self, admin_id):
        """Показ редактора серверов"""
        if not self.is_admin(admin_id):
            return
        
        self.reload_servers_config()
        
        message = "🔧 РЕДАКТОР СЕРВЕРОВ\n\n"
        message += "Выберите сервер для редактирования:\n\n"
        
        for key, server in self.servers_config.items():
            message += f"🟢 {server['name']}\n"
            message += f"   IP: {server['ip']}\n"
            message += f"   Вайп: раз в {server.get('wipe_interval', 1)} нед.\n\n"
        
        keyboard = self.keyboards.servers_editor_keyboard(self.servers_config)
        
        self.send_message(admin_id, message, keyboard)
    
    def start_edit_server(self, admin_id, server_key):
        """Начало редактирования сервера"""
        if not self.is_admin(admin_id):
            return
        
        self.reload_servers_config()
        
        server = self.servers_config.get(server_key)
        if not server:
            self.send_message(admin_id, "❌ Сервер не найден")
            return
        
        keyboard = self.keyboards.server_edit_options_keyboard(server_key)
        
        message = f"✏️ РЕДАКТИРОВАНИЕ: {server['name']}\n\n"
        message += "Что хотите изменить?"
        
        self.send_message(admin_id, message, keyboard)
    
    def start_edit_server_name(self, admin_id, server_key):
        """Начало изменения названия сервера"""
        if not self.is_admin(admin_id):
            return
        
        self.user_states[admin_id] = f'edit_server_name_{server_key}'
        self.send_message(admin_id, "📝 Введите новое название сервера:", 
                        self.keyboards.back_keyboard())
    
    def edit_server_name(self, admin_id, server_key, text):
        """Изменение названия сервера"""
        if not self.is_admin(admin_id):
            return
        
        server = self.servers_config.get(server_key)
        if server:
            old_name = server['name']
            server['name'] = text.strip()
            self.save_servers_config()
            self.reload_servers_config()
            
            log.info(f"📝 Название сервера {server_key} изменено: {old_name} -> {text.strip()}")
            
            self.send_message(admin_id, f"✅ Название сервера изменено на: {text.strip()}\n\n"
                             f"💡 Теперь новая информация будет отображаться всем пользователям.", 
                            self.keyboards.admin_keyboard())
        
        if admin_id in self.user_states:
            del self.user_states[admin_id]
    
    def start_edit_server_ip(self, admin_id, server_key):
        """Начало изменения IP сервера"""
        if not self.is_admin(admin_id):
            return
        
        self.user_states[admin_id] = f'edit_server_ip_{server_key}'
        self.send_message(admin_id, "🌐 Введите новый IP адрес сервера (формат: ip:port):", 
                        self.keyboards.back_keyboard())
    
    def edit_server_ip(self, admin_id, server_key, text):
        """Изменение IP сервера"""
        if not self.is_admin(admin_id):
            return
        
        server = self.servers_config.get(server_key)
        if server:
            old_ip = server['ip']
            new_ip = text.strip()
            
            if ':' not in new_ip:
                self.send_message(admin_id, "❌ Неверный формат IP. Используйте формат: ip:port (например: 5.42.211.191:35000)")
                if admin_id in self.user_states:
                    del self.user_states[admin_id]
                return
            
            server['ip'] = new_ip
            self.save_servers_config()
            self.reload_servers_config()
            
            log.info(f"🌐 IP сервера {server_key} изменен: {old_ip} -> {new_ip}")
            
            self.send_message(admin_id, f"✅ IP сервера изменен на: {new_ip}\n\n"
                             f"💡 Теперь новая информация будет отображаться всем пользователям.", 
                            self.keyboards.admin_keyboard())
        
        if admin_id in self.user_states:
            del self.user_states[admin_id]
    
    def start_edit_server_wipe(self, admin_id, server_key):
        """Начало изменения интервала вайпа"""
        if not self.is_admin(admin_id):
            return
        
        self.user_states[admin_id] = f'edit_server_wipe_{server_key}'
        self.send_message(admin_id, "🔄 Введите новый интервал вайпа в неделях (1 или 2):", 
                        self.keyboards.back_keyboard())
    
    def edit_server_wipe(self, admin_id, server_key, text):
        """Изменение интервала вайпа"""
        if not self.is_admin(admin_id):
            return
        
        try:
            interval = int(text.strip())
            if interval < 1 or interval > 2:
                self.send_message(admin_id, "❌ Интервал должен быть 1 или 2 недели")
                if admin_id in self.user_states:
                    del self.user_states[admin_id]
                return
            
            server = self.servers_config.get(server_key)
            if server:
                old_interval = server['wipe_interval']
                server['wipe_interval'] = interval
                self.save_servers_config()
                self.reload_servers_config()
                
                log.info(f"🔄 Интервал вайпа сервера {server_key} изменен: {old_interval} -> {interval} нед.")
                
                self.send_message(admin_id, f"✅ Интервал вайпа изменен на: {interval} нед.\n\n"
                                 f"💡 Теперь новая информация будет отображаться всем пользователям.", 
                                self.keyboards.admin_keyboard())
        except ValueError:
            self.send_message(admin_id, "❌ Введите число 1 или 2")
        finally:
            if admin_id in self.user_states:
                del self.user_states[admin_id]
    
    # ========== АДМИНСКИЕ ФУНКЦИИ ==========
    
    def show_admin_menu(self, admin_id):
        """Админ-панель"""
        if not self.is_admin(admin_id):
            return
        
        self.send_message(admin_id, "👑 АДМИН-ПАНЕЛЬ\n\nВыберите действие:", 
                        self.keyboards.admin_keyboard())
    
    def show_stats(self, admin_id):
        """Статистика"""
        if not self.is_admin(admin_id):
            return
        
        session = self.db.get_session()
        try:
            users_count = session.query(User).count()
            promos_count = session.query(PromoCode).filter_by(is_active=True).count()
            tickets_open = session.query(Ticket).filter_by(status='open').count()
            tickets_closed = session.query(Ticket).filter_by(status='closed').count()
            usage_count = session.query(PromoUsage).count()
        finally:
            session.close()
        
        message = f"📊 СТАТИСТИКА\n\n"
        message += f"👥 Пользователей: {users_count}\n"
        message += f"👑 Администраторов: {len(self.admin_ids)}\n"
        message += f"🎮 Серверов: {len(self.servers_config)}\n"
        message += f"🎁 Активных промокодов: {promos_count}\n"
        message += f"📈 Использований промокодов: {usage_count}\n"
        message += f"🎫 Тикетов (открыто/закрыто): {tickets_open}/{tickets_closed}"
        
        self.send_message(admin_id, message, self.keyboards.admin_keyboard())
    
    def show_users_list(self, admin_id):
        """Список пользователей"""
        if not self.is_admin(admin_id):
            return
        
        users = self.db.get_all_users()
        message = f"👥 ПОЛЬЗОВАТЕЛИ (всего: {len(users)})\n\n"
        
        for user in users[:20]:
            is_admin = "👑" if user.vk_id in self.admin_ids else "👤"
            message += f"{is_admin} @id{user.vk_id} ({user.first_name} {user.last_name})\n"
            message += f"  📅 {user.registered_at.strftime('%d.%m.%Y')}\n"
        
        self.send_message(admin_id, message, self.keyboards.admin_keyboard())
    
    def start_broadcast(self, admin_id):
        """Начало рассылки"""
        if not self.is_admin(admin_id):
            return
        
        users = self.db.get_all_users()
        self.user_states[admin_id] = 'waiting_broadcast'
        self.send_message(admin_id, f"📢 Введите текст рассылки\n(будет отправлено {len(users)} пользователям):", 
                        self.keyboards.back_keyboard())
    
    def send_broadcast(self, admin_id, text):
        """Отправка рассылки"""
        if not self.is_admin(admin_id):
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
