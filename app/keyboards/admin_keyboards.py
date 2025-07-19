from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime


def get_admin_main_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мероприятия", callback_data="admin_events")],
            [InlineKeyboardButton(text="Модераторы", callback_data="admin_moderators")],
            [InlineKeyboardButton(text="Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="Экспорт участников", callback_data="admin_export")],
        ]
    )

def get_events_list_keyboard(events):
    keyboard = []
    for event in events:
        event_date = event.date.strftime("%d.%m.%Y")
        keyboard.append([
            InlineKeyboardButton(
                text=f"{event.title} ({event_date})", 
                callback_data=f"manage_event_{event.id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton(text="➕ Создать мероприятие", callback_data="create_event")])
    keyboard.append([InlineKeyboardButton(text="« Назад", callback_data="admin_main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_event_management_keyboard(event_id: int):
    """Клавиатура для управления конкретным мероприятием"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Участники", callback_data=f"view_participants_{event_id}")],
        [
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_event_{event_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_event_{event_id}")
        ],
        [InlineKeyboardButton(text="◀️ К списку мероприятий", callback_data="admin_events")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="admin_main_menu")]
    ])
    return keyboard

def get_event_form_keyboard(with_skip: bool = False):
    keyboard = [[InlineKeyboardButton(text="Отмена", callback_data="cancel_event_form")]]
    if with_skip:
        keyboard.insert(0, [InlineKeyboardButton(text="Пропустить", callback_data="skip_field")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_confirm_keyboard(action: str, entity_id: int = None):
    callback_prefix = f"{action}_{entity_id}" if entity_id else action
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{callback_prefix}"),
                InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_{callback_prefix}")
            ]
        ]
    )

def get_moderator_management_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить модератора", callback_data="add_moderator")],
            [InlineKeyboardButton(text="Удалить модератора", callback_data="remove_moderator")],
            [InlineKeyboardButton(text="« Назад", callback_data="admin_main_menu")],
        ]
    )

def get_broadcast_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Начать рассылку", callback_data="start_broadcast")],
            [InlineKeyboardButton(text="« Назад", callback_data="admin_main_menu")],
        ]
    )

def get_export_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Экспортировать всех участников", callback_data="export_all_participants")],
            [InlineKeyboardButton(text="Экспортировать по мероприятию", callback_data="export_by_event")],
            [InlineKeyboardButton(text="« Назад", callback_data="admin_main_menu")],
        ]
    )
