#!/usr/bin/env python3
"""One-off data migration: align selected dictionary glosses with the official
Japanese/English columns of the bundled corpus.

Every target was re-verified against ``song_translations.japanese`` (primary)
and ``song_translations.english`` (fallback); the evidence is recorded in the
``EVIDENCE`` table below and in ``docs/alician-grammar.md``.

Three places must stay in sync:

    dictionary.explanation            (per-sense gloss)
    dictionary_headwords.display_explanation / display_class  (UI headword)
    <pos>.translation                 (per-class export tables)

The gloss text doubles as the translated surface, so each sense gloss is kept
short and free of parentheses/notes.

Usage
-----
    py -3.14 scripts/migrate_gloss_fixes.py --dry-run
    py -3.14 scripts/migrate_gloss_fixes.py            # apply + write rollback
    py -3.14 scripts/migrate_gloss_fixes.py --rollback backups/xxx_rollback.json
"""
from __future__ import annotations

import argparse
import io
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "app/src/main/assets/translated.db"
BACKUP_DIR = ROOT / "backups"

CLASS_TABLES = ("adj.", "adv.", "art.", "conj.", "interj.", "n.", "num.",
                "prep.", "pron.", "v.", "vi.", "vt.")

# word -> (final senses [(gloss, class)], evidence note)
FIXES: dict[str, tuple[list[tuple[str, str]], str]] = {
    "Qllsiim": (
        [("我们", "pron.")],
        "唯一对齐例 offid=232: Endjulf Qllsiim Vell Luan a Og Amiy… ↔ "
        "「そうして 我々は 共に愛し合い…」；EN=we；中文本地化『我们用这种方式…』。"
        "旧释义『人们』与其自身 JP/EN 列矛盾。",
    ),
    "Qllsiimtiel": (
        [("我们自己", "pron.")],
        "唯一对齐例 offid=230: Lishe Endyd Amiy Qllsiimtiel ↔ "
        "「まず我々自身を愛してあげましょう」；EN=ourselves。"
        "旧释义『它自己(?)』人称错误（应为第一人称复数）。",
    ),
    "Xianya": (
        [("他们", "pron."), ("那些", "pron.")],
        "4 例官方日文：offid=228「それらは ぼくを何度も突き刺した」、"
        "offid=520 EN \"I think they are adorable now\"、offid=716 EN "
        "\"Flocking together, they look for the next sacrifice\" 均为第三人称复数；"
        "offid=246 中文本地化作指示代词『那是…』。词典 JP 列記 それら/あいつら、"
        "EN=Those people。旧释义『那个 / 它(作主语)』只覆盖单数指示，"
        "词类亦应为 pron.。",
    ),
    "Salah": (
        [("阴影", "n.")],
        "4/4 例官方日文皆为「影」：offid=154 瞳の影、offid=430 朝影に映る、"
        "offid=665 影に取り憑かれたもの、offid=856 あどけない人影；EN=shadow。"
        "旧义项2『水面(?)』有误——『水面』实为 Akarche(n. 水面)，见 offid=154 "
        "「瞳の影 瞳の奥の水面」中 Akarche 承担『水面』。",
    ),
    "Rinasia": (
        [("诞生", "v."), ("出生（亦可写作 Rin / Rin Asia）", "v.")],
        "6 例官方日文：offid=241/497/498/854/1008 为「生まれ／生まれ変わる／"
        "産まれてきた／生まれる／生まれてこなければ」；EN=born/reborn。"
        "义项1『诞生』已准确；义项2 原为『产生。也可以写作Rin或Rin Asia(?)』，"
        "『产生』不当且句末说明会被当成译文表面。",
    ),
    "Loosya": (
        [("连", "adj.")],
        "3 例官方日文取 すら/も（焦点助词）：offid=236「人ですら ない」、"
        "offid=865「意味すら嘲る」、offid=631「独裁者も」。"
        "旧释义『任何(?)』与 すら（连…都）不符。",
    ),
    "ob": (
        [("持续", "v.")],
        "官方日文均为 ていた（过去持续）：offid=185「止まっ ていた時間」、"
        "offid=319「みんな待っ てた」，EN=had been waiting；词典 JP 列記 ていた。"
        "旧释义『助动词 / 用于过去完成时(?)』前者是词类标签、后者与 ていた 不符。",
    ),
    "Coll": (
        [("身躯", "n.")],
        "4/4 例官方日文皆为「体」：offid=305 汚い体、offid=321 体をすり抜け、"
        "offid=543 大きな体、offid=683 ぼくらの体；EN=body。释义内容正确，"
        "仅去除存疑标记。",
    ),
    "tie": (
        [("在", "prep.")],
        "offid=62/63: end Karna Awter Noll tie Haymate ↔ 「いつかまた 故郷で会えるように」；"
        "词典 JP 列記 中、EN=Inside。释义『在』可用，仅去除存疑标记"
        "（不可写作『在…中』——该字段同时充当译文表面）。",
    ),
    "Mail": (
        [("披上", "v."), ("衣服", "n.")],
        "offid=588: Ah Mail Shiita ↔ 「天命を纏い」；offid=747: Swiina Mail ↔ "
        "「服を着替えて」；词典 EN=clad、JP=纏い。两个义项『披上/衣服』均与"
        "官方译文相符，仅去除存疑标记。",
    ),
}


def headword_display(senses: list[tuple[str, str]]) -> str:
    if len(senses) == 1:
        return senses[0][0]
    return "".join(f"({i}){g}" for i, (g, _) in enumerate(senses, 1))


