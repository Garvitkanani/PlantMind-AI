"""
Database Connection Module
Handles PostgreSQL connection using SQLAlchemy
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Suppress SQLAlchemy 2.0 deprecation warning for declarative_base
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    # declarative_base() is still functional in SQLAlchemy 2.0
    pass

# Get database URL from environment
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:password@localhost:5432/plantmind"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL logging
    pool_pre_ping=True,
    pool_size=int(os.environ.get("DB_POOL_SIZE", "10")),
    max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "20")),
    pool_recycle=int(os.environ.get("DB_POOL_RECYCLE_SECONDS", "1800")),
)

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


# Get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
