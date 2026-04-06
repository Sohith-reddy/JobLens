"""
Job scam detection scoring module.
"""

from core.scoring.gate_scorer import (
    evaluate_job_posting,
    evaluate_rules,
    get_model,
    get_rules_summary,
    clear_model_cache,
    add_rule,
    Severity,
    Rule,
    RuleHit,
    ScoringResult,
    RULES,
    _model_cache,
)

__all__ = [
    "evaluate_job_posting",
    "evaluate_rules",
    "get_model",
    "get_rules_summary",
    "clear_model_cache",
    "add_rule",
    "Severity",
    "Rule",
    "RuleHit",
    "ScoringResult",
    "RULES",
    "_model_cache",
]
