"""
Production Tracker Agent - V2 Production & Inventory Brain

Responsibility:
- Receive progress update from floor supervisor
- Save to production_progress table
- Recalculate completion percentage
- Recalculate ETA based on actual production pace
- Detect delays
- Send delay alert if needed (Phi-3 Mini)
- Detect completion and trigger handoff to V3

Pace-Based ETA Recalculation:
Instead of using cycle time (which may not match real world), the agent uses 
actual measured pace from supervisor updates. This makes ETA increasingly 
accurate as production progresses.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import (
    ProductionSchedule, ProductionProgress, Order, Machine, User, OrderStatusLog
)
from src.gmail.gmail_sender import gmail_sender
from src.models.ollama_phi3 import OllamaPhi3

logger = logging.getLogger(__name__)


@dataclass
class ProgressUpdateResult:
    """Result of a progress update"""
    success: bool
    progress_id: Optional[int]
    completion_percentage: float
    new_eta: Optional[datetime]
    is_delayed: bool
    is_complete: bool
    message: str
    delay_alert_triggered: bool = False


class ProductionTrackerAgent:
    """
    Production Tracker Agent
    
    Tracks production progress, recalculates ETAs, and detects delays.
    """
    
    def __init__(self, db_session: Session, email_sender=None):
        self.db = db_session
        self.ai_model = OllamaPhi3()
        self.email_sender = email_sender
    
    def update_progress(
        self,
        schedule_id: int,
        pieces_completed: int,
        updated_by: int,
        notes: Optional[str] = None
    ) -> ProgressUpdateResult:
        """
        Update production progress for a scheduled order.
        
        Args:
            schedule_id: Production schedule ID
            pieces_completed: Total pieces completed so far
            updated_by: User ID of supervisor making the update
            notes: Optional notes
            
        Returns:
            ProgressUpdateResult with update details
        """
        logger.info(f"Updating progress for schedule {schedule_id}: {pieces_completed} pieces")
        
        # Step 1: Get schedule and related order
        schedule = self.db.query(ProductionSchedule).filter(
            ProductionSchedule.schedule_id == schedule_id
        ).first()
        
        if not schedule:
            logger.error(f"Schedule {schedule_id} not found")
            return ProgressUpdateResult(
                success=False,
                progress_id=None,
                completion_percentage=0,
                new_eta=None,
                is_delayed=False,
                is_complete=False,
                message="Schedule not found"
            )
        
        order = schedule.order
        if not order:
            logger.error(f"No order found for schedule {schedule_id}")
            return ProgressUpdateResult(
                success=False,
                progress_id=None,
                completion_percentage=0,
                new_eta=None,
                is_delayed=False,
                is_complete=False,
                message="Order not found for schedule"
            )
        
        total_pieces = order.quantity
        
        # Step 2: Validate input
        if pieces_completed > total_pieces:
            pieces_completed = total_pieces
        
        if pieces_completed < 0:
            pieces_completed = 0
        
        # Step 3: Calculate completion percentage
        completion_pct = (pieces_completed / total_pieces) * 100 if total_pieces > 0 else 0
        
        # Step 4: Calculate new ETA based on actual pace
        new_eta = None
        is_delayed = False
        
        if schedule.actual_start and pieces_completed > 0:
            new_eta, is_delayed = self._calculate_new_eta(
                schedule=schedule,
                pieces_completed=pieces_completed,
                total_pieces=total_pieces
            )
        
        # Step 5: Save progress update
        progress = ProductionProgress(
            schedule_id=schedule_id,
            pieces_completed=pieces_completed,
            total_pieces=total_pieces,
            completion_percentage=completion_pct,
            updated_by=updated_by,
            notes=notes
        )
        
        self.db.add(progress)
        
        # Step 6: Check for completion
        is_complete = pieces_completed >= total_pieces
        
        if is_complete:
            self._handle_completion(schedule, order)
        
        # Step 7: Handle delay detection
        delay_alert_triggered = False
        if is_delayed and not schedule.delay_alert_sent:
            self._send_delay_alert(schedule, order, pieces_completed, new_eta)
            schedule.delay_alert_sent = True
            delay_alert_triggered = True
        
        self.db.commit()
        self.db.refresh(progress)
        
        logger.info(f"Progress updated: {completion_pct:.1f}% complete, delayed={is_delayed}")
        
        return ProgressUpdateResult(
            success=True,
            progress_id=progress.progress_id,
            completion_percentage=completion_pct,
            new_eta=new_eta,
            is_delayed=is_delayed,
            is_complete=is_complete,
            message=self._generate_message(is_complete, is_delayed, completion_pct),
            delay_alert_triggered=delay_alert_triggered
        )
    
    def _calculate_new_eta(
        self,
        schedule: ProductionSchedule,
        pieces_completed: int,
        total_pieces: int
    ) -> tuple[Optional[datetime], bool]:
        """
        Calculate new ETA based on actual production pace.
        
        Returns:
            Tuple of (new_eta, is_delayed)
        """
        now = datetime.now(timezone.utc)
        
        # Calculate hours elapsed since actual start
        if not schedule.actual_start:
            return None, False
        
        # Ensure actual_start is timezone-aware
        actual_start = schedule.actual_start
        if actual_start.tzinfo is None:
            actual_start = actual_start.replace(tzinfo=timezone.utc)
        
        hours_elapsed = (now - actual_start).total_seconds() / 3600
        
        if hours_elapsed <= 0 or pieces_completed <= 0:
            return None, False
        
        # Calculate actual pace (pieces per hour)
        pieces_per_hour = pieces_completed / hours_elapsed
        
        # Calculate remaining pieces and time
        pieces_remaining = total_pieces - pieces_completed
        hours_remaining = pieces_remaining / pieces_per_hour if pieces_per_hour > 0 else 0
        
        # Calculate new ETA
        new_eta = now + timedelta(hours=hours_remaining)
        
        # Check if delayed (compare to required delivery date)
        is_delayed = False
        if schedule.order and schedule.order.required_delivery_date:
            is_delayed = new_eta.date() > schedule.order.required_delivery_date
        
        return new_eta, is_delayed
    
    def _handle_completion(self, schedule: ProductionSchedule, order: Order):
        """Handle order completion - updates status, frees machine, deducts material"""
        logger.info(f"Order {order.order_id} production completed")
        
        # Deduct material from inventory
        material_used_kg = self._deduct_material_for_order(order)
        if material_used_kg > 0:
            logger.info(f"Deducted {material_used_kg:.2f} kg of material from inventory for order {order.order_id}")
        
        # Update schedule
        schedule.status = "completed"
        schedule.actual_end = datetime.now(timezone.utc)
        
        # Update order
        order.status = "completed"
        
        # Free up machine and track actual runtime hours
        if schedule.machine_id:
            machine = self.db.query(Machine).filter(
                Machine.machine_id == schedule.machine_id
            ).first()
            if machine:
                machine.status = "available"
                machine.current_order_id = None
                # Track actual runtime (not estimated) for maintenance scheduling
                if schedule.actual_start and schedule.actual_end:
                    start = schedule.actual_start
                    end = schedule.actual_end
                    # Ensure both are timezone-aware for safe subtraction
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                    actual_hours = (end - start).total_seconds() / 3600
                    machine.add_runtime_hours(actual_hours)

        # Log status change for audit trail
        status_log = OrderStatusLog(
            order_id=order.order_id,
            old_status="in_production",
            new_status="completed",
            change_source="supervisor",
            notes=f"Production completed — machine freed, material deducted ({material_used_kg:.2f} kg)",
        )
        self.db.add(status_log)
    
    def _deduct_material_for_order(self, order: Order) -> float:
        """
        Deduct material used from raw_materials inventory and log to stock_log.
        
        Returns:
            Amount of material deducted in kg
        """
        from decimal import Decimal
        from src.database.models import Product, RawMaterial, StockLog
        
        # Find the product
        product = self.db.query(Product).filter(
            Product.name.ilike(order.product_name),
            Product.is_active == True
        ).first()
        
        if not product or not product.material_id:
            logger.warning(f"Cannot deduct material: Product '{order.product_name}' not found or has no material")
            return 0.0
        
        # Calculate material used
        material_needed_kg = float(product.material_required_per_unit_kg) * order.quantity
        
        # Get raw material
        material = self.db.query(RawMaterial).filter(
            RawMaterial.material_id == product.material_id
        ).first()
        
        if not material:
            logger.warning(f"Cannot deduct material: Raw material ID {product.material_id} not found")
            return 0.0
        
        # Record values before update
        current_stock = float(material.current_stock_kg)
        new_stock = max(0, current_stock - material_needed_kg)
        
        # Create stock log entry for automatic production usage
        stock_log = StockLog(
            material_id=material.material_id,
            order_id=order.order_id,
            change_type="production_usage",
            quantity_before_kg=current_stock,
            quantity_after_kg=new_stock,
            change_amount_kg=-material_needed_kg,  # Negative because we're removing
            reason=f"Production completed for order #{order.order_id} - {order.product_name} ({order.quantity} units)",
            updated_by=None  # System action
        )
        self.db.add(stock_log)
        
        # Deduct from inventory
        material.current_stock_kg = Decimal(str(new_stock))
        material.last_updated = datetime.now(timezone.utc)
        
        logger.info(f"Material {material.name}: {current_stock:.2f} kg → {new_stock:.2f} kg "
                   f"(used {material_needed_kg:.2f} kg for order {order.order_id}) - Logged to stock_log")
        
        return material_needed_kg
    
    def _send_delay_alert(
        self,
        schedule: ProductionSchedule,
        order: Order,
        pieces_completed: int,
        new_eta: datetime
    ):
        """Send delay alert email to owner using AI-generated content"""
        logger.warning(f"Delay detected for order {order.order_id}")
        
        # Get owner email from environment
        import os
        owner_email = os.environ.get("OWNER_EMAIL", "owner@factory.com")
        factory_name = os.environ.get("FACTORY_NAME", "PlantMind AI Factory")
        
        # Draft alert email using AI
        ai_body = self._draft_delay_alert(
            order=order,
            pieces_completed=pieces_completed,
            new_eta=new_eta,
            factory_name=factory_name
        )
        
        # Send if email sender configured
        if self.email_sender and self.email_sender.enabled:
            try:
                result = self.email_sender.send_delay_alert(
                    owner_email=owner_email,
                    order_id=order.order_id,
                    product_name=order.product_name,
                    customer_name=order.customer.name if order.customer else "Unknown",
                    original_deadline=order.required_delivery_date.strftime("%Y-%m-%d") if order.required_delivery_date else "Unknown",
                    new_eta=new_eta.strftime("%Y-%m-%d") if new_eta else "Unknown",
                    pieces_completed=pieces_completed,
                    total_pieces=order.quantity,
                    ai_generated_body=ai_body
                )
                if result.get("success"):
                    logger.info(f"Delay alert sent to {owner_email}")
                else:
                    logger.error(f"Failed to send delay alert: {result.get('error')}")
            except Exception as e:
                logger.error(f"Failed to send delay alert: {e}")
        else:
            logger.warning("Email sender not configured - delay alert not sent")
    
    def _draft_delay_alert(
        self,
        order: Order,
        pieces_completed: int,
        new_eta: datetime,
        factory_name: str = "PlantMind AI Factory"
    ) -> str:
        """Draft delay alert email body using Phi-3 Mini AI.
        
        Returns:
            AI-generated email body text (not subject)
        """
        try:
            body = self.ai_model.draft_delay_alert(
                order_id=order.order_id,
                customer_name=order.customer.name if order.customer else "Unknown",
                product_name=order.product_name,
                pieces_completed=pieces_completed,
                total_pieces=order.quantity,
                original_deadline=order.required_delivery_date.strftime("%Y-%m-%d") if order.required_delivery_date else "Unknown",
                new_eta=new_eta.strftime("%Y-%m-%d") if new_eta else "Unknown",
                factory_name=factory_name,
            )
            logger.info(f"AI-generated delay alert for order #{order.order_id}")
            return body
        except Exception as e:
            logger.error(f"Phi-3 delay alert drafting failed: {e}")
            return self.ai_model._fallback_delay_alert(
                order_id=order.order_id,
                customer_name=order.customer.name if order.customer else "Unknown",
                product_name=order.product_name,
                pieces_completed=pieces_completed,
                total_pieces=order.quantity,
                original_deadline=order.required_delivery_date.strftime("%Y-%m-%d") if order.required_delivery_date else "Unknown",
                new_eta=new_eta.strftime("%Y-%m-%d") if new_eta else "Unknown",
                factory_name=factory_name,
            )
    
    def _generate_message(self, is_complete: bool, is_delayed: bool, completion_pct: float) -> str:
        """Generate status message"""
        if is_complete:
            return "Production completed successfully"
        elif is_delayed:
            return f"Progress updated: {completion_pct:.1f}% - DELAY DETECTED"
        else:
            return f"Progress updated: {completion_pct:.1f}% complete"
    
    def get_progress_history(self, schedule_id: int) -> list[ProductionProgress]:
        """Get all progress updates for a schedule"""
        return self.db.query(ProductionProgress).filter(
            ProductionProgress.schedule_id == schedule_id
        ).order_by(ProductionProgress.created_at.asc()).all()
    
    def get_latest_progress(self, schedule_id: int) -> Optional[ProductionProgress]:
        """Get latest progress update for a schedule"""
        return self.db.query(ProductionProgress).filter(
            ProductionProgress.schedule_id == schedule_id
        ).order_by(ProductionProgress.created_at.desc()).first()


# Factory function
def create_tracker(db_session: Session, email_sender=None) -> ProductionTrackerAgent:
    """Factory function to create ProductionTrackerAgent instance
    
    Args:
        db_session: SQLAlchemy database session
        email_sender: Email sender instance (defaults to gmail_sender singleton)
    """
    sender = email_sender or gmail_sender
    return ProductionTrackerAgent(db_session, sender)
