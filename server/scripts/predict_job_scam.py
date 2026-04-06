#!/usr/bin/env python3
"""
Load trained artifact (job_scam_model.joblib) and score new job descriptions.
Uses ensemble approach: ML model + keyword-based rules.

Usage:
  python scripts/predict_job_scam.py --model data/models/job_scam_model.joblib --text "your job post..."
  python scripts/predict_job_scam.py --model data/models/job_scam_model.joblib --file jd.txt
  python scripts/predict_job_scam.py --model data/models/job_scam_model.joblib --interactive
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple
from joblib import load
from sentence_transformers import SentenceTransformer

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.clients import ModelArtifact  # noqa: F401 - needed for unpickling

# Default model path
DEFAULT_MODEL_PATH = Path(__file__).parent.parent / "data" / "models" / "job_scam_model.joblib"


@dataclass
class ScamKeywordRule:
    """A rule that detects scam indicators via keywords/patterns."""
    name: str
    patterns: List[str]
    weight: float  # How much this rule contributes to scam score (0.0 - 1.0)
    description: str


# Scam detection rules with weights
SCAM_RULES: List[ScamKeywordRule] = [
    ScamKeywordRule(
        name="registration_fee",
        patterns=[
            r"registration\s+fee",
            r"processing\s+fee",
            r"refundable\s+fee",
            r"application\s+fee",
            r"security\s+deposit",
            r"pay\s+(?:to\s+)?(?:apply|register|join)",
            r"fee\s+(?:of|is)\s+(?:rs\.?|₹|inr)?\s*\d+",
        ],
        weight=0.9,
        description="Legitimate jobs never ask for money upfront"
    ),
    ScamKeywordRule(
        name="personal_documents",
        patterns=[
            r"government\s+id\s+proof",
            r"submit\s+(?:your\s+)?(?:aadhar|pan|passport)",
            r"id\s+proof\s+for\s+verification",
            r"send\s+(?:your\s+)?documents",
            r"bank\s+(?:account|details)\s+(?:for|to)",
        ],
        weight=0.7,
        description="Asking for sensitive documents before hiring is suspicious"
    ),
    ScamKeywordRule(
        name="urgency_pressure",
        patterns=[
            r"urgent\s+(?:hiring|requirement|opening)",
            r"limited\s+(?:opening|position|slot|seat)",
            r"apply\s+immediately",
            r"last\s+(?:date|day)\s+(?:to\s+)?apply",
            r"only\s+\d+\s+(?:position|slot|seat|opening)",
            r"vacancy\s+closes",
            r"don'?t\s+miss",
            r"hurry\s+up",
            r"act\s+(?:now|fast)",
        ],
        weight=0.4,
        description="Excessive urgency is a pressure tactic"
    ),
    ScamKeywordRule(
        name="guaranteed_placement",
        patterns=[
            r"guaranteed\s+(?:job|placement|offer|selection)",
            r"100%\s+(?:job|placement)",
            r"sure\s+(?:shot\s+)?(?:job|selection)",
            r"confirmed\s+(?:job|offer)",
            r"pre[- ]?placement\s+offer",
        ],
        weight=0.6,
        description="No legitimate employer can guarantee placement"
    ),
    ScamKeywordRule(
        name="unrealistic_salary",
        patterns=[
            r"earn\s+(?:up\s+to\s+)?(?:rs\.?|₹|inr|\$)?\s*\d{1,2}[,.]?\d{0,3}\s*(?:lakh|lac|k)?\s*(?:per|/)\s*(?:day|week)",
            r"(?:rs\.?|₹|inr|\$)\s*\d{1,2}[,.]?\d{0,3}\s*(?:lakh|lac)\s*(?:per|/)\s*month",
            r"unlimited\s+(?:earning|income)",
            r"high\s+(?:income|earning)\s+potential",
        ],
        weight=0.5,
        description="Unrealistic salary promises are red flags"
    ),
    ScamKeywordRule(
        name="work_from_home_scam",
        patterns=[
            r"work\s+from\s+home\s+(?:job|opportunity)",
            r"(?:typing|data\s+entry|copy\s+paste)\s+job",
            r"(?:simple|easy)\s+(?:online\s+)?(?:work|job|task)",
            r"no\s+(?:experience|qualification|skill)\s+(?:required|needed)",
            r"anyone\s+can\s+(?:do|apply|join)",
        ],
        weight=0.4,
        description="Vague work-from-home jobs with no skills required"
    ),
    ScamKeywordRule(
        name="contact_red_flags",
        patterns=[
            r"whatsapp\s+(?:us|me|now|only)",
            r"contact\s+(?:on\s+)?whatsapp",
            r"send\s+(?:resume|cv)\s+(?:on|to)\s+whatsapp",
            r"telegram\s+(?:us|me|only)",
            r"(?:call|contact)\s+(?:this\s+)?(?:number|no\.?)",
        ],
        weight=0.5,
        description="Legitimate companies use official channels, not WhatsApp"
    ),
    ScamKeywordRule(
        name="vague_company",
        patterns=[
            r"(?:reputed|leading|top|mnc)\s+company",
            r"(?:international|global)\s+(?:company|organization|firm)",
            r"well[- ]?known\s+(?:company|brand)",
            r"confidential\s+(?:client|company|project)",
        ],
        weight=0.3,
        description="Vague company descriptions without naming the company"
    ),
    ScamKeywordRule(
        name="too_good_to_be_true",
        patterns=[
            r"no\s+interview",
            r"direct\s+(?:hiring|selection|joining)",
            r"spot\s+(?:offer|selection|joining)",
            r"immediate\s+(?:selection|joining|offer)",
            r"same\s+day\s+(?:offer|joining)",
            r"walk[- ]?in\s+(?:and\s+)?(?:get\s+)?(?:selected|hired)",
        ],
        weight=0.6,
        description="Instant hiring without proper process is suspicious"
    ),
]


@dataclass
class KeywordAnalysisResult:
    """Result of keyword-based scam analysis."""
    keyword_score: float  # 0.0 to 1.0
    triggered_rules: List[Tuple[str, str, float]] = field(default_factory=list)  # (rule_name, description, weight)
    

def analyze_keywords(text: str) -> KeywordAnalysisResult:
    """Analyze text for scam keywords and patterns."""
    text_lower = text.lower()
    triggered = []
    total_weight = 0.0
    
    for rule in SCAM_RULES:
        for pattern in rule.patterns:
            if re.search(pattern, text_lower):
                triggered.append((rule.name, rule.description, rule.weight))
                total_weight += rule.weight
                break  # Only count each rule once
    
    # Normalize score to 0-1 range (cap at 1.0)
    # Using diminishing returns formula so multiple flags compound but don't exceed 1.0
    if total_weight > 0:
        keyword_score = 1.0 - (1.0 / (1.0 + total_weight))
    else:
        keyword_score = 0.0
    
    return KeywordAnalysisResult(
        keyword_score=keyword_score,
        triggered_rules=triggered
    )


def ensemble_score(ml_proba: float, keyword_result: KeywordAnalysisResult, 
                   ml_weight: float = 0.5, keyword_weight: float = 0.5) -> float:
    """
    Combine ML model probability with keyword-based score.
    
    Uses weighted average, but if keyword score is very high (strong scam signals),
    it can override a low ML score.
    """
    keyword_score = keyword_result.keyword_score
    
    # If we have very strong keyword signals (registration fee, etc.), boost the score
    has_critical_flag = any(weight >= 0.7 for _, _, weight in keyword_result.triggered_rules)
    
    if has_critical_flag:
        # Critical flags detected - use max of weighted avg and boosted keyword score
        weighted_avg = (ml_proba * ml_weight) + (keyword_score * keyword_weight)
        boosted = max(keyword_score, 0.6)  # Ensure at least 0.6 if critical flag present
        return max(weighted_avg, boosted)
    else:
        # Standard weighted average
        return (ml_proba * ml_weight) + (keyword_score * keyword_weight)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(DEFAULT_MODEL_PATH), help="Path to saved model artifact")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text", type=str, help="Job posting text to score")
    g.add_argument("--file", type=str, help="Path to a text file containing job posting text")
    g.add_argument("--interactive", action="store_true", help="Paste mode (Ctrl+D to finish input)")
    ap.add_argument("--device", default=None, help="Force device: cpu or mps. Default auto.")
    ap.add_argument("--ml-weight", type=float, default=0.5, help="Weight for ML model (0-1)")
    ap.add_argument("--keyword-weight", type=float, default=0.5, help="Weight for keyword rules (0-1)")
    ap.add_argument("--verbose", "-v", action="store_true", help="Show detailed analysis")
    args = ap.parse_args()

    artifact = load(args.model)

    # Choose device
    device = args.device
    if device is None:
        try:
            import torch
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        except Exception:
            device = "cpu"

    embedder = SentenceTransformer(artifact.embedding_model, device=device)

    if args.text:
        text = args.text
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        print("Paste job posting text, then press Ctrl+D (mac/linux) to finish:\n")
        text = sys.stdin.read()

    # ML model prediction
    emb = embedder.encode([text], normalize_embeddings=True)
    ml_proba = float(artifact.classifier.predict_proba(emb)[0, 1])
    
    # Keyword-based analysis
    keyword_result = analyze_keywords(text)
    
    # Ensemble score
    final_score = ensemble_score(
        ml_proba, 
        keyword_result,
        ml_weight=args.ml_weight,
        keyword_weight=args.keyword_weight
    )
    
    # Use the artifact threshold for final prediction
    pred = int(final_score >= artifact.threshold)
    label = "SCAM / FRAUDULENT" if pred == 1 else "LEGIT / NOT FRAUD"
    
    # Output
    print("\n" + "=" * 50)
    print("           JobLens Scam Analysis")
    print("=" * 50)
    
    print(f"\n📊 ML Model Score:      {ml_proba:.4f}")
    print(f"🔍 Keyword Score:       {keyword_result.keyword_score:.4f}")
    print(f"⚖️  Combined Score:      {final_score:.4f}")
    print(f"📏 Threshold:           {artifact.threshold:.4f}")
    print(f"\n🎯 Prediction:          {label}")
    
    if keyword_result.triggered_rules:
        print(f"\n⚠️  Red Flags Detected ({len(keyword_result.triggered_rules)}):")
        for rule_name, description, weight in sorted(keyword_result.triggered_rules, key=lambda x: -x[2]):
            severity = "🔴" if weight >= 0.7 else "🟠" if weight >= 0.5 else "🟡"
            print(f"   {severity} {rule_name}: {description}")
    else:
        print("\n✅ No keyword red flags detected")
    
    if args.verbose:
        print(f"\n--- Detailed Weights ---")
        print(f"ML weight: {args.ml_weight}, Keyword weight: {args.keyword_weight}")
        print(f"Triggered rules: {[r[0] for r in keyword_result.triggered_rules]}")
    
    print()


if __name__ == "__main__":
    main()