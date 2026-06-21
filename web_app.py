import json
import logging
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
import httpx
from sqlalchemy import select, update

from config import settings
from database import AsyncSessionLocal
from models import User, GmailAccount, TargetEmail, CampaignTarget
from encryption import encryptor

logger = logging.getLogger(__name__)
web_app = FastAPI(title="Gmail Campaign Bot Web Helper")


@web_app.get("/unsubscribe/{recipient_id}/{campaign_id}", response_class=HTMLResponse)
async def process_unsubscribe(recipient_id: int, campaign_id: int):
    """Processes recipient opt-out actions."""
    async with AsyncSessionLocal() as session:
        # Load email record
        email_record = await session.get(TargetEmail, recipient_id)
        if not email_record:
            raise HTTPException(status_code=404, detail="Subscriber record not found.")

        # Update opt-out states
        email_record.is_unsubscribed = True
        email_record.unsubscribed_at = datetime.utcnow()
        
        # Log opt-out in current Campaign queue logs if active
        await session.execute(
            update(CampaignTarget)
            .where(CampaignTarget.campaign_id == campaign_id, CampaignTarget.target_email_id == recipient_id)
            .values(status="failed", error_message="Recipient unsubscribed via click.")
        )
        await session.commit()

    # Simple compliance success message
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Unsubscribed Successfully</title>
        <style>
            body { font-family: -apple-system, sans-serif; text-align: center; padding: 50px; background-color: #fafafa; color: #333; }
            .card { background: white; padding: 40px 30px; border-radius: 8px; border: 1px solid #eaeaea; display: inline-block; max-width: 420px; }
            h2 { color: #e74c3c; font-weight: 500; }
            p { color: #777; font-size: 14px; line-height: 1.6; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Opt-out Processed</h2>
            <p>You have been successfully removed from this mailing list and will no longer receive campaigns from this sender.</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
