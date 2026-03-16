import requests
from bs4 import BeautifulSoup
from config import SERVERS, WIPE_SCHEDULE, SHOP_URL
import time
from datetime import datetime

class ServerMonitor:
    def __init__(self):
        self.cache = {
            'online': {},
            'last_update': 0,
            'players': {}
        }
        self.cache_time = 60  # Обновление раз в минуту
    
    def get_server_online(self):
        """Парсит онлайн серверов с сайта мониторинга"""
        current_time = time.time()
        
        # Возвращаем кэш если он свежий
        if current_time - self.cache['last_update'] < self.cache_time:
            return self.cache['online']
        
        online_data = {}
        players_data = {}
        
        for key, server in SERVERS.items():
            try:
                print(f"Парсинг сервера {key}...")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(
                    server['monitor_url'],
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Поиск онлайна (нужно подобрать селектор под сайт)
                    # Вариант 1: Ищем по классу
                    online_elem = soup.select_one('.server-online, .online-count, .players-online')
                    
                    # Вариант 2: Ищем по тексту с числами
                    if not online_elem:
                        # Ищем любой элемент содержащий цифры и слеш (например "150/200")
                        for elem in soup.find_all(['div', 'span', 'p']):
                            text = elem.get_text().strip()
                            if '/' in text and text.replace('/','').replace(' ','').isdigit():
                                online_elem = elem
                                break
                    
                    if online_elem:
                        online_text = online_elem.get_text().strip()
                        online_data[key] = online_text
                        
                        # Парсим количество игроков
                        try:
                            if '/' in online_text:
                                current, max_players = online_text.split('/')
                                players_data[key] = {
                                    'current': int(current.strip()),
                                    'max': int(max_players.strip())
                                }
                            else:
                                players_data[key] = {'current': 0, 'max': 0}
                        except:
                            players_data[key] = {'current': 0, 'max': 0}
                    else:
                        online_data[key] = "0/100"
                        players_data[key] = {'current': 0, 'max': 100}
                        print(f"Не найден элемент с онлайном для {key}")
                else:
                    online_data[key] = "0/100"
                    players_data[key] = {'current': 0, 'max': 100}
                    print(f"Ошибка HTTP {response.status_code} для {key}")
                    
            except Exception as e:
                print(f"Ошибка парсинга {key}: {e}")
                online_data[key] = "0/100"
                players_data[key] = {'current': 0, 'max': 100}
            
            time.sleep(1)  # Задержка между запросами
        
        # Обновляем кэш
        self.cache['online'] = online_data
        self.cache['players'] = players_data
        self.cache['last_update'] = current_time
        
        return online_data
    
    def format_server_info(self):
        """Форматирует информацию о серверах"""
        online = self.get_server_online()
        
        info = "🦀 **HOSTILE RUST — МОНИТОРИНГ** 🦀\n"
        info += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
        for key, server in SERVERS.items():
            status_emoji = "🟢" if "0/100" not in online.get(key, "0/100") else "🟡"
            
            info += f"{status_emoji} **{server['name']}**\n"
            info += f"📌 IP: `{server['ip']}`\n"
            info += f"👥 Онлайн: **{online.get(key, '0/100')}**\n"
            
            # Добавляем статус на основе онлайна
            try:
                current = int(online.get(key, "0/100").split('/')[0])
                if current > 50:
                    info += "📊 Загруженность: 🔴 Высокая\n"
                elif current > 20:
                    info += "📊 Загруженность: 🟡 Средняя\n"
                else:
                    info += "📊 Загруженность: 🟢 Низкая\n"
            except:
                pass
            
            info += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
        info += f"🔄 **Вайп:** {WIPE_SCHEDULE}\n"
        info += f"🛒 **Магазин:** [Перейти]({SHOP_URL})\n"
        info += f"🕒 **Обновлено:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        
        return info
    
    def get_server_status(self, server_key):
        """Возвращает статус конкретного сервера"""
        online = self.get_server_online()
        return online.get(server_key, "0/100")

# Создаем глобальный экземпляр
monitor = ServerMonitor()
