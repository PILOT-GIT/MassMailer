import json
import logging
import re
import smtplib
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any

from config import settings
from encryption import encryptor
from database import AsyncSessionLocal
from models import GmailAccount

logger = logging.getLogger(__name__)

def html_to_text(html_content: str) -> str:
    """Converts HTML to plain text using regex for standard email reader fallbacks."""
    text = html_content
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text.strip()

async def get_gmail_client(account_id: int) -> str:
    """Decrypts credentials and returns the Gmail App Password string."""
    async with AsyncSessionLocal() as session:
        acc = await session.get(GmailAccount, account_id)
        if not acc:
            raise ValueError(f"Gmail Account ID {account_id} not found in database.")
            
        token_data_str = encryptor.decrypt_token(acc.encrypted_credentials)
        token_data = json.loads(token_data_str)
        
    return token_data.get("app_password")

def build_mime_message(
    sender: str,
    recipient_email: str,
    subject: str,
    body_html: str,
    physical_address: str,
    unsubscribe_url: str
) -> MIMEMultipart:
    """Assembles a compliant multi-part MIME email object containing HTML and Plain Text parts."""
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient_email
    
    # Compliance: Add opt-out headers
    message["List-Unsubscribe"] = f"<{unsubscribe_url}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    
    # Compliance: physical address footer
    footer_html = (
        f"<br><br><hr>"
        f"<p style='font-size:11px;color:#666;font-family:sans-serif;'>"
        f"You are receiving this email because you opted in. "
        f"If you no longer want to receive these updates, you can "
        f"<a href='{unsubscribe_url}'>unsubscribe here</a>.<br>"
        f"Mailing Address: {physical_address}"
        f"</p>"
    )
    footer_text = (
        f"\n\n---\n"
        f"You are receiving this email because you opted in. "
        f"If you no longer want to receive these updates, you can unsubscribe here: {unsubscribe_url}\n"
        f"Mailing Address: {physical_address}"
    )

    full_html = body_html + footer_html
    full_text = html_to_text(body_html) + footer_text
    
    # Attach plain text fallback first
    part_text = MIMEText(full_text, "plain", "utf-8")
    message.attach(part_text)
    
    # Attach HTML part second (email clients prefer rendering the last attached block)
    part_html = MIMEText(full_html, "html", "utf-8")
    message.attach(part_html)
    
    return message

async def send_campaign_email(
    gmail_client: str,  # This parameter is the decrypted App Password string
    sender_email: str,
    recipient_email: str,
    subject: str,
    body_html: str,
    physical_address: str,
    unsubscribe_url: str
):
    """Executes message transmission via Gmail's SMTP server on port 587 using App Passwords."""
    message = build_mime_message(
        sender=sender_email,
        recipient_email=recipient_email,
        subject=subject,
        body_html=body_html,
        physical_address=physical_address,
        unsubscribe_url=unsubscribe_url
    )
    
    def _send_sync():
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender_email, gmail_client)
        server.send_message(message)
        server.quit()

    # Offload the blocking socket operations to a worker thread pool
    await asyncio.to_thread(_send_sync)
