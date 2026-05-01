# PlantMind AI — Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Configure Environment (2 minutes)

Open `.env` file and update these required values:

```env
# Database (update password if needed)
DATABASE_URL=postgresql://postgres:password@localhost:5432/plantmind

# Gmail SMTP (REQUIRED for email sending)
GMAIL_SMTP_EMAIL=your-factory-email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx  # 16-char app password

# Factory Owner (REQUIRED for reports)
OWNER_EMAIL=owner@yourfactory.com
FACTORY_NAME=Your Factory Name
```

**Get Gmail App Password:**
1. Go to https://myaccount.google.com/apppasswords
2. Sign in to your factory Gmail account
3. Select "Mail" → "Other (Custom name)" → Type "PlantMind AI"
4. Click "Generate"
5. Copy the 16-character password (looks like: `abcd efgh ijkl mnop`)
6. Paste in `.env` (spaces optional)

---

### Step 2: Install Dependencies (1 minute)

```bash
pip install -r requirements.txt
```

---

### Step 3: Setup AI Model (30 seconds)

```bash
ollama pull phi3:mini
```

Verify it's working:
```bash
ollama list
# Should show: phi3:mini
```

---

### Step 4: Initialize Database (30 seconds)

```bash
python -c "from src.database import init_db; init_db()"
```

You should see:
- "Admin user created successfully"
- "Office user created successfully"
- "Owner user created successfully"
- "Supervisor user created successfully"
- "Store user created successfully"
- "Database initialization completed"

---

### Step 5: Start Application (10 seconds)

```bash
uvicorn src.app:app --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

### Step 6: Access Dashboards

Open browser and go to: **http://localhost:8000**

#### Login Credentials:

| Role | Username | Password | Dashboard |
|------|----------|----------|-----------|
| **Owner** | `owner` | `owner123` | Factory Command Center |
| **Admin** | `admin` | `admin123` | Full System Access |
| **Office** | `office` | `office123` | Order Intake |
| **Supervisor** | `supervisor` | `supervisor123` | Production Floor |
| **Store** | `store` | `store123` | Inventory Management |

---

## 🎮 Test the System

### Test 1: Owner Dashboard
1. Login as `owner` / `owner123`
2. View Factory Health Overview
3. Check Live Orders, Machine Status, Inventory

### Test 2: Office Dashboard
1. Login as `office` / `office123`
2. Click "Check New Emails" (will show "No unread emails" if Gmail not configured)
3. View order statistics

### Test 3: V2 Production Flow
1. Login as `store` / `store123` → `/api/v2/store-dashboard`
2. View inventory levels
3. Try updating stock

### Test 4: V3 MIS Report (Manual Trigger)
```bash
curl -X POST http://localhost:8000/api/v2/process-mis-report
```

Check owner email inbox for the report!

---

## 🔧 Troubleshooting

### Issue: "Gmail SMTP not configured" in logs
**Solution:** Set `GMAIL_SMTP_EMAIL` and `GMAIL_APP_PASSWORD` in `.env`

### Issue: "Ollama model not found"
**Solution:** Run `ollama pull phi3:mini`

### Issue: Database connection failed
**Solution:** 
```bash
# Start PostgreSQL service
# Create database manually:
psql -U postgres -c "CREATE DATABASE plantmind;"
```

### Issue: Port 8000 already in use
**Solution:** Change port in `.env`: `APP_PORT=8001`

---

## 📚 Documentation

- **Full Implementation Details:** `IMPLEMENTATION_SUMMARY.md`
- **Original Plans:** `PlantMind_AI_Project_Plan.md`, `V1_Smart_Order_Intake.md`, `V2_Production_Inventory_Brain.md`, `V3_Dispatch_Reporting_Engine.md`
- **Architecture:** See IMPLEMENTATION_SUMMARY.md for diagrams

---

## ✅ Verification Checklist

Before declaring "ready for production":

- [ ] Gmail App Password created and set in `.env`
- [ ] Owner email address set in `.env`
- [ ] phi3:mini pulled via Ollama
- [ ] Database initialized with all 5 users
- [ ] Application starts without errors
- [ ] Owner dashboard accessible at `/owner-dashboard`
- [ ] Can login as all 4 roles (owner, office, supervisor, store)
- [ ] Manual MIS report test sends email to owner

**If all checked → System is production-ready!**

---

## 🆘 Support

If you encounter issues:

1. Check logs: Look for `ERROR` messages in console
2. Verify `.env` configuration
3. Check database: `psql -U postgres -d plantmind -c "\dt"`
4. Test Ollama: `curl http://localhost:11434/api/tags`

---

**Ready to automate your factory! 🏭🤖**
