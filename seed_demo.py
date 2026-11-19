#!/usr/bin/env python3
"""
Seed 12 demo customers with different expiry dates.

Usage:
    python seed_demo.py https://your-app.onrender.com
    python seed_demo.py http://127.0.0.1:8000

Safe to run multiple times: existing license numbers are skipped.
"""
import json
import sys
import urllib.request
from datetime import date, timedelta

BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")


def request(path: str, method: str = "GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        body = res.read().decode()
        return json.loads(body) if body else {}


def main():
    today = date.today()
    demo = [
        ("Rahul Sharma", "+91 98765 43210", "LIC-2026-1042", 0, "Microsoft 365 · Mumbai"),
        ("Priya Mehta", "+91 98210 56789", "LIC-2026-1038", 1, "Adobe Creative Cloud · Pune"),
        ("Karan Shah", "+91 99887 76655", "LIC-2026-1044", 2, "TallyPrime · Ahmedabad"),
        ("Ananya Iyer", "+91 98111 22334", "LIC-2026-1051", 2, "Zoho One · Chennai"),
        ("Vikram Singh", "+91 98990 11223", "LIC-2026-1067", 3, "AutoCAD · Delhi"),
        ("Neha Gupta", "+91 97654 33221", "LIC-2026-1073", 5, "Microsoft 365 · Jaipur"),
        ("Arjun Nair", "+91 98450 77889", "LIC-2026-1080", 7, "QuickBooks · Bengaluru"),
        ("Sneha Patel", "+91 99250 44556", "LIC-2026-1092", 15, "Adobe Photoshop · Surat"),
        ("Rohan Desai", "+91 98330 66778", "LIC-2026-1105", 30, "TallyPrime · Nashik"),
        ("Kavya Reddy", "+91 90000 12345", "LIC-2026-1118", 60, "Zoho Books · Hyderabad"),
        ("Mohit Verma", "+91 97170 88990", "LIC-2025-0981", -10, "Microsoft 365 · Noida"),
        ("Pooja Joshi", "+91 96500 33445", "LIC-2025-0944", -30, "Adobe Acrobat · Indore"),
    ]

    existing = {
        c.get("license_number")
        for c in request("/api/customers?page_size=1000").get("customers", [])
    }

    created = 0
    for name, mobile, license_number, offset, notes in demo:
        if license_number in existing:
            print(f"skip (already exists): {name}")
            continue
        request(
            "/api/customers",
            "POST",
            {
                "name": name,
                "mobile": mobile,
                "license_number": license_number,
                "issue_date": (today - timedelta(days=365)).isoformat(),
                "expiry_date": (today + timedelta(days=offset)).isoformat(),
                "notes": notes,
            },
        )
        created += 1
        print(f"added: {name} (expiry {today + timedelta(days=offset)})")

    print(f"\nDone: {created} demo customers created on {BASE_URL}")

    try:
        request("/api/trigger-check", "POST")
        print("Expiry check triggered — notifications generated for 2-day expiries.")
    except Exception as exc:  # noqa: BLE001
        print(f"Could not trigger expiry check: {exc}")


if __name__ == "__main__":
    main()
