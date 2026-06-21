from datetime import datetime
from typing import List, Optional
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255))
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    physical_address: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    gmail_accounts: Mapped[List["GmailAccount"]] = relationship("GmailAccount", back_populates="user", cascade="all, delete-orphan")
    target_lists: Mapped[List["TargetList"]] = relationship("TargetList", back_populates="user", cascade="all, delete-orphan")
    campaigns: Mapped[List["Campaign"]] = relationship("Campaign", back_populates="user", cascade="all, delete-orphan")

class GmailAccount(Base):
    __tablename__ = "gmail_accounts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    user: Mapped["User"] = relationship("User", back_populates="gmail_accounts")
    campaign_senders: Mapped[List["CampaignSender"]] = relationship("CampaignSender", back_populates="gmail_account", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("user_id", "email", name="uq_user_gmail_email"),
    )

class TargetList(Base):
    __tablename__ = "target_lists"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    user: Mapped["User"] = relationship("User", back_populates="target_lists")
    emails: Mapped[List["TargetEmail"]] = relationship("TargetEmail", back_populates="target_list", cascade="all, delete-orphan")
    campaigns: Mapped[List["Campaign"]] = relationship("Campaign", back_populates="target_list")

class TargetEmail(Base):
    __tablename__ = "target_emails"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    list_id: Mapped[int] = mapped_column(Integer, ForeignKey("target_lists.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_unsubscribed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unsubscribed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    target_list: Mapped["TargetList"] = relationship("TargetList", back_populates="emails")
    campaign_targets: Mapped[List["CampaignTarget"]] = relationship("CampaignTarget", back_populates="target_email", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint("list_id", "email", name="uq_list_email"),
    )

class Campaign(Base):
    __tablename__ = "campaigns"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    list_id: Mapped[int] = mapped_column(Integer, ForeignKey("target_lists.id", ondelete="RESTRICT"), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    physical_address: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False) # draft, scheduled, sending, completed, failed, paused
    scheduled_send_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    user: Mapped["User"] = relationship("User", back_populates="campaigns")
    target_list: Mapped["TargetList"] = relationship("TargetList", back_populates="campaigns")
    senders: Mapped[List["CampaignSender"]] = relationship("CampaignSender", back_populates="campaign", cascade="all, delete-orphan")
    targets: Mapped[List["CampaignTarget"]] = relationship("CampaignTarget", back_populates="campaign", cascade="all, delete-orphan")
    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="campaign", cascade="all, delete-orphan")

class CampaignSender(Base):
    __tablename__ = "campaign_senders"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    gmail_account_id: Mapped[int] = mapped_column(Integer, ForeignKey("gmail_accounts.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="senders")
    gmail_account: Mapped["GmailAccount"] = relationship("GmailAccount", back_populates="campaign_senders")
    
    __table_args__ = (
        UniqueConstraint("campaign_id", "gmail_account_id", name="uq_campaign_sender"),
    )

class CampaignTarget(Base):
    __tablename__ = "campaign_targets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    target_email_id: Mapped[int] = mapped_column(Integer, ForeignKey("target_emails.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False) # pending, sent, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="targets")
    target_email: Mapped["TargetEmail"] = relationship("TargetEmail", back_populates="campaign_targets")
    
    __table_args__ = (
        UniqueConstraint("campaign_id", "target_email_id", name="uq_campaign_target_email"),
    )

class Job(Base):
    __tablename__ = "jobs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    apscheduler_job_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="jobs")
