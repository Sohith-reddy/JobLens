"""
Pydantic models for system endpoints.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    model_path: str
