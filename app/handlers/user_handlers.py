from datetime import datetime
from typing import Optional
import json

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.utils.markdown import hbold, hitalic, hcode
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.database import get_db
from app.database.models import User, Event, Registration
from app.keyboards.user_keyboards import (
    get_main_menu_keyboard,
    get_events_pagination_keyboard,
    get_event_detail_keyboard,
    get_back_to_menu_keyboard,
    get_registration_keyboard
)
from app.config import EVENTS_PER_PAGE

user_router = Router()

async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    """Безопасное редактирование сообщения - обрабатывает случаи с медиа"""
    try:
        # Пытаемся отредактировать как обычное текстовое сообщение
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception as e:
        # Если не удалось (например, было медиа), удаляем старое и отправляем новое
        try:
            await callback.message.delete()
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except:
            # В крайнем случае просто отправляем новое сообщение
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

@user_router.message(Command("start"))
async def start_command(message: Message):
    """Обработчик команды /start"""
    welcome_text = (
        f"🎉 Ассаляму алейкум, {hbold(message.from_user.first_name)}!\n\n"
        f"Добро пожаловать в бот {hbold('Совета татарской молодёжи')}!\n\n"
        f"Здесь вы можете:\n"
        f"📅 Узнать о ближайших халяльных мероприятиях\n"
        f"✅ Зарегистрироваться на интересующие события\n"
        f"👥 Быть в курсе активностей татарской общины Москвы\n\n"
        f"Выберите действие в меню ниже:"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )

@user_router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    """Показать главное меню"""
    welcome_text = (
        f"🏠 {hbold('Главное меню')}\n\n"
        f"Выберите действие:"
    )
    
    await safe_edit_message(callback, welcome_text, get_main_menu_keyboard())
    await callback.answer()

@user_router.callback_query(F.data == "upcoming_events")
async def show_upcoming_events(callback: CallbackQuery):
    """Показать список ближайших мероприятий"""
    await show_events_page(callback, page=1)

@user_router.callback_query(F.data == "back_to_events")
async def back_to_events(callback: CallbackQuery):
    """Вернуться к списку мероприятий"""
    await show_events_page(callback, page=1)

@user_router.callback_query(F.data.startswith("events_page_"))
async def handle_events_pagination(callback: CallbackQuery):
    """Обработчик пагинации мероприятий"""
    page = int(callback.data.split("_")[-1])
    await show_events_page(callback, page)

async def show_events_page(callback: CallbackQuery, page: int):
    """Показать страницу мероприятий"""
    async for db in get_db():
        # Получаем общее количество предстоящих мероприятий
        total_query = select(func.count(Event.id)).where(Event.date >= datetime.now())
        total_result = await db.execute(total_query)
        total_events = total_result.scalar()
        
        if total_events == 0:
            await safe_edit_message(
                callback,
                "📅 На данный момент нет запланированных мероприятий.\n"
                "Следите за обновлениями!",
                get_back_to_menu_keyboard()
            )
            await callback.answer()
            return
        
        # Вычисляем offset для пагинации
        offset = (page - 1) * EVENTS_PER_PAGE
        
        # Получаем мероприятия для текущей страницы
        events_query = (
            select(Event)
            .where(Event.date >= datetime.now())
            .order_by(Event.date)
            .offset(offset)
            .limit(EVENTS_PER_PAGE)
        )
        events_result = await db.execute(events_query)
        events = events_result.scalars().all()
        
        # Формируем текст со списком мероприятий
        text = f"📅 {hbold('Ближайшие мероприятия')}\n\n"
        
        for i, event in enumerate(events, 1):
            event_date = event.date.strftime("%d.%m.%Y")
            event_time = event.date.strftime("%H:%M")
            
            speakers_text = ""
            if event.speakers:
                try:
                    speakers = json.loads(event.speakers)
                    if speakers:
                        speakers_text = f"\n👨‍🏫 {', '.join(speakers)}"
                except:
                    if event.speakers.strip():
                        speakers_text = f"\n👨‍🏫 {event.speakers}"
            
            text += (
                f"{hbold(f'{offset + i}. {event.title}')}\n"
                f"📅 {event_date} в {event_time}\n"
                f"📍 {event.location or 'Место уточняется'}"
                f"{speakers_text}\n\n"
                f"➡️ /event_{event.id} - подробнее\n\n"
            )
        
        # Создаем клавиатуру с пагинацией
        keyboard = get_events_pagination_keyboard(
            current_page=page,
            total_pages=(total_events + EVENTS_PER_PAGE - 1) // EVENTS_PER_PAGE,
            events=events
        )
        
        await safe_edit_message(callback, text, keyboard)
        await callback.answer()

