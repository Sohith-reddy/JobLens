"""
Resume-JD matching and scoring module.
"""

from core.matching.match_scorer import (
    compute_match,
    compute_fit_score,
    compute_credibility_score,
    generate_heuristic_suggestions,
    generate_llm_suggestions,
    FitScore,
    CredibilityScore,
    Suggestions,
    MatchResult,
    get_embedding_model,
    get_embeddings,
)

__all__ = [
    "compute_match",
    "compute_fit_score",
    "compute_credibility_score",
    "generate_heuristic_suggestions",
    "generate_llm_suggestions",
    "FitScore",
    "CredibilityScore",
    "Suggestions",
    "MatchResult",
    "get_embedding_model",
    "get_embeddings",
]
