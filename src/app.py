"""
Main Application Entry Point
PlantMind AI - Smart Order Intake System
Version 2 (V1 + Production & Inventory Brain)
"""

import os
import sys
import logging
from contextlib import asynccontextmanager

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.database import init_db
from src.routes.v1_routes import create_v1_app
from src.routes.v2_routes import router as v2_router
from src.routes.owner_router import router as owner_router
from src.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app):
    """Initialize database, bootstrap data, and start background scheduler."""
    logger.info("Starting PlantMind AI V2 application...")
    init_db()
    
    # Start background task scheduler
    start_scheduler()
    logger.info("Background scheduler started.")
    
    logger.info("Startup initialization complete.")
    yield
    
    # Shutdown
    stop_scheduler()
    logger.info("Shutting down PlantMind AI V2 application.")


# Create FastAPI app with V1 and V2
app = create_v1_app(lifespan=lifespan)

# Include V2 routes
app.include_router(v2_router)

# Include Owner routes
app.include_router(owner_router)
