"""
Templates Package
Jinja2 template configuration for HTML rendering
"""

from pathlib import Path
from fastapi.templating import Jinja2Templates

# Get the directory containing this file
templates_dir = Path(__file__).parent

# Create Jinja2 templates instance
templates = Jinja2Templates(directory=str(templates_dir))

__all__ = ["templates"]
