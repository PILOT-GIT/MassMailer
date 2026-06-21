import json
import logging
import re
import smtplib
import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from database import AsyncSessionLocal
from models import User, GmailAccount
from encryption import encryptor
from bot.states import GmailAuthStates
from bot.keyboards import get_gmail_menu_keyboard, get_cancel_keyboard

logger = logging.getLogger(__name__)
router = Router()

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def test_smtp_credentials(email: str, password: str) -> bool:
    """Synchronously checks if SMTP login succeeds with the provided credentials."""
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(email, password)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"SMTP authentication verification failed for {email}: {str(e)}")
        return False

@router.callback_query(F.data == "gmail:list")
async def process_list_gmail_accounts(callback: CallbackQuery, db_user: User):
    async with AsyncSessionLocal() as session:
        stmt = select(GmailAccount).where(GmailAccount.user_id == db_user.id)
        result = await session.execute(stmt)
        accounts = result.scalars().all()

    if not accounts:
        await callback.message.edit_text(
            text="🔴 **No Gmail accounts connected.**\n\nPlease add a Gmail Account using the menu below to send campaigns.",
            parse_mode="Markdown",
            reply_markup=get_gmail_menu_keyboard()
        )
    else:
        account_list = "\n".join([f"• `{acc.email}`" for acc in accounts])
        text = f"🟢 **Connected Gmail Accounts:**\n\n{account_list}"
        await callback.message.edit_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=get_gmail_menu_keyboard()
        )
    await callback.answer()

@router.callback_query(F.data == "gmail:connect")
async def process_connect_gmail_auth_link(callback: CallbackQuery, state: FSMContext):
    """Entry point for connecting Gmail Account. Prompts for email address."""
    await state.set_state(GmailAuthStates.email_input)
    await callback.message.edit_text(
        text="✉️ **Step 1: Add Gmail Account**\n\nEnter your Gmail email address:",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard("gmail")
    )
    await callback.answer()

@router.message(GmailAuthStates.email_input)
async def process_gmail_email_input(message: Message, state: FSMContext):
    """Processes email input and validates format."""
    email = message.text.strip().lower()
    if not EMAIL_REGEX.match(email):
        await message.answer("❌ Invalid email format. Please send a valid Gmail email address.")
        return

    await state.update_data(email=email)
    await state.set_state(GmailAuthStates.password_input)
    await message.answer(
        text=(
            "🔑 **Step 2: Enter App Password**\n\n"
            "Enter your 16-character Gmail App Password.\n"
            "(Go to myaccount.google.com -> App Passwords to generate it. Paste it without spaces)."
        ),
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard("gmail")
    )

@router.message(GmailAuthStates.password_input)
async def process_gmail_password_input(message: Message, state: FSMContext, db_user: User):
    """Processes app password input, runs connection check, and encrypts credentials to database."""
    raw_password = message.text
    # Sanitize spaces
    cleaned_password = raw_password.replace(" ", "").strip()

    if len(cleaned_password) != 16:
        await message.answer(
            "❌ Gmail App Passwords must be exactly 16 characters long.\n"
            "Please copy it and paste it again:"
        )
        return

    data = await state.get_data()
    email = data.get("email")

    status_message = await message.answer("🔄 Verifying connection via Gmail SMTP. Please wait...")

    # Run blocking SMTP login check inside a background thread pool
    auth_success = await asyncio.to_thread(test_smtp_credentials, email, cleaned_password)

    if not auth_success:
        await status_message.delete()
        await message.answer(
            "❌ **SMTP Authentication Failed**\n\n"
            "Gmail SMTP server rejected the credentials. Please ensure:\n"
            "1. 2-Step Verification is enabled on your Google Account.\n"
            "2. You generated a valid 'App Password' for Mail.\n"
            "3. The email matches the Google account.\n\n"
            "Please try pasting the 16-character App Password again:"
        )
        return

    # Encrypt the App Password payload
    payload = json.dumps({"app_password": cleaned_password})
    encrypted_credentials = encryptor.encrypt_token(payload)

    # Save to the remote Supabase Postgres instance
    async with AsyncSessionLocal() as session:
        stmt = select(GmailAccount).where(
            GmailAccount.user_id == db_user.id,
            GmailAccount.email == email
        )
        res = await session.execute(stmt)
        gmail_account = res.scalar_one_or_none()

        if gmail_account:
            gmail_account.encrypted_credentials = encrypted_credentials
        else:
            gmail_account = GmailAccount(
                user_id=db_user.id,
                email=email,
                encrypted_credentials=encrypted_credentials
            )
            session.add(gmail_account)

        await session.commit()

    await state.clear()
    await status_message.delete()
    await message.answer(
        text=(
            f"🟢 **Gmail Account Added Successfully!**\n\n"
            f"Address `{email}` is now connected and ready to send campaigns."
        ),
        parse_mode="Markdown",
        reply_markup=get_gmail_menu_keyboard()
    )
