"""
Gate-based scam detection module for JobLens AI.

Combines ML model predictions with rule-based red flag detection using a gate-based ensemble:
- Critical rules can hard-override the ML prediction
- Otherwise, ML score combined with rule severity determines final label
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache

import numpy as np
from joblib import load
from sentence_transformers import SentenceTransformer

from core.clients.model_artifact import ModelArtifact  # noqa: F401 - needed for unpickling
from core.clients.groq_client import check_job_posting_relevance, is_groq_available


class Severity(Enum):
    """Rule severity levels with associated weights."""
    LOW = 0.25
    MEDIUM = 0.75
    HIGH = 1.25
    CRITICAL = 2.0


@dataclass
class Rule:
    """A scam detection rule with compiled regex patterns."""
    rule_id: str
    severity: Severity
    patterns: List[re.Pattern]
    explanation: str
    
    @classmethod
    def create(cls, rule_id: str, severity: Severity, patterns: List[str], explanation: str) -> "Rule":
        """Create a rule with compiled regex patterns."""
        compiled = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
        return cls(rule_id=rule_id, severity=severity, patterns=compiled, explanation=explanation)


@dataclass
class RuleHit:
    """A matched rule with details."""
    rule_id: str
    severity: str
    matched_text_or_pattern: str
    explanation: str


@dataclass
class ScoringResult:
    """Complete scoring result from the gate-based ensemble."""
    ml_probability: float
    ml_pred: int
    rule_hits: List[Dict[str, Any]]
    rule_score: float
    final_label: str
    final_reason: str
    decision_path: List[str]
    is_job_posting: bool = True  # Default to True for backward compatibility
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ml_probability": self.ml_probability,
            "ml_pred": self.ml_pred,
            "rule_hits": self.rule_hits,
            "rule_score": self.rule_score,
            "final_label": self.final_label,
            "final_reason": self.final_reason,
            "decision_path": self.decision_path,
            "is_job_posting": self.is_job_posting,
        }


# =============================================================================
# RULE DEFINITIONS
# =============================================================================

RULES: List[Rule] = [
    # =========================================================================
    # CRITICAL RULES - Hard override to SCAM
    # =========================================================================
    
    # Upfront fees / deposits / activation fees
    Rule.create(
        rule_id="CRIT_UPFRONT_FEE",
        severity=Severity.CRITICAL,
        patterns=[
            r"(?:registration|processing|application|training|activation|onboarding|joining)\s+fee",
            r"(?:refundable|non[- ]?refundable)\s+(?:fee|deposit|amount)",
            r"pay\s+(?:to\s+)?(?:apply|register|join|start|begin)",
            r"fee\s+(?:of|is|:)\s*(?:rs\.?|₹|inr|\$|usd)?\s*\d+",
            r"deposit\s+(?:of|is|:)\s*(?:rs\.?|₹|inr|\$|usd)?\s*\d+",
            r"(?:advance|upfront)\s+(?:payment|fee|amount|deposit)",
            r"security\s+deposit",
            r"deposit\s+for\s+(?:training|resources|materials|equipment|laptop|software|tools)",
            r"activation\s+(?:fee|charge|cost|amount)",
            r"(?:pay|payment)\s+(?:for\s+)?(?:kit|starter\s+kit|training\s+kit|materials)",
        ],
        explanation="Legitimate jobs never ask for money upfront"
    ),
    
    # SSN / sensitive documents UPFRONT (before hiring) - scam indicator
    # Note: Legitimate companies ask for docs AFTER selection for onboarding, not before
    # IMPORTANT: Patterns should NOT match educational/warning text about fraud
    Rule.create(
        rule_id="CRIT_SENSITIVE_DOCS_UPFRONT",
        severity=Severity.CRITICAL,
        patterns=[
            # SSN is almost never asked upfront - always suspicious
            r"(?:send|provide|submit|share)\s+(?:your\s+)?(?:ssn|social\s+security)\s*(?:number|#)?",
            r"(?:ssn|social\s+security)\s*(?:number|#)?\s+(?:required|needed)\s+(?:to\s+)?(?:apply|register|start|proceed)",
            # Bank details BEFORE hiring (not for salary setup after joining)
            r"(?:send|provide|share)\s+(?:your\s+)?bank\s+(?:account|details|information)\s+(?:to\s+)?(?:apply|register|start|proceed)",
            r"bank\s+(?:account|details)\s+(?:for|to)\s+(?:registration|application|processing)",
            # Asking to EMAIL/SEND sensitive docs (vs bringing to interview/onboarding)
            r"(?:email|send|whatsapp|text)\s+(?:us\s+)?(?:your\s+)?(?:id|passport|aadhaar|pan|ssn|bank)\s+(?:details|copy|scan|photo)",
            # Government ID for "verification" before any interview - but NOT educational text
            r"(?:government|govt)\s+id\s+(?:verification|proof)\s+(?:for|to)\s+(?:registration|application|processing)",
            # Scam pattern: ID required to "start" or "proceed" (not for onboarding after selection)
            r"(?:id|identity)\s+(?:proof|verification)\s+(?:required|needed)\s+(?:to\s+)?(?:start|proceed|apply|register)",
            # Direct request patterns - "please submit/provide your PAN before interview"
            r"(?:please\s+)?(?:submit|provide|send|share|upload)\s+(?:your\s+)?(?:pan\s+card|pan|aadhaar|aadhar|passport|govt?\s+id)\s+(?:before|prior\s+to)\s+(?:the\s+)?(?:interview|selection)",
            # "PAN required before interview" (direct requirement, not description)
            r"(?:pan\s+card|aadhaar|passport)\s+(?:is\s+)?(?:required|needed|mandatory)\s+(?:before|prior\s+to)\s+(?:interview|selection|offer)",
            # Submit documents to apply/register (not for post-selection onboarding)
            r"(?:submit|upload|attach)\s+(?:your\s+)?(?:pan\s+card|aadhaar|passport|government\s+id|identity\s+proof)\s+(?:to\s+)?(?:apply|register|proceed)",
            # "We need your PAN/ID before..." (direct collection request)
            r"(?:we\s+)?(?:need|require|collect)\s+(?:your\s+)?(?:pan|aadhaar|passport|id)\s+(?:details?|information|copy|number)\s+(?:before|prior\s+to)\s+(?:interview|offer|selection)",
            # KEY: "Requiring candidates to submit PAN before interview" - but NOT if it's educational text
            # Educational text contains "fraud indicator", "scam", "red flag" later in the same sentence
            # Use negative lookahead to exclude sentences that mention it's a fraud/scam indicator
            r"(?:requiring|require)\s+(?:candidates?\s+)?(?:to\s+)?submit\s+(?:a\s+)?(?:pan\s+card|government[- ]?(?:issued\s+)?(?:id|identification))[^.]*?before\s+(?:conducting\s+)?(?:an?\s+)?interview(?![^.]*(?:fraud|scam|red\s+flag|warning|indicator))",
        ],
        explanation="Asking for PAN/ID/sensitive documents before interview or formal offer is a scam indicator"
    ),
    
    # Crypto / gift card payments
    # IMPORTANT: Exclude negation contexts like "never pay in bitcoin", "will not ask for gift cards"
    # These are often warnings about scams in legitimate job postings
    Rule.create(
        rule_id="CRIT_CRYPTO_GIFTCARD",
        severity=Severity.CRITICAL,
        patterns=[
            # Crypto payment requests - exclude negation
            r"(?<!never\s)(?<!not\s)(?<!won't\s)(?<!will\snot\s)(?:pay|payment|send|transfer)\s+(?:via|through|in|using)\s+(?:bitcoin|btc|ethereum|eth|usdt|crypto)(?!\s+is\s+(?:a\s+)?(?:scam|fraud|fake))",
            r"(?<!never\s)(?<!not\s)(?:bitcoin|btc|ethereum|eth|usdt|crypto(?:currency)?)\s+(?:payment|transfer|deposit|wallet)(?!\s+(?:scam|fraud|warning))",
            # Gift card requests - exclude negation and warnings
            r"(?<!never\s)(?<!not\s)(?<!won't\s)(?<!no\s)(?:buy|purchase|send|get)\s+(?:\w+\s+)?gift\s+cards?(?!\s+(?:scam|fraud|warning))",
            r"(?<!never\s)(?<!not\s)(?<!won't\s)(?:pay|payment)\s+(?:with|using|via)\s+gift\s+cards?",
            # Direct gift card mentions in payment context (not warnings)
            r"(?:send|provide|purchase)\s+(?:us\s+)?(?:\$?\d+\s+)?(?:worth\s+of\s+)?(?:itunes|amazon|google\s+play|steam|walmart)\s+(?:gift\s+)?cards?",
            r"(?:itunes|amazon|google\s+play|steam|walmart)\s+(?:gift\s+)?card\s+(?:code|number|pin)",
        ],
        explanation="Crypto or gift card payments for jobs are always scams"
    ),
    
    # Personal wallet / personal banking for business
    Rule.create(
        rule_id="CRIT_PERSONAL_BANKING",
        severity=Severity.CRITICAL,
        patterns=[
            r"(?:personal|my|individual)\s+(?:wallet|bank\s+account|account|paypal|venmo|zelle|cashapp)",
            r"(?:send|transfer|deposit)\s+(?:to|into)\s+(?:personal|my|this)\s+(?:account|wallet)",
            r"(?:use|using)\s+(?:your|my)\s+(?:personal\s+)?(?:bank\s+account|wallet|paypal)",
            r"(?:wire|transfer)\s+(?:to|into)\s+(?:this|the\s+following)\s+(?:personal\s+)?account",
            r"(?:your|my)\s+(?:personal\s+)?(?:bank|banking)\s+(?:for|to\s+handle)\s+(?:transactions?|payments?|transfers?)",
        ],
        explanation="Legitimate companies never use personal wallets or banking for business transactions"
    ),
    
    # Wire transfer requirements
    Rule.create(
        rule_id="CRIT_WIRE_TRANSFER",
        severity=Severity.CRITICAL,
        patterns=[
            r"wire\s+transfer\s+(?:required|needed|only|to)",
            r"(?:send|make)\s+(?:a\s+)?wire\s+transfer",
            r"(?:western\s+union|moneygram|money\s+order)",
            r"(?:transfer|send|wire)\s+(?:funds?|money|amount)\s+(?:to|via)",
            r"(?:bank\s+)?wire\s+(?:to|for)\s+(?:processing|registration|activation)",
        ],
        explanation="Wire transfer requests for jobs are always scams"
    ),
    
    # Messaging app only communication
    Rule.create(
        rule_id="CRIT_MESSAGING_APP_ONLY",
        severity=Severity.CRITICAL,
        patterns=[
            r"(?:contact|reach|message|communicate)\s+(?:us\s+)?(?:only\s+)?(?:on|via|through)\s+(?:telegram|whatsapp|signal|wechat)",
            r"(?:telegram|whatsapp|signal)\s+only",
            r"no\s+(?:official\s+)?(?:email|phone)",
            r"(?:dm|direct\s+message)\s+(?:on|via)\s+(?:telegram|whatsapp)",
            r"(?:all|only)\s+(?:communication|contact)\s+(?:via|through|on)\s+(?:telegram|whatsapp)",
            r"(?:text|message)\s+(?:me|us)\s+(?:on|at)\s+(?:telegram|whatsapp)",
        ],
        explanation="Legitimate companies use official channels, not just messaging apps"
    ),
    
    # Personal residence for logistics/shipping
    Rule.create(
        rule_id="CRIT_PERSONAL_RESIDENCE",
        severity=Severity.CRITICAL,
        patterns=[
            r"(?:use|using)\s+(?:your|personal)\s+(?:home|residence|address)\s+(?:for|to)\s+(?:shipping|logistics|receiving|packages?|deliveries?)",
            r"(?:ship|send|receive)\s+(?:packages?|items?|products?)\s+(?:to|from|at)\s+(?:your|home)\s+(?:address|residence)",
            r"(?:home|residential)\s+(?:address|location)\s+(?:for|as)\s+(?:warehouse|storage|shipping\s+point)",
            r"(?:packages?|shipments?)\s+(?:will\s+)?(?:arrive|come|be\s+sent)\s+(?:to|at)\s+(?:your\s+)?(?:home|residence)",
            r"(?:reship|re-ship|forward)\s+(?:packages?|items?)\s+(?:from\s+)?(?:your\s+)?(?:home|address)",
        ],
        explanation="Using personal residence for logistics is a reshipping scam indicator"
    ),
    
    # =========================================================================
    # HIGH SEVERITY RULES
    # =========================================================================
    
    # No interview / no formal hiring process
    Rule.create(
        rule_id="HIGH_NO_INTERVIEW",
        severity=Severity.HIGH,
        patterns=[
            r"no\s+interview\s+(?:required|needed|necessary)",
            r"(?:direct|immediate|instant)\s+(?:hiring|selection|offer|job)\s+(?:without|no)\s+interview",
            r"(?:skip|bypass|no\s+need\s+for)\s+(?:the\s+)?interview",
            r"(?:hired|selected|chosen)\s+(?:without|no)\s+(?:any\s+)?interview",
            r"no\s+(?:formal\s+)?(?:interview|hiring)\s+process",
            r"(?:interview|screening)\s+(?:not\s+)?(?:required|needed|necessary)",
        ],
        explanation="No interview process is a major red flag"
    ),
    
    # High pay for minimal work / guaranteed high pay
    Rule.create(
        rule_id="HIGH_UNREALISTIC_PAY",
        severity=Severity.HIGH,
        patterns=[
            r"(?:earn|make|get)\s+(?:up\s+to\s+)?(?:rs\.?|₹|inr|\$|usd)?\s*\d{3,}[,.]?\d*\s*(?:per|/|a)\s*(?:day|hour)",
            r"(?:rs\.?|₹|inr|\$)\s*\d+[,.]?\d*\s*(?:k|lakh|lac)?\s*(?:per|/)\s*(?:week|day)",
            r"(?:high|great|excellent|amazing|incredible)\s+(?:pay|salary|income|earnings?)\s+(?:for\s+)?(?:minimal|little|easy|simple|basic)\s+(?:work|effort|tasks?)",
            r"(?:guaranteed|fixed)\s+(?:daily|weekly|monthly)\s+(?:income|pay|salary|earnings?)\s+(?:of\s+)?(?:rs\.?|₹|inr|\$)?\s*\d+",
            r"(?:daily|weekly)\s+(?:pay|payment|deposit|income)\s+(?:of\s+)?(?:rs\.?|₹|inr|\$)?\s*\d{2,}",
            r"(?:immediate|instant|same[- ]?day)\s+(?:daily\s+)?(?:pay|payment|deposit)",
            r"(?:no\s+(?:experience|skills?|qualification)\s+(?:required|needed))[^.]*(?:(?:rs\.?|₹|inr|\$)\s*\d{2,}|(?:high|great|excellent)\s+(?:salary|pay))",
        ],
        explanation="Unrealistic pay promises for minimal work are scam indicators"
    ),
    
    # Guaranteed job / placement
    Rule.create(
        rule_id="HIGH_GUARANTEED_JOB",
        severity=Severity.HIGH,
        patterns=[
            r"(?:100%|guaranteed|sure\s+shot|definite)\s+(?:job|placement|selection|offer|career|employment)",
            r"(?:confirmed|guaranteed)\s+(?:pre[- ]?placement|ppo|offer)",
            r"job\s+(?:guarantee|assured|confirmed)",
            r"guarantee[sd]?\s+(?:career|placement|job|employment)",
            r"guaranteed\s+(?:placement|job|position|employment)\s+(?:letter|offer|after|upon)",
            r"(?:placement|job|employment)\s+(?:is\s+)?(?:guaranteed|assured|confirmed)",
            r"(?:we\s+)?guarantee\s+(?:you\s+)?(?:a\s+)?(?:job|position|employment|placement)",
        ],
        explanation="No legitimate employer can guarantee placement"
    ),
    
    # Urgency and scarcity tactics
    # NOTE: "Apply now" alone is common on legitimate sites, so we look for more aggressive patterns
    Rule.create(
        rule_id="HIGH_URGENCY_SCARCITY",
        severity=Severity.HIGH,
        patterns=[
            # Extreme scarcity - very limited positions
            r"(?:single|only\s+(?:one|\d))\s+(?:vacancy|position|opening|slot|seat)",
            r"(?:very\s+)?limited\s+(?:vacancy|positions?|openings?|slots?|seats?)\s+(?:left|remaining|available)",
            # Urgent hiring with pressure
            r"(?:urgent(?:ly)?|immediate(?:ly)?)\s+(?:hiring|looking|need|require|opening)[^.]*(?:apply|contact|call)",
            # Don't miss / last chance
            r"(?:don'?t|do\s+not)\s+miss\s+(?:this|the)\s+(?:opportunity|chance)",
            r"(?:last|final)\s+(?:chance|opportunity|day|call)\s+(?:to\s+)?(?:apply|join|register)",
            # Closing soon with specific timeframe
            r"(?:closing|expires?|ends?)\s+(?:today|tomorrow|in\s+\d+\s+(?:hours?|days?))",
            # Act fast with urgency words (not just "apply now")
            r"(?:act|respond)\s+(?:fast|quick(?:ly)?|immediately|urgently)",
            r"(?:hurry|rush)[^.]*(?:apply|register|join)",
            # Apply immediately/urgently (stronger than just "apply now")
            r"apply\s+(?:urgent(?:ly)?|immediately)\s+(?:to|for|at)",
        ],
        explanation="Artificial urgency and scarcity are manipulation tactics"
    ),
    
    # Generic Gmail / free email for business
    Rule.create(
        rule_id="HIGH_GENERIC_EMAIL",
        severity=Severity.HIGH,
        patterns=[
            r"(?:contact|email|apply|send\s+(?:resume|cv))\s+(?:to|at)[^@]*@(?:gmail|yahoo|hotmail|outlook|aol|mail)\.com",
            r"(?:hr|hiring|recruitment|jobs?)[^@]*@(?:gmail|yahoo|hotmail|outlook)\.com",
            r"(?:our\s+)?(?:company|organization|firm|business)[^.]*@(?:gmail|yahoo|hotmail)\.com",
            r"@(?:gmail|yahoo|hotmail|outlook)\.com[^.]*(?:pvt|ltd|inc|corp|llc|company|enterprise)",
        ],
        explanation="Legitimate companies use professional email domains, not Gmail/Yahoo"
    ),
    
    # Encrypted / suspicious email domains
    Rule.create(
        rule_id="HIGH_SUSPICIOUS_DOMAIN",
        severity=Severity.HIGH,
        patterns=[
            r"@(?:protonmail|tutanota|guerrillamail|tempmail|10minutemail|mailinator)\.(?:com|ch|de|org)",
            r"@(?:\w+)?(?:secure|encrypted|private|anonymous)(?:\w+)?\.(?:com|org|net)",
            r"@(?:\w{10,}|\d{5,})\.(?:com|org|net)",
            r"(?:encrypted|secure|private)\s+email\s+(?:address|domain|only)",
        ],
        explanation="Encrypted or suspicious email domains are red flags"
    ),
    
    # WFH with urgency
    Rule.create(
        rule_id="HIGH_WFH_SCAM",
        severity=Severity.HIGH,
        patterns=[
            r"work\s+from\s+home[^.]*(?:immediate|urgent|limited\s+(?:slots?|positions?|openings?))",
            r"(?:immediate|urgent)\s+(?:start|joining)[^.]*work\s+from\s+home",
            r"limited\s+(?:slots?|positions?|openings?|seats?)[^.]*(?:work\s+from\s+home|wfh|remote)",
            r"(?:wfh|work\s+from\s+home)[^.]*(?:no\s+experience|anyone\s+can|easy\s+money)",
        ],
        explanation="WFH with urgency and limited slots is a common scam pattern"
    ),
    
    # =========================================================================
    # MEDIUM SEVERITY RULES
    # =========================================================================
    
    # Vague company / executive identity
    Rule.create(
        rule_id="MED_VAGUE_IDENTITY",
        severity=Severity.MEDIUM,
        patterns=[
            r"(?:reputed|leading|top|famous|well[- ]?known)\s+(?:mnc|company|organization|group|firm)",
            r"(?:a|an)\s+leading\s+(?:\w+\s+){0,3}(?:company|group|firm|organization)",
            r"(?:international|global|multinational)\s+(?:company|organization|firm|group)",
            r"confidential\s+(?:client|company|project|employer)",
            r"(?:prestigious|renowned|established)\s+(?:company|organization|firm|group)",
            r"(?:ceo|cfo|director|manager|executive)\s+(?:of\s+)?(?:a\s+)?(?:leading|top|major)",
            r"(?:undisclosed|unnamed|anonymous)\s+(?:company|client|employer)",
            r"(?:our\s+)?(?:client|company)\s+(?:prefers?\s+to\s+)?(?:remain|stay)\s+(?:anonymous|confidential)",
        ],
        explanation="Vague company or executive descriptions without naming them"
    ),
    
    # Immediate onboarding / no formal process
    Rule.create(
        rule_id="MED_RUSHED_HIRING",
        severity=Severity.MEDIUM,
        patterns=[
            r"immediate\s+(?:onboarding|joining|start|hiring)",
            r"(?:onboarding|joining|start)\s+(?:within|in)\s+(?:\d+\s+)?(?:hours?|days?)",
            r"(?:brief|short|quick|5[- ]?minute)\s+interview",
            r"(?:start|begin|join)\s+(?:work(?:ing)?|immediately|today|tomorrow)",
            r"(?:no|skip)\s+(?:background\s+check|verification|screening)",
            r"(?:hired|selected)\s+(?:on\s+the\s+)?(?:spot|immediately|instantly)",
        ],
        explanation="Legitimate companies have proper hiring processes, not rushed onboarding"
    ),
    
    # Vague operational details
    Rule.create(
        rule_id="MED_VAGUE_OPERATIONS",
        severity=Severity.MEDIUM,
        patterns=[
            r"(?:simple|easy|basic)\s+(?:tasks?|work|job|duties)",
            r"(?:details|information)\s+(?:will\s+be\s+)?(?:provided|shared|given)\s+(?:later|after|upon)",
            r"(?:more|full)\s+(?:details|information)\s+(?:after|upon)\s+(?:joining|registration|payment)",
            r"(?:job|work|task)\s+(?:details|description)\s+(?:to\s+be\s+)?(?:discussed|shared)\s+(?:later|privately)",
            r"(?:training|orientation)\s+(?:will\s+)?(?:explain|cover)\s+(?:everything|all\s+details)",
        ],
        explanation="Vague operational details are suspicious"
    ),
    
    # Spam-like phrases
    Rule.create(
        rule_id="MED_SPAM_PHRASES",
        severity=Severity.MEDIUM,
        patterns=[
            r"congratulations[,!]?\s+you\s+(?:are|have\s+been)\s+(?:selected|shortlisted|chosen)",
            r"you\s+(?:have\s+)?won\s+(?:a\s+)?(?:job|position|opportunity)",
            r"(?:dear\s+)?(?:candidate|applicant|job\s+seeker)[,!]\s+(?:congratulations|you\s+(?:are|have))",
            r"(?:selected|chosen)\s+(?:for\s+)?(?:a\s+)?(?:special|exclusive|unique)\s+opportunity",
            r"(?:you'?ve\s+been|you\s+are)\s+(?:pre[- ]?)?(?:selected|approved|qualified)",
        ],
        explanation="Spam-like congratulatory messages without application are scams"
    ),
    
    # Unrealistic earnings claims
    Rule.create(
        rule_id="MED_UNREALISTIC_EARNINGS",
        severity=Severity.MEDIUM,
        patterns=[
            r"(?:unlimited|passive|residual)\s+(?:income|earning|money)",
            r"(?:make|earn)\s+money\s+(?:while\s+you\s+)?(?:sleep|do\s+nothing)",
            r"(?:financial\s+)?freedom\s+(?:in|within)\s+(?:\d+\s+)?(?:days?|weeks?|months?)",
            r"(?:get\s+)?rich\s+(?:quick(?:ly)?|fast|easily)",
            r"(?:easy|quick|fast)\s+money",
            r"(?:money|income)\s+(?:on\s+)?(?:autopilot|auto[- ]?pilot)",
        ],
        explanation="Unrealistic earning promises are red flags"
    ),
    
    # Urgency with external channels
    Rule.create(
        rule_id="MED_URGENCY_EXTERNAL",
        severity=Severity.MEDIUM,
        patterns=[
            r"(?:act\s+now|apply\s+(?:now|immediately|today)|hurry)[^.]*(?:whatsapp|telegram|call)",
            r"(?:hiring\s+immediately|urgent\s+(?:requirement|hiring|opening))[^.]*(?:contact|call|whatsapp|telegram)",
            r"(?:limited\s+time|closing\s+soon|vacancy\s+closes)[^.]*(?:apply|contact|call)",
            r"(?:call|text|message)\s+(?:now|immediately|urgently)\s+(?:at|on)?\s*(?:\+?\d{10,}|whatsapp|telegram)",
        ],
        explanation="Urgency combined with informal contact channels is suspicious"
    ),
    
    # =========================================================================
    # LOW SEVERITY RULES
    # =========================================================================
    
    # Formatting issues
    Rule.create(
        rule_id="LOW_FORMATTING_ISSUES",
        severity=Severity.LOW,
        patterns=[
            r"[!]{3,}",
            r"[?]{3,}",
            r"[\U0001F300-\U0001F9FF]{3,}",  # 3+ consecutive emojis
            r"[A-Z\s]{30,}",  # Long ALL CAPS sections
            r"\$+\s*\$+",  # Multiple dollar signs
            r"(?:earn|make|get)\s*\$+",
        ],
        explanation="Excessive formatting (caps, punctuation, emojis) is unprofessional"
    ),
    
    # Poor grammar / spelling (common in scams)
    Rule.create(
        rule_id="LOW_POOR_GRAMMAR",
        severity=Severity.LOW,
        patterns=[
            r"(?:kindly\s+)?(?:do\s+the\s+)?needful",
            r"(?:revert|revert\s+back)\s+(?:to\s+)?(?:us|me)",
            r"(?:your\s+)?good\s+(?:self|name)",
            r"(?:we\s+)?(?:are\s+)?(?:hiring|looking)\s+(?:for\s+)?(?:the\s+)?(?:candidate|candidates|peoples?)",
        ],
        explanation="Poor grammar and unusual phrasing common in scam postings"
    ),
]


# =============================================================================
# MODEL CACHING
# =============================================================================

_model_cache: Dict[str, Tuple[Any, SentenceTransformer]] = {}


def get_model(model_path: str = "job_scam_model.joblib") -> Tuple[Any, SentenceTransformer]:
    """
    Load and cache the ML model and embedder.
    
    Returns:
        Tuple of (artifact, embedder)
    """
    if model_path not in _model_cache:
        artifact = load(model_path)
        
        # Detect device
        try:
            import torch
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        except Exception:
            device = "cpu"
        
        embedder = SentenceTransformer(artifact.embedding_model, device=device)
        _model_cache[model_path] = (artifact, embedder)
    
    return _model_cache[model_path]


def clear_model_cache() -> None:
    """Clear the model cache (useful for testing)."""
    _model_cache.clear()


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================

def evaluate_rules(text: str) -> Tuple[List[RuleHit], float]:
    """
    Evaluate all rules against the text.
    
    Returns:
        Tuple of (list of rule hits, total rule score)
    """
    hits: List[RuleHit] = []
    total_score = 0.0
    
    for rule in RULES:
        for pattern in rule.patterns:
            match = pattern.search(text)
            if match:
                hits.append(RuleHit(
                    rule_id=rule.rule_id,
                    severity=rule.severity.name,
                    matched_text_or_pattern=match.group(0)[:100],  # Truncate long matches
                    explanation=rule.explanation,
                ))
                total_score += rule.severity.value
                break  # Only count each rule once
    
    return hits, total_score


def evaluate_job_posting(
    text: str,
    model_path: str = "job_scam_model.joblib",
    t_high: Optional[float] = None,
    t_low: Optional[float] = None,
    skip_relevance_check: bool = False,
) -> Dict[str, Any]:
    """
    Evaluate a job posting using the gate-based ensemble.
    
    Args:
        text: The job posting text to evaluate
        model_path: Path to the joblib model artifact
        t_high: High threshold for SCAM classification (default: max(artifact.threshold, 0.60))
        t_low: Low threshold for SUSPICIOUS classification (default: min(artifact.threshold, 0.45))
        skip_relevance_check: If True, skip the Groq relevance check (default: False)
    
    Returns:
        Dictionary containing:
        - ml_probability: float
        - ml_pred: 0/1 using artifact.threshold
        - rule_hits: list of rule hit objects
        - rule_score: float
        - final_label: "LEGIT", "SUSPICIOUS", "SCAM", or "NOT_JOB_POSTING"
        - final_reason: short explanation
        - decision_path: list of strings explaining the decision
        - is_job_posting: bool (True if text is a job posting, False otherwise)
    """
    decision_path: List[str] = []
    
    # Handle empty or very short text - reject as not a job posting
    if not text or len(text.strip()) < 50:
        decision_path.append(f"Input validation: text too short ({len(text.strip()) if text else 0} chars, minimum 50 required)")
        return {
            "ml_probability": 0.0,
            "ml_pred": 0,
            "rule_hits": [],
            "rule_score": 0.0,
            "final_label": "NOT_JOB_POSTING",
            "final_reason": "Text is too short to be a valid job posting. Job descriptions typically contain detailed requirements, responsibilities, and company information.",
            "decision_path": decision_path,
            "is_job_posting": False,
        }
    
    # Check if text is a relevant job posting using Groq LLM
    if not skip_relevance_check:
        is_relevant, relevance_reason = check_job_posting_relevance(text)
        
        if not is_relevant:
            decision_path.append(f"Relevance check: NOT a job posting - {relevance_reason}")
            return {
                "ml_probability": 0.0,
                "ml_pred": 0,
                "rule_hits": [],
                "rule_score": 0.0,
                "final_label": "NOT_JOB_POSTING",
                "final_reason": relevance_reason,
                "decision_path": decision_path,
                "is_job_posting": False,
            }
        else:
            decision_path.append(f"Relevance check: confirmed job posting - {relevance_reason}")
    
    # Load model
    try:
        artifact, embedder = get_model(model_path)
    except Exception as e:
        decision_path.append(f"Error: Could not load model from {model_path} - {str(e)}")
        # On model error, we can't verify - reject for safety
        return {
            "ml_probability": 0.0,
            "ml_pred": 0,
            "rule_hits": [],
            "rule_score": 0.0,
            "final_label": "NOT_JOB_POSTING",
            "final_reason": f"Unable to analyze: model loading error. Please try again later.",
            "decision_path": decision_path,
            "is_job_posting": False,
        }
    
    # Set thresholds
    if t_high is None:
        t_high = max(artifact.threshold, 0.60)
    if t_low is None:
        t_low = min(artifact.threshold, 0.45)
    
    decision_path.append(f"Thresholds: T_HIGH={t_high:.4f}, T_LOW={t_low:.4f}, artifact.threshold={artifact.threshold:.4f}")
    
    # Compute ML probability
    try:
        embedding = embedder.encode([text], normalize_embeddings=True)
        ml_probability = float(artifact.classifier.predict_proba(embedding)[0, 1])
    except Exception as e:
        ml_probability = 0.0
        decision_path.append(f"ML scoring error: {str(e)}, defaulting to 0.0")
    
    ml_pred = int(ml_probability >= artifact.threshold)
    decision_path.append(f"ML model: probability={ml_probability:.4f}, pred={ml_pred} (threshold={artifact.threshold:.4f})")
    
    # Evaluate rules
    rule_hits_obj, rule_score = evaluate_rules(text)
    rule_hits = [
        {
            "rule_id": hit.rule_id,
            "severity": hit.severity,
            "matched_text_or_pattern": hit.matched_text_or_pattern,
            "explanation": hit.explanation,
        }
        for hit in rule_hits_obj
    ]
    
    if rule_hits:
        decision_path.append(f"Rules: {len(rule_hits)} hits, total_score={rule_score:.2f}")
        for hit in rule_hits_obj:
            decision_path.append(f"  - {hit.rule_id} ({hit.severity}): {hit.explanation}")
    else:
        decision_path.append("Rules: no hits")
    
    # Check for critical rules
    has_critical = any(hit.severity == "CRITICAL" for hit in rule_hits_obj)
    
    # Gate logic
    final_label: str
    final_reason: str
    
    # Gate 1: Critical rule override
    if has_critical:
        final_label = "SCAM"
        critical_rules = [h.rule_id for h in rule_hits_obj if h.severity == "CRITICAL"]
        final_reason = f"Critical red flag detected: {', '.join(critical_rules)}"
        decision_path.append(f"GATE 1 TRIGGERED: Critical rule(s) -> SCAM")
    
    # Gate 2: High ML probability
    elif ml_probability >= t_high:
        final_label = "SCAM"
        final_reason = f"ML model confidence {ml_probability:.1%} exceeds high threshold"
        decision_path.append(f"GATE 2 TRIGGERED: ML probability ({ml_probability:.4f}) >= T_HIGH ({t_high:.4f}) -> SCAM")
    
    # Gate 3: Medium ML + significant rules
    elif t_low <= ml_probability < t_high and rule_score >= 1.0:
        final_label = "SUSPICIOUS"
        final_reason = f"Moderate ML score ({ml_probability:.1%}) combined with rule flags (score={rule_score:.2f})"
        decision_path.append(f"GATE 3 TRIGGERED: T_LOW <= ML < T_HIGH AND rule_score >= 1.0 -> SUSPICIOUS")
    
    # Gate 4: Default to LEGIT
    else:
        final_label = "LEGIT"
        if ml_probability < t_low and rule_score < 1.0:
            final_reason = "Low risk indicators from both ML and rules"
        elif ml_probability < t_low:
            final_reason = "ML model indicates low scam probability"
        else:
            final_reason = "Insufficient evidence to flag as suspicious"
        decision_path.append(f"GATE 4 (DEFAULT): No gates triggered -> LEGIT")
    
    return ScoringResult(
        ml_probability=ml_probability,
        ml_pred=ml_pred,
        rule_hits=rule_hits,
        rule_score=rule_score,
        final_label=final_label,
        final_reason=final_reason,
        decision_path=decision_path,
    ).to_dict()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_rules_summary() -> List[Dict[str, Any]]:
    """Get a summary of all configured rules."""
    return [
        {
            "rule_id": rule.rule_id,
            "severity": rule.severity.name,
            "severity_weight": rule.severity.value,
            "explanation": rule.explanation,
            "pattern_count": len(rule.patterns),
        }
        for rule in RULES
    ]


def add_rule(
    rule_id: str,
    severity: str,
    patterns: List[str],
    explanation: str,
) -> None:
    """
    Add a new rule dynamically.
    
    Args:
        rule_id: Unique identifier for the rule
        severity: One of "LOW", "MEDIUM", "HIGH", "CRITICAL"
        patterns: List of regex patterns
        explanation: Human-readable explanation
    """
    severity_enum = Severity[severity.upper()]
    new_rule = Rule.create(rule_id, severity_enum, patterns, explanation)
    RULES.append(new_rule)
