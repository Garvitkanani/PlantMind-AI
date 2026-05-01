"""
Duplicate Order Detection Agent

Detects potential duplicate orders based on:
- Same customer
- Same or similar product name
- Same or similar quantity
- Recent timeframe (within last 7 days)
- Same or similar delivery date

Returns similarity score and suggested duplicate order IDs.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from src.database.models import Order, Customer

logger = logging.getLogger(__name__)


@dataclass
class DuplicateCheckResult:
    """Result of duplicate order check"""
    is_duplicate: bool
    confidence: float  # 0.0 to 1.0
    similar_orders: List[dict]
    message: str


class DuplicateDetectorAgent:
    """
    Duplicate Order Detection Agent
    
    Analyzes new orders to detect potential duplicates before creation.
    """
    
    # Similarity thresholds
    SIMILAR_PRODUCT_THRESHOLD = 0.85  # 85% similar product names
    SIMILAR_QUANTITY_THRESHOLD = 0.10  # Within 10% quantity difference
    TIME_WINDOW_DAYS = 7  # Check orders from last 7 days
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def check_for_duplicates(
        self,
        customer_email: str,
        product_name: str,
        quantity: int,
        delivery_date: Optional[str] = None,
        exclude_order_id: Optional[int] = None
    ) -> DuplicateCheckResult:
        """
        Check if this order matches any existing orders.
        
        Args:
            customer_email: Customer email address
            product_name: Product name to check
            quantity: Order quantity
            delivery_date: Required delivery date (optional)
            exclude_order_id: Order ID to exclude (for re-checking)
            
        Returns:
            DuplicateCheckResult with similarity analysis
        """
        logger.info(f"Checking for duplicates: {customer_email} - {product_name} - {quantity}")
        
        # Find customer
        customer = self.db.query(Customer).filter(
            Customer.email.ilike(customer_email)
        ).first()
        
        if not customer:
            # New customer - no duplicates possible
            return DuplicateCheckResult(
                is_duplicate=False,
                confidence=0.0,
                similar_orders=[],
                message="New customer - no existing orders to compare"
            )
        
        # Get recent orders from this customer
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.TIME_WINDOW_DAYS)
        
        recent_orders = self.db.query(Order).filter(
            Order.customer_id == customer.customer_id,
            Order.created_at >= cutoff_date,
            Order.status.notin_(['cancelled', 'dispatched'])  # Exclude completed
        ).all()
        
        if exclude_order_id:
            recent_orders = [o for o in recent_orders if o.order_id != exclude_order_id]
        
        if not recent_orders:
            return DuplicateCheckResult(
                is_duplicate=False,
                confidence=0.0,
                similar_orders=[],
                message="No recent orders from this customer"
            )
        
        # Check each order for similarity
        similar_orders = []
        
        for order in recent_orders:
            similarity_score = self._calculate_similarity(
                product_name, quantity, delivery_date, order
            )
            
            if similarity_score > 0.7:  # High similarity threshold
                similar_orders.append({
                    "order_id": order.order_id,
                    "order_number": f"ORD-{order.order_id:03d}",
                    "product_name": order.product_name,
                    "quantity": order.quantity,
                    "status": order.status,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "similarity_score": round(similarity_score, 2),
                    "priority": order.priority or "normal"
                })
        
        # Sort by similarity score (highest first)
        similar_orders.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        # Determine if duplicate
        if similar_orders:
            best_match = similar_orders[0]
            confidence = best_match["similarity_score"]
            
            if confidence >= 0.95:
                return DuplicateCheckResult(
                    is_duplicate=True,
                    confidence=confidence,
                    similar_orders=similar_orders,
                    message=f"🔴 HIGH CONFIDENCE DUPLICATE: Very similar to {best_match['order_number']}"
                )
            elif confidence >= 0.85:
                return DuplicateCheckResult(
                    is_duplicate=True,
                    confidence=confidence,
                    similar_orders=similar_orders,
                    message=f"🟠 LIKELY DUPLICATE: Similar to {best_match['order_number']}"
                )
            else:
                return DuplicateCheckResult(
                    is_duplicate=False,
                    confidence=confidence,
                    similar_orders=similar_orders,
                    message=f"🟡 POSSIBLE DUPLICATE: Review similar orders below"
                )
        
        return DuplicateCheckResult(
            is_duplicate=False,
            confidence=0.0,
            similar_orders=[],
            message="No similar orders found - safe to create"
        )
    
    def _calculate_similarity(
        self,
        new_product: str,
        new_quantity: int,
        new_delivery_date: Optional[str],
        existing_order: Order
    ) -> float:
        """
        Calculate similarity score between new order and existing order.
        
        Returns score between 0.0 and 1.0
        """
        scores = []
        
        # Product name similarity (most important)
        product_similarity = SequenceMatcher(
            None, 
            new_product.lower(), 
            (existing_order.product_name or "").lower()
        ).ratio()
        scores.append(product_similarity * 0.5)  # 50% weight
        
        # Quantity similarity
        if existing_order.quantity and existing_order.quantity > 0:
            quantity_diff = abs(new_quantity - existing_order.quantity)
            quantity_ratio = quantity_diff / existing_order.quantity
            quantity_similarity = max(0, 1 - quantity_ratio)
            scores.append(quantity_similarity * 0.3)  # 30% weight
        
        # Delivery date similarity (if both provided)
        if new_delivery_date and existing_order.required_delivery_date:
            try:
                new_date = datetime.strptime(new_delivery_date, "%Y-%m-%d").date()
                existing_date = existing_order.required_delivery_date
                date_diff = abs((new_date - existing_date).days)
                date_similarity = max(0, 1 - (date_diff / 7))  # Within 7 days = similar
                scores.append(date_similarity * 0.2)  # 20% weight
            except (ValueError, TypeError):
                pass
        
        return sum(scores)
    
    def find_exact_duplicate(
        self,
        customer_email: str,
        product_name: str,
        quantity: int
    ) -> Optional[Order]:
        """
        Find exact duplicate (same customer, product, quantity within 24 hours).
        
        Returns existing order if exact duplicate found.
        """
        customer = self.db.query(Customer).filter(
            Customer.email.ilike(customer_email)
        ).first()
        
        if not customer:
            return None
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(hours=24)
        
        return self.db.query(Order).filter(
            Order.customer_id == customer.customer_id,
            Order.product_name.ilike(product_name),
            Order.quantity == quantity,
            Order.created_at >= cutoff_date
        ).first()


# Factory function
def create_duplicate_detector(db_session: Session) -> DuplicateDetectorAgent:
    """Factory function to create DuplicateDetectorAgent instance"""
    return DuplicateDetectorAgent(db_session)
