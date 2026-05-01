"""
Database Package
Handles PostgreSQL operations using SQLAlchemy
"""

import logging
import os
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import text

from .connection import Base, SessionLocal, engine, get_db
from .models import (
    Customer, EmailLog, Order, User, OrderNote,
    Supplier, RawMaterial, Product, Machine,
    ProductionSchedule, ProductionProgress, ReorderLog, StockLog,
    DispatchLog, MisReportLog, OrderStatusLog
)

__all__ = [
    "engine",
    "Base",
    "SessionLocal",
    "get_db",
    "Customer",
    "Order",
    "OrderNote",
    "EmailLog",
    "User",
    "Supplier",
    "RawMaterial",
    "Product",
    "Machine",
    "ProductionSchedule",
    "ProductionProgress",
    "ReorderLog",
    "StockLog",
    "DispatchLog",
    "MisReportLog",
    "OrderStatusLog",
]

logger = logging.getLogger(__name__)


def init_db():
    """Initialize database by creating all tables"""
    # Create all tables
    Base.metadata.create_all(bind=engine)

    bootstrap_default_users = (
        os.environ.get("BOOTSTRAP_DEFAULT_USERS", "true").strip().lower() == "true"
    )
    if not bootstrap_default_users:
        logger.info("Skipping default user bootstrap (BOOTSTRAP_DEFAULT_USERS=false).")
        return

    # Default passwords for all 4 roles
    admin_password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin123")
    office_password = os.environ.get("DEFAULT_OFFICE_PASSWORD", "office123")
    owner_password = os.environ.get("DEFAULT_OWNER_PASSWORD", "owner123")
    supervisor_password = os.environ.get("DEFAULT_SUPERVISOR_PASSWORD", "supervisor123")
    store_password = os.environ.get("DEFAULT_STORE_PASSWORD", "store123")
    
    if any(p.endswith("123") for p in [admin_password, office_password, owner_password, supervisor_password, store_password]):
        logger.warning(
            "Using default bootstrap passwords. Set custom passwords in .env before production use."
        )

    # Create initial users with raw SQL via engine directly to avoid ORM complexity
    with engine.begin() as conn:
        # Check if admin user exists
        result = conn.execute(
            text("SELECT username FROM users WHERE username = 'admin'")
        ).fetchone()

        if not result:
            hashed_pw = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
            now = datetime.now(timezone.utc)
            conn.execute(
                text(
                    """INSERT INTO users (username, password_hash, role, is_active, created_at)
                       VALUES ('admin', :password_hash, 'office_staff', true, :created_at)"""
                ),
                {"password_hash": hashed_pw, "created_at": now},
            )
            logger.info("Admin user created successfully.")
        else:
            logger.info("Admin user already exists.")

        # Check if office user exists
        result = conn.execute(
            text("SELECT username FROM users WHERE username = 'office'")
        ).fetchone()

        if not result:
            hashed_pw = bcrypt.hashpw(office_password.encode(), bcrypt.gensalt()).decode()
            now = datetime.now(timezone.utc)
            conn.execute(
                text(
                    """INSERT INTO users (username, password_hash, role, is_active, created_at)
                       VALUES ('office', :password_hash, 'office_staff', true, :created_at)"""
                ),
                {"password_hash": hashed_pw, "created_at": now},
            )
            logger.info("Office user created successfully.")
        else:
            logger.info("Office user already exists.")

        # Check if owner user exists
        result = conn.execute(
            text("SELECT username FROM users WHERE username = 'owner'")
        ).fetchone()

        if not result:
            hashed_pw = bcrypt.hashpw(owner_password.encode(), bcrypt.gensalt()).decode()
            now = datetime.now(timezone.utc)
            conn.execute(
                text(
                    """INSERT INTO users (username, password_hash, role, is_active, created_at)
                       VALUES ('owner', :password_hash, 'owner', true, :created_at)"""
                ),
                {"password_hash": hashed_pw, "created_at": now},
            )
            logger.info("Owner user created successfully.")
        else:
            logger.info("Owner user already exists.")

        # Check if supervisor user exists
        result = conn.execute(
            text("SELECT username FROM users WHERE username = 'supervisor'")
        ).fetchone()

        if not result:
            hashed_pw = bcrypt.hashpw(supervisor_password.encode(), bcrypt.gensalt()).decode()
            now = datetime.now(timezone.utc)
            conn.execute(
                text(
                    """INSERT INTO users (username, password_hash, role, is_active, created_at)
                       VALUES ('supervisor', :password_hash, 'supervisor', true, :created_at)"""
                ),
                {"password_hash": hashed_pw, "created_at": now},
            )
            logger.info("Supervisor user created successfully.")
        else:
            logger.info("Supervisor user already exists.")

        # Check if store user exists
        result = conn.execute(
            text("SELECT username FROM users WHERE username = 'store'")
        ).fetchone()

        if not result:
            hashed_pw = bcrypt.hashpw(store_password.encode(), bcrypt.gensalt()).decode()
            now = datetime.now(timezone.utc)
            conn.execute(
                text(
                    """INSERT INTO users (username, password_hash, role, is_active, created_at)
                       VALUES ('store', :password_hash, 'store_staff', true, :created_at)"""
                ),
                {"password_hash": hashed_pw, "created_at": now},
            )
            logger.info("Store user created successfully.")
        else:
            logger.info("Store user already exists.")

    # Bootstrap V2 seed data
    bootstrap_v2_seed_data()
    
    logger.info("Database initialization completed successfully.")


