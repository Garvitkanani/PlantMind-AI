"""
Reorder Agent - V2 Production & Inventory Brain

Responsibility:
- Determine reorder quantity from raw_materials table
- Use Phi-3 Mini to draft professional reorder email
- Send email via Gmail SMTP to supplier
- Log reorder in reorder_log table
- Update order status to 'awaiting_material' if triggered by order

AI Model: Phi-3 Mini Q4_K_M (fast, lightweight — email drafting is simple)
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import RawMaterial, ReorderLog, Supplier, Order, OrderStatusLog
from src.gmail.gmail_sender import gmail_sender
from src.models.ollama_phi3 import OllamaPhi3

logger = logging.getLogger(__name__)


@dataclass
class ReorderResult:
    """Result of a reorder operation"""
    success: bool
    reorder_id: Optional[int]
    email_sent: bool
    supplier_email: Optional[str]
    quantity_kg: Decimal
    message: str
    email_subject: Optional[str] = None
    email_body: Optional[str] = None


class ReorderAgent:
    """
    Reorder Agent
    
    Automatically reorders raw materials from suppliers when stock is low.
    Uses AI to draft professional emails and sends via Gmail SMTP.
    """
    
    def __init__(self, db_session: Session, email_sender=None):
        self.db = db_session
        self.ai_model = OllamaPhi3()
        self.email_sender = email_sender  # Optional email sender (Gmail SMTP)
    
    def reorder_for_material(
        self,
        material: RawMaterial,
        triggered_by: str = "auto_order",
        order_id: Optional[int] = None,
        custom_quantity: Optional[Decimal] = None
    ) -> ReorderResult:
        """
        Create and send a reorder for a specific material.
        
        Args:
            material: RawMaterial to reorder
            triggered_by: 'auto_order', 'manual_store', 'system_alert', or 'scheduled'
            order_id: Associated order ID (if triggered by order check)
            custom_quantity: Optional custom quantity (uses material.reorder_quantity_kg if None)
            
        Returns:
            ReorderResult with status and details
        """
        logger.info(f"Starting reorder for material: {material.name}")
        
        # Step 1: Get supplier details
        supplier = self._get_supplier(material.supplier_id)
        if not supplier:
            logger.error(f"No supplier found for material {material.name}")
            return ReorderResult(
                success=False,
                reorder_id=None,
                email_sent=False,
                supplier_email=None,
                quantity_kg=custom_quantity or Decimal(str(material.reorder_quantity_kg)),
                message=f"No supplier configured for {material.name}"
            )
        
        # Step 2: Determine reorder quantity
        quantity = custom_quantity or Decimal(str(material.reorder_quantity_kg))
        
        # Step 3: Draft email using AI
        email_subject, email_body = self._draft_reorder_email(
            material=material,
            supplier=supplier,
            quantity=quantity
        )
        
        # Step 4: Send email if sender is configured
        email_sent = False
        if self.email_sender and supplier.email:
            try:
                self.email_sender.send_email(
                    to=supplier.email,
                    subject=email_subject,
                    body=email_body
                )
                email_sent = True
                logger.info(f"Reorder email sent to {supplier.email}")
            except Exception as e:
                logger.error(f"Failed to send reorder email: {e}")
        else:
            logger.info("Email sender not configured - email drafted but not sent")
        
        # Step 5: Log the reorder
        reorder_log = ReorderLog(
            material_id=material.material_id,
            supplier_id=supplier.supplier_id,
            quantity_kg=quantity,
            triggered_by=triggered_by,
            order_id=order_id,
            email_sent_to=supplier.email if email_sent else None,
            email_subject=email_subject,
            email_body=email_body,
            status="ordered" if email_sent else "pending",
            notes=f"Triggered by {triggered_by}"
        )
        
        self.db.add(reorder_log)
        self.db.commit()
        self.db.refresh(reorder_log)
        
        logger.info(f"Reorder logged with ID: {reorder_log.reorder_id}")
        
        # Step 6: Update order status if applicable
        if order_id and triggered_by == "auto_order":
            self._update_order_status(order_id, "awaiting_material")
        
        return ReorderResult(
            success=True,
            reorder_id=reorder_log.reorder_id,
            email_sent=email_sent,
            supplier_email=supplier.email,
            quantity_kg=quantity,
            message=f"Reorder created for {quantity}kg of {material.name}",
            email_subject=email_subject,
            email_body=email_body
        )
    
    def _get_supplier(self, supplier_id: Optional[int]) -> Optional[Supplier]:
        """Get supplier by ID"""
        if not supplier_id:
            return None
        return self.db.query(Supplier).filter(
            Supplier.supplier_id == supplier_id,
            Supplier.is_active == True
        ).first()
    
    def _draft_reorder_email(
        self,
        material: RawMaterial,
        supplier: Supplier,
        quantity: Decimal
    ) -> tuple[str, str]:
        """
        Use Phi-3 Mini to draft a professional reorder email.
        
        Returns:
            Tuple of (subject, body)
        """
        import os
        factory_name = os.environ.get("FACTORY_NAME", "PlantMind AI Factory")

        current_stock = float(material.current_stock_kg) if material.current_stock_kg else 0
        reorder_level = float(material.reorder_level_kg) if material.reorder_level_kg else 0

        subject, body = self.ai_model.draft_reorder_email(
            material_name=material.name,
            quantity_kg=float(quantity),
            supplier_name=supplier.name,
            current_stock_kg=current_stock,
            reorder_level_kg=reorder_level,
            factory_name=factory_name,
        )

        logger.info(f"AI-drafted reorder email for {material.name} ({quantity} kg) to {supplier.name}")
        return subject, body
    
    def _update_order_status(self, order_id: int, new_status: str):
        """Update order status in database with audit logging"""
        order = self.db.query(Order).filter(Order.order_id == order_id).first()
        if order:
            old_status = order.status
            order.status = new_status

            # Log status change for audit trail
            status_log = OrderStatusLog(
                order_id=order_id,
                old_status=old_status,
                new_status=new_status,
                change_source="v2_processor",
                notes=f"Reorder triggered — material below threshold",
            )
            self.db.add(status_log)
            self.db.commit()
            logger.info(f"Order {order_id} status: {old_status} → {new_status} (logged)")
    
    def check_and_reorder_low_stock(self) -> list[ReorderResult]:
        """
        Check all materials and reorder those below reorder level.
        
        Returns:
            List of ReorderResults for any reorders triggered
        """
        results = []
        
        # Find materials needing reorder
        materials = self.db.query(RawMaterial).filter(
            RawMaterial.current_stock_kg <= RawMaterial.reorder_level_kg
        ).all()
        
        logger.info(f"Found {len(materials)} materials needing reorder")
        
        for material in materials:
            # Check if already pending reorder
            pending = self.db.query(ReorderLog).filter(
                ReorderLog.material_id == material.material_id,
                ReorderLog.status.in_(["pending", "ordered", "confirmed"])
            ).first()
            
            if pending:
                logger.info(f"Skipping {material.name} - already has pending reorder")
                continue
            
            # Create reorder
            result = self.reorder_for_material(
                material=material,
                triggered_by="system_alert"
            )
            results.append(result)
        
        return results


# Factory function
def create_reorder_agent(db_session: Session, email_sender=None) -> ReorderAgent:
    """Factory function to create ReorderAgent instance
    
    Args:
        db_session: SQLAlchemy database session
        email_sender: Email sender instance (defaults to gmail_sender singleton)
    """
    sender = email_sender or gmail_sender
    return ReorderAgent(db_session, sender)
