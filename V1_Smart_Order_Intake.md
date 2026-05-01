# 📧 PlantMind AI — Version 1
## Smart Order Intake System
### Standalone Project | Builds into PlantMind AI Final

**Version:** 1.0  
**Module:** Order Intake & Email Intelligence  
**Timeline:** 3 Weeks  
**Position in Full Project:** V1 of 3 — Foundation Layer  

---

## 📌 Table of Contents
1. [What V1 Is](#1-what-v1-is)
2. [Problem This Solves](#2-problem-this-solves)
3. [System Flow](#3-system-flow)
4. [Agents in V1](#4-agents-in-v1)
5. [Email Filter Logic](#5-email-filter-logic)
6. [AI Extraction Logic](#6-ai-extraction-logic)
7. [Database Schema — V1 Tables](#7-database-schema--v1-tables)
8. [Dashboard — Office Staff](#8-dashboard--office-staff)
9. [Tech Stack](#9-tech-stack)
10. [Folder Structure](#10-folder-structure)
11. [Week-by-Week Plan](#11-week-by-week-plan)
12. [Testing Checklist](#12-testing-checklist)
13. [How V1 Connects to V2](#13-how-v1-connects-to-v2)
14. [Resume Value](#14-resume-value)

---

## 1. What V1 Is

V1 is the **entry point of PlantMind AI**. It is a fully standalone, working system that does one job extremely well: it reads incoming customer emails, filters out irrelevant ones, reads any attached Purchase Order documents, uses a local AI model to extract structured order information, and displays all orders on a clean dashboard for office staff.

When V1 is complete, the factory office has a fully automated order intake system. No one needs to manually read emails and type order details into Excel. The system does it automatically every time office staff clicks one button.

V1 is impressive enough to stand alone as a college project. It is also the foundation that V2 and V3 build on top of.

---

## 2. Problem This Solves

### Before V1 (Manual Process)
```
Customer sends email with PO attached
          ↓
Office staff opens email (maybe after hours)
          ↓
Opens PDF attachment manually
          ↓
Reads through it to find product, quantity, date
          ↓
Types it all into Excel manually
          ↓
Tells production team verbally or via WhatsApp
          ↓
Information gets lost, delayed, or entered wrong
```

**Problems:** Slow. Error-prone. Dependent on one person. No record. No visibility.

### After V1 (Automated)
```
Customer sends email with PO attached
          ↓
Office staff clicks "Check Emails" button
          ↓
System reads, filters, extracts, and saves order
          ↓
Order appears on dashboard instantly
          ↓
Full team has visibility immediately
```

**Result:** Zero manual typing. Zero missed emails. Full order history. Instant visibility.

---

## 3. System Flow

```
┌─────────────────────────────────────────────────────┐
│           OFFICE STAFF DASHBOARD                    │
│    Clicks "Check New Emails" button                 │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              EMAIL READER AGENT                     │
│                                                     │
│  1. Connects to Gmail using OAuth2 credentials      │
│  2. Fetches all UNREAD emails from inbox            │
│  3. Passes each email to the Email Filter           │
│  4. Already-processed emails are skipped            │
│     (tracked via email_log table)                   │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              EMAIL FILTER AGENT                     │
│                                                     │
│  Checks subject line for keywords:                  │
│  PO / Purchase Order / Order / Requirement /        │
│  Enquiry / Inquiry / RFQ / Request                  │
│                                                     │
│  MATCH → passes to Attachment Parser                │
│  NO MATCH → email ignored, marked as skipped        │
└──────────────────────┬──────────────────────────────┘
                       │
                  EMAIL MATCHED
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│            ATTACHMENT PARSER                        │
│                                                     │
│  Checks if email has attachment:                    │
│                                                     │
│  PDF attachment → PyMuPDF extracts all text         │
│  DOCX attachment → python-docx extracts all text    │
│  No attachment → uses email body text only          │
│                                                     │
│  Output: clean plain text of order content          │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│           ORDER EXTRACTION AGENT                    │
│        (Powered by Mistral 7B Q4_K_M)               │
│                                                     │
│  Sends combined text (email + attachment) to        │
│  Mistral with a structured extraction prompt        │
│                                                     │
│  AI extracts:                                       │
│  · Customer name                                    │
│  · Customer email address                           │
│  · Product name / part name                         │
│  · Quantity required                                │
│  · Required delivery date                           │
│  · Special instructions (if any)                    │
│                                                     │
│  Returns: clean JSON object                         │
└──────────────────────┬──────────────────────────────┘
                       │
            ┌──────────┴──────────┐
            │                     │
      ALL FIELDS              MISSING FIELDS
       PRESENT                   FOUND
            │                     │
            ▼                     ▼
┌─────────────────┐   ┌───────────────────────────┐
│  ORDER SAVED    │   │  FLAGGED FOR MANUAL REVIEW │
│  TO DATABASE    │   │  Appears in "Needs Action" │
│  Status: New    │   │  section of dashboard      │
│                 │   │  Office staff fills gap    │
│  Customer auto- │   │  manually then approves    │
│  created if new │   └───────────────────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│           DASHBOARD UPDATED                         │
│  New order appears in "Incoming Orders" table       │
│  Email marked as processed in email_log             │
│  Customer added to customers table if new           │
└─────────────────────────────────────────────────────┘
```

---

## 4. Agents in V1

### Agent 1 — Email Reader Agent
**File:** `agents/email_reader_agent.py`

**Responsibility:**
- Authenticate with Gmail using stored OAuth2 token
- Fetch all unread emails from inbox
- For each email, check email_log table — skip if already processed
- Extract: sender address, subject, body text, list of attachments
- Pass each unprocessed email to Email Filter Agent

**Key Logic:**
- Uses Gmail API with `messages.list` and `messages.get`
- Reads only UNREAD emails to avoid reprocessing
- After processing, marks email as read in Gmail
- Saves every email (matched or not) to email_log with status

---

### Agent 2 — Email Filter Agent
**File:** `agents/email_filter_agent.py`

**Responsibility:**
- Receive email subject line
- Check against keyword list (case-insensitive)
- Return: PROCESS or SKIP decision

**Keyword List:**
```
"purchase order", "po", "p.o", "order", "requirement",
"enquiry", "inquiry", "rfq", "request for quotation",
"request for quote", "supply request", "material request"
```

**Logic:**
- Any ONE keyword match in subject → PROCESS
- Zero matches → SKIP, log as "irrelevant" in email_log
- Keyword matching is case-insensitive
- Partial matches count (e.g. "our order for 500 pcs" matches "order")

---

### Agent 3 — Attachment Parser
**File:** `parsers/attachment_parser.py`

**Responsibility:**
- Receive list of attachments from email
- Download each attachment temporarily
- Extract all readable text from PDF or DOCX
- Return combined plain text
- Delete temporary files after extraction

**Supported Formats:**
- `.pdf` → PyMuPDF (fitz) — extracts text from digital PDFs (scanned-image PDFs need OCR in a later enhancement)
- `.docx` → python-docx — extracts all paragraphs and tables
- `.doc` → not supported (log warning, use email body only)
- No attachment → return empty string (email body used only)

**Table Extraction:**
PyMuPDF preserves readable table text in many digital PDFs, which is important because most Purchase Order documents are formatted in columns such as Item, Quantity, Rate, and Delivery Date.

---

### Agent 4 — Order Extraction Agent
**File:** `agents/order_extractor_agent.py`

**Responsibility:**
- Combine email body text + attachment text into one string
- Send to Mistral 7B Q4_K_M via Ollama API
- Parse AI response as JSON
- Validate all required fields are present
- Return structured order data or flag as incomplete

**AI Model Used:** Mistral 7B Instruct Q4_K_M
**Why Mistral:** Customer emails are often messy, informal, or in mixed formats. Mistral 7B has strong instruction-following and handles real-world noisy text well. Phi-3 Mini is too lightweight for this extraction task.

**Required Fields:**
- customer_name (required)
- customer_email (required — taken from sender if not in body)
- product_name (required)
- quantity (required)
- delivery_date (required)
- special_instructions (optional — empty string if not present)

**Validation:**
If any required field is missing or unclear → order is flagged, not saved automatically. Office staff sees it in "Needs Review" section and can fill in the missing field manually.

---

## 5. Email Filter Logic

### Why Manual Trigger (Not Automatic)
The system checks emails only when office staff clicks the "Check Emails" button. This is intentional:
- Gives staff control over when processing happens
- Avoids processing emails that arrive mid-conversation with a customer
- Keeps the system predictable and easy to understand
- No risk of background processes interfering with work

### Filter Decision Table

| Subject Line Example | Decision | Reason |
|---------------------|----------|--------|
| "Purchase Order #4521 — HDPE Caps" | PROCESS | Contains "Purchase Order" |
| "PO attached for 5000 pcs" | PROCESS | Contains "PO" |
| "Requirement for plastic containers" | PROCESS | Contains "Requirement" |
| "RFQ — Injection Moulded Parts" | PROCESS | Contains "RFQ" |
| "Meeting tomorrow at 3 PM" | SKIP | No keywords |
| "Invoice #1023 from XYZ" | SKIP | No keywords |
| "Happy Diwali from ABC Plastics" | SKIP | No keywords |
| "Order status enquiry" | PROCESS | Contains "Order" and "enquiry" |

---

## 6. AI Extraction Logic

### Prompt Sent to Mistral 7B

```
You are an order processing assistant for a plastic injection moulding factory.

You will receive the content of a customer email and any attached Purchase Order document.

Your task is to extract the following information and return it as a valid JSON object only.
Do not write any explanation. Do not write any extra text. Return only the JSON.

Extract these fields:
- customer_name: Full name of the customer or company placing the order
- customer_email: Email address of the sender
- product_name: Name or description of the product or part being ordered
- quantity: Number of pieces or units required (integer only, no units text)
- delivery_date: Required delivery date in YYYY-MM-DD format
- special_instructions: Any special requirements, notes, or instructions (empty string if none)

If any field cannot be determined from the content, set its value to null.

Email and document content:
[EMAIL BODY AND ATTACHMENT TEXT INSERTED HERE]
```

### Expected AI Output
```json
{
  "customer_name": "Rajesh Polymers Pvt Ltd",
  "customer_email": "orders@rajeshpolymers.com",
  "product_name": "HDPE Container Cap 50mm",
  "quantity": 10000,
  "delivery_date": "2025-06-15",
  "special_instructions": "All caps must be food-grade certified"
}
```

### Handling AI Errors
- If Mistral returns invalid JSON → retry once with cleaner prompt
- If second attempt fails → flag email for manual review
- If Mistral returns null for required field → flag for manual review
- All errors logged in email_log table with error details

---

## 7. Database Schema — V1 Tables

V1 primarily uses 4 core tables from the full PlantMind schema. In the integrated V1+V2+V3 system, additional tables (products, raw_materials, machines, schedules, logs) are already available and get activated as later modules are implemented.

---

### Table 1: customers
Stores all customers discovered from emails. Auto-created when new sender found.

```
customer_id        SERIAL PRIMARY KEY
name               VARCHAR(200) NOT NULL
email              VARCHAR(200) UNIQUE NOT NULL
phone              VARCHAR(20)
address            TEXT
created_at         TIMESTAMP DEFAULT NOW()
```

---

### Table 2: orders
Core order record. Created by Order Extraction Agent.

```
order_id                SERIAL PRIMARY KEY
customer_id             INTEGER REFERENCES customers(customer_id)
product_name            VARCHAR(300) NOT NULL
quantity                INTEGER NOT NULL
required_delivery_date  DATE
special_instructions    TEXT
status                  VARCHAR(50) DEFAULT 'new'
                        -- Values: new / needs_review / scheduled /
                        --         in_production / completed / dispatched
source_email_id         INTEGER REFERENCES email_log(email_id)
created_at              TIMESTAMP DEFAULT NOW()
```

> Note: In the full PlantMind deployment, extracted `product_name` is mapped to the shared `products` catalog and linked through `product_id` for downstream scheduling and inventory logic.

---

### Table 3: email_log
Every email the system sees — processed or skipped.

```
email_id           SERIAL PRIMARY KEY
gmail_message_id   VARCHAR(200) UNIQUE NOT NULL
direction          VARCHAR(10) DEFAULT 'in'
                   -- Values: in / out
from_address       VARCHAR(200)
to_address         VARCHAR(200)
subject            TEXT
body_summary       TEXT
attachment_name    VARCHAR(200)
filter_decision    VARCHAR(20)
                   -- Values: process / skip
processing_status  VARCHAR(30)
                   -- Values: success / flagged / error / skipped
linked_order_id    INTEGER REFERENCES orders(order_id)
error_details      TEXT
processed_at       TIMESTAMP DEFAULT NOW()
```

---

### Table 4: users
Login credentials for all roles. V1 primarily uses the office role, while the same table already supports owner, supervisor, and store users for V2/V3.

```
user_id            SERIAL PRIMARY KEY
username           VARCHAR(100) UNIQUE NOT NULL
password_hash      VARCHAR(255) NOT NULL
role               VARCHAR(30) NOT NULL
                   -- Values: owner / office / supervisor / store
is_active          BOOLEAN DEFAULT TRUE
created_at         TIMESTAMP DEFAULT NOW()
```

---

## 8. Dashboard — Office Staff

V1 has one dashboard: the Office Staff Dashboard. It is accessible at `http://localhost:8000` or `http://[PC-IP]:8000` from any device on the same WiFi network.

### Login Page
- Username and password fields
- On success: redirected to Office Staff Dashboard
- Wrong credentials: error message shown inline
- Session stored in browser cookie (expires after 8 hours)

---

### Office Staff Dashboard Layout

#### Top Bar
- PlantMind AI logo + "V1 — Order Intake"
- Logged in as: [username]
- Logout button

---

#### Section 1 — Action Button (Most Prominent Element)
```
┌─────────────────────────────────────────┐
│                                         │
│     📧  CHECK NEW EMAILS                │
│         [Large clickable button]        │
│                                         │
│  Last checked: Today 2:30 PM            │
│  Emails processed this session: 3       │
│                                         │
└─────────────────────────────────────────┘
```
Clicking this triggers the full email → extraction → save pipeline.
A loading spinner shows while processing. Results appear below when done.

---

#### Section 2 — Processing Result (appears after button click)
Shows what happened in the last check:
- X new orders created
- X emails skipped (not relevant)
- X emails need manual review
- X emails already processed before

---

#### Section 3 — Needs Review (Flagged Orders)
Orders where AI could not extract all fields. Office staff must complete these manually.

| Order # | From | Product | Missing Field | Action |
|---------|------|---------|---------------|--------|
| ORD-004 | abc@xyz.com | Plastic Cap | delivery_date | [Complete] |

Clicking [Complete] opens a small form to fill in the missing field and approve the order.

---

#### Section 4 — All Orders Table
Complete list of all orders in the system.

| Order # | Customer | Product | Qty | Delivery Date | Status | Received |
|---------|----------|---------|-----|---------------|--------|----------|
| ORD-007 | Raj Polymers | HDPE Cap | 10,000 | 15 Jun 2025 | New | Today |
| ORD-006 | ABC Plastics | Container | 5,000 | 20 Jun 2025 | Scheduled | Yesterday |

- Click any order row to see full details
- Status badges are color coded: New (blue), Scheduled (orange), In Production (yellow), Completed (green), Dispatched (grey)
- Search bar to filter by customer name or product

---

#### Section 5 — Email Log
Last 20 emails the system has seen.

| Time | From | Subject | Decision | Result |
|------|------|---------|----------|--------|
| 2:30 PM | raj@xyz.com | PO #4521 HDPE Caps | Processed | Order Created |
| 2:30 PM | info@abc.com | Meeting tomorrow | Skipped | Not relevant |

---

## 9. Tech Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| AI Runtime | Ollama | Latest | Run Mistral locally |
| AI Model | Mistral 7B Instruct Q4_K_M | mistral:7b-instruct-q4_K_M | Order extraction |
| Backend | Python + FastAPI | Python 3.11+ | API server + HTML serving |
| Database | PostgreSQL | 15+ | Data storage |
| ORM | SQLAlchemy | 2.x | Database interaction |
| Email Read | Gmail API | v1 | Read inbox via OAuth2 |
| PDF Parser | PyMuPDF | Latest | Extract text from PDF attachments |
| DOCX Parser | python-docx | Latest | Extract text from DOCX attachments |
| Password | bcrypt | Latest | Hash user passwords |
| Sessions | itsdangerous | Latest | Secure session cookies |
| Frontend | HTML5 + CSS3 + Vanilla JS | — | Dashboard UI |
| Config | python-dotenv | Latest | Environment variables |
| HTTP Client | httpx | Latest | Call Ollama API |

### Python Dependencies (requirements.txt)
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
```

---

## 10. Folder Structure

```
plantmind-v1/
│
├── main.py                          # FastAPI app, routes registration
├── requirements.txt
├── .env                             # Gmail credentials, DB URL, secret key
├── credentials.json                 # Gmail OAuth2 credentials (from Google Console)
├── token.json                       # Auto-generated after first Gmail login
│
├── agents/
│   ├── email_reader_agent.py        # Gmail API connection, fetch unread emails
│   ├── email_filter_agent.py        # Keyword matching, process/skip decision
│   └── order_extractor_agent.py     # Mistral 7B extraction, JSON validation
│
├── parsers/
│   ├── attachment_parser.py         # Routes to PDF or DOCX parser
│   ├── pdf_parser.py                # PyMuPDF text extraction
│   └── docx_parser.py              # python-docx text extraction
│
├── models/
│   └── ollama_mistral.py            # Ollama API call wrapper for Mistral 7B
│
├── database/
│   ├── connection.py                # SQLAlchemy engine + session
│   ├── schema.sql                   # Full SQL CREATE TABLE statements
│   └── queries/
│       ├── order_queries.py         # Save order, get orders, update status
│       ├── customer_queries.py      # Find or create customer
│       └── email_log_queries.py     # Log email, check if already processed
│
├── routers/
│   ├── auth_router.py               # POST /login, GET /logout
│   ├── email_router.py              # POST /check-emails (trigger agent)
│   └── order_router.py              # GET /orders, POST /orders/complete-review
│
├── templates/
│   ├── login.html
│   └── office_dashboard.html
│
└── static/
    ├── css/
    │   └── style.css
    └── js/
        └── office_dashboard.js
```

---

## 11. Week-by-Week Plan

### Week 1 — Setup & Email Reading

**Day 1–2: Environment Setup**
- Install PostgreSQL, create database `plantmind`
- Run schema.sql to create all 4 V1 tables
- Insert 1 test user (office_staff role) with bcrypt hashed password
- Install Ollama, pull `mistral:7b-instruct-q4_K_M`
- Test Ollama responds: `ollama run mistral:7b-instruct-q4_K_M "Hello"`
- Set up project folder structure
- Create `.env` file with DB URL, secret key

**Day 3–4: Gmail API Setup**
- Go to Google Cloud Console → Create project → Enable Gmail API
- Download `credentials.json`
- Write `email_reader_agent.py` — OAuth2 flow, first login via browser
- Test: print list of unread email subjects from inbox
- Handle token refresh (auto-refresh when expired)

**Day 5–7: Email Filter + Attachment Parser**
- Write `email_filter_agent.py` — keyword matching logic
- Test filter with 10 sample emails (5 relevant, 5 not)
- Write `pdf_parser.py` — extract text from a sample PO PDF
- Write `docx_parser.py` — extract text from a sample PO DOCX
- Write `attachment_parser.py` — routes to correct parser
- Test: send yourself a test email with PDF attached → system reads and extracts text

**Week 1 Milestone:** Email reading works. Filter correctly identifies relevant emails. Attachment text is extracted cleanly.

---

### Week 2 — AI Extraction + Database

**Day 8–9: Ollama Integration**
- Write `ollama_mistral.py` — simple function that sends text to Mistral, returns response
- Test raw extraction: paste a sample PO text → Mistral returns JSON
- Refine prompt until JSON is clean and accurate
- Test with 5 different PO formats (different customers write differently)

**Day 10–11: Order Extraction Agent**
- Write `order_extractor_agent.py`
- Connect attachment text → Mistral prompt → JSON parse
- Add validation logic: check all required fields present
- Handle null fields → flag as incomplete
- Handle invalid JSON response → retry once → flag if fails again

**Day 12–13: Database Layer**
- Write `connection.py` — SQLAlchemy engine
- Write all query files: order_queries, customer_queries, email_log_queries
- Test: save a manually constructed order dict to database
- Test: find-or-create customer logic (same customer emails twice → only one record)

**Day 14: Full Pipeline Test (No Dashboard)**
- Run full flow from Python script (no UI yet)
- Send test email with PO PDF to Gmail
- Run script → email read → filtered → PDF parsed → Mistral extracts → order saved to DB
- Query DB to confirm order is saved correctly

**Week 2 Milestone:** Full backend pipeline works. Email → extraction → database. No dashboard yet.

---

### Week 3 — Dashboard + Login + Polish

**Day 15–16: FastAPI + Auth**
- Write `main.py` — FastAPI app setup, register all routers
- Write `auth_router.py` — POST /login with bcrypt verification, session cookie
- Write `login.html` — clean login form
- Test: login with correct/incorrect credentials

**Day 17–18: Office Dashboard**
- Write `office_dashboard.html` — full layout with all 5 sections
- Write `office_dashboard.js` — "Check Emails" button calls POST /check-emails
- Show loading spinner while processing
- Show results summary after processing
- Display orders table with status badges
- Display email log table

**Day 19: Order Router + Review Flow**
- Write `order_router.py` — GET /orders, POST /orders/complete-review
- Build "Needs Review" section with complete form
- Test: flag an order → staff completes missing field → order status updates to "new"

**Day 20–21: Final Testing + Polish**
- Test with 10 different real-format PO emails
- Test on phone browser via local network IP
- Fix any UI issues
- Clean up all code
- Write README for V1

**Week 3 Milestone:** V1 is fully complete. Login works. Dashboard works. Full email-to-order pipeline runs on button click. Works on phone browser via local network.

---

## 12. Testing Checklist

### Email Reading Tests
- [ ] System fetches unread emails correctly
- [ ] Already-processed emails are not reprocessed
- [ ] System handles Gmail API token expiry gracefully

### Filter Tests
- [ ] Email with "PO" in subject → processed
- [ ] Email with "purchase order" (lowercase) → processed
- [ ] Email with "Meeting tomorrow" → skipped
- [ ] Email with no subject → skipped
- [ ] Result logged in email_log correctly

### Attachment Tests
- [ ] PDF with table format PO → text extracted correctly
- [ ] DOCX format PO → text extracted correctly
- [ ] Email with no attachment → email body used
- [ ] Email with unsupported attachment (.xlsx) → email body used, warning logged

### AI Extraction Tests
- [ ] Clean PO email → all fields extracted correctly
- [ ] Casual customer email ("please send 500 caps by next month") → fields extracted
- [ ] PO with quantity in words ("five thousand pieces") → extracted as integer 5000
- [ ] Missing delivery date → field is null, order flagged for review
- [ ] New customer → customer record created in DB
- [ ] Repeat customer → existing customer record linked, no duplicate created

### Dashboard Tests
- [ ] Login with correct credentials → dashboard loads
- [ ] Login with wrong password → error message shown
- [ ] "Check Emails" button → spinner shows → results appear
- [ ] Flagged order → complete review form → order approved
- [ ] Dashboard loads on phone browser via local IP

---

## 13. How V1 Connects to V2

V1 ends with orders in the database with status = `new`.

V2 picks up from here. It reads all orders with status `new`, checks inventory, schedules production, and updates status to `scheduled` then `in_production`.

The V1 tables (`orders`, `customers`, `email_log`, `users`) are used directly by V2 and V3. In the complete project, other schema tables are pre-defined from the start and become active as later modules are connected.

The `orders.status` field is the handoff point between all 3 versions:
```
V1 creates order → status = "new"
V2 picks up → status = "scheduled" → "in_production" → "completed"
V3 picks up → status = "dispatched"
```

---

## 14. Resume Value

### What V1 Demonstrates
- Gmail API integration with OAuth2 (industry skill)
- Local LLM deployment and prompt engineering
- Intelligent document parsing (PDF + DOCX)
- End-to-end agent pipeline design
- FastAPI backend development
- PostgreSQL database design
- Role-based authentication

### Resume Description for V1

```
PlantMind AI — V1: Smart Order Intake System
Python · FastAPI · Mistral 7B · Ollama · Gmail API · PostgreSQL · PyMuPDF

• Built an agentic AI system that automatically reads customer purchase 
  order emails, parses PDF/DOCX attachments, and extracts structured order 
  data using a locally-run Mistral 7B language model
• Implemented intelligent email filtering to process only relevant 
  business emails, ignoring all irrelevant inbox noise
• Designed a PostgreSQL schema and automated order creation pipeline 
  eliminating all manual data entry for factory order intake
• Built a role-based web dashboard accessible across local network 
  enabling office staff to trigger processing and review all orders
```

---

*V1 — Smart Order Intake | Part of PlantMind AI*
