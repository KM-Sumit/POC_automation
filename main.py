"""
Main FastAPI application - License Expiry WhatsApp Reminder System.
Serves both API endpoints and the frontend HTML.
"""
import json
import logging
import os
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import pytz
from dotenv import load_dotenv
from fastapi import (
    Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, init_db
from models import AppSettings, Customer, ImportJob, NotificationLog
from scheduler import run_expiry_check, start_scheduler, stop_scheduler
from whatsapp import WhatsAppClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="License Expiry Reminder System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

BASE_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class CustomerCreate(BaseModel):
    name: str
    mobile: str
    license_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: str
    notes: Optional[str] = None

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v):
        cleaned = re.sub(r"[\s\-\+]", "", v)
        if not re.match(r"^\d{10,15}$", cleaned):
            raise ValueError("Mobile number must be 10-15 digits")
        return cleaned

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("expiry_date must be YYYY-MM-DD")
        return v


class CustomerUpdate(CustomerCreate):
    pass


class ImportMappingRequest(BaseModel):
    job_id: int
    name_col: str
    mobile_col: str
    license_col: str
    expiry_col: str
    issue_col: Optional[str] = None
    skip_duplicates: bool = True


class SettingsUpdate(BaseModel):
    reminder_days_before: int = 2
    timezone: str = "Asia/Kolkata"
    scheduler_enabled: bool = True
    demo_mode: bool = True
    customer_template_name: str = "license_expiry_reminder"
    client_template_name: str = "license_expiry_client_notification"
    template_language_code: str = "hi"


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    await init_db()
    # Read timezone from DB settings
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AppSettings))
        settings = result.scalars().first()
        tz = settings.timezone if settings else "Asia/Kolkata"
    start_scheduler(timezone=tz)
    logger.info("Application started.")


