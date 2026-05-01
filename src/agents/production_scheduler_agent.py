"""
Production Scheduler Agent - V2 Production & Inventory Brain

Responsibility:
- Find best available machine for the order
- Calculate production timeline using machine cycle time
- Create production_schedule record
- Update machine and order status

Machine Selection Logic:
1. Find all machines with status = "available"
2. If one or more available → pick the one with lowest machine_id (oldest/most familiar)
3. If no machine available → find machine with earliest estimated completion
4. Schedule this order to start immediately after that machine finishes
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import Order, Product, Machine, ProductionSchedule

logger = logging.getLogger(__name__)


@dataclass
class ScheduleResult:
    """Result of production scheduling"""
    success: bool
    schedule_id: Optional[int]
    machine_id: Optional[int]
    machine_name: Optional[str]
    estimated_start: Optional[datetime]
    estimated_end: Optional[datetime]
    estimated_hours: float
    message: str


class ProductionSchedulerAgent:
    """
    Production Scheduler Agent
    
    Schedules orders on available machines and calculates production timelines.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def schedule_order(self, order: Order) -> ScheduleResult:
        """
        Schedule an order on the best available machine.
        
        Args:
            order: Order to schedule
            
        Returns:
            ScheduleResult with scheduling details
        """
        logger.info(f"Scheduling order {order.order_id}: {order.product_name}")
        
        # Step 1: Find product to get cycle time
        product = self._find_product(order.product_name)
        if not product:
            logger.error(f"Product not found: {order.product_name}")
            return ScheduleResult(
                success=False,
                schedule_id=None,
                machine_id=None,
                machine_name=None,
                estimated_start=None,
                estimated_end=None,
                estimated_hours=0,
                message=f"Product '{order.product_name}' not found"
            )
        
        # Step 2: Calculate production time
        estimated_hours = self._calculate_production_time(product, order.quantity)
        logger.info(f"Estimated production time: {estimated_hours:.2f} hours")
        
        # Step 3: Find best machine
        machine_result = self._find_best_machine(estimated_hours)
        
        if not machine_result:
            logger.error("No machines available for scheduling")
            return ScheduleResult(
                success=False,
                schedule_id=None,
                machine_id=None,
                machine_name=None,
                estimated_start=None,
                estimated_end=None,
                estimated_hours=estimated_hours,
                message="No machines available for scheduling"
            )
        
        machine, start_time = machine_result
        
        # Step 4: Calculate end time
        end_time = start_time + timedelta(hours=estimated_hours)
        
        # Step 5: Create production schedule
        schedule = ProductionSchedule(
            order_id=order.order_id,
            machine_id=machine.machine_id,
            estimated_start=start_time,
            estimated_end=end_time,
            status="scheduled"
        )
        
        # Generate batch number
        batch_number = self._generate_batch_number(order, machine)
        schedule.batch_number = batch_number
        order.batch_number = batch_number
        
        self.db.add(schedule)
        
        # Step 6: Update machine status (runtime hours tracked on completion by tracker agent)
        machine.status = "running"
        machine.current_order_id = order.order_id
        
        # Step 7: Update order status
        order.status = "scheduled"
        
        # Add system note about scheduling
        from src.database.models import OrderNote
        note = OrderNote(
            order_id=order.order_id,
            note_type="system",
            note_text=f"Order scheduled on {machine.name}. Batch: {batch_number}. Est: {estimated_hours:.1f} hours.",
            created_by=None  # System action
        )
        self.db.add(note)
        
        self.db.commit()
        self.db.refresh(schedule)
        
        logger.info(f"Order {order.order_id} scheduled on {machine.name} "
                   f"(Start: {start_time}, End: {end_time})")
        
        return ScheduleResult(
            success=True,
            schedule_id=schedule.schedule_id,
            machine_id=machine.machine_id,
            machine_name=machine.name,
            estimated_start=start_time,
            estimated_end=end_time,
            estimated_hours=estimated_hours,
            message=f"Order scheduled on {machine.name}"
        )
    
    def _find_product(self, product_name: str) -> Optional[Product]:
        """Find product by name (case-insensitive, with fallback partial match)"""
        # Exact case-insensitive match
        safe_name = product_name.replace("%", "\\%").replace("_", "\\_")
        product = self.db.query(Product).filter(
            Product.name.ilike(safe_name),
            Product.is_active == True
        ).first()
        if product:
            return product
        # Partial match fallback
        return self.db.query(Product).filter(
            Product.name.ilike(f"%{safe_name}%"),
            Product.is_active == True
        ).first()
    
    def _calculate_production_time(self, product: Product, quantity: int) -> float:
        """
        Calculate total production time in hours.
        
        Formula: quantity × cycle_time_seconds / 3600
        """
        total_seconds = quantity * product.machine_cycle_time_seconds
        return total_seconds / 3600
    
    def _find_best_machine(self, estimated_hours: float) -> Optional[tuple[Machine, datetime]]:
        """
        Find the best machine for scheduling.
        
        Returns:
            Tuple of (machine, start_time) or None if no machine available
        """
        now = datetime.now(timezone.utc)
        
        # Step 1: Look for available machines (excluding those needing maintenance)
        available_machines = self.db.query(Machine).filter(
            Machine.status == "available",
            Machine.is_active == True
        ).order_by(Machine.machine_id).all()
        
        # Filter out machines needing maintenance
        ready_machines = [m for m in available_machines if not m.needs_maintenance()]
        
        if ready_machines:
            # Pick the first (lowest ID = oldest/most familiar)
            best_machine = ready_machines[0]
            return (best_machine, now)
        
        # Log warning if machines available but need maintenance
        if available_machines and not ready_machines:
            logger.warning(f"{len(available_machines)} machines available but need maintenance")
        
        # Step 2: No available machines - find machine with earliest completion
        running_schedules = self.db.query(ProductionSchedule).filter(
            ProductionSchedule.status.in_(["scheduled", "in_production"]),
            ProductionSchedule.machine_id.isnot(None)
        ).order_by(ProductionSchedule.estimated_end).all()
        
        if running_schedules:
            # Get the schedule with earliest completion
            earliest_schedule = running_schedules[0]
            machine = self.db.query(Machine).filter(
                Machine.machine_id == earliest_schedule.machine_id
            ).first()
            
            if machine and not machine.needs_maintenance():
                # Start after current schedule ends (add 1 hour buffer for changeover)
                start_time = earliest_schedule.estimated_end + timedelta(hours=1)
                return (machine, start_time)
        
        # No machines available
        return None
    
    def _generate_batch_number(self, order: Order, machine: Machine) -> str:
        """
        Generate a unique batch/lot number for production tracking.
        
        Format: P{product_code}-{date}-{machine_id}-{sequence}
        Example: PHDPE-20260130-01-001
        """
        from datetime import datetime
        
        # Generate product code from product name (first 4 chars uppercase)
        product_code = (order.product_name[:4] if order.product_name else "PROD").upper()
        
        # Date component
        date_str = datetime.now().strftime("%Y%m%d")
        
        # Machine ID (2 digits)
        machine_str = f"{machine.machine_id:02d}"
        
        # Check for existing batches today to get sequence
        existing_batches = self.db.query(ProductionSchedule).filter(
            ProductionSchedule.batch_number.like(f"{product_code}-{date_str}-{machine_str}-%")
        ).count()
        
        sequence = existing_batches + 1
        
        return f"{product_code}-{date_str}-{machine_str}-{sequence:03d}"
    
    def get_machines_needing_maintenance(self) -> list[Machine]:
        """Get list of machines that need maintenance"""
        machines = self.db.query(Machine).filter(
            Machine.is_active == True,
            Machine.status.in_(["available", "running"])
        ).all()
        
        return [m for m in machines if m.needs_maintenance()]
    
    def get_machine_utilization(self) -> dict:
        """
        Get current machine utilization statistics.
        
        Returns:
            Dictionary with utilization stats
        """
        total_machines = self.db.query(Machine).filter(Machine.is_active == True).count()
        
        available = self.db.query(Machine).filter(
            Machine.status == "available",
            Machine.is_active == True
        ).count()
        
        running = self.db.query(Machine).filter(
            Machine.status == "running",
            Machine.is_active == True
        ).count()
        
        maintenance = self.db.query(Machine).filter(
            Machine.status == "maintenance",
            Machine.is_active == True
        ).count()
        
        return {
            "total": total_machines,
            "available": available,
            "running": running,
            "maintenance": maintenance,
            "utilization_rate": (running / total_machines * 100) if total_machines > 0 else 0
        }


# Factory function
def create_scheduler(db_session: Session) -> ProductionSchedulerAgent:
    """Factory function to create ProductionSchedulerAgent instance"""
    return ProductionSchedulerAgent(db_session)
