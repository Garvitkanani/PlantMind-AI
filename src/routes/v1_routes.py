"""
V1 API Routes - Matches V1 Specification Exactly

Endpoints:
- POST /check-emails (trigger email processing)
- GET /orders (get all orders)
- POST /orders/complete-review (complete flagged order review)
- GET /email-log (get email log)
- GET /dashboard (dashboard HTML)
- POST /login (authentication)
- GET /logout (logout)
"""

import logging
import os
import threading
from io import BytesIO
from datetime import datetime, timezone
from time import time

import bcrypt
from fastapi import APIRouter, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from src.database.connection import SessionLocal
from src.database.models import User, Customer, Order, OrderStatusLog
from src.processors.v1_email_processor import v1_email_processor
from src.security import SecurityHeadersMiddleware
from src.system.self_check import run_system_self_check

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Setup templates
templates = Jinja2Templates(directory="src/templates")

# App secret key (should be in .env)
APP_SECRET_KEY = os.environ.get(
    "APP_SECRET_KEY", "your-secret-key-here-change-in-production"
)
SESSION_MAX_AGE_SECONDS = int(os.environ.get("SESSION_MAX_AGE_SECONDS", "28800"))
SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "plantmind_session")
SESSION_SAME_SITE = os.environ.get("SESSION_SAME_SITE", "lax")
SESSION_HTTPS_ONLY = os.environ.get("SESSION_HTTPS_ONLY", "false").lower() == "true"

LOGIN_ATTEMPT_WINDOW_SECONDS = int(os.environ.get("LOGIN_ATTEMPT_WINDOW_SECONDS", "300"))
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
_login_attempts: dict[str, list[float]] = {}
_login_lock = threading.Lock()
_login_last_cleanup = 0.0  # Timestamp of last cleanup


def _cleanup_login_attempts():
    """Remove expired entries from _login_attempts to prevent memory leak."""
    global _login_last_cleanup
    now = time()
    # Only cleanup every 5 minutes to avoid excessive work
    if now - _login_last_cleanup < 300:
        return
    _login_last_cleanup = now
    with _login_lock:
        expired_keys = []
        for key, failures in _login_attempts.items():
            # Keep only recent failures
            recent = [ts for ts in failures if now - ts <= LOGIN_ATTEMPT_WINDOW_SECONDS]
            if not recent:
                expired_keys.append(key)
            else:
                _login_attempts[key] = recent
        for key in expired_keys:
            del _login_attempts[key]


# Authentication helpers
def get_current_user(request: Request):
    """Get current user from session"""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def _track_login_failure(client_key: str):
    now = time()
    with _login_lock:
        failures = _login_attempts.get(client_key, [])
        failures = [ts for ts in failures if now - ts <= LOGIN_ATTEMPT_WINDOW_SECONDS]
        failures.append(now)
        _login_attempts[client_key] = failures


def _is_rate_limited(client_key: str) -> bool:
    now = time()
    with _login_lock:
        failures = _login_attempts.get(client_key, [])
        failures = [ts for ts in failures if now - ts <= LOGIN_ATTEMPT_WINDOW_SECONDS]
        _login_attempts[client_key] = failures
        return len(failures) >= LOGIN_MAX_ATTEMPTS


def _reset_login_failures(client_key: str):
    with _login_lock:
        _login_attempts.pop(client_key, None)


def require_office_staff(request: Request):
    """Ensure user is office staff or owner"""
    user_id = get_current_user(request)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=403, detail="Permission denied")

        # Check role from the dict returned by to_dict()
        user_data = user.to_dict()
        if user_data["role"] not in {"office_staff", "office", "owner"}:
            raise HTTPException(status_code=403, detail="Permission denied")

        return user_data
    finally:
        db.close()


