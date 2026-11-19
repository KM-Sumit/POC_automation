# 📋 License Expiry WhatsApp Reminder System

A production-ready system to manage customer licenses and automatically send WhatsApp reminders before they expire.

---

## 🚀 Quick Start

### 1. Navigate to project directory
```bash
cd license-reminder
```

### 2. Create a virtual environment (recommended)
```bash
python3 -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
```bash
cp .env.example .env
nano .env   # Edit with your credentials
```

### 5. Run the application
```bash
uvicorn main:app --reload
```

### 6. Open in browser
```
http://127.0.0.1:8000
```

---

## ⚙️ Environment Variables

| Variable | Description | Required |
|---|---|---|
| `WHATSAPP_ACCESS_TOKEN` | Meta WhatsApp Cloud API access token | Yes (for real sending) |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp Business phone number ID | Yes (for real sending) |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | Meta Business Account ID | Yes (for real sending) |
| `WHATSAPP_API_VERSION` | API version (default: `v21.0`) | No |
| `CLIENT_WHATSAPP_NUMBER` | Your business WhatsApp number (e.g. `919876543210`) | Yes |
| `DEMO_MODE` | Set `true` to log instead of send (default: `true`) | No |
| `TIMEZONE` | Scheduler timezone (default: `Asia/Kolkata`) | No |
| `APP_SECRET_KEY` | Secret key for session security | Yes |
| `ADMIN_USERNAME` | Admin login username (default: `admin`) | No |
| `ADMIN_PASSWORD` | Admin login password (default: `admin123`) | No |

---

## 📱 WhatsApp Setup

### Step 1: Create Meta App
1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Create a new App → Select "Business" type
3. Add "WhatsApp" product to your app

### Step 2: Get Credentials
1. Go to **WhatsApp → API Setup**
2. Copy your **Phone Number ID** and **Access Token**
3. Add your test/business phone number

### Step 3: Create Message Templates
Templates must be approved in Meta Business Manager before use.

**Customer Template** (`license_expiry_reminder`):
```
Namaste {{1}},

Aapka license number {{2}}, {{3}} ko expire hone wala hai.

Kripya samay par apna license renew karwa lein.

Dhanyavaad.
```

**Client Notification Template** (`license_expiry_client_notification`):
```
License Expiry Reminder!

Customer: {{1}}
Mobile: {{2}}
License Number: {{3}}
Expiry Date: {{4}}

Customer ko WhatsApp reminder bhejne ki process initiate kar di gayi hai.
```

---

## 📊 Excel / CSV Import

The import wizard accepts any Excel or CSV file format.

**How it works:**
1. Upload your `.xlsx`, `.xls`, or `.csv` file
2. Map your file's columns to required fields (auto-detection attempts to match common names)
3. Preview parsed data with validation errors highlighted
4. Import — duplicates are automatically skipped (optional)

**Column names do NOT need to match anything specific** — the mapping step handles any format.

---

## ⏰ Automatic Scheduler

The scheduler runs at **9:00 AM every day** (configurable timezone) and:
- Finds all licenses expiring in `reminder_days_before` days (default: 2 days)
- Sends one WhatsApp message to the **customer**
- Sends one WhatsApp notification to the **business client**
- Never sends duplicate reminders for the same customer + expiry date
- Stores all notification logs (Sent / Failed / Pending)

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/dashboard` | Dashboard statistics |
| GET | `/api/customers` | List customers (with pagination, search, filter) |
| POST | `/api/customers` | Add a new customer |
| PUT | `/api/customers/{id}` | Update a customer |
| DELETE | `/api/customers/{id}` | Soft-delete a customer |
| POST | `/api/upload` | Upload Excel/CSV file |
| POST | `/api/upload/preview` | Preview import with column mapping |
| POST | `/api/upload/import` | Execute import |
| GET | `/api/notifications` | List notification history |
| POST | `/api/notifications/{id}/retry` | Retry a failed notification |
| GET | `/api/settings` | Get application settings |
| PUT | `/api/settings` | Update application settings |
| POST | `/api/test-whatsapp` | Send a test WhatsApp message |
| POST | `/api/trigger-check` | Manually trigger the expiry check |

