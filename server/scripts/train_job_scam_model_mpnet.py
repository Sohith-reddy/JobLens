#!/usr/bin/env python3
"""
Train Fake vs Legit Job Posting classifier using:
- SentenceTransformer embeddings: all-mpnet-base-v2
- Classifier: Logistic Regression (class_weight='balanced')
- Threshold tuning on validation set (recall-target or max-F1)

Usage:
  python scripts/train_job_scam_model_mpnet.py --csv data/fake_job_postings.csv --out data/models/job_scam_model.joblib

Outputs:
- job_scam_model.joblib (artifact includes embedding model name, classifier, threshold, text columns)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
from joblib import dump

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    roc_auc_score,
    precision_recall_curve,
    classification_report,
    confusion_matrix,
)

from sentence_transformers import SentenceTransformer

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.clients import ModelArtifact

# Default paths
DEFAULT_CSV_PATH = Path(__file__).parent.parent / "data" / "fake_job_postings.csv"
DEFAULT_OUTPUT_PATH = Path(__file__).parent.parent / "data" / "models" / "job_scam_model1.joblib"


DEFAULT_TEXT_COLS = ["title", "company_profile", "description", "requirements", "benefits"]
DEFAULT_LABEL_COL = "fraudulent"


def clean_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = re.sub(r"<[^>]+>", " ", s)  # strip HTML
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_text_row(row: pd.Series, cols: List[str]) -> str:
    parts = []
    for c in cols:
        if c in row and pd.notna(row[c]):
            val = clean_text(row[c])
            if val:
                parts.append(f"[{c}] {val}")
    return " ".join(parts)


def pr_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    return float(average_precision_score(y_true, y_score))


def choose_threshold_max_f1(y_true: np.ndarray, y_score: np.ndarray) -> Tuple[float, Dict[str, float]]:
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_score)
    f1s = []
    for i, t in enumerate(thresholds):
        p = precisions[i]
        r = recalls[i]
        f1 = 0.0 if (p + r) == 0 else float(2 * p * r / (p + r))
        f1s.append(f1)

    best_idx = int(np.argmax(f1s)) if f1s else 0
    best_t = float(thresholds[best_idx]) if len(thresholds) else 0.5
    best = {
        "precision": float(precisions[best_idx]),
        "recall": float(recalls[best_idx]),
        "f1": float(f1s[best_idx]),
    }
    return best_t, best


def choose_threshold_for_recall(y_true: np.ndarray, y_score: np.ndarray, recall_target: float) -> Tuple[float, Dict[str, float]]:
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_score)

    # thresholds[i] aligns with precisions[i], recalls[i]
    candidates = []
    for i, t in enumerate(thresholds):
        r = recalls[i]
        if r >= recall_target:
            candidates.append((float(t), float(precisions[i]), float(recalls[i])))

    if candidates:
        # pick the highest threshold that still meets recall target (better precision)
        t, p, r = max(candidates, key=lambda x: x[0])
        f1 = 0.0 if (p + r) == 0 else float(2 * p * r / (p + r))
        return t, {"precision": p, "recall": r, "f1": f1}

    # if cannot reach recall target, choose threshold yielding max recall
    best_idx = int(np.argmax(recalls[:-1])) if len(recalls) > 1 else 0
    t = float(thresholds[best_idx]) if best_idx < len(thresholds) else 0.0
    p = float(precisions[best_idx]) if best_idx < len(precisions) else 0.0
    r = float(recalls[best_idx]) if best_idx < len(recalls) else 0.0
    f1 = 0.0 if (p + r) == 0 else float(2 * p * r / (p + r))
    return t, {"precision": p, "recall": r, "f1": f1}


def apply_threshold(y_score: np.ndarray, threshold: float) -> np.ndarray:
    return (y_score >= threshold).astype(int)


def print_eval(split: str, y_true: np.ndarray, y_score: np.ndarray, threshold: float) -> None:
    y_pred = apply_threshold(y_score, threshold)

    print(f"\n=== {split} ===")
    print(f"PR-AUC (Average Precision): {pr_auc(y_true, y_score):.4f}")
    print(f"ROC-AUC: {roc_auc_score(y_true, y_score):.4f}")
    print(f"Threshold: {threshold:.4f}")
    print("\nClassification report:")
    print(classification_report(y_true, y_pred, digits=4))
    print("Confusion matrix [[tn fp] [fn tp]]:")
    print(confusion_matrix(y_true, y_pred))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(DEFAULT_CSV_PATH), help="Path to fake_job_postings.csv (EMSCAD format)")
    ap.add_argument("--out", default=str(DEFAULT_OUTPUT_PATH))
    ap.add_argument("--embedding_model", default="all-mpnet-base-v2")
    ap.add_argument("--text_cols", default=",".join(DEFAULT_TEXT_COLS))
    ap.add_argument("--label_col", default=DEFAULT_LABEL_COL)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test_size", type=float, default=0.15)
    ap.add_argument("--val_size", type=float, default=0.15)
    ap.add_argument("--batch_size", type=int, default=32)  # mpnet is heavier; 16-32 is safe
    ap.add_argument("--threshold_mode", choices=["recall", "f1"], default="recall")
    ap.add_argument("--recall_target", type=float, default=0.85)
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        raise FileNotFoundError(f"CSV not found: {args.csv}")

    df = pd.read_csv(args.csv)

    if args.label_col not in df.columns:
        raise ValueError(f"Label col '{args.label_col}' not in CSV. Columns={list(df.columns)}")

    y = df[args.label_col].astype(int).values
    if set(np.unique(y)) - {0, 1}:
        raise ValueError(f"Label column must be 0/1. Found: {sorted(np.unique(y).tolist())}")

    text_cols = [c.strip() for c in args.text_cols.split(",") if c.strip()]
    used_cols = [c for c in text_cols if c in df.columns]
    missing = [c for c in text_cols if c not in df.columns]
    if missing:
        print(f"Warning: missing text cols ignored: {missing}")
    if not used_cols:
        raise ValueError("No valid text columns found. Provide --text_cols with existing columns.")

    texts = df.apply(lambda r: build_text_row(r, used_cols), axis=1).tolist()

    # stratified split: train / val / test
    X_train, X_temp, y_train, y_temp = train_test_split(
        texts, y,
        test_size=(args.test_size + args.val_size),
        stratify=y,
        random_state=args.seed,
    )
    val_ratio_of_temp = args.val_size / (args.test_size + args.val_size)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp,
        test_size=(1 - val_ratio_of_temp),
        stratify=y_temp,
        random_state=args.seed,
    )

    print("Dataset sizes:")
    print(f"  Train: {len(X_train)} (fraud rate {y_train.mean():.4f})")
    print(f"  Val:   {len(X_val)}   (fraud rate {y_val.mean():.4f})")
    print(f"  Test:  {len(X_test)}  (fraud rate {y_test.mean():.4f})")

    # MPS if available
    import torch
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"\nEmbedding device: {device}")

    embedder = SentenceTransformer(args.embedding_model, device=device)

    def embed(batch_texts: List[str]) -> np.ndarray:
        return embedder.encode(
            batch_texts,
            batch_size=args.batch_size,
            show_progress_bar=True,
            normalize_embeddings=True,
        )

    print("\nEncoding embeddings...")
    Xtr = embed(X_train)
    Xva = embed(X_val)
    Xte = embed(X_test)

    # Train classifier
    clf = LogisticRegression(
        max_iter=3000,
        class_weight="balanced",
        solver="lbfgs",
    )
    clf.fit(Xtr, y_train)

    # Validation threshold tuning
    val_score = clf.predict_proba(Xva)[:, 1]
    if args.threshold_mode == "f1":
        threshold, thm = choose_threshold_max_f1(y_val, val_score)
        print(f"\nChosen threshold (max F1 on val): {threshold:.4f} metrics={json.dumps(thm)}")
    else:
        threshold, thm = choose_threshold_for_recall(y_val, val_score, args.recall_target)
        print(f"\nChosen threshold (val recall >= {args.recall_target:.2f} if possible): {threshold:.4f} metrics={json.dumps(thm)}")

    # Evaluate
    train_score = clf.predict_proba(Xtr)[:, 1]
    test_score = clf.predict_proba(Xte)[:, 1]

    print_eval("TRAIN", y_train, train_score, threshold)
    print_eval("VAL", y_val, val_score, threshold)
    print_eval("TEST", y_test, test_score, threshold)

    artifact = ModelArtifact(
        embedding_model=args.embedding_model,
        device=device,
        text_cols=used_cols,
        label_col=args.label_col,
        threshold=float(threshold),
        classifier=clf,
    )
    dump(artifact, args.out)
    print(f"\nSaved model artifact => {args.out}")
    print("\nInference rule:")
    print("  scam_probability = clf.predict_proba(embed(text))[0,1]")
    print("  scam_pred = (scam_probability >= threshold)")


if __name__ == "__main__":
    main()