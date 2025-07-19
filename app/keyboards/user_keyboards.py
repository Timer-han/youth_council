from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

def get_main_menu_keyboard():
    """Клавиатура главного меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Ближайшие мероприятия", callback_data="upcoming_events")],
            [InlineKeyboardButton(text="👤 Мой профиль", callback_data="my_profile")],
        ]
    )

def get_events_pagination_keyboard(current_page: int, total_pages: int, events=None):
    """Клавиатура пагинации для списка мероприятий"""
    keyboard = []
    
    # Кнопки для каждого мероприятия
    if events:
        for event in events:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"📅 {event.title}",
                    callback_data=f"event_{event.id}"
                )
            ])
    
    # Кнопки пагинации
    pagination_buttons = []
    if current_page > 1:
        pagination_buttons.append(
            InlineKeyboardButton(text="« Назад", callback_data=f"events_page_{current_page - 1}")
        )
    if current_page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton(text="Вперёд »", callback_data=f"events_page_{current_page + 1}")
        )
    
    if pagination_buttons:
        keyboard.append(pagination_buttons)
    
    # Кнопка возврата в главное меню
    keyboard.append([InlineKeyboardButton(text="« Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_event_detail_keyboard(event_id: int, is_registered: bool, registration_required: bool, registration_available: bool):
    """Клавиатура для детальной информации о мероприятии"""
    keyboard = []
    
    if registration_required and registration_available and not is_registered:
        keyboard.append([
            InlineKeyboardButton(
                text="📝 Зарегистрироваться",
                callback_data=f"register_{event_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="« К списку мероприятий", callback_data="upcoming_events")])
    keyboard.append([InlineKeyboardButton(text="« Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_back_to_menu_keyboard():
    """Клавиатура с кнопкой возврата в главное меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="« Главное меню", callback_data="main_menu")
        ]]
    )

def get_registration_keyboard():
    """Клавиатура для процесса регистрации"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="Отмена", callback_data="main_menu")
        ]]
    )
