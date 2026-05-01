"""
Inventory Check Agent - V2 Production & Inventory Brain

Responsibility:
- Read order details from database
- Look up product in products table
- Calculate total raw material needed
- Compare against current stock
- Return: SUFFICIENT or INSUFFICIENT with amounts

Trigger: Called automatically when new order appears with status = "new"
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import Order, Product, RawMaterial

logger = logging.getLogger(__name__)


@dataclass
class InventoryCheckResult:
    """Result of inventory check for an order"""
    order_id: int
    sufficient: bool
    material_id: Optional[int]
    material_name: Optional[str]
    material_needed_kg: Decimal
    current_stock_kg: Decimal
    stock_after_order_kg: Decimal
    buffer_stock_kg: Decimal
    shortfall_kg: Optional[Decimal]
    message: str


class InventoryCheckAgent:
    """
    Inventory Check Agent
    
    Checks if sufficient raw material exists for an order.
    Considers buffer stock to ensure factory never runs empty.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def check_order(self, order: Order) -> InventoryCheckResult:
        """
        Check if sufficient material exists for an order.
        
        Args:
            order: Order object to check
            
        Returns:
            InventoryCheckResult with detailed analysis
        """
        logger.info(f"Checking inventory for order {order.order_id}: {order.product_name}")
        
        # Step 1: Find matching product
        product = self._find_product(order.product_name)
        
        if not product:
            logger.warning(f"Product not found: {order.product_name}")
            return InventoryCheckResult(
                order_id=order.order_id,
                sufficient=False,
                material_id=None,
                material_name=None,
                material_needed_kg=Decimal("0"),
                current_stock_kg=Decimal("0"),
                stock_after_order_kg=Decimal("0"),
                buffer_stock_kg=Decimal("0"),
                shortfall_kg=None,
                message=f"Product '{order.product_name}' not found in database. Manual setup required."
            )
        
        # Step 2: Get raw material details
        material = self.db.query(RawMaterial).filter(
            RawMaterial.material_id == product.material_id
        ).first()
        
        if not material:
            logger.warning(f"Raw material not found for product: {product.name}")
            return InventoryCheckResult(
                order_id=order.order_id,
                sufficient=False,
                material_id=product.material_id,
                material_name=None,
                material_needed_kg=Decimal("0"),
                current_stock_kg=Decimal("0"),
                stock_after_order_kg=Decimal("0"),
                buffer_stock_kg=Decimal("0"),
                shortfall_kg=None,
                message=f"Raw material for '{product.name}' not found. Contact admin."
            )
        
        # Step 3: Calculate material needed
        material_needed = self._calculate_material_needed(product, order.quantity)
        current_stock = Decimal(str(material.current_stock_kg))
        buffer_stock = Decimal(str(material.reorder_level_kg))
        
        # Step 4: Check sufficiency (including buffer)
        stock_after_order = current_stock - material_needed
        remaining_after_buffer = stock_after_order - buffer_stock
        
        sufficient = remaining_after_buffer >= 0
        
        if sufficient:
            message = (
                f"Sufficient stock. Need {material_needed:.2f} kg, "
                f"have {current_stock:.2f} kg. "
                f"After order: {stock_after_order:.2f} kg (buffer: {buffer_stock:.2f} kg)"
            )
            shortfall = None
            logger.info(f"Order {order.order_id}: SUFFICIENT - {message}")
        else:
            shortfall = abs(remaining_after_buffer)
            message = (
                f"INSUFFICIENT stock. Need {material_needed:.2f} kg, "
                f"have {current_stock:.2f} kg. "
                f"Shortfall including buffer: {shortfall:.2f} kg"
            )
            logger.warning(f"Order {order.order_id}: INSUFFICIENT - {message}")
        
        return InventoryCheckResult(
            order_id=order.order_id,
            sufficient=sufficient,
            material_id=material.material_id,
            material_name=material.name,
            material_needed_kg=material_needed,
            current_stock_kg=current_stock,
            stock_after_order_kg=stock_after_order,
            buffer_stock_kg=buffer_stock,
            shortfall_kg=shortfall,
            message=message
        )
    
    def _find_product(self, product_name: str) -> Optional[Product]:
        """
        Find product by name (case-insensitive partial match).
        
        First tries exact match, then partial match.
        """
        # Try exact case-insensitive match first
        product = self.db.query(Product).filter(
            Product.name.ilike(product_name),
            Product.is_active == True
        ).first()
        
        if product:
            return product
        
        # Try partial match - but sanitize input to prevent LIKE injection
        safe_name = product_name.replace("%", "\\%").replace("_", "\\_")
        product = self.db.query(Product).filter(
            Product.name.ilike(f"%{safe_name}%"),
            Product.is_active == True
        ).first()
        
        return product
    
    def _calculate_material_needed(self, product: Product, quantity: int) -> Decimal:
        """
        Calculate total material needed for a given quantity.
        
        Formula: quantity × material_required_per_unit_kg
        """
        per_unit = Decimal(str(product.material_required_per_unit_kg))
        return per_unit * Decimal(quantity)
    
    def get_all_new_orders(self) -> list[Order]:
        """Get all orders with status 'new' that need inventory check"""
        return self.db.query(Order).filter(
            Order.status == "new"
        ).all()
    
    def check_all_new_orders(self) -> list[InventoryCheckResult]:
        """Check inventory for all new orders"""
        new_orders = self.get_all_new_orders()
        results = []
        
        logger.info(f"Checking inventory for {len(new_orders)} new orders")
        
        for order in new_orders:
            result = self.check_order(order)
            results.append(result)
        
        return results


# Singleton instance factory
def create_inventory_checker(db_session: Session) -> InventoryCheckAgent:
    """Factory function to create InventoryCheckAgent instance"""
    return InventoryCheckAgent(db_session)
