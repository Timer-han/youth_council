from datetime import datetime
import json
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.database import get_db
from app.database.models import User, Event, Registration
from app.keyboards.admin_keyboards import (
    get_admin_main_menu_keyboard,
    get_events_list_keyboard,
    get_event_management_keyboard,
    get_event_form_keyboard,
    get_confirm_keyboard,
    get_moderator_management_keyboard,
    get_broadcast_keyboard,
    get_export_keyboard
)
from app.config import ADMIN_IDS

admin_router = Router()

# FSM для создания/редактирования мероприятия
class EventForm(StatesGroup):
    title = State()
    short_description = State()
    full_description = State()
    date = State()
    location = State()
    speakers = State()
    image_path = State()
    registration_required = State()
    max_participants = State()
    confirm = State()

# FSM для рассылки
class BroadcastForm(StatesGroup):
    text = State()
    with_registration = State()
    confirm = State()

# Проверка на админа/модератора
async def is_admin_or_moderator(user_id: int) -> bool:
    async for db in get_db():
        user = await db.execute(select(User).where(User.telegram_id == user_id))
        user = user.scalar_one_or_none()
        if user and (user.is_admin or user.is_moderator):
            return True
        if user_id in ADMIN_IDS:
            return True
    return False

# Команда /admin
@admin_router.message(Command("admin"))
async def admin_panel(message: Message):
    if not await is_admin_or_moderator(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён.")
        return
    await message.answer("🛠 Админ-панель:", reply_markup=get_admin_main_menu_keyboard())

# Список мероприятий
@admin_router.callback_query(F.data == "admin_events")
async def list_events(callback: CallbackQuery):
    if not await is_admin_or_moderator(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён.", show_alert=True)
        return
    
    async for db in get_db():
        events = await db.execute(select(Event).order_by(Event.date.desc()))
        events = events.scalars().all()
        
        if not events:
            await callback.message.edit_text(
                "📅 Мероприятия не найдены. Создайте новое мероприятие!",
                reply_markup=get_events_list_keyboard([])
            )
        else:
            await callback.message.edit_text(
                "📅 Список мероприятий:",
                reply_markup=get_events_list_keyboard(events)
            )
    await callback.answer()

# Начало создания мероприятия
@admin_router.callback_query(F.data == "create_event")
async def start_event_creation(callback: CallbackQuery, state: FSMContext):
    if not await is_admin_or_moderator(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён.", show_alert=True)
        return
    
    await state.set_state(EventForm.title)
    await callback.message.edit_text(
        "📝 Введите название мероприятия:",
        reply_markup=get_event_form_keyboard()
    )
    await callback.answer()

# Получение названия мероприятия
@admin_router.message(EventForm.title)
async def process_event_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(EventForm.short_description)
    await message.answer(
        "📝 Введите краткое описание мероприятия:",
        reply_markup=get_event_form_keyboard(with_skip=True)
    )

# Получение краткого описания
@admin_router.message(EventForm.short_description)
async def process_short_description(message: Message, state: FSMContext):
    await state.update_data(short_description=message.text)
    await state.set_state(EventForm.full_description)
    await message.answer(
        "📝 Введите полное описание мероприятия:",
        reply_markup=get_event_form_keyboard(with_skip=True)
    )

# Пропуск необязательного поля
@admin_router.callback_query(F.data == "skip_field")
async def skip_optional_field(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    
    # Определяем текущее состояние и следующее
    if current_state == EventForm.short_description.state:
        await state.update_data(short_description=None)
        await state.set_state(EventForm.full_description)
        await callback.message.edit_text(
            "📝 Введите полное описание мероприятия:",
            reply_markup=get_event_form_keyboard(with_skip=True)
        )
    elif current_state == EventForm.full_description.state:
        await state.update_data(full_description=None)
        await state.set_state(EventForm.date)
        await callback.message.edit_text(
            "📅 Введите дату и время мероприятия (формат: ДД.ММ.ГГГГ ЧЧ:ММ):",
            reply_markup=get_event_form_keyboard()
        )
    elif current_state == EventForm.location.state:
        await state.update_data(location=None)
        await state.set_state(EventForm.speakers)
        await callback.message.edit_text(
            "👥 Введите список спикеров (через запятую):",
            reply_markup=get_event_form_keyboard(with_skip=True)
        )
    elif current_state == EventForm.speakers.state:
        await state.update_data(speakers=None)
        await state.set_state(EventForm.image_path)
        await callback.message.edit_text(
            "🖼 Отправьте изображение для мероприятия:",
            reply_markup=get_event_form_keyboard(with_skip=True)
        )
    elif current_state == EventForm.image_path.state:
        await state.update_data(image_path=None)
        await state.set_state(EventForm.registration_required)
        await callback.message.edit_text(
            "❓ Требуется ли регистрация? (да/нет):",
            reply_markup=get_event_form_keyboard()
        )
    elif current_state == EventForm.max_participants.state:
        await state.update_data(max_participants=None)
        data = await state.get_data()
        confirmation_message = await format_confirmation_message(data)
        await callback.message.edit_text(
            confirmation_message,
            reply_markup=get_confirm_keyboard('create_event')
        )
        await state.set_state(EventForm.confirm)
    
    await callback.answer()

# Вспомогательная функция для форматирования сообщения подтверждения
async def format_confirmation_message(data):
    confirmation_message = "📋 Проверьте данные мероприятия:\n\n"
    confirmation_message += f"📝 Название: {data['title']}\n"
    if data.get('short_description'):
        confirmation_message += f"📝 Краткое описание: {data['short_description']}\n"
    if data.get('full_description'):
        confirmation_message += f"📝 Полное описание: {data['full_description']}\n"
    confirmation_message += f"📅 Дата: {data['date']}\n"
    if data.get('location'):
        confirmation_message += f"📍 Место: {data['location']}\n"
    if data.get('speakers'):
        try:
            speakers = json.loads(data['speakers'])
            confirmation_message += f"👥 Спикеры: {', '.join(speakers)}\n"
        except:
            confirmation_message += f"👥 Спикеры: {data['speakers']}\n"
    confirmation_message += f"✅ Регистрация: {'Требуется' if data.get('registration_required') else 'Не требуется'}\n"
    if data.get('max_participants'):
        confirmation_message += f"👥 Максимум участников: {data['max_participants']}\n"
    return confirmation_message

# Получение полного описания
@admin_router.message(EventForm.full_description)
async def process_full_description(message: Message, state: FSMContext):
    await state.update_data(full_description=message.text)
    await state.set_state(EventForm.date)
    await message.answer(
        "📅 Введите дату и время мероприятия (формат: ДД.ММ.ГГГГ ЧЧ:ММ):",
        reply_markup=get_event_form_keyboard()
    )

# Получение даты
@admin_router.message(EventForm.date)
async def process_date(message: Message, state: FSMContext):
    try:
        event_date = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        await state.update_data(date=event_date)
        await state.set_state(EventForm.location)
        await message.answer(
            "📍 Введите место проведения:",
            reply_markup=get_event_form_keyboard(with_skip=True)
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ ЧЧ:ММ",
            reply_markup=get_event_form_keyboard()
        )

# Получение места проведения
@admin_router.message(EventForm.location)
async def process_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.set_state(EventForm.speakers)
    await message.answer(
        "👥 Введите список спикеров (через запятую):",
        reply_markup=get_event_form_keyboard(with_skip=True)
    )

# Получение спикеров
@admin_router.message(EventForm.speakers)
async def process_speakers(message: Message, state: FSMContext):
    speakers = [s.strip() for s in message.text.split(",")]
    await state.update_data(speakers=json.dumps(speakers))
    await state.set_state(EventForm.image_path)
    await message.answer(
        "🖼 Отправьте изображение для мероприятия:",
        reply_markup=get_event_form_keyboard(with_skip=True)
    )

# Получение изображения
@admin_router.message(EventForm.image_path)
async def process_image(message: Message, state: FSMContext):
    if message.photo:
        await state.update_data(image_path=message.photo[-1].file_id)
    await state.set_state(EventForm.registration_required)
    await message.answer(
        "❓ Требуется ли регистрация? (да/нет):",
        reply_markup=get_event_form_keyboard()
    )

# Получение флага регистрации
@admin_router.message(EventForm.registration_required)
async def process_registration_required(message: Message, state: FSMContext):
    registration_required = message.text.lower() in ['да', 'yes', '1', 'true']
    await state.update_data(registration_required=registration_required)
    
    if registration_required:
        await state.set_state(EventForm.max_participants)
        await message.answer(
            "👥 Введите максимальное количество участников (или пропустите):",
            reply_markup=get_event_form_keyboard(with_skip=True)
        )
    else:
        await state.update_data(max_participants=None)
        data = await state.get_data()
        confirmation_message = await format_confirmation_message(data)
        
        await message.answer(
            confirmation_message,
            reply_markup=get_confirm_keyboard('create_event')
        )
        await state.set_state(EventForm.confirm)

# Получение максимального количества участников
@admin_router.message(EventForm.max_participants)
async def process_max_participants(message: Message, state: FSMContext):
    try:
        max_participants = int(message.text)
        await state.update_data(max_participants=max_participants)
    except ValueError:
        await message.answer(
            "❌ Введите целое число или нажмите 'Пропустить'",
            reply_markup=get_event_form_keyboard(with_skip=True)
        )
        return
    
    data = await state.get_data()
    confirmation_message = await format_confirmation_message(data)
    
    await message.answer(
        confirmation_message,
        reply_markup=get_confirm_keyboard('create_event')
    )
    await state.set_state(EventForm.confirm)

# Подтверждение создания мероприятия
@admin_router.callback_query(F.data == "confirm_create_event")
async def confirm_event_creation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    async for db in get_db():
        new_event = Event(
            title=data['title'],
            short_description=data.get('short_description'),
            full_description=data.get('full_description'),
            date=data['date'],
            location=data.get('location'),
            speakers=data.get('speakers'),
            image_path=data.get('image_path'),
            registration_required=data['registration_required'],
            max_participants=data.get('max_participants')
        )
        db.add(new_event)
        await db.commit()
    
    await callback.message.edit_text(
        "✅ Мероприятие успешно создано!",
        reply_markup=get_admin_main_menu_keyboard()
    )
    await state.clear()
    await callback.answer()

# Отмена создания мероприятия
@admin_router.callback_query(F.data == "cancel_event_form")
async def cancel_event_creation(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Создание мероприятия отменено",
        reply_markup=get_admin_main_menu_keyboard()
    )
    await callback.answer()

# Управление конкретным мероприятием
@admin_router.callback_query(F.data.startswith("manage_event_"))
async def manage_event(callback: CallbackQuery):
    if not await is_admin_or_moderator(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    async for db in get_db():
        event = await db.execute(select(Event).where(Event.id == event_id))
        event = event.scalar_one_or_none()
        
        if not event:
            await callback.answer("❌ Мероприятие не найдено", show_alert=True)
            return
        
        event_date = event.date.strftime("%d.%m.%Y %H:%M")
        text = f"📅 Мероприятие: {event.title}\n"
        text += f"📅 Дата: {event_date}\n"
        if event.location:
            text += f"📍 Место: {event.location}\n"
        if event.speakers:
            try:
                speakers = json.loads(event.speakers)
                text += f"👥 Спикеры: {', '.join(speakers)}\n"
            except:
                text += f"👥 Спикеры: {event.speakers}\n"
        
        # Получаем количество участников
        reg_count = await db.execute(
            select(func.count(Registration.id)).where(Registration.event_id == event_id)
        )
        participants_count = reg_count.scalar()
        text += f"\n👥 Зарегистрировано участников: {participants_count}"
        if event.max_participants:
            text += f" из {event.max_participants}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_event_management_keyboard(event_id)
        )
    await callback.answer()

# Удаление мероприятия
@admin_router.callback_query(F.data.startswith("delete_event_"))
async def delete_event_prompt(callback: CallbackQuery):
    event_id = int(callback.data.split("_")[-1])
    async for db in get_db():
        event = await db.execute(select(Event).where(Event.id == event_id))
        event = event.scalar_one_or_none()
        
        if not event:
            await callback.answer("❌ Мероприятие не найдено", show_alert=True)
            return
        
        await callback.message.edit_text(
            f"❓ Вы действительно хотите удалить мероприятие '{event.title}'?",
            reply_markup=get_confirm_keyboard('delete_event', event_id)
        )
    await callback.answer()

# Подтверждение удаления мероприятия
@admin_router.callback_query(F.data.startswith("confirm_delete_event_"))
async def confirm_delete_event(callback: CallbackQuery):
    event_id = int(callback.data.split("_")[-1])
    async for db in get_db():
        # Удаляем все регистрации
        await db.execute(delete(Registration).where(Registration.event_id == event_id))
        # Удаляем мероприятие
        await db.execute(delete(Event).where(Event.id == event_id))
        await db.commit()
    
    await callback.message.edit_text(
        "✅ Мероприятие успешно удалено",
        reply_markup=get_admin_main_menu_keyboard()
    )
    await callback.answer()

# Отмена удаления мероприятия
@admin_router.callback_query(F.data.startswith("cancel_delete_event_"))
async def cancel_delete_event(callback: CallbackQuery):
    event_id = int(callback.data.split("_")[-1])
    await manage_event(callback)

# Возврат в главное меню админа
@admin_router.callback_query(F.data == "admin_main_menu")
async def return_to_admin_menu(callback: CallbackQuery):
    if not await is_admin_or_moderator(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🛠 Админ-панель:",
        reply_markup=get_admin_main_menu_keyboard()
    )
    await callback.answer()

# Просмотр списка участников мероприятия
@admin_router.callback_query(F.data.startswith("view_participants_"))
async def view_participants(callback: CallbackQuery):
    if not await is_admin_or_moderator(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    async for db in get_db():
        # Получаем информацию о мероприятии
        event = await db.execute(select(Event).where(Event.id == event_id))
        event = event.scalar_one_or_none()
        
        if not event:
            await callback.answer("❌ Мероприятие не найдено", show_alert=True)
            return
        
        # Получаем список участников с информацией о пользователях
        participants = await db.execute(
            select(Registration, User)
            .join(User, Registration.user_id == User.id)
            .where(Registration.event_id == event_id)
            .order_by(Registration.registered_at.desc())
        )
        participants = participants.all()
        
        if not participants:
            text = f"📅 Мероприятие: {event.title}\n\n"
            text += "👥 Участники отсутствуют"
        else:
            text = f"📅 Мероприятие: {event.title}\n\n"
            text += f"👥 Зарегистрировано участников: {len(participants)}"
            if event.max_participants:
                text += f" из {event.max_participants}"
            text += "\n\n📋 Список участников:\n"
            
            for i, (registration, user) in enumerate(participants, 1):
                # Формируем информацию об участнике
                participant_info = f"{i}. "
                
                # Формируем полное имя из first_name и last_name
                full_name = ""
                if user.first_name:
                    full_name += user.first_name
                if user.last_name:
                    full_name += f" {user.last_name}"
                
                if full_name.strip():
                    participant_info += full_name.strip()
                else:
                    participant_info += f"@{user.username}" if user.username else f"ID: {user.telegram_id}"
                
                # Добавляем дату регистрации
                reg_date = registration.registered_at.strftime("%d.%m.%Y %H:%M")
                participant_info += f" ({reg_date})"
                
                text += participant_info + "\n"
                
                # Ограничиваем количество участников в одном сообщении
                if i >= 50:  # Telegram имеет ограничение на длину сообщения
                    text += f"\n... и ещё {len(participants) - i} участников"
                    break
        
        # Создаем клавиатуру с возможностью экспорта
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Экспорт в CSV", callback_data=f"export_participants_{event_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"manage_event_{event_id}")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# Экспорт участников в CSV файл
@admin_router.callback_query(F.data.startswith("export_participants_"))
async def export_participants(callback: CallbackQuery):
    if not await is_admin_or_moderator(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    async for db in get_db():
        # Получаем информацию о мероприятии
        event = await db.execute(select(Event).where(Event.id == event_id))
        event = event.scalar_one_or_none()
        
        if not event:
            await callback.answer("❌ Мероприятие не найдено", show_alert=True)
            return
        
        # Получаем список участников
        participants = await db.execute(
            select(Registration, User)
            .join(User, Registration.user_id == User.id)
            .where(Registration.event_id == event_id)
            .order_by(Registration.registered_at.desc())
        )
        participants = participants.all()
        
        if not participants:
            await callback.answer("❌ Нет участников для экспорта", show_alert=True)
            return
        
        # Создаем CSV контент
        import io
        import csv
        
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)
        
        # Заголовки
        csv_writer.writerow(['№', 'Имя', 'Username', 'Telegram ID', 'Дата регистрации'])
        
        # Данные участников
        for i, (registration, user) in enumerate(participants, 1):
            # Формируем полное имя
            full_name = ""
            if user.first_name:
                full_name += user.first_name
            if user.last_name:
                full_name += f" {user.last_name}"
            
            csv_writer.writerow([
                i,
                full_name.strip() if full_name.strip() else '',
                user.username or '',
                user.telegram_id,
                registration.registered_at.strftime("%d.%m.%Y %H:%M")
            ])
        
        # Конвертируем в байты для отправки
        csv_content = csv_buffer.getvalue().encode('utf-8-sig')  # utf-8-sig для корректного отображения в Excel
        csv_file = io.BytesIO(csv_content)
        csv_file.name = f"participants_{event.title}_{datetime.now().strftime('%d_%m_%Y')}.csv"
        
        # Отправляем файл
        from aiogram.types import BufferedInputFile
        document = BufferedInputFile(csv_content, filename=csv_file.name)
        
        await callback.message.answer_document(
            document,
            caption=f"📊 Список участников мероприятия '{event.title}'\n"
                   f"Всего участников: {len(participants)}"
        )
        
        await callback.answer("✅ Файл сформирован!")


# FSM для редактирования мероприятия
class EventEditForm(StatesGroup):
    event_id = State()
    field = State()
    value = State()
    confirm = State()

# Начало редактирования мероприятия
@admin_router.callback_query(F.data.startswith("edit_event_"))
async def start_edit_event(callback: CallbackQuery, state: FSMContext):
    if not await is_admin_or_moderator(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    async for db in get_db():
        event = await db.execute(select(Event).where(Event.id == event_id))
        event = event.scalar_one_or_none()
        
        if not event:
            await callback.answer("❌ Мероприятие не найдено", show_alert=True)
            return
        
        # Сохраняем ID мероприятия в состояние
        await state.update_data(event_id=event_id)
        await state.set_state(EventEditForm.field)
        
        # Формируем текст с текущими данными мероприятия
        event_date = event.date.strftime("%d.%m.%Y %H:%M")
        text = f"✏️ Редактирование мероприятия '{event.title}'\n\n"
        text += "Выберите поле для редактирования:\n\n"
        text += f"📝 Название: {event.title}\n"
        text += f"📝 Краткое описание: {event.short_description or 'Не указано'}\n"
        text += f"📝 Полное описание: {event.full_description or 'Не указано'}\n"
        text += f"📅 Дата: {event_date}\n"
        text += f"📍 Место: {event.location or 'Не указано'}\n"
        
        if event.speakers:
            try:
                speakers = json.loads(event.speakers)
                text += f"👥 Спикеры: {', '.join(speakers)}\n"
            except:
                text += f"👥 Спикеры: {event.speakers}\n"
        else:
            text += "👥 Спикеры: Не указаны\n"
        
        text += f"✅ Регистрация: {'Требуется' if event.registration_required else 'Не требуется'}\n"
        text += f"👥 Максимум участников: {event.max_participants or 'Без ограничений'}\n"
        
        # Создаем клавиатуру для выбора поля
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Название", callback_data="edit_field_title")],
            [InlineKeyboardButton(text="📝 Краткое описание", callback_data="edit_field_short_description")],
            [InlineKeyboardButton(text="📝 Полное описание", callback_data="edit_field_full_description")],
            [InlineKeyboardButton(text="📅 Дата", callback_data="edit_field_date")],
            [InlineKeyboardButton(text="📍 Место", callback_data="edit_field_location")],
            [InlineKeyboardButton(text="👥 Спикеры", callback_data="edit_field_speakers")],
            [InlineKeyboardButton(text="🖼 Изображение", callback_data="edit_field_image")],
            [InlineKeyboardButton(text="✅ Регистрация", callback_data="edit_field_registration")],
            [InlineKeyboardButton(text="👥 Макс. участников", callback_data="edit_field_max_participants")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"manage_event_{event_id}")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# Обработка выбора поля для редактирования
@admin_router.callback_query(F.data.startswith("edit_field_"))
async def select_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split("edit_field_")[1]
    await state.update_data(field=field)
    await state.set_state(EventEditForm.value)
    
    # Определяем текст запроса в зависимости от поля
    field_messages = {
        'title': "📝 Введите новое название мероприятия:",
        'short_description': "📝 Введите новое краткое описание мероприятия:",
        'full_description': "📝 Введите новое полное описание мероприятия:",
        'date': "📅 Введите новую дату и время (формат: ДД.ММ.ГГГГ ЧЧ:ММ):",
        'location': "📍 Введите новое место проведения:",
        'speakers': "👥 Введите новый список спикеров (через запятую):",
        'image': "🖼 Отправьте новое изображение для мероприятия:",
        'registration': "✅ Требуется ли регистрация? (да/нет):",
        'max_participants': "👥 Введите новое максимальное количество участников (или 0 для снятия ограничений):"
    }
    
    message_text = field_messages.get(field, "Введите новое значение:")
    
    # Для некоторых полей добавляем кнопку "Очистить поле"
    clearable_fields = ['short_description', 'full_description', 'location', 'speakers', 'image', 'max_participants']
    
    if field in clearable_fields:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Очистить поле", callback_data="clear_field")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ])
        await callback.message.edit_text(message_text, reply_markup=keyboard)
    else:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ])
        await callback.message.edit_text(message_text, reply_markup=keyboard)
    
    await callback.answer()

# Очистка поля
@admin_router.callback_query(F.data == "clear_field")
async def clear_field(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    event_id = data['event_id']
    field = data['field']
    
    await state.update_data(value=None)
    await state.set_state(EventEditForm.confirm)
    
    await callback.message.edit_text(
        f"❓ Вы действительно хотите очистить поле '{field}'?",
        reply_markup=get_confirm_keyboard('edit_event', event_id)
    )
    await callback.answer()

# Обработка нового значения поля
@admin_router.message(EventEditForm.value)
async def process_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data['field']
    value = message.text
    
    # Валидация в зависимости от поля
    if field == 'date':
        try:
            event_date = datetime.strptime(value, "%d.%m.%Y %H:%M")
            value = event_date
        except ValueError:
            await message.answer(
                "❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ ЧЧ:ММ",
                reply_markup=get_event_form_keyboard()
            )
            return
    elif field == 'registration':
        value = value.lower() in ['да', 'yes', '1', 'true']
    elif field == 'max_participants':
        try:
            value = int(value) if int(value) > 0 else None
        except ValueError:
            await message.answer(
                "❌ Введите целое число или 0 для снятия ограничений",
                reply_markup=get_event_form_keyboard()
            )
            return
    elif field == 'speakers':
        speakers = [s.strip() for s in value.split(",")]
        value = json.dumps(speakers)
    
    await state.update_data(value=value)
    await state.set_state(EventEditForm.confirm)
    
    # Показываем подтверждение
    field_names = {
        'title': 'Название',
        'short_description': 'Краткое описание',
        'full_description': 'Полное описание',
        'date': 'Дата',
        'location': 'Место',
        'speakers': 'Спикеры',
        'registration': 'Регистрация',
        'max_participants': 'Максимум участников'
    }
    
    field_name = field_names.get(field, field)
    
    if field == 'date':
        display_value = value.strftime("%d.%m.%Y %H:%M")
    elif field == 'registration':
        display_value = 'Требуется' if value else 'Не требуется'
    elif field == 'speakers':
        try:
            speakers = json.loads(value)
            display_value = ', '.join(speakers)
        except:
            display_value = str(value)
    elif field == 'max_participants':
        display_value = str(value) if value else 'Без ограничений'
    else:
        display_value = str(value)
    
    await message.answer(
        f"❓ Подтвердите изменение:\n\n"
        f"Поле: {field_name}\n"
        f"Новое значение: {display_value}",
        reply_markup=get_confirm_keyboard('edit_event', data['event_id'])
    )

# Обработка изображения при редактировании
@admin_router.message(EventEditForm.value, F.photo)
async def process_edit_image(message: Message, state: FSMContext):
    data = await state.get_data()
    if data['field'] == 'image':
        value = message.photo[-1].file_id
        await state.update_data(value=value)
        await state.set_state(EventEditForm.confirm)
        
        await message.answer(
            "❓ Подтвердите изменение изображения мероприятия:",
            reply_markup=get_confirm_keyboard('edit_event', data['event_id'])
        )

# Подтверждение редактирования
@admin_router.callback_query(F.data.startswith("confirm_edit_event_"))
async def confirm_edit_event(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    event_id = data['event_id']
    field = data['field']
    value = data['value']
    
    async for db in get_db():
        # Обновляем поле в базе данных
        field_mapping = {
            'title': Event.title,
            'short_description': Event.short_description,
            'full_description': Event.full_description,
            'date': Event.date,
            'location': Event.location,
            'speakers': Event.speakers,
            'image': Event.image_path,
            'registration': Event.registration_required,
            'max_participants': Event.max_participants
        }
        
        if field in field_mapping:
            await db.execute(
                update(Event)
                .where(Event.id == event_id)
                .values({field_mapping[field]: value})
            )
            await db.commit()
    
    await callback.message.edit_text(
        "✅ Мероприятие успешно отредактировано!",
        reply_markup=get_admin_main_menu_keyboard()
    )
    await state.clear()
    await callback.answer()

# Отмена редактирования
@admin_router.callback_query(F.data == "cancel_edit")
async def cancel_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    event_id = data.get('event_id')
    await state.clear()
    
    if event_id:
        # Возвращаемся к управлению мероприятием
        callback.data = f"manage_event_{event_id}"
        await manage_event(callback)
    else:
        await callback.message.edit_text(
            "❌ Редактирование отменено",
            reply_markup=get_admin_main_menu_keyboard()
        )
    await callback.answer()

# TODO: Добавить хендлеры для управления модераторами (только для is_admin)
# TODO: Добавить просмотр списка участников мероприятия
# TODO: Добавить массовую рассылку с опциональной регистрацией
# TODO: Добавить экспорт участников в файл