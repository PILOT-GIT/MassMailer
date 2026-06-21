import asyncio
import logging
from datetime import datetime
from typing import Any, List, Set, Tuple
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import create_engine
from sqlalchemy import select, update

from config import settings
from database import AsyncSessionLocal, sync_database_url, sync_connect_args
from models import Campaign, CampaignSender, CampaignTarget, TargetEmail, GmailAccount, User, Job
from gmail_service import get_gmail_client, send_campaign_email

logger = logging.getLogger(__name__)

# Persistent job store mapping. APScheduler needs a sync SQLAlchemy engine even
# while the app itself uses SQLAlchemy's async engine.
scheduler_engine = create_engine(
    sync_database_url(settings.DATABASE_URL),
    connect_args=sync_connect_args(settings.DATABASE_URL),
)
jobstores = {
    'default': SQLAlchemyJobStore(engine=scheduler_engine)
}
scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")

# In-memory registration tracker to prevent overlapping runs on the same campaign
active_campaign_runs: Set[int] = set()

async def schedule_campaign_job(campaign_id: int, run_at: datetime):
    """Schedules a campaign job inside the persistent APScheduler JobStore."""
    job_id = f"campaign_{campaign_id}"
    scheduler.add_job(
        execute_campaign_worker_task,
        trigger='date',
        run_date=run_at,
        args=[campaign_id],
        id=job_id,
        replace_existing=True
    )
    
    # Store schedule metadata in jobs table for query visibility
    async with AsyncSessionLocal() as session:
        # Clear any existing reference
        from sqlalchemy import delete
        await session.execute(delete(Job).where(Job.campaign_id == campaign_id))
        
        new_job = Job(
            campaign_id=campaign_id,
            apscheduler_job_id=job_id,
            run_at=run_at
        )
        session.add(new_job)
        await session.commit()

async def execute_campaign_worker(campaign_id: int):
    """Triggers campaign processing immediately in a separate async background task context."""
    if campaign_id in active_campaign_runs:
        logger.warning(f"Campaign {campaign_id} is already running. Skipping execution trigger.")
        return
    active_campaign_runs.add(campaign_id)
    asyncio.create_task(execute_campaign_worker_task(campaign_id))

async def check_and_process_pending_campaigns():
    """Periodic scanner (runs every 30s) to discover due campaigns or resume crashed sending states."""
    logger.info("Scanning for due or interrupted campaigns...")
    now = datetime.utcnow()
    
    async with AsyncSessionLocal() as session:
        # 1. Fetch campaigns that are scheduled and due
        due_stmt = select(Campaign).where(
            (Campaign.status == "scheduled") & (Campaign.scheduled_send_time <= now)
        )
        due_res = await session.execute(due_stmt)
        due_campaigns = due_res.scalars().all()
        
        # 2. Fetch campaigns stuck in 'sending' status (crash recovery check)
        sending_stmt = select(Campaign).where(Campaign.status == "sending")
        sending_res = await session.execute(sending_stmt)
        sending_campaigns = sending_res.scalars().all()
        
    campaigns_to_process = list(due_campaigns)
    for c in sending_campaigns:
        if c.id not in active_campaign_runs:
            logger.info(f"Campaign {c.id} found in 'sending' state but is inactive. Triggering recovery.")
            campaigns_to_process.append(c)

    for campaign in campaigns_to_process:
        if campaign.id in active_campaign_runs:
            continue
            
        logger.info(f"Launching campaign ID {campaign.id} (Status: {campaign.status})")
        
        # Ensure status is set to sending
        async with AsyncSessionLocal() as session:
            db_camp = await session.get(Campaign, campaign.id)
            if db_camp:
                db_camp.status = "sending"
                await session.commit()
                
        active_campaign_runs.add(campaign.id)
        asyncio.create_task(execute_campaign_worker_task(campaign.id))


