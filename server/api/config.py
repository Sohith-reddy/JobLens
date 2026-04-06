"""
Application configuration.
"""

import os
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Model and data paths
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = DATA_DIR / "models"
DEFAULT_MODEL_PATH = os.getenv("MODEL_PATH", str(MODELS_DIR / "job_scam_model.joblib"))
CACHE_DB_PATH = DATA_DIR / "joblens_cache.db"

# Limits
MAX_PDF_SIZE = 10 * 1024 * 1024  # 10 MB
