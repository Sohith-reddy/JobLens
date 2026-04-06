"""
Pydantic models for API request/response schemas.
"""

from api.models.scoring import (
    ScoreRequest,
    ScoreResponse,
    ScoreURLRequest,
    ScoreURLResponse,
    NotJobPostingResponse,
    NotJobPostingURLResponse,
    RuleHitResponse,
    RuleSummary,
    RulesResponse,
)
from api.models.resume import (
    BasicsSchema,
    SkillsSchema,
    ExperienceEntry,
    ProjectEntry,
    EducationEntry,
    ResumeSchemaModel,
    ResumeParseResult,
    FitScoreComponents,
    FitScoreResult,
    CredibilitySignals,
    CredibilityScoreResult,
    BulletRewrite,
    SuggestionsResult,
    TimingsMs,
    ResumeMatchResponse,
    JDValidationResponse,
)
from api.models.system import HealthResponse

__all__ = [
    # Scoring models
    "ScoreRequest",
    "ScoreResponse",
    "ScoreURLRequest",
    "ScoreURLResponse",
    "NotJobPostingResponse",
    "NotJobPostingURLResponse",
    "RuleHitResponse",
    "RuleSummary",
    "RulesResponse",
    # Resume models
    "BasicsSchema",
    "SkillsSchema",
    "ExperienceEntry",
    "ProjectEntry",
    "EducationEntry",
    "ResumeSchemaModel",
    "ResumeParseResult",
    "FitScoreComponents",
    "FitScoreResult",
    "CredibilitySignals",
    "CredibilityScoreResult",
    "BulletRewrite",
    "SuggestionsResult",
    "TimingsMs",
    "ResumeMatchResponse",
    "JDValidationResponse",
    # System models
    "HealthResponse",
]