def _serialize_order_row(row) -> dict:
    """Convert joined order row to API-friendly dict."""
    def _to_iso(value):
        if value is None:
            return None
        return value if isinstance(value, str) else value.isoformat()

    return {
        "order_id": row.order_id,
        "customer_id": row.customer_id,
        "customer_name": row.customer_name or "Unknown",
        "product_name": row.product_name,
        "quantity": row.quantity,
        "required_delivery_date": _to_iso(row.required_delivery_date),
        "special_instructions": row.special_instructions,
        "status": row.status,
        "source_email_id": row.source_email_id,
        "created_at": _to_iso(row.created_at),
    }


def _fetch_orders_by_status(db, status: str | None = None):
    """Fetch orders joined with customer names in one query."""
    # Use proper parameterized queries - never concatenate user input into SQL
    if status is not None:
        query = text(
            "SELECT o.order_id, o.customer_id, c.name AS customer_name, "
            "o.product_name, o.quantity, o.required_delivery_date, o.special_instructions, "
            "o.status, o.source_email_id, o.created_at "
            "FROM orders o "
            "LEFT JOIN customers c ON c.customer_id = o.customer_id "
            "WHERE o.status = :status "
            "ORDER BY o.created_at DESC"
        )
        return db.execute(query, {"status": status}).mappings().all()
    else:
        query = text(
            "SELECT o.order_id, o.customer_id, c.name AS customer_name, "
            "o.product_name, o.quantity, o.required_delivery_date, o.special_instructions, "
            "o.status, o.source_email_id, o.created_at "
            "FROM orders o "
            "LEFT JOIN customers c ON c.customer_id = o.customer_id "
            "ORDER BY o.created_at DESC"
        )
        return db.execute(query).mappings().all()


