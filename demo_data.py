"""
Demo data shared by the startup seeder and seed_demo.py.

Tuples: name, mobile, license number, expiry offset (days), notes, issue offset.
Keeping everything here means the deployed app can rebuild the demo dataset
automatically after a restart on Render's ephemeral filesystem.
"""
from datetime import date, datetime, timedelta

DEMO_STUDENTS = [
    ("Aarav Sharma", "+91 98765 10001", "LIC-2025-1001", -45, "B.Tech CSE · Microsoft 365", -410),
    ("Ishita Verma", "+91 98765 10002", "", -7, "B.Des · Adobe Creative Cloud", -372),
    ("Rohan Mehta", "+91 98765 10003", "", 0, "BBA · TallyPrime", -365),
    ("Priya Nair", "+91 98765 10004", "", 1, "B.Sc IT · MATLAB", -365),
    ("Karan Patel", "+91 98765 10005", "LIC-2026-1005", 2, "", -365),
    ("Ananya Iyer", "+91 98111 22334", "LIC-2026-1006", 2, "MCA · Zoho One", -365),
    ("Vikram Singh", "+91 98990 11223", "LIC-2026-1007", 3, "B.Tech Civil · Autodesk Fusion 360", -365),
    ("Neha Gupta", "+91 97654 33221", "LIC-2026-1008", 5, "M.Com · QuickBooks", -365),
    ("Arjun Reddy", "+91 98450 77889", "LIC-2026-1009", 7, "B.Sc Statistics · SPSS", -365),
    ("Sneha Joshi", "+91 99250 44556", "LIC-2026-1010", 10, "", -365),
    ("Mohit Kumar", "+91 97170 88990", "LIC-2026-1011", 15, "", None),
    ("Kavya Menon", "+91 90000 12345", "LIC-2026-1012", 30, "M.Tech · Wolfram Mathematica", -365),
    ("Aditya Rao", "+91 98330 66778", "LIC-2026-1013", 60, "B.Tech ECE · OriginPro", -365),
    ("Pooja Desai", "+91 96500 33445", "LIC-2026-1014", 120, "MBA · Microsoft 365", -365),
    ("Aisha Khan", "+91 98765 10015", "LIC-2026-1015", 4, "B.Pharm · SPSS", -365),
    ("Rakesh Yadav", "+91 98765 10016", "", 6, "", -365),
    ("Simran Kaur", "+91 98765 10017", "LIC-2026-1017", 8, "B.Tech IT · Microsoft 365", -365),
    ("Divya Nair", "+91 98765 10018", "LIC-2026-1018", 12, "M.Sc · OriginPro", -365),
    ("Yash Thakur", "+91 98765 10019", "", 18, "B.Des · Adobe Creative Cloud", -365),
    ("Farhan Ali", "+91 98765 10020", "LIC-2026-1020", 20, "B.Arch · SketchUp Pro", -365),
    ("Harsh Vardhan", "+91 98765 10021", "LIC-2026-1021", 45, "B.Tech ECE · MATLAB", -365),
    ("Tanya Bhatia", "+91 98765 10022", "", -1, "BBA · QuickBooks", -370),
    ("Sameer Khan", "+91 98765 10023", "LIC-2026-1023", -30, "B.Sc · Wolfram Mathematica", -400),
    ("Nisha Patel", "+91 98765 10024", "LIC-2026-1024", 90, "MBA · Zoho One", -365),
]

DEMO_CLIENT_NUMBER = "919999999999"


async def seed_demo_if_empty(session, settings) -> int:
    """Seed students + demo notifications when the database has no customers.

    Runs only in demo mode. Returns the number of students created.
    """
    from sqlalchemy import func, select
    from models import Customer, NotificationLog

    if not settings or not settings.demo_mode:
        return 0

    total = (await session.execute(select(func.count(Customer.id)))).scalar() or 0
    if total:
        return 0

    today = date.today()
    customers = []
    for name, mobile, license_number, expiry_offset, notes, issue_offset in DEMO_STUDENTS:
        customer = Customer(
            name=name,
            mobile=mobile,
            license_number=license_number or "",
            issue_date=(
                today + timedelta(days=issue_offset) if issue_offset is not None else None
            ),
            expiry_date=today + timedelta(days=expiry_offset),
            notes=notes or None,
        )
        session.add(customer)
        customers.append(customer)

    await session.flush()

    # Recreate the same notification state as the demo guide: the students
    # expiring on the reminder date each get a customer + owner notification,
    # and the last owner notification stays failed so Retry can be demonstrated.
    target_date = today + timedelta(days=settings.reminder_days_before)
    expiring = [customer for customer in customers if customer.expiry_date == target_date]
    for index, customer in enumerate(expiring):
        session.add(
            NotificationLog(
                customer_id=customer.id,
                notification_type="customer",
                recipient_number=customer.mobile,
                template_name=settings.customer_template_name,
                message_content=f"[DEMO] Customer reminder for {customer.name}",
                status="sent",
                whatsapp_message_id=f"demo_customer_{customer.id}_{target_date}",
                expiry_date=target_date,
                sent_at=datetime.now(),
            )
        )

        is_last = index == len(expiring) - 1
        session.add(
            NotificationLog(
                customer_id=customer.id,
                notification_type="client",
                recipient_number="" if is_last else DEMO_CLIENT_NUMBER,
                template_name=settings.client_template_name,
                message_content=f"[DEMO] Owner notification for {customer.name}",
                status="failed" if is_last else "sent",
                whatsapp_message_id=None if is_last else f"demo_client_{customer.id}_{target_date}",
                error_message="Client WhatsApp number not configured" if is_last else None,
                expiry_date=target_date,
                sent_at=None if is_last else datetime.now(),
            )
        )

    await session.commit()
    return len(customers)
