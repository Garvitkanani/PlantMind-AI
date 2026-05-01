"""
Security helpers and middleware for PlantMind AI.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import HTTPException


def _get_session_user(request) -> dict:
    """
    Build a user dict from the session.
    The login handler stores user_id, username, role as flat session keys.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "user_id": user_id,
        "username": request.session.get("username", ""),
        "role": request.session.get("role", ""),
    }


def require_supervisor(request):
    """Require supervisor role for access"""
    user = _get_session_user(request)
    if user.get("role") not in ["supervisor", "owner", "office_staff", "admin"]:
        raise HTTPException(status_code=403, detail="Supervisor access required")
    return user


def require_store_staff(request):
    """Require store staff role for access"""
    user = _get_session_user(request)
    if user.get("role") not in ["store", "store_staff", "owner", "office_staff", "admin"]:
        raise HTTPException(status_code=403, detail="Store staff access required")
    return user


def require_owner(request):
    """Require owner role for access"""
    user = _get_session_user(request)
    if user.get("role") not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Owner access required")
    return user


def require_office_staff(request):
    """Require office staff role for access"""
    user = _get_session_user(request)
    if user.get("role") not in ["office", "office_staff", "owner", "admin"]:
        raise HTTPException(status_code=403, detail="Office staff access required")
    return user


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add defensive HTTP headers to all responses."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data:; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )
        return response

