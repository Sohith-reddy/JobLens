"""
System endpoints for health checks and configuration.
"""

import logging

from fastapi import APIRouter

from api.models.scoring import RuleSummary, RulesResponse
from api.models.system import HealthResponse
from api.config import DEFAULT_MODEL_PATH

logger = logging.getLogger(__name__)

# System router for health checks
router = APIRouter(tags=["System"])

# Configuration router for rules and settings
config_router = APIRouter(tags=["Configuration"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns the API status and whether the ML model is loaded.
    """
    from core.scoring import _model_cache

    model_loaded = DEFAULT_MODEL_PATH in _model_cache

    return HealthResponse(
        status="ok",
        model_loaded=model_loaded,
        model_path=DEFAULT_MODEL_PATH,
    )


@config_router.get(
    "/rules",
    response_model=RulesResponse,
    summary="List detection rules",
)
async def list_rules() -> RulesResponse:
    """
    List all configured detection rules.

    Returns rule IDs, severities, weights, and explanations.
    """
    from core.scoring import get_rules_summary

    rules = get_rules_summary()
    return RulesResponse(
        rules=[RuleSummary(**r) for r in rules],
        total_rules=len(rules),
    )
