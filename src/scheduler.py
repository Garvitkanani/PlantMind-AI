"""
Background Task Scheduler for PlantMind AI V2

Runs periodic tasks:
- V2 processing every 60 seconds (check new orders, inventory, scheduling)
- Low stock check every 30 minutes
- Machine maintenance reminders (daily)
"""

import logging
import threading
import time
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: BackgroundScheduler | None = None


def v2_processing_job():
    """Background job to run V2 processing pipeline"""
    try:
        from src.processors.v2_processor import run_v2_processing
        
        logger.debug("Running V2 processing job...")
        result = run_v2_processing()
        
        if result.get("success"):
            new_orders = result.get("new_orders", {})
            logger.info(
                f"V2 processing complete: {new_orders.get('total_orders', 0)} orders checked, "
                f"{new_orders.get('scheduled', 0)} scheduled, "
                f"{new_orders.get('awaiting_material', 0)} awaiting material"
            )
        else:
            logger.error(f"V2 processing failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"V2 processing job error: {e}")


def low_stock_check_job():
    """Background job to check and reorder low stock materials"""
    try:
        from src.database.connection import SessionLocal
        from src.agents.reorder_agent import create_reorder_agent
        from src.database.models import RawMaterial
        
        logger.info("Running low stock check...")
        
        db = SessionLocal()
        try:
            agent = create_reorder_agent(db)
            results = agent.check_and_reorder_low_stock()
            
            if results:
                logger.info(f"Created {len(results)} reorders for low stock materials")
            else:
                logger.info("No materials need reordering")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Low stock check job error: {e}")


def v3_dispatch_job():
    """Background job to process completed orders for dispatch."""
    try:
        from src.processors.v3_processor import run_v3_dispatch

        logger.debug("Running V3 dispatch job...")
        result = run_v3_dispatch()
        if result.get("success"):
            logger.info(
                "V3 dispatch complete: dispatched=%s skipped=%s",
                result.get("dispatched", 0),
                result.get("skipped", 0),
            )
        else:
            logger.error("V3 dispatch failed: %s", result.get("error"))
    except Exception as e:
        logger.error("V3 dispatch job error: %s", e)


def v3_mis_report_job():
    """Daily MIS report job."""
    try:
        from src.processors.v3_processor import run_v3_mis_report

        logger.info("Running V3 MIS report job...")
        result = run_v3_mis_report()
        if result.get("success"):
            logger.info("V3 MIS report generated successfully")
        else:
            logger.error("V3 MIS report failed: %s", result.get("error"))
    except Exception as e:
        logger.error("V3 MIS report job error: %s", e)


def start_scheduler():
    """Start the background task scheduler"""
    global _scheduler
    
    if _scheduler is not None:
        logger.warning("Scheduler already running")
        return
    
    _scheduler = BackgroundScheduler()
    
    # V2 processing every 60 seconds (check new orders)
    _scheduler.add_job(
        v2_processing_job,
        trigger=IntervalTrigger(seconds=60),
        id="v2_processing",
        name="V2 Order Processing",
        replace_existing=True
    )
    
    # Low stock check every 30 minutes
    _scheduler.add_job(
        low_stock_check_job,
        trigger=IntervalTrigger(minutes=30),
        id="low_stock_check",
        name="Low Stock Check",
        replace_existing=True
    )

    # V3 dispatch processing every 5 minutes
    _scheduler.add_job(
        v3_dispatch_job,
        trigger=IntervalTrigger(minutes=5),
        id="v3_dispatch",
        name="V3 Dispatch Processing",
        replace_existing=True,
    )

    # V3 daily MIS report at 09:00 local server time
    _scheduler.add_job(
        v3_mis_report_job,
        trigger=CronTrigger(hour=9, minute=0),
        id="v3_mis_report",
        name="V3 Daily MIS Report",
        replace_existing=True,
    )
    
    _scheduler.start()
    logger.info(
        "Background scheduler started with jobs: V2 processing (60s), "
        "Low stock check (30min), V3 dispatch (5min), V3 MIS report (09:00 daily)"
    )


def stop_scheduler():
    """Stop the background task scheduler"""
    global _scheduler
    
    if _scheduler is None:
        return
    
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Background scheduler stopped")


def get_scheduler_status():
    """Get current scheduler status"""
    if _scheduler is None:
        return {"running": False, "jobs": []}
    
    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None
        })
    
    return {"running": True, "jobs": jobs}