def snapshot(con: sqlite3.Connection, word: str) -> dict:
    state: dict = {"word": word}
    state["dictionary"] = [
        dict(r) for r in con.execute(
            "SELECT * FROM dictionary WHERE lower(words)=lower(?) ORDER BY sense_order", (word,)
        )
    ]
    state["headwords"] = [
        dict(r) for r in con.execute(
            "SELECT * FROM dictionary_headwords WHERE lower(words)=lower(?)", (word,)
        )
    ]
    state["class_tables"] = {}
    for table in CLASS_TABLES:
        rows = [dict(r) for r in con.execute(
            f"SELECT * FROM `{table}` WHERE lower(words)=lower(?)", (word,)
        )]
        if rows:
            state["class_tables"][table] = rows
    return state


def apply_fixes(con: sqlite3.Connection, fixes: dict, dry: bool) -> list[dict]:
    log: list[dict] = []
    for word, (senses, _evidence) in fixes.items():
        before = snapshot(con, word)
        if not before["dictionary"]:
            print(f"  ! {word}: 词典无此词，跳过")
            continue
        log.append(before)
        if dry:
            print(f"  [dry] {word}: {[r['explanation'] for r in before['dictionary']]}"
                  f" -> {[s[0] for s in senses]}")
            continue

        # --- derived values -------------------------------------------------
        classes = []
        for gloss, cls in senses:
            if cls not in classes:
                classes.append(cls)
        primary_class = classes[0]
        display = headword_display(senses)
        hw_id = before["dictionary"][0]["headword_id"]

        # --- dictionary -----------------------------------------------------
        existing = sorted(before["dictionary"], key=lambda r: r["sense_order"])
        for index, (gloss, cls) in enumerate(senses):
            if index < len(existing):
                row = existing[index]
                con.execute(
                    "UPDATE dictionary SET explanation=?, class=? WHERE id=?",
                    (gloss, cls, row["id"]),
                )
            else:
                con.execute(
                    "INSERT INTO dictionary (headword_id, words, explanation, class,"
                    " sense_order, count, variety, time, english_gloss, japanese_gloss)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (hw_id, word, gloss, cls, index + 1,
                     existing[0]["count"], existing[0]["variety"], existing[0]["time"],
                     existing[0]["english_gloss"], existing[0]["japanese_gloss"]),
                )
        for row in existing[len(senses):]:
            con.execute("DELETE FROM dictionary WHERE id=?", (row["id"],))

        # --- dictionary_headwords -------------------------------------------
        con.execute(
            "UPDATE dictionary_headwords SET display_explanation=?, display_class=?"
            " WHERE id=?",
            (display, primary_class, hw_id),
        )

        # --- per-class export tables ----------------------------------------
        for table in CLASS_TABLES:
            con.execute(f"DELETE FROM `{table}` WHERE lower(words)=lower(?)", (word,))
        grouped: dict[str, list[str]] = {}
        for gloss, cls in senses:
            grouped.setdefault(cls, []).append(gloss)
        for cls, glosses in grouped.items():
            con.execute(
                f"INSERT INTO `{cls}` (words, translation, count, variety) VALUES (?,?,?,?)",
                (word, "，".join(glosses), before["dictionary"][0]["count"],
                 before["dictionary"][0]["variety"]),
            )
        print(f"  + {word}: {[r['explanation'] for r in before['dictionary']]}"
              f" -> {[s[0] for s in senses]}  (class {primary_class}, display {display!r})")
    return log


def rollback(con: sqlite3.Connection, path: Path) -> None:
    log = json.loads(path.read_text(encoding="utf-8"))
    for state in log:
        word = state["word"]
        for table in CLASS_TABLES:
            con.execute(f"DELETE FROM `{table}` WHERE lower(words)=lower(?)", (word,))
        con.execute("DELETE FROM dictionary WHERE lower(words)=lower(?)", (word,))
        con.execute("DELETE FROM dictionary_headwords WHERE lower(words)=lower(?)", (word,))
        for row in state["dictionary"]:
            cols = ",".join(row)
            placeholders = ",".join("?" * len(row))
            con.execute(f"INSERT INTO dictionary ({cols}) VALUES ({placeholders})",
                        tuple(row.values()))
        for row in state["headwords"]:
            cols = ",".join(row)
            placeholders = ",".join("?" * len(row))
            con.execute(f"INSERT INTO dictionary_headwords ({cols}) VALUES ({placeholders})",
                        tuple(row.values()))
        for table, rows in state["class_tables"].items():
            for row in rows:
                cols = ",".join(row)
                placeholders = ",".join("?" * len(row))
                con.execute(f"INSERT INTO `{table}` ({cols}) VALUES ({placeholders})",
                            tuple(row.values()))
        print(f"  < 已还原 {word}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", metavar="ROLLBACK_JSON")
    ap.add_argument("--only", nargs="*", metavar="WORD")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        if args.rollback:
            with con:
                rollback(con, Path(args.rollback))
            print("回滚完成。")
            return 0
        wanted = {x.lower() for x in (args.only or [])}
        fixes = {w: v for w, v in FIXES.items() if not wanted or w.lower() in wanted}
        print(f"目标词条: {len(fixes)}")
        with con:
            log = apply_fixes(con, fixes, args.dry_run)
        if not args.dry_run:
            BACKUP_DIR.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            out = BACKUP_DIR / f"gloss_fix_{stamp}_rollback.json"
            out.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\n回滚文件: {out}")
            print(f"回滚命令: py -3.14 scripts/migrate_gloss_fixes.py --rollback {out}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
