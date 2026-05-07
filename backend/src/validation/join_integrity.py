"""
Join integrity validation suite — Task 2.4.

Validates the premise_equipment_table for correctness properties:
  Property 3: Every row has a non-null end_use AND efficiency > 0.

All outputs saved to output/join_integrity/ as HTML + Markdown.

Run standalone:
    python -m src.validation.join_integrity
"""

import os
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np

from src import config

logger = logging.getLogger(__name__)

OUT_DIR = os.path.join("output", "join_integrity")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(f"Wrote {path}")


def _load_safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exc