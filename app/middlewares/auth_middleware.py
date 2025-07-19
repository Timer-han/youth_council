from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from app.database.database import get_db
from app.database.models import User
from app.config import ADMIN_IDS

class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем user_id в зависимости от типа события
        user_id = event.from_user.id
        
        # Проверяем, является ли пользователь админом или модератором
        async for db in get_db():
            user = await db.execute(select(User).where(User.telegram_id == user_id))
            user = user.scalar_one_or_none()
            
            if user and (user.is_admin or user.is_moderator):
                return await handler(event, data)
            
            if user_id in ADMIN_IDS:
                # Если пользователь в списке админов, но не в БД - создаем запись
                if not user:
                    user = User(
                        telegram_id=user_id,
                        username=event.from_user.username,
                        first_name=event.from_user.first_name,
                        last_name=event.from_user.last_name,
                        is_admin=True
                    )
                    db.add(user)
                    await db.commit()
                return await handler(event, data)
        
        # Если пользователь не админ/модератор - отправляем сообщение об ошибке
        if isinstance(event, CallbackQuery):
            await event.answer("⛔️ Доступ запрещён.", show_alert=True)
        else:
            await event.answer("⛔️ Доступ запрещён.")
        return None
