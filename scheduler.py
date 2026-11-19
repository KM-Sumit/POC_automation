"""
APScheduler-based daily expiry checker and notification sender.
"""
import logging
from datetime import date, datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import Customer, NotificationLog, AppSettings
from whatsapp import WhatsAppClient

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _get_settings(session: AsyncSession) -> AppSettings | None:
    result = await session.execute(select(AppSettings))
    return result.scalars().first()


async def _build_wa_client(settings: AppSettings) -> WhatsAppClient:
    import os
    from dotenv import load_dotenv
    load_dotenv()

    client_number = os.getenv("CLIENT_WHATSAPP_NUMBER", "")
    if not client_number and settings.demo_mode:
        client_number = "919999999999"  # Demo placeholder

    cfg = {
        "access_token": os.getenv("WHATSAPP_ACCESS_TOKEN", ""),
        "phone_number_id": os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
        "api_version": os.getenv("WHATSAPP_API_VERSION", "v21.0"),
        "demo_mode": settings.demo_mode,
        "customer_template_name": settings.customer_template_name,
        "client_template_name": settings.client_template_name,
        "template_language_code": settings.template_language_code,
        "client_whatsapp_number": client_number,
    }
    return WhatsAppClient(cfg)


async def run_expiry_check():
    """
    Core job: find licenses expiring in `reminder_days_before` days
    and send WhatsApp reminders if not already sent.
    """
    logger.info("Running scheduled expiry check...")

    async with AsyncSessionLocal() as session:
        settings = await _get_settings(session)
        if not settings or not settings.scheduler_enabled:
            logger.info("Scheduler disabled in settings, skipping.")
            return

        reminder_days = settings.reminder_days_before
        target_date = date.today() + timedelta(days=reminder_days)

        # Fetch active customers expiring on the target date
        result = await session.execute(
            select(Customer).where(
                and_(
                    Customer.expiry_date == target_date,
                    Customer.is_active == True,  # noqa: E712
                )
            )
        )
        customers = result.scalars().all()

        if not customers:
            logger.info(f"No licenses expiring on {target_date}.")
            return

        logger.info(f"Found {len(customers)} license(s) expiring on {target_date}.")
        wa_client = await _build_wa_client(settings)

        for customer in customers:
            await _process_customer(session, customer, wa_client, settings, target_date)

        await session.commit()


async def _process_customer(
    session: AsyncSession,
    customer: Customer,
    wa_client: WhatsAppClient,
    settings: AppSettings,
    target_date: date,
):
    """Send customer + client notifications if not already sent today."""
    for notif_type in ("customer", "client"):
        # Check for existing sent notification for this customer + expiry_date + type
        existing = await session.execute(
            select(NotificationLog).where(
                and_(
                    NotificationLog.customer_id == customer.id,
                    NotificationLog.expiry_date == target_date,
                    NotificationLog.notification_type == notif_type,
                    NotificationLog.status == "sent",
                )
            )
        )
        if existing.scalars().first():
            logger.info(
                f"Notification already sent for customer {customer.id} ({notif_type}), skipping."
            )
            continue

        # Determine recipient
        recipient = customer.mobile if notif_type == "customer" else wa_client.client_number

        log = NotificationLog(
            customer_id=customer.id,
            notification_type=notif_type,
            recipient_number=recipient,
            template_name=(
                settings.customer_template_name
                if notif_type == "customer"
                else settings.client_template_name
            ),
            expiry_date=target_date,
            status="pending",
        )
        session.add(log)
        await session.flush()  # get log.id

        try:
            if notif_type == "customer":
                result = await wa_client.send_customer_reminder(customer, settings)
            else:
                result = await wa_client.send_client_notification(customer, settings)

            if result.get("success"):
                log.status = "sent"
                log.whatsapp_message_id = result.get("message_id", "")
                log.message_content = result.get("preview", "")
                log.sent_at = datetime.now()
                logger.info(f"Notification sent: customer={customer.id}, type={notif_type}")
            else:
                log.status = "failed"
                log.error_message = result.get("error", "Unknown error")
                logger.warning(
                    f"Notification failed: customer={customer.id}, type={notif_type}, error={log.error_message}"
                )
        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            logger.error(f"Exception sending notification: {e}")


def start_scheduler(timezone: str = "Asia/Kolkata"):
    """Start the APScheduler with daily job at 9 AM in the configured timezone."""
    if scheduler.running:
        return

    tz = pytz.timezone(timezone)
    scheduler.add_job(
        run_expiry_check,
        trigger=CronTrigger(hour=9, minute=0, timezone=tz),
        id="expiry_check",
        replace_existing=True,
        misfire_grace_time=3600,  # allow up to 1 hour late start
    )
    scheduler.start()
    logger.info(f"Scheduler started. Daily check at 09:00 {timezone}.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
