"""
Routes Package
Contains API endpoints for the application
"""

from .v1_routes import create_v1_app, router
from .v2_routes import router as v2_router

__all__ = ["router", "create_v1_app", "v2_router"]
