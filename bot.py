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
import pytz

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
        
        # Устанавливаем МСК часовой пояс для всего бота
        self.msk_tz = pytz.timezone('Europe/Moscow')
        
        self.db = Database()
        self.vk = vk_api.VkApi(token=TOKEN)
        self.longpoll = VkLongPoll(self.vk)
        self.vk_api = self.vk.get_api()
        self.keyboards = Keyboards()
        self.user_states = {}
        self.temp_notes = {}
        
        self.admin_ids = self.load_admins()
        self.servers_config = self.load_servers_config()
        self.load_notes()
        self.load_wipe_subscribers()
        
        self.start_reminder_checker()
        self.start_wipe_checker()
        
        log.info("✅ VK Бот Hostile Rust запущен!")
        log.info(f"👑 Администраторы: {self.admin_ids}")
        log.info(f"🎮 Загружено серверов: {len(self.servers_config)}")
        log.info(f"📝 Загружено заметок: {sum(len(v) for v in self.notes.values())}")
        log.info(f"🔔 Подписчиков на вайпы: {len(self.wipe_subscribers)}")
        log.info(f"🕐 Часовой пояс: МСК (Europe/Moscow)")
    
    # ========== ЗАГРУЗКА ПОДПИСЧИКОВ ==========
    
    def load_wipe_subscribers(self):
        DATA_DIR = Path("data")
        SUBSCRIBERS_FILE = DATA_DIR / "wipe_subscribers.json"
        
        try:
            if SUBSCRIBERS_FILE.exists() and SUBSCRIBERS_FILE.stat().st_size > 0:
                with open(SUBSCRIBERS_FILE, 'r', encoding='utf-8') as f:
                    self.wipe_subscribers = json.load(f)
                    log.info("✅ Подписчики на вайпы загружены")
            else:
                self.wipe_subscribers = []
                DATA_DIR.mkdir(exist_ok=True)
                self.save_wipe_subscribers()
        except (json.JSONDecodeError, FileNotFoundError) as e:
            log.error(f"❌ Ошибка загрузки подписчиков: {e}")
            self.wipe_subscribers = []
            self.save_wipe_subscribers()
    
    def save_wipe_subscribers(self):
        DATA_DIR = Path("data")
        SUBSCRIBERS_FILE = DATA_DIR / "wipe_subscribers.json"
        with open(SUBSCRIBERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.wipe_subscribers, f, indent=2, ensure_ascii=False)
        log.info("💾 Подписчики на вайпы сохранены")
    
    # ========== ПРОВЕРКА ВАЙПОВ (МСК) ==========
    
    def get_next_wipe_date(self, server_key):
        """Получение следующей даты вайпа в МСК"""
        server = self.servers_config.get(server_key)
        if not server:
            return None
        
        now = datetime.now(self.msk_tz)
        weeks_interval = server.get('wipe_interval', 1)
        
        if weeks_interval > 1:  # x2 сервер (раз в 2 недели)
            # Находим ближайший четверг
            days_until_thursday = (3 - now.weekday()) % 7
            if days_until_thursday == 0 and now.hour >= 12:
                days_until_thursday = 7
            
            next_thursday = now + timedelta(days=days_until_thursday)
            
            # Определяем время вайпа (первый четверг месяца - 22:00, иначе 12:00)
            is_first_thursday = (next_thursday.day <= 7)
            wipe_hour = 22 if is_first_thursday else 12
            
            wipe_date = next_thursday.replace(hour=wipe_hour, minute=0, second=0, microsecond=0)
            
            # Для x2 сервера: вайп только по четным неделям (относительно 06.02.2025)
            epoch = datetime(2025, 2, 6, 12, 0, 0, tzinfo=self.msk_tz)
            weeks_since_epoch = (wipe_date - epoch).days // 7
            
            if weeks_since_epoch % 2 == 1:
                wipe_date += timedelta(weeks=2)
                # Пересчитываем время
                is_first_thursday = (wipe_date.day <= 7)
                wipe_hour = 22 if is_first_thursday else 12
                wipe_date = wipe_date.replace(hour=wipe_hour, minute=0, second=0, microsecond=0)
            
            return wipe_date
        
        else:  # x100 сервер (раз в 1 неделю)
            days_until_thursday = (3 - now.weekday()) % 7
            if days_until_thursday == 0 and now.hour >= 22:
                days_until_thursday = 7
            
            next_thursday = now + timedelta(days=days_until_thursday)
            
            is_first_thursday = (next_thursday.day <= 7)
            wipe_hour = 22 if is_first_thursday else 12
            
            return next_thursday.replace(hour=wipe_hour, minute=0, second=0, microsecond=0)
    
    def start_wipe_checker(self):
        """Запуск проверки вайпов с МСК временем"""
        def check_wipes():
            last_notified = {}  # Словарь для отслеживания отправленных уведомлений
            
            while True:
                try:
                    now = datetime.now(self.msk_tz)
                    log.info(f"🔍 Проверка вайпов: {now.strftime('%Y-%m-%d %H:%M:%S')} МСК")
                    
                    for server_key, server in self.servers_config.items():
                        next_wipe = self.get_next_wipe_date(server_key)
                        if not next_wipe:
                            continue
                        
                        time_until_wipe = (next_wipe - now).total_seconds()
                        hours_until = time_until_wipe / 3600
                        notify_key = f"{server_key}_{next_wipe.strftime('%Y%m%d')}"
                        
                        # Логирование для отладки
                        log.debug(f"  {server['name']}: вайп {next_wipe.strftime('%d.%m.%Y %H:%M')}, до вайпа {hours_until:.2f} ч.")
                        
                        # Уведомление за 1 час (с запасом 50-70 минут)
                        # Проверяем, что уведомление ещё не отправлено
                        if 0.83 <= hours_until <= 1.2 and notify_key not in last_notified:
                            server_name = server['name']
                            is_first_thursday = self.is_first_thursday_of_month(next_wipe)
                            wipe_time = "22:00 МСК" if is_first_thursday else "12:00 МСК"
                            
                            message = f"⚠️ ВНИМАНИЕ!\n\n"
                            message += f"🎮 {server_name}\n"
                            message += f"💣 Вайп через 1 час!\n"
                            message += f"📅 {next_wipe.strftime('%d.%m.%Y')}\n"
                            message += f"⏰ Время: {wipe_time}\n\n"
                            message += f"🔄 Не забудьте подготовиться!"
                            
                            log.info(f"🔔 Отправка уведомлений о вайпе для {server_name} ({len(self.wipe_subscribers)} подписчиков)")
                            
                            for subscriber_id in self.wipe_subscribers:
                                try:
                                    self.send_message(subscriber_id, message)
                                    time.sleep(0.5)
                                except Exception as e:
                                    log.error(f"Ошибка отправки уведомления {subscriber_id}: {e}")
                            
                            # Запоминаем, что отправили уведомление для этого вайпа
                            last_notified[notify_key] = True
                            log.info(f"✅ Уведомление для {server_name} отправлено, флаг установлен")
                        
                        # Автоматически удаляем флаги через 2 часа после вайпа
                        if notify_key in last_notified and time_until_wipe < -7200:  # 2 часа после вайпа
                            del last_notified[notify_key]
                            log.info(f"🗑 Флаг уведомления для {server_name} удалён (прошло 2 часа после вайпа)")
                    
                except Exception as e:
                    log.error(f"❌ Ошибка проверки вайпов: {e}")
                
                time.sleep(60)  # Проверка раз в минуту
        
        wipe_thread = threading.Thread(target=check_wipes, daemon=True)
        wipe_thread.start()
        log.info("⏰ Запущена проверка вайпов (МСК время)")
    
    def load_notes(self):
        DATA_DIR = Path("data")
        NOTES_FILE = DATA_DIR / "admin_notes.json"
        
        try:
            if NOTES_FILE.exists() and NOTES_FILE.stat().st_size > 0:
                with open(NOTES_FILE, 'r', encoding='utf-8') as f:
                    self.notes = json.load(f)
                    log.info("✅ Заметки загружены")
            else:
                self.notes = {}
                DATA_DIR.mkdir(exist_ok=True)
                self.save_notes()
        except (json.JSONDecodeError, FileNotFoundError) as e:
            log.error(f"❌ Ошибка загрузки заметок: {e}")
            self.notes = {}
            self.save_notes()
    
    def save_notes(self):
        DATA_DIR = Path("data")
        NOTES_FILE = DATA_DIR / "admin_notes.json"
        with open(NOTES_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.notes, f, indent=2, ensure_ascii=False)
        log.info("💾 Заметки сохранены")
    
    def start_reminder_checker(self):
        def check_reminders():
            while True:
                try:
                    now = datetime.now(self.msk_tz)
                    for admin_id, admin_notes in self.notes.items():
                        admin_id_int = int(admin_id)
                        for note in admin_notes:
                            reminder_time = note.get('reminder_time')
                            if reminder_time and not note.get('reminded', False):
                                reminder_dt = datetime.fromisoformat(reminder_time)
                                if reminder_dt.tzinfo is None:
                                    reminder_dt = self.msk_tz.localize(reminder_dt)
                                if reminder_dt <= now:
                                    message = f"📝 НАПОМИНАНИЕ!\n\n"
                                    message += f"📌 {note['title']}\n\n"
                                    message += f"📄 {note['content']}\n\n"
                                    message += f"⏰ Создано: {note['created_at'][:16]}\n"
                                    message += f"🔔 Напоминание сработало!"
                                    self.send_message(admin_id_int, message)
                                    note['reminded'] = True
                                    self.save_notes()
                                    log.info(f"🔔 Отправлено напоминание админу {admin_id}: {note['title']}")
                except Exception as e:
                    log.error(f"❌ Ошибка проверки напоминаний: {e}")
                time.sleep(60)
        
        reminder_thread = threading.Thread(target=check_reminders, daemon=True)
        reminder_thread.start()
        log.info("⏰ Запущена проверка напоминаний")
    
    def load_admins(self):
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
        
        admins = list(ADMIN_IDS)
        DATA_DIR.mkdir(exist_ok=True)
        with open(ADMIN_FILE, 'w', encoding='utf-8') as f:
            json.dump(admins, f, indent=2, ensure_ascii=False)
        
        log.info("✅ Создан новый список администраторов")
        return admins
    
    def save_admins(self):
        DATA_DIR = Path("data")
        ADMIN_FILE = DATA_DIR / "admins.json"
        with open(ADMIN_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.admin_ids, f, indent=2, ensure_ascii=False)
        log.info("💾 Список администраторов сохранен")
    
    def load_servers_config(self):
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
        DATA_DIR = Path("data")
        SERVERS_FILE = DATA_DIR / "servers.json"
        with open(SERVERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.servers_config, f, indent=2, ensure_ascii=False)
        log.info("💾 Конфигурация серверов сохранена")
    
    def reload_servers_config(self):
        try:
            self.servers_config = self.load_servers_config()
            log.info("🔄 Конфигурация серверов принудительно перезагружена")
            return True
        except Exception as e:
            log.error(f"❌ Ошибка перезагрузки конфигурации серверов: {e}")
            return False
    
    def is_admin(self, user_id):
        return user_id in self.admin_ids
    
    def send_message(self, user_id, message, keyboard=None, attachment=None):
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
        for admin_id in self.admin_ids:
            self.send_message(admin_id, message, keyboard)
    
    def handle_message(self, user_id, text, payload=None):
        log.info(f"📨 Сообщение от {user_id}: {text[:50] if text else ''}")
        
        try:
            user_info = self.vk_api.users.get(user_ids=user_id)[0]
            first_name = user_info.get('first_name', '')
            last_name = user_info.get('last_name', '')
            self.db.add_user(user_id, first_name, last_name)
        except Exception as e:
            log.error(f"❌ Ошибка регистрации пользователя: {e}")
        
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
                elif command == 'create_note':
                    self.start_create_note(user_id)
                    return
                elif command == 'list_notes':
                    self.list_notes(user_id)
                    return
                elif command.startswith('delete_note_'):
                    note_id = int(command.replace('delete_note_', ''))
                    self.delete_note(user_id, note_id)
                    return
                elif command.startswith('view_note_'):
                    note_id = int(command.replace('view_note_', ''))
                    self.view_note(user_id, note_id)
                    return
                elif command == 'subscribe_wipe':
                    self.subscribe_to_wipe(user_id)
                    return
                elif command == 'unsubscribe_wipe':
                    self.unsubscribe_from_wipe(user_id)
                    return
                elif command == 'no_reminder':
                    self.create_note_reminder(user_id, 'без напоминания')
                    return
            except Exception as e:
                log.error(f"❌ Ошибка обработки payload: {e}")
        
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
            elif state == 'waiting_note_title':
                self.create_note_title(user_id, text)
                return
            elif state == 'waiting_note_content':
                self.create_note_content(user_id, text)
                return
            elif state == 'waiting_note_reminder':
                self.create_note_reminder(user_id, text)
                return
        
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
        elif text_lower in ['🔔 подписаться на вайпы', 'подписаться на вайпы']:
            self.subscribe_to_wipe(user_id)
        elif text_lower in ['🔕 отписаться от вайпов', 'отписаться от вайпов']:
            self.unsubscribe_from_wipe(user_id)
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
            elif text_lower in ['📝 заметки', 'заметки']:
                self.show_notes_menu(user_id)
            else:
                self.offer_ticket_creation(user_id)
        elif self.check_promo_code(user_id, text):
            pass
        else:
            self.offer_ticket_creation(user_id)
    
    # ========== ПОДПИСКА НА УВЕДОМЛЕНИЯ О ВАЙПАХ ==========
    
    def subscribe_to_wipe(self, user_id):
        if user_id in self.wipe_subscribers:
            self.send_message(user_id, "🔔 Вы уже подписаны на уведомления о вайпах!")
            return
        
        self.wipe_subscribers.append(user_id)
        self.save_wipe_subscribers()
        
        message = "✅ Вы подписались на уведомления о вайпах!\n\n"
        message += "🔔 Бот будет присылать вам оповещения за 1 час до вайпа на серверах:\n"
        message += "• x2 сервер (раз в 2 недели)\n"
        message += "• x100 сервер (каждую неделю)\n\n"
        message += "❌ Чтобы отписаться, напишите: Отписаться от вайпов"
        
        self.send_message(user_id, message)
        log.info(f"🔔 Пользователь {user_id} подписался на уведомления о вайпах")
    
    def unsubscribe_from_wipe(self, user_id):
        if user_id not in self.wipe_subscribers:
            self.send_message(user_id, "🔕 Вы не были подписаны на уведомления о вайпах!")
            return
        
        self.wipe_subscribers.remove(user_id)
        self.save_wipe_subscribers()
        
        message = "❌ Вы отписались от уведомлений о вайпах!\n\n"
        message += "Чтобы снова подписаться, напишите: Подписаться на вайпы"
        
        self.send_message(user_id, message)
        log.info(f"🔕 Пользователь {user_id} отписался от уведомлений о вайпах")
    
    # ========== ЗАМЕТКИ ДЛЯ АДМИНОВ ==========
    
    def show_notes_menu(self, admin_id):
        if not self.is_admin(admin_id):
            return
        
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button('➕ Создать заметку', VkKeyboardColor.PRIMARY, 
                           payload={'command': 'create_note'})
        keyboard.add_button('📋 Список заметок', VkKeyboardColor.SECONDARY,
                           payload={'command': 'list_notes'})
        keyboard.add_line()
        keyboard.add_button('◀️ Назад в админку', VkKeyboardColor.SECONDARY,
                           payload={'command': 'admin_back'})
        
        message = "📝 УПРАВЛЕНИЕ ЗАМЕТКАМИ\n\n"
        message += "Здесь вы можете создавать заметки с напоминаниями.\n"
        message += "Бот сам напомнит вам в указанное время в личные сообщения.\n\n"
        message += "📌 Напоминания можно установить:\n"
        message += "• через minutes (например: 30m)\n"
        message += "• через hours (например: 2h)\n"
        message += "• через days (например: 3d)\n"
        message += "• на конкретное время (например: 2024-12-31 23:59)"
        
        self.send_message(admin_id, message, keyboard)
    
    def start_create_note(self, admin_id):
        if not self.is_admin(admin_id):
            return
        
        self.user_states[admin_id] = 'waiting_note_title'
        self.send_message(admin_id, "📝 Создание заметки\n\nВведите название заметки (не более 100 символов):", 
                         self.keyboards.back_keyboard())
    
    def create_note_title(self, admin_id, title):
        if not self.is_admin(admin_id):
            return
        
        if not title or len(title.strip()) < 1:
            self.send_message(admin_id, "❌ Название не может быть пустым. Попробуйте снова:")
            return
        
        if len(title) > 100:
            self.send_message(admin_id, "❌ Название слишком длинное (максимум 100 символов). Попробуйте снова:")
            return
        
        self.temp_notes[admin_id] = {'title': title.strip()}
        self.user_states[admin_id] = 'waiting_note_content'
        
        self.send_message(admin_id, f"✅ Название: {title}\n\nТеперь введите текст заметки (не более 1000 символов):", 
                         self.keyboards.back_keyboard())
    
    def create_note_content(self, admin_id, content):
        if not self.is_admin(admin_id):
            return
        
        if not content or len(content.strip()) < 1:
            self.send_message(admin_id, "❌ Текст не может быть пустым. Попробуйте снова:")
            return
        
        if len(content) > 1000:
            self.send_message(admin_id, "❌ Текст слишком длинный (максимум 1000 символов). Попробуйте снова:")
            return
        
        self.temp_notes[admin_id]['content'] = content.strip()
        self.user_states[admin_id] = 'waiting_note_reminder'
        
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button('⏰ Без напоминания', VkKeyboardColor.SECONDARY,
                           payload={'command': 'no_reminder'})
        
        message = "✅ Текст сохранен!\n\n"
        message += "📌 Установите время напоминания:\n\n"
        message += "Примеры:\n"
        message += "• 30m - через 30 минут\n"
        message += "• 2h - через 2 часа\n"
        message += "• 3d - через 3 дня\n"
        message += "• 2024-12-31 23:59 - на конкретную дату\n\n"
        message += "Или нажмите кнопку Без напоминания"
        
        self.send_message(admin_id, message, keyboard)
    
    def create_note_reminder(self, admin_id, text):
        if not self.is_admin(admin_id):
            return
        
        reminder_time = None
        reminder_text = "Без напоминания"
        
        if text and text.lower() != 'без напоминания':
            try:
                text_lower = text.lower().strip()
                
                if text_lower.endswith('m'):
                    minutes = int(text_lower[:-1])
                    reminder_time = datetime.now(self.msk_tz) + timedelta(minutes=minutes)
                    reminder_text = f"Через {minutes} минут"
                elif text_lower.endswith('h'):
                    hours = int(text_lower[:-1])
                    reminder_time = datetime.now(self.msk_tz) + timedelta(hours=hours)
                    reminder_text = f"Через {hours} часов"
                elif text_lower.endswith('d'):
                    days = int(text_lower[:-1])
                    reminder_time = datetime.now(self.msk_tz) + timedelta(days=days)
                    reminder_text = f"Через {days} дней"
                else:
                    reminder_time = datetime.strptime(text, '%Y-%m-%d %H:%M')
                    reminder_time = self.msk_tz.localize(reminder_time)
                    reminder_text = reminder_time.strftime('%d.%m.%Y %H:%M')
                
                if reminder_time and reminder_time <= datetime.now(self.msk_tz):
                    self.send_message(admin_id, "❌ Время напоминания должно быть в будущем!")
                    return
                    
            except ValueError:
                self.send_message(admin_id, "❌ Неверный формат времени. Используйте: 30m, 2h, 3d или 2024-12-31 23:59")
                return
        
        admin_id_str = str(admin_id)
        if admin_id_str not in self.notes:
            self.notes[admin_id_str] = []
        
        note_id = len(self.notes[admin_id_str]) + 1
        
        note = {
            'id': note_id,
            'title': self.temp_notes[admin_id]['title'],
            'content': self.temp_notes[admin_id]['content'],
            'created_at': datetime.now(self.msk_tz).isoformat(),
            'reminder_time': reminder_time.isoformat() if reminder_time else None,
            'reminded': False,
            'reminder_text': reminder_text
        }
        
        self.notes[admin_id_str].append(note)
        self.save_notes()
        
        if admin_id in self.temp_notes:
            del self.temp_notes[admin_id]
        if admin_id in self.user_states:
            del self.user_states[admin_id]
        
        message = f"✅ Заметка создана!\n\n"
        message += f"📌 {note['title']}\n\n"
        message += f"📄 {note['content']}\n\n"
        message += f"⏰ Напоминание: {reminder_text}\n"
        message += f"🆔 ID заметки: {note_id}"
        
        self.send_message(admin_id, message, self.keyboards.admin_keyboard())
        log.info(f"📝 Админ {admin_id} создал заметку #{note_id}: {note['title']}")
    
    def list_notes(self, admin_id):
        if not self.is_admin(admin_id):
            return
        
        admin_id_str = str(admin_id)
        notes = self.notes.get(admin_id_str, [])
        
        if not notes:
            keyboard = VkKeyboard(inline=True)
            keyboard.add_button('➕ Создать заметку', VkKeyboardColor.PRIMARY,
                               payload={'command': 'create_note'})
            keyboard.add_button('◀️ Назад', VkKeyboardColor.SECONDARY,
                               payload={'command': 'admin_back'})
            self.send_message(admin_id, "📭 У вас нет заметок. Создайте первую заметку!", keyboard)
            return
        
        message = f"📝 ВАШИ ЗАМЕТКИ (всего: {len(notes)})\n\n"
        
        for note in notes[-10:]:
            status = "🔔" if note.get('reminder_time') and not note.get('reminded') else "📌"
            reminder_info = ""
            if note.get('reminder_time') and not note.get('reminded'):
                reminder_dt = datetime.fromisoformat(note['reminder_time'])
                if reminder_dt.tzinfo is None:
                    reminder_dt = self.msk_tz.localize(reminder_dt)
                if reminder_dt > datetime.now(self.msk_tz):
                    reminder_info = f" (напомнить: {reminder_dt.strftime('%d.%m %H:%M')})"
            
            message += f"{status} #{note['id']} - {note['title']}{reminder_info}\n"
            message += f"   📄 {note['content'][:50]}...\n\n"
        
        keyboard = VkKeyboard(inline=True)
        
        for note in notes[-5:]:
            keyboard.add_button(f"🔍 #{note['id']}", VkKeyboardColor.SECONDARY,
                               payload={'command': f'view_note_{note["id"]}'})
            keyboard.add_button(f"🗑 #{note['id']}", VkKeyboardColor.NEGATIVE,
                               payload={'command': f'delete_note_{note["id"]}'})
            keyboard.add_line()
        
        keyboard.add_button('➕ Создать заметку', VkKeyboardColor.PRIMARY,
                           payload={'command': 'create_note'})
        keyboard.add_line()
        keyboard.add_button('◀️ Назад в админку', VkKeyboardColor.SECONDARY,
                           payload={'command': 'admin_back'})
        
        self.send_message(admin_id, message, keyboard)
    
    def view_note(self, admin_id, note_id):
        if not self.is_admin(admin_id):
            return
        
        admin_id_str = str(admin_id)
        notes = self.notes.get(admin_id_str, [])
        
        for note in notes:
            if note['id'] == note_id:
                message = f"📌 ЗАМЕТКА #{note_id}\n\n"
                message += f"Название: {note['title']}\n\n"
                message += f"Текст:\n{note['content']}\n\n"
                message += f"Создано: {note['created_at'][:16]}\n"
                
                if note.get('reminder_time') and not note.get('reminded'):
                    reminder_dt = datetime.fromisoformat(note['reminder_time'])
                    if reminder_dt.tzinfo is None:
                        reminder_dt = self.msk_tz.localize(reminder_dt)
                    if reminder_dt > datetime.now(self.msk_tz):
                        message += f"Напоминание: {reminder_dt.strftime('%d.%m.%Y %H:%M')}\n"
                    else:
                        message += f"Напоминание: Ожидает отправки\n"
                elif note.get('reminded'):
                    message += f"Напоминание: ✅ Отправлено\n"
                else:
                    message += f"Напоминание: Не установлено\n"
                
                keyboard = VkKeyboard(inline=True)
                keyboard.add_button('🗑 Удалить', VkKeyboardColor.NEGATIVE,
                                   payload={'command': f'delete_note_{note_id}'})
                keyboard.add_line()
                keyboard.add_button('◀️ К списку', VkKeyboardColor.SECONDARY,
                                   payload={'command': 'list_notes'})
                keyboard.add_button('◀️ В админку', VkKeyboardColor.SECONDARY,
                                   payload={'command': 'admin_back'})
                
                self.send_message(admin_id, message, keyboard)
                return
        
        self.send_message(admin_id, f"❌ Заметка #{note_id} не найдена!")
    
    def delete_note(self, admin_id, note_id):
        if not self.is_admin(admin_id):
            return
        
        admin_id_str = str(admin_id)
        notes = self.notes.get(admin_id_str, [])
        
        for i, note in enumerate(notes):
            if note['id'] == note_id:
                title = note['title']
                notes.pop(i)
                for j, n in enumerate(notes):
                    n['id'] = j + 1
                self.save_notes()
                
                self.send_message(admin_id, f"✅ Заметка #{note_id} - {title} удалена!")
                log.info(f"🗑 Админ {admin_id} удалил заметку #{note_id}")
                self.list_notes(admin_id)
                return
        
        self.send_message(admin_id, f"❌ Заметка #{note_id} не найдена!")
    
    # ========== ОСТАЛЬНЫЕ МЕТОДЫ ==========
    
    def is_first_thursday_of_month(self, date):
        return date.day <= 7 and date.weekday() == 3
    
    def show_main_menu(self, user_id):
        try:
            user_info = self.vk_api.users.get(user_ids=user_id)[0]
            name = user_info['first_name']
            welcome = f"🔥 Привет, {name}!\n\n🎮 Добро пожаловать в Hostile Rust!\nВыберите действие:"
        except:
            welcome = "🔥 Добро пожаловать в Hostile Rust!\n\nВыберите действие:"
        
        self.send_message(user_id, welcome, self.keyboards.main_keyboard())
    
    def show_promocodes(self, user_id):
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
        
        if user_id in self.wipe_subscribers:
            message += "\n🔔 Вы подписаны на уведомления о вайпах"
        else:
            message += "\n🔕 Напишите Подписаться на вайпы, чтобы получать уведомления за час до вайпа"
        
        self.send_message(user_id, message, self.keyboards.servers_keyboard())
    
    def send_server_ip(self, user_id, server_key):
        self.reload_servers_config()
        server = self.servers_config.get(server_key)
        if server:
            self.send_message(user_id, f"📋 IP {server['name']}:\n{server['ip']}")
    
    def show_server_ips(self, user_id):
        self.reload_servers_config()
        message = "📋 IP СЕРВЕРОВ\n\n"
        for key, server in self.servers_config.items():
            message += f"{server['name']}:\n{server['ip']}\n\n"
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    def show_rules(self, user_id):
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
        message = f"🛒 МАГАЗИН HOSTILE RUST\n\n{SHOP_URL}\n\n💡 Перейдите по ссылке для пополнения баланса!"
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    def show_wipe_info(self, user_id):
        self.reload_servers_config()
        now = datetime.now(self.msk_tz)
        
        message = "💣 ИНФОРМАЦИЯ О ВАЙПАХ\n\n"
        message += "📌 Все вайпы проходят по четвергам\n"
        message += "🕐 Обычное время: 12:00 МСК\n"
        message += "🕙 Первый четверг месяца: 22:00 МСК\n"
        message += f"🕐 Текущее время: {now.strftime('%H:%M:%S')} МСК\n\n"
        
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
        message += "🔄 Вайпы x100 сервера проходят строго раз в 7 дней\n\n"
        
        if user_id in self.wipe_subscribers:
            message += "🔔 Вы подписаны на уведомления о вайпах (за час)\n"
            message += "❌ Отписаться: Отписаться от вайпов"
        else:
            message += "🔕 Подписаться на уведомления: Подписаться на вайпы"
        
        self.send_message(user_id, message, self.keyboards.back_keyboard())
    
    def offer_ticket_creation(self, user_id):
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
        session = self.db.get_session()
        try:
            user = session.query(User).filter_by(vk_id=user_id).first()
            if user:
                tickets = session.query(Ticket).filter_by(user_id=user.id, status='open').all()
                if tickets:
                    last_ticket = tickets[-1]
                    if (datetime.now(self.msk_tz) - last_ticket.created_at).total_seconds() < TICKET_COOLDOWN_MINUTES * 60:
                        self.send_message(user_id, f"⏳ Тикет можно создавать раз в {TICKET_COOLDOWN_MINUTES} минут", 
                                        self.keyboards.back_keyboard())
                        return
        finally:
            session.close()
        
        self.user_states[user_id] = 'waiting_ticket'
        self.send_message(user_id, "📝 Опишите ваш вопрос подробно:", self.keyboards.back_keyboard())
    
    def create_ticket(self, user_id, text):
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
                message = f"🟢 ТИКЕТ #{t.id}\n👤 От: {user_name}\n📅 {t.created_at.strftime('%d.%m.%Y %H:%M')}\n📝 {t.title}\n"
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
                keyboard.add_button(f'❌ Закрыть #{t.id} ({user_name[:15]}...)', VkKeyboardColor.NEGATIVE,
                                  payload={'command': f'admin_close_{t.id}'})
                keyboard.add_line()
            keyboard.add_button('◀️ Назад', VkKeyboardColor.SECONDARY, payload={'command': 'admin_back'})
            self.send_message(admin_id, "📋 Выберите тикет для закрытия:", keyboard)
        finally:
            session.close()
    
    def start_ticket_answer(self, admin_id, ticket_id):
        if not self.is_admin(admin_id):
            return
        self.user_states[admin_id] = f'ticket_reply_{ticket_id}'
        self.send_message(admin_id, f"✏️ Введите ответ на тикет #{ticket_id}:", self.keyboards.back_keyboard())
    
    def reply_to_ticket(self, admin_id, ticket_id, text):
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
            msg = TicketMessage(ticket_id=ticket_id, user_id=admin_id, message=text, is_admin=True)
            session.add(msg)
            session.commit()
        finally:
            session.close()
        
        self.send_message(user_id, f"📩 ОТВЕТ НА ТИКЕТ #{ticket_id}\n\n👑 Администратор:\n{text}")
        if admin_id in self.user_states:
            del self.user_states[admin_id]
        self.send_message(admin_id, f"✅ Ответ отправлен!", self.keyboards.admin_keyboard())
    
    def close_ticket_admin(self, admin_id, ticket_id):
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
            ticket.closed_at = datetime.now(self.msk_tz)
            session.commit()
        finally:
            session.close()
        
        self.send_message(user_id, f"🔒 Тикет #{ticket_id} закрыт администратором\n\nЕсли остались вопросы, создайте новый тикет.")
        self.send_message(admin_id, f"✅ Тикет #{ticket_id} закрыт!", self.keyboards.admin_keyboard())
    
    # ========== ПРОМОКОДЫ ==========
    
    def check_promo_code(self, user_id, text):
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
                        used = session.query(PromoUsage).filter_by(user_id=user.id, promo_id=promo_obj.id).first()
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
        if not self.is_admin(admin_id):
            return
        self.user_states[admin_id] = 'waiting_promo_add'
        self.send_message(admin_id, "➕ Введите новый промокод:", self.keyboards.back_keyboard())
    
    def add_promo(self, admin_id, code):
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
        
        promos.append({"code": code, "date": datetime.now(self.msk_tz).isoformat()})
        with open(DATA_PROMO, 'w', encoding='utf-8') as f:
            json.dump(promos, f, indent=2, ensure_ascii=False)
        
        self.db.add_promo(code, "Промокод")
        if admin_id in self.user_states:
            del self.user_states[admin_id]
        self.send_message(admin_id, f"✅ Промокод {code} добавлен!", self.keyboards.admin_keyboard())
    
    def show_promo_list(self, admin_id):
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
        keyboard.add_button('◀️ Назад', VkKeyboardColor.SECONDARY, payload={'command': 'admin_back'})
        self.send_message(admin_id, "➖ Выберите промокод для удаления:", keyboard)
    
    def delete_promo(self, admin_id, code):
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
        if not self.is_admin(admin_id):
            return
        
        session = self.db.get_session()
        try:
            recent_usages = session.query(PromoUsage).order_by(PromoUsage.used_at.desc()).limit(10).all()
            message = "📈 СТАТИСТИКА ПРОМОКОДОВ\n\n🕒 ПОСЛЕДНИЕ АКТИВАЦИИ:\n"
            
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
                        message += f"• {user_name}\n  Код: {promo.code}\n  Дата: {usage.used_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            else:
                message += "Нет активаций\n"
            
            total_usages = session.query(PromoUsage).count()
            message += f"\n📊 ВСЕГО АКТИВАЦИЙ: {total_usages}"
        finally:
            session.close()
        
        self.send_message(admin_id, message, self.keyboards.admin_keyboard())
    
    # ========== УПРАВЛЕНИЕ АДМИНАМИ ==========
    
    def show_admin_management(self, admin_id):
        if not self.is_admin(admin_id):
            return
        
        message = "👑 УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ\n\n📋 ТЕКУЩИЕ АДМИНЫ:\n"
        for aid in self.admin_ids:
            try:
                user_info = self.vk_api.users.get(user_ids=aid)[0]
                user_name = f"{user_info['first_name']} {user_info['last_name']}"
                message += f"• {user_name} (id{aid})\n"
            except:
                message += f"• id{aid}\n"
        
        self.send_message(admin_id, message, self.keyboards.admin_management_keyboard())
    
    def start_add_admin_flow(self, admin_id):
        if not self.is_admin(admin_id):
            return
        self.user_states[admin_id] = 'waiting_add_admin'
        self.send_message(admin_id, "➕ Введите ID пользователя ВК для добавления в админы:", self.keyboards.back_keyboard())
    
    def process_add_admin(self, admin_id, text):
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
            self.send_message(admin_id, f"✅ {user_name} (id{new_admin_id}) добавлен в администраторы!", self.keyboards.admin_keyboard())
            self.send_message(new_admin_id, "🎉 Поздравляем! Вы назначены администратором Hostile Rust!")
        except ValueError:
            self.send_message(admin_id, "❌ Неверный ID. Введите числовой ID пользователя")
        finally:
            if admin_id in self.user_states:
                del self.user_states[admin_id]
    
    def start_remove_admin_flow(self, admin_id):
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
        keyboard.add_button('◀️ Назад', VkKeyboardColor.SECONDARY, payload={'command': 'admin_manage_admins'})
        self.send_message(admin_id, "➖ Выберите админа для удаления:", keyboard)
    
    def remove_admin(self, admin_id, remove_admin_id):
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
        
        self.send_message(admin_id, f"✅ {user_name} удален из администраторов!", self.keyboards.admin_keyboard())
        self.send_message(remove_admin_id, "ℹ️ Вы были удалены из администраторов Hostile Rust")
    
    # ========== РЕДАКТИРОВАНИЕ СЕРВЕРОВ ==========
    
    def show_servers_editor(self, admin_id):
        if not self.is_admin(admin_id):
            return
        self.reload_servers_config()
        message = "🔧 РЕДАКТОР СЕРВЕРОВ\n\nВыберите сервер для редактирования:\n\n"
        for key, server in self.servers_config.items():
            message += f"🟢 {server['name']}\n   IP: {server['ip']}\n   Вайп: раз в {server.get('wipe_interval', 1)} нед.\n\n"
        self.send_message(admin_id, message, self.keyboards.servers_editor_keyboard(self.servers_config))
    
    def start_edit_server(self, admin_id, server_key):
        if not self.is_admin(admin_id):
            return
        self.reload_servers_config()
        server = self.servers_config.get(server_key)
        if not server:
            self.send_message(admin_id, "❌ Сервер не найден")
            return
        self.send_message(admin_id, f"✏️ РЕДАКТИРОВАНИЕ: {server['name']}\n\nЧто хотите изменить?", 
                         self.keyboards.server_edit_options_keyboard(server_key))
    
    def start_edit_server_name(self, admin_id, server_key):
        if not self.is_admin(admin_id):
            return
        self.user_states[admin_id] = f'edit_server_name_{server_key}'
        self.send_message(admin_id, "📝 Введите новое название сервера:", self.keyboards.back_keyboard())
    
    def edit_server_name(self, admin_id, server_key, text):
        if not self.is_admin(admin_id):
            return
        server = self.servers_config.get(server_key)
        if server:
            server['name'] = text.strip()
            self.save_servers_config()
            self.reload_servers_config()
            self.send_message(admin_id, f"✅ Название сервера изменено на: {text.strip()}", self.keyboards.admin_keyboard())
        if admin_id in self.user_states:
            del self.user_states[admin_id]
    
    def start_edit_server_ip(self, admin_id, server_key):
        if not self.is_admin(admin_id):
            return
        self.user_states[admin_id] = f'edit_server_ip_{server_key}'
        self.send_message(admin_id, "🌐 Введите новый IP адрес сервера (формат: ip:port):", self.keyboards.back_keyboard())
    
    def edit_server_ip(self, admin_id, server_key, text):
        if not self.is_admin(admin_id):
            return
        server = self.servers_config.get(server_key)
        if server:
            new_ip = text.strip()
            if ':' not in new_ip:
                self.send_message(admin_id, "❌ Неверный формат IP. Используйте формат: ip:port (например: 5.42.211.191:35000)")
                if admin_id in self.user_states:
                    del self.user_states[admin_id]
                return
            server['ip'] = new_ip
            self.save_servers_config()
            self.reload_servers_config()
            self.send_message(admin_id, f"✅ IP сервера изменен на: {new_ip}", self.keyboards.admin_keyboard())
        if admin_id in self.user_states:
            del self.user_states[admin_id]
    
    def start_edit_server_wipe(self, admin_id, server_key):
        if not self.is_admin(admin_id):
            return
        self.user_states[admin_id] = f'edit_server_wipe_{server_key}'
        self.send_message(admin_id, "🔄 Введите новый интервал вайпа в неделях (1 или 2):", self.keyboards.back_keyboard())
    
    def edit_server_wipe(self, admin_id, server_key, text):
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
                server['wipe_interval'] = interval
                self.save_servers_config()
                self.reload_servers_config()
                self.send_message(admin_id, f"✅ Интервал вайпа изменен на: {interval} нед.", self.keyboards.admin_keyboard())
        except ValueError:
            self.send_message(admin_id, "❌ Введите число 1 или 2")
        finally:
            if admin_id in self.user_states:
                del self.user_states[admin_id]
    
    # ========== АДМИНСКИЕ ФУНКЦИИ ==========
    
    def show_admin_menu(self, admin_id):
        if not self.is_admin(admin_id):
            return
        self.send_message(admin_id, "👑 АДМИН-ПАНЕЛЬ\n\nВыберите действие:", self.keyboards.admin_keyboard())
    
    def show_stats(self, admin_id):
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
        
        message = f"📊 СТАТИСТИКА\n\n👥 Пользователей: {users_count}\n👑 Администраторов: {len(self.admin_ids)}\n🎮 Серверов: {len(self.servers_config)}\n🎁 Активных промокодов: {promos_count}\n📈 Использований промокодов: {usage_count}\n🎫 Тикетов (открыто/закрыто): {tickets_open}/{tickets_closed}\n🔔 Подписчиков на вайпы: {len(self.wipe_subscribers)}"
        self.send_message(admin_id, message, self.keyboards.admin_keyboard())
    
    def show_users_list(self, admin_id):
        if not self.is_admin(admin_id):
            return
        users = self.db.get_all_users()
        message = f"👥 ПОЛЬЗОВАТЕЛИ (всего: {len(users)})\n\n"
        for user in users[:20]:
            is_admin = "👑" if user.vk_id in self.admin_ids else "👤"
            message += f"{is_admin} @id{user.vk_id} ({user.first_name} {user.last_name})\n  📅 {user.registered_at.strftime('%d.%m.%Y')}\n"
        self.send_message(admin_id, message, self.keyboards.admin_keyboard())
    
    def start_broadcast(self, admin_id):
        if not self.is_admin(admin_id):
            return
        users = self.db.get_all_users()
        self.user_states[admin_id] = 'waiting_broadcast'
        self.send_message(admin_id, f"📢 Введите текст рассылки\n(будет отправлено {len(users)} пользователям):", self.keyboards.back_keyboard())
    
    def send_broadcast(self, admin_id, text):
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
            self.send_message(admin_id, f"✅ Рассылка завершена!\nОтправлено: {sent}", self.keyboards.admin_keyboard())
        
        threading.Thread(target=broadcast, daemon=True).start()
        if admin_id in self.user_states:
            del self.user_states[admin_id]
        self.send_message(admin_id, "⏳ Рассылка запущена...")
    
    def run(self):
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
                        threading.Thread(target=self.handle_message, args=(event.user_id, event.text, payload), daemon=True).start()
            except Exception as e:
                log.error(f"❌ Ошибка в главном цикле: {e}")
                time.sleep(5)

if __name__ == '__main__':
    bot = HostileRustVKBot()
    bot.run()
