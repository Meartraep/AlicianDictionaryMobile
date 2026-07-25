from __future__ import annotations

import os
import sys
from pathlib import Path


def is_lite_build() -> bool:
    if os.environ.get("ALICIAN_LITE_BUILD") == "1":
        return True
    if getattr(sys, "frozen", False):
        return "lite" in Path(sys.executable).stem.lower()
    return False


def feature_flags() -> dict:
    lite = is_lite_build()
    return {
        "lite": lite,
        "translator": True,
        "fuzzy_search": True,
        "semantic_search": not lite,
    }
