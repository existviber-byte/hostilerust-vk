from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import json

class Keyboards:
    def main_keyboard(self):
        """Главное меню"""
        keyboard = VkKeyboard(one_time=False)
        
        keyboard.add_button('🎁 Промокоды', color=VkKeyboardColor.PRIMARY)
        keyboard.add_button('🎮 Сервера', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('📜 Правила', color=VkKeyboardColor.SECONDARY)
        keyboard.add_button('🛒 Магазин', color=VkKeyboardColor.POSITIVE)
        keyboard.add_line()
        keyboard.add_button('🎫 Поддержка', color=VkKeyboardColor.SECONDARY)
        keyboard.add_button('⏳ До вайпа', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('📋 IP серверов', color=VkKeyboardColor.PRIMARY)
        
        return keyboard
    
    def back_keyboard(self):
        """Клавиатура с кнопкой Назад"""
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button('◀️ Назад в меню', color=VkKeyboardColor.SECONDARY)
        return keyboard
    
    def admin_keyboard(self):
        """Админ-панель"""
        keyboard = VkKeyboard(one_time=False)
        
        keyboard.add_button('➕ Добавить промо', color=VkKeyboardColor.POSITIVE)
        keyboard.add_button('➖ Удалить промо', color=VkKeyboardColor.NEGATIVE)
        keyboard.add_line()
        keyboard.add_button('📋 Список промокодов', color=VkKeyboardColor.PRIMARY)
        keyboard.add_button('👥 Пользователи', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('📊 Статистика', color=VkKeyboardColor.SECONDARY)
        keyboard.add_button('📩 Тикеты', color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button('📢 Рассылка', color=VkKeyboardColor.POSITIVE)
        keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY)
        
        return keyboard
    
    def tickets_keyboard(self):
        """Меню тикетов"""
        keyboard = VkKeyboard(one_time=False)
        
        keyboard.add_button('➕ Создать тикет', color=VkKeyboardColor.POSITIVE)
        keyboard.add_button('📋 Мои тикеты', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('◀️ Назад в меню', color=VkKeyboardColor.SECONDARY)
        
        return keyboard
    
    def servers_keyboard(self):
        """Клавиатура с серверами"""
        keyboard = VkKeyboard(inline=True)
        
        keyboard.add_button('📋 x2 IP', color=VkKeyboardColor.PRIMARY, 
                          payload={'command': 'copy_ip_x5'})
        keyboard.add_line()
        keyboard.add_button('📋 x100 IP', color=VkKeyboardColor.PRIMARY,
                          payload={'command': 'copy_ip_x100'})
        keyboard.add_line()
        keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY,
                          payload={'command': 'back_to_main'})
        
        return keyboard
    
    def confirm_keyboard(self, action, item_id):
        """Клавиатура подтверждения"""
        keyboard = VkKeyboard(inline=True)
        
        keyboard.add_button('✅ Да', color=VkKeyboardColor.POSITIVE,
                          payload={'command': f'confirm_{action}_{item_id}'})
        keyboard.add_button('❌ Нет', color=VkKeyboardColor.NEGATIVE,
                          payload={'command': 'cancel'})
        
        return keyboard
