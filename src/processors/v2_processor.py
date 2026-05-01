"""
V2 Processor - Production & Inventory Brain Orchestrator

Coordinates all V2 agents:
1. Inventory Check Agent - verifies material availability
2. Reorder Agent - auto-reorders from suppliers if needed
3. Production Scheduler Agent - assigns orders to machines
4. Production Tracker Agent - monitors progress & detects delays

Triggered by: New orders with status="new"
Polls every 60 seconds via background task
"""

import logging
from typing import Dict, List
from uuid import uuid4

from sqlalchemy.orm import Session

from src.database.connection import SessionLocal
from src.database.models import Order
from src.agents.inventory_check_agent import create_inventory_checker, InventoryCheckResult
from src.agents.reorder_agent import create_reorder_agent, ReorderResult
from src.agents.production_scheduler_agent import create_scheduler, ScheduleResult

logger = logging.getLogger(__name__)


class V2ProcessingResult:
    """Result of V2 processing pipeline"""
    def __init__(self):
        self.total_orders = 0
        self.inventory_checked = 0
        self.reorders_triggered = 0
        self.scheduled = 0
        self.awaiting_material = 0
        self.errors = 0
        self.details: List[Dict] = []
    
    def to_dict(self) -> Dict:
        return {
            "total_orders": self.total_orders,
            "inventory_checked": self.inventory_checked,
            "reorders_triggered": self.reorders_triggered,
            "scheduled": self.scheduled,
            "awaiting_material": self.awaiting_material,
            "errors": self.errors,
            "details": self.details
        }


