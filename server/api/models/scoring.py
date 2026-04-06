"""
Pydantic models for job scoring endpoints.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    """Request model for scoring a job posting via URL."""
    url: str = Field(..., description="The job posting URL to scrape and analyze")
    use_playwright: bool = Field( 
        default=True , 
        description="Whether to use Playwright for JS-heavy sites"
    )
    model_path: Optional[str] = Field(
        default=None,
        description="Optional path to model artifact (defaults to job_scam_model.joblib)"
    )
    t_high: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="High threshold for SCAM classification"
    )
    t_low: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Low threshold for SUSPICIOUS classification"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://www.linkedin.com/jobs/view/1234567890",
                }
            ]
        }
    }


class RuleHitResponse(BaseModel):
    """A single rule hit in the response."""
    rule_id: str
    severity: str
    matched_text_or_pattern: str
    explanation: str


class ScoreResponse(BaseModel):
    """Response model for scoring results."""
    ml_probability: float = Field(..., description="ML model's scam probability (0-1)")
    ml_pred: int = Field(..., description="ML prediction using artifact threshold (0=legit, 1=scam)")
    rule_hits: list[RuleHitResponse] = Field(..., description="List of triggered rules")
    rule_score: float = Field(..., description="Total rule severity score")
    final_label: str = Field(..., description="Final classification: LEGIT, SUSPICIOUS, SCAM, or NOT_JOB_POSTING")
    final_reason: str = Field(..., description="Human-readable explanation for the classification")
    decision_path: list[str] = Field(..., description="Step-by-step decision explanation")
    is_job_posting: bool = Field(default=True, description="Whether the text is a valid job posting")


class NotJobPostingResponse(BaseModel):
    """Simple response when content is not a job posting."""
    is_job_posting: bool = Field(default=False, description="Always False for this response type")
    message: str = Field(..., description="Simple message explaining why this is not a job posting")


class NotJobPostingURLResponse(BaseModel):
    """Simple response when URL content is not a job posting."""
    url: str = Field(..., description="The URL that was analyzed")
    is_job_posting: bool = Field(default=False, description="Always False for this response type")
    message: str = Field(..., description="Simple message explaining why this is not a job posting")


class ScoreURLRequest(BaseModel):
    """Request model for scoring a job posting from URL."""
    url: str = Field(..., description="The job posting URL to scrape and analyze")

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://www.linkedin.com/jobs/view/1234567890"
            }
        }
    }


class ScoreURLResponse(BaseModel):
    """Response model for URL scoring results."""
    url: str = Field(..., description="The original URL that was scraped")
    final_extracted_text: str = Field(..., description="The job description text extracted from the page")
    extraction_method: str = Field(..., description="Method used for extraction")
    extraction_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for extraction quality")
    score_result: ScoreResponse = Field(..., description="The scam detection scoring result")
    warnings: list[str] = Field(default_factory=list, description="Warnings about extraction quality")


class RuleSummary(BaseModel):
    """Summary of a detection rule."""
    rule_id: str
    severity: str
    severity_weight: float
    explanation: str
    pattern_count: int


class RulesResponse(BaseModel):
    """Response containing all rules."""
    rules: list[RuleSummary]
    total_rules: int