@user_router.callback_query(F.data.startswith("event_"))
async def show_event_detail(callback: CallbackQuery):
    """Показать подробную информацию о мероприятии"""
    event_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    async for db in get_db():
        # Получаем мероприятие
        event_query = select(Event).where(Event.id == event_id)
        event_result = await db.execute(event_query)
        event = event_result.scalar_one_or_none()
        
        if not event:
            await callback.answer("Мероприятие не найдено", show_alert=True)
            return
        
        # Проверяем, зарегистрирован ли пользователь
        user_query = select(User).where(User.telegram_id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        is_registered = False
        if user:
            registration_query = select(Registration).where(
                and_(Registration.user_id == user.id, Registration.event_id == event_id)
            )
            registration_result = await db.execute(registration_query)
            is_registered = registration_result.scalar_one_or_none() is not None
        
        # Получаем количество зарегистрированных участников
        participants_query = select(func.count(Registration.id)).where(Registration.event_id == event_id)
        participants_result = await db.execute(participants_query)
        participants_count = participants_result.scalar()
        
        # Формируем текст с подробной информацией
        event_date = event.date.strftime("%d.%m.%Y")
        event_time = event.date.strftime("%H:%M")
        
        text = f"📅 {hbold(event.title)}\n\n"
        
        if event.short_description:
            text += f"{hitalic(event.short_description)}\n\n"
        
        text += f"📅 {hbold('Дата:')} {event_date}\n"
        text += f"⏰ {hbold('Время:')} {event_time}\n"
        text += f"📍 {hbold('Место:')} {event.location or 'Уточняется'}\n"
        
        if event.speakers:
            try:
                speakers = json.loads(event.speakers)
                if speakers:
                    text += f"👨‍🏫 {hbold('Спикеры:')} {', '.join(speakers)}\n"
            except:
                if event.speakers.strip():
                    text += f"👨‍🏫 {hbold('Спикеры:')} {event.speakers}\n"
        
        text += f"👥 {hbold('Зарегистрировано:')} {participants_count}"
        
        if event.max_participants:
            text += f" из {event.max_participants}"
        
        text += "\n\n"
        
        if event.full_description:
            text += f"{hbold('Описание:')}\n{event.full_description}\n\n"
        
        if is_registered:
            text += "✅ Вы зарегистрированы на это мероприятие"
        elif event.registration_required:
            if event.max_participants and participants_count >= event.max_participants:
                text += "❌ Регистрация закрыта (достигнут лимит участников)"
            else:
                text += "📝 Для участия требуется регистрация"
        
        # Создаем клавиатуру
        keyboard = get_event_detail_keyboard(
            event_id=event_id,
            is_registered=is_registered,
            registration_required=event.registration_required,
            registration_available=(
                event.registration_required and 
                not is_registered and 
                (not event.max_participants or participants_count < event.max_participants)
            )
        )
        
        # Если есть изображение, отправляем с фото
        if event.image_path:
            try:
                await callback.message.edit_media(
                    media=InputMediaPhoto(
                        media=event.image_path,
                        caption=text,
                        parse_mode="HTML"
                    ),
                    reply_markup=keyboard
                )
            except Exception as e:
                # Если не удалось загрузить изображение, используем безопасный метод
                await safe_edit_message(callback, text, keyboard)
        else:
            await safe_edit_message(callback, text, keyboard)
        
        await callback.answer()

@user_router.callback_query(F.data.startswith("register_"))
async def register_for_event(callback: CallbackQuery):
    """Регистрация на мероприятие"""
    event_id = int(callback.data.split("_")[1])
    telegram_user = callback.from_user
    
    async for db in get_db():
        # Получаем или создаем пользователя
        user_query = select(User).where(User.telegram_id == telegram_user.id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name
            )
            db.add(user)
            await db.flush()
        
        # Проверяем, не зарегистрирован ли уже
        existing_registration = await db.execute(
            select(Registration).where(
                and_(Registration.user_id == user.id, Registration.event_id == event_id)
            )
        )
        if existing_registration.scalar_one_or_none():
            await callback.answer("Вы уже зарегистрированы на это мероприятие!", show_alert=True)
            return
        
        # Проверяем лимит участников
        event_query = select(Event).where(Event.id == event_id)
        event_result = await db.execute(event_query)
        event = event_result.scalar_one_or_none()
        
        if not event:
            await callback.answer("Мероприятие не найдено", show_alert=True)
            return
        
        if event.max_participants:
            participants_count_query = select(func.count(Registration.id)).where(Registration.event_id == event_id)
            participants_count_result = await db.execute(participants_count_query)
            participants_count = participants_count_result.scalar()
            
            if participants_count >= event.max_participants:
                await callback.answer("К сожалению, достигнут лимит участников", show_alert=True)
                return
        
        # Создаем регистрацию
        registration = Registration(
            user_id=user.id,
            event_id=event_id
        )
        db.add(registration)
        await db.commit()
        
        await callback.answer("✅ Вы успешно зарегистрированы!", show_alert=True)
        
        # Обновляем информацию о мероприятии
        await show_event_detail(callback)

@user_router.callback_query(F.data == "my_profile")
async def show_user_profile(callback: CallbackQuery):
    """Показать профиль пользователя"""
    user_id = callback.from_user.id
    
    async for db in get_db():
        # Получаем пользователя
        user_query = select(User).where(User.telegram_id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            # Создаем пользователя если его нет
            user = User(
                telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name
            )
            db.add(user)
            await db.commit()
        
        # Получаем регистрации пользователя на предстоящие мероприятия
        registrations_query = (
            select(Registration)
            .options(selectinload(Registration.event))
            .where(Registration.user_id == user.id)
            .join(Event)
            .where(Event.date >= datetime.now())
            .order_by(Event.date)
        )
        registrations_result = await db.execute(registrations_query)
        registrations = registrations_result.scalars().all()
        
        # Формируем текст профиля
        text = f"👤 {hbold('Мой профиль')}\n\n"
        text += f"👋 {hbold('Имя:')} {user.first_name}"
        if user.last_name:
            text += f" {user.last_name}"
        text += "\n"
        
        if user.username:
            text += f"📝 {hbold('Username:')} @{user.username}\n"
        
        if user.phone:
            text += f"📱 {hbold('Телефон:')} {user.phone}\n"
        
        text += f"📅 {hbold('Дата регистрации:')} {user.created_at.strftime('%d.%m.%Y')}\n\n"
        
        if registrations:
            text += f"📝 {hbold('Мои регистрации:')}\n\n"
            for reg in registrations:
                event_date = reg.event.date.strftime("%d.%m.%Y")
                event_time = reg.event.date.strftime("%H:%M")
                text += f"• {hbold(reg.event.title)}\n"
                text += f"  📅 {event_date} в {event_time}\n"
                text += f"  📍 {reg.event.location or 'Место уточняется'}\n\n"
        else:
            text += "📝 У вас пока нет регистраций на предстоящие мероприятия."
        
        await safe_edit_message(callback, text, get_back_to_menu_keyboard())
        await callback.answer()

@user_router.message(F.text.startswith('/event_'))
async def event_command(message: Message):
    """Обработчик команды /event_X"""
    try:
        event_id = int(message.text.split('_')[1])
        # Создаем фиктивный callback для переиспользования логики
        callback_data = f"event_{event_id}"
        
        class MockCallbackQuery:
            def __init__(self, message, user, data):
                self.message = message
                self.from_user = user
                self.data = data
            
            async def answer(self, text=None, show_alert=False):
                pass
        
        mock_callback = MockCallbackQuery(message, message.from_user, callback_data)
        await show_event_detail(mock_callback)
        
    except (ValueError, IndexError):
        await message.answer(
            "❌ Неверный формат команды. Используйте /event_ID, где ID - номер мероприятия.",
            reply_markup=get_main_menu_keyboard()
        )