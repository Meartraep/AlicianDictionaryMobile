# -*- coding: utf-8 -*-
"""Shared helpers for the song_translations realignment work."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WS = re.compile(r"[\s\u00a0\u2000-\u200a\u202f\u3000]+")

def norm(t):
    return WS.sub(" ", t or "").strip()

_PUNCT = "\u3000 .,!?;:\u3001\u3002\uff01\uff1f\uff1b\uff1a\u2018\u2019\u201c\u201d'\"()[]{}<>-~\u2014\u2026\u30fb\u00b7\u00a1\u00bf*\u2019"

def clean_tok(t):
    return t.strip(_PUNCT).casefold()

def canon(text):
    """Token list of normalized text: punctuation stripped, lowercased."""
    out = []
    for t in norm(text).split(" "):
        c = clean_tok(t)
        if c:
            out.append(c)
    return out

sys.path.insert(0, str(ROOT / "scripts"))
import import_alicianlabs as _ial  # noqa: E402
REPO_TO_APP = dict(_ial.REPO_TO_APP)
APP_TO_REPO = {v: k for k, v in REPO_TO_APP.items()}

def song_source_key(app_title):
    return APP_TO_REPO.get(app_title)

def load_extract(path=None):
    p = Path(path) if path else (ROOT / "scripts/realign/extract.json")
    return json.loads(p.read_text(encoding="utf-8"))
