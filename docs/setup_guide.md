# PlantMind AI - Setup Guide

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

1. **Python 3.11+**
   - Download from [python.org](https://www.python.org/downloads/)
   - Verify installation: `python --version`

2. **PostgreSQL 15+**
   - Download from [postgresql.org](https://www.postgresql.org/download/)
   - Default credentials: `postgres` / `password` (changeable)

3. **Ollama**
   - Download from [ollama.com](https://ollama.com/download)
   - Pull Phi-3 Mini model: `ollama pull phi3:mini`

---

## 🚀 Installation Steps

### Step 1: Clone Project

Copy the project to your local machine:

```bash
# Navigate to your preferred directory
cd D:\PlantMind AI

# Project structure should be:
# D:\PlantMind AI\
#   ├── src/
#   ├── docs/
#   ├── tests/
#   ├── requirements.txt
#   └── .env.example
```

### Step 2: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Database

1. **Create PostgreSQL Database:**

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create database
CREATE DATABASE plantmind;

-- Create tables (run schema.sql or use init_db)
```

2. **Update Environment Variables:**

```bash
# Copy .env.example to .env
cp .env.example .env

# Edit .env file
```

Edit `D:\PlantMind AI\.env`:

```env
# Database Configuration
DATABASE_URL=postgresql://postgres:password@localhost:5432/plantmind

# Gmail API Configuration
GMAIL_CLIENT_SECRET=config/credentials.json
GMAIL_TOKEN_PATH=config/token.json
GMAIL_SMTP_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-gmail-app-password

# Ollama API Configuration
OLLAMA_API_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=phi3:mini

# App Configuration
APP_SECRET_KEY=your-secure-secret-key-here
APP_HOST=0.0.0.0
APP_PORT=8000
```

### Step 4: Setup Gmail API

1. **Go to Google Cloud Console:**
   - Visit [console.cloud.google.com](https://console.cloud.google.com/)
   - Create a new project named "PlantMind AI"

2. **Enable Gmail API:**
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"

3. **Create OAuth 2.0 Credentials:**
   - Navigate to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Desktop app" as application type
   - Download the JSON file as `credentials.json`

4. **Save credentials.json:**
   ```bash
   # Move credentials.json to config folder
   move C:\path\to\credentials.json D:\PlantMind AI\config\credentials.json
   ```

### Step 5: Setup Ollama

1. **Install Ollama:**
   - Download from [ollama.com/download](https://ollama.com/download)
   - Run the installer

2. **Pull Phi-3 Mini Model:**

```bash
# Start Ollama service (should start automatically on install)
ollama serve

# In a new terminal, pull the model
ollama pull phi3:mini
```

3. **Verify Model:**

```bash
ollama list
# Should show: phi3:mini
```

### Step 6: Initialize Database

```bash
# Activate virtual environment if not already
venv\Scripts\activate

# Navigate to project
cd D:\PlantMind AI

# Initialize database (creates tables and admin user)
python -c "from src.database import init_db; init_db()"
```

You should see:
```
✅ Admin user created successfully!
```

---

## ▶️ Running the Application

### Start Ollama (if not running)

```bash
ollama serve
```

### Start FastAPI Server

```bash
# Activate virtual environment
venv\Scripts\activate

# Navigate to project
cd D:\PlantMind AI

# Run the application
uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
```

### Access the Application

- **Dashboard:** http://localhost:8000/login
- **Startup Readiness:** http://localhost:8000/health/startup
- **Default Credentials:**
  - Username: `admin`
  - Password: `admin123`

---

## 📝 First-Time Setup Checklist

- [ ] Python 3.11+ installed
- [ ] PostgreSQL 15+ installed and running
- [ ] Ollama installed and running
- [ ] Phi-3 Mini model pulled
- [ ] Database `plantmind` created
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file configured
- [ ] `credentials.json` downloaded and placed in `config/` folder
- [ ] Database initialized (`init_db()`)
- [ ] Server running on port 8000
- [ ] Can access http://localhost:8000/login

---

## 🔧 Troubleshooting

### Database Connection Issues

```python
# Test database connection
python -c "from src.database.connection import engine; print(engine.url)"
```

### Gmail Authentication Issues

1. Make sure `credentials.json` is in the `config/` folder
2. Run the email reader test first:
```bash
python -c "from src.agents.email_reader_agent import test_email_reader; test_email_reader()"
```

### Ollama Connection Issues

1. Verify Ollama is running: `ollama list`
2. Check API endpoint: `curl http://localhost:11434/api/tags`
3. Model should be available: `ollama pull phi3:mini`

### Port Already in Use

```bash
# Change port in .env
APP_PORT=8001

# Or terminate existing process
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

---

## 📚 Additional Commands

```bash
# Run tests
pytest tests/

# Update database schema
python -c "from src.database import Base, engine; Base.metadata.create_all(bind=engine)"

# Reset database
python -c "from src.database.connection import engine; from src.database.models import *; Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine)"
```

---

## 🎯 Next Steps

1. **Test Email Processing:**
   - Login to the dashboard
   - Click "Process Emails" button

2. **Configure Email Filtering:**
   - Modify keywords in `src/agents/email_filter_agent.py`

3. **Customize AI Extraction:**
   - Edit prompt in `src/models/ollama_mistral.py`

---

## 📞 Support

If you encounter issues:

1. Check the error messages carefully
2. Verify all prerequisites are installed
3. Review the `.env` configuration
4. Test individual components before running the full system

---

## ✅ Verification Checklist

Run these commands to verify your setup:

```bash
# 1. Check Python version
python --version

# 2. Check PostgreSQL accessibility
psql -U postgres -c "SELECT 1"

# 3. Check Ollama
ollama list

# 4. Test database connection
python -c "from src.database.connection import engine; print('DB OK')"

# 5. Test imports
python -c "from src.agents.email_reader_agent import EmailReaderAgent; print('Agents OK')"

# 6. Test AI model
python -c "from src.models.ollama_mistral import OllamaMistral; m = OllamaMistral(); print('AI OK')"

# 7. Check startup readiness report
curl http://localhost:8000/health/startup
```

All tests passing? You're ready to go! 🚀