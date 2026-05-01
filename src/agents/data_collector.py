"""
V3 MIS Data Collector.
Collects key operational metrics from the database for owner MIS reporting.

Metrics collected:
  - Active orders (new/scheduled/in_production/awaiting_material)
  - Completed orders (ready for dispatch)
  - Dispatched orders (sent to customer)
  - Low stock materials (below reorder level)
  - Pending reorders (awaiting supplier delivery)
  - Running machines / total machines
  - Delayed production schedules
"""

import logging

from src.database.models import Machine, Order, ProductionSchedule, RawMaterial, ReorderLog

logger = logging.getLogger(__name__)


class MisDataCollector:
    """Collect daily factory metrics from the database."""

    def __init__(self, db_session):
        self.db = db_session

    def collect(self):
        """
        Collect all metrics for MIS report generation.

        Returns:
            dict with all factory-wide metrics
        """
        return self.collect_summary()

    def collect_summary(self):
        """Collect summary metrics from the database."""
        active_orders = (
            self.db.query(Order)
            .filter(Order.status.in_(["new", "scheduled", "in_production", "awaiting_material"]))
            .count()
        )
        completed_orders = self.db.query(Order).filter(Order.status == "completed").count()
        dispatched_orders = self.db.query(Order).filter(Order.status == "dispatched").count()
        low_stock_materials = (
            self.db.query(RawMaterial)
            .filter(RawMaterial.current_stock_kg <= RawMaterial.reorder_level_kg)
            .count()
        )
        pending_reorders = (
            self.db.query(ReorderLog)
            .filter(ReorderLog.status.in_(["pending", "ordered", "confirmed"]))
            .count()
        )
        running_machines = self.db.query(Machine).filter(Machine.status == "running").count()
        total_machines = self.db.query(Machine).filter(Machine.is_active.is_(True)).count()
        delayed_schedules = (
            self.db.query(ProductionSchedule)
            .filter(
                ProductionSchedule.status == "in_production",
                ProductionSchedule.delay_alert_sent.is_(True),
            )
            .count()
        )

        summary = {
            "active_orders": active_orders,
            "completed_orders": completed_orders,
            "dispatched_orders": dispatched_orders,
            "low_stock_materials": low_stock_materials,
            "pending_reorders": pending_reorders,
            "running_machines": running_machines,
            "total_machines": total_machines,
            "delayed_schedules": delayed_schedules,
        }

        logger.info(
            "MIS metrics collected: active=%d, completed=%d, dispatched=%d, low_stock=%d",
            active_orders, completed_orders, dispatched_orders, low_stock_materials,
        )

        return summary