@app.on_event("shutdown")
async def shutdown():
    stop_scheduler()
    logger.info("Application stopped.")


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Render/uptime health check."""
    return {"status": "ok"}


@app.get("/", response_class=FileResponse)
async def serve_frontend():
    index_path = BASE_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_path)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.get("/api/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    today = date.today()

    settings_r = await db.execute(select(AppSettings))
    app_settings = settings_r.scalars().first()
    reminder_days = app_settings.reminder_days_before if app_settings else 2

    total_q = await db.execute(select(func.count(Customer.id)).where(Customer.is_active == True))  # noqa
    total = total_q.scalar() or 0

    active_q = await db.execute(
        select(func.count(Customer.id)).where(
            and_(Customer.is_active == True, Customer.expiry_date >= today)  # noqa
        )
    )
    active = active_q.scalar() or 0

    expired_q = await db.execute(
        select(func.count(Customer.id)).where(
            and_(Customer.is_active == True, Customer.expiry_date < today)  # noqa
        )
    )
    expired = expired_q.scalar() or 0

    from datetime import timedelta
    upcoming_q = await db.execute(
        select(func.count(Customer.id)).where(
            and_(
                Customer.is_active == True,  # noqa
                Customer.expiry_date >= today,
                Customer.expiry_date <= today + timedelta(days=reminder_days),
            )
        )
    )
    upcoming = upcoming_q.scalar() or 0

    sent_q = await db.execute(
        select(func.count(NotificationLog.id)).where(NotificationLog.status == "sent")
    )
    sent = sent_q.scalar() or 0

    failed_q = await db.execute(
        select(func.count(NotificationLog.id)).where(NotificationLog.status == "failed")
    )
    failed = failed_q.scalar() or 0

    pending_q = await db.execute(
        select(func.count(NotificationLog.id)).where(NotificationLog.status == "pending")
    )
    pending = pending_q.scalar() or 0

    total_logs_q = await db.execute(select(func.count(NotificationLog.id)))
    total_logs = total_logs_q.scalar() or 0

    return {
        "total_customers": total,
        "active_licenses": active,
        "upcoming_expiries": upcoming,
        "expired_licenses": expired,
        "messages_sent": sent,
        "failed_notifications": failed,
        "pending_notifications": pending,
        "total_notifications": total_logs,
        "reminder_days_before": reminder_days,
    }


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
@app.get("/api/customers")
async def list_customers(
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    from datetime import timedelta

    query = select(Customer).where(Customer.is_active == True)  # noqa

    if search:
        query = query.where(
            or_(
                Customer.name.ilike(f"%{search}%"),
                Customer.mobile.ilike(f"%{search}%"),
                Customer.license_number.ilike(f"%{search}%"),
            )
        )

    if status_filter == "active":
        query = query.where(
            and_(Customer.expiry_date >= today + timedelta(days=31))
        )
    elif status_filter == "expiring_soon":
        query = query.where(
            and_(
                Customer.expiry_date >= today,
                Customer.expiry_date <= today + timedelta(days=30),
            )
        )
    elif status_filter == "expired":
        query = query.where(Customer.expiry_date < today)

    count_q = select(func.count()).select_from(query.subquery())
    total_q = await db.execute(count_q)
    total = total_q.scalar() or 0

    query = query.order_by(Customer.expiry_date.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    customers = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "customers": [_serialize_customer(c) for c in customers],
    }


def _serialize_customer(c: Customer) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "mobile": c.mobile,
        "license_number": c.license_number,
        "issue_date": c.issue_date.isoformat() if c.issue_date else None,
        "expiry_date": c.expiry_date.isoformat(),
        "notes": c.notes,
        "extra_data": c.extra_data_dict,
        "status": c.status,
        "days_until_expiry": c.days_until_expiry,
        "created_at": c.created_at.isoformat(),
    }


@app.post("/api/customers", status_code=201)
async def create_customer(payload: CustomerCreate, db: AsyncSession = Depends(get_db)):
    expiry = datetime.strptime(payload.expiry_date, "%Y-%m-%d").date()
    issue = (
        datetime.strptime(payload.issue_date, "%Y-%m-%d").date()
        if payload.issue_date
        else None
    )
    customer = Customer(
        name=payload.name.strip(),
        mobile=payload.mobile,
        license_number=(payload.license_number or "").strip(),
        issue_date=issue,
        expiry_date=expiry,
        notes=payload.notes,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return _serialize_customer(customer)


@app.put("/api/customers/{customer_id}")
async def update_customer(
    customer_id: int, payload: CustomerUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer.name = payload.name.strip()
    customer.mobile = payload.mobile
    customer.license_number = (payload.license_number or "").strip()
    customer.expiry_date = datetime.strptime(payload.expiry_date, "%Y-%m-%d").date()
    customer.issue_date = (
        datetime.strptime(payload.issue_date, "%Y-%m-%d").date()
        if payload.issue_date
        else None
    )
    customer.notes = payload.notes
    await db.commit()
    await db.refresh(customer)
    return _serialize_customer(customer)


@app.delete("/api/customers/{customer_id}")
async def delete_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer.is_active = False
    await db.commit()
    return {"message": "Customer deleted successfully"}


# ---------------------------------------------------------------------------
# Excel / CSV Upload
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}
MAX_FILE_SIZE_MB = 20


def _read_file(file_path: Path) -> pd.DataFrame:
    ext = file_path.suffix.lower()
    if ext == ".csv":
        df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(file_path, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Step 1: Upload file, return columns and preview rows."""
    ext = Path(file.filename or "file.xlsx").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_FILE_SIZE_MB}MB)")

    safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    file_path = UPLOAD_DIR / safe_name
    file_path.write_bytes(content)

    try:
        df = _read_file(file_path)
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    if df.empty:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="File is empty")

    # Create import job
    job = ImportJob(
        filename=file.filename,
        file_path=str(file_path),
        total_rows=len(df),
        status="pending",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    columns = list(df.columns)
    preview = df.head(5).to_dict(orient="records")

    return {
        "job_id": job.id,
        "filename": file.filename,
        "total_rows": len(df),
        "columns": columns,
        "preview": preview,
    }


@app.post("/api/upload/preview")
async def preview_import(payload: ImportMappingRequest, db: AsyncSession = Depends(get_db)):
    """Step 2: Preview with column mapping applied - shows parsed data + validation."""
    result = await db.execute(select(ImportJob).where(ImportJob.id == payload.job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Upload job not found")

    file_path = Path(job.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Uploaded file not found on server")

    df = _read_file(file_path)
    rows, errors = _parse_rows(df, payload)

    duplicates = 0
    seen = set()
    for row in rows:
        key = (row["license_number"], row["expiry_date"])
        if key in seen:
            duplicates += 1
        seen.add(key)

    return {
        "total": len(df),
        "valid": len(rows),
        "duplicates": duplicates,
        "errors": errors[:20],  # first 20 errors
        "preview": rows[:10],
    }


@app.post("/api/upload/import")
async def import_data(payload: ImportMappingRequest, db: AsyncSession = Depends(get_db)):
    """Step 3: Actual import - saves customers to DB."""
    result = await db.execute(select(ImportJob).where(ImportJob.id == payload.job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Upload job not found")

    file_path = Path(job.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Uploaded file not found")

    df = _read_file(file_path)
    rows, parse_errors = _parse_rows(df, payload)

    imported = 0
    skipped = 0
    failed = len(parse_errors)

    for row in rows:
        if payload.skip_duplicates:
            dup = await db.execute(
                select(Customer).where(
                    and_(
                        Customer.license_number == row["license_number"],
                        Customer.is_active == True,  # noqa
                    )
                )
            )
            if dup.scalars().first():
                skipped += 1
                continue

        customer = Customer(
            name=row["name"],
            mobile=row["mobile"],
            license_number=row["license_number"],
            issue_date=row.get("issue_date"),
            expiry_date=row["expiry_date"],
            import_job_id=job.id,
        )
        customer.extra_data_dict = row.get("extra_data", {})
        db.add(customer)
        imported += 1

    job.status = "completed"
    job.imported_rows = imported
    job.skipped_rows = skipped
    job.error_rows = failed
    job.column_mapping = json.dumps(
        {
            "name_col": payload.name_col,
            "mobile_col": payload.mobile_col,
            "license_col": payload.license_col,
            "expiry_col": payload.expiry_col,
            "issue_col": payload.issue_col,
        }
    )
    job.error_details = json.dumps(parse_errors[:50])

    await db.commit()

    return {
        "message": "Import completed",
        "imported": imported,
        "skipped": skipped,
        "errors": failed,
        "error_details": parse_errors[:20],
    }


def _parse_date(val: str) -> Optional[date]:
    """Try multiple date formats."""
    if not val or str(val).strip() in ("", "nan", "None"):
        return None
    val = str(val).strip()
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%b-%Y", "%d %b %Y", "%d %B %Y",
        "%Y/%m/%d", "%d.%m.%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _parse_rows(df: pd.DataFrame, payload: ImportMappingRequest) -> tuple[list, list]:
    """Parse and validate rows using the column mapping."""
    rows = []
    errors = []
    mapped_cols = {
        payload.name_col, payload.mobile_col,
        payload.license_col, payload.expiry_col,
    }
    if payload.issue_col:
        mapped_cols.add(payload.issue_col)

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-indexed, header is row 1
        name = str(row.get(payload.name_col, "")).strip()
        mobile = re.sub(r"[\s\-\+\.]", "", str(row.get(payload.mobile_col, "")).strip())
        license_num = str(row.get(payload.license_col, "")).strip()
        expiry_raw = str(row.get(payload.expiry_col, "")).strip()

        row_errors = []
        if not name:
            row_errors.append("Name is empty")
        if not mobile or not re.match(r"^\d{10,15}$", mobile):
            row_errors.append(f"Invalid mobile: '{mobile}'")
        if not license_num:
            row_errors.append("License number is empty")

        expiry_date = _parse_date(expiry_raw)
        if not expiry_date:
            row_errors.append(f"Invalid expiry date: '{expiry_raw}'")

        if row_errors:
            errors.append({"row": row_num, "errors": row_errors, "data": dict(row)})
            continue

        issue_date = None
        if payload.issue_col:
            issue_date = _parse_date(str(row.get(payload.issue_col, "")))

        # Preserve all other columns in extra_data
        extra = {k: v for k, v in row.items() if k not in mapped_cols}

        rows.append({
            "name": name,
            "mobile": mobile,
            "license_number": license_num,
            "expiry_date": expiry_date,
            "issue_date": issue_date,
            "extra_data": extra,
        })

    return rows, errors


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@app.get("/api/notifications")
async def list_notifications(
    page: int = 1,
    page_size: int = 50,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(NotificationLog, Customer.name, Customer.license_number)
        .join(Customer, NotificationLog.customer_id == Customer.id)
    )
    if status_filter:
        query = query.where(NotificationLog.status == status_filter)

    count_q = select(func.count()).select_from(
        select(NotificationLog).where(
            NotificationLog.status == status_filter if status_filter else True
        ).subquery()
    )
    total_r = await db.execute(count_q)
    total = total_r.scalar() or 0

    query = query.order_by(NotificationLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    notifications = []
    for log, cust_name, lic_num in rows:
        notifications.append({
            "id": log.id,
            "customer_id": log.customer_id,
            "customer_name": cust_name,
            "license_number": lic_num,
            "notification_type": log.notification_type,
            "recipient_number": log.recipient_number,
            "template_name": log.template_name,
            "status": log.status,
            "whatsapp_message_id": log.whatsapp_message_id,
            "error_message": log.error_message,
            "expiry_date": log.expiry_date.isoformat(),
            "sent_at": log.sent_at.isoformat() if log.sent_at else None,
            "retry_count": log.retry_count,
            "created_at": log.created_at.isoformat(),
        })

    return {"total": total, "notifications": notifications}


@app.post("/api/notifications/{notification_id}/retry")
async def retry_notification(notification_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(NotificationLog).where(NotificationLog.id == notification_id)
    )
    log = result.scalars().first()
    if not log:
        raise HTTPException(status_code=404, detail="Notification not found")
    if log.status == "sent":
        raise HTTPException(status_code=400, detail="Notification already sent")

    cust_r = await db.execute(select(Customer).where(Customer.id == log.customer_id))
    customer = cust_r.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    settings_r = await db.execute(select(AppSettings))
    settings = settings_r.scalars().first()

    import os
    retry_client_number = os.getenv("CLIENT_WHATSAPP_NUMBER", "")
    if not retry_client_number and settings and settings.demo_mode:
        retry_client_number = "919999999999"  # Demo placeholder
    wa_client = WhatsAppClient({
        "access_token": os.getenv("WHATSAPP_ACCESS_TOKEN", ""),
        "phone_number_id": os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
        "api_version": os.getenv("WHATSAPP_API_VERSION", "v21.0"),
        "demo_mode": settings.demo_mode if settings else True,
        "customer_template_name": settings.customer_template_name if settings else "license_expiry_reminder",
        "client_template_name": settings.client_template_name if settings else "license_expiry_client_notification",
        "template_language_code": settings.template_language_code if settings else "hi",
        "client_whatsapp_number": retry_client_number,
    })

    if log.notification_type == "customer":
        send_result = await wa_client.send_customer_reminder(customer, settings)
    else:
        send_result = await wa_client.send_client_notification(customer, settings)

    log.retry_count += 1
    if send_result.get("success"):
        log.status = "sent"
        log.whatsapp_message_id = send_result.get("message_id", "")
        log.sent_at = datetime.now()
        log.error_message = None
    else:
        log.status = "failed"
        log.error_message = send_result.get("error", "Unknown error")

    await db.commit()
    return {"success": send_result.get("success"), "message": "Retry complete"}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@app.get("/api/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppSettings))
    settings = result.scalars().first()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")
    return {
        "reminder_days_before": settings.reminder_days_before,
        "timezone": settings.timezone,
        "scheduler_enabled": settings.scheduler_enabled,
        "demo_mode": settings.demo_mode,
        "customer_template_name": settings.customer_template_name,
        "client_template_name": settings.client_template_name,
        "template_language_code": settings.template_language_code,
        "business_name": os.getenv("BUSINESS_NAME", "Aarav Technologies"),
        "owner_whatsapp_number": os.getenv("CLIENT_WHATSAPP_NUMBER", ""),
        "sending_number": os.getenv("WHATSAPP_DISPLAY_NUMBER", ""),
        "whatsapp_connected": bool(
            os.getenv("WHATSAPP_ACCESS_TOKEN") and os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        ),
    }


@app.put("/api/settings")
async def update_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppSettings))
    settings = result.scalars().first()
    if not settings:
        raise HTTPException(status_code=404, detail="Settings not found")

    settings.reminder_days_before = payload.reminder_days_before
    settings.timezone = payload.timezone
    settings.scheduler_enabled = payload.scheduler_enabled
    settings.demo_mode = payload.demo_mode
    settings.customer_template_name = payload.customer_template_name
    settings.client_template_name = payload.client_template_name
    settings.template_language_code = payload.template_language_code
    await db.commit()

    # Restart scheduler with new timezone
    stop_scheduler()
    if payload.scheduler_enabled:
        start_scheduler(timezone=payload.timezone)

    return {"message": "Settings updated successfully"}


# ---------------------------------------------------------------------------
# Test WhatsApp
# ---------------------------------------------------------------------------
@app.post("/api/test-whatsapp")
async def test_whatsapp(db: AsyncSession = Depends(get_db)):
    """Send a test message to the client's configured WhatsApp number."""
    settings_r = await db.execute(select(AppSettings))
    settings = settings_r.scalars().first()

    import os
    client_number = os.getenv("CLIENT_WHATSAPP_NUMBER", "")
    is_demo = settings.demo_mode if settings else True
    if not client_number:
        if is_demo:
            client_number = "919999999999"  # Demo placeholder
        else:
            return {"success": False, "error": "CLIENT_WHATSAPP_NUMBER not set in environment"}

    wa_client = WhatsAppClient({
        "access_token": os.getenv("WHATSAPP_ACCESS_TOKEN", ""),
        "phone_number_id": os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
        "api_version": os.getenv("WHATSAPP_API_VERSION", "v21.0"),
        "demo_mode": settings.demo_mode if settings else True,
        "customer_template_name": settings.customer_template_name if settings else "license_expiry_reminder",
        "client_template_name": settings.client_template_name if settings else "license_expiry_client_notification",
        "template_language_code": settings.template_language_code if settings else "hi",
        "client_whatsapp_number": client_number,
    })

    # Create a dummy customer for the test
    dummy = Customer(
        id=0,
        name="Test Customer",
        mobile=client_number,
        license_number="TEST-001",
        expiry_date=date.today(),
        is_active=True,
    )
    result = await wa_client.send_client_notification(dummy, settings)
    return result


# ---------------------------------------------------------------------------
# Trigger manual check (useful for testing)
# ---------------------------------------------------------------------------
@app.post("/api/trigger-check")
async def trigger_expiry_check():
    """Manually trigger the expiry check job (for testing)."""
    await run_expiry_check()
    return {"message": "Expiry check triggered successfully"}