def bootstrap_v2_seed_data():
    """Bootstrap V2 seed data for suppliers, materials, products, and machines"""
    with engine.begin() as conn:
        # Check if suppliers exist
        result = conn.execute(text("SELECT COUNT(*) FROM suppliers")).fetchone()
        if result and result[0] > 0:
            logger.info("V2 seed data already exists. Skipping.")
            return
        
        now = datetime.now(timezone.utc)
        
        # Insert suppliers
        conn.execute(
            text("""
                INSERT INTO suppliers (name, email, phone, material_supplied, address, is_active, created_at)
                VALUES 
                    ('Rajesh Polymers', 'orders@rajeshpolymers.com', '+91-9876543210', 'HDPE Granules', 'Ahmedabad, Gujarat', true, :created_at),
                    ('Gujarat Plastics', 'sales@gujaratplastics.com', '+91-9876543211', 'PP Granules', 'Surat, Gujarat', true, :created_at),
                    ('Mumbai Chemicals', 'supply@mumbaichem.com', '+91-9876543212', 'PVC Compound', 'Mumbai, Maharashtra', true, :created_at)
            """),
            {"created_at": now}
        )
        logger.info("Suppliers created successfully.")
        
        # Insert raw materials
        conn.execute(
            text("""
                INSERT INTO raw_materials (name, type, current_stock_kg, reorder_level_kg, reorder_quantity_kg, unit_price_per_kg, supplier_id, created_at)
                VALUES 
                    ('HDPE Granules', 'High-Density Polyethylene', 500.00, 100.00, 500.00, 85.50, 1, :created_at),
                    ('PP Granules', 'Polypropylene', 300.00, 75.00, 400.00, 92.00, 2, :created_at),
                    ('PVC Compound', 'Polyvinyl Chloride', 200.00, 50.00, 300.00, 110.00, 3, :created_at)
            """),
            {"created_at": now}
        )
        logger.info("Raw materials created successfully.")
        
        # Insert products
        conn.execute(
            text("""
                INSERT INTO products (name, description, material_id, material_required_per_unit_kg, machine_cycle_time_seconds, is_active, created_at)
                VALUES 
                    ('HDPE Container Cap 50mm', 'Standard 50mm HDPE cap for containers', 1, 0.012, 8, true, :created_at),
                    ('PP Container 500ml', '500ml polypropylene food container', 2, 0.018, 12, true, :created_at),
                    ('PVC Pipe Fitting', 'Standard PVC pipe connector', 3, 0.025, 15, true, :created_at)
            """),
            {"created_at": now}
        )
        logger.info("Products created successfully.")
        
        # Insert machines
        conn.execute(
            text("""
                INSERT INTO machines (name, model, status, last_maintenance_date, next_scheduled_maintenance, notes, is_active, created_at)
                VALUES 
                    ('Machine-01', 'Toshiba IS220GN', 'available', '2025-03-15', '2025-06-15', 'Primary machine for HDPE caps', true, :created_at),
                    ('Machine-02', 'Toshiba IS180GN', 'available', '2025-04-01', '2025-07-01', 'Secondary machine', true, :created_at),
                    ('Machine-03', 'JSW J220AD', 'available', '2025-04-10', '2025-07-10', 'For PP products', true, :created_at)
            """),
            {"created_at": now}
        )
        logger.info("Machines created successfully.")
