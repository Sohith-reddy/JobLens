"""
Pydantic models for resume matching endpoints.
"""

from typing import Optional

from pydantic import BaseModel, Field


class BasicsSchema(BaseModel):
    """Resume basics schema."""
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[str] = Field(default_factory=list)


class SkillsSchema(BaseModel):
    """Resume skills schema."""
    technical: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)


class ExperienceEntry(BaseModel):
    """Resume experience entry."""
    company: str = ""
    title: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = Field(default_factory=list)
    tech: list[str] = Field(default_factory=list)
    impact_metrics: list[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    """Resume project entry."""
    name: str = ""
    bullets: list[str] = Field(default_factory=list)
    tech: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    """Resume education entry."""
    school: str = ""
    degree: str = ""
    start: str = ""
    end: str = ""


class ResumeSchemaModel(BaseModel):
    """Complete resume schema."""
    basics: BasicsSchema = Field(default_factory=BasicsSchema)
    summary: str = ""
    skills: SkillsSchema = Field(default_factory=SkillsSchema)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class ResumeParseResult(BaseModel):
    """Resume parsing result."""
    schema_: ResumeSchemaModel = Field(alias="schema")
    raw_text: str
    parse_warnings: list[str] = Field(default_factory=list)
    parse_confidence: float = Field(ge=0.0, le=1.0)

    class Config:
        populate_by_name = True


class FitScoreComponents(BaseModel):
    """Fit score component breakdown."""
    skill_match: int = Field(ge=0, le=35)
    experience_match: int = Field(ge=0, le=30)
    ats_keyword_match: int = Field(ge=0, le=20)
    role_alignment: int = Field(ge=0, le=15)


class FitScoreResult(BaseModel):
    """Fit score result."""
    overall: int = Field(ge=0, le=100)
    components: FitScoreComponents
    must_have_gaps: list[str] = Field(default_factory=list)
    evidence_map: dict[str, list[str]] = Field(default_factory=dict)


class CredibilitySignals(BaseModel):
    """Credibility score signals."""
    specificity: int = Field(ge=0, le=25)
    consistency: int = Field(ge=0, le=25)
    verifiability: int = Field(ge=0, le=25)
    clarity: int = Field(ge=0, le=25)


class CredibilityScoreResult(BaseModel):
    """Credibility score result."""
    overall: int = Field(ge=0, le=100)
    signals: CredibilitySignals
    boosters: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


class BulletRewrite(BaseModel):
    """Bullet rewrite suggestion."""
    original: str
    rewrite_options: list[str] = Field(default_factory=list)
    why: str = ""
    guardrail_note: str = "Consider adding only if true."


class SuggestionsResult(BaseModel):
    """Improvement suggestions."""
    missing_requirements: list[str] = Field(default_factory=list)
    bullet_rewrites: list[BulletRewrite] = Field(default_factory=list)
    ats_improvements: list[str] = Field(default_factory=list)
    project_recommendations: list[str] = Field(default_factory=list)


class TimingsMs(BaseModel):
    """Timing breakdown in milliseconds."""
    pdf_extract: Optional[int] = None
    parse: Optional[int] = None
    embed: Optional[int] = None
    scoring: Optional[int] = None
    llm: Optional[int] = None


class ResumeMatchResponse(BaseModel):
    """Response model for resume matching."""
    resume_parse: dict = Field(..., description="Resume parsing result with schema, raw_text, warnings, confidence")
    fit_score: FitScoreResult
    credibility_score: CredibilityScoreResult
    suggestions: SuggestionsResult
    timings_ms: dict = Field(default_factory=dict)


class JDValidationResponse(BaseModel):
    """Response when job description fails validation (scam/not a job posting)."""
    is_valid_job_posting: bool = Field(default=False, description="Whether the JD is a valid job posting")
    message: str = Field(..., description="Explanation of why the JD was rejected")
    scam_score: Optional[float] = Field(default=None, description="Scam probability if detected as scam")
    final_label: Optional[str] = Field(default=None, description="Classification: SCAM, SUSPICIOUS, or NOT_JOB_POSTING")
