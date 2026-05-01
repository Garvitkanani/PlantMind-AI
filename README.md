# 🤖 PlantMind AI

**Agentic AI System for Injection Moulding Factory Automation**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791.svg)](https://www.postgresql.org/)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20AI-black.svg)](https://ollama.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 🌟 Overview

PlantMind AI is a **fully local, multi-agent AI system** that automates end-to-end operations of an injection moulding manufacturing factory. From reading customer order emails to scheduling production and sending daily reports - everything runs locally with zero cloud dependency.

### The Problem We Solve

| Before | After |
|--------|-------|
| Manual email reading & data entry | Automated AI-powered order extraction |
| No inventory visibility | Real-time material tracking with auto-reorder |
| Production tracking on paper | Live dashboard with progress updates |
| Manual dispatch notifications | Automatic customer emails on completion |
| No daily reports | AI-generated morning briefing at 9 AM |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLANTMIND AI SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│  V1: Order Intake          V2: Production & Inventory           │
│  ─────────────────         ────────────────────────────         │
│  • Email Reader            • Inventory Check Agent              │
│  • Email Filter            • Auto Reorder Agent                 │
│  • Attachment Parser       • Production Scheduler               │
│  • Order Extraction        • Production Tracker                 │
│                                                                 │
│  V3: Dispatch & Reporting                                       │
│  ──────────────────────────                                     │
│  • Dispatch Watcher        • MIS Report Agent                   │
│  • Dispatch Agent          • Data Collector                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

### V1 - Smart Order Intake
- 📧 Gmail OAuth2 integration for automatic email scanning
- 🔍 Intelligent email filtering (PO, Order, RFQ, Enquiry)
- 📎 PDF & DOCX attachment parsing
- 🤖 AI-powered order extraction (Mistral 7B)
- ✅ Automatic customer creation
- ⚠️ Manual review for incomplete extractions

### V2 - Production & Inventory Brain
- 📦 Real-time raw material stock tracking
- 🔄 Automatic supplier reordering when stock is low
- ⚙️ Intelligent production scheduling across machines
- 📊 Live production progress tracking
- ⚠️ Delay detection with automatic owner alerts

### V3 - Dispatch & Reporting Engine
- 🚚 Automatic dispatch confirmation emails to customers
- 📈 Daily MIS report at 9:00 AM (AI-generated)
- 📊 Owner dashboard with factory-wide metrics
- 📝 Complete audit trail of all order status changes

### Role-Based Dashboards
| Role | Dashboard | Access |
|------|------------|--------|
| Owner | Full factory view | `/dashboard/owner` |
| Office Staff | Order management | `/dashboard` |
| Supervisor | Production floor | `/api/v2/supervisor-dashboard` |
| Store | Inventory management | `/api/v2/store-dashboard` |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python + FastAPI |
| **Database** | PostgreSQL + SQLAlchemy |
| **AI Runtime** | Ollama |
| **AI Models** | Mistral 7B Q4_K_M, Phi-3 Mini |
| **Email** | Gmail API (OAuth2) + SMTP |
| **Scheduler** | APScheduler |
| **Frontend** | HTML5 + CSS3 + Vanilla JS |
| **Auth** | bcrypt + Session middleware |

---

## 📁 Project Structure

```
plantmind-ai/
├── src/
│   ├── agents/           # AI agents for all tasks
│   ├── processors/       # Pipeline orchestrators
│   ├── routes/           # API endpoints
│   ├── database/         # Models & connection
│   ├── models/          # Ollama integrations
│   ├── gmail/           # Email reading & sending
│   ├── parsers/         # PDF/DOCX parsing
│   ├── templates/       # HTML dashboards
│   ├── static/          # CSS & JavaScript
│   └── scheduler.py     # Background tasks
├── tests/               # Test suite
├── scripts/             # Deployment scripts
├── config/             # Configuration templates
├── requirements.txt    # Python dependencies
├── schema.sql          # Database schema
└── README.md           # This file
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Ollama with models installed

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/PlantMind-AI.git
cd PlantMind-AI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings:
# - DATABASE_URL (PostgreSQL connection)
# - GMAIL credentials
# - OLLAMA settings
```

### Database Setup

```bash
# Create database
psql -U postgres -c "CREATE DATABASE plantmind;"

# Initialize tables (auto-creates users)
python -c "from src.database import init_db; init_db()"

# Pull AI models
ollama pull mistral:7b-instruct-q4_K_M
ollama pull phi3:mini
```

### Run the Application

```bash
# Start server
python src/main.py
# or
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** and login with default credentials:
- **office** / **office123**
- **owner** / **owner123**
- **supervisor** / **supervisor123**
- **store** / **store123**

> ⚠️ **Important**: Change default passwords in production!

---

## 📋 Default Users

| Username | Password | Role |
|----------|-----------|------|
| office | office123 | Order intake |
| owner | owner123 | Full dashboard + reports |
| supervisor | supervisor123 | Production tracking |
| store | store123 | Inventory management |

---

## 🔒 Security

- All secrets stored in `.env` (never committed)
- Role-based access control
- Session management with secure cookies
- Rate limiting on login
- Input sanitization on all outputs
- CSP security headers enabled
- bcrypt password hashing

---

## 📊 Database Schema

16 tables covering all factory operations:
- `users` - Authentication
- `customers` - Customer directory
- `orders` - Order tracking
- `products` - Product catalog
- `machines` - Machine management
- `raw_materials` - Inventory
- `production_schedule` - Production planning
- `production_progress` - Floor updates
- `reorder_log` - Supplier orders
- And more...

---

## 🎯 Key Highlights

- ✅ **100% Local** - No cloud, no subscriptions, no API costs
- ✅ **Multi-Agent** - 8 specialized AI agents working together
- ✅ **Production Ready** - Real deployment in manufacturing context
- ✅ **Resume Worthy** - Demonstrates advanced AI, backend, and system integration skills
- ✅ **End-to-End** - Complete factory automation in one system

---

## 📝 License

MIT License - See [LICENSE](LICENSE) for details.

---

## 👤 Author

**Garvit** - BTech AI & Data Science, Year 2

Built for real deployment in an injection moulding factory + portfolio showcase.

---

*Transforming factory chaos into intelligent automation with AI.*