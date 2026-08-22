"""Import English/Japanese translations from alicianlabs into translated.db.

Alignment strategy: the app lyric stores one Alician sentence per block (with
word-by-word glosses below it).  The alicianlabs source stores the same lyric
as blank-line-separated paragraphs which may merge several app sentences.
Each app sentence is therefore matched, in order, to the alicianlabs
paragraph with the best normalized word overlap.

Table: song_translations(song_title, sentence, english, japanese, korean)
- sentence is the app lyric sentence ('' for songs absent from the app DB,
  which are stored as a single whole-text row and never referenced by the UI).
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DB = Path(r"app\src\main\assets\translated.db")
REPO = Path(r"C:\Users\meart\Desktop\alicianlabs-master\script\songs_data")

# repo base name -> app song title (songs present in the app database)
REPO_TO_APP: Dict[str, str] = {
    "A_Little_Servant": "A Little Servant",
    "a_Witch_of_Ice_Cage": "氷の檻のトリエスタ",
    "Acquazzone": "地平線のアクアツォーネ",
    "Akasha_no_hibun": "アーカーシャの碑文",
    "Alice_Music": "Alice Music",
    "ALQ": "ALQ",
    "Apocalypse": "Apocalypse",
    "Bad_end_syndrome": "バッドエンド·シンドローム(Bad End Syndrome)",
    "Children_in_the_Ashes": "Cԋιʅԃɾҽɳ ιɳ ƚԋҽ Aʂԋҽʂ(Children in the Ashes)",
    "Chocolate_Missile": "Chocolate Missile",
    "Doppelgängers": "Doppelgängers",
    "eat_you_up": "EAT YOU UP",
    "Elysions_Old_Mans": "エリシアンズ・オールドマンズ(Elysion's Old Mans)",
    "End_of_Mythology": "End of Mythology",
    "Endorphin": "EИDФЯPHIИ(Endorphin)",
    "Fehlt": "FEHLT",
    "Flyburg_and_Endroll": "フライブルクとエンドロウル(Flyburg and the Endroll)",
    "Forbidden_Wonderlands": "Forbidden Wonderland short ver",
    "Friend": "Friend",
    "Frozen_Tree": "Frozen Tree",
    "Fushigi_Chan": "Fushigi Chan",
    "Give_Me_a_Nightmare": "Give Me a Nightmare",
    "HOLIC": "HOLIC",
    "Hypnotized": "HӋPПO̵͇̫̲ƬIZΣD(Hypnotized)",
    "i_am_always_wrong": "i am always wrong",
    "Kill_My_Fortune": "ᖽᐸᓰᒪᒪ ᘻᖻ ᖴᓍᖇᖶᑘᘉᘿ(Kill My Fortune)",
    "killed_by_angel": "KILLED BY ANGEL",
    "kuusou_modernism": "空想モダニズム -Alice Schach remix-",
    "life_in_a_plastic_bag": "Life in a Plastic Bag",
    "Lost_My_Savepoint": "Lost My Savepoint",
    "Maharajah": "Maharajah",
    "Maze_No.9": "九番目の迷路(Maze No.9)",
    "NEW_GAME": "▷ NEW GAME",
    "no_parents": "NO PARENTS",
    "O": "𝕆(O)",
    "Popcorns_Falling_from_Heaven": "Popcorns Falling from Heaven",
    "Psukhe": "Psukhe",
    "QUEEN_FLY": "QUEEN FLY",
    "snooze_and_snooze": "Sno (_ _) oze & Sn (o_o) ze",
    "Teardrop_del_Rey": "Teardrop del Ray",
    "The_Fatal_Fantasy": "The Fatal Fantasia",
    "the_white_land": "The White Land",
    "Thirty_Million_Persona": "Thirty Million Persona",
    "Toys": "Toys",
    "under_wonder_nights": "Under Wonder Nights",
    "Urxbxrxs": "Urxbxrxs",
    "Wanderers": "ᗯᗅᑎᗫᙍᖇᙍᖇᏕ(WANDERERS)",
    "Wanderschaffen_s_Law": "ワンダーシャッフェンの法則",
    "wonder_world_sketch": "Wonder World Sketch",
    "Zukan": "図鑑(Zukan)",
}

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
_WS_RE = re.compile(r"[\s\u00a0\u2000-\u200a\u202f\u3000]+")


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def _words(text: str) -> List[str]:
    tokens = _WORD_RE.findall(_normalize(text))
    result: List[str] = []
    for token in tokens:
        result.append(token.casefold())
        # CamelCase handling (e.g. HamilSlay -> hamil, slay) so words written
        # without a space still match the repo transcription.
        for part in re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z]*", token):
            lowered = part.casefold()
            if lowered != token.casefold():
                result.append(lowered)
    return result


# Sentences whose repo transcription diverges too much for word overlap.
MANUAL_OVERRIDES = {
    ("NO PARENTS", "Heik Deris ou Ription Bis iy Yekis end Zill ol Sion"): (
        "How does absurdity taste? This is the nightmare we’ve been in",
        "不条理の味はどう？　これが僕らの見た悪夢だよ",
    ),
}


def split_paragraphs(text: str) -> List[str]:
    paragraphs: List[str] = []
    current: List[str] = []
    for raw in (text or "").splitlines():
        line = _normalize(raw)
        if not line:
            if current:
                paragraphs.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append("\n".join(current))
    return paragraphs


def is_annotation(line: str) -> bool:
    return bool(re.search(r"[：:]", line))


def app_sentences(lyric: str) -> List[str]:
    sentences: List[str] = []
    for line in (lyric or "").splitlines():
        stripped = _normalize(line)
        if not stripped or is_annotation(stripped):
            continue
        sentences.append(stripped)
    return sentences


def best_paragraph(
    sentence: str, paragraphs: List[str], start: int,
) -> Tuple[Optional[int], float]:
    """Best paragraph by sentence-word coverage, searching from start onward."""
    sw = set(_words(sentence))
    if not sw:
        return None, 0.0
    best_idx: Optional[int] = None
    best_score = 0.0
    for index in range(start, len(paragraphs)):
        pw = set(_words(paragraphs[index]))
        if not pw:
            continue
        score = len(sw & pw) / len(sw)
        if score > best_score:
            best_score = score
            best_idx = index
        if score >= 1.0:
            break
    return best_idx, best_score


def parse_song_file(path: Path) -> Optional[Tuple[str, str, str, str]]:
    content = path.read_text(encoding="utf-8")
    title = re.search(r'title = "([^"]*)"', content)
    original = re.search(r"original_lyrics = `([^`]*)`", content)
    english = re.search(r"english_lyrics = `([^`]*)`", content)
    japanese = re.search(r"japanese_lyrics\s*=\s*`([^`]*)`", content)
    if not title:
        return None
    return (
        title.group(1),
        original.group(1) if original else "",
        english.group(1) if english else "",
        japanese.group(1) if japanese else "",
    )


def main() -> None:
    songs: Dict[str, Tuple[str, str, str]] = {}
    for path in sorted(REPO.glob("*.js")):
        parsed = parse_song_file(path)
        if parsed and parsed[0]:
            # Key by the parsed title so filenames with encoding-mangled
            # characters (e.g. Doppelg盲ngers) still resolve correctly.
            songs[parsed[0]] = (path.stem, parsed[0], parsed[1], parsed[2], parsed[3])

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS song_translations")
    cur.execute(
        """
        CREATE TABLE song_translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_title TEXT NOT NULL,
            sentence TEXT NOT NULL DEFAULT '',
            english TEXT NOT NULL DEFAULT '',
            japanese TEXT NOT NULL DEFAULT '',
            korean TEXT NOT NULL DEFAULT '',
            UNIQUE(song_title, sentence)
        )
        """
    )
    cur.execute(
        "CREATE INDEX idx_song_translations_lookup "
        "ON song_translations(song_title, sentence)"
    )

    app_titles = {
        str(row["title"]) for row in cur.execute("SELECT title FROM songs")
    }

    def resolve_app_title(repo_name: str, parsed_title: str) -> Optional[str]:
        if repo_name in REPO_TO_APP:
            return REPO_TO_APP[repo_name]
        target = _normalize(parsed_title).casefold()
        for app_title in app_titles:
            if _normalize(app_title).casefold() == target:
                return app_title
        return None

    total_sentence_rows = 0
    unmatched: List[str] = []
    for parsed_title, (repo_name, _, original, english, japanese) in sorted(songs.items()):
        app_title = resolve_app_title(repo_name, parsed_title)
        orig_paras = split_paragraphs(original)
        eng_paras = split_paragraphs(english)
        jpn_paras = split_paragraphs(japanese)

        if app_title is None:
            cur.execute(
                "INSERT OR REPLACE INTO song_translations "
                "(song_title, sentence, english, japanese, korean) VALUES (?, '', ?, ?, '')",
                (parsed_title, english.strip(), japanese.strip()),
            )
            print(f"[STORE-ONLY] {parsed_title} (not in app, whole-text)")
            continue

        lyric = cur.execute(
            "SELECT lyric FROM songs WHERE title = ?", (app_title,)
        ).fetchone()
        if lyric is None or not lyric["lyric"]:
            print(f"[NO-LYRIC] {app_title}")
            continue
        sentences = app_sentences(lyric["lyric"])
        if not sentences:
            continue

        pointer = 0
        for sentence in sentences:
            override = MANUAL_OVERRIDES.get((app_title, sentence))
            if override is not None:
                cur.execute(
                    "INSERT OR REPLACE INTO song_translations "
                    "(song_title, sentence, english, japanese, korean) "
                    "VALUES (?, ?, ?, ?, '')",
                    (app_title, sentence, override[0], override[1]),
                )
                total_sentence_rows += 1
                continue
            best_idx, score = best_paragraph(sentence, orig_paras, pointer)
            restart_idx, restart_score = best_paragraph(sentence, orig_paras, 0)
            if restart_score > score:
                best_idx, score = restart_idx, restart_score
            if best_idx is None or score < 0.4:
                unmatched.append(f"{app_title} [{score:.2f}] {sentence[:60]}")
                continue
            pointer = max(pointer, best_idx)
            eng = eng_paras[best_idx] if best_idx < len(eng_paras) else ""
            jpn = jpn_paras[best_idx] if best_idx < len(jpn_paras) else ""
            cur.execute(
                "INSERT OR REPLACE INTO song_translations "
                "(song_title, sentence, english, japanese, korean) VALUES (?, ?, ?, ?, '')",
                (app_title, sentence, eng, jpn),
            )
            total_sentence_rows += 1

    for title in sorted(app_titles):
        if title not in set(REPO_TO_APP.values()):
            print(f"[APP-NO-REPO] {title}")

    print("\nUnmatched sentences (skipped):")
    for line in unmatched:
        print("  ", line)

    conn.commit()
    print(f"\nInserted {total_sentence_rows} sentence rows.")
    print("Table total:", cur.execute("SELECT COUNT(*) FROM song_translations").fetchone()[0])
    conn.close()


if __name__ == "__main__":
    main()
