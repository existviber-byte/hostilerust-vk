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
        keyboard.add_button('📈 Статистика промокодов', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('👥 Пользователи', color=VkKeyboardColor.SECONDARY)
        keyboard.add_button('📊 Статистика', color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button('📩 Тикеты', color=VkKeyboardColor.PRIMARY)
        keyboard.add_button('📢 Рассылка', color=VkKeyboardColor.POSITIVE)
        keyboard.add_line()
        keyboard.add_button('👑 Управление админами', color=VkKeyboardColor.PRIMARY)
        keyboard.add_button('🔧 Редактировать сервера', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY)
        
        return keyboard
    
    def admin_management_keyboard(self):
        """Клавиатура управления админами"""
        keyboard = VkKeyboard(inline=True)
        
        keyboard.add_button('➕ Добавить админа', color=VkKeyboardColor.POSITIVE,
                          payload={'command': 'start_add_admin'})
        keyboard.add_line()
        keyboard.add_button('➖ Удалить админа', color=VkKeyboardColor.NEGATIVE,
                          payload={'command': 'start_remove_admin'})
        keyboard.add_line()
        keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY,
                          payload={'command': 'admin_back'})
        
        return keyboard
    
    def servers_editor_keyboard(self, servers_config):
        """Клавиатура редактора серверов"""
        keyboard = VkKeyboard(inline=True)
        
        for key, server in servers_config.items():
            keyboard.add_button(f'✏️ {server["name"][:30]}', color=VkKeyboardColor.PRIMARY,
                              payload={'command': f'edit_server_{key}'})
            keyboard.add_line()
        
        keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY,
                          payload={'command': 'admin_back'})
        
        return keyboard
    
    def server_edit_options_keyboard(self, server_key):
        """Клавиатура опций редактирования сервера"""
        keyboard = VkKeyboard(inline=True)
        
        keyboard.add_button('📝 Изменить название', color=VkKeyboardColor.PRIMARY,
                          payload={'command': f'edit_server_name_{server_key}'})
        keyboard.add_line()
        keyboard.add_button('🌐 Изменить IP', color=VkKeyboardColor.PRIMARY,
                          payload={'command': f'edit_server_ip_{server_key}'})
        keyboard.add_line()
        keyboard.add_button('🔄 Изменить вайп', color=VkKeyboardColor.PRIMARY,
                          payload={'command': f'edit_server_wipe_{server_key}'})
        keyboard.add_line()
        keyboard.add_button('🕐 Изменить час вайпа', color=VkKeyboardColor.PRIMARY,
                          payload={'command': f'edit_server_hour_{server_key}'})
        keyboard.add_line()
        keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY,
                          payload={'command': 'admin_edit_servers'})
        
        return keyboard
    
    def remove_admin_keyboard(self, admin_ids, current_admin_id):
        """Клавиатура для удаления админов"""
        keyboard = VkKeyboard(inline=True)
        
        for aid in admin_ids:
            if aid != current_admin_id:  # Нельзя удалить самого себя
                # Здесь нужно получить имя пользователя, но мы не можем это сделать в клавиатуре
                # Поэтому используем ID
                keyboard.add_button(f'❌ Удалить id{aid}', color=VkKeyboardColor.NEGATIVE,
                                  payload={'command': f'remove_admin_{aid}'})
                keyboard.add_line()
        
        keyboard.add_button('◀️ Назад', color=VkKeyboardColor.SECONDARY,
                          payload={'command': 'admin_manage_admins'})
        
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
                          payload={'command': 'copy_ip_x2'})
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
