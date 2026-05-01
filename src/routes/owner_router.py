"""
Owner dashboard routes for V3.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from src.database.connection import SessionLocal
from src.database.models import User

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


def require_owner(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=403, detail="Permission denied")
        user_data = user.to_dict()
        if user_data.get("role") != "owner":
            raise HTTPException(status_code=403, detail="Owner access required")
        return user_data
    finally:
        db.close()


@router.get("/dashboard/owner", response_class=HTMLResponse)
async def owner_dashboard_page(request: Request):
    user = require_owner(request)
    return templates.TemplateResponse(
        request,
        "owner_dashboard.html",
        {"username": user["username"]},
    )


@router.get("/api/v3/owner/dashboard-data")
async def owner_dashboard_data(request: Request):
    require_owner(request)
    db = SessionLocal()
    try:
        overview_row = db.execute(
            text(
                "SELECT "
                "(SELECT COUNT(*) FROM orders WHERE status IN ('new','scheduled','in_production','awaiting_material')) AS active_orders, "
                "(SELECT COUNT(*) FROM orders WHERE status = 'in_production') AS in_production, "
                "(SELECT COUNT(*) FROM orders WHERE status = 'dispatched') AS dispatched_total, "
                "(SELECT COUNT(*) FROM orders WHERE status = 'completed') AS completed_total, "
                "(SELECT COUNT(*) FROM production_schedule WHERE status='in_production' AND delay_alert_sent = true) AS overdue"
            )
        ).mappings().first()

        orders = db.execute(
            text(
                "SELECT o.order_id, c.name AS customer_name, o.product_name, o.quantity, "
                "o.required_delivery_date, o.status, o.created_at, o.dispatch_email_sent, "
                "ps.machine_id, m.name AS machine_name, "
                "(SELECT completion_percentage FROM production_progress "
                " WHERE schedule_id = ps.schedule_id "
                " ORDER BY created_at DESC LIMIT 1) AS completion_percentage "
                "FROM orders o "
                "LEFT JOIN customers c ON c.customer_id = o.customer_id "
                "LEFT JOIN production_schedule ps ON ps.order_id = o.order_id "
                "LEFT JOIN machines m ON m.machine_id = ps.machine_id "
                "ORDER BY o.created_at DESC LIMIT 100"
            )
        ).mappings().all()

        machines = db.execute(
            text(
                "SELECT machine_id, name, model, status, current_order_id, "
                "last_maintenance_date, next_scheduled_maintenance, "
                "total_runtime_hours, is_active "
                "FROM machines ORDER BY machine_id ASC"
            )
        ).mappings().all()

        materials = db.execute(
            text(
                "SELECT name, current_stock_kg, reorder_level_kg, "
                "unit_price_per_kg, last_updated "
                "FROM raw_materials ORDER BY name ASC"
            )
        ).mappings().all()

        activity = db.execute(
            text(
                "SELECT direction, subject, from_address, to_address, "
                "processing_status, processed_at "
                "FROM email_log ORDER BY processed_at DESC LIMIT 20"
            )
        ).mappings().all()

        # Query from mis_report_log (proper table, not email_log)
        mis_history = db.execute(
            text(
                "SELECT mis_report_log_id, report_date, owner_email, "
                "email_subject, report_body, send_status, attempts, "
                "error_details, triggered_by, created_at "
                "FROM mis_report_log "
                "ORDER BY report_date DESC LIMIT 14"
            )
        ).mappings().all()

        # Dispatch history from dispatch_log
        dispatch_history = db.execute(
            text(
                "SELECT dl.dispatch_log_id, dl.order_id, dl.customer_email, "
                "dl.email_subject, dl.send_status, dl.attempts, "
                "dl.error_details, dl.created_at, "
                "o.product_name, o.quantity "
                "FROM dispatch_log dl "
                "LEFT JOIN orders o ON o.order_id = dl.order_id "
                "ORDER BY dl.created_at DESC LIMIT 20"
            )
        ).mappings().all()

        def serialize(obj):
            """Recursively convert non-JSON-serializable types."""
            from datetime import date, datetime
            from decimal import Decimal
            if isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [serialize(v) for v in obj]
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return float(obj)
            return obj

        return JSONResponse(
            serialize({
                "success": True,
                "overview": dict(overview_row or {}),
                "orders": [dict(row) for row in orders],
                "machines": [dict(row) for row in machines],
                "materials": [dict(row) for row in materials],
                "activity": [dict(row) for row in activity],
                "mis_history": [dict(row) for row in mis_history],
                "dispatch_history": [dict(row) for row in dispatch_history],
            })
        )
    finally:
        db.close()