async def execute_campaign_worker_task(campaign_id: int):
    """The core engine logic. Rotates senders, retries failures, handles compliance, and reports progress."""
    from bot import bot  # Deferred import to prevent circular structure
    
    logger.info(f"Worker processing campaign queue for ID: {campaign_id}")
    
    try:
        async with AsyncSessionLocal() as session:
            campaign = await session.get(Campaign, campaign_id)
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found in database.")
                active_campaign_runs.discard(campaign_id)
                return
                
            # Fetch all mapped senders
            sender_stmt = select(CampaignSender).where(CampaignSender.campaign_id == campaign_id)
            sender_res = await session.execute(sender_stmt)
            campaign_senders = sender_res.scalars().all()
            
            if not campaign_senders:
                await mark_campaign_failed(session, campaign, "No senders mapped to this campaign.", bot)
                active_campaign_runs.discard(campaign_id)
                return
                
            # Load and instantiate sender accounts
            active_senders: List[Tuple[GmailAccount, Any]] = []
            for cs in campaign_senders:
                acc = await session.get(GmailAccount, cs.gmail_account_id)
                if acc:
                    try:
                        client = await get_gmail_client(acc.id)
                        active_senders.append((acc, client))
                    except Exception as err:
                        logger.warning(f"Could not connect Gmail Sender ID {acc.id} ({acc.email}): {str(err)}")
            
            if not active_senders:
                await mark_campaign_failed(session, campaign, "Could not initialize credentials for any mapped senders.", bot)
                active_campaign_runs.discard(campaign_id)
                return
                
            # Fetch pending queue targets
            targets_stmt = select(CampaignTarget).where(
                CampaignTarget.campaign_id == campaign_id,
                CampaignTarget.status == 'pending'
            )
            targets_res = await session.execute(targets_stmt)
            pending_targets = targets_res.scalars().all()
            
            user = await session.get(User, campaign.user_id)
            telegram_chat_id = user.telegram_id if user else None

        sent_count = 0
        failed_count = 0
        
        # Loop through queue
        for index, target in enumerate(pending_targets):
            # Verify senders list is not completely empty
            if not active_senders:
                async with AsyncSessionLocal() as session:
                    await mark_campaign_failed(session, await session.get(Campaign, campaign_id), "All sender accounts revoked during sending loop.", bot)
                break
                
            # Round-robin selection of sender credentials for workload rotation
            sender_account, sender_client = active_senders[index % len(active_senders)]
            
            async with AsyncSessionLocal() as session:
                db_target = await session.get(CampaignTarget, target.id)
                db_email = await session.get(TargetEmail, db_target.target_email_id)
                db_camp = await session.get(Campaign, campaign_id)
                
                # Check opt-out status
                if db_email.is_unsubscribed:
                    db_target.status = "failed"
                    db_target.error_message = "Recipient previously opted out."
                    db_camp.failed_count += 1
                    failed_count += 1
                    await session.commit()
                    continue
                    
                # Format templating
                first = db_email.first_name or "Subscriber"
                last = db_email.last_name or ""
                subject_fmt = db_camp.subject.replace("{first_name}", first).replace("{last_name}", last)
                body_fmt = db_camp.body_html.replace("{first_name}", first).replace("{last_name}", last)
                
                # Compliance link
                unsub_url = f"{settings.WEB_URL}/unsubscribe/{db_email.id}/{campaign_id}"
                
                # Transmission attempt loop with retry mechanism
                retries = 3
                success = False
                last_error = ""
                
                for attempt in range(retries):
                    try:
                        await send_campaign_email(
                            gmail_client=sender_client,
                            sender_email=sender_account.email,
                            recipient_email=db_email.email,
                            subject=subject_fmt,
                            body_html=body_fmt,
                            physical_address=db_camp.physical_address,
                            unsubscribe_url=unsub_url
                        )
                        success = True
                        break
                    except Exception as e:
                        last_error = str(e)
                        logger.warning(f"Send attempt {attempt+1} failed to {db_email.email}: {last_error}")
                        
                        # Handle fatal Gmail App Password authentication error dynamically
                        if "535" in last_error or "AuthenticationFailed" in last_error or "invalid_grant" in last_error or "Credentials" in last_error:
                            logger.error(f"Fatal credentials error on {sender_account.email}. Evicting sender.")
                            # Remove revoked client from selection pool
                            active_senders = [s for s in active_senders if s[0].id != sender_account.id]
                            # Re-fetch new rotated client for current email immediately
                            if active_senders:
                                sender_account, sender_client = active_senders[index % len(active_senders)]
                            break
                        
                        await asyncio.sleep(2 ** attempt) # Exponential backoff retry delay

                if success:
                    db_target.status = "sent"
                    db_target.sent_at = datetime.utcnow()
                    db_camp.sent_count += 1
                    sent_count += 1
                else:
                    db_target.status = "failed"
                    db_target.error_message = last_error
                    db_camp.failed_count += 1
                    failed_count += 1
                    
                await session.commit()
                
            # Throttling to conform to standard limits
            await asyncio.sleep(1.5)

        # Complete campaign execution
        async with AsyncSessionLocal() as session:
            db_camp = await session.get(Campaign, campaign_id)
            if db_camp and db_camp.status == "sending":
                db_camp.status = "completed"
                await session.commit()

        if telegram_chat_id:
            try:
                await bot.send_message(
                    chat_id=telegram_chat_id,
                    text=(
                        f"🔔 **Campaign Complete!**\n\n"
                        f"Subject: `{campaign.subject}`\n"
                        f"Successfully Sent: `{sent_count}`\n"
                        f"Failed Transmissions: `{failed_count}`"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    except Exception as exc:
        logger.exception(f"Unexpected campaign failure for ID {campaign_id}: {str(exc)}")
        async with AsyncSessionLocal() as session:
            db_camp = await session.get(Campaign, campaign_id)
            if db_camp:
                db_camp.status = "failed"
                await session.commit()
    finally:
        active_campaign_runs.discard(campaign_id)

async def mark_campaign_failed(session: Any, campaign: Campaign, reason: str, bot: Any):
    """Updates campaign table details on validation error and alerts Telegram user."""
    if not campaign:
        return

    campaign.status = "failed"
    await session.commit()
    
    user = await session.get(User, campaign.user_id)
    if user:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=(
                    f"⚠️ **Campaign Sending FAILED!**\n\n"
                    f"Subject: `{campaign.subject}`\n"
                    f"Reason: `{reason}`"
                ),
                parse_mode="Markdown"
            )
        except Exception:
            pass