---

## 🗄️ Database

SQLite database is stored at `./license_reminder.db` (auto-created on first run).

**Tables:**
- `customers` — Customer records with flexible `extra_data` JSON for original Excel columns
- `import_jobs` — Upload history with column mapping
- `notification_logs` — All WhatsApp message logs
- `app_settings` — Application configuration

---

## 📁 Project Structure

```
license-reminder/
├── main.py          # FastAPI app + all API endpoints
├── database.py      # SQLAlchemy async engine + session
├── models.py        # ORM models
├── whatsapp.py      # WhatsApp Cloud API client + demo mode
├── scheduler.py     # APScheduler daily expiry checker
├── index.html       # Complete frontend dashboard (SPA)
├── requirements.txt # Python dependencies
├── .env.example     # Environment variable template
├── uploads/         # Uploaded Excel/CSV files (auto-created)
└── README.md        # This file
```

---

## 🔒 Security Notes

- Never commit your `.env` file to version control
- Change `APP_SECRET_KEY` to a secure random string in production
- Change default admin credentials before deploying
- The `uploads/` directory should not be publicly accessible in production

---

## 🧪 Testing

### Test without WhatsApp credentials:
Leave `DEMO_MODE=true` in `.env`. All messages will be logged to the console instead of being sent.

### Manual expiry check:
Click **"▶ Run Check"** button in the dashboard header or call:
```bash
curl -X POST http://127.0.0.1:8000/api/trigger-check
```

### Test WhatsApp connection:
Go to **Settings** → Click **"📱 Test WhatsApp"**

---

## 📋 Requirements

- Python 3.11+
- pip
- Internet connection (for WhatsApp API)

---

## 🚀 Deploy on Render

This repository includes `render.yaml` and a `/health` endpoint.

### Option A — Blueprint (recommended)

1. Push the repo to GitHub.
2. Render Dashboard → **New** → **Blueprint** → select this repo.
3. Apply the blueprint. Render reads `render.yaml` automatically.
4. Fill the secret env vars when prompted:
   - `CLIENT_WHATSAPP_NUMBER` (owner number)
   - `WHATSAPP_ACCESS_TOKEN`
   - `WHATSAPP_PHONE_NUMBER_ID`
   - `DATABASE_URL` (optional, see below)
5. Deploy.

### Option B — Manual Web Service

- **Runtime:** Python 3
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path:** `/health`
- **Environment variables:** `DEMO_MODE=true`, `TIMEZONE=Asia/Kolkata`, `BUSINESS_NAME=Aarav Technologies`

### Database (important)

`render.yaml` defaults to SQLite. On Render's **free** plan the filesystem is
ephemeral, so data resets on every deploy/restart.

For persistent data choose one of these:

1. **Render Postgres** (recommended) — copy the **Internal Database URL** into
   the `DATABASE_URL` env var. The app converts `postgres://` to the async
   driver automatically and creates tables on boot.
2. **Persistent disk** (paid instance) — add a disk mounted at `/var/data`,
   then set `DATABASE_URL=sqlite+aiosqlite:////var/data/license_reminder.db`.
   Also set `UPLOAD_DIR=/var/data/uploads` if you want uploaded files to persist.

### Demo data on the deployed site

After deploy, seed the 12 demo customers from your machine:

```bash
python seed_demo.py https://your-app.onrender.com
```

### Free tier notes

- The service sleeps after inactivity, so the in-process 9:00 AM scheduler only
  runs while the service is awake. For reliable reminders use an always-on
  instance or a Render Cron Job that calls `POST /api/trigger-check`.
- There is no login in this demo build. Anyone with the URL can access the
  dashboard and APIs. Add authentication before using real customer data.

