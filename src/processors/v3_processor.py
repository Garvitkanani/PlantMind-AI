"""
V3 Processor — Dispatch & MIS Report Pipeline

Orchestrates:
  1. Dispatch pipeline: find completed orders → generate AI email → send → log
  2. MIS report pipeline: collect metrics → generate AI report → send → log

Both pipelines are idempotent (safe to re-run) thanks to dispatch_email_sent dedup
and report_date uniqueness in mis_report_log.
"""

import logging
import os
from datetime import datetime, timezone

from src.database.connection import SessionLocal
from src.agents.dispatch_watcher import DispatchWatcher
from src.agents.dispatch_agent import DispatchAgent
from src.agents.data_collector import MisDataCollector
from src.agents.mis_report_agent import MisReportAgent

logger = logging.getLogger(__name__)


def run_v3_dispatch() -> dict:
    """
    V3 Dispatch Pipeline.

    Steps:
    1. DispatchWatcher finds completed orders (not yet dispatched)
    2. DispatchAgent generates AI email and sends via SMTP
    3. Logs to dispatch_log and order_status_log
    4. Marks order as dispatched with dedup flag

    Returns:
        dict with pipeline results
    """
    db = SessionLocal()
    try:
        watcher = DispatchWatcher(db)
        agent = DispatchAgent(db_session=db)

        # Find orders ready for dispatch
        completed_orders = watcher.get_completed_orders()
        logger.info(f"V3 Dispatch: Found {len(completed_orders)} orders ready for dispatch")

        if not completed_orders:
            return {
                "success": True,
                "message": "No orders ready for dispatch",
                "dispatched": 0,
                "skipped": 0,
            }

        results = []
        dispatched_count = 0
        skipped_count = 0

        for order in completed_orders:
            try:
                result = agent.dispatch_order(order)
                results.append(result)

                if result.get("skipped"):
                    skipped_count += 1
                else:
                    dispatched_count += 1

            except Exception as e:
                logger.error(f"Dispatch failed for order #{order.order_id}: {e}")
                results.append({
                    "order_id": order.order_id,
                    "status": "error",
                    "error": str(e),
                })

        # Commit all changes at once
        db.commit()

        logger.info(
            f"V3 Dispatch complete: {dispatched_count} dispatched, {skipped_count} skipped"
        )

        return {
            "success": True,
            "message": f"Dispatched {dispatched_count} order(s)",
            "dispatched": dispatched_count,
            "skipped": skipped_count,
            "details": results,
        }

    except Exception as e:
        logger.error(f"V3 Dispatch pipeline error: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def run_v3_mis_report() -> dict:
    """
    V3 MIS Report Pipeline.

    Steps:
    1. MisDataCollector gathers factory-wide metrics
    2. MisReportAgent generates AI report via Mistral 7B
    3. Quality validation + auto-regeneration if needed
    4. Send via Gmail SMTP to owner
    5. Log to mis_report_log and email_log

    Returns:
        dict with pipeline results
    """
    db = SessionLocal()
    try:
        owner_email = os.environ.get("OWNER_REPORT_EMAIL", "owner@factory.com")
        report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Step 1: Collect metrics
        collector = MisDataCollector(db)
        summary = collector.collect()

        logger.info(f"V3 MIS: Collected metrics for {report_date}: {summary}")

        # Step 2: Generate AI report with quality validation
        agent = MisReportAgent(db)
        body = agent.build_report_body(report_date, summary)

        # Step 3: Send email and log
        subject = agent.log_report(report_date, owner_email, body)

        # Commit logs
        db.commit()

        word_count = len(body.split())
        logger.info(
            f"V3 MIS Report complete: date={report_date}, words={word_count}, sent to {owner_email}"
        )

        return {
            "success": True,
            "message": f"MIS report generated and sent to {owner_email}",
            "report_date": report_date,
            "word_count": word_count,
            "subject": subject,
        }

    except Exception as e:
        logger.error(f"V3 MIS Report pipeline error: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


class V3Processor:
    """
    Class-based wrapper around the V3 dispatch and MIS report pipelines.

    Accepts an injected db_session so it can be used in tests without
    creating a new database connection.  The existing module-level
    functions (run_v3_dispatch / run_v3_mis_report) are unchanged and
    continue to be used by the scheduler.
    """

    def __init__(self, db_session, email_sender=None):
        self.db = db_session
        self.email_sender = email_sender

    # ------------------------------------------------------------------
    # Dispatch pipeline
    # ------------------------------------------------------------------

    def process_completed_orders(self) -> dict:
        """
        Find completed orders and send dispatch confirmation emails.

        Returns:
            dict with keys: completed_found, dispatched, skipped, details
        """
        watcher = DispatchWatcher(self.db)
        agent_kwargs = {"db_session": self.db}
        if self.email_sender is not None:
            agent_kwargs["email_sender"] = self.email_sender
        agent = DispatchAgent(**agent_kwargs)

        completed_orders = watcher.get_completed_orders()
        completed_found = len(completed_orders)

        results = []
        dispatched_count = 0
        skipped_count = 0

        for order in completed_orders:
            try:
                result = agent.dispatch_order(order)
                results.append(result)
                if result.get("skipped"):
                    skipped_count += 1
                else:
                    dispatched_count += 1
            except Exception as e:
                logger.error("Dispatch failed for order #%s: %s", order.order_id, e)
                results.append({
                    "order_id": order.order_id,
                    "status": "error",
                    "error": str(e),
                })

        self.db.commit()

        return {
            "completed_found": completed_found,
            "dispatched": dispatched_count,
            "skipped": skipped_count,
            "details": results,
        }

    # ------------------------------------------------------------------
    # MIS report pipeline
    # ------------------------------------------------------------------

    def generate_daily_mis_report(self) -> dict:
        """
        Collect factory metrics, generate an AI MIS report, and send it.

        Returns:
            dict with keys: summary, owner_email, report_date, word_count
        """
        owner_email = os.environ.get("OWNER_REPORT_EMAIL", "owner@factory.com")
        report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        collector = MisDataCollector(self.db)
        summary = collector.collect()

        agent_kwargs = {"db_session": self.db}
        if self.email_sender is not None:
            agent_kwargs["email_sender"] = self.email_sender
        agent = MisReportAgent(**agent_kwargs)

        body = agent.build_report_body(report_date, summary)
        agent.log_report(report_date, owner_email, body)

        self.db.commit()

        word_count = len(body.split())
        logger.info(
            "V3Processor MIS report complete: date=%s, words=%d, sent to %s",
            report_date,
            word_count,
            owner_email,
        )

        return {
            "summary": summary,
            "owner_email": owner_email,
            "report_date": report_date,
            "word_count": word_count,
        }
