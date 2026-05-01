# PlantMind AI V1 - Smart Order Intake

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-336791.svg)](https://www.postgresql.org/)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-black.svg)](https://ollama.com/)
[![Status](https://img.shields.io/badge/V1-Production%20Ready-success.svg)]()

PlantMind AI V1 is a **local-first agentic system** for injection moulding factories that automates order intake from Gmail emails and PO attachments.  
It converts messy email content into structured orders with an office dashboard and manual review safety net.

---

## Why This Project Stands Out

- Solves a real manufacturing workflow pain point end-to-end.
- Uses **local LLM inference** (Ollama + Phi-3 Mini), not paid cloud APIs.
- Includes production-minded features: auth, logging, flagged review, export, search, UX shortcuts.
- Built to be deployable in a real SME factory office on local infrastructure.

---

## Core Features

### Intake Pipeline
- Gmail OAuth2 integration for unread inbox scanning.
- Intelligent email relevance filtering (PO/order/RFQ/enquiry intent).
- PDF and DOCX attachment parsing.
- AI extraction to structured JSON: customer, product, quantity, delivery date, instructions.
- Automatic DB persistence and processing audit log.

### Office Dashboard
- Manual trigger processing workflow.
- Flagged orders review workflow.
- Search/filter on orders.
- Email log with click-to-preview modal.
- Processing progress indicator and success toasts.
- Auto-refresh toggle.
- Dark mode toggle.
- Keyboard shortcuts:
  - `Ctrl + F` focus search
  - `R` refresh dashboard data
  - `P` process emails
- Excel export (`.xlsx`) for orders.

---

## Architecture

```text
Office Dashboard
    ->
Email Reader Agent (Gmail API)
    ->
Email Filter Agent
    ->
Attachment Parser (PDF/DOCX)
    ->
Order Extraction Agent (Phi-3 Mini via Ollama)
    ->
PostgreSQL (orders/customers/email_log/users)
    ->
Dashboard + Review Flow + Export
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI |
| Database | PostgreSQL + SQLAlchemy |
| AI Runtime | Ollama |
| AI Model | `phi3:mini` |
| Email | Gmail API OAuth2 |
| Parsing | PyMuPDF, python-docx |
| Auth | bcrypt + session middleware |
| Frontend | Jinja2 + Tailwind + Vanilla JS |
| Export | openpyxl |

---

## Project Structure

```text
src/
  agents/         # Gmail read, filter, extraction orchestrators
  parsers/        # Attachment parsing
  processors/     # End-to-end V1 pipeline logic
  routes/         # FastAPI routes and dashboard endpoints
  database/       # Models, connection, init bootstrap
  templates/      # Login + office dashboard
```

---

## Quick Start (Windows / Local)

### 1) Create venv and install dependencies

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Configure `.env`

Copy `.env.example` to `.env` and set:

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/plantmind
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_RECYCLE_SECONDS=1800
APP_SECRET_KEY=change-this-to-a-long-random-value
GMAIL_CLIENT_SECRET=config/credentials.json
GMAIL_TOKEN_PATH=config/token.json
OLLAMA_API_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=phi3:mini
APP_HOST=0.0.0.0
APP_PORT=8000
SESSION_MAX_AGE_SECONDS=28800
SESSION_COOKIE_NAME=plantmind_session
SESSION_SAME_SITE=lax
SESSION_HTTPS_ONLY=false
LOGIN_ATTEMPT_WINDOW_SECONDS=300
LOGIN_MAX_ATTEMPTS=5
BOOTSTRAP_DEFAULT_USERS=true
DEFAULT_ADMIN_PASSWORD=change-admin-password
DEFAULT_OFFICE_PASSWORD=change-office-password
```

### 3) Prepare services

```powershell
# PostgreSQL: ensure DB exists
psql -U postgres -c "CREATE DATABASE plantmind;"

# Ollama model
ollama pull phi3:mini
```

### 4) Initialize database

```powershell
.\venv\Scripts\python -c "from src.database import init_db; init_db()"
```

### 5) Run app

```powershell
.\venv\Scripts\python -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000/login`.

---

## API Highlights

- `POST /check-emails` -> trigger processing pipeline
- `GET /orders` -> all orders
- `GET /orders/flagged` -> flagged review queue
- `POST /orders/{id}/complete-review` -> resolve flagged order
- `GET /email-log` -> email processing log
- `GET /processing-summary` -> dashboard summary metrics
- `GET /customer-stats` -> quick customer cards
- `GET /orders/export` -> Excel export
- `GET /health/startup` -> detailed readiness report (DB/Ollama/Gmail/scheduler)

---

## Testing

```powershell
.\venv\Scripts\python -m pytest -q
.\venv\Scripts\python -m compileall src
```

---

## Security Notes

- Do not commit `.env`, Gmail credentials, or token files.
- Change bootstrap/default users before production use.
- Use a strong `APP_SECRET_KEY`.
- Dashboard rendering is escaped for untrusted content in email-derived fields.
- Login endpoint includes rate limiting for repeated failures.
- Session cookies are configurable (`SameSite`, max age, HTTPS-only).
- Security headers (CSP, frame deny, nosniff) are enabled by default.
- Database pool settings are configurable for throughput under load.

---

## Demo and Portfolio Assets

- Demo script: `docs/demo_script.md`
- Setup guide: `docs/setup_guide.md`
- Technical overview: `docs/technical_overview.md`
- User manual: `docs/user_manual.md`
- Full V1 product spec: `V1_Smart_Order_Intake.md`

If you are publishing on LinkedIn, record a short walkthrough following `docs/demo_script.md`.

---

## Roadmap

- V2: production scheduling + inventory intelligence.
- V3: dispatch automation + daily MIS reporting.

PlantMind AI V1 is the intake foundation for the full factory intelligence stack.

