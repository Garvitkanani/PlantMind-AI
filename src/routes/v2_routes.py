"""
V2 API Routes - Production & Inventory Brain

All V2 endpoints for:
- Production scheduling and tracking
- Inventory management
- Supplier reordering
- Dashboard data
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import text

from src.database.connection import SessionLocal
from src.database.models import (
    ProductionSchedule, ProductionProgress, Machine, RawMaterial,
    Supplier, ReorderLog, Order, User
)
from src.routes.v1_routes import require_office_staff
from src.security import require_supervisor, require_store_staff
from src.processors.v2_processor import run_v2_processing, V2Processor
from src.processors.v3_processor import run_v3_dispatch, run_v3_mis_report
from src.agents.production_tracker_agent import create_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2")


# ============ Pydantic Models ============

class ProgressUpdateRequest(BaseModel):
    pieces_completed: int
    notes: Optional[str] = None


class StockUpdateRequest(BaseModel):
    new_stock_kg: float
    notes: Optional[str] = None


class ReorderCreateRequest(BaseModel):
    material_id: int
    supplier_id: int
    quantity_kg: float
    expected_delivery: Optional[str] = None
    triggered_by: str = "manual_store"


# ============ Dashboard Pages ============

@router.get("/supervisor-dashboard", response_class=HTMLResponse)
async def supervisor_dashboard_page(request: Request):
    """Render Floor Supervisor Dashboard"""
    from src.templates import templates
    require_supervisor(request)
    return templates.TemplateResponse("supervisor_dashboard.html", {"request": request})


@router.get("/store-dashboard", response_class=HTMLResponse)
async def store_dashboard_page(request: Request):
    """Render Store Staff Dashboard"""
    from src.templates import templates
    require_store_staff(request)
    return templates.TemplateResponse("store_dashboard.html", {"request": request})


# ============ Production Schedule APIs ============

@router.get("/production-schedule")
async def get_production_schedule(request: Request):
    """Get all production schedules with related data"""
    require_supervisor(request)
    
    db = SessionLocal()
    try:
        # Get schedules with order and machine details
        schedules = db.query(ProductionSchedule).all()
        
        result = []
        for s in schedules:
            # Get latest progress
            latest_progress = db.query(ProductionProgress).filter(
                ProductionProgress.schedule_id == s.schedule_id
            ).order_by(ProductionProgress.created_at.desc()).first()
            
            order_data = {}
            if s.order:
                order_data = {
                    "order_id": s.order.order_id,
                    "product_name": s.order.product_name,
                    "quantity": s.order.quantity,
                    "customer_name": s.order.customer.name if s.order.customer else None,
                    "required_delivery_date": s.order.required_delivery_date.isoformat() if s.order.required_delivery_date else None
                }
            
            machine_data = {}
            if s.machine:
                machine_data = {
                    "machine_id": s.machine.machine_id,
                    "name": s.machine.name,
                    "model": s.machine.model
                }
            
            # Check if delayed
            is_delayed = s.is_delayed() if hasattr(s, 'is_delayed') else False
            new_eta = None
            if is_delayed and latest_progress:
                # Calculate new ETA
                if s.actual_start and latest_progress.completion_percentage > 0:
                    hours_elapsed = (datetime.now(timezone.utc) - s.actual_start).total_seconds() / 3600
                    pieces_per_hour = latest_progress.pieces_completed / hours_elapsed if hours_elapsed > 0 else 0
                    if pieces_per_hour > 0:
                        pieces_remaining = latest_progress.total_pieces - latest_progress.pieces_completed
                        hours_remaining = pieces_remaining / pieces_per_hour
                        new_eta = datetime.now(timezone.utc) + timedelta(hours=hours_remaining)
            
            result.append({
                "schedule_id": s.schedule_id,
                "order_id": s.order_id,
                "machine_id": s.machine_id,
                "status": s.status,
                "estimated_start": s.estimated_start.isoformat() if s.estimated_start else None,
                "estimated_end": s.estimated_end.isoformat() if s.estimated_end else None,
                "actual_start": s.actual_start.isoformat() if s.actual_start else None,
                "actual_end": s.actual_end.isoformat() if s.actual_end else None,
                "delay_alert_sent": s.delay_alert_sent,
                "product_name": order_data.get("product_name"),
                "quantity": order_data.get("quantity"),
                "customer_name": order_data.get("customer_name"),
                "machine_name": machine_data.get("name"),
                "completion_percentage": float(latest_progress.completion_percentage) if latest_progress else 0,
                "pieces_completed": latest_progress.pieces_completed if latest_progress else 0,
                "is_delayed": is_delayed,
                "new_eta": new_eta.isoformat() if new_eta else None
            })
        
        return {"success": True, "schedules": result}
    finally:
        db.close()


@router.post("/production-schedule/{schedule_id}/start")
async def start_production(request: Request, schedule_id: int):
    """Start production on a scheduled order"""
    require_supervisor(request)
    
    db = SessionLocal()
    try:
        schedule = db.query(ProductionSchedule).filter(
            ProductionSchedule.schedule_id == schedule_id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        if schedule.status != "scheduled":
            raise HTTPException(status_code=400, detail="Schedule is not in 'scheduled' status")
        
        # Update schedule
        schedule.status = "in_production"
        schedule.actual_start = datetime.now(timezone.utc)
        
        # Update order
        if schedule.order:
            schedule.order.status = "in_production"
        
        db.commit()
        
        return {"success": True, "message": "Production started"}
    finally:
        db.close()


@router.post("/production-schedule/{schedule_id}/progress")
async def update_progress(request: Request, schedule_id: int, data: ProgressUpdateRequest):
    """Update production progress"""
    user = require_supervisor(request)
    
    db = SessionLocal()
    try:
        tracker = create_tracker(db)
        result = tracker.update_progress(
            schedule_id=schedule_id,
            pieces_completed=data.pieces_completed,
            updated_by=user["user_id"],
            notes=data.notes
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        
        return {
            "success": True,
            "completion_percentage": result.completion_percentage,
            "is_delayed": result.is_delayed,
            "is_complete": result.is_complete,
            "delay_alert_triggered": result.delay_alert_triggered
        }
    finally:
        db.close()


@router.post("/production-schedule/{schedule_id}/complete")
async def complete_production(request: Request, schedule_id: int):
    """Manually mark production as complete"""
    require_supervisor(request)
    
    db = SessionLocal()
    try:
        schedule = db.query(ProductionSchedule).filter(
            ProductionSchedule.schedule_id == schedule_id
        ).first()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        if schedule.order:
            from src.agents.production_tracker_agent import ProductionTrackerAgent
            tracker = ProductionTrackerAgent(db)
            
            # Complete the order
            tracker._handle_completion(schedule, schedule.order)
            db.commit()
        
        return {"success": True, "message": "Production marked complete"}
    finally:
        db.close()


# ============ Machine APIs ============

@router.get("/machines")
async def get_machines(request: Request):
    """Get all machines with their status"""
    require_supervisor(request)
    
    db = SessionLocal()
    try:
        machines = db.query(Machine).all()
        return {
            "success": True,
            "machines": [m.to_dict() for m in machines]
        }
    finally:
        db.close()


# ============ Material/Inventory APIs ============

@router.get("/materials")
async def get_materials(request: Request):
    """Get all raw materials with stock levels"""
    require_store_staff(request)
    
    db = SessionLocal()
    try:
        materials = db.query(RawMaterial).all()
        
        result = []
        for m in materials:
            supplier_name = m.supplier.name if m.supplier else None
            
            result.append({
                "material_id": m.material_id,
                "name": m.name,
                "type": m.type,
                "current_stock_kg": float(m.current_stock_kg),
                "reorder_level_kg": float(m.reorder_level_kg),
                "reorder_quantity_kg": float(m.reorder_quantity_kg),
                "unit_price_per_kg": float(m.unit_price_per_kg) if m.unit_price_per_kg else None,
                "supplier_id": m.supplier_id,
                "supplier_name": supplier_name,
                "needs_reorder": m.needs_reorder()
            })
        
        return {"success": True, "materials": result}
    finally:
        db.close()


@router.post("/materials/{material_id}/stock")
async def update_material_stock(
    request: Request,
    material_id: int,
    data: StockUpdateRequest
):
    """Update material stock level with full audit logging"""
    user = require_store_staff(request)
    
    db = SessionLocal()
    try:
        material = db.query(RawMaterial).filter(
            RawMaterial.material_id == material_id
        ).first()
        
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        
        # Calculate change
        old_stock = float(material.current_stock_kg)
        new_stock = data.new_stock_kg
        change_amount = new_stock - old_stock
        
        # Determine change type from reason
        change_type = "manual_update"
        if data.notes:
            notes_lower = data.notes.lower()
            if "delivery" in notes_lower:
                change_type = "delivery"
            elif "wastage" in notes_lower or "scrap" in notes_lower:
                change_type = "wastage"
            elif "returns" in notes_lower:
                change_type = "returns"
            elif "production" in notes_lower or "usage" in notes_lower:
                change_type = "production_usage"
        
        # Create stock log entry
        from src.database.models import StockLog
        stock_log = StockLog(
            material_id=material_id,
            order_id=None,
            change_type=change_type,
            quantity_before_kg=old_stock,
            quantity_after_kg=new_stock,
            change_amount_kg=change_amount,
            reason=data.notes or "Manual stock update",
            updated_by=user.get("user_id")
        )
        db.add(stock_log)
        
        # Update material stock
        material.current_stock_kg = new_stock
        material.last_updated = datetime.now(timezone.utc)
        
        # Check for any awaiting orders that can now be scheduled
        processor = V2Processor(db)
        awaiting_result = processor.process_awaiting_material_orders()
        
        db.commit()
        
        return {
            "success": True,
            "old_stock": old_stock,
            "new_stock": new_stock,
            "change_amount": change_amount,
            "change_type": change_type,
            "orders_scheduled": awaiting_result.get("scheduled", 0)
        }
    finally:
        db.close()


@router.get("/stock-log")
async def get_stock_log(request: Request, material_id: Optional[int] = None, limit: int = 100):
    """Get stock change history (audit trail)"""
    require_store_staff(request)
    
    db = SessionLocal()
    try:
        from src.database.models import StockLog
        
        query = db.query(StockLog)
        
        if material_id:
            query = query.filter(StockLog.material_id == material_id)
        
        logs = query.order_by(StockLog.updated_at.desc()).limit(limit).all()
        
        return {
            "success": True,
            "logs": [log.to_dict() for log in logs]
        }
    finally:
        db.close()


# ============ Supplier APIs ============

@router.get("/suppliers")
async def get_suppliers(request: Request):
    """Get all suppliers"""
    require_store_staff(request)
    
    db = SessionLocal()
    try:
        suppliers = db.query(Supplier).filter(Supplier.is_active == True).all()
        return {
            "success": True,
            "suppliers": [s.to_dict() for s in suppliers]
        }
    finally:
        db.close()


# ============ Reorder APIs ============

@router.get("/reorders")
async def get_reorders(request: Request, limit: int = 50):
    """Get reorder history"""
    require_store_staff(request)
    
    db = SessionLocal()
    try:
        reorders = db.query(ReorderLog).order_by(
            ReorderLog.created_at.desc()
        ).limit(limit).all()
        
        result = []
        for r in reorders:
            result.append({
                "reorder_id": r.reorder_id,
                "material_id": r.material_id,
                "material_name": r.material.name if r.material else None,
                "supplier_id": r.supplier_id,
                "supplier_name": r.supplier.name if r.supplier else None,
                "quantity_kg": float(r.quantity_kg),
                "status": r.status,
                "triggered_by": r.triggered_by,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "expected_delivery": r.delivery_expected_by.isoformat() if r.delivery_expected_by else None
            })
        
        return {"success": True, "reorders": result}
    finally:
        db.close()


@router.post("/reorders")
async def create_reorder(request: Request, data: ReorderCreateRequest):
    """Create a manual reorder"""
    require_store_staff(request)
    
    db = SessionLocal()
    try:
        from src.agents.reorder_agent import create_reorder_agent
        
        material = db.query(RawMaterial).filter(
            RawMaterial.material_id == data.material_id
        ).first()
        
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        
        agent = create_reorder_agent(db)
        result = agent.reorder_for_material(
            material=material,
            triggered_by=data.triggered_by,
            custom_quantity=__import__('decimal').Decimal(str(data.quantity_kg))
        )
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        
        return {
            "success": True,
            "reorder_id": result.reorder_id,
            "email_sent": result.email_sent
        }
    finally:
        db.close()


# ============ V2 Processing APIs ============

@router.post("/process-new-orders")
async def trigger_v2_processing(request: Request):
    """Manually trigger V2 processing for new orders"""
    require_office_staff(request)
    
    result = run_v2_processing()
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Processing failed"))
    
    return result


@router.post("/process-dispatch")
async def trigger_v3_dispatch(request: Request):
    """Manually trigger V3 dispatch processing for completed orders."""
    require_office_staff(request)

    result = run_v3_dispatch()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Dispatch processing failed"))
    return result


@router.post("/process-mis-report")
async def trigger_v3_mis_report(request: Request):
    """Manually trigger V3 MIS report generation."""
    require_office_staff(request)

    result = run_v3_mis_report()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "MIS report generation failed"))
    return result


@router.get("/dashboard-stats")
async def get_v2_dashboard_stats(request: Request):
    """Get V2 statistics for dashboard"""
    require_office_staff(request)
    
    db = SessionLocal()
    try:
        processor = V2Processor(db)
        stats = processor.get_dashboard_stats()
        
        return {"success": True, "stats": stats}
    finally:
        db.close()
