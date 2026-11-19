"""
SQLAlchemy ORM models for the License Reminder System.
"""
import json
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Integer, String, Date, DateTime, Boolean, Text, ForeignKey, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile: Mapped[str] = mapped_column(String(20), nullable=False)
    license_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Flexible JSON storage for original Excel columns
    extra_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    import_job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("import_jobs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    import_job: Mapped[Optional["ImportJob"]] = relationship("ImportJob", back_populates="customers")
    notifications: Mapped[list["NotificationLog"]] = relationship("NotificationLog", back_populates="customer", cascade="all, delete-orphan")

    @property
    def extra_data_dict(self) -> dict:
        if self.extra_data:
            try:
                return json.loads(self.extra_data)
            except Exception:
                return {}
        return {}

    @extra_data_dict.setter
    def extra_data_dict(self, value: dict):
        self.extra_data = json.dumps(value, default=str) if value else None

    @property
    def status(self) -> str:
        today = date.today()
        if self.expiry_date < today:
            return "expired"
        elif (self.expiry_date - today).days <= 30:
            return "expiring_soon"
        return "active"

    @property
    def days_until_expiry(self) -> int:
        return (self.expiry_date - date.today()).days


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, completed, failed
    column_mapping: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="import_job")

    @property
    def column_mapping_dict(self) -> dict:
        if self.column_mapping:
            try:
                return json.loads(self.column_mapping)
            except Exception:
                return {}
        return {}


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)  # customer, client
    recipient_number: Mapped[str] = mapped_column(String(20), nullable=False)
    template_name: Mapped[str] = mapped_column(String(100), nullable=False)
    message_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, sent, failed
    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    customer: Mapped["Customer"] = relationship("Customer", back_populates="notifications")


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reminder_days_before: Mapped[int] = mapped_column(Integer, default=2)
    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Kolkata")
    scheduler_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    customer_template_name: Mapped[str] = mapped_column(String(100), default="license_expiry_reminder")
    client_template_name: Mapped[str] = mapped_column(String(100), default="license_expiry_client_notification")
    template_language_code: Mapped[str] = mapped_column(String(10), default="hi")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
