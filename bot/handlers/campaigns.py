from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from database import AsyncSessionLocal
from models import User, TargetList, GmailAccount, Campaign, CampaignSender, CampaignTarget, TargetEmail
from bot.states import CampaignCreationStates
from bot.keyboards import (
    get_campaign_menu_keyboard,
    get_dynamic_selection_keyboard,
    get_schedule_keyboard,
    get_confirmation_keyboard,
    get_cancel_keyboard
)
from scheduler import schedule_campaign_job, execute_campaign_worker

router = Router()

@router.callback_query(F.data == "campaign:list")
async def process_view_campaigns(callback: CallbackQuery, db_user: User):
    async with AsyncSessionLocal() as session:
        stmt = select(Campaign).where(Campaign.user_id == db_user.id)
        result = await session.execute(stmt)
        campaigns = result.scalars().all()

        camp_details = []
        for camp in campaigns:
            # Count targets sent / total
            sent_stmt = select(CampaignTarget).where(
                CampaignTarget.campaign_id == camp.id,
                CampaignTarget.status == 'sent'
            )
            sent_res = await session.execute(sent_stmt)
            sent_count = len(sent_res.scalars().all())

            total_stmt = select(CampaignTarget).where(CampaignTarget.campaign_id == camp.id)
            total_res = await session.execute(total_stmt)
            total_count = len(total_res.scalars().all())

            camp_details.append(
                f"📧 **{camp.subject}**\n"
                f"• Status: `{camp.status.upper()}`\n"
                f"• Progress: `{sent_count}/{total_count}` emails sent\n"
                f"• Scheduled: `{camp.scheduled_send_time or 'Immediate'}`"
            )

    if not camp_details:
        await callback.message.edit_text(
            text="📧 **No campaigns created yet.**\n\nStart a new draft using the menu below.",
            parse_mode="Markdown",
            reply_markup=get_campaign_menu_keyboard()
        )
    else:
        text = "📧 **Your Campaigns:**\n\n" + "\n\n".join(camp_details)
        await callback.message.edit_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=get_campaign_menu_keyboard()
        )
    await callback.answer()

# --- Creation Wizard Flow ---

@router.callback_query(F.data == "campaign:create")
async def process_campaign_create_list(callback: CallbackQuery, state: FSMContext, db_user: User):
    async with AsyncSessionLocal() as session:
        stmt = select(TargetList).where(TargetList.user_id == db_user.id)
        result = await session.execute(stmt)
        lists = result.scalars().all()

    if not lists:
        await callback.message.edit_text(
            text="❌ **No Target Lists Available**\n\nYou must upload a subscriber list before creating a campaign.",
            parse_mode="Markdown",
            reply_markup=get_campaign_menu_keyboard()
        )
        await callback.answer()
        return

    options = [(lst.name, f"camp_list:{lst.id}") for lst in lists]
    await state.set_state(CampaignCreationStates.selecting_target_list)
    await callback.message.edit_text(
        text="📂 **Step 1: Choose Target List**\n\nSelect the subscriber list to receive this email campaign:",
        parse_mode="Markdown",
        reply_markup=get_dynamic_selection_keyboard(options, "campaigns")
    )
    await callback.answer()

@router.callback_query(CampaignCreationStates.selecting_target_list, F.data.startswith("camp_list:"))
async def process_select_list_callback(callback: CallbackQuery, state: FSMContext, db_user: User):
    list_id = int(callback.data.split(":")[1])
    await state.update_data(list_id=list_id)

    async with AsyncSessionLocal() as session:
        stmt = select(GmailAccount).where(GmailAccount.user_id == db_user.id)
        result = await session.execute(stmt)
        accounts = result.scalars().all()

    if not accounts:
        await callback.message.edit_text(
            text="❌ **No Gmail Senders Connected**\n\nYou must connect at least one Gmail account in settings first.",
            parse_mode="Markdown",
            reply_markup=get_campaign_menu_keyboard()
        )
        await state.clear()
        await callback.answer()
        return

    options = [(acc.email, f"camp_send:{acc.id}") for acc in accounts]
    await state.set_state(CampaignCreationStates.selecting_sender)
    await callback.message.edit_text(
        text="⚙️ **Step 2: Select Sender Account**\n\nChoose the connected Gmail address to send from:",
        parse_mode="Markdown",
        reply_markup=get_dynamic_selection_keyboard(options, "campaigns")
    )
    await callback.answer()

