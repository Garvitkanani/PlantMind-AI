# 🏭 PlantMind AI — Full Project Plan
### Agentic AI System for Injection Moulding Manufacturing Factory
**Version:** 1.0  
**Author:** Garvit  
**Degree:** BTech AI & Data Science — Year 2, KJSIT  
**Target:** Real Deployment + Resume/Portfolio Showcase  

---

## 📌 Table of Contents
1. [Project Summary](#1-project-summary)
2. [Problem Statement](#2-problem-statement)
3. [System Overview](#3-system-overview)
4. [Users & Roles](#4-users--roles)
5. [Complete Agent Flow](#5-complete-agent-flow)
6. [Module Breakdown](#6-module-breakdown)
7. [Database Schema](#7-database-schema)
8. [Tech Stack](#8-tech-stack)
9. [AI Model Strategy](#9-ai-model-strategy)
10. [Email Intelligence System](#10-email-intelligence-system)
11. [Dashboard Design](#11-dashboard-design)
12. [Project Folder Structure](#12-project-folder-structure)
13. [Week-by-Week Development Timeline](#13-week-by-week-development-timeline)
14. [Resume & Portfolio Value](#14-resume--portfolio-value)

---

## 1. Project Summary

**PlantMind AI** is a fully local, 100% free, multi-agent AI system built for injection moulding manufacturing factories. It automates the entire office workflow — from reading incoming customer order emails, processing purchase orders, scheduling production, monitoring raw material inventory, triggering automatic reorder emails to suppliers, tracking production progress on the floor, sending dispatch confirmation emails to customers, and delivering a daily MIS report to the factory owner every morning at 9 AM.

The system runs entirely on a single PC (Dell G15 5520) on a local network. No cloud. No paid APIs. No subscriptions. Every device inside the factory (phones, tablets, laptops) can access the dashboard through a browser on the same WiFi network.

---

## 2. Problem Statement

### Current Reality in a Typical Injection Moulding Factory Office

| Problem | Impact |
|--------|--------|
| Customer PO emails are manually read and entered into Excel | Slow, error-prone, time wasted |
| No one tracks whether raw material is sufficient for an order | Last-minute shortages cause production delays |
| Supplier reorders are done manually by calling or emailing | Stockouts happen frequently |
| Production progress is tracked on paper or WhatsApp manually | Owner has no real-time visibility |
| No daily summary — owner has to ask multiple people for updates | Time-consuming, incomplete picture |
| Dispatch confirmation is sent manually after checking with floor | Delays in client communication |

### PlantMind AI solves every single one of these.

---

## 3. System Overview

```
┌─────────────────────────────────────────────────────────┐
│                     PLANTMIND AI                        │
│              Running on Dell G15 5520                   │
│         Accessible via Local Network Browser            │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   MODULE 1          MODULE 2          MODULE 3
 Order Intake     Production &        Dispatch &
  & Email AI      Inventory AI       Reporting AI
```

### Core Principle
PlantMind AI works as a **pipeline of intelligent agents**. Each agent has one job. When it finishes, it passes the result to the next agent. The system is always watching, always processing, always updating — with zero manual data entry required from office staff for routine tasks.

---

## 4. Users & Roles

| Role | Who They Are | What They Do in PlantMind AI |
|------|-------------|------------------------------|
| **Owner / Manager** | Factory owner | Views full dashboard, receives daily 9 AM MIS report email, gets delay alerts |
| **Office Staff** | Order entry / admin person | Monitors incoming orders on dashboard, can manually trigger email check, views order status |
| **Floor Supervisor** | Production floor in-charge | Opens dashboard on any browser, updates production progress (pieces completed per order) |
| **Store Person** | Inventory / stores in-charge | Views raw material stock levels, sees auto-generated reorder status, updates stock when delivery arrives |

### Login System
All 4 roles have separate login credentials (username + password). Each role sees only what is relevant to them. The dashboard shows different views per role after login.

---

## 5. Complete Agent Flow

```
TRIGGER: Office Staff clicks "Check Emails" button on Dashboard
                          │
                          ▼
┌─────────────────────────────────────┐
│         EMAIL READER AGENT          │
│  - Connects to Gmail via Gmail API  │
│  - Scans inbox for unread emails    │
│  - Filters: only processes emails   │
│    with keywords in subject:        │
│    "PO", "Purchase Order", "Order", │
│    "Requirement", "Enquiry"         │
│  - All other emails: ignored        │
│  - Downloads attachments (PDF/DOCX) │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│      ORDER EXTRACTION AGENT         │
│  - Sends email body + attachment    │
│    text to Mistral 7B Q4_K_M        │
│  - AI extracts:                     │
│    · Customer name                  │
│    · Product name / part name       │
│    · Quantity required              │
│    · Required delivery date         │
│    · Special instructions if any    │
│  - Creates new order record in DB   │
│  - Marks email as processed         │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│      INVENTORY CHECK AGENT          │
│  - Reads order material requirement │
│  - Checks current raw material      │
│    stock in PostgreSQL database     │
│  - Calculates: is stock sufficient? │
│    (based on product-material       │
│     mapping table)                  │
└────────┬─────────────────┬──────────┘
         │                 │
    SUFFICIENT          INSUFFICIENT
         │                 │
         ▼                 ▼
  Continue flow    ┌──────────────────┐
                   │  REORDER AGENT   │
                   │ - Calculates how │
                   │   much to order  │
                   │ - Drafts reorder │
                   │   email to       │
                   │   supplier       │
                   │ - Sends via      │
                   │   Gmail SMTP     │
                   │ - Logs reorder   │
                   │   in database    │
                   └────────┬─────────┘
                            │
                            ▼
                     Continue flow
                            │
                            ▼
┌─────────────────────────────────────┐
│    PRODUCTION SCHEDULER AGENT       │
│  - Checks all active machine slots  │
│  - Finds available machine          │
│  - Assigns order to machine         │
│  - Sets estimated start date        │
│  - Sets estimated completion date   │
│  - Updates order status:            │
│    "Scheduled"                      │
│  - Dashboard shows new schedule     │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│     PRODUCTION TRACKER AGENT        │
│  - Floor Supervisor opens dashboard │
│  - Selects order, enters:           │
│    "Pieces completed so far"        │
│  - Agent calculates % completion    │
│  - Estimates new ETA                │
│  - If behind schedule:              │
│    → Emails owner with delay alert  │
│  - If production complete:          │
│    → Triggers Dispatch Agent        │
└──────────────────┬──────────────────┘
                   │
              PRODUCTION
               COMPLETE
                   │
                   ▼
┌─────────────────────────────────────┐
│         DISPATCH AGENT              │
│  - Marks order as "Ready to Ship"   │
│  - Drafts dispatch confirmation     │
│    email to customer:               │
│    "Your order ORD-XXX is ready.    │
│     Dispatch date: DD/MM/YYYY"      │
│  - Sends email via Gmail SMTP       │
│  - Updates order status:            │
│    "Dispatched"                     │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│       DAILY MIS REPORT AGENT        │
│  TRIGGER: Every day at 9:00 AM      │
│  - Reads entire database            │
│  - Generates summary:               │
│    · Total active orders            │
│    · Orders completed today         │
│    · Orders delayed                 │
│    · Current raw material levels    │
│    · Pending reorders               │
│    · Machines utilization           │
│  - Sends formatted email to owner  │
│    at 9:00 AM sharp every morning   │
└─────────────────────────────────────┘
```

---

## 6. Module Breakdown

### Module 1 — Smart Order Intake

**Purpose:** Automatically read customer emails, understand what they want, and create an order in the system.

**Components:**
- Email Reader Agent
- Smart Email Filter (keyword-based subject line filtering)
- Attachment Parser (PDF and DOCX support using PyMuPDF and python-docx)
- Order Extraction Agent (powered by Mistral 7B Q4_K_M)
- Order Creation in PostgreSQL

**Key Intelligence:**
The AI reads the email body and any attached Purchase Order document. It understands natural language — even if the customer writes casually. It extracts structured data (product name, quantity, date) and saves it as a clean order record. No human needs to type anything.

**Email Filter Logic:**
Only emails with the following keywords in the subject line are processed:
- "PO", "Purchase Order", "Order", "Requirement", "Enquiry", "Inquiry", "RFQ", "Request"

All other emails (spam, newsletters, personal) are completely ignored.

---

### Module 2 — Production & Inventory

**Purpose:** Check if materials are available, reorder if not, schedule the order on a machine, and track production progress.

**Components:**
- Inventory Check Agent
- Auto Reorder Agent (Phi-3 Mini Q4_K_M for speed)
- Production Scheduler Agent
- Production Tracker Agent
- Floor Supervisor Web Form (simple browser-based input)

**Key Intelligence:**
- The system knows which plastic granule / raw material is needed for each product (stored in a product-material mapping table)
- It checks current stock against required quantity
- If insufficient, it automatically calculates reorder quantity and sends a professional email to the supplier
- Production scheduling considers machine availability and existing workload
- Floor supervisor inputs progress updates via a simple web form — no app installation needed

---

### Module 3 — Dispatch & Reporting

**Purpose:** Notify customer when order is ready and give the owner a daily morning briefing.

**Components:**
- Dispatch Agent (Phi-3 Mini Q4_K_M)
- Daily MIS Report Agent (Mistral 7B Q4_K_M for quality report generation)
- Gmail SMTP for sending all emails
- APScheduler for 9 AM daily trigger

**Key Intelligence:**
- Dispatch email is automatically sent to customer when floor supervisor marks production complete
- Daily MIS report is a clean, readable email summarizing the entire factory status — sent at 9 AM every morning without anyone pressing a button

---

## 7. Database Schema

### Tables Overview

**1. users**
Stores login credentials for all 4 roles.
- user_id, username, password_hash, role (owner/office/supervisor/store), created_at

**2. customers**
Customer directory built automatically from processed emails.
- customer_id, name, email, phone, address, created_at

**3. suppliers**
Supplier directory for raw material reordering.
- supplier_id, name, email, phone, material_supplied, created_at

**4. raw_materials**
Current stock of all plastic granules and raw materials.
- material_id, name, type, current_stock_kg, reorder_level_kg, reorder_quantity_kg, unit_price, supplier_id, last_updated

**5. products**
All products the factory manufactures.
- product_id, name, description, material_required_per_unit_kg, machine_cycle_time_seconds, created_at

**6. product_material_mapping**
Links each product to the raw material it needs.
- mapping_id, product_id, material_id, quantity_per_unit_kg

**7. machines**
All injection moulding machines in the factory.
- machine_id, name, status (available/running/maintenance), current_order_id, last_maintenance_date

**8. orders**
Core order table — every customer order lives here.
- order_id, customer_id, product_id, quantity, required_delivery_date, status (new/scheduled/in_production/completed/dispatched), created_at, source_email_id

**9. order_status_log**
Full history of every status change for every order.
- log_id, order_id, old_status, new_status, changed_at, changed_by

**10. production_schedule**
Tracks which order is assigned to which machine.
- schedule_id, order_id, machine_id, estimated_start, estimated_end, actual_start, actual_end, status

**11. production_progress**
Floor supervisor inputs live here.
- progress_id, schedule_id, pieces_completed, total_pieces, updated_by, updated_at, notes

**12. reorder_log**
Every supplier reorder email sent by the system.
- reorder_id, material_id, supplier_id, quantity_ordered_kg, email_sent_at, status (sent/confirmed/delivered)

**13. email_log**
Every email the system processes (incoming) or sends (outgoing).
- email_id, direction (in/out), from_address, to_address, subject, body_summary, attachment_name, processed_at, linked_order_id

**14. mis_report_log**
Record of every daily MIS report generated and sent.
- report_id, generated_at, sent_to_email, report_summary_text, status

---

## 8. Tech Stack

### Complete Free Stack — Runs 100% on Local PC

| Layer | Technology | Purpose | Cost |
|-------|-----------|---------|------|
| AI Runtime | Ollama | Run LLMs locally | Free |
| Primary AI Model | Mistral 7B Instruct Q4_K_M | Complex reasoning, email extraction, report generation | Free |
| Secondary AI Model | Phi-3 Mini Q4_K_M | Fast simple tasks: reorder emails, dispatch emails, status alerts | Free |
| Backend Framework | Python + FastAPI | API server, agent orchestration, dashboard backend | Free |
| Database | PostgreSQL | All data storage | Free |
| ORM | SQLAlchemy | Database interaction from Python | Free |
| Email Reading | Gmail API (OAuth2) | Read incoming customer emails | Free |
| Email Sending | Nodemailer / smtplib (Python) | Send all outgoing emails via Gmail SMTP | Free |
| PDF Parser | PyMuPDF (fitz) | Extract text from PDF attachments | Free |
| DOCX Parser | python-docx | Extract text from Word attachments | Free |
| Task Scheduler | APScheduler | Trigger 9 AM daily MIS report | Free |
| Frontend Dashboard | HTML + CSS + Vanilla JS | All 4 user role dashboards | Free |
| Local Network Access | FastAPI serves HTML | Any device on WiFi opens dashboard in browser | Free |
| Password Security | bcrypt | Hash and verify passwords | Free |
| Environment Config | python-dotenv | Store Gmail credentials securely | Free |

### Why No React or Streamlit?
FastAPI serving plain HTML/CSS/JS is the right choice here because:
- Works on any browser, any device, on local network
- No build step, no Node.js required on factory devices
- Loads instantly even on slow local network
- Easier to maintain long term

---

## 9. AI Model Strategy

### Two Models, Two Jobs

| Task | Model | Reason |
|------|-------|--------|
| Reading email + extracting order details | Mistral 7B Q4_K_M | Needs deep language understanding, handles messy customer writing |
| Parsing PDF/DOCX attachments | Mistral 7B Q4_K_M | Complex document understanding |
| Daily MIS Report generation | Mistral 7B Q4_K_M | Needs quality, structured, professional writing |
| Reorder email drafting | Phi-3 Mini Q4_K_M | Simple template-style email, speed matters |
| Dispatch confirmation email | Phi-3 Mini Q4_K_M | Short, simple email, no heavy reasoning needed |
| Delay alert email to owner | Phi-3 Mini Q4_K_M | Short alert message |

### Model Loading Strategy
- Models are **not loaded simultaneously** — they are loaded on-demand and unloaded after task completes
- This prevents VRAM overflow on the RTX 3050 (4GB VRAM)
- Mistral 7B Q4_K_M uses ~3.8 GB VRAM
- Phi-3 Mini Q4_K_M uses ~2.3 GB VRAM
- Only one model runs at a time

### Ollama Commands to Pull Models
```
ollama pull mistral:7b-instruct-q4_K_M
ollama pull phi3:mini-q4_K_M
```

---

## 10. Email Intelligence System

### Incoming Email Processing

**Step 1 — Filter**
System reads Gmail inbox. Only emails matching these subject keywords are processed:
`PO | Purchase Order | Order | Requirement | Enquiry | Inquiry | RFQ | Request for Quotation`

**Step 2 — Extract**
Email body + attachment text is sent to Mistral with this instruction style:
> "You are a factory order assistant. Extract the following fields from this email: customer name, product name, quantity, required delivery date, special instructions. Return as JSON only."

**Step 3 — Validate**
System checks if extracted data is complete. If critical fields are missing (e.g. quantity not found), it flags the email for manual review on the Office Staff dashboard — it does NOT auto-create an incomplete order.

**Step 4 — Log**
Every processed email is saved in the email_log table with full details.

### Outgoing Emails — 4 Types

| Email Type | Trigger | Sent To | Model Used |
|-----------|---------|---------|-----------|
| Supplier Reorder | Stock below reorder level | Supplier | Phi-3 Mini |
| Delay Alert | Production behind schedule | Owner | Phi-3 Mini |
| Dispatch Confirmation | Production marked complete | Customer | Phi-3 Mini |
| Daily MIS Report | 9 AM every day | Owner | Mistral 7B |

---

## 11. Dashboard Design

### Login Page
Single login page. Username + password. Role is detected automatically after login. Each role is redirected to their own dashboard view.

---

### Owner Dashboard
- Total orders today (new / in production / completed / dispatched)
- Raw material stock levels with visual indicators (green/yellow/red)
- Machines status (running / available / maintenance)
- Recent delay alerts
- Button: Download MIS Report (last 7 days)
- Recent email log

---

### Office Staff Dashboard
- Button: **"Check New Emails"** (manual trigger — the main action button)
- Incoming orders list with status
- Flagged emails (incomplete extraction — needs manual review)
- Order details view (click any order to see full details)
- Email processing log

---

### Floor Supervisor Dashboard
- List of all orders currently "In Production" assigned to machines
- For each order: machine name, total pieces, pieces completed, ETA
- **Update Progress Form:** Select order → Enter pieces completed → Submit
- Completed orders button (mark production done → triggers dispatch)

---

### Store Person Dashboard
- Raw material stock table (material name, current stock, reorder level, status)
- Reorder log (what was ordered, when, from which supplier)
- **Update Stock Form:** When new material delivery arrives → select material → enter received quantity → submit
- Low stock alerts panel

---

## 12. Project Folder Structure

```
plantmind-ai/
│
├── main.py                         # FastAPI app entry point
├── scheduler.py                    # APScheduler for 9 AM MIS report
├── .env                            # Gmail credentials, DB URL (never commit this)
├── requirements.txt                # All Python dependencies
│
├── agents/
│   ├── email_reader_agent.py       # Gmail API, email fetching & filtering
│   ├── order_extractor_agent.py    # Mistral 7B — extracts order from email
│   ├── inventory_check_agent.py    # Checks stock vs order requirement
│   ├── reorder_agent.py            # Phi-3 Mini — drafts & sends reorder email
│   ├── production_scheduler_agent.py # Assigns order to machine
│   ├── production_tracker_agent.py # Handles floor supervisor updates
│   ├── dispatch_agent.py           # Phi-3 Mini — sends dispatch email
│   └── mis_report_agent.py         # Mistral 7B — generates & sends daily report
│
├── models/
│   ├── ollama_mistral.py           # Mistral 7B Q4_K_M interface
│   └── ollama_phi3.py              # Phi-3 Mini Q4_K_M interface
│
├── database/
│   ├── connection.py               # PostgreSQL connection via SQLAlchemy
│   ├── schema.sql                  # Full SQL schema (all 14 tables)
│   └── queries/
│       ├── order_queries.py
│       ├── inventory_queries.py
│       ├── production_queries.py
│       └── report_queries.py
│
├── routers/
│   ├── auth_router.py              # Login / logout endpoints
│   ├── order_router.py             # Order-related API endpoints
│   ├── inventory_router.py         # Inventory & reorder endpoints
│   ├── production_router.py        # Production tracking endpoints
│   └── report_router.py            # MIS report endpoints
│
├── email/
│   ├── gmail_reader.py             # Gmail API OAuth2 read
│   ├── gmail_sender.py             # Gmail SMTP send
│   └── email_templates/
│       ├── reorder_template.txt
│       ├── dispatch_template.txt
│       ├── delay_alert_template.txt
│       └── mis_report_template.txt
│
├── parsers/
│   ├── pdf_parser.py               # PyMuPDF — extract text from PDF
│   └── docx_parser.py              # python-docx — extract text from DOCX
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── dashboard.js
│
└── templates/
    ├── login.html
    ├── owner_dashboard.html
    ├── office_dashboard.html
    ├── supervisor_dashboard.html
    └── store_dashboard.html
```

---

## 13. Week-by-Week Development Timeline

### Phase 1 — Foundation (Weeks 1–2)

**Week 1**
- Install and configure PostgreSQL
- Create all 14 tables using schema.sql
- Install Ollama, pull Mistral 7B Q4_K_M and Phi-3 Mini Q4_K_M
- Test both models via Ollama API — make sure they respond correctly
- Set up Gmail API OAuth2 — get credentials.json
- Set up project folder structure
- Create .env file with all credentials
- Install all Python dependencies (FastAPI, SQLAlchemy, PyMuPDF, etc.)

**Week 2**
- Build FastAPI app skeleton (main.py)
- Build login system (auth_router.py) with bcrypt password hashing
- Create 4 basic dashboard HTML pages (just layout, no data yet)
- Test login → role detection → redirect to correct dashboard
- Seed database with test data (2–3 customers, 3 machines, 5 materials, 2 products)

**Milestone:** Login works. All 4 dashboards load. Database is ready. Both AI models respond.

---

### Phase 2 — Email & Order Intake (Weeks 3–4)

**Week 3**
- Build gmail_reader.py — connect to Gmail, fetch unread emails
- Build email filter logic — keyword matching on subject line
- Build pdf_parser.py and docx_parser.py — test with sample PO documents
- Test: send a test PO email to Gmail → system reads it → attachment text extracted

**Week 4**
- Build order_extractor_agent.py — send email + attachment to Mistral 7B
- Prompt engineering: craft the perfect extraction prompt for Mistral
- Handle edge cases: missing fields → flag for manual review
- Build order_queries.py — save extracted order to database
- Connect "Check Emails" button on Office Dashboard to trigger this full flow
- Test end-to-end: email arrives → button clicked → order appears in dashboard

**Milestone:** Full email-to-order pipeline works. Send 5 test emails with different formats. All extracted correctly.

---

### Phase 3 — Inventory & Reorder (Weeks 5–6)

**Week 5**
- Build inventory_check_agent.py
- Create product-material mapping data in database
- Build logic: order quantity × material per unit = total material needed
- Compare against current stock → sufficient or not
- Build Store Person dashboard with live stock table
- Build stock update form (store person enters received quantity)

**Week 6**
- Build reorder_agent.py — Phi-3 Mini drafts reorder email
- Build gmail_sender.py — send email via Gmail SMTP
- Build reorder email template
- Test: set material stock below reorder level → order comes in → reorder email auto-sent to supplier
- Build reorder_log entries in database
- Show reorder status on Store Person dashboard

**Milestone:** Inventory check works. Auto reorder email sent correctly. Store person can update stock.

---

### Phase 4 — Production Scheduling & Tracking (Weeks 7–9)

**Week 7**
- Build production_scheduler_agent.py
- Logic: check machine availability → assign order → calculate ETA based on quantity × cycle time
- Create production_schedule record in database
- Show scheduled orders on Floor Supervisor dashboard with machine assignment

**Week 8**
- Build Floor Supervisor update form
- Build production_tracker_agent.py
- Calculate % completion and updated ETA on each supervisor update
- Build delay detection: if current date > estimated end date and not complete → delay alert
- Build delay alert email (Phi-3 Mini) → send to owner

**Week 9**
- Test full production flow: order scheduled → supervisor updates progress 3–4 times → completion marked
- Test delay scenario: set ETA to yesterday → update progress → owner gets delay email
- Connect production completion → automatically trigger Dispatch Agent

**Milestone:** Full production tracking works. Delay alerts sent. Supervisor dashboard fully functional.

---

### Phase 5 — Dispatch & MIS Report (Weeks 10–11)

**Week 10**
- Build dispatch_agent.py — Phi-3 Mini drafts dispatch email
- Build dispatch email template
- Test: mark order complete → dispatch email auto-sent to customer → order status → "Dispatched"
- Update all dashboard status views to show dispatched orders correctly

**Week 11**
- Build mis_report_agent.py — Mistral 7B reads all data, generates full summary
- Build MIS report email template
- Build APScheduler trigger: every day at 9:00 AM → generate report → send to owner email
- Test report quality: does it cover all key metrics clearly?
- Refine Mistral prompt until report quality is professional

**Milestone:** Dispatch email works. Daily MIS report arrives at 9 AM. Full pipeline is complete end-to-end.

---

### Phase 6 — Polish, Testing & Demo (Week 12)

**Week 12**
- Full end-to-end test with realistic data
- Run 10 complete order cycles from email → dispatch
- Fix all bugs found during testing
- Improve dashboard UI — make it clean and professional
- Write README.md with full setup instructions
- Record a demo video showing the full flow (for portfolio)
- Take screenshots of all dashboards for resume/portfolio
- Write project description for resume

**Final Milestone:** PlantMind AI is demo-ready. All agents work. All 4 dashboards work. Full pipeline runs smoothly.

---

## 14. Resume & Portfolio Value

### What Makes This Impressive

**Technical Depth**
- Multi-agent AI pipeline (not just a chatbot)
- Two AI models used strategically (not just one)
- Gmail API integration (OAuth2 — industry standard)
- PostgreSQL with 14 normalized tables
- Local LLM deployment using Ollama (cutting-edge skill)
- Role-based access control with authentication
- Automated email generation and sending
- Task scheduling (APScheduler)
- PDF and DOCX document parsing

**Business Impact**
- Solves real, painful problems in a real industry
- Actually deployed (or deployable) in a real factory
- Measurable outcomes: hours saved per day, errors eliminated

### How to Present on Resume

```
PlantMind AI — Factory Intelligence Platform
Agentic AI System | Python, FastAPI, PostgreSQL, Ollama, Gmail API

• Built a multi-agent AI system automating end-to-end factory office 
  operations for an injection moulding manufacturing business
• Implemented intelligent email parsing using Mistral 7B (Q4_K_M) 
  to extract structured order data from customer PO emails and attachments
• Developed automated inventory monitoring with real-time reorder 
  triggers — supplier emails sent automatically when stock falls below threshold
• Built production scheduling and progress tracking system accessible 
  via local network dashboard by floor supervisors
• Integrated daily AI-generated MIS report delivered to factory owner 
  every morning via automated email pipeline
• Deployed entirely on local infrastructure (Dell G15, RTX 3050) 
  with zero cloud dependency or recurring cost
Tech: Python · FastAPI · PostgreSQL · Ollama · Mistral 7B · Phi-3 Mini · 
      Gmail API · PyMuPDF · SQLAlchemy · HTML/CSS · APScheduler
```

### Skills It Proves to Recruiters
- Agentic AI architecture and design
- Local LLM deployment and prompt engineering
- Backend development (FastAPI, REST APIs)
- Database design and SQL
- System integration (Email APIs, file parsers, schedulers)
- Real-world problem solving in manufacturing domain
- End-to-end project ownership

---

*PlantMind AI — Turning factory chaos into intelligent automation.*
