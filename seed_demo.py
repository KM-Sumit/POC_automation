#!/usr/bin/env python3
"""
Seed 14 demo students for a complete feature walkthrough.

Usage:
    python seed_demo.py https://poc-automation.onrender.com
    python seed_demo.py https://poc-automation.onrender.com --mixed-notifications
    python seed_demo.py http://127.0.0.1:8000

The data intentionally covers:
  - 2 expired, 1 expiring today, 4 inside the 2-day reminder window
  - 3 students without a license number (optional field)
  - 3 students without additional details (optional field)
  - 1 student without license issue date
  - 14 records => 3 pages, plus every status tab and search
  - 2 students expiring in 2 days => 4 WhatsApp notifications

--mixed-notifications keeps one owner notification failed so the Retry
button can be demonstrated. It is skipped automatically if real WhatsApp
credentials are configured, to avoid sending live messages.

Safe to run multiple times: existing students (name + mobile) are skipped.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

ARGS = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
FLAGS = {arg for arg in sys.argv[1:] if arg.startswith("--")}
BASE_URL = (ARGS[0] if ARGS else "http://127.0.0.1:8000").rstrip("/")
MIXED_NOTIFICATIONS = "--mixed-notifications" in FLAGS

# name, mobile, license number, expiry offset (days), notes, issue offset
STUDENTS = [
    ("Aarav Sharma", "+91 98765 10001", "LIC-2025-1001", -45, "B.Tech CSE · Microsoft 365", -410),
    ("Ishita Verma", "098765 10002", "", -7, "B.Des · Adobe Creative Cloud", -372),
    ("Rohan Mehta", "9876510003", "", 0, "BBA · TallyPrime", -365),
    ("Priya Nair", "+919876510004", "", 1, "B.Sc IT · MATLAB", -365),
    ("Karan Patel", "98765-10005", "LIC-2026-1005", 2, "", -365),
    ("Ananya Iyer", "+91 98111 22334", "LIC-2026-1006", 2, "MCA · Zoho One", -365),
    ("Vikram Singh", "098990 11223", "LIC-2026-1007", 3, "B.Tech Civil · Autodesk Fusion 360", -365),
    ("Neha Gupta", "+91 97654 33221", "LIC-2026-1008", 5, "M.Com · QuickBooks", -365),
    ("Arjun Reddy", "98450 77889", "LIC-2026-1009", 7, "B.Sc Statistics · SPSS", -365),
    ("Sneha Joshi", "+91 99250 44556", "LIC-2026-1010", 10, "", -365),
    ("Mohit Kumar", "97170 88990", "LIC-2026-1011", 15, "", None),
    ("Kavya Menon", "+91 90000 12345", "LIC-2026-1012", 30, "M.Tech · Wolfram Mathematica", -365),
    ("Aditya Rao", "98330 66778", "LIC-2026-1013", 60, "B.Tech ECE · OriginPro", -365),
    ("Pooja Desai", "+91 96500 33445", "LIC-2026-1014", 120, "MBA · Microsoft 365", -365),
]


def request(path: str, method: str = "GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = res.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} failed ({exc.code}): {detail}") from exc


def normalize_mobile(value: str) -> str:
    digits = re.sub(r"\D", "", str(value))
    if digits.startswith("0"):
        digits = "91" + digits[1:]
    elif len(digits) == 10:
        digits = "91" + digits
    return digits


def set_demo_mode(enabled: bool):
    settings = request("/api/settings")
    request(
        "/api/settings",
        "PUT",
        {
            "reminder_days_before": settings["reminder_days_before"],
            "timezone": settings["timezone"],
            "scheduler_enabled": settings["scheduler_enabled"],
            "demo_mode": enabled,
            "customer_template_name": settings["customer_template_name"],
            "client_template_name": settings["client_template_name"],
            "template_language_code": settings["template_language_code"],
        },
    )


def print_notification_state():
    dashboard = request("/api/dashboard")
    logs = request("/api/notifications?page_size=100").get("notifications", [])
    print(
        "Notifications: "
        f"{dashboard['messages_sent']} sent, "
        f"{dashboard['failed_notifications']} failed, "
        f"{dashboard['pending_notifications']} pending"
    )
    for log in logs:
        print(
            f"  - {log['customer_name']} | {log['notification_type']} | "
            f"{log['status']} | {log['recipient_number']}"
        )
    if any(log["status"] == "failed" for log in logs):
        print("Retry button is ready on the Notifications page.")


def main():
    today = date.today()
    existing = {
        (customer["name"], normalize_mobile(customer["mobile"]))
        for customer in request("/api/customers?page_size=1000").get("customers", [])
    }

    created = 0
    for name, mobile, license_number, expiry_offset, notes, issue_offset in STUDENTS:
        key = (name, normalize_mobile(mobile))
        if key in existing:
            print(f"skip (already exists): {name}")
            continue

        request(
            "/api/customers",
            "POST",
            {
                "name": name,
                "mobile": mobile,
                "license_number": license_number or None,
                "issue_date": (
                    (today + timedelta(days=issue_offset)).isoformat()
                    if issue_offset is not None
                    else None
                ),
                "expiry_date": (today + timedelta(days=expiry_offset)).isoformat(),
                "notes": notes or None,
            },
        )
        created += 1
        expiry = today + timedelta(days=expiry_offset)
        print(f"added: {name} (expiry {expiry}, {expiry_offset:+d} days)")

    expired = sum(1 for student in STUDENTS if student[3] < 0)
    today_count = sum(1 for student in STUDENTS if student[3] == 0)
    next_two_days = sum(1 for student in STUDENTS if 0 <= student[3] <= 2)
    active_31 = sum(1 for student in STUDENTS if student[3] >= 31)
    missing_license = sum(1 for student in STUDENTS if not student[2])
    missing_notes = sum(1 for student in STUDENTS if not student[4])

    print(f"\nDone: {created} demo students created on {BASE_URL}")
    print(
        "Coverage: "
        f"{len(STUDENTS)} total | {expired} expired | {today_count} expiring today | "
        f"{next_two_days} in next 2 days | {active_31} active (31+ days)"
    )
    print(
        f"Optional fields: {missing_license} without license number | "
        f"{missing_notes} without additional details"
    )

    if MIXED_NOTIFICATIONS:
        settings = request("/api/settings")
        if settings.get("whatsapp_connected"):
            print(
                "\nReal WhatsApp credentials detected. Skipping failure simulation "
                "so no live messages are sent."
            )
            MIXED_NOTIFICATIONS = False

    if MIXED_NOTIFICATIONS:
        print("\nPreparing mixed notifications (sent + failed) for the Retry demo...")
        set_demo_mode(False)
        request("/api/trigger-check", "POST")
        set_demo_mode(True)

        logs = request("/api/notifications?page_size=100").get("notifications", [])
        failed_owner_logs = [
            log
            for log in logs
            if log["status"] == "failed" and log["notification_type"] == "client"
        ]
        if failed_owner_logs:
            retried = failed_owner_logs[0]
            request(f"/api/notifications/{retried['id']}/retry", "POST")
            print(
                f"Retried one owner notification for {retried['customer_name']} "
                "(now sent). One failed notification is kept for the live Retry demo."
            )
        else:
            print("No failed owner notification was produced; all notifications are sent.")
    else:
        request("/api/trigger-check", "POST")
        print("\nExpiry check triggered: notifications generated for 2-day expiries.")

    print_notification_state()


if __name__ == "__main__":
    main()