@router.callback_query(CampaignCreationStates.selecting_sender, F.data.startswith("camp_send:"))
async def process_select_sender_callback(callback: CallbackQuery, state: FSMContext):
    gmail_account_id = int(callback.data.split(":")[1])
    await state.update_data(gmail_account_id=gmail_account_id)
    
    await state.set_state(CampaignCreationStates.entering_subject)
    await callback.message.edit_text(
        text="📝 **Step 3: Enter Email Subject**\n\nType and send the email subject line.",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard("campaigns")
    )
    await callback.answer()

@router.message(CampaignCreationStates.entering_subject)
async def process_subject_input(message: Message, state: FSMContext):
    subject = message.text.strip()
    if not subject or len(subject) > 200:
        await message.answer("❌ Invalid subject line. Please enter a shorter subject line.")
        return

    await state.update_data(subject=subject)
    await state.set_state(CampaignCreationStates.entering_body)
    await message.answer(
        text=(
            "✉️ **Step 4: Enter HTML Email Body**\n\n"
            "Please send the message body. You can use standard HTML formatting tags.\n\n"
            "**Supported Personalization Tags:**\n"
            "• `{first_name}` - Inserts the subscriber's first name\n"
            "• `{last_name}` - Inserts the subscriber's last name"
        ),
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard("campaigns")
    )

@router.message(CampaignCreationStates.entering_body)
async def process_body_input(message: Message, state: FSMContext, db_user: User):
    body = message.text.strip()
    if not body:
        await message.answer("❌ Body text cannot be empty. Please send a valid message.")
        return

    await state.update_data(body=body)
    
    # Check if user already has a saved physical address for default skip
    if db_user.physical_address:
        await state.update_data(address=db_user.physical_address)
        await state.set_state(CampaignCreationStates.selecting_schedule)
        await message.answer(
            text=(
                f"🏠 **Compliance: Physical Address**\n\n"
                f"Using profile address: `{db_user.physical_address}`\n\n"
                f"📅 **Step 5: Set Send Schedule**\n"
                f"Choose when this campaign should fire."
            ),
            parse_mode="Markdown",
            reply_markup=get_schedule_keyboard()
        )
    else:
        await state.set_state(CampaignCreationStates.entering_address)
        await message.answer(
            text=(
                "🏠 **Step 5: Compliance - Physical Address**\n\n"
                "To comply with anti-spam laws (e.g. CAN-SPAM), you must supply a physical mailing address "
                "which will be appended to the email footer. Please reply with your physical address:"
            ),
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard("campaigns")
        )

@router.message(CampaignCreationStates.entering_address)
async def process_address_input(message: Message, state: FSMContext):
    address = message.text.strip()
    if not address or len(address) < 10:
        await message.answer("❌ Address is too short. Please provide a full valid physical address.")
        return

    await state.update_data(address=address)
    await state.set_state(CampaignCreationStates.selecting_schedule)
    await message.answer(
        text="📅 **Step 6: Set Send Schedule**\n\nChoose when this campaign should be executed.",
        parse_mode="Markdown",
        reply_markup=get_schedule_keyboard()
    )

@router.callback_query(CampaignCreationStates.selecting_schedule, F.data == "schedule:now")
async def process_schedule_now(callback: CallbackQuery, state: FSMContext):
    await state.update_data(schedule_time="now")
    await render_confirmation(callback, state)
    await callback.answer()

@router.callback_query(CampaignCreationStates.selecting_schedule, F.data == "schedule:future")
async def process_schedule_future_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CampaignCreationStates.entering_custom_time)
    await callback.message.edit_text(
        text=(
            "📅 **Enter Date & Time**\n\n"
            "Please send the scheduled date/time in the following format (UTC):\n"
            "`YYYY-MM-DD HH:MM`\n\n"
            "Example: `2026-06-25 10:00`"
        ),
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard("campaigns")
    )
    await callback.answer()

@router.message(CampaignCreationStates.entering_custom_time)
async def process_custom_time_input(message: Message, state: FSMContext):
    time_str = message.text.strip()
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        if dt <= datetime.utcnow():
            await message.answer("❌ Scheduled time must be in the future (UTC). Please retry.")
            return
        
        await state.update_data(schedule_time=time_str)
        # Render confirmation page next
        await render_confirmation_message(message, state)
    except ValueError:
        await message.answer("❌ Invalid format. Please use `YYYY-MM-DD HH:MM`.")

