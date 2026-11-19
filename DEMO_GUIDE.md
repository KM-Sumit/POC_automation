# 14 Students Demo Guide

Live app: https://poc-automation.onrender.com

Ye data purposely banaya gaya hai taaki har feature demo ho sake. Har student kisi
na kisi feature ko cover karta hai.

## Starting state

| Metric | Value |
|---|---|
| Total students | 14 |
| Active licenses (expiry today ya future) | 12 |
| Expiring in next 2 days | 4 |
| Expired | 2 |
| Customers pages (5 per page) | 3 |
| Notifications | 4 (3 sent + 1 failed for Retry demo) |

## Student list

| # | Student | Expiry | Days | License | Additional details | Demo use |
|---|---|---|---|---|---|---|
| 1 | Aarav Sharma | 05 Oct 2026 | -45 | LIC-2025-1001 | B.Tech CSE · Microsoft 365 | Expired tab |
| 2 | Ishita Verma | 12 Nov 2026 | -7 | — | B.Des · Adobe Creative Cloud | Expired + blank license |
| 3 | Rohan Mehta | Today | 0 | — | BBA · TallyPrime | Expires today + blank license |
| 4 | Priya Nair | Tomorrow | +1 | — | B.Sc IT · MATLAB | Upcoming tomorrow + blank license |
| 5 | Karan Patel | Day after tomorrow | +2 | LIC-2026-1005 | — | Notification + blank details |
| 6 | Ananya Iyer | Day after tomorrow | +2 | LIC-2026-1006 | MCA · Zoho One | Notification + failed Retry |
| 7 | Vikram Singh | +3 days | +3 | LIC-2026-1007 | B.Tech Civil · Autodesk Fusion 360 | 7-day range |
| 8 | Neha Gupta | +5 days | +5 | LIC-2026-1008 | M.Com · QuickBooks | 7-day range |
| 9 | Arjun Reddy | +7 days | +7 | LIC-2026-1009 | B.Sc Statistics · SPSS | 7-day range |
| 10 | Sneha Joshi | +10 days | +10 | LIC-2026-1010 | — | 30-day list + blank details |
| 11 | Mohit Kumar | +15 days | +15 | LIC-2026-1011 | — | Blank issue date + blank details |
| 12 | Kavya Menon | +30 days | +30 | LIC-2026-1012 | M.Tech · Wolfram Mathematica | Expiring soon tab |
| 13 | Aditya Rao | +60 days | +60 | LIC-2026-1013 | B.Tech ECE · OriginPro | Active tab |
| 14 | Pooja Desai | +120 days | +120 | LIC-2026-1014 | MBA · Microsoft 365 | Active tab |

## Feature-by-feature demo

### 1. Dashboard
- Total customers: **14**
- Active licenses: **12**
- Upcoming expiries: **4** (Rohan today, Priya tomorrow, Karan + Ananya in 2 days)
- Expired licenses: **2**
- Notification cards: **3 sent, 1 failed**
- Recent notifications aur expiring-soon list dikhao.

### 2. Customers
- **Pagination:** 14 records, 5 per page => 3 pages. Page 2/3 pe jao.
- **Tabs:**
  - All customers: 14
  - Active: 2 (Aditya, Pooja)
  - Expiring soon: 10
  - Expired: 2 (Aarav, Ishita)
- **Search:**
  - `Ishita` => blank license wala student
  - `98111` => Ananya (mobile search)
  - `LIC-2026-1010` => Sneha
  - `Mohit` => blank issue date + blank details
- **License filter (page 1):**
  - `Without license number` => Ishita, Rohan, Priya
  - `With license number` => baaki page-1 records
- **Sort:** Latest, Expiry, Name.
- **Add customer (optional fields):** form me sirf Name, Mobile, Expiry bharo;
  License number aur Additional details blank chhod do => record save hota hai.
- **Edit:** Mohit Kumar kholo => License issue date aur Additional details blank
  hain, phir bhi record valid hai.
- **Delete:** demo ke liye ek temporary student add karo, phir Delete karke
  confirm dialog dikhao.

