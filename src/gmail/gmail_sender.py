"""
Gmail SMTP Sender
Production-grade email delivery with retry logic and error handling.

Uses Gmail SMTP with App Password for outbound emails:
- Dispatch confirmations to customers
- Reorder requests to suppliers  
- Delay alerts to owner
- Daily MIS reports to owner
"""

import logging
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

logger = logging.getLogger(__name__)


class GmailSender:
    """
    Production-grade Gmail SMTP sender with:
    - Retry logic with exponential backoff
    - HTML and plain text support
    - Batch sending capabilities
    - Comprehensive error handling
    """
    
    def __init__(self):
        self.smtp_server = os.environ.get("GMAIL_SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.environ.get("GMAIL_SMTP_PORT", "587"))
        self.username = os.environ.get("GMAIL_SMTP_EMAIL", "").strip()
        self.app_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
        self.from_name = os.environ.get("FACTORY_NAME", "PlantMind AI Factory")
        self.enabled = bool(self.username and self.app_password)
        
        if not self.enabled:
            logger.warning(
                "Gmail SMTP not fully configured. "
                "Set GMAIL_SMTP_EMAIL and GMAIL_APP_PASSWORD in .env"
            )
    
    def _create_message(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> MIMEMultipart:
        """Create MIME message with both plain text and HTML versions."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.username}>"
        msg["To"] = to
        
        if cc:
            msg["Cc"] = ", ".join(cc)
        if bcc:
            msg["Bcc"] = ", ".join(bcc)
        
        # Plain text part
        part1 = MIMEText(body_text, "plain", "utf-8")
        msg.attach(part1)
        
        # HTML part (if provided)
        if body_html:
            part2 = MIMEText(body_html, "html", "utf-8")
            msg.attach(part2)
        
        return msg
    
    def _send_with_retry(
        self,
        msg: MIMEMultipart,
        to_addresses: List[str],
        max_retries: int = 3,
        base_delay: float = 1.0
    ) -> dict:
        """
        Send email with exponential backoff retry.
        
        Returns:
            dict with success status and details
        """
        for attempt in range(max_retries):
            try:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                    server.starttls()
                    server.login(self.username, self.app_password)
                    server.send_message(msg, to_addrs=to_addresses)
                
                logger.info(f"Email sent successfully to {to_addresses}")
                return {
                    "success": True,
                    "attempts": attempt + 1,
                    "recipients": to_addresses
                }
                
            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP Authentication failed: {e}")
                return {
                    "success": False,
                    "error": "Authentication failed. Check GMAIL_SMTP_EMAIL and GMAIL_APP_PASSWORD.",
                    "attempts": attempt + 1
                }
                
            except Exception as e:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"Email send attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                if attempt < max_retries - 1:
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries} attempts failed to send email")
                    return {
                        "success": False,
                        "error": str(e),
                        "attempts": max_retries
                    }
        
        return {"success": False, "error": "Unknown error", "attempts": max_retries}
    
    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> dict:
        """
        Send a single email.
        
        Args:
            to: Primary recipient email
            subject: Email subject
            body: Plain text body
            body_html: Optional HTML version
            cc: Carbon copy recipients
            bcc: Blind carbon copy recipients
            
        Returns:
            dict with success status
        """
        if not self.enabled:
            logger.warning("Email sending disabled - SMTP not configured")
            return {
                "success": False,
                "error": "SMTP not configured",
                "sent": False
            }
        
        # Build recipient list for SMTP
        all_recipients = [to]
        if cc:
            all_recipients.extend(cc)
        if bcc:
            all_recipients.extend(bcc)
        
        # Create message
        msg = self._create_message(to, subject, body, body_html, cc, bcc)
        
        # Send with retry
        result = self._send_with_retry(msg, all_recipients)
        result["subject"] = subject
        result["recipient"] = to
        
        return result
    
    def send_dispatch_confirmation(
        self,
        customer_email: str,
        customer_name: str,
        order_id: int,
        product_name: str,
        quantity: int,
        ai_generated_body: str
    ) -> dict:
        """
        Send dispatch confirmation email to customer.
        Uses AI-generated body from Phi-3 Mini.
        """
        subject = f"Your Order #{order_id} is Ready for Dispatch — {self.from_name}"
        
        # Create professional HTML version
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4f46e5; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
                .footer {{ background: #f3f4f6; padding: 20px; text-align: center; font-size: 12px; color: #6b7280; }}
                .order-details {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .detail-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #e5e7eb; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🏭 Order Dispatch Confirmation</h2>
                </div>
                <div class="content">
                    <p>Dear {customer_name},</p>
                    <div class="order-details">
                        <div class="detail-row"><strong>Order ID:</strong> <span>#{order_id}</span></div>
                        <div class="detail-row"><strong>Product:</strong> <span>{product_name}</span></div>
                        <div class="detail-row"><strong>Quantity:</strong> <span>{quantity:,} units</span></div>
                    </div>
                    <div style="white-space: pre-wrap; margin-top: 20px;">{ai_generated_body}</div>
                </div>
                <div class="footer">
                    <p>{self.from_name} | Automated by PlantMind AI</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(
            to=customer_email,
            subject=subject,
            body=ai_generated_body,
            body_html=html_body
        )
    
    def send_reorder_request(
        self,
        supplier_email: str,
        supplier_name: str,
        material_name: str,
        quantity_kg: float,
        ai_generated_body: str
    ) -> dict:
        """
        Send reorder request email to supplier.
        Uses AI-generated body from Phi-3 Mini.
        """
        subject = f"Reorder Request: {material_name} — {quantity_kg}kg — {self.from_name}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #059669; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
                .material-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; 
                                  border-left: 4px solid #059669; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>📦 Material Reorder Request</h2>
                </div>
                <div class="content">
                    <p>Dear {supplier_name},</p>
                    <div class="material-box">
                        <h3>{material_name}</h3>
                        <p><strong>Quantity Required:</strong> {quantity_kg} kg</p>
                    </div>
                    <div style="white-space: pre-wrap; margin-top: 20px;">{ai_generated_body}</div>
                </div>
                <div style="background: #f3f4f6; padding: 20px; text-align: center; font-size: 12px; color: #6b7280;">
                    <p>{self.from_name} Procurement Team</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(
            to=supplier_email,
            subject=subject,
            body=ai_generated_body,
            body_html=html_body
        )
    
    def send_delay_alert(
        self,
        owner_email: str,
        order_id: int,
        product_name: str,
        customer_name: str,
        original_deadline: str,
        new_eta: str,
        pieces_completed: int,
        total_pieces: int,
        ai_generated_body: str
    ) -> dict:
        """
        Send production delay alert to factory owner.
        Uses AI-generated body from Phi-3 Mini.
        """
        subject = f"🚨 PRODUCTION DELAY: Order #{order_id} — {product_name}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .alert-banner {{ background: #dc2626; color: white; padding: 20px; 
                                  border-radius: 8px 8px 0 0; text-align: center; }}
                .content {{ background: #fef2f2; padding: 30px; border: 1px solid #fecaca; }}
                .delay-box {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0;
                              border-left: 4px solid #dc2626; }}
                .progress-bar {{ background: #e5e7eb; height: 20px; border-radius: 10px; overflow: hidden; }}
                .progress-fill {{ background: #dc2626; height: 100%; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="alert-banner">
                    <h2>⚠️ Production Delay Detected</h2>
                </div>
                <div class="content">
                    <div class="delay-box">
                        <h3>Order #{order_id} — {product_name}</h3>
                        <p><strong>Customer:</strong> {customer_name}</p>
                        <p><strong>Original Deadline:</strong> {original_deadline}</p>
                        <p><strong>New ETA:</strong> {new_eta}</p>
                        <div style="margin-top: 15px;">
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: {(pieces_completed/total_pieces)*100}%"></div>
                            </div>
                            <p style="text-align: center; margin-top: 8px;">
                                {pieces_completed:,} / {total_pieces:,} pieces completed
                            </p>
                        </div>
                    </div>
                    <div style="white-space: pre-wrap; margin-top: 20px;">{ai_generated_body}</div>
                </div>
                <div style="background: #f3f4f6; padding: 20px; text-align: center; font-size: 12px; color: #6b7280;">
                    <p>PlantMind AI Production Management System</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(
            to=owner_email,
            subject=subject,
            body=ai_generated_body,
            body_html=html_body
        )
    
    def send_mis_report(
        self,
        owner_email: str,
        report_date: str,
        ai_generated_report: str,
        summary_stats: dict
    ) -> dict:
        """
        Send daily MIS report to factory owner.
        Uses AI-generated report from Mistral 7B.
        """
        subject = f"PlantMind AI — Daily Factory Report | {report_date}"
        
        # Build stats cards HTML
        stats_html = ""
        if summary_stats:
            stats_html = "<div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0;'>"
            for key, value in summary_stats.items():
                stats_html += f"""
                <div style="background: white; padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #4f46e5;">{value}</div>
                    <div style="font-size: 12px; color: #6b7280; text-transform: uppercase;">{key}</div>
                </div>
                """
            stats_html += "</div>"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%); 
                           color: white; padding: 30px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; }}
                .report-box {{ background: white; padding: 25px; border-radius: 8px; margin: 20px 0;
                              box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
                .section-title {{ color: #4f46e5; border-bottom: 2px solid #4f46e5; 
                                  padding-bottom: 8px; margin-top: 25px; }}
                .footer {{ background: #f3f4f6; padding: 20px; text-align: center; 
                          font-size: 12px; color: #6b7280; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏭 Daily Factory Report</h1>
                    <p>{report_date}</p>
                </div>
                <div class="content">
                    {stats_html}
                    <div class="report-box">
                        <div style="white-space: pre-wrap;">{ai_generated_report}</div>
                    </div>
                </div>
                <div class="footer">
                    <p><strong>PlantMind AI</strong> | Automated Factory Intelligence</p>
                    <p>This report was generated automatically at 9:00 AM</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(
            to=owner_email,
            subject=subject,
            body=ai_generated_report,
            body_html=html_body
        )


# Singleton instance
gmail_sender = GmailSender()
