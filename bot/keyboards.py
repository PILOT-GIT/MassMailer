from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Tuple

def get_main_menu_keyboard(is_approved: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not is_approved:
        builder.button(text="🔄 Check Approval Status", callback_data="auth:check_approval")
        return builder.as_markup()
        
    builder.button(text="📧 Campaigns", callback_data="menu:campaigns")
    builder.button(text="👥 Target Lists", callback_data="menu:lists")
    builder.button(text="⚙️ Gmail Accounts", callback_data="menu:gmail")
    builder.button(text="👤 Profile & Compliance", callback_data="menu:profile")
    builder.adjust(2, 2)
    return builder.as_markup()

def get_campaign_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Create Campaign", callback_data="campaign:create")
    builder.button(text="📜 View Campaigns", callback_data="campaign:list")
    builder.button(text="🔙 Back to Main Menu", callback_data="back:main")
    builder.adjust(1)
    return builder.as_markup()

def get_list_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Upload New List", callback_data="list:create")
    builder.button(text="📜 View Lists", callback_data="list:list")
    builder.button(text="🔙 Back to Main Menu", callback_data="back:main")
    builder.adjust(1)
    return builder.as_markup()

def get_gmail_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Add Gmail Account", callback_data="gmail:connect")
    builder.button(text="📜 View Accounts", callback_data="gmail:list")
    builder.button(text="🔙 Back to Main Menu", callback_data="back:main")
    builder.adjust(1)
    return builder.as_markup()

def get_profile_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Edit Physical Address", callback_data="profile:edit_address")
    builder.button(text="🔙 Back to Main Menu", callback_data="back:main")
    builder.adjust(1)
    return builder.as_markup()

def get_dynamic_selection_keyboard(options: List[Tuple[str, str]], back_target: str) -> InlineKeyboardMarkup:
    """Generates an inline keyboard for dynamic lists (e.g. lists of senders or lists of target segments)."""
    builder = InlineKeyboardBuilder()
    for label, callback in options:
        builder.button(text=label, callback_data=callback)
    builder.button(text="❌ Cancel", callback_data=f"back:{back_target}")
    builder.adjust(1)
    return builder.as_markup()

def get_schedule_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Send Immediately", callback_data="schedule:now")
    builder.button(text="📅 Schedule for Future Time", callback_data="schedule:future")
    builder.button(text="❌ Cancel", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()

def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirm & Launch", callback_data="campaign:confirm")
    builder.button(text="❌ Cancel & Delete Draft", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()

def get_cancel_keyboard(back_target: str = "main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Cancel", callback_data=f"back:{back_target}")
    return builder.as_markup()