### 3. Upcoming Expiries
- Default **2-day** range:
  - Expiring tomorrow: **1** (Priya)
  - Expiring in 2 days: **2** (Karan, Ananya)
  - Total list: **4** (Rohan, Priya, Karan, Ananya)
- Top-right date range button click karo => **7-day** range, total **7**
  (Vikram, Neha, Arjun add ho jate hain).
- **Reminder filter:** All / Sent / Failed / Scheduled.
- **Export list** button => CSV download.
- Search: `Ananya` ya `LIC-2026-1005`.

### 4. Notifications
- **4 notifications** hain: Karan aur Ananya ke liye customer + owner messages.
- **3 sent + 1 failed** (Ananya ke owner notification ko jaan-boojh kar failed
  rakha hai).
- Demo flow:
  1. `Failed` tab kholo.
  2. Ananya ki failed owner notification select karo.
  3. **Retry** click karo => status sent ho jata hai.
- Period filter: Last 7 days / Last 30 days / All time.
- Search: student name, mobile ya license.
- Recipient filter: All / Customer / Business owner.
- `View` se notification detail modal dikhao.

### 5. Import Excel
- **Ready-made test file:** [`demo_students_import.xlsx`](https://poc-automation.onrender.com/demo_students_import.xlsx)
  (repo me bhi hai). Download karke upload karo.
- File me **6 rows** hain:
  - 5 valid rows (Riya, Dev, Nikhil, Meera, Karan)
  - 1 invalid mobile (`9876`, Sara Khan)
  - 1 duplicate license (`LIC-2026-1005`, Karan Patel already exists)
- Columns map karo:
  - Full Name => Customer name
  - WhatsApp No. => Mobile number
  - License ID => License number
  - Valid Till => Expiry date
- Preview me **5 valid + 1 error** dikhega.
- `Skip duplicate records` ON rakhna. Import result:
  - **Imported: 4**
  - **Skipped: 1** (duplicate Karan Patel)
  - **Errors: 1** (invalid mobile)
  - Total customers: **18**
- Import ke baad 4 naye students ko delete kar sakte ho.
- Page ka built-in **Sample file** button bhi CSV validation demo ke liye use kar sakte ho.

### 6. Settings
- **Demo mode ON** hai => koi real WhatsApp message nahi jata.
- **Send test message** => demo success toast.
- **Reminder preference:** 2 days se 3 days karo, save karo, Dashboard pe
  wapas jao => Upcoming Expiries **5** ho jayengi (Vikram +3 bhi add).
- Scheduler ON/OFF, timezone, templates aur message preview dikhao.

## 5-minute demo flow (recommended)

1. **Dashboard** — 14 total, 4 upcoming, 2 expired.
2. **Customers** — 3 pages, Expiring soon tab, search `Ishita`, filter
   `Without license number`, ek naya student bina license/details ke add karo
   aur delete karo.
3. **Upcoming Expiries** — 2-day se 7-day range toggle, export CSV.
4. **Notifications** — failed notification Retry karke sent dikhao.
5. **Import Excel** — sample file upload, validation error + import preview.
6. **Settings** — test message, reminder days 2 => 3, message preview.

## Important notes

- **Auto-seed:** App startup par khud demo data bana deta hai. Agar database
  empty ho aur Demo mode ON ho, to 14 students + 3 sent/1 failed notifications
  automatically wapas aa jate hain. Render restart ya naye deploy ke baad bhi
  data zero nahi rahega.
- Manual seed ki zarurat sirf tab hai jab database me kuch customers pehle se
  hain aur aap clean demo state chahte ho:

  ```bash
  python3 seed_demo.py https://poc-automation.onrender.com --mixed-notifications
  ```

- Failed notification demo ke liye intentional hai. Retry karte hi sent ho
  jayegi. Isse `Retry` feature live dikh sakta hai.
- Real WhatsApp bhejne ke liye Render Environment me `WHATSAPP_ACCESS_TOKEN`,
  `WHATSAPP_PHONE_NUMBER_ID`, `CLIENT_WHATSAPP_NUMBER` set karke Demo mode OFF
  karna hoga. Real numbers ke bina OFF mat karna.
