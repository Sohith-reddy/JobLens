"""Shared model artifact dataclass for job scam detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Any


@dataclass
class ModelArtifact:
    """Model artifact containing trained classifier and metadata."""
    embedding_model: str
    device: str
    text_cols: List[str]
    label_col: str
    threshold: float
    classifier: Any  # sklearn model
