from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import AsyncSessionLocal
from models import User
from bot.keyboards import get_profile_keyboard, get_cancel_keyboard

router = Router()

class ProfileStates(StatesGroup):
    editing_address = State()

@router.callback_query(F.data == "profile:edit_address")
async def process_edit_address_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileStates.editing_address)
    await callback.message.edit_text(
        text=(
            "📝 **Compliance: Edit Physical Address**\n\n"
            "Please send the physical address you want to appear in the footer of your email campaigns."
        ),
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard("profile")
    )
    await callback.answer()

@router.message(ProfileStates.editing_address)
async def process_address_update_input(message: Message, state: FSMContext, db_user: User):
    address = message.text.strip()
    if not address or len(address) < 10:
        await message.answer("❌ Invalid address. Please send your full valid physical address.")
        return

    # Update in database
    async with AsyncSessionLocal() as session:
        # Load user back in current transaction session context
        db_user_ref = await session.get(User, db_user.id)
        if db_user_ref:
            db_user_ref.physical_address = address
            await session.commit()

    await state.clear()
    await message.answer(
        text=f"✅ **Address updated successfully!**\n\nNew Address: `{address}`",
        parse_mode="Markdown",
        reply_markup=get_profile_keyboard()
    )
