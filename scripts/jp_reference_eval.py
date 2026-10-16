#!/usr/bin/env python3
"""Official-lyrics benchmark for the Alician -> Chinese translator.

Why this exists
---------------
``sentence_alignments.chinese_translation`` is an official *Chinese
localization* of the Japanese original.  It freely swaps cause/effect clauses
and drops connectives, so a difflib score against it rewards the wrong
behaviour.  The authoritative references live in ``song_translations``:

    sentence  -- the Alician line
    japanese  -- the official Japanese original   (PRIMARY)
    english   -- the official English translation (FALLBACK)

Scoring model
-------------
Each Alician function word below is attested to correspond to a Japanese
marker, and that marker has an idiomatic Chinese reflex.  A *case* is counted
when

    the Alician word occurs in the line  AND  the Japanese marker occurs in
    the official Japanese block,

and it is a *hit* when the translator's Chinese surface contains an acceptable
reflex.  Lines without Japanese fall back to the official English marker.

Per word we report: cases, hits, accuracy, "chance" (how often that reflex
appears in an average output, i.e. how weak the marker is) and lift.

Usage
-----
    py -3.14 scripts/jp_reference_eval.py
    py -3.14 scripts/jp_reference_eval.py --worst 20
    py -3.14 scripts/jp_reference_eval.py --only elize poetklar gout
    py -3.14 scripts/jp_reference_eval.py --json scripts/_scratch_eval.json
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "app/src/main/assets/translated.db"
sys.path.insert(0, str(ROOT / "app/src/main/python"))

from webui_backend.translation_service import TranslationService  # noqa: E402

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")

# Alician word -> (Japanese markers any-of, English markers any-of,
#                  acceptable Chinese reflexes any-of)
SPECS: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "elize":    (("から", "だから"), ("because", "so ", "that's why"), ("因为", "所以", "因此", "正因")),
    "poetklar": (("ながら",), ("while",), ("一边", "同时", "着")),
    "folme":    (("から",), ("from",), ("从",)),
    "gout":     (("でも", "けど", "けれど", "しかし"), ("but",), ("但是", "但", "不过", "却")),
    "foul":     (("きっと",), ("definitely", "surely"), ("一定", "绝")),
    "mols":     (("だけ",), ("only", "just"), ("只",)),
    "baly":     (("いつも", "いつだって"), ("always",), ("总是", "无论何时")),
    "quim":     (("なら",), ("if ",), ("假如", "如果", "若")),
    "zel":      (("何",), ("anything", "nothing", "what"), ("任何", "什么", "没")),
    "ifa":      (("で", "と"), ("with", "together"), ("伴随", "用", "和", "一起")),
    "il":       (("へ",), ("toward",), ("到",)),
    "poutie":   (("たら", "ば", "なら", "と"), ("when", "if "), ("当", "如果", "随着", "正如")),
    "yiela":    (("なさい",), ("please",), ("来", "吧")),
    "phier":    (("ください", "お願い"), ("please",), ("请",)),
    "lishe":    (("ましょう",), ("let's", "let "), ("让",)),
    "hiele":    (("ほら", "ねえ"), ("look", "hey", "come on"), ("看", "哪", "来")),
    "lend":     (("か",), ("?",), ("是否",)),
    "rie":      (("やがて",), ("eventually",), ("不久", "早晚", "终")),
    "osa":      (("も",), ("too", "also"), ("也",)),
    "ol":       (("た",), (), ("已", "过", "了")),
    "ob":       (("ていた",), ("had been",), ("已经", "曾")),
    "vell":     (("だろう",), ("will",), ("将",)),
    "laiz":     (("だろう",), (), ("将",)),
    "nai":      (("ない", "ません", "なかった"), ("not", "don't", "can't"), ("不", "没", "无", "别", "未")),
    "kulu":     (("ない", "できる"), ("can", "can't"), ("能", "不")),
    "qleea":    (("てしまう", "しまう", "ちゃう"), ("completely",), ("将", "快", "已", "掉", "完")),
    "ou":       (("の",), ("of",), ("的",)),
}

# Japanese markers that are too frequent to be diagnostic on their own.
WEAK_MARKERS = {"で", "と", "も", "か", "た", "の", "何"}

# Function words whose surface is produced by grammar rules rather than by a
# dictionary gloss; excluded from the lexical-recall axis.
GRAMMAR_WORDS = set(SPECS) | {
    "a", "es", "en", "ta", "sii", "sip", "wei", "weiy", "dou", "endil",
    "iqyur", "ra", "iy", "laiz", "vell", "qleea", "nai", "ol", "ob", "ord",
    "yien", "laiz", "imm", "arch", "arche", "lim", "alfloul", "pllia", "uleim",
    "forle", "winde", "lid", "elied", "tozlom", "ijlim", "mols", "osa", "baly",
    "og", "amiy", "kulu", "phim", "foul", "crain", "lend", "erikes", "fevla",
    "phier", "yiela", "yiep", "lqll", "dis", "poet", "poetolt", "hiele",
    "lishe", "leste", "noa", "ieq", "iequim", "quim", "poutie", "imeila",
    "end", "ah",
    # morphology markers whose dictionary "explanation" is a rule, not a gloss
    "qls", "lait", "yur",
    # words absorbed into attested constructions / phrase entries
    "falke", "brait", "endyd", "bai", "aihel", "ail", "poul", "fiq",
}

# Gloss strings may list alternatives ("散落，飘"); accept any segment.
GLOSS_SPLIT_RE = re.compile(r"[，,、/；;・]+")
# The adjective/adverbial particles vary with the syntactic slot the word
# takes (无情的 -> 无情地), which is not a meaning difference.
DE_PARTICLES_RE = re.compile(r"[的地得]")


def norm_gloss(text: str) -> str:
    return DE_PARTICLES_RE.sub("", text)


def load_docs(conn: sqlite3.Connection) -> list[tuple[str, str, str]]:
    rows = conn.execute(
        "SELECT sentence, japanese, english FROM song_translations"
        " WHERE sentence IS NOT NULL AND TRIM(sentence) <> ''"
    ).fetchall()
    seen: set[tuple[str, str, str]] = set()
    docs: list[tuple[str, str, str]] = []
    for r in rows:
        key = (str(r["sentence"]), str(r["japanese"] or ""), str(r["english"] or ""))
        if key in seen:
            continue
        seen.add(key)
        docs.append(key)
    return docs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worst", type=int, default=0)
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--only", nargs="*", metavar="WORD")
    ap.add_argument("--fallback", action="store_true",
                    help="enable spelling-similarity fallback matching")
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    docs = load_docs(conn)
    conn.close()

    only = {w.lower() for w in (args.only or [])}
    specs = {w: s for w, s in SPECS.items() if not only or w in only}
    spec_words = set(specs)

    service = TranslationService(str(DB), enable_fallback_matching=args.fallback)

    outputs: list[tuple[str, str, str, str, set[str]]] = []
    src = {"jp": 0, "en": 0, "none": 0}
    for sentence, jp, en in docs:
        words = {w.lower() for w in WORD_RE.findall(sentence)}
        if not words & spec_words:
            continue
        jp_flat = jp.replace("\n", " ").strip()
        en_flat = en.replace("\n", " ").strip()
        if jp_flat:
            src["jp"] += 1
        elif en_flat:
            src["en"] += 1
        else:
            src["none"] += 1
        out = service.translate(sentence, "alician_to_zh")["result_text"]
        outputs.append((sentence, jp_flat, en_flat, out, words))
    service.close()

    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"cases": 0, "hits": 0})
    failures: list[tuple[str, str, str, str, str]] = []
    for sentence, jp, en, out, words in outputs:
        use_jp = bool(jp)
        if not use_jp and not en:
            continue
        text = jp if use_jp else en
        for word, (jp_markers, en_markers, reflexes) in specs.items():
            if word not in words:
                continue
            markers = jp_markers if use_jp else en_markers
            if not markers or not any(m in text for m in markers):
                continue
            stats[word]["cases"] += 1
            if any(r in out for r in reflexes):
                stats[word]["hits"] += 1
            else:
                failures.append((word, sentence, text[:120], out[:120], "/".join(reflexes)))

    # "chance": how often each reflex set shows up in an average output.
    chance: dict[tuple[str, ...], float] = {}
    denom = len(outputs) or 1
    for reflex_set in {specs[w][2] for w in specs}:
        chance[reflex_set] = sum(
            1 for _, _, _, out, _ in outputs if any(r in out for r in reflex_set)
        ) / denom

    total_cases = sum(v["cases"] for v in stats.values())
    total_hits = sum(v["hits"] for v in stats.values())

    # --- second, independent axis: lexical recall -------------------------
    # The dictionary glosses are manually verified, so every recognised
    # content word should show one of its glosses in the Chinese surface.
    # This detects dropped or metadata-replaced lexical items, independently
    # of the function-word specs above.
    lex_total = 0
    lex_hits = 0
    lex_misses: list[tuple[str, str, str]] = []
    service_words = {k: list(v) for k, v in service._word_by_lower.items()}
    clean_gloss = service._clean_surface_gloss
    for sentence, _, _, out, words in outputs:
        for word in words:
            if word in GRAMMAR_WORDS:
                continue
            glosses: set[str] = set()
            for entry in service_words.get(word) or []:
                surface = clean_gloss(str(entry.get("explanation") or ""))
                for segment in GLOSS_SPLIT_RE.split(surface):
                    segment = norm_gloss(segment.strip())
                    if segment:
                        glosses.add(segment)
            if not glosses:
                continue
            lex_total += 1
            if any(g in norm_gloss(out) for g in glosses):
                lex_hits += 1
            else:
                lex_misses.append((word, sentence, out[:120]))
    if args.worst:
        lex_misses.sort()
        print(f"\n=== 词汇未命中（最多 {args.worst} 条，共 {len(lex_misses)}）===")
        for word, sentence, out in lex_misses[:args.worst]:
            print(f"[{word}] {sentence}")
            print(f"      OUT: {out}")

    print("=== 官方歌词基准评估（日文优先 / 英文回退）===")
    print(f"评分行数: {len(outputs)}  (日文 {src['jp']} / 英文回退 {src['en']} / 无参考 {src['none']})")
    if total_cases:
        print(f"[轴1] 功能词标记命中率: {total_hits}/{total_cases} = {total_hits / total_cases:.3f}")
    if lex_total:
        print(f"[轴2] 词汇释义召回率:   {lex_hits}/{lex_total} = {lex_hits / lex_total:.3f}"
              f"   (未命中样例 {len(lex_misses)})")
    print()
    print(f"{'词':<10}{'用例':>6}{'命中':>6}{'准确':>8}{'偶然':>8}{'提升':>8}  强度")
    rows_out = []
    for word, v in sorted(
        stats.items(),
        key=lambda kv: (kv[1]["hits"] / kv[1]["cases"]) if kv[1]["cases"] else 1.0,
    ):
        cases, hits = v["cases"], v["hits"]
        if not cases:
            continue
        acc = hits / cases
        ch = chance[specs[word][2]]
        lift = acc / ch if ch else 0.0
        weak = "*弱" if any(m in WEAK_MARKERS for m in specs[word][0]) else ""
        rows_out.append((word, cases, hits, acc, ch, lift, weak))
        print(f"{word:<10}{cases:>6}{hits:>6}{acc:>8.3f}{ch:>8.3f}{lift:>8.2f}  {weak}")

    if args.worst:
        print(f"\n=== 失败样例（最多 {args.worst} 条，共 {len(failures)}）===")
        for word, sentence, ref, out, want in failures[:args.worst]:
            print(f"[{word}] 期望含 {want}")
            print(f"    AL : {sentence}")
            print(f"    REF: {ref}")
            print(f"    OUT: {out}")

    print("\n注: 偶然 = 该反射词在本文档集随机输出中的出现率；提升 = 准确/偶然。")
    print("    *弱 = 所用日语标记为高频单字（で/と/も/か/た/の/何），判别力低。")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "rows_scored": len(outputs),
            "reference_split": src,
            "overall": {
                "cases": total_cases,
                "hits": total_hits,
                "accuracy": (total_hits / total_cases) if total_cases else 0.0,
            },
            "per_word": {
                w: {"cases": c, "hits": h, "accuracy": a, "chance": ch,
                    "lift": l, "weak_marker": bool(k)}
                for w, c, h, a, ch, l, k in rows_out
            },
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写出 JSON: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
