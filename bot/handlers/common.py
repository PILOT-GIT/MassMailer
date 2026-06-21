from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.keyboards import (
    get_main_menu_keyboard,
    get_campaign_menu_keyboard,
    get_list_menu_keyboard,
    get_gmail_menu_keyboard,
    get_profile_keyboard
)
from models import User

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User):
    welcome_text = (
        f"👋 Hello, @{db_user.telegram_username or 'User'}!\n\n"
        f"Welcome to the **Gmail Campaign Manager** Telegram Bot.\n"
        f"Use the dashboard below to configure settings, create lists, "
        f"and schedule compliant opt-in email campaigns."
    )
    await message.answer(
        text=welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(is_approved=True)
    )

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer(
        text="🎛️ **Main Menu Dashboard**",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(is_approved=True)
    )

@router.callback_query(F.data == "back:main")
@router.callback_query(F.data == "cancel")
async def process_cancel_or_back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        text="🎛️ **Main Menu Dashboard**",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard(is_approved=True)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("menu:"))
async def process_menu_navigation(callback: CallbackQuery):
    menu_type = callback.data.split(":")[1]
    
    if menu_type == "campaigns":
        await callback.message.edit_text(
            text="📧 **Campaign Dashboard**\nCreate, track, and manage your email campaigns.",
            parse_mode="Markdown",
            reply_markup=get_campaign_menu_keyboard()
        )
    elif menu_type == "lists":
        await callback.message.edit_text(
            text="👥 **Target List Dashboard**\nUpload, modify, and manage subscriber segments.",
            parse_mode="Markdown",
            reply_markup=get_list_menu_keyboard()
        )
    elif menu_type == "gmail":
        await callback.message.edit_text(
            text="⚙️ **Gmail Accounts Connection**\nLink new sender credentials or review authenticated accounts.",
            parse_mode="Markdown",
            reply_markup=get_gmail_menu_keyboard()
        )
    elif menu_type == "profile":
        await callback.message.edit_text(
            text="👤 **Profile & Compliance Settings**\nSet your required physical mailing address for CAN-SPAM compliance.",
            parse_mode="Markdown",
            reply_markup=get_profile_keyboard()
        )
    await callback.answer()