class V2Processor:
    """
    V2 Production & Inventory Brain Processor
    
    Orchestrates the complete V2 workflow:
    - Checks inventory for new orders
    - Triggers reorders if stock insufficient
    - Schedules orders on machines when material available
    """
    
    def __init__(self, db_session: Session = None, email_sender=None):
        self.db = db_session or SessionLocal()
        self.email_sender = email_sender
        
        # Initialize agents
        self.inventory_checker = create_inventory_checker(self.db)
        self.reorder_agent = create_reorder_agent(self.db, email_sender)
        self.scheduler = create_scheduler(self.db)
    
    def process_new_orders(self) -> V2ProcessingResult:
        """
        Process all new orders through V2 pipeline.
        
        Pipeline:
        1. Get all orders with status="new"
        2. For each order:
           a. Check inventory
           b. If insufficient → trigger reorder, set status="awaiting_material"
           c. If sufficient → schedule on machine, set status="scheduled"
        
        Returns:
            V2ProcessingResult with summary
        """
        run_id = uuid4().hex[:12]
        result = V2ProcessingResult()
        
        # Get all new orders - sort by priority (urgent first, then rush, then normal)
        new_orders = self.inventory_checker.get_all_new_orders()
        
        # Priority sort: urgent > rush > normal
        priority_order = {"urgent": 0, "rush": 1, "normal": 2}
        new_orders.sort(key=lambda o: priority_order.get(o.priority or "normal", 2))
        
        result.total_orders = len(new_orders)
        
        logger.info(
            "V2 run_id=%s: Found %s new orders (sorted by priority)",
            run_id,
            len(new_orders),
        )
        
        for order in new_orders:
            try:
                detail = self._process_single_order(order, run_id=run_id)
                result.details.append(detail)
                
                # Update counters
                if detail.get("inventory_checked"):
                    result.inventory_checked += 1
                if detail.get("reorder_triggered"):
                    result.reorders_triggered += 1
                if detail.get("scheduled"):
                    result.scheduled += 1
                if detail.get("awaiting_material"):
                    result.awaiting_material += 1
                    
            except Exception as e:
                logger.error(
                    "V2 run_id=%s order_id=%s: Error processing order: %s",
                    run_id,
                    order.order_id,
                    e,
                )
                result.errors += 1
                result.details.append({
                    "order_id": order.order_id,
                    "error": str(e)
                })
        
        logger.info("V2 run_id=%s: Processing complete: %s", run_id, result.to_dict())
        return result
    
    def _process_single_order(self, order: Order, run_id: str | None = None) -> Dict:
        """Process a single order through V2 pipeline"""
        detail = {
            "order_id": order.order_id,
            "product": order.product_name,
            "quantity": order.quantity,
            "inventory_checked": True
        }
        
        # Step 1: Check inventory
        inventory_result = self.inventory_checker.check_order(order)
        detail["inventory_result"] = {
            "sufficient": inventory_result.sufficient,
            "material_needed_kg": float(inventory_result.material_needed_kg),
            "current_stock_kg": float(inventory_result.current_stock_kg),
            "shortfall_kg": float(inventory_result.shortfall_kg) if inventory_result.shortfall_kg else None
        }
        
        if not inventory_result.sufficient:
            # Step 2a: Insufficient stock - trigger reorder
            logger.info(
                "V2 run_id=%s order_id=%s: Insufficient stock, triggering reorder",
                run_id,
                order.order_id,
            )
            
            if inventory_result.material_id:
                from src.database.models import RawMaterial
                material = self.db.query(RawMaterial).filter(
                    RawMaterial.material_id == inventory_result.material_id
                ).first()
                
                if material:
                    reorder_result = self.reorder_agent.reorder_for_material(
                        material=material,
                        triggered_by="auto_order",
                        order_id=order.order_id
                    )
                    
                    detail["reorder_triggered"] = reorder_result.success
                    detail["reorder_result"] = {
                        "success": reorder_result.success,
                        "reorder_id": reorder_result.reorder_id,
                        "quantity_kg": float(reorder_result.quantity_kg),
                        "email_sent": reorder_result.email_sent
                    }
                    
                    # Order status is already updated to "awaiting_material" by reorder agent
                    detail["awaiting_material"] = True
                    detail["status"] = "awaiting_material"
                else:
                    detail["error"] = "Material not found for reorder"
            else:
                detail["error"] = "No material associated with this product"
        else:
            # Step 2b: Sufficient stock - schedule production
            logger.info(
                "V2 run_id=%s order_id=%s: Sufficient stock, scheduling production",
                run_id,
                order.order_id,
            )
            
            schedule_result = self.scheduler.schedule_order(order)
            
            detail["scheduled"] = schedule_result.success
            detail["schedule_result"] = {
                "success": schedule_result.success,
                "schedule_id": schedule_result.schedule_id,
                "machine_id": schedule_result.machine_id,
                "machine_name": schedule_result.machine_name,
                "estimated_hours": schedule_result.estimated_hours
            }
            
            if schedule_result.success:
                detail["status"] = "scheduled"
            else:
                detail["status"] = "new"  # Keep as new if scheduling failed
                detail["error"] = schedule_result.message
        
        return detail
    
    def process_awaiting_material_orders(self) -> Dict:
        """
        Check orders awaiting material and schedule if stock now available.
        
        Called periodically to check if reorders have been fulfilled.
        """
        result = {
            "checked": 0,
            "scheduled": 0,
            "still_waiting": 0,
            "errors": 0
        }
        
        # Get orders awaiting material
        awaiting_orders = self.db.query(Order).filter(
            Order.status == "awaiting_material"
        ).all()
        
        result["checked"] = len(awaiting_orders)
        logger.info("V2 awaiting_check: Checking %s orders awaiting material", len(awaiting_orders))
        
        for order in awaiting_orders:
            try:
                # Re-check inventory
                inventory_result = self.inventory_checker.check_order(order)
                
                if inventory_result.sufficient:
                    # Stock now available - schedule it
                    schedule_result = self.scheduler.schedule_order(order)
                    
                    if schedule_result.success:
                        result["scheduled"] += 1
                        logger.info(
                            "V2 awaiting_check order_id=%s: Scheduled after material arrival",
                            order.order_id,
                        )
                    else:
                        result["still_waiting"] += 1
                else:
                    result["still_waiting"] += 1
                    
            except Exception as e:
                logger.error(
                    "V2 awaiting_check order_id=%s: Error checking awaiting order: %s",
                    order.order_id,
                    e,
                )
                result["errors"] += 1
        
        return result
    
    def get_dashboard_stats(self) -> Dict:
        """Get statistics for V2 dashboard"""
        from src.database.models import RawMaterial, Machine, ProductionSchedule
        
        # Inventory stats
        low_stock = self.db.query(RawMaterial).filter(
            RawMaterial.current_stock_kg <= RawMaterial.reorder_level_kg
        ).count()
        
        total_materials = self.db.query(RawMaterial).count()
        
        # Machine stats
        machine_stats = self.scheduler.get_machine_utilization()
        
        # Production stats
        active_schedules = self.db.query(ProductionSchedule).filter(
            ProductionSchedule.status.in_(["scheduled", "in_production"])
        ).count()
        
        delayed = self.db.query(ProductionSchedule).filter(
            ProductionSchedule.status == "in_production",
            ProductionSchedule.delay_alert_sent == True
        ).count()
        
        # Order stats
        awaiting_material = self.db.query(Order).filter(
            Order.status == "awaiting_material"
        ).count()
        
        return {
            "inventory": {
                "total_materials": total_materials,
                "low_stock_count": low_stock,
                "healthy_percentage": ((total_materials - low_stock) / total_materials * 100) 
                                       if total_materials > 0 else 0
            },
            "machines": machine_stats,
            "production": {
                "active_schedules": active_schedules,
                "delayed_count": delayed
            },
            "orders": {
                "awaiting_material": awaiting_material
            }
        }
    
    def close(self):
        """Close database session if we created it"""
        if hasattr(self, 'db') and self.db:
            self.db.close()


# Convenience function for background tasks
def run_v2_processing(email_sender=None) -> Dict:
    """
    Run V2 processing pipeline (convenience function for scheduler).
    
    Returns:
        Dict with processing results
    """
    processor = None
    try:
        processor = V2Processor(email_sender=email_sender)
        
        # Process new orders
        result = processor.process_new_orders()
        
        # Check awaiting orders
        awaiting_result = processor.process_awaiting_material_orders()
        
        return {
            "new_orders": result.to_dict(),
            "awaiting_orders": awaiting_result,
            "success": True
        }
    except Exception as e:
        logger.error(f"V2 processing failed: {e}")
        return {
            "error": str(e),
            "success": False
        }
    finally:
        if processor:
            processor.close()
