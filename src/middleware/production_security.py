"""
Production Security Middleware
Additional security hardening for production deployments.
"""

import logging
import re
import time
from typing import Callable, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory rate limiting middleware.
    For production, use Redis-based rate limiting.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        exclude_paths: Optional[list] = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.exclude_paths = exclude_paths or ["/health", "/static/"]
        self.requests: dict[str, list[float]] = {}
        self._last_cleanup = 0.0  # Timestamp of last full cleanup

    def _cleanup_expired_ips(self, now: float) -> None:
        """Remove IPs with no recent requests to prevent memory leak."""
        # Only run full cleanup every 60 seconds
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        expired_ips = [
            ip for ip, times in self.requests.items()
            if not times or now - times[-1] > 60
        ]
        for ip in expired_ips:
            del self.requests[ip]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for excluded paths
        path = request.url.path
        for exclude in self.exclude_paths:
            if path.startswith(exclude):
                return await call_next(request)

        # Get client IP
        client_ip = self._get_client_ip(request)
        now = time.time()

        # Clean old requests for this IP
        if client_ip in self.requests:
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if now - req_time < 60
            ]
        else:
            self.requests[client_ip] = []

        # Periodic cleanup of expired IPs
        self._cleanup_expired_ips(now)

        # Check rate limit
        request_count = len(self.requests[client_ip])
        if request_count >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": 60,
                },
            )

        # Record request
        self.requests[client_ip].append(now)

        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.requests_per_minute - request_count - 1)
        )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request, respecting X-Forwarded-For."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """
    Logs security-relevant request information.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request details
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
        user_agent = request.headers.get("User-Agent", "unknown")
        method = request.method
        path = request.url.path
        
        # Check for suspicious patterns
        suspicious = self._detect_suspicious_request(request)
        if suspicious:
            logger.warning(f"Suspicious request detected: {suspicious} from {client_ip}")

        response = await call_next(request)
        
        duration = time.time() - start_time
        
        # Log response details for security analysis
        logger.info(
            f"{method} {path} - {response.status_code} - {duration:.3f}s - {client_ip}"
        )
        
        return response

    def _detect_suspicious_request(self, request: Request) -> Optional[str]:
        """Detect potentially malicious request patterns."""
        path = request.url.path.lower()
        
        # Path traversal attempts
        if ".." in path or "%2e%2e" in path:
            return "path_traversal"
        
        # SQL injection patterns
        sql_patterns = ["union select", "insert into", "delete from", "drop table", "--", ";--"]
        query = str(request.url.query).lower()
        for pattern in sql_patterns:
            if pattern in query:
                return f"sql_injection_attempt: {pattern}"
        
        # XSS attempts in query params
        xss_patterns = ["<script", "javascript:", "onerror=", "onload="]
        for pattern in xss_patterns:
            if pattern in query:
                return f"xss_attempt: {pattern}"
        
        return None


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    Restrict access to specific IP addresses or CIDR ranges.
    """

    def __init__(self, app, allowed_ips: Optional[list] = None):
        super().__init__(app)
        self.allowed_ips = set(allowed_ips or ["127.0.0.1", "::1"])

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
        
        if client_ip not in self.allowed_ips:
            logger.warning(f"Access denied for IP: {client_ip}")
            return JSONResponse(
                status_code=403,
                content={"error": "Access denied"},
            )
        
        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Limit request body size to prevent DoS.
    """

    def __init__(self, app, max_size_mb: int = 50):
        super().__init__(app)
        self.max_size_bytes = max_size_mb * 1024 * 1024

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        
        if content_length:
            size = int(content_length)
            if size > self.max_size_bytes:
                logger.warning(f"Request too large: {size} bytes from {request.client.host}")
                return JSONResponse(
                    status_code=413,
                    content={"error": f"Request body too large (max {self.max_size_bytes // (1024*1024)}MB)"},
                )
        
        return await call_next(request)


def apply_production_security(app: FastAPI, environment: str = "production") -> None:
    """
    Apply all production security middleware to the FastAPI app.
    """
    if environment == "production":
        # Rate limiting
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=60,
            burst_size=10,
        )
        
        # Security audit logging
        app.add_middleware(SecurityAuditMiddleware)
        
        # Request size limiting
        app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=50)
        
        logger.info("Production security middleware applied")
    else:
        # Development: only add basic audit logging
        app.add_middleware(SecurityAuditMiddleware)
        logger.info("Development security middleware applied")
