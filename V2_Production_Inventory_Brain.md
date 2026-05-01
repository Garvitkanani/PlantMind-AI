# 🏭 PlantMind AI — Version 2
## Production & Inventory Brain
### Standalone Project | Builds into PlantMind AI Final

**Version:** 2.0  
**Module:** Inventory Monitoring + Auto Reorder + Production Scheduling + Progress Tracking  
**Timeline:** 5 Weeks  
**Position in Full Project:** V2 of 3 — Core Intelligence Layer  
**Depends On:** V1 database (orders, customers, users tables)

---

## 📌 Table of Contents
1. [What V2 Is](#1-what-v2-is)
2. [Problem This Solves](#2-problem-this-solves)
3. [System Flow](#3-system-flow)
4. [Agents in V2](#4-agents-in-v2)
5. [Inventory Logic](#5-inventory-logic)
6. [Reorder Email Logic](#6-reorder-email-logic)
7. [Production Scheduling Logic](#7-production-scheduling-logic)
8. [Production Tracking Logic](#8-production-tracking-logic)
9. [Database Schema — V2 Tables](#9-database-schema--v2-tables)
10. [Dashboards — Supervisor & Store](#10-dashboards--supervisor--store)
11. [Tech Stack](#11-tech-stack)
12. [Folder Structure](#12-folder-structure)
13. [Week-by-Week Plan](#13-week-by-week-plan)
14. [Testing Checklist](#14-testing-checklist)
15. [How V2 Connects to V3](#15-how-v2-connects-to-v3)
16. [Resume Value](#16-resume-value)

---

## 1. What V2 Is

V2 is the **operational brain of PlantMind AI**. It takes orders created by V1 and drives them through the entire production process — from checking whether raw materials are available, automatically reordering from suppliers if not, scheduling the order on the correct injection moulding machine, and tracking production progress as the floor supervisor updates piece counts.

V2 is the most complex module. It contains the most agents, the most database tables, and the most business logic. It is where the factory's actual operations are digitized and automated.

When V2 is complete, the factory has full visibility into what is being produced, on which machine, at what progress, and whether any delays are expected — all in real time, through a browser.

---

## 2. Problem This Solves

### Inventory Problems (Before V2)
- Store person manually checks stock by physically counting or looking at a notebook
- No one knows if there is enough material for a new order until production is about to start
- Supplier reorders happen late — causing production stoppages
- No history of what was ordered from which supplier, when

### Production Problems (Before V2)
- No one knows which machine is running which order
- Production timelines are estimated verbally — no tracking
- Owner has no way to know if an order will be delivered on time
- Delays are discovered only when the customer calls asking where their order is
- Progress tracking happens on paper or not at all

### After V2
- System checks material availability the moment an order comes in
- If stock is low, reorder email is sent to supplier automatically
- Every order is assigned to a specific machine with a calculated timeline
- Floor supervisor updates progress via browser — no app needed
- System detects delays automatically and alerts owner immediately

---

## 3. System Flow

```
INPUT: Order in database with status = "new"
(Created by V1 Email Intake System)
                    │
                    ▼
┌───────────────────────────────────────────────┐
│          INVENTORY CHECK AGENT                │
│                                               │
│  1. Reads order: product_name + quantity      │
│  2. Looks up product in products table        │
│  3. Gets material_required_per_unit_kg        │
│  4. Calculates total material needed:         │
│     total = quantity × material_per_unit      │
│  5. Checks raw_materials table for            │
│     current_stock_kg of that material         │
│  6. Compares: current_stock vs total_needed   │
└──────────────┬────────────────────────────────┘
               │
      ┌─────────┴──────────┐
      │                    │
 SUFFICIENT           INSUFFICIENT
      │                    │
      │                    ▼
      │      ┌─────────────────────────────┐
      │      │      REORDER AGENT          │
      │      │                             │
      │      │  Phi-3 Mini Q4_K_M          │
      │      │                             │
      │      │  1. Calculates reorder qty: │
      │      │     reorder_quantity_kg     │
      │      │     from raw_materials table│
      │      │  2. Drafts reorder email    │
      │      │  3. Sends to supplier via   │
      │      │     Gmail SMTP              │
      │      │  4. Logs in reorder_log     │
      │      │  5. Flags order:            │
      │      │     "awaiting_material"     │
      │      └──────────────┬──────────────┘
      │                     │
      │              Material ordered,
      │              Store person updates
      │              stock on delivery
      │                     │
      └──────────┬──────────┘
                 │
         STOCK CONFIRMED
                 │
                 ▼
┌───────────────────────────────────────────────┐
│        PRODUCTION SCHEDULER AGENT             │
│                                               │
│  1. Reads all machines from machines table    │
│  2. Finds machine with status = "available"   │
│  3. If none available: finds machine with     │
│     earliest estimated completion             │
│  4. Calculates production timeline:           │
│     total_seconds = qty × cycle_time_seconds  │
│     estimated_hours = total_seconds / 3600    │
│  5. Sets estimated_start and estimated_end    │
│  6. Creates record in production_schedule     │
│  7. Updates machine status = "running"        │
│  8. Updates order status = "scheduled"        │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│         FLOOR SUPERVISOR DASHBOARD            │
│                                               │
│  Shows scheduled order on supervisor screen   │
│  Machine assignment visible                   │
│  Supervisor manually starts production        │
│  Updates order status = "in_production"       │
└──────────────────────┬────────────────────────┘
                       │
           Supervisor updates progress
           periodically via dashboard
                       │
                       ▼
┌───────────────────────────────────────────────┐
│        PRODUCTION TRACKER AGENT               │
│                                               │
│  On each supervisor update:                   │
│  1. Receives: order_id + pieces_completed     │
│  2. Saves to production_progress table        │
│  3. Calculates completion %:                  │
│     pct = pieces_completed / total_quantity   │
│  4. Recalculates ETA based on current pace:   │
│     remaining = total - completed             │
│     pace = completed / hours_elapsed          │
│     new_eta = now + (remaining / pace)        │
│  5. Compares new_eta vs required_delivery_date│
│                                               │
│  IF new_eta > required_delivery_date:         │
│     → DELAY DETECTED                         │
│     → Sends delay alert email to owner        │
│     → Logs delay in order_status_log          │
│                                               │
│  IF pieces_completed = total_quantity:        │
│     → PRODUCTION COMPLETE                    │
│     → Updates order status = "completed"      │
│     → Updates machine status = "available"    │
│     → V3 Dispatch Agent picks up from here    │
└───────────────────────────────────────────────┘
```

---

## 4. Agents in V2

### Agent 1 — Inventory Check Agent
**File:** `agents/inventory_check_agent.py`

**Responsibility:**
- Read order details from database
- Look up product in products table
- Calculate total raw material needed
- Compare against current stock
- Return: SUFFICIENT or INSUFFICIENT with amounts

**Trigger:** Called automatically when new order appears with status = `new`
**Polling:** V2 checks for new orders every 60 seconds using a background task in FastAPI

**Key Calculation:**
```
total_material_needed_kg = order.quantity × product.material_required_per_unit_kg
available_stock_kg = raw_materials.current_stock_kg
buffer_stock_kg = raw_materials.reorder_level_kg

if available_stock_kg - total_material_needed_kg < buffer_stock_kg:
    → INSUFFICIENT (reorder needed even if technically enough for this order)
else:
    → SUFFICIENT
```

The buffer check ensures the factory never runs completely empty even after fulfilling an order.

---

### Agent 2 — Reorder Agent
**File:** `agents/reorder_agent.py`

**AI Model:** Phi-3 Mini Q4_K_M (fast, lightweight — email drafting is simple)

**Responsibility:**
- Determine reorder quantity from raw_materials table
- Use Phi-3 Mini to draft a professional reorder email
- Send email via Gmail SMTP to supplier
- Log reorder in reorder_log table
- Update order status to `awaiting_material` if triggered by order

**Reorder Email Content:**
Phi-3 Mini receives the material name, quantity to order, supplier name, and factory name, then drafts a short, professional email. The prompt is simple and structured so Phi-3 handles it well at high speed.

**When Reorder Is Triggered:**
- Inventory check finds stock insufficient for an order (order-triggered reorder)
- Store person manually triggers reorder from Store Dashboard (manual reorder)
- Both cases use the same Reorder Agent

---

### Agent 3 — Production Scheduler Agent
**File:** `agents/production_scheduler_agent.py`

**Responsibility:**
- Find best available machine for the order
- Calculate production timeline using machine cycle time
- Create production_schedule record
- Update machine and order status

**Machine Selection Logic:**
```
Step 1: Find all machines with status = "available"
Step 2: If one or more available → pick the one with lowest machine_id (oldest, most used = most familiar)
Step 3: If no machine available → find machine with earliest estimated_end in production_schedule
Step 4: Schedule this order to start immediately after that machine finishes
```

**Timeline Calculation:**
```
total_pieces = order.quantity
cycle_time_per_piece = product.machine_cycle_time_seconds
total_seconds = total_pieces × cycle_time_per_piece
total_hours = total_seconds / 3600
estimated_end = estimated_start + total_hours (in datetime)
```

This gives a realistic machine-based timeline, not a guessed date.

---

### Agent 4 — Production Tracker Agent
**File:** `agents/production_tracker_agent.py`

**Responsibility:**
- Receive progress update from floor supervisor
- Save to production_progress table
- Recalculate completion percentage
- Recalculate ETA based on actual production pace
- Detect delays
- Send delay alert if needed (Phi-3 Mini)
- Detect completion and trigger handoff to V3

**Pace-Based ETA Recalculation:**
Instead of using cycle time (which may not match real world), the agent uses actual measured pace from supervisor updates. This makes ETA increasingly accurate as production progresses.

```
hours_elapsed = (now - schedule.actual_start).total_seconds() / 3600
pieces_per_hour = pieces_completed / hours_elapsed
pieces_remaining = total_pieces - pieces_completed
hours_remaining = pieces_remaining / pieces_per_hour
new_eta = now + timedelta(hours=hours_remaining)
```

**Delay Alert Email:**
Sent by Phi-3 Mini to owner email. Contains: order number, customer name, product, original deadline, new estimated completion date, pieces done so far.

---

## 5. Inventory Logic

### Product-Material Mapping
Each product in the factory uses a specific raw material (plastic granule type). This mapping is stored in the `product_material_mapping` table and set up manually once during system setup.

**Example Mappings:**
| Product | Material | Kg per 1000 pieces |
|---------|----------|-------------------|
| HDPE Cap 50mm | HDPE Granules | 12 kg |
| PP Container 500ml | PP Granules | 18 kg |
| PVC Pipe Fitting | PVC Compound | 25 kg |

### Stock Level Indicators (Dashboard Color Codes)
| Level | Condition | Color |
|-------|-----------|-------|
| Good | current_stock > reorder_level × 2 | Green |
| Low | current_stock between reorder_level and reorder_level × 2 | Yellow |
| Critical | current_stock < reorder_level | Red — auto reorder triggered |

### Stock Update by Store Person
When a material delivery arrives, store person opens Store Dashboard, selects material, enters quantity received. System adds it to current_stock_kg. Reorder status updated to "delivered" if it was pending.

---

## 6. Reorder Email Logic

### Prompt Sent to Phi-3 Mini
```
You are an assistant for a plastic injection moulding factory.
Write a short, professional email to a supplier requesting material.
Return only the email body text. No subject line. No extra explanation.

Details:
- Factory Name: [from .env]
- Supplier Name: [from suppliers table]
- Material Name: [from raw_materials table]
- Quantity to Order: [reorder_quantity_kg] kg
- Urgency: [normal / urgent based on whether order is waiting]
```

### Example Generated Email
```
Dear [Supplier Name],

We hope this message finds you well.

We would like to place an order for [X] kg of [Material Name] 
at your earliest convenience. Please confirm availability and 
expected delivery timeline.

Kindly send the invoice and dispatch details to this email address.

Thank you for your continued support.

Best regards,
[Factory Name]
```

### Email Sent Via
Gmail SMTP using `smtplib` in Python. Uses App Password from Gmail settings (not OAuth for sending — simpler and reliable).

---

## 7. Production Scheduling Logic

### Machine Status Values
- `available` — No order assigned, ready for new job
- `running` — Currently processing an order
- `maintenance` — Under maintenance, not available for scheduling

### Schedule Creation
When an order is scheduled:
1. `production_schedule` record created with `estimated_start` and `estimated_end`
2. Machine `status` updated to `running`
3. Machine `current_order_id` updated to this order
4. Order `status` updated to `scheduled`
5. Floor supervisor sees new entry on their dashboard

### When Supervisor Starts Production
Supervisor clicks "Start Production" on their dashboard for a scheduled order. This:
1. Sets `production_schedule.actual_start` to current time
2. Updates order status to `in_production`
3. Enables the "Update Progress" form for that order

### Multiple Machines
The factory may have 3–5 injection moulding machines. Each runs independently. The scheduler handles all of them. Multiple orders can be in production simultaneously on different machines.

---

## 8. Production Tracking Logic

### Progress Update Frequency
Floor supervisor updates progress as they see fit — once per shift, or multiple times per day. There is no forced frequency. Each update saves a new row in `production_progress` with timestamp and pieces completed (total so far, not just this session).

### Completion Detection
```
if pieces_completed >= order.quantity:
    → Mark production_schedule.actual_end = now
    → Update order.status = "completed"
    → Update machine.status = "available"
    → machine.current_order_id = null
    → V3 Dispatch Agent triggered (in final version)
    → In V2 standalone: status just shows "completed" on dashboard
```

### Delay Detection
Runs on every supervisor progress update:
```
if new_eta > order.required_delivery_date:
    and delay_alert_already_sent = False:
        → Send delay alert email to owner
        → Set delay_alert_sent = True in production_schedule
        → Log in order_status_log
```

One delay alert per order maximum — system does not spam owner with repeated alerts for the same order.

---

## 9. Database Schema — V2 Tables

V2 adds 6 new tables. V1 tables (orders, customers, email_log, users) are used as-is.

---

### Table 5: raw_materials
```
material_id              SERIAL PRIMARY KEY
name                     VARCHAR(200) NOT NULL
type                     VARCHAR(100)
current_stock_kg         DECIMAL(10,2) NOT NULL DEFAULT 0
reorder_level_kg         DECIMAL(10,2) NOT NULL
reorder_quantity_kg      DECIMAL(10,2) NOT NULL
unit_price_per_kg        DECIMAL(10,2)
supplier_id              INTEGER REFERENCES suppliers(supplier_id)
last_updated             TIMESTAMP DEFAULT NOW()
```

---

### Table 6: suppliers
```
supplier_id              SERIAL PRIMARY KEY
name                     VARCHAR(200) NOT NULL
email                    VARCHAR(200) NOT NULL
phone                    VARCHAR(20)
material_supplied        VARCHAR(200)
address                  TEXT
created_at               TIMESTAMP DEFAULT NOW()
```

---

### Table 7: products
Maps product names to their material requirements and machine cycle times.
```
product_id               SERIAL PRIMARY KEY
name                     VARCHAR(300) NOT NULL
description              TEXT
material_id              INTEGER REFERENCES raw_materials(material_id)
material_required_per_unit_kg   DECIMAL(8,4) NOT NULL
machine_cycle_time_seconds      INTEGER NOT NULL
created_at               TIMESTAMP DEFAULT NOW()
```

---

### Table 8: machines
```
machine_id               SERIAL PRIMARY KEY
name                     VARCHAR(100) NOT NULL
status                   VARCHAR(30) DEFAULT 'available'
                         -- available / running / maintenance
current_order_id         INTEGER REFERENCES orders(order_id)
last_maintenance_date    DATE
notes                    TEXT
```

---

### Table 9: production_schedule
```
schedule_id              SERIAL PRIMARY KEY
order_id                 INTEGER REFERENCES orders(order_id)
machine_id               INTEGER REFERENCES machines(machine_id)
estimated_start          TIMESTAMP NOT NULL
estimated_end            TIMESTAMP NOT NULL
actual_start             TIMESTAMP
actual_end               TIMESTAMP
status                   VARCHAR(30) DEFAULT 'scheduled'
                         -- scheduled / in_production / completed / cancelled
delay_alert_sent         BOOLEAN DEFAULT FALSE
created_at               TIMESTAMP DEFAULT NOW()
```

---

### Table 10: production_progress
One row per supervisor update. Cumulative pieces_completed (not delta).
```
progress_id              SERIAL PRIMARY KEY
schedule_id              INTEGER REFERENCES production_schedule(schedule_id)
pieces_completed         INTEGER NOT NULL
total_pieces             INTEGER NOT NULL
completion_percentage    DECIMAL(5,2)
updated_by               INTEGER REFERENCES users(user_id)
updated_at               TIMESTAMP DEFAULT NOW()
notes                    VARCHAR(500)
```

---

### Table 11: reorder_log
```
reorder_id               SERIAL PRIMARY KEY
material_id              INTEGER REFERENCES raw_materials(material_id)
supplier_id              INTEGER REFERENCES suppliers(supplier_id)
triggered_by_order_id    INTEGER REFERENCES orders(order_id)
quantity_ordered_kg      DECIMAL(10,2) NOT NULL
email_sent_at            TIMESTAMP DEFAULT NOW()
status                   VARCHAR(30) DEFAULT 'sent'
                         -- sent / confirmed / delivered / cancelled
delivery_date            DATE
notes                    TEXT
```

---

### Table 12: order_status_log
Full audit trail of every status change on every order.
```
log_id                   SERIAL PRIMARY KEY
order_id                 INTEGER REFERENCES orders(order_id)
old_status               VARCHAR(50)
new_status               VARCHAR(50)
changed_at               TIMESTAMP DEFAULT NOW()
changed_by               VARCHAR(100)
                         -- "system" or username
notes                    TEXT
```

---

## 10. Dashboards — Supervisor & Store

### Floor Supervisor Dashboard

**Access:** Login with supervisor role credentials
**URL:** `http://[PC-IP]:8000` → login → supervisor dashboard

#### Section 1 — My Active Jobs
Table showing all orders currently assigned to machines:

| Order # | Customer | Product | Machine | Pieces Done | Total | % | ETA | Status |
|---------|----------|---------|---------|-------------|-------|---|-----|--------|
| ORD-007 | Raj Polymers | HDPE Cap | Machine 2 | 3,500 | 10,000 | 35% | 14 Jun | On Track |
| ORD-009 | ABC Plastics | Container | Machine 1 | 0 | 5,000 | 0% | 20 Jun | Scheduled |

ETA column shows green if on track, red if delayed.

#### Section 2 — Scheduled (Not Started)
Orders assigned to a machine but not yet started. Supervisor clicks "Start Production" to begin.

#### Section 3 — Update Progress Form
```
Select Order: [Dropdown of in_production orders]
Pieces Completed So Far: [Number input]
Notes (optional): [Text field]
[Submit Update]
```
After submit: table refreshes, new ETA recalculated and shown.

#### Section 4 — Mark Complete
For each in_production order: "Mark as Complete" button.
Supervisor clicks when all pieces are done. System sets actual_end, updates machine to available.

#### Section 5 — Completed Today
Orders marked complete today — for supervisor's reference.

---

### Store Person Dashboard

**Access:** Login with store role credentials

#### Section 1 — Raw Material Stock
| Material | Current Stock (kg) | Reorder Level (kg) | Status | Last Updated |
|---------|-------------------|--------------------|--------|-------------|
| HDPE Granules | 450 kg | 200 kg | 🟢 Good | Today |
| PP Granules | 180 kg | 200 kg | 🔴 Critical | Yesterday |
| PVC Compound | 320 kg | 150 kg | 🟡 Low | 2 days ago |

#### Section 2 — Update Stock (Delivery Received)
```
Material: [Dropdown]
Quantity Received (kg): [Number input]
Supplier: [Auto-filled from material]
Delivery Date: [Date picker — defaults to today]
Notes: [Optional]
[Update Stock]
```

#### Section 3 — Pending Reorders
Reorder emails sent but delivery not yet confirmed.

| Material | Qty Ordered | Supplier | Sent On | Status |
|---------|-------------|----------|---------|--------|
| PP Granules | 500 kg | SK Polymers | Yesterday | Sent |

Store person can mark as "Delivered" when material arrives (same as updating stock — linked).

#### Section 4 — Reorder History
Last 30 reorder records for reference.

---

## 11. Tech Stack

All tools same as V1 plus additions:

| Component | Technology | Purpose |
|-----------|-----------|---------|
| AI Model (fast tasks) | Phi-3 Mini Q4_K_M | Reorder emails, delay alerts |
| AI Model (complex) | Mistral 7B Q4_K_M | Only if needed for edge cases |
| Background Tasks | FastAPI BackgroundTasks | Auto-check new orders every 60 seconds |
| Email Sending | smtplib (Python stdlib) | Send reorder + delay alert emails via Gmail SMTP |
| All V1 tech | Same | No changes to V1 stack |

### Gmail SMTP Setup (for sending emails)
Uses Gmail App Password (not OAuth). Set up once:
1. Google Account → Security → 2-Step Verification → App Passwords
2. Generate password for "Mail"
3. Store in `.env` as `GMAIL_APP_PASSWORD`

This is separate from Gmail API (used for reading). Reading uses OAuth2. Sending uses SMTP + App Password.

---

## 12. Folder Structure

V2 adds to V1 folder structure. New files only shown:

```
plantmind-v2/
│
├── (all V1 files remain unchanged)
│
├── agents/
│   ├── (V1 agents unchanged)
│   ├── inventory_check_agent.py      # Stock vs order requirement check
│   ├── reorder_agent.py              # Phi-3 Mini drafts + sends reorder email
│   ├── production_scheduler_agent.py # Machine assignment + timeline calculation
│   └── production_tracker_agent.py   # Progress tracking, ETA, delay detection
│
├── models/
│   ├── ollama_mistral.py             # (from V1, unchanged)
│   └── ollama_phi3.py                # NEW — Phi-3 Mini Q4_K_M interface
│
├── database/
│   └── queries/
│       ├── (V1 queries unchanged)
│       ├── inventory_queries.py      # Stock read/update, reorder log
│       ├── production_queries.py     # Schedule, progress, machine status
│       └── supplier_queries.py       # Supplier lookup
│
├── routers/
│   ├── (V1 routers unchanged)
│   ├── inventory_router.py           # GET /inventory, POST /inventory/update-stock
│   └── production_router.py          # GET /production, POST /production/update-progress
│                                     # POST /production/start, POST /production/complete
│
├── email/
│   ├── gmail_reader.py               # (from V1, unchanged)
│   └── gmail_sender.py               # NEW — smtplib SMTP sending
│
├── templates/
│   ├── (V1 templates unchanged)
│   ├── supervisor_dashboard.html
│   └── store_dashboard.html
│
└── static/
    └── js/
        ├── office_dashboard.js       # (from V1)
        ├── supervisor_dashboard.js
        └── store_dashboard.js
```

---

## 13. Week-by-Week Plan

### Week 4 — Inventory System

**Day 22–23: Database Setup for V2**
- Add V2 tables to PostgreSQL: raw_materials, suppliers, products, machines, production_schedule, production_progress, reorder_log, order_status_log
- Seed test data: 3 machines, 4 materials, 3 suppliers, 3 products with material mappings
- Write inventory_queries.py: get stock, update stock, get material for product

**Day 24–25: Inventory Check Agent**
- Write `inventory_check_agent.py`
- Implement calculation logic (quantity × material per unit)
- Add buffer check against reorder level
- Test: create test order → agent correctly identifies sufficient / insufficient
- Add background task in FastAPI to poll for new orders every 60 seconds

**Day 26–28: Reorder Agent + Gmail SMTP**
- Write `gmail_sender.py` using smtplib + App Password
- Test: send a plain text email to yourself via Gmail SMTP
- Write `ollama_phi3.py` — Phi-3 Mini interface
- Write `reorder_agent.py` — prompt Phi-3, get email body, send via SMTP
- Test: set stock below reorder level → create order → reorder email auto-sent to supplier

**Week 4 Milestone:** Inventory check works. Reorder email sent automatically when stock is low.

---

### Week 5 — Production Scheduling

**Day 29–30: Production Scheduler Agent**
- Write `production_scheduler_agent.py`
- Machine availability check logic
- Timeline calculation using cycle time
- Create production_schedule record
- Update machine and order status

**Day 31–32: Supervisor Dashboard**
- Write `supervisor_dashboard.html`
- Write `supervisor_dashboard.js`
- Write `production_router.py` — GET /production/my-jobs, POST /production/start
- Display scheduled orders with machine assignment
- "Start Production" button → sets actual_start, updates status

**Day 33: Full Scheduling Flow Test**
- Create 3 test orders → all go through inventory check → get scheduled
- One order goes to Machine 1, next to Machine 2, third waits
- All visible on supervisor dashboard correctly

**Week 5 Milestone:** Production scheduling works. All orders get machine assignments with calculated timelines.

---

### Week 6 — Production Tracking + Store Dashboard

**Day 34–35: Production Tracker Agent**
- Write `production_tracker_agent.py`
- Progress save to DB
- Completion % calculation
- ETA recalculation from actual pace
- Delay detection logic
- Write delay alert prompt for Phi-3 Mini + send via Gmail SMTP

**Day 36–37: Store Person Dashboard**
- Write `store_dashboard.html` and JS
- Stock table with color indicators
- Stock update form
- Pending reorders section
- Write `inventory_router.py` — POST /inventory/update-stock, GET /inventory/reorders

**Day 38: Integration Test**
- Full flow: email in (V1) → order created → inventory checked → reorder sent → scheduled → supervisor starts → updates progress → delay detected → owner gets alert → supervisor marks complete

**Week 6 Milestone:** Full V2 pipeline works. Tracker agent detects delays and alerts owner.

---

### Week 7 — Store Dashboard Polish + Edge Cases

**Day 39–40: Edge Case Handling**
- What if no machine is available? (schedule to next available slot)
- What if same material needed by 2 orders simultaneously? (check combined)
- What if supervisor enters progress higher than total? (validation)
- What if Phi-3 Mini fails? (fallback to template email without AI)

**Day 41–42: V1 + V2 Integration Test**
- Run V1 and V2 together (same database, same FastAPI app)
- Full pipeline from email → order → inventory → schedule → tracking
- Fix any integration bugs

**Day 43: Final Polish**
- Clean up all dashboards
- Test on phone browser
- Write README for V2

**Week 7 Milestone:** V2 is complete and integrated with V1. All edge cases handled. Tested end-to-end.

---

## 14. Testing Checklist

### Inventory Tests
- [ ] Order for 10,000 caps needing 120 kg → stock is 150 kg → SUFFICIENT
- [ ] Order for 10,000 caps needing 120 kg → stock is 80 kg → INSUFFICIENT → reorder triggered
- [ ] Reorder email received in supplier inbox with correct material and quantity
- [ ] Reorder logged in reorder_log table correctly
- [ ] Store person updates stock after delivery → stock level reflects correctly
- [ ] Stock level indicator shows correct color (green/yellow/red) on dashboard

### Scheduling Tests
- [ ] Machine 1 available → order assigned to Machine 1
- [ ] All machines running → order queued after earliest finishing machine
- [ ] Timeline calculated correctly (1000 pieces × 45 sec = 12.5 hours)
- [ ] Order status updates from new → scheduled correctly
- [ ] Machine status updates to running when order assigned

### Tracking Tests
- [ ] Supervisor updates progress → pieces_completed saved
- [ ] Completion % calculated correctly
- [ ] ETA recalculated based on actual pace (not cycle time)
- [ ] ETA exceeds deadline → delay alert email sent to owner
- [ ] Delay alert sent only once per order (not repeatedly)
- [ ] Supervisor marks complete → machine becomes available → order status = completed

### Dashboard Tests
- [ ] Supervisor dashboard shows all in_production orders
- [ ] ETA color shows red when delayed
- [ ] Store dashboard shows correct stock colors
- [ ] Stock update form adds quantity correctly to existing stock
- [ ] Pending reorders section shows correct status

---

## 15. How V2 Connects to V3

V2 ends with orders having status = `completed` in the database.

V3 picks up from here. The Dispatch Agent in V3 watches for orders with status = `completed` and automatically sends a dispatch confirmation email to the customer, then updates status to `dispatched`.

The handoff is clean and database-driven. V3 does not need to know anything about how the order was produced — it only cares that production is done.

Additionally, V3's Daily MIS Report Agent reads data from all V2 tables (machines, production_schedule, raw_materials, reorder_log) to build the owner's morning summary.

---

## 16. Resume Value

### What V2 Demonstrates
- Multi-agent orchestration with conditional branching
- Business logic implementation (inventory calculations, scheduling algorithms)
- Background task automation in FastAPI
- Gmail SMTP email automation
- Local LLM use for practical email generation (Phi-3 Mini)
- Real-time dashboard with live data updates
- ETA calculation using pace-based algorithms
- Delay detection and automated alerting

### Resume Description for V2

```
PlantMind AI — V2: Production & Inventory Brain
Python · FastAPI · Phi-3 Mini · Ollama · PostgreSQL · Gmail SMTP

• Built intelligent inventory monitoring system that calculates 
  material requirements per order and triggers automated supplier 
  reorder emails using Phi-3 Mini LLM when stock falls below threshold
• Designed production scheduling algorithm that assigns orders to 
  injection moulding machines based on availability and calculates 
  realistic timelines using machine cycle time data
• Implemented pace-based ETA recalculation system that dynamically 
  updates delivery estimates from floor supervisor progress inputs
• Built automated delay detection agent that alerts factory owner 
  via email when production pace indicates deadline will be missed
• Developed role-specific dashboards for Floor Supervisor and Store 
  Person with real-time production visibility across local network
```

---

*V2 — Production & Inventory Brain | Part of PlantMind AI*
