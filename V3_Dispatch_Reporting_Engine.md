# 🚚 PlantMind AI — Version 3
## Dispatch & Reporting Engine
### Standalone Project | Final Layer of PlantMind AI

**Version:** 3.0  
**Module:** Dispatch Email + Daily MIS Report + Owner Dashboard + Full Login System  
**Timeline:** 3 Weeks  
**Position in Full Project:** V3 of 3 — Output & Intelligence Layer  
**Depends On:** V1 (orders, customers, email_log, users tables) + V2 (production_schedule, machines, raw_materials, reorder_log tables)

---

## 📌 Table of Contents
1. [What V3 Is](#1-what-v3-is)
2. [Problem This Solves](#2-problem-this-solves)
3. [System Flow](#3-system-flow)
4. [Agents in V3](#4-agents-in-v3)
5. [Dispatch Email Logic](#5-dispatch-email-logic)
6. [MIS Report Logic](#6-mis-report-logic)
7. [Database Schema — V3 Tables](#7-database-schema--v3-tables)
8. [Dashboard — Owner](#8-dashboard--owner)
9. [Full Login System — All 4 Roles](#9-full-login-system--all-4-roles)
10. [Tech Stack](#10-tech-stack)
11. [Folder Structure](#11-folder-structure)
12. [Week-by-Week Plan](#12-week-by-week-plan)
13. [Testing Checklist](#13-testing-checklist)
14. [How V3 Completes PlantMind AI](#14-how-v3-completes-plantmind-ai)
15. [Resume Value](#15-resume-value)

---

## 1. What V3 Is

V3 is the **final output layer of PlantMind AI**. It handles two critical responsibilities that close the loop on factory operations:

**First — Dispatch:** When V2 marks an order as `completed`, V3's Dispatch Agent immediately detects it and sends a professional dispatch confirmation email to the customer. The customer is informed their order is ready without any human action required.

**Second — Reporting:** Every morning at exactly 9:00 AM, V3's MIS Report Agent wakes up, reads the entire state of the factory from the database, uses Mistral 7B to generate a clean and readable summary, and emails it to the factory owner. The owner wakes up knowing exactly what is happening in their business — orders status, stock levels, machine utilization, pending reorders, and any delays — all in one email.

V3 also delivers the **Owner Dashboard** — the most complete view in the system — and finalizes the **login system** for all 4 roles.

When V3 is complete, PlantMind AI is a fully closed loop: orders come in, get produced, get dispatched, and the owner is briefed every morning. Zero manual communication required.

---

## 2. Problem This Solves

### Dispatch Problems (Before V3)
- After production is complete, someone has to physically check with the floor
- Office staff then has to manually email the customer
- This often happens late — customer calls first asking for update
- No record of when dispatch confirmation was sent
- Customer experience is poor — they feel ignored

### Reporting Problems (Before V3)
- Owner has no single place to see full factory status
- Has to ask multiple people: "What orders are pending?", "How is stock?", "Any delays?"
- Each person gives partial information
- Takes 30–45 minutes every morning to get a full picture
- Information is verbal, not documented
- Owner travelling or away = completely blind to operations

### After V3
- Customer gets dispatch email the moment production is marked complete — automatic, professional, instant
- Owner gets a full factory briefing at 9 AM every morning — no questions asked, no chasing people
- Full audit trail of all dispatch emails and reports sent
- Owner dashboard gives real-time view at any time, not just 9 AM

---

## 3. System Flow

```
FLOW A — DISPATCH (Event Triggered)
─────────────────────────────────────────────────

INPUT: Order status changes to "completed"
       (Set by V2 Production Tracker Agent)
                    │
                    ▼
┌───────────────────────────────────────────────────┐
│            DISPATCH WATCHER                       │
│                                                   │
│  Background task running every 30 seconds         │
│  Queries orders table for:                        │
│  status = "completed"                             │
│  AND dispatch_email_sent = FALSE                  │
│                                                   │
│  For each such order → trigger Dispatch Agent     │
└──────────────────────┬────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────┐
│             DISPATCH AGENT                        │
│          (Phi-3 Mini Q4_K_M)                      │
│                                                   │
│  1. Reads order details from database:            │
│     · Order ID, Product name, Quantity            │
│     · Customer name, Customer email               │
│     · Required delivery date                      │
│     · Special instructions if any                 │
│                                                   │
│  2. Sends order data to Phi-3 Mini with           │
│     dispatch email prompt                         │
│                                                   │
│  3. Phi-3 Mini drafts professional dispatch       │
│     confirmation email body                       │
│                                                   │
│  4. Sends email to customer via Gmail SMTP        │
│                                                   │
│  5. Updates order:                                │
│     · status = "dispatched"                       │
│     · dispatch_email_sent = TRUE                  │
│     · dispatch_sent_at = NOW()                    │
│                                                   │
│  6. Logs in dispatch_log table                    │
│  7. Logs in email_log table (direction = "out")   │
└───────────────────────────────────────────────────┘


FLOW B — DAILY MIS REPORT (Time Triggered)
─────────────────────────────────────────────────

TRIGGER: APScheduler fires every day at 9:00 AM
                    │
                    ▼
┌───────────────────────────────────────────────────┐
│           DATA COLLECTOR                          │
│                                                   │
│  Reads from all database tables:                  │
│                                                   │
│  From orders:                                     │
│  · Total active orders (new + scheduled +         │
│    in_production)                                 │
│  · Orders completed today                         │
│  · Orders dispatched today                        │
│  · Overdue orders (deadline passed, not done)     │
│  · Orders awaiting material                       │
│                                                   │
│  From production_schedule:                        │
│  · Orders currently in production                 │
│  · Estimated completion dates                     │
│  · Any delayed orders (ETA > deadline)            │
│                                                   │
│  From machines:                                   │
│  · How many machines running                      │
│  · How many machines available                    │
│  · How many machines in maintenance               │
│                                                   │
│  From raw_materials:                              │
│  · Materials at critical level (below reorder)    │
│  · Materials at low level                         │
│  · Materials in good stock                        │
│                                                   │
│  From reorder_log:                                │
│  · Pending reorders (sent, not delivered)         │
│                                                   │
│  Returns: structured data dictionary              │
└──────────────────────┬────────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────────┐
│           MIS REPORT AGENT                        │
│         (Mistral 7B Q4_K_M)                       │
│                                                   │
│  1. Receives structured factory data              │
│  2. Sends to Mistral with report generation prompt│
│  3. Mistral writes clean, readable summary        │
│     in professional English                       │
│  4. Report includes all key sections              │
│     (detailed in Section 6)                       │
│                                                   │
│  5. Email sent to owner via Gmail SMTP            │
│  6. Logged in mis_report_log table                │
└───────────────────────────────────────────────────┘
```

---

## 4. Agents in V3

### Agent 1 — Dispatch Watcher (Background Task)
**File:** `agents/dispatch_watcher.py`

**Responsibility:**
- Run as a FastAPI background task every 30 seconds
- Query database for orders with `status = completed` AND `dispatch_email_sent = FALSE`
- For each matching order → call Dispatch Agent
- Ensures no completed order is missed even if system was briefly restarted

**Why 30 Seconds:**
Production completion is an important event. Customer should receive confirmation quickly. 30 seconds is fast enough to feel immediate without overloading the system.

**Duplicate Prevention:**
The `dispatch_email_sent` boolean flag in the orders table ensures each order triggers exactly one dispatch email regardless of how many times the watcher runs.

---

### Agent 2 — Dispatch Agent
**File:** `agents/dispatch_agent.py`

**AI Model:** Phi-3 Mini Q4_K_M

**Responsibility:**
- Receive order details from Dispatch Watcher
- Build prompt for Phi-3 Mini
- Get email body from Phi-3 Mini
- Send email to customer via Gmail SMTP
- Update order status to `dispatched`
- Set `dispatch_email_sent = TRUE` and `dispatch_sent_at = NOW()`
- Log in dispatch_log and email_log

**Why Phi-3 Mini (Not Mistral):**
Dispatch emails are short, structured, and professional. They follow a predictable template. Phi-3 Mini handles this at much higher speed with lower resource usage. Mistral 7B is unnecessary here.

**Fallback:**
If Phi-3 Mini fails or returns unusable output → system uses a hardcoded plain text template and still sends the email. Customer always gets notified. Error is logged.

---

### Agent 3 — Data Collector
**File:** `agents/data_collector.py`

**Responsibility:**
- No AI involved — pure database reads
- Called by MIS Report Agent at 9 AM
- Executes 8–10 targeted SQL queries
- Returns one clean Python dictionary with all factory metrics
- This dictionary is then formatted into text and sent to Mistral

**Data Collected:**

```python
{
    "report_date": "2025-06-10",
    "orders": {
        "total_active": 12,
        "new": 3,
        "scheduled": 4,
        "in_production": 5,
        "completed_today": 2,
        "dispatched_today": 2,
        "overdue": 1,
        "awaiting_material": 1
    },
    "production": {
        "active_jobs": [
            {
                "order_id": "ORD-007",
                "customer": "Raj Polymers",
                "product": "HDPE Cap 50mm",
                "machine": "Machine 2",
                "progress_pct": 65,
                "eta": "2025-06-12",
                "deadline": "2025-06-15",
                "status": "on_track"
            }
        ],
        "delayed_jobs": []
    },
    "machines": {
        "running": 3,
        "available": 1,
        "maintenance": 1,
        "total": 5
    },
    "inventory": {
        "critical": ["PP Granules (80 kg / 200 kg reorder level)"],
        "low": ["PVC Compound (320 kg / 150 kg reorder level)"],
        "good": ["HDPE Granules (450 kg)"]
    },
    "reorders": {
        "pending": ["PP Granules — 500 kg — SK Polymers — sent yesterday"]
    }
}
```

---

### Agent 4 — MIS Report Agent
**File:** `agents/mis_report_agent.py`

**AI Model:** Mistral 7B Q4_K_M

**Responsibility:**
- Receive structured data dictionary from Data Collector
- Convert data to readable text summary for the prompt
- Send to Mistral 7B with report generation prompt
- Receive generated report text
- Send as email to owner at 9 AM
- Log in mis_report_log table

**Why Mistral 7B (Not Phi-3):**
The MIS report must be well-written, clear, and professional. The owner reads it every morning. It must feel like a smart assistant wrote it — not a template. Mistral 7B's superior language quality is worth the extra seconds here. The report generates at 9 AM when no other agents are running, so VRAM is fully available.

**APScheduler Setup:**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(
    generate_and_send_mis_report,
    trigger="cron",
    hour=9,
    minute=0
)
scheduler.start()
```

---

## 5. Dispatch Email Logic

### Prompt Sent to Phi-3 Mini

```
You are an assistant for a plastic injection moulding factory.
Write a short, professional dispatch confirmation email to a customer.
Return only the email body. No subject line. No extra text.

Order Details:
- Order ID: [order_id]
- Customer Name: [customer_name]
- Product: [product_name]
- Quantity: [quantity] pieces
- Original Required Delivery Date: [required_delivery_date]
- Special Instructions: [special_instructions or "None"]
- Factory Name: [from .env]
```

### Example Generated Dispatch Email

```
Subject: Your Order [ORD-007] is Ready for Dispatch

Dear Raj Polymers,

We are pleased to inform you that your order ORD-007 for 10,000 pieces 
of HDPE Cap 50mm has been completed and is ready for dispatch.

Please arrange for collection or confirm your preferred delivery 
method at your earliest convenience.

Thank you for your business. We look forward to serving you again.

Best regards,
[Factory Name]
[Factory Email]
```

### Subject Line
Subject line is NOT generated by AI — it is constructed by code:
```python
subject = f"Your Order {order_id} is Ready for Dispatch — {factory_name}"
```
This ensures subject is always clean, consistent, and professional regardless of AI output quality.

### Sent Via
Gmail SMTP using App Password (same as V2 reorder emails). Same `gmail_sender.py` file — no new email infrastructure needed.

---

## 6. MIS Report Logic

### Prompt Sent to Mistral 7B

```
You are a factory management AI assistant for a plastic injection 
moulding factory. Write a daily morning report for the factory owner.

Use the data provided below. Write in clear, professional English.
Use short paragraphs. Keep it concise but complete. 
The owner should be able to read this in under 2 minutes.

Structure the report with these sections:
1. Good Morning Summary (2-3 sentences — overall factory health)
2. Orders Overview (active, completed, dispatched, overdue)
3. Production Status (what is running, on which machine, ETA)
4. Inventory Alert (critical and low materials only — skip if all good)
5. Pending Reorders (what was ordered, from whom, when)
6. Action Required (anything owner needs to decide or follow up on)

Factory Data for Today ([report_date]):
[Formatted data dictionary inserted here as readable text]

Write the report now.
```

### Example Generated MIS Report Email

```
Subject: PlantMind AI — Daily Factory Report | 10 June 2025

Good Morning,

Daily Factory Report — Tuesday, 10 June 2025

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SUMMARY
Factory operations are running smoothly today. 12 active orders 
are in the system. 2 orders were completed and dispatched yesterday. 
One order requires your attention due to a material shortage.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ORDERS OVERVIEW
· Active Orders: 12 (3 new, 4 scheduled, 5 in production)
· Completed Yesterday: 2
· Dispatched Yesterday: 2
· Overdue: 1 — ORD-003 (deadline was 8 June, still in production)
· Awaiting Material: 1 — ORD-011 (waiting for PP Granules delivery)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRODUCTION STATUS
· Machine 1: ORD-005 — PP Container 500ml for ABC Plastics
  Progress: 80% complete — On track for 12 June deadline
· Machine 2: ORD-007 — HDPE Cap 50mm for Raj Polymers
  Progress: 65% complete — On track for 15 June deadline
· Machine 3: ORD-003 — PVC Fitting for XYZ Industries
  Progress: 45% complete — DELAYED — new ETA 14 June, deadline was 8 June
· Machine 4: Available
· Machine 5: Under maintenance

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INVENTORY ALERTS
⚠ CRITICAL — PP Granules: 80 kg remaining (reorder level: 200 kg)
  Reorder of 500 kg sent to SK Polymers yesterday — awaiting delivery

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PENDING REORDERS
· PP Granules — 500 kg — SK Polymers — sent 9 June — awaiting delivery

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ACTION REQUIRED
1. ORD-003 is delayed by 6 days — consider informing XYZ Industries
2. Machine 5 is under maintenance — confirm repair timeline with technician

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PlantMind AI | Automated Factory Intelligence
```

### Report Quality Control
Before sending, the system checks:
- Report length is between 200 and 1000 words (if outside → regenerate once)
- Report contains all 6 section headers (if missing → regenerate once)
- If second generation also fails → send raw data table as plain text fallback
- Owner always gets an email at 9 AM regardless of AI quality

---

## 7. Database Schema — V3 Tables

V3 adds 2 new tables. V1 and V2 tables are modified slightly (2 new columns added to `orders`).

---

### Modification to orders table (from V1)
Two new columns added:

```sql
ALTER TABLE orders
ADD COLUMN dispatch_email_sent    BOOLEAN DEFAULT FALSE,
ADD COLUMN dispatch_sent_at       TIMESTAMP;
```

These columns allow the Dispatch Watcher to efficiently find un-dispatched completed orders and prevent duplicate emails.

---

### Table 13: dispatch_log
Full record of every dispatch email sent to every customer.

```
dispatch_id              SERIAL PRIMARY KEY
order_id                 INTEGER REFERENCES orders(order_id)
customer_id              INTEGER REFERENCES customers(customer_id)
customer_email           VARCHAR(200) NOT NULL
email_subject            TEXT NOT NULL
email_body_summary       TEXT
sent_at                  TIMESTAMP DEFAULT NOW()
status                   VARCHAR(30) DEFAULT 'sent'
                         -- sent / failed
error_details            TEXT
```

---

### Table 14: mis_report_log
Record of every daily MIS report generated and sent.

```
report_id                SERIAL PRIMARY KEY
report_date              DATE NOT NULL
generated_at             TIMESTAMP DEFAULT NOW()
sent_to_email            VARCHAR(200) NOT NULL
report_subject           TEXT
report_body              TEXT
generation_status        VARCHAR(30) DEFAULT 'success'
                         -- success / fallback / failed
error_details            TEXT
```

---

## 8. Dashboard — Owner

The Owner Dashboard is the most complete view in PlantMind AI. It shows the entire factory at a glance. Accessible at `http://[PC-IP]:8000` after login with owner credentials.

### Top Bar
- PlantMind AI logo
- "Good Morning, [Owner Name]" (if before 12 PM) / "Good Afternoon" / "Good Evening"
- Today's date and day
- Logout button

---

### Section 1 — Factory Health Snapshot (Top of Page)
Four large metric cards displayed prominently:

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ ACTIVE ORDERS│  │  IN PRODUCTION│  │  DISPATCHED  │  │   OVERDUE    │
│      12      │  │       5      │  │   TODAY: 2   │  │      1       │
│              │  │              │  │              │  │   ⚠ ACTION   │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

Colors: Active (blue), In Production (orange), Dispatched (green), Overdue (red).

---

### Section 2 — Live Orders Table
Complete table of all orders in the system.

| Order # | Customer | Product | Qty | Deadline | Machine | Progress | Status | ETA |
|---------|----------|---------|-----|----------|---------|----------|--------|-----|
| ORD-007 | Raj Polymers | HDPE Cap | 10,000 | 15 Jun | Machine 2 | 65% | 🟡 In Production | 12 Jun |
| ORD-003 | XYZ Industries | PVC Fitting | 8,000 | 8 Jun | Machine 3 | 45% | 🔴 Delayed | 14 Jun |
| ORD-011 | ABC Plastics | Container | 5,000 | 25 Jun | — | 0% | 🟠 Awaiting Material | — |

- Click any row → full order detail panel slides in from right
- Filter by status using tabs: All / Active / Delayed / Completed / Dispatched
- Search by customer name or order number

---

### Section 3 — Machine Status Board
Visual representation of all machines:

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   MACHINE 1     │  │   MACHINE 2     │  │   MACHINE 3     │
│  🟢 RUNNING     │  │  🟢 RUNNING     │  │  🔴 DELAYED     │
│  ORD-005        │  │  ORD-007        │  │  ORD-003        │
│  80% complete   │  │  65% complete   │  │  45% complete   │
│  ETA: 12 Jun    │  │  ETA: 12 Jun    │  │  ETA: 14 Jun    │
└─────────────────┘  └─────────────────┘  └─────────────────┘

┌─────────────────┐  ┌─────────────────┐
│   MACHINE 4     │  │   MACHINE 5     │
│  ⚪ AVAILABLE   │  │  🔧 MAINTENANCE │
│  Ready for job  │  │  Since: 8 Jun   │
└─────────────────┘  └─────────────────┘
```

---

### Section 4 — Raw Material Stock
| Material | Stock | Reorder Level | Status | Last Reorder |
|---------|-------|---------------|--------|-------------|
| HDPE Granules | 450 kg | 200 kg | 🟢 Good | — |
| PP Granules | 80 kg | 200 kg | 🔴 Critical | Yesterday (pending) |
| PVC Compound | 320 kg | 150 kg | 🟡 Low | — |

---

### Section 5 — Recent Activity Feed
Chronological list of recent system events:

```
Today 08:45 AM — Dispatch email sent to Raj Polymers for ORD-005
Today 07:30 AM — Production complete: ORD-005 on Machine 1
Yesterday 04:15 PM — Delay detected: ORD-003 (new ETA: 14 Jun)
Yesterday 02:00 PM — Reorder sent to SK Polymers: 500 kg PP Granules
Yesterday 11:30 AM — New order created: ORD-011 from ABC Plastics
```

---

### Section 6 — MIS Report History
List of last 7 daily reports with download/view button.

| Date | Sent At | Status | Action |
|------|---------|--------|--------|
| 10 Jun 2025 | 9:00 AM | ✅ Sent | [View Report] |
| 9 Jun 2025 | 9:00 AM | ✅ Sent | [View Report] |

Clicking "View Report" shows the full report text in a modal popup.

---

## 9. Full Login System — All 4 Roles

V3 finalizes the login system across all modules. V1 built basic login for office staff. V3 completes it for all 4 roles with proper role-based dashboard routing.

### Role → Dashboard Mapping

| Role | Dashboard | Key Capabilities |
|------|-----------|-----------------|
| `owner` | Owner Dashboard | Full factory view, MIS history, all orders, all machines, all stock |
| `office_staff` | Office Dashboard | Check emails, view orders, complete flagged orders |
| `supervisor` | Supervisor Dashboard | Start production, update progress, mark complete |
| `store` | Store Dashboard | View stock, update stock, view reorders |

### Login Flow
```
User opens http://[PC-IP]:8000
        ↓
Login page shown (all roles use same login page)
        ↓
User enters username + password
        ↓
System verifies password hash (bcrypt)
        ↓
System reads user.role from database
        ↓
Redirect to correct dashboard based on role:
  owner       → /dashboard/owner
  office_staff → /dashboard/office
  supervisor  → /dashboard/supervisor
  store       → /dashboard/store
```

### Session Management
- Session stored in signed cookie (itsdangerous library)
- Session expires after 8 hours of inactivity
- Each dashboard page checks session role before rendering
- Wrong role accessing wrong URL → redirected to their correct dashboard
- Expired session → redirected to login page

### Default Users (Seeded at Setup)
```sql
INSERT INTO users (username, password_hash, role) VALUES
('owner', '[hashed_password]', 'owner'),
('office', '[hashed_password]', 'office_staff'),
('supervisor', '[hashed_password]', 'supervisor'),
('store', '[hashed_password]', 'store');
```
Passwords are changed by the user after first login via a simple change-password form on each dashboard.

---

## 10. Tech Stack

All tools same as V1 and V2. V3 adds only APScheduler.

| Component | Technology | Purpose |
|-----------|-----------|---------|
| AI Model (dispatch email) | Phi-3 Mini Q4_K_M | Fast dispatch email generation |
| AI Model (MIS report) | Mistral 7B Q4_K_M | High quality daily report generation |
| Task Scheduler | APScheduler | Trigger MIS report at 9 AM daily |
| Background Watcher | FastAPI BackgroundTasks | Dispatch watcher every 30 seconds |
| Email Sending | smtplib (Python stdlib) | Dispatch + MIS report emails via Gmail SMTP |
| All V1 + V2 tech | Same | No changes to existing stack |

### APScheduler Installation
```
pip install apscheduler
```

### Full Python Dependencies (Final requirements.txt for all 3 versions)
```
fastapi
uvicorn
sqlalchemy
psycopg2-binary
pymupdf
python-docx
google-auth
google-auth-oauthlib
google-api-python-client
bcrypt
itsdangerous
python-dotenv
httpx
python-multipart
jinja2
apscheduler
```

---

## 11. Folder Structure

V3 adds to V1 + V2 folder structure. New files only shown:

```
plantmind-v3/
│
├── (all V1 + V2 files remain unchanged)
│
├── scheduler.py                      # NEW — APScheduler setup, 9 AM job registration
│
├── agents/
│   ├── (V1 + V2 agents unchanged)
│   ├── dispatch_watcher.py           # NEW — Background task, polls every 30 seconds
│   ├── dispatch_agent.py             # NEW — Phi-3 Mini drafts + sends dispatch email
│   ├── data_collector.py             # NEW — Reads all DB tables, returns metrics dict
│   └── mis_report_agent.py           # NEW — Mistral 7B generates + sends MIS report
│
├── database/
│   └── queries/
│       ├── (V1 + V2 queries unchanged)
│       ├── dispatch_queries.py        # NEW — dispatch_log CRUD, update order dispatch fields
│       └── report_queries.py         # NEW — mis_report_log CRUD, data collection queries
│
├── routers/
│   ├── (V1 + V2 routers unchanged)
│   └── owner_router.py               # NEW — GET /dashboard/owner, GET /reports/history
│
├── email/
│   └── email_templates/
│       ├── (V2 templates unchanged)
│       ├── dispatch_template.txt      # NEW — fallback template if Phi-3 fails
│       └── mis_report_template.txt    # NEW — fallback template if Mistral fails
│
├── templates/
│   ├── (V1 + V2 templates unchanged)
│   └── owner_dashboard.html          # NEW — Full owner view
│
└── static/
    └── js/
        ├── (V1 + V2 JS unchanged)
        └── owner_dashboard.js         # NEW — Activity feed, machine board, report viewer
```

---

## 12. Week-by-Week Plan

### Week 10 — Dispatch System

**Day 64–65: Database V3 Setup**
- Run ALTER TABLE to add `dispatch_email_sent` and `dispatch_sent_at` to orders table
- Create `dispatch_log` table
- Create `mis_report_log` table
- Write `dispatch_queries.py` — get undispatched completed orders, update dispatch fields, insert dispatch_log
- Test queries: manually set an order to completed → query finds it

**Day 66–67: Dispatch Agent**
- Write `dispatch_agent.py`
- Build prompt for Phi-3 Mini
- Test prompt: send order details → Phi-3 returns clean email body
- Refine prompt until output is consistently professional
- Connect to `gmail_sender.py` (already built in V2)
- Test end-to-end: order marked complete → email sent to customer → dispatch_log updated

**Day 68–70: Dispatch Watcher**
- Write `dispatch_watcher.py` as FastAPI background task
- Register it in `main.py` using `app.on_event("startup")`
- Test watcher: start app → set order to completed → within 30 seconds dispatch email arrives
- Test duplicate prevention: run watcher 5 times → only 1 email sent per order
- Test fallback: force Phi-3 to fail → hardcoded template email still sent

**Week 10 Milestone:** Dispatch system fully working. Completed orders trigger customer emails automatically within 30 seconds. Zero duplicate emails.

---

### Week 11 — MIS Report System

**Day 71–72: Data Collector**
- Write `data_collector.py`
- Write all 8–10 SQL queries covering every metric
- Format collected data into clean Python dictionary
- Test: run collector → print dictionary → verify all numbers are correct
- Edge case: what if no orders exist? (return zeros, not errors)

**Day 73–74: MIS Report Agent**
- Write `mis_report_agent.py`
- Convert data dictionary to readable text block for prompt
- Write prompt for Mistral 7B (detailed, with section structure)
- Test prompt: run Mistral → read output → is it professional and complete?
- Iterate prompt until report quality is consistently excellent
- Add quality check (length + section headers check)
- Add fallback: if AI fails → send plain data table
- Connect to `gmail_sender.py` → send email to owner

**Day 75–76: APScheduler Setup**
- Write `scheduler.py`
- Configure cron job: every day at 9:00 AM
- Register scheduler startup in `main.py`
- Test scheduler: temporarily set to 9 AM today → confirm email arrives
- Test scheduler after system restart → confirms it re-registers automatically

**Day 77: MIS Report Full Test**
- Seed realistic test data (5 orders, 3 machines running, 1 material critical)
- Run MIS report manually (via test endpoint)
- Review report quality: does it cover everything? Is it readable?
- Adjust prompt and data formatting until report feels like a real management tool

**Week 11 Milestone:** MIS report generates correctly. Mistral writes a professional, complete, readable report. APScheduler fires at 9 AM. Owner receives email.

---

### Week 12 — Owner Dashboard + Final Integration

**Day 78–79: Owner Dashboard**
- Write `owner_dashboard.html` with all 6 sections
- Write `owner_router.py` — API endpoints for all owner data
- Write `owner_dashboard.js` — machine status board (dynamic cards), activity feed, report viewer
- Test all sections load with real database data
- Test report viewer modal shows full report text

**Day 80: Full Login System Completion**
- Review auth_router.py from V1 — confirm role-based routing works for all 4 roles
- Test all 4 role logins → each goes to correct dashboard
- Test wrong-role URL access → redirected correctly
- Test session expiry → redirected to login
- Add change-password form to all 4 dashboards

**Day 81–82: Full System Integration Test**
- Run complete PlantMind AI (V1 + V2 + V3 all together)
- Test complete pipeline 5 times with realistic data:
  1. Send PO email to Gmail
  2. Click Check Emails on office dashboard
  3. Order created → inventory checked → reorder sent if needed
  4. Order scheduled on machine → supervisor starts
  5. Supervisor updates progress 3 times
  6. Supervisor marks complete → dispatch email auto-sent to customer
  7. 9 AM arrives → owner gets MIS report
- All 4 dashboards tested simultaneously (different browser tabs)

**Day 83–84: Polish + Final Testing**
- Fix all bugs from integration test
- Test on phone browser via local network IP (all 4 dashboards)
- Test edge cases: Gmail API token expiry, Ollama model not loaded, DB connection drop
- Make sure all error messages are user-friendly (not raw Python errors)
- Clean all code — remove print statements, add proper logging

**Day 85: Documentation + Demo**
- Write final README.md with full setup instructions
- Write `.env.example` file showing all required environment variables
- Record demo video showing full pipeline (for portfolio/LinkedIn)
- Take screenshots of all 4 dashboards for resume
- Write project description for resume (in Section 15)

**Week 12 Milestone:** PlantMind AI is fully complete, tested, documented, and demo-ready.

---

## 13. Testing Checklist

### Dispatch Tests
- [ ] Order status set to "completed" → dispatch email sent within 30 seconds
- [ ] Dispatch email received by customer with correct order details
- [ ] Subject line correct: "Your Order ORD-XXX is Ready for Dispatch"
- [ ] Order status updated to "dispatched" after email sent
- [ ] dispatch_email_sent flag = TRUE after sending
- [ ] Watcher runs 10 times → only 1 email sent (no duplicates)
- [ ] Phi-3 Mini fails → fallback template email still sent
- [ ] dispatch_log record created with correct details
- [ ] Dispatched orders show correctly on all dashboards

### MIS Report Tests
- [ ] APScheduler fires exactly at 9:00 AM
- [ ] Data collector returns correct numbers (verified against DB manually)
- [ ] Mistral generates report with all 6 sections present
- [ ] Report length is between 200 and 1000 words
- [ ] Report identifies overdue orders correctly
- [ ] Report flags critical materials correctly
- [ ] Owner receives email at 9 AM with full report in body
- [ ] mis_report_log record created for each report
- [ ] Mistral fails → fallback plain text report still sent
- [ ] MIS report history visible on owner dashboard

### Owner Dashboard Tests
- [ ] Login as owner → redirected to owner dashboard (not other dashboards)
- [ ] 4 metric cards show correct live numbers
- [ ] Orders table shows all orders with correct status and progress
- [ ] Machine status board shows correct state for all machines
- [ ] Raw material stock shows correct colors
- [ ] Activity feed shows recent events in correct order
- [ ] MIS report history shows last 7 reports
- [ ] View Report modal shows full report text correctly

### Login System Tests
- [ ] Owner login → owner dashboard
- [ ] Office staff login → office dashboard
- [ ] Supervisor login → supervisor dashboard
- [ ] Store person login → store dashboard
- [ ] Supervisor tries to access /dashboard/owner → redirected to supervisor dashboard
- [ ] Wrong password → error message, no access
- [ ] Session expires after 8 hours → redirected to login
- [ ] Change password form works for all 4 roles

### Full Pipeline Tests (End-to-End)
- [ ] Pipeline run 1: email → order → sufficient stock → schedule → progress → complete → dispatch ✅
- [ ] Pipeline run 2: email → order → insufficient stock → reorder → stock updated → schedule → progress → complete → dispatch ✅
- [ ] Pipeline run 3: email → order → schedule → progress delay detected → owner alerted → complete → dispatch ✅
- [ ] All 4 dashboards work simultaneously without conflict
- [ ] System works on phone browser via local network IP
- [ ] System recovers correctly if restarted mid-operation

---

## 14. How V3 Completes PlantMind AI

V3 is the final piece that closes the loop. Here is the complete status flow across all 3 versions:

```
V1 creates order        → status = "new"
V2 checks inventory     → status = "awaiting_material" (if needed)
V2 stock arrives        → status = "new" (reset to continue)
V2 schedules production → status = "scheduled"
V2 supervisor starts    → status = "in_production"
V2 supervisor completes → status = "completed"
V3 dispatches           → status = "dispatched"
```

Every single status transition is logged in `order_status_log` with timestamp and actor (system or username). This gives a full audit trail for every order from creation to dispatch.

### Integration Checklist for Final PlantMind AI
- [ ] Single `main.py` starts everything: FastAPI, APScheduler, background tasks
- [ ] Single PostgreSQL database with all 14 tables
- [ ] All 4 dashboards accessible from same login page
- [ ] All agents share same database connection pool
- [ ] V1 → V2 handoff works (new orders auto-picked up by inventory check)
- [ ] V2 → V3 handoff works (completed orders auto-dispatched within 30 seconds)
- [ ] MIS report covers data from all 3 modules
- [ ] All emails sent from same Gmail account
- [ ] Both AI models (Mistral + Phi-3) available via Ollama, loaded on-demand

---

## 15. Resume Value

### What V3 Demonstrates
- APScheduler for production-grade task automation
- Event-driven background processing (dispatch watcher)
- Advanced prompt engineering for structured report generation
- Complete role-based access control system
- End-to-end system integration across 3 modules
- Professional email generation using LLMs
- Full-stack ownership from database to dashboard to email delivery

### Resume Description for V3

```
PlantMind AI — V3: Dispatch & Reporting Engine
Python · FastAPI · Mistral 7B · Phi-3 Mini · APScheduler · PostgreSQL

• Built automated dispatch system that detects production completion 
  and sends customer confirmation emails within 30 seconds using 
  Phi-3 Mini LLM — zero manual action required
• Engineered daily MIS report system using Mistral 7B that synthesizes 
  complete factory operations data and delivers a professional morning 
  briefing to the factory owner at 9 AM every day via APScheduler
• Designed Owner Dashboard providing real-time visibility into all 
  orders, machine status, inventory levels, and production progress 
  across the factory floor
• Completed full role-based authentication system covering all 4 
  user roles with secure session management and role-enforced routing
• Integrated all 3 modules into a single cohesive system — from 
  email intake through production tracking to dispatch confirmation
```

### Final PlantMind AI — Resume Description (Combined)

```
PlantMind AI — Agentic AI Factory Intelligence Platform
Python · FastAPI · PostgreSQL · Ollama · Mistral 7B · Phi-3 Mini ·
Gmail API · APScheduler · PyMuPDF

• Designed and built a complete multi-agent AI system automating 
  end-to-end operations of a plastic injection moulding factory — 
  from customer order intake to production dispatch
• 8 specialized AI agents handle: email reading, order extraction, 
  inventory monitoring, supplier reordering, production scheduling, 
  progress tracking, dispatch confirmation, and daily reporting
• Deployed entirely on local infrastructure (Dell G15, RTX 3050) 
  with zero cloud dependency, zero recurring cost, using quantized 
  LLMs (Mistral 7B Q4_K_M + Phi-3 Mini Q4_K_M) via Ollama
• 4 role-specific dashboards (Owner, Office Staff, Supervisor, Store) 
  accessible across factory local network from any device
• Real deployment context: built for and demonstrated in a real 
  injection moulding manufacturing business
```

---

*V3 — Dispatch & Reporting Engine | Final Layer of PlantMind AI*
