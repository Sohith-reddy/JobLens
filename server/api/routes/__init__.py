"""
API route modules.
"""

from api.routes.scoring import router as scoring_router
from api.routes.resume import router as resume_router
from api.routes.system import router as system_router, config_router

__all__ = ["scoring_router", "resume_router", "system_router", "config_router"]
