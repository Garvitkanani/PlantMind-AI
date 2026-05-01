"""
V3 Dispatch Agent.
Builds AI-generated dispatch confirmation emails using Phi-3 Mini,
sends via Gmail SMTP, logs to dispatch_log, and marks orders as dispatched.

Key features:
- Phi-3 Mini AI-generated professional dispatch emails
- dispatch_email_sent dedup prevents re-sending
- Full audit trail via DispatchLog and OrderStatusLog
- Retry-safe email sending with error logging
"""

import os
import logging
from datetime import datetime, timezone
from uuid import uuid4

from src.database.models import DispatchLog, EmailLog, OrderStatusLog
from src.gmail.gmail_sender import gmail_sender
from src.models.ollama_phi3 import OllamaPhi3

logger = logging.getLogger(__name__)


def utc_now():
    return datetime.now(timezone.utc)


class DispatchAgent:
    """Create AI-generated dispatch emails and update order state."""

    def __init__(self, db_session, email_sender=None):
        self.db = db_session
        self.email_sender = email_sender or gmail_sender
        self.ai_model = OllamaPhi3()
        self.factory_name = os.environ.get("FACTORY_NAME", "PlantMind AI Factory")

    def dispatch_order(self, order):
        """
        Generate and send a dispatch confirmation email for a completed order.

        Steps:
        1. Check dedup flag (dispatch_email_sent)
        2. Generate AI email body via Phi-3 Mini
        3. Send email via Gmail SMTP
        4. Log to email_log and dispatch_log
        5. Update order status to 'dispatched'
        6. Log status change to order_status_log

        Returns:
            dict with dispatch result details
        """
        # Dedup check — skip if already dispatched
        if getattr(order, "dispatch_email_sent", False):
            logger.info(
                "Order #%s already has dispatch_email_sent=True — skipping",
                order.order_id,
            )
            return {
                "order_id": order.order_id,
                "status": "already_dispatched",
                "skipped": True,
            }

        customer_email = order.customer.email if order.customer else ""
        customer_name = order.customer.name if order.customer else "Customer"

        # Step 1: Generate AI email body using Phi-3 Mini
        ai_body = self._generate_dispatch_body(
            customer_name=customer_name,
            order_id=order.order_id,
            product_name=order.product_name,
            quantity=order.quantity,
        )

        subject = (
            f"Your Order #{order.order_id} is Ready for Dispatch — {self.factory_name}"
        )

        # Step 2: Send email via Gmail SMTP
        send_result = self.email_sender.send_dispatch_confirmation(
            customer_email=customer_email,
            customer_name=customer_name,
            order_id=order.order_id,
            product_name=order.product_name,
            quantity=order.quantity,
            ai_generated_body=ai_body,
        )
        send_success = bool(send_result.get("success"))
        attempts = int(send_result.get("attempts", 0))
        error_details = send_result.get("error")

        # Step 3: Log to email_log
        email_log = EmailLog(
            gmail_message_id=f"dispatch-{order.order_id}-{uuid4().hex[:10]}",
            direction="out",
            from_address=self.email_sender.username if hasattr(self.email_sender, 'username') else "factory@plantmind.local",
            to_address=customer_email,
            subject=subject,
            body_summary=ai_body[:5000],
            attachment_name="",
            filter_decision="process",
            processing_status="success" if send_success else "error",
            linked_order_id=order.order_id,
            error_details=error_details,
            processed_at=utc_now(),
        )
        self.db.add(email_log)

        # Step 4: Log to dispatch_log
        dispatch_log = DispatchLog(
            order_id=order.order_id,
            customer_email=customer_email,
            email_subject=subject,
            email_body=ai_body[:10000],
            send_status="sent" if send_success else "failed",
            attempts=attempts,
            error_details=error_details,
            triggered_by="v3_dispatch_job",
        )
        self.db.add(dispatch_log)

        # Step 5: Update order status + dedup flags
        old_status = order.status
        order.status = "dispatched"
        order.dispatch_email_sent = True
        order.dispatch_sent_at = utc_now()

        # Step 6: Log status change for audit trail
        status_log = OrderStatusLog(
            order_id=order.order_id,
            old_status=old_status,
            new_status="dispatched",
            change_source="v3_processor",
            notes=f"Dispatch email {'sent' if send_success else 'failed'} to {customer_email}",
        )
        self.db.add(status_log)

        logger.info(
            "Order #%s dispatched: email_%s to %s",
            order.order_id,
            "sent" if send_success else "failed",
            customer_email,
        )

        return {
            "order_id": order.order_id,
            "status": "dispatched",
            "customer_email": customer_email,
            "email_send_status": dispatch_log.send_status,
            "ai_generated": True,
        }

    def _generate_dispatch_body(
        self,
        customer_name: str,
        order_id: int,
        product_name: str,
        quantity: int,
    ) -> str:
        """Generate dispatch email body using Phi-3 Mini AI."""
        try:
            body = self.ai_model.draft_dispatch_email(
                customer_name=customer_name,
                order_id=order_id,
                product_name=product_name,
                quantity=quantity,
                factory_name=self.factory_name,
            )
            logger.info("AI-generated dispatch email for order #%s", order_id)
            return body
        except Exception as e:
            logger.error("Phi-3 dispatch body generation failed: %s — using fallback", e)
            return self.ai_model._fallback_dispatch_email(
                customer_name, order_id, product_name, quantity, self.factory_name
            )
