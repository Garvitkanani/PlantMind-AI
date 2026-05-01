"""
Database Models
SQLAlchemy ORM models for PlantMind AI schema (Updated to match V1 specification)
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    DECIMAL,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .connection import Base


def utc_now():
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Customer(Base):
    """Customers table - stores customer information (Matches V1 specification)"""

    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)  # Changed from customer_name
    email = Column(
        String(200), unique=True, nullable=False
    )  # Changed from customer_email
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=True)

    # Relationship with orders
    orders = relationship("Order", back_populates="customer")

    def __repr__(self):
        return f"<Customer(id={self.customer_id}, name='{self.name}')>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        created_at_iso = None
        if self.created_at:
            try:
                created_at_iso = self.created_at.isoformat()
            except AttributeError:
                pass

        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "created_at": created_at_iso,
        }


class Order(Base):
    """Orders table - stores processed order information (Matches V1 specification)"""

    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=False)
    product_name = Column(String(300), nullable=False)
    quantity = Column(Integer, nullable=False)
    required_delivery_date = Column(
        Date, nullable=True
    )  # Changed from delivery_date String
    special_instructions = Column(Text, nullable=True)
    status = Column(
        String(50), default="new"
    )  # Values: new / needs_review / scheduled / in_production / awaiting_material / completed / dispatched
    priority = Column(
        String(20), default="normal"
    )  # Values: normal / urgent / rush
    batch_number = Column(String(50), nullable=True)  # For lot tracking
    estimated_hours_actual = Column(DECIMAL(8, 2), nullable=True)  # Actual time taken vs estimate
    source_email_id = Column(
        Integer,
        ForeignKey(
            "email_log.email_id",
            use_alter=True,
            name="fk_orders_source_email_id",
        ),
        nullable=True,
    )  # Changed from source_email

    # V3 dispatch tracking
    dispatch_email_sent = Column(Boolean, default=False)  # Dedup: prevents re-sending dispatch email
    dispatch_sent_at = Column(DateTime, nullable=True)  # Timestamp of dispatch email

    # Timestamps
    created_at = Column(DateTime, default=utc_now, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="orders")
    source_email = relationship("EmailLog", foreign_keys=[source_email_id])
    notes = relationship("OrderNote", back_populates="order", order_by="OrderNote.created_at.desc()")

    def __repr__(self):
        return f"<Order(id={self.order_id}, product='{self.product_name}', quantity={self.quantity})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        customer_name = None
        if self.customer:
            customer_name = self.customer.name

        delivery_date_iso = None
        if self.required_delivery_date:
            try:
                delivery_date_iso = self.required_delivery_date.isoformat()
            except AttributeError:
                pass

        created_at_iso = None
        if self.created_at:
            try:
                created_at_iso = self.created_at.isoformat()
            except AttributeError:
                pass

        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "customer_name": customer_name or "Unknown",
            "product_name": self.product_name,
            "quantity": self.quantity,
            "required_delivery_date": delivery_date_iso,
            "special_instructions": self.special_instructions,
            "status": self.status,
            "priority": self.priority or "normal",
            "batch_number": self.batch_number,
            "estimated_hours_actual": float(self.estimated_hours_actual) if self.estimated_hours_actual else None,
            "created_at": created_at_iso,
        }


class OrderNote(Base):
    """Order notes table - internal communication and timeline tracking"""

    __tablename__ = "order_notes"

    note_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=False)
    note_type = Column(String(50), default="general")  # general / status_change / customer_call / internal / system
    note_text = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    order = relationship("Order", back_populates="notes")
    user = relationship("User", backref="order_notes")

    def __repr__(self):
        return f"<OrderNote(id={self.note_id}, order={self.order_id}, type='{self.note_type}')>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "note_id": self.note_id,
            "order_id": self.order_id,
            "note_type": self.note_type,
            "note_text": self.note_text,
            "created_by": self.created_by,
            "created_by_name": self.user.username if self.user else "System",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EmailLog(Base):
    """Email log table - tracks email processing status (Matches V1 specification)"""

    __tablename__ = "email_log"

    email_id = Column(
        Integer, primary_key=True, autoincrement=True
    )  # Changed from log_id
    gmail_message_id = Column(
        String(200), unique=True, nullable=False
    )  # Changed from message_id
    direction = Column(String(10), default="in")  # Values: in / out
    from_address = Column(String(200), nullable=True)  # Changed from from_email
    to_address = Column(String(200), nullable=True)
    subject = Column(Text, nullable=True)
    body_summary = Column(Text, nullable=True)
    attachment_name = Column(String(200), nullable=True)
    filter_decision = Column(String(20), nullable=True)  # process / skip
    processing_status = Column(
        String(30), nullable=True
    )  # success / flagged / error / skipped
    linked_order_id = Column(
        Integer,
        ForeignKey(
            "orders.order_id",
            use_alter=True,
            name="fk_email_log_linked_order_id",
        ),
        nullable=True,
    )  # Changed from order_id
    error_details = Column(Text, nullable=True)  # Changed from error_message
    processed_at = Column(
        DateTime, default=utc_now, nullable=True
    )  # Changed from created_at

    # Relationships
    order = relationship("Order", foreign_keys=[linked_order_id])

    def __repr__(self):
        return f"<EmailLog(id={self.email_id}, subject='{self.subject}', status='{self.processing_status}')>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        processed_at_iso = None
        if self.processed_at:
            try:
                processed_at_iso = self.processed_at.isoformat()
            except AttributeError:
                pass

        return {
            "email_id": self.email_id,
            "gmail_message_id": self.gmail_message_id,
            "direction": self.direction,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "subject": self.subject,
            "body_summary": self.body_summary,
            "attachment_name": self.attachment_name,
            "filter_decision": self.filter_decision,
            "processing_status": self.processing_status,
            "linked_order_id": self.linked_order_id,
            "error_details": self.error_details,
            "processed_at": processed_at_iso,
        }


class User(Base):
    """Users table - stores login credentials (Matches V1 specification)"""

    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        String(30), nullable=False
    )  # Values: owner / office_staff / supervisor / store
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    def __repr__(self):
        return (
            f"<User(id={self.user_id}, username='{self.username}', role='{self.role}')>"
        )

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        created_at_iso = None
        if self.created_at:
            try:
                created_at_iso = self.created_at.isoformat()
            except AttributeError:
                pass

        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": created_at_iso,
        }


# ============================================================================
# V2 Models - Production & Inventory Brain
# ============================================================================


class Supplier(Base):
    """Suppliers table - stores supplier contact information for auto-reorder"""

    __tablename__ = "suppliers"

    supplier_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=True)
    material_supplied = Column(String(200), nullable=True)
    address = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    materials = relationship("RawMaterial", back_populates="supplier")
    reorders = relationship("ReorderLog", back_populates="supplier")

    def __repr__(self):
        return f"<Supplier(id={self.supplier_id}, name='{self.name}')>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "supplier_id": self.supplier_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "material_supplied": self.material_supplied,
            "address": self.address,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RawMaterial(Base):
    """Raw materials table - tracks inventory levels and reorder triggers"""

    __tablename__ = "raw_materials"

    material_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    type = Column(String(100), nullable=True)
    current_stock_kg = Column(DECIMAL(10, 2), nullable=False, default=0)
    reorder_level_kg = Column(DECIMAL(10, 2), nullable=False)
    reorder_quantity_kg = Column(DECIMAL(10, 2), nullable=False)
    unit_price_per_kg = Column(DECIMAL(10, 2), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=True)
    last_updated = Column(DateTime, default=utc_now)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    supplier = relationship("Supplier", back_populates="materials")
    products = relationship("Product", back_populates="material")
    reorders = relationship("ReorderLog", back_populates="material")

    def __repr__(self):
        return f"<RawMaterial(id={self.material_id}, name='{self.name}', stock={self.current_stock_kg})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "material_id": self.material_id,
            "name": self.name,
            "type": self.type,
            "current_stock_kg": float(self.current_stock_kg) if self.current_stock_kg else 0,
            "reorder_level_kg": float(self.reorder_level_kg) if self.reorder_level_kg else 0,
            "reorder_quantity_kg": float(self.reorder_quantity_kg) if self.reorder_quantity_kg else 0,
            "unit_price_per_kg": float(self.unit_price_per_kg) if self.unit_price_per_kg else None,
            "supplier_id": self.supplier_id,
            "needs_reorder": self.needs_reorder(),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    def needs_reorder(self) -> bool:
        """Check if material stock is below reorder level"""
        if self.current_stock_kg is None or self.reorder_level_kg is None:
            return False
        return float(self.current_stock_kg) <= float(self.reorder_level_kg)

    def calculate_stock_after_order(self, quantity_needed_kg: float) -> float:
        """Calculate remaining stock after fulfilling an order"""
        current = float(self.current_stock_kg) if self.current_stock_kg else 0
        return max(0, current - quantity_needed_kg)


class Product(Base):
    """Products table - maps product names to material requirements and cycle times"""

    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=True)
    material_required_per_unit_kg = Column(DECIMAL(8, 4), nullable=False)
    machine_cycle_time_seconds = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    material = relationship("RawMaterial", back_populates="products")

    def __repr__(self):
        return f"<Product(id={self.product_id}, name='{self.name}')>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "product_id": self.product_id,
            "name": self.name,
            "description": self.description,
            "material_id": self.material_id,
            "material_required_per_unit_kg": float(self.material_required_per_unit_kg) if self.material_required_per_unit_kg else 0,
            "machine_cycle_time_seconds": self.machine_cycle_time_seconds,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def calculate_material_needed(self, quantity: int) -> float:
        """Calculate total material needed for given quantity"""
        per_unit = float(self.material_required_per_unit_kg) if self.material_required_per_unit_kg else 0
        return per_unit * quantity

    def calculate_production_time_hours(self, quantity: int) -> float:
        """Calculate total production time in hours for given quantity"""
        total_seconds = quantity * self.machine_cycle_time_seconds
        return total_seconds / 3600


class Machine(Base):
    """Machines table - tracks injection moulding machines and their status"""

    __tablename__ = "machines"

    machine_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    model = Column(String(100), nullable=True)
    status = Column(String(30), default="available")  # available / running / maintenance / offline
    current_order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=True)
    last_maintenance_date = Column(Date, nullable=True)
    next_scheduled_maintenance = Column(Date, nullable=True)
    maintenance_interval_hours = Column(Integer, default=720)  # Default 30 days
    total_runtime_hours = Column(DECIMAL(10, 2), default=0)  # Cumulative runtime for maintenance tracking
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    current_order = relationship("Order", foreign_keys=[current_order_id])
    schedules = relationship("ProductionSchedule", back_populates="machine")

    def __repr__(self):
        return f"<Machine(id={self.machine_id}, name='{self.name}', status='{self.status}')>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "machine_id": self.machine_id,
            "name": self.name,
            "model": self.model,
            "status": self.status,
            "current_order_id": self.current_order_id,
            "last_maintenance_date": self.last_maintenance_date.isoformat() if self.last_maintenance_date else None,
            "next_scheduled_maintenance": self.next_scheduled_maintenance.isoformat() if self.next_scheduled_maintenance else None,
            "maintenance_interval_hours": self.maintenance_interval_hours,
            "total_runtime_hours": float(self.total_runtime_hours) if self.total_runtime_hours else 0,
            "needs_maintenance": self.needs_maintenance(),
            "notes": self.notes,
            "is_active": self.is_active,
        }

    def is_available(self) -> bool:
        """Check if machine is available for scheduling"""
        return self.status == "available" and self.is_active

    def needs_maintenance(self) -> bool:
        """Check if machine needs maintenance based on runtime hours"""
        if not self.total_runtime_hours or not self.maintenance_interval_hours:
            return False
        return float(self.total_runtime_hours) >= self.maintenance_interval_hours

    def add_runtime_hours(self, hours: float):
        """Add runtime hours and check if maintenance is due"""
        current = float(self.total_runtime_hours) if self.total_runtime_hours else 0
        self.total_runtime_hours = current + hours


class ProductionSchedule(Base):
    """Production schedule table - links orders to machines with scheduling info"""

    __tablename__ = "production_schedule"

    schedule_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=False, unique=True)
    machine_id = Column(Integer, ForeignKey("machines.machine_id"), nullable=True)
    estimated_start = Column(DateTime, nullable=False)
    estimated_end = Column(DateTime, nullable=False)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    status = Column(String(30), default="scheduled")  # scheduled / in_production / completed / cancelled / delayed
    batch_number = Column(String(50), nullable=True)  # Batch/lot number for tracking
    delay_alert_sent = Column(Boolean, default=False)
    delay_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    order = relationship("Order", foreign_keys=[order_id])
    machine = relationship("Machine", back_populates="schedules")
    progress_updates = relationship("ProductionProgress", back_populates="schedule")

    def __repr__(self):
        return f"<ProductionSchedule(id={self.schedule_id}, order={self.order_id}, status='{self.status}')>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "schedule_id": self.schedule_id,
            "order_id": self.order_id,
            "machine_id": self.machine_id,
            "batch_number": self.batch_number,
            "estimated_start": self.estimated_start.isoformat() if self.estimated_start else None,
            "estimated_end": self.estimated_end.isoformat() if self.estimated_end else None,
            "actual_start": self.actual_start.isoformat() if self.actual_start else None,
            "actual_end": self.actual_end.isoformat() if self.actual_end else None,
            "status": self.status,
            "delay_alert_sent": self.delay_alert_sent,
            "delay_reason": self.delay_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def is_delayed(self) -> bool:
        """Check if production is delayed based on current progress"""
        if self.status != "in_production":
            return False
        
        # Get latest progress
        if not self.progress_updates:
            return False
        
        latest_progress = max(self.progress_updates, key=lambda p: p.created_at)
        if not latest_progress or not self.order or not self.order.required_delivery_date:
            return False
        
        # Calculate new ETA based on current pace
        from datetime import datetime, timezone
        if not latest_progress.completion_percentage or latest_progress.completion_percentage <= 0:
            return False
        
        hours_elapsed = (datetime.now(timezone.utc) - self.actual_start).total_seconds() / 3600
        pieces_per_hour = latest_progress.pieces_completed / hours_elapsed if hours_elapsed > 0 else 0
        
        if pieces_per_hour <= 0:
            return False
        
        pieces_remaining = latest_progress.total_pieces - latest_progress.pieces_completed
        hours_remaining = pieces_remaining / pieces_per_hour
        
        from datetime import timedelta
        new_eta = datetime.now(timezone.utc) + timedelta(hours=hours_remaining)
        
        return new_eta.date() > self.order.required_delivery_date

    def get_completion_percentage(self) -> float:
        """Get latest completion percentage from progress updates"""
        if not self.progress_updates:
            return 0.0
        latest = max(self.progress_updates, key=lambda p: p.created_at)
        return float(latest.completion_percentage) if latest.completion_percentage else 0.0


class ProductionProgress(Base):
    """Production progress table - tracks supervisor updates on production progress"""

    __tablename__ = "production_progress"

    progress_id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(Integer, ForeignKey("production_schedule.schedule_id"), nullable=False)
    pieces_completed = Column(Integer, nullable=False)  # Good pieces only
    pieces_defective = Column(Integer, default=0)  # Scrap/defective pieces
    total_pieces = Column(Integer, nullable=False)
    completion_percentage = Column(DECIMAL(5, 2), nullable=True)
    scrap_reason = Column(String(200), nullable=True)  # Reason for scrap (if any)
    batch_number = Column(String(50), nullable=True)  # Batch/lot number
    updated_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    schedule = relationship("ProductionSchedule", back_populates="progress_updates")
    updated_by_user = relationship("User", foreign_keys=[updated_by])

    def __repr__(self):
        return f"<ProductionProgress(id={self.progress_id}, schedule={self.schedule_id}, completed={self.pieces_completed})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "progress_id": self.progress_id,
            "schedule_id": self.schedule_id,
            "pieces_completed": self.pieces_completed,
            "pieces_defective": self.pieces_defective or 0,
            "total_pieces": self.total_pieces,
            "total_produced": (self.pieces_completed or 0) + (self.pieces_defective or 0),
            "scrap_rate": self.calculate_scrap_rate(),
            "completion_percentage": float(self.completion_percentage) if self.completion_percentage else 0,
            "scrap_reason": self.scrap_reason,
            "batch_number": self.batch_number,
            "updated_by": self.updated_by,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def calculate_scrap_rate(self) -> float:
        """Calculate scrap/defective rate as percentage"""
        total = (self.pieces_completed or 0) + (self.pieces_defective or 0)
        if total <= 0:
            return 0.0
        return ((self.pieces_defective or 0) / total) * 100

    def calculate_completion(self) -> float:
        """Calculate completion percentage"""
        if self.total_pieces <= 0:
            return 0.0
        return (self.pieces_completed / self.total_pieces) * 100


class ReorderLog(Base):
    """Reorder log table - logs all supplier reorders (auto and manual)"""

    __tablename__ = "reorder_log"

    reorder_id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.supplier_id"), nullable=True)
    quantity_kg = Column(DECIMAL(10, 2), nullable=False)
    triggered_by = Column(String(50), nullable=False)  # auto_order / manual_store / system_alert / scheduled
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=True)
    email_sent_to = Column(String(200), nullable=True)
    email_subject = Column(Text, nullable=True)
    email_body = Column(Text, nullable=True)
    status = Column(String(30), default="pending")  # pending / ordered / confirmed / shipped / delivered / cancelled
    delivery_expected_by = Column(Date, nullable=True)
    actual_delivery_date = Column(Date, nullable=True)
    delivery_quantity_kg = Column(DECIMAL(10, 2), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    material = relationship("RawMaterial", back_populates="reorders")
    supplier = relationship("Supplier", back_populates="reorders")
    order = relationship("Order", foreign_keys=[order_id])

    def __repr__(self):
        return f"<ReorderLog(id={self.reorder_id}, material={self.material_id}, status='{self.status}')>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "reorder_id": self.reorder_id,
            "material_id": self.material_id,
            "supplier_id": self.supplier_id,
            "quantity_kg": float(self.quantity_kg) if self.quantity_kg else 0,
            "triggered_by": self.triggered_by,
            "order_id": self.order_id,
            "email_sent_to": self.email_sent_to,
            "status": self.status,
            "delivery_expected_by": self.delivery_expected_by.isoformat() if self.delivery_expected_by else None,
            "actual_delivery_date": self.actual_delivery_date.isoformat() if self.actual_delivery_date else None,
            "delivery_quantity_kg": float(self.delivery_quantity_kg) if self.delivery_quantity_kg else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StockLog(Base):
    """Stock log table - audit trail for all material inventory changes"""

    __tablename__ = "stock_log"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(Integer, ForeignKey("raw_materials.material_id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=True)
    change_type = Column(String(50), nullable=False)  # manual_update, production_usage, delivery, wastage, returns
    quantity_before_kg = Column(DECIMAL(10, 2), nullable=False)
    quantity_after_kg = Column(DECIMAL(10, 2), nullable=False)
    change_amount_kg = Column(DECIMAL(10, 2), nullable=False)
    reason = Column(String(200), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    updated_at = Column(DateTime, default=utc_now)

    # Relationships
    material = relationship("RawMaterial", backref="stock_logs")
    order = relationship("Order", backref="stock_logs")
    user = relationship("User", backref="stock_updates")

    def __repr__(self):
        return f"<StockLog(id={self.log_id}, material={self.material_id}, type='{self.change_type}', change={self.change_amount_kg})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "log_id": self.log_id,
            "material_id": self.material_id,
            "material_name": self.material.name if self.material else None,
            "order_id": self.order_id,
            "change_type": self.change_type,
            "quantity_before_kg": float(self.quantity_before_kg),
            "quantity_after_kg": float(self.quantity_after_kg),
            "change_amount_kg": float(self.change_amount_kg),
            "reason": self.reason,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DispatchLog(Base):
    """V3 dispatch log - tracks dispatch email delivery attempts and outcomes."""

    __tablename__ = "dispatch_log"

    dispatch_log_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=False)
    customer_email = Column(String(200), nullable=True)
    email_subject = Column(Text, nullable=True)
    email_body = Column(Text, nullable=True)
    send_status = Column(String(30), default="queued")  # queued / sent / failed
    attempts = Column(Integer, default=0)
    error_details = Column(Text, nullable=True)
    triggered_by = Column(String(50), default="v3_dispatch_job")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    order = relationship("Order", backref="dispatch_logs")

    def to_dict(self):
        return {
            "dispatch_log_id": self.dispatch_log_id,
            "order_id": self.order_id,
            "customer_email": self.customer_email,
            "email_subject": self.email_subject,
            "send_status": self.send_status,
            "attempts": self.attempts,
            "error_details": self.error_details,
            "triggered_by": self.triggered_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MisReportLog(Base):
    """V3 MIS report log - tracks daily MIS delivery attempts and outcomes."""

    __tablename__ = "mis_report_log"

    mis_report_log_id = Column(Integer, primary_key=True, autoincrement=True)
    report_date = Column(Date, nullable=False)
    owner_email = Column(String(200), nullable=True)
    email_subject = Column(Text, nullable=True)
    report_body = Column(Text, nullable=True)
    send_status = Column(String(30), default="queued")  # queued / sent / failed
    attempts = Column(Integer, default=0)
    error_details = Column(Text, nullable=True)
    triggered_by = Column(String(50), default="v3_mis_report_job")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def to_dict(self):
        return {
            "mis_report_log_id": self.mis_report_log_id,
            "report_date": self.report_date.isoformat() if self.report_date else None,
            "owner_email": self.owner_email,
            "email_subject": self.email_subject,
            "send_status": self.send_status,
            "attempts": self.attempts,
            "error_details": self.error_details,
            "triggered_by": self.triggered_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OrderStatusLog(Base):
    """V3 order status audit log — tracks every status transition for full traceability."""

    __tablename__ = "order_status_log"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=False)
    old_status = Column(String(50), nullable=True)  # NULL for initial creation
    new_status = Column(String(50), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    change_source = Column(
        String(50), nullable=False, default="system"
    )  # system / manual / v1_processor / v2_processor / v3_processor / supervisor / office_staff
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    order = relationship("Order", backref="status_logs")
    user = relationship("User", backref="status_changes")

    def __repr__(self):
        return (
            f"<OrderStatusLog(id={self.log_id}, order={self.order_id}, "
            f"{self.old_status} -> {self.new_status})>"
        )

    def to_dict(self):
        return {
            "log_id": self.log_id,
            "order_id": self.order_id,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "changed_by": self.changed_by,
            "changed_by_name": self.user.username if self.user else "System",
            "change_source": self.change_source,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
