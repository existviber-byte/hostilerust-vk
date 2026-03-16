import sys
import logging
import traceback

# Настраиваем логирование ВСЕГО
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/bot_debug.log', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info("="*60)
logger.info("ЗАПУСК БОТА В РЕЖИМЕ ОТЛАДКИ")
logger.info("="*60)

try:
    # Импортируем всё по порядку и проверяем каждый импорт
    logger.info("Импорт config...")
    import config
    logger.info(f"config.TOKEN = {'Задан' if config.TOKEN else 'НЕ ЗАДАН!'}")
    logger.info(f"config.GROUP_ID = {config.GROUP_ID}")
    logger.info(f"config.ADMIN_IDS = {config.ADMIN_IDS}")
    
    logger.info("Импорт database...")
    from database import Database
    
    logger.info("Импорт keyboards...")
    from keyboards import Keyboards
    
    logger.info("Импорт vk_api...")
    import vk_api
    from vk_api.longpoll import VkLongPoll, VkEventType
    from vk_api.utils import get_random_id
    
    logger.info("Все импорты успешны!")
    
    # Пробуем создать экземпляр бота
    logger.info("Создание экземпляра бота...")
    
    class DebugBot:
        def __init__(self):
            logger.info("Инициализация VkApi...")
            self.vk = vk_api.VkApi(token=config.TOKEN)
            
            logger.info("Создание LongPoll...")
            self.longpoll = VkLongPoll(self.vk)
            
            logger.info("Получение API...")
            self.vk_session = self.vk.get_api()
            
            logger.info("Создание Database...")
            self.db = Database()
            
            logger.info("Создание Keyboards...")
            self.keyboards = Keyboards()
            
            self.user_states = {}
            logger.info("✅ Бот инициализирован!")
        
        def send_message(self, user_id, message, keyboard=None, attachment=None):
            try:
                logger.info(f"Отправка сообщения {user_id}: {message[:50]}...")
                params = {
                    'user_id': user_id,
                    'message': message,
                    'random_id': get_random_id(),
                }
                if keyboard:
                    params['keyboard'] = keyboard.get_keyboard()
                self.vk_session.messages.send(**params)
                logger.info("Сообщение отправлено")
                return True
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")
                logger.error(traceback.format_exc())
                return False
        
        def handle_message(self, user_id, message, payload=None):
            logger.info(f"Обработка сообщения от {user_id}: {message}")
            try:
                if message.lower() in ['начать', 'старт', 'start', 'меню', 'привет']:
                    logger.info("Команда 'начать' - отправляем меню")
                    
                    # Пробуем получить имя пользователя
                    try:
                        user_info = self.vk_session.users.get(user_ids=user_id)[0]
                        name = user_info['first_name']
                        welcome = f"🦀 Добро пожаловать, {name}! 🦀\n\nБот работает в тестовом режиме."
                    except:
                        welcome = "🦀 Добро пожаловать в Hostile Rust! 🦀"
                    
                    self.send_message(user_id, welcome, self.keyboards.main_keyboard())
                else:
                    logger.info(f"Неизвестная команда: {message}")
                    self.send_message(user_id, f"Я получил: '{message}'. Напишите 'начать' для меню.")
            
            except Exception as e:
                logger.error(f"Ошибка в handle_message: {e}")
                logger.error(traceback.format_exc())
                self.send_message(user_id, "❌ Ошибка обработки команды")
        
        def run(self):
            logger.info("Запуск основного цикла...")
            print("\n" + "="*60)
            print("✅ DEBUG БОТ ЗАПУЩЕН!")
            print("📝 Отправьте 'начать' в сообщения группы")
            print("="*60 + "\n")
            
            for event in self.longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                    logger.info(f"Событие: {event.user_id} -> {event.text}")
                    self.handle_message(event.user_id, event.text, event.payload)
    
    # Запускаем бота
    bot = DebugBot()
    bot.run()
    
except Exception as e:
    logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
    logger.critical(traceback.format_exc())
    print(f"\n❌ Ошибка: {e}")
    print("Проверьте логи в /tmp/bot_debug.log")
