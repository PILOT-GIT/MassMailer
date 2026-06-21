import csv
import io
import re
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, delete
from database import AsyncSessionLocal
from models import User, TargetList, TargetEmail
from bot.states import TargetListStates
from bot.keyboards import get_list_menu_keyboard, get_cancel_keyboard

router = Router()
EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")

@router.callback_query(F.data == "list:list")
async def process_view_lists(callback: CallbackQuery, db_user: User):
    async with AsyncSessionLocal() as session:
        stmt = select(TargetList).where(TargetList.user_id == db_user.id)
        result = await session.execute(stmt)
        lists = result.scalars().all()
        
        list_details = []
        for lst in lists:
            # Count subscribers
            count_stmt = select(TargetEmail).where(
                TargetEmail.list_id == lst.id,
                TargetEmail.is_unsubscribed == False
            )
            count_res = await session.execute(count_stmt)
            count = len(count_res.scalars().all())
            list_details.append(f"• **{lst.name}** ({count} active subscribers)")

    if not list_details:
        await callback.message.edit_text(
            text="👥 **No target lists found.**\n\nUpload a CSV list to start campaigns.",
            parse_mode="Markdown",
            reply_markup=get_list_menu_keyboard()
        )
    else:
        text = "👥 **Your Target Lists:**\n\n" + "\n".join(list_details)
        await callback.message.edit_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=get_list_menu_keyboard()
        )
    await callback.answer()

@router.callback_query(F.data == "list:create")
async def process_create_list_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TargetListStates.entering_list_name)
    await callback.message.edit_text(
        text="📝 **Step 1: Name Your List**\n\nPlease reply with a descriptive name for this subscriber list.",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard("lists")
    )
    await callback.answer()

@router.message(TargetListStates.entering_list_name)
async def process_list_name_input(message: Message, state: FSMContext):
    list_name = message.text.strip()
    if not list_name or len(list_name) > 100:
        await message.answer("❌ Invalid name. Please send a shorter text name.")
        return
        
    await state.update_data(list_name=list_name)
    await state.set_state(TargetListStates.uploading_csv)
    await message.answer(
        text=(
            f"📂 **Step 2: Upload CSV File for '{list_name}'**\n\n"
            f"Please upload a `.csv` document containing your opt-in subscribers.\n\n"
            f"**Expected CSV columns (comma-separated):**\n"
            f"`email`, `first_name`, `last_name`\n\n"
            f"*Make sure headers match exactly. Max size: 2MB.*"
        ),
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard("lists")
    )

@router.message(TargetListStates.uploading_csv, F.document)
async def process_list_csv_upload(message: Message, state: FSMContext, bot: Bot, db_user: User):
    document = message.document
    if not document.file_name.endswith('.csv'):
        await message.answer("❌ Invalid format. Please upload a file ending with `.csv`.")
        return

    # Check file size limit (2MB)
    if document.file_size > 2 * 1024 * 1024:
        await message.answer("❌ File too large. Please limit list size to under 2MB.")
        return

    # Downloader step
    file_info = await bot.get_file(document.file_id)
    file_bytes = await bot.download_file(file_info.file_path)
    
    # Read CSV in memory
    try:
        csv_data = io.StringIO(file_bytes.read().decode('utf-8'))
        reader = csv.DictReader(csv_data)
        
        # Verify Headers
        required_headers = {'email', 'first_name', 'last_name'}
        if not required_headers.issubset(set(reader.fieldnames or [])):
            await message.answer("❌ CSV missing required headers. Headers must include `email`, `first_name`, `last_name`.")
            return
            
        contacts = []
        for idx, row in enumerate(reader):
            email = row.get('email', '').strip()
            first_name = row.get('first_name', '').strip() or None
            last_name = row.get('last_name', '').strip() or None
            
            if not email or not EMAIL_REGEX.match(email):
                continue  # skip invalid emails
                
            contacts.append({
                "email": email,
                "first_name": first_name,
                "last_name": last_name
            })
            
    except Exception as e:
        await message.answer(f"❌ Failed to parse CSV file: {str(e)}")
        return

    if not contacts:
        await message.answer("❌ No valid contacts found in the uploaded file.")
        return

    # Database insertion
    data = await state.get_data()
    list_name = data.get("list_name")
    
    async with AsyncSessionLocal() as session:
        # Create TargetList
        new_list = TargetList(user_id=db_user.id, name=list_name)
        session.add(new_list)
        await session.commit()
        await session.refresh(new_list)

        # Batch insert TargetEmails
        for contact in contacts:
            email_record = TargetEmail(
                list_id=new_list.id,
                email=contact["email"],
                first_name=contact["first_name"],
                last_name=contact["last_name"]
            )
            session.add(email_record)
        await session.commit()

    await state.clear()
    await message.answer(
        text=(
            f"🎉 **List Uploaded successfully!**\n\n"
            f"List Name: **{list_name}**\n"
            f"Valid Contacts Processed: `{len(contacts)}`"
        ),
        parse_mode="Markdown",
        reply_markup=get_list_menu_keyboard()
    )
