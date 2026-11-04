"""Published retrieval-evaluation results (data/evaluation/results/latest.json).

They are static, public information about public-domain documents: nothing here is user data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def results_path() -> Path:
    default = Path(__file__).resolve().parents[3] / "data" / "evaluation" / "results" / "latest.json"
    return Path(os.getenv("EVALUATION_RESULTS_PATH", default))


class ResultsUnreadable(Exception):
    """The file exists but is not valid JSON."""


def load_latest() -> dict | None:
    """The published results, or None when none have been published."""
    path = results_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        raise ResultsUnreadable from None
