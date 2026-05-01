"""
V3 Dispatch Watcher.
Finds orders that are ready for dispatch (completed + not yet dispatched).
Uses dispatch_email_sent flag for dedup protection.
"""

from sqlalchemy import or_

from src.database.models import Order


class DispatchWatcher:
    """Fetch candidate orders for dispatch operations."""

    def __init__(self, db_session):
        self.db = db_session

    def get_completed_orders(self):
        """
        Get orders that are completed but haven't been dispatched yet.

        Uses the dispatch_email_sent column for dedup:
        - Only returns orders with status='completed'
        - Excludes orders where dispatch_email_sent is already True
        - Orders by created_at ascending (oldest first)
        """
        return (
            self.db.query(Order)
            .filter(
                Order.status == "completed",
                or_(
                    Order.dispatch_email_sent == False,
                    Order.dispatch_email_sent.is_(None),
                ),
            )
            .order_by(Order.created_at.asc())
            .all()
        )
