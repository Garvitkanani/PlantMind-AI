"""
V1 Email Processor - Matches V1 Specification Exactly
Orchestrates the entire email processing pipeline as specified in V1_Smart_Order_Intake.md
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4


def utc_now():
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

from src.agents.email_filter_agent import EmailFilterAgent
from src.agents.email_reader_agent import EmailReaderAgent
from src.agents.order_extractor_agent import order_extractor
from src.database.connection import SessionLocal
from src.database.models import Customer, EmailLog, Order
from src.parsers.attachment_parser import attachment_parser

logger = logging.getLogger(__name__)


class V1EmailProcessor:
    """
    V1 Email Processor - Main orchestrator
    Follows the exact flow from V1 specification:
    1. Fetch unread emails via Email Reader Agent
    2. Filter emails via Email Filter Agent
    3. Parse attachments via Attachment Parser
    4. Extract order details via Order Extraction Agent
    5. Save to database and update dashboard
    """

    def __init__(self):
        self.email_reader = EmailReaderAgent()
        self.email_filter = EmailFilterAgent()
        self.order_extractor = order_extractor

    def process_new_emails(self, user_id: int = 1) -> Dict:
        """
        Main processing function - triggered by office staff clicking "Check New Emails" button
        Returns processing results summary
        """
        run_id = uuid4().hex[:12]
        summary = {
            "run_id": run_id,
            "total_emails": 0,
            "processed": 0,
            "skipped": 0,
            "flagged": 0,
            "already_processed": 0,
            "errors": 0,
            "orders_created": 0,
            "details": [],
        }

        try:
            # Step 1: Fetch unread emails
            logger.info("V1 run_id=%s user_id=%s: Fetching unread emails...", run_id, user_id)
            unread_emails = self.email_reader.get_unread_emails()

            if not unread_emails:
                logger.info("V1 run_id=%s: No unread emails found", run_id)
                return summary

            summary["total_emails"] = len(unread_emails)

            # Process each email
            for email in unread_emails:
                email_result = self._process_single_email(email, run_id=run_id)
                summary["details"].append(email_result)

                # Mark non-error emails as read so they are not reprocessed forever.
                message_id = email.get("message_id")
                if message_id and email_result["status"] in {
                    "processed",
                    "skipped",
                    "flagged",
                    "already_processed",
                }:
                    self.email_reader.mark_email_as_read(message_id)

                # Update summary counts
                if email_result["status"] == "processed":
                    summary["processed"] += 1
                    if email_result.get("order_created"):
                        summary["orders_created"] += 1
                elif email_result["status"] == "skipped":
                    summary["skipped"] += 1
                elif email_result["status"] == "flagged":
                    summary["flagged"] += 1
                    if email_result.get("order_created"):
                        summary["orders_created"] += 1
                elif email_result["status"] == "already_processed":
                    summary["already_processed"] += 1
                elif email_result["status"] == "error":
                    summary["errors"] += 1

            logger.info("V1 run_id=%s: Processing complete: %s", run_id, summary)
            return summary

        except Exception as e:
            logger.error("V1 run_id=%s: Processing error: %s", run_id, e)
            summary["error"] = str(e)
            return summary

    def _process_single_email(self, email: Dict, run_id: str | None = None) -> Dict:
        """
        Process a single email through the complete pipeline
        """
        email_id = email.get("id")
        message_id = email.get("message_id")
        sender = email.get("from_email") or email.get("from")
        subject = email.get("subject")
        body = email.get("body", "")
        attachments = email.get("attachments", [])

        result = {
            "email_id": email_id,
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
            "status": "pending",
            "filter_decision": None,
            "extraction_result": None,
            "order_created": False,
            "error": None,
        }

        db = SessionLocal()
        try:
            # Check if already processed
            existing_log = (
                db.query(EmailLog)
                .filter(EmailLog.gmail_message_id == message_id)
                .first()
            )

            if existing_log:
                result["status"] = "already_processed"
                result["filter_decision"] = existing_log.filter_decision
                result["processing_status"] = existing_log.processing_status
                return result

            # Step 2: Filter email
            filter_result = self.email_filter.filter_email(email)
            should_process = filter_result.get("should_process") or filter_result.get(
                "needs_review"
            )
            result["filter_decision"] = "process" if should_process else "skip"

            if not should_process:
                # Log skipped email
                self._log_email_skip(db, email)
                result["status"] = "skipped"
                db.commit()
                return result

            # Email passed filter, continue processing
            logger.info(
                "V1 run_id=%s message_id=%s: Processing email subject=%s",
                run_id,
                message_id,
                subject,
            )

            # Step 3: Parse attachments
            hydrated_attachments = self._hydrate_attachments(message_id, attachments)
            combined_text, attachment_info = attachment_parser.extract_all_text(
                hydrated_attachments, body
            )

            # Step 4: Extract order details using AI
            extraction_result = self.order_extractor.extract_order(
                combined_text, sender if sender else ""
            )
            result["extraction_result"] = extraction_result

            # Step 5: Handle extraction result
            if extraction_result["error"]:
                # Extraction failed
                self._log_email_error(db, email, extraction_result["error"])
                result["status"] = "error"
                result["error"] = extraction_result["error"]
                db.commit()  # Commit the error log

            elif extraction_result["is_complete"]:
                # All fields present - create order
                order_data = extraction_result["extracted_data"]
                order_id = self._create_order_from_extraction(
                    db, email, order_data, extraction_result["missing_fields"]
                )
                result["order_created"] = True
                result["status"] = "processed"

                # Update email log with success
                self._log_email_success(db, email, "process", order_id)

            else:
                # Missing fields - flag for manual review
                order_data = extraction_result["extracted_data"]
                order_id = self._create_flagged_order(
                    db, email, order_data, extraction_result["missing_fields"]
                )
                result["status"] = "flagged"
                result["order_created"] = True  # Still created but flagged

                # Update email log with flagged status
                self._log_email_flagged(
                    db, email, "process", order_id, extraction_result["missing_fields"]
                )

            db.commit()
            return result

        except Exception as e:
            db.rollback()
            logger.error(
                "V1 run_id=%s email_id=%s message_id=%s: Error processing email: %s",
                run_id,
                email_id,
                message_id,
                e,
            )
            result["status"] = "error"
            result["error"] = str(e)
            return result
        finally:
            db.close()

    def _log_email_skip(self, db, email: Dict) -> None:
        """Log skipped email to email_log table"""
        email_log = EmailLog(
            gmail_message_id=email.get("message_id"),
            direction="in",
            from_address=email.get("from_email") or email.get("from"),
            to_address=email.get("to_email") or email.get("to") or "",
            subject=email.get("subject", ""),
            body_summary=self._summarize_body(email.get("body", "")),
            attachment_name=self._get_attachment_names(email.get("attachments", [])),
            filter_decision="skip",
            processing_status="skipped",
            processed_at=utc_now(),
        )
        db.add(email_log)

    def _log_email_success(
        self, db, email: Dict, filter_decision: str, order_id: int
    ) -> None:
        """Log successfully processed email"""
        email_log = EmailLog(
            gmail_message_id=email.get("message_id"),
            direction="in",
            from_address=email.get("from_email") or email.get("from"),
            to_address=email.get("to_email") or email.get("to") or "",
            subject=email.get("subject", ""),
            body_summary=self._summarize_body(email.get("body", "")),
            attachment_name=self._get_attachment_names(email.get("attachments", [])),
            filter_decision=filter_decision,
            processing_status="success",
            linked_order_id=order_id,
            processed_at=utc_now(),
        )
        db.add(email_log)

    def _log_email_flagged(
        self, db, email: Dict, filter_decision: str, order_id: int, missing_fields: List
    ) -> None:
        """Log flagged email (needs manual review)"""
        email_log = EmailLog(
            gmail_message_id=email.get("message_id"),
            direction="in",
            from_address=email.get("from_email") or email.get("from"),
            to_address=email.get("to_email") or email.get("to") or "",
            subject=email.get("subject", ""),
            body_summary=self._summarize_body(email.get("body", "")),
            attachment_name=self._get_attachment_names(email.get("attachments", [])),
            filter_decision=filter_decision,
            processing_status="flagged",
            linked_order_id=order_id,
            error_details=f"Missing fields: {missing_fields}",
            processed_at=utc_now(),
        )
        db.add(email_log)

    def _log_email_error(self, db, email: Dict, error_message: str) -> None:
        """Log email processing error"""
        email_log = EmailLog(
            gmail_message_id=email.get("message_id"),
            direction="in",
            from_address=email.get("from_email") or email.get("from"),
            to_address=email.get("to_email") or email.get("to") or "",
            subject=email.get("subject", ""),
            body_summary=self._summarize_body(email.get("body", "")),
            attachment_name=self._get_attachment_names(email.get("attachments", [])),
            filter_decision="process",  # Originally passed filter
            processing_status="error",
            error_details=error_message,
            processed_at=utc_now(),
        )
        db.add(email_log)

    def _create_order_from_extraction(
        self, db, email: Dict, order_data: Dict, missing_fields: List
    ) -> int:
        """Create order from successfully extracted data"""
        # Find or create customer
        customer_email = (
            email.get("from_email")
            or email.get("from")
            or order_data.get("customer_email")
        )
        customer = db.query(Customer).filter(Customer.email == customer_email).first()

        if not customer:
            customer = Customer(
                name=order_data.get("customer_name", "Unknown Customer"),
                email=customer_email,
                created_at=utc_now(),
            )
            db.add(customer)
            db.flush()  # Get customer_id

        # Parse delivery date
        delivery_date_str = order_data.get("delivery_date")
        delivery_date = None
        if delivery_date_str:
            try:
                delivery_date = datetime.strptime(delivery_date_str, "%Y-%m-%d").date()
            except ValueError:
                delivery_date = None

        # Create order
        order = Order(
            customer_id=customer.customer_id,
            product_name=order_data.get("product_name", "Unknown Product"),
            quantity=order_data.get("quantity", 0),
            required_delivery_date=delivery_date,
            special_instructions=order_data.get("special_instructions", ""),
            status="new",
            created_at=utc_now(),
        )
        db.add(order)
        db.flush()  # Get order_id

        return int(order.order_id)

    def _create_flagged_order(
        self, db, email: Dict, order_data: Dict, missing_fields: List
    ) -> int:
        """Create order but flag it for manual review"""
        # Find or create customer
        customer_email = (
            email.get("from_email")
            or email.get("from")
            or order_data.get("customer_email")
        )
        customer = db.query(Customer).filter(Customer.email == customer_email).first()

        if not customer:
            customer = Customer(
                name=order_data.get("customer_name", "Customer Needs Review"),
                email=customer_email,
                created_at=utc_now(),
            )
            db.add(customer)
            db.flush()

        # Parse delivery date if present
        delivery_date_str = order_data.get("delivery_date")
        delivery_date = None
        if delivery_date_str:
            try:
                delivery_date = datetime.strptime(delivery_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        # Create order with flagged status
        order = Order(
            customer_id=customer.customer_id,
            product_name=order_data.get("product_name", "Product Needs Review"),
            quantity=order_data.get("quantity", 0) or 0,
            required_delivery_date=delivery_date,
            special_instructions=order_data.get("special_instructions", ""),
            status="needs_review",  # Flagged status
            created_at=utc_now(),
        )
        db.add(order)
        db.flush()

        return int(order.order_id)

    def _summarize_body(self, body: str, max_length: int = 5000) -> str:
        """Store a long-form body preview for dashboard email modal."""
        if not body:
            return ""
        if len(body) <= max_length:
            return body
        return body[:max_length] + "..."

    def _get_attachment_names(self, attachments: List) -> str:
        """Get comma-separated list of attachment names"""
        if not attachments:
            return ""
        names = [att.get("filename", "unnamed") for att in attachments]
        return ", ".join(names)

    def _hydrate_attachments(
        self, message_id: str | None, attachments: List[Dict]
    ) -> List[Dict]:
        """
        Fetch attachment bytes from Gmail and return parser-ready attachments.
        """
        if not message_id or not attachments:
            return []

        hydrated = []
        for attachment in attachments:
            attachment_id = attachment.get("attachmentId")
            if not attachment_id:
                continue
            data = self.email_reader.download_attachment_data(message_id, attachment_id)
            hydrated.append(
                {
                    "filename": attachment.get("filename", ""),
                    "mimeType": attachment.get("mimeType", ""),
                    "data": data,
                }
            )
        return hydrated


# Singleton instance
v1_email_processor = V1EmailProcessor()