# ============== AUTHENTICATION ROUTES ==============
@router.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root to login page"""
    return RedirectResponse(url="/login", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page HTML"""
    return templates.TemplateResponse(request, "login.html", {})


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Process login - authenticate office staff"""
    _cleanup_login_attempts()  # Periodic cleanup of expired login attempt records
    client_ip = request.client.host if request.client else "unknown"
    client_key = f"{client_ip}:{username.lower().strip()}"
    if _is_rate_limited(client_key):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "Too many failed attempts. Please wait a few minutes and try again.",
            },
            status_code=429,
        )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()

        if not user:
            _track_login_failure(client_key)
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "Invalid username or password"},
            )

        # Get user data as dict to avoid ORM complexity
        user_data = user.to_dict()

        # Check if user is active
        if not user_data.get("is_active", False):
            _track_login_failure(client_key)
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "Invalid username or password"},
            )

        # Verify password using raw SQL query and bcrypt verification
        # This avoids ORM column access issues
        db_result = db.execute(
            text("SELECT password_hash FROM users WHERE username = :username"),
            {"username": username},
        ).fetchone()

        if not db_result:
            _track_login_failure(client_key)
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "Invalid username or password"},
            )

        stored_hash = db_result[0]

        # Verify password
        if not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            _track_login_failure(client_key)
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "Invalid username or password"},
            )

        # Regenerate session ID to prevent session fixation attacks
        request.session.clear()

        # Store user in session
        request.session["user_id"] = user_data["user_id"]
        request.session["username"] = user_data["username"]
        request.session["role"] = user_data["role"]
        _reset_login_failures(client_key)

        logger.info(f"User {username} logged in successfully")

        role = user_data.get("role")
        if role == "owner":
            redirect_url = "/dashboard/owner"
        elif role == "supervisor":
            redirect_url = "/api/v2/supervisor-dashboard"
        elif role == "store":
            redirect_url = "/api/v2/store-dashboard"
        else:
            redirect_url = "/dashboard"

        # Redirect based on role
        return RedirectResponse(url=redirect_url, status_code=303)

    finally:
        db.close()


@router.get("/logout")
async def logout(request: Request):
    """Logout user"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# ============== DASHBOARD ROUTES ==============
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Office staff dashboard HTML"""
    # Check authentication
    user = require_office_staff(request)

    db = SessionLocal()
    try:
        new_orders = [
            _serialize_order_row(row) for row in _fetch_orders_by_status(db, "new")
        ]
        flagged_orders = [
            _serialize_order_row(row)
            for row in _fetch_orders_by_status(db, "needs_review")
        ]

        # Get recent email log using raw SQL
        recent_emails_result = db.execute(
            text("SELECT * FROM email_log ORDER BY processed_at DESC LIMIT 20")
        ).fetchall()

        recent_emails = []
        for row in recent_emails_result:
            email_dict = {
                "email_id": row[0],
                "gmail_message_id": row[1],
                "direction": row[2],
                "from_address": row[3],
                "to_address": row[4],
                "subject": row[5],
                "body_summary": row[6],
                "attachment_name": row[7],
                "filter_decision": row[8],
                "processing_status": row[9],
                "linked_order_id": row[10],
                "error_details": row[11],
                "processed_at": (
                    row[12] if isinstance(row[12], str) else row[12].isoformat()
                ) if row[12] else None,
            }
            recent_emails.append(email_dict)

        # Counts for summary using raw SQL
        total_orders_result = db.execute(text("SELECT COUNT(*) FROM orders")).fetchone()
        total_orders = total_orders_result[0] if total_orders_result else 0

        flagged_count = len(flagged_orders)
        new_count = len(new_orders)

        # Get last email check time
        last_check_result = db.execute(
            text(
                "SELECT processed_at FROM email_log ORDER BY processed_at DESC LIMIT 1"
            )
        ).fetchone()
        last_checked = (
            last_check_result[0].isoformat()
            if last_check_result and last_check_result[0]
            else None
        )

        return templates.TemplateResponse(
            request,
            "office_dashboard.html",
            {
                "username": user["username"],
                "new_orders": new_orders,
                "flagged_orders": flagged_orders,
                "recent_emails": recent_emails,
                "total_orders": total_orders,
                "flagged_count": flagged_count,
                "new_count": new_count,
                "last_checked": last_checked,
            },
        )
    finally:
        db.close()


# ============== API ENDPOINTS (called by dashboard) ==============
@router.post("/check-emails")
async def check_emails(request: Request):
    """Trigger email processing - called by 'Check New Emails' button"""
    user = require_office_staff(request)

    logger.info(f"User {user['username']} triggered email check")

    try:
        # Process emails
        result = v1_email_processor.process_new_emails(user["user_id"])

        # Return processing summary
        return JSONResponse(
            {"success": True, "message": "Email processing completed", "result": result}
        )
    except Exception as e:
        logger.error(f"Email processing failed: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/orders")
async def get_orders(request: Request):
    """Get all orders (for dashboard table)"""
    require_office_staff(request)

    db = SessionLocal()
    try:
        orders_data = [
            _serialize_order_row(row) for row in _fetch_orders_by_status(db, None)
        ]

        return JSONResponse(
            {"success": True, "orders": orders_data, "count": len(orders_data)}
        )
    finally:
        db.close()


@router.get("/orders/flagged")
async def get_flagged_orders(request: Request):
    """Get flagged orders (needs review)"""
    require_office_staff(request)

    db = SessionLocal()
    try:
        flagged_data = [
            _serialize_order_row(row)
            for row in _fetch_orders_by_status(db, "needs_review")
        ]

        return JSONResponse(
            {
                "success": True,
                "flagged_orders": flagged_data,
                "count": len(flagged_data),
            }
        )
    finally:
        db.close()


@router.post("/orders/{order_id}/complete-review")
async def complete_order_review(
    request: Request,
    order_id: int,
    product_name: str = Form(None),
    quantity: str = Form(None),
    delivery_date: str = Form(None),
):
    """Complete flagged order review - fill in missing fields"""
    user = require_office_staff(request)

    db = SessionLocal()
    try:
        # Check if order exists and is flagged
        order_check = db.execute(
            text("SELECT status FROM orders WHERE order_id = :order_id"),
            {"order_id": order_id},
        ).fetchone()

        if not order_check:
            raise HTTPException(status_code=404, detail="Order not found")

        if order_check[0] != "needs_review":
            raise HTTPException(
                status_code=400, detail="Order is not flagged for review"
            )

        # Build update query based on provided fields
        updates = []
        params = {"order_id": order_id}

        if product_name:
            updates.append("product_name = :product_name")
            params["product_name"] = product_name

        if quantity:
            try:
                quantity_int = int(quantity)
                if quantity_int <= 0:
                    raise HTTPException(
                        status_code=400, detail="Quantity must be a positive number"
                    )
                updates.append("quantity = :quantity")
                params["quantity"] = quantity_int
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid quantity format")

        if delivery_date:
            try:
                delivery_dt = datetime.strptime(delivery_date, "%Y-%m-%d").date()
                updates.append("required_delivery_date = :required_delivery_date")
                params["required_delivery_date"] = delivery_dt
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
                )

        # Always update status to 'new'
        updates.append("status = 'new'")

        if updates:
            update_query = (
                f"UPDATE orders SET {', '.join(updates)} WHERE order_id = :order_id"
            )
            db.execute(text(update_query), params)
            db.commit()

        logger.info(f"Order {order_id} review completed by {user['username']}")

        return JSONResponse(
            {
                "success": True,
                "message": "Order review completed successfully",
                "order_id": order_id,
            }
        )
    finally:
        db.close()


@router.get("/email-log")
async def get_email_log(request: Request):
    """Get email log for dashboard"""
    require_office_staff(request)

    db = SessionLocal()
    try:
        email_logs_result = db.execute(
            text("SELECT * FROM email_log ORDER BY processed_at DESC LIMIT 50")
        ).fetchall()

        logs_data = []
        for row in email_logs_result:
            email_dict = {
                "email_id": row[0],
                "gmail_message_id": row[1],
                "direction": row[2],
                "from_address": row[3],
                "to_address": row[4],
                "subject": row[5],
                "body_summary": row[6],
                "attachment_name": row[7],
                "filter_decision": row[8],
                "processing_status": row[9],
                "linked_order_id": row[10],
                "error_details": row[11],
                "processed_at": (
                    row[12] if isinstance(row[12], str) else row[12].isoformat()
                ) if row[12] else None,
            }
            logs_data.append(email_dict)

        return JSONResponse(
            {"success": True, "email_logs": logs_data, "count": len(logs_data)}
        )
    finally:
        db.close()


@router.get("/processing-summary")
async def get_processing_summary(request: Request):
    """Get summary statistics for dashboard"""
    require_office_staff(request)

    db = SessionLocal()
    try:
        # Count orders by status using raw SQL
        new_count_result = db.execute(
            text("SELECT COUNT(*) FROM orders WHERE status = 'new'")
        ).fetchone()
        new_count = new_count_result[0] if new_count_result else 0

        needs_review_result = db.execute(
            text("SELECT COUNT(*) FROM orders WHERE status = 'needs_review'")
        ).fetchone()
        needs_review_count = needs_review_result[0] if needs_review_result else 0

        total_orders_result = db.execute(text("SELECT COUNT(*) FROM orders")).fetchone()
        total_orders = total_orders_result[0] if total_orders_result else 0

        # Count emails by processing status
        processed_count_result = db.execute(
            text("SELECT COUNT(*) FROM email_log WHERE processing_status = 'success'")
        ).fetchone()
        processed_count = processed_count_result[0] if processed_count_result else 0

        skipped_count_result = db.execute(
            text("SELECT COUNT(*) FROM email_log WHERE processing_status = 'skipped'")
        ).fetchone()
        skipped_count = skipped_count_result[0] if skipped_count_result else 0

        flagged_count_result = db.execute(
            text("SELECT COUNT(*) FROM email_log WHERE processing_status = 'flagged'")
        ).fetchone()
        flagged_count = flagged_count_result[0] if flagged_count_result else 0

        # Get last processing time
        last_processing_result = db.execute(
            text(
                "SELECT processed_at FROM email_log ORDER BY processed_at DESC LIMIT 1"
            )
        ).fetchone()

        last_processed = (
            last_processing_result[0].isoformat()
            if last_processing_result and last_processing_result[0]
            else None
        )

        return JSONResponse(
            {
                "success": True,
                "summary": {
                    "orders": {
                        "new": new_count,
                        "needs_review": needs_review_count,
                        "total": total_orders,
                    },
                    "emails": {
                        "processed": processed_count,
                        "skipped": skipped_count,
                        "flagged": flagged_count,
                    },
                    "last_processed": last_processed,
                },
            }
        )
    finally:
        db.close()


@router.get("/customer-stats")
async def get_customer_stats(request: Request):
    """Get customer quick stats for dashboard cards."""
    require_office_staff(request)

    db = SessionLocal()
    try:
        total_customers_result = db.execute(text("SELECT COUNT(*) FROM customers")).fetchone()
        total_customers = total_customers_result[0] if total_customers_result else 0

        recent_customers_result = db.execute(
            text(
                "SELECT customer_id, name, email, created_at "
                "FROM customers ORDER BY created_at DESC LIMIT 5"
            )
        ).fetchall()

        recent_customers = [
            {
                "customer_id": row[0],
                "name": row[1],
                "email": row[2],
                "created_at": (
                    row[3] if isinstance(row[3], str) else row[3].isoformat()
                ) if row[3] else None,
            }
            for row in recent_customers_result
        ]

        return JSONResponse(
            {
                "success": True,
                "stats": {
                    "total_customers": total_customers,
                    "recent_customers": recent_customers,
                },
            }
        )
    finally:
        db.close()


@router.get("/orders/export")
async def export_orders_excel(request: Request):
    """Export all orders to Excel (.xlsx)."""
    require_office_staff(request)

    db = SessionLocal()
    try:
        orders_result = db.execute(
            text(
                "SELECT o.order_id, c.name, c.email, o.product_name, o.quantity, "
                "o.required_delivery_date, o.special_instructions, o.status, o.created_at "
                "FROM orders o "
                "LEFT JOIN customers c ON c.customer_id = o.customer_id "
                "ORDER BY o.created_at DESC"
            )
        ).fetchall()
    finally:
        db.close()

    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="Excel export dependency missing. Install openpyxl to enable this feature.",
        ) from exc

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Orders"
    sheet.append(
        [
            "Order ID",
            "Customer",
            "Customer Email",
            "Product",
            "Quantity",
            "Required Delivery Date",
            "Special Instructions",
            "Status",
            "Created At",
        ]
    )

    for row in orders_result:
        sheet.append(
            [
                row[0],
                row[1] or "Unknown",
                row[2] or "",
                row[3] or "",
                row[4] or 0,
                row[5] if isinstance(row[5], str) else (row[5].isoformat() if row[5] else ""),
                row[6] or "",
                row[7] or "",
                row[8] if isinstance(row[8], str) else (row[8].isoformat() if row[8] else ""),
            ]
        )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    filename = f"plantmind-orders-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/orders/export/csv")
async def export_orders_csv(request: Request):
    """Export all orders to CSV (lightweight alternative to Excel)."""
    require_office_staff(request)

    db = SessionLocal()
    try:
        orders_result = db.execute(
            text(
                "SELECT o.order_id, c.name, c.email, o.product_name, o.quantity, "
                "o.required_delivery_date, o.special_instructions, o.status, o.created_at "
                "FROM orders o "
                "LEFT JOIN customers c ON c.customer_id = o.customer_id "
                "ORDER BY o.created_at DESC"
            )
        ).fetchall()
    finally:
        db.close()

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Order ID", "Customer", "Customer Email", "Product", "Quantity",
        "Required Delivery Date", "Special Instructions", "Status", "Created At"
    ])
    
    # Data rows
    for row in orders_result:
        writer.writerow([
            row[0],
            row[1] or "Unknown",
            row[2] or "",
            row[3] or "",
            row[4] or 0,
            row[5] if isinstance(row[5], str) else (row[5].isoformat() if row[5] else ""),
            row[6] or "",
            row[7] or "",
            row[8] if isinstance(row[8], str) else (row[8].isoformat() if row[8] else ""),
        ])

    # Get the value and encode to bytes
    csv_content = output.getvalue()
    output.close()

    filename = f"plantmind-orders-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============== ORDER CREATION (Manual) ==============
@router.post("/orders/create")
async def create_order(
    request: Request,
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    product_name: str = Form(...),
    quantity: int = Form(...),
    delivery_date: str = Form(None),
    special_instructions: str = Form(""),
):
    """Create a new order manually (office staff only)"""
    user = require_office_staff(request)
    
    db = SessionLocal()
    try:
        # Find or create customer
        customer = db.query(Customer).filter(Customer.email == customer_email).first()
        
        if not customer:
            customer = Customer(
                name=customer_name,
                email=customer_email,
                created_at=datetime.now(timezone.utc)
            )
            db.add(customer)
            db.flush()
        
        # Parse delivery date if provided
        required_delivery_date = None
        if delivery_date:
            try:
                required_delivery_date = datetime.strptime(delivery_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Create order
        order = Order(
            customer_id=customer.customer_id,
            product_name=product_name,
            quantity=quantity,
            required_delivery_date=required_delivery_date,
            special_instructions=special_instructions,
            status="new",
            created_at=datetime.now(timezone.utc)
        )
        db.add(order)
        db.flush()
        
        # Log status change
        from src.database.models import OrderStatusLog
        status_log = OrderStatusLog(
            order_id=order.order_id,
            old_status=None,
            new_status="new",
            changed_by=user["user_id"],
            change_source="office_staff",
            notes="Manual order creation"
        )
        db.add(status_log)
        
        db.commit()
        
        logger.info(f"Order {order.order_id} created manually by {user['username']}")
        
        return JSONResponse({
            "success": True,
            "message": f"Order ORD-{order.order_id:03d} created successfully",
            "order_id": order.order_id
        })
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ============== AI HEALTH CHECK ==============
@router.get("/health/ai")
async def ai_health_check():
    """Check Ollama AI models status"""
    import httpx
    
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check if Ollama is running
            response = await client.get(f"{ollama_host}/api/tags")
            
            if response.status_code != 200:
                return JSONResponse({
                    "status": "offline",
                    "message": "Ollama not responding"
                }, status_code=503)
            
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            
            # Check for required models
            has_mistral = any("mistral" in m.lower() for m in model_names)
            has_phi3 = any("phi3" in m.lower() for m in model_names)
            
            return JSONResponse({
                "status": "online",
                "ollama_version": response.headers.get("ollama-version", "unknown"),
                "models": model_names,
                "mistral_available": has_mistral,
                "phi3_available": has_phi3,
                "message": "AI models ready" if (has_mistral or has_phi3) else "No models loaded"
            })
            
    except httpx.ConnectError:
        return JSONResponse({
            "status": "offline",
            "message": "Cannot connect to Ollama. Is it running?"
        }, status_code=503)
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


# ============== HEALTH CHECK ==============
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({"status": "healthy", "version": "v1.0.0"})


@router.get("/health/startup")
async def startup_health_check():
    """Detailed startup/runtime readiness checks."""
    report = run_system_self_check()
    status_code = 200 if report["ok"] else 503
    return JSONResponse(
        {
            "status": "ready" if report["ok"] else "degraded",
            "version": "v1.0.0",
            "report": report,
        },
        status_code=status_code,
    )


def create_v1_app(lifespan=None) -> FastAPI:
    """Create FastAPI app with V1 routes"""
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.sessions import SessionMiddleware
    from contextlib import asynccontextmanager

    app = FastAPI(
        title="PlantMind AI V1 - Smart Order Intake",
        description="Version 1 - Automated order intake system",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add session middleware
    app.add_middleware(
        SessionMiddleware,
        secret_key=APP_SECRET_KEY,
        session_cookie=SESSION_COOKIE_NAME,
        max_age=SESSION_MAX_AGE_SECONDS,
        same_site=SESSION_SAME_SITE,
        https_only=SESSION_HTTPS_ONLY,
    )
    app.add_middleware(SecurityHeadersMiddleware)

    # Mount static files
    app.mount("/static", StaticFiles(directory="src/static"), name="static")

    # Include router
    app.include_router(router)

    return app


