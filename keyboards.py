from vk_api.keyboard import VkKeyboard, VkKeyboardColor

class Keyboards:
    @staticmethod
    def main_keyboard():
        keyboard = VkKeyboard(inline=False)
        keyboard.add_button('🎁 Промокоды', color=VkKeyboardColor.PRIMARY)
        keyboard.add_button('🖥 Сервера', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('📜 Правила', color=VkKeyboardColor.SECONDARY)
        keyboard.add_button('🎫 Поддержка', color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button('🛒 Магазин', color=VkKeyboardColor.POSITIVE)
        keyboard.add_button('🔄 Вайп', color=VkKeyboardColor.PRIMARY)
        return keyboard
    
    @staticmethod
    def admin_keyboard():
        keyboard = VkKeyboard(inline=False)
        keyboard.add_button('📊 Статистика', color=VkKeyboardColor.PRIMARY)
        keyboard.add_button('📨 Рассылка', color=VkKeyboardColor.POSITIVE)
        keyboard.add_line()
        keyboard.add_button('➕ Добавить промо', color=VkKeyboardColor.POSITIVE)
        keyboard.add_button('➖ Удалить промо', color=VkKeyboardColor.NEGATIVE)
        keyboard.add_line()
        keyboard.add_button('🎫 Тикеты админ', color=VkKeyboardColor.SECONDARY)
        keyboard.add_button('👥 Пользователи', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY)
        return keyboard
    
    @staticmethod
    def tickets_keyboard():
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button('➕ Создать тикет', color=VkKeyboardColor.POSITIVE,
                          payload={'command': 'create_ticket'})
        return keyboard
    
    @staticmethod
    def back_keyboard():
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button('◀️ Назад в меню', color=VkKeyboardColor.SECONDARY,
                          payload={'command': 'back_to_main'})
        return keyboard
    
    @staticmethod
    def shop_keyboard():
        keyboard = VkKeyboard(inline=True)
        keyboard.add_openlink_button('🛒 Открыть магазин', 'https://hostilerust.gamestores.app/')
        keyboard.add_line()
        keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY,
                          payload={'command': 'back_to_main'})
        return keyboard
    
    @staticmethod
    def server_refresh_keyboard():
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button('🔄 Обновить онлайн', color=VkKeyboardColor.PRIMARY,
                          payload={'command': 'refresh_servers'})
        keyboard.add_line()
        keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY,
                          payload={'command': 'back_to_main'})
        return keyboard
