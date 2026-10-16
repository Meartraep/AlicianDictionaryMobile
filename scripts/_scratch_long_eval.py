"""Scratch: evaluate translator on long aligned sentences (Alician->Chinese).

Computes difflib similarity between machine output and reference translation,
prints the worst cases for manual grammar mining.
"""
from __future__ import annotations

import difflib
import io
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "python"))

from webui_backend.translation_service import TranslationService

DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
MIN_WORDS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 60


def norm(s: str) -> str:
    return "".join(ch for ch in (s or "") if not ch.isspace() and ch not in "，。！？…·、""''×")


def main() -> None:
    con = sqlite3.connect(DB)
    rows = con.execute(
        """
        SELECT DISTINCT alician_sentence, chinese_translation
        FROM sentence_alignments
        WHERE alignment_status IN ('aligned_exact','aligned_close')
        """
    ).fetchall()
    con.close()

    seen = set()
    data = []
    for a, c in rows:
        a = (a or "").strip()
        c = (c or "").strip()
        if not a or not c or a.casefold() in seen:
            continue
        seen.add(a.casefold())
        wc = len(a.split())
        if wc >= MIN_WORDS:
            data.append((a, c, wc))
    data.sort(key=lambda x: -x[2])
    print(f"long sentences (>={MIN_WORDS} words): {len(data)}")

    svc = TranslationService(DB, enable_fallback_matching=False)
    scored = []
    unknown_total = 0
    for a, c, wc in data:
        res = svc.translate(a, "alician_to_zh")
        out = res["result_text"]
        unk = res["stats"]["unknown"]
        unknown_total += unk
        sim = difflib.SequenceMatcher(None, norm(out), norm(c)).ratio()
        scored.append((sim, wc, unk, a, c, out))
    svc.close()

    scored.sort(key=lambda x: x[0])
    avg = sum(s[0] for s in scored) / len(scored)
    print(f"avg similarity: {avg:.3f}; total unknown tokens: {unknown_total}")
    print(f"\n===== WORST {LIMIT} =====")
    for sim, wc, unk, a, c, out in scored[:LIMIT]:
        print(f"\nsim={sim:.2f} wc={wc} unk={unk}")
        print(f"A : {a}")
        print(f"REF: {c}")
        print(f"OUT: {out}")


if __name__ == "__main__":
    main()
