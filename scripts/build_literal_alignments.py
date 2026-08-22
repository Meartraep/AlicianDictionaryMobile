"""Create lyric_literal_alignments table and fill it with refined 对译.

Reads the same distinct-line ordering used when the translations were crafted
(scripts/aligned_lines_dump.txt), applies the hand-written literal
translations from scripts/literal_part_*.json, and writes one row per
sentence_alignments row that already has a chinese_translation.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB = Path(r"app\src\main\assets\translated.db")
PARTS = [
    Path(r"scripts\literal_part_1.json"),
    Path(r"scripts\literal_part_2.json"),
    Path(r"scripts\literal_part_3.json"),
    Path(r"scripts\literal_part_4.json"),
    Path(r"scripts\literal_part_5.json"),
    Path(r"scripts\literal_part_6.json"),
]


def load_mapping() -> dict[int, str]:
    merged: dict[int, str] = {}
    for path in PARTS:
        with path.open(encoding="utf-8") as handle:
            for key, value in json.load(handle).items():
                merged[int(key)] = str(value).strip()
    return merged


def main() -> None:
    mapping = load_mapping()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # The distinct-line ordering MUST match the dump used to craft translations.
    rows = cur.execute(
        "SELECT id, song_id, song_title, album, song_sentence_order, "
        "alician_sentence, chinese_translation "
        "FROM sentence_alignments "
        "WHERE TRIM(chinese_translation) <> '' "
        "ORDER BY song_title, song_sentence_order"
    ).fetchall()

    distinct: list[sqlite3.Row] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row["alician_sentence"] or "").strip()
        if key in seen:
            continue
        seen.add(key)
        distinct.append(row)

    missing: list[tuple[int, str]] = []
    for index, row in enumerate(distinct, start=1):
        key = str(row["alician_sentence"] or "").strip()
        if not key:
            continue  # blank alignment lines get no literal translation
        literal = mapping.get(index, "")
        if not literal:
            missing.append((index, key))
    if missing:
        raise SystemExit(
            "缺少对译的句子：\n"
            + "\n".join(f"  [{index}] {key}" for index, key in missing)
        )
    if len(mapping) != sum(1 for r in distinct if str(r["alician_sentence"] or "").strip()):
        extra = set(mapping) - {i for i, r in enumerate(distinct, 1)
                                if str(r["alician_sentence"] or "").strip()}
        if extra:
            print("警告：映射中存在未使用的序号（将忽略）：", sorted(extra))

    cur.execute("DROP TABLE IF EXISTS lyric_literal_alignments")
    cur.execute(
        """
        CREATE TABLE lyric_literal_alignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sentence_alignment_id INTEGER NOT NULL UNIQUE,
            song_id INTEGER NOT NULL,
            song_title TEXT NOT NULL,
            album TEXT,
            song_sentence_order INTEGER,
            alician_sentence TEXT NOT NULL DEFAULT '',
            chinese_translation_literal TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(sentence_alignment_id) REFERENCES sentence_alignments(id) ON DELETE CASCADE,
            FOREIGN KEY(song_id) REFERENCES songs(id)
        )
        """
    )
    cur.execute(
        "CREATE INDEX idx_literal_alignments_song "
        "ON lyric_literal_alignments(song_id, song_sentence_order)"
    )

    by_sentence: dict[str, str] = {}
    for index, row in enumerate(distinct, start=1):
        key = str(row["alician_sentence"] or "").strip()
        if key:
            by_sentence[key] = mapping[index]

    inserted = 0
    for row in rows:
        key = str(row["alician_sentence"] or "").strip()
        literal = by_sentence.get(key, "")
        if not literal:
            continue
        cur.execute(
            "INSERT INTO lyric_literal_alignments "
            "(sentence_alignment_id, song_id, song_title, album, "
            " song_sentence_order, alician_sentence, chinese_translation_literal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                row["id"],
                row["song_id"],
                row["song_title"],
                row["album"],
                row["song_sentence_order"],
                key,
                literal,
            ),
        )
        inserted += 1

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM lyric_literal_alignments").fetchone()[0]
    print(f"已写入 {inserted} 行，表内共 {total} 行。")
    conn.close()


if __name__ == "__main__":
    main()
