from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from database import AsyncSessionLocal
from models import User
from config import settings

class ApprovalMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Determine the user ID based on the event type
        user_id = None
        username = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id
            username = event.from_user.username
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            username = event.from_user.username

        if not user_id:
            return await handler(event, data)

        async with AsyncSessionLocal() as session:
            # Look up the user in Postgres
            stmt = select(User).where(User.telegram_id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            # Auto-approve the admin to ease deployment and testing bootstrap
            if not user and user_id == settings.ADMIN_TELEGRAM_ID:
                user = User(
                    telegram_id=user_id,
                    telegram_username=username,
                    is_approved=True
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

            # If user does not exist or isn't approved, block execution
            if not user or not user.is_approved:
                # If they already exist in database but are not approved yet
                if not user:
                    # Register them as unapproved
                    new_user = User(
                        telegram_id=user_id,
                        telegram_username=username,
                        is_approved=False
                    )
                    session.add(new_user)
                    await session.commit()

                # Notify user and halt propagation
                warning_text = (
                    f"⚠️ **Access Denied**\n\n"
                    f"Your account is currently pending approval.\n"
                    f"**Telegram ID:** `{user_id}`\n\n"
                    f"Please contact your administrator to authorize your account."
                )
                if isinstance(event, Message):
                    await event.answer(warning_text, parse_mode="Markdown")
                elif isinstance(event, CallbackQuery):
                    await event.answer("Access Denied. Account pending approval.", show_alert=True)
                    await event.message.answer(warning_text, parse_mode="Markdown")
                return

            # Inject the user object into the handler context data dict
            data["db_user"] = user
            data["db_session"] = session
            return await handler(event, data)
