import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.app import app

if __name__ == "__main__":
    import uvicorn

    # Reload environment
    load_dotenv()

    host = os.environ.get("APP_HOST", "0.0.0.0")
    port = int(os.environ.get("APP_PORT", "8000"))

    print(f"🚀 Starting PlantMind AI V1 on {host}:{port}")
    print(f"📊 Dashboard: http://localhost:{port}/login")
    print("🔑 Login users are initialized by database bootstrap (change defaults before production use).")
    print("=" * 60)

    uvicorn.run(app, host=host, port=port, reload=True)