async def render_confirmation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    preview = await get_campaign_preview_text(data)
    await state.set_state(CampaignCreationStates.confirming_campaign)
    await callback.message.edit_text(
        text=preview,
        parse_mode="Markdown",
        reply_markup=get_confirmation_keyboard()
    )

async def render_confirmation_message(message: Message, state: FSMContext):
    data = await state.get_data()
    preview = await get_campaign_preview_text(data)
    await state.set_state(CampaignCreationStates.confirming_campaign)
    await message.answer(
        text=preview,
        parse_mode="Markdown",
        reply_markup=get_confirmation_keyboard()
    )

async def get_campaign_preview_text(data: dict) -> str:
    list_name, sender_email = "Unknown List", "Unknown Email"
    
    async with AsyncSessionLocal() as session:
        # Fetch human-readable representations
        lst = await session.get(TargetList, data.get("list_id"))
        if lst:
            list_name = lst.name
        acc = await session.get(GmailAccount, data.get("gmail_account_id"))
        if acc:
            sender_email = acc.email

    text = (
        f"📊 **Campaign Summary Confirmation**\n\n"
        f"📧 **Subject:** {data.get('subject')}\n"
        f"👥 **Target List:** {list_name}\n"
        f"⚙️ **Gmail Sender:** `{sender_email}`\n"
        f"🏠 **Compliance Address:** `{data.get('address')}`\n"
        f"📅 **Schedule:** `{data.get('schedule_time')}`\n\n"
        f"**Preview of HTML Body:**\n"
        f"```html\n"
        f"{data.get('body')}\n"
        f"```\n"
        f"⚠️ *Please review the details above. Click Confirm to compile the queue.*"
    )
    return text

@router.callback_query(CampaignCreationStates.confirming_campaign, F.data == "campaign:confirm")
async def process_campaign_confirm_save(callback: CallbackQuery, state: FSMContext, db_user: User):
    data = await state.get_data()
    await state.clear()
    
    list_id = data.get("list_id")
    gmail_account_id = data.get("gmail_account_id")
    subject = data.get("subject")
    body = data.get("body")
    address = data.get("address")
    schedule_val = data.get("schedule_time")

    # Set status
    if schedule_val == "now":
        status = "sending"
        sched_time = None
    else:
        status = "scheduled"
        sched_time = datetime.strptime(schedule_val, "%Y-%m-%d %H:%M")

    async with AsyncSessionLocal() as session:
        # 1. Create Campaign
        new_camp = Campaign(
            user_id=db_user.id,
            list_id=list_id,
            subject=subject,
            body_html=body,
            physical_address=address,
            status=status,
            scheduled_send_time=sched_time
        )
        session.add(new_camp)
        await session.commit()
        await session.refresh(new_camp)

        # 2. Add to CampaignSender
        new_sender = CampaignSender(
            campaign_id=new_camp.id,
            gmail_account_id=gmail_account_id
        )
        session.add(new_sender)

        # 3. Create target send queue entries
        stmt = select(TargetEmail).where(
            TargetEmail.list_id == list_id,
            TargetEmail.is_unsubscribed == False
        )
        result = await session.execute(stmt)
        emails = result.scalars().all()

        for target_email in emails:
            camp_target = CampaignTarget(
                campaign_id=new_camp.id,
                target_email_id=target_email.id,
                status="pending"
            )
            session.add(camp_target)
        await session.commit()

    # 4. Trigger Scheduler
    if status == "sending":
        # Launch immediate background worker task
        await execute_campaign_worker(new_camp.id)
        await callback.message.edit_text(
            text="🚀 **Campaign compilation complete.** Emails are now being delivered.",
            parse_mode="Markdown",
            reply_markup=get_campaign_menu_keyboard()
        )
    else:
        # Register standard cron-date job inside Postgres JobStore
        await schedule_campaign_job(new_camp.id, sched_time)
        await callback.message.edit_text(
            text=f"📅 **Campaign scheduled successfully!** Run date: `{schedule_val}` UTC.",
            parse_mode="Markdown",
            reply_markup=get_campaign_menu_keyboard()
        )
    await callback.answer()
