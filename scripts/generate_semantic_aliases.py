#!/usr/bin/env python3
"""Generate high-precision Chinese semantic aliases for ``translated.db``.

This is a development/build-time tool.  It deliberately does not ship or load
text2vec in the Android runtime.  A typical invocation is:

    python scripts/generate_semantic_aliases.py \
        --db app/src/main/assets/translated.db \
        --model-path D:/models/text2vec-base-chinese

The generator only considers high-frequency words from jieba's dictionary that
the runtime dictionary cannot already match directly.  It embeds cleaned
dictionary-definition anchors once, evaluates candidates with batched cosine
similarity, and accepts only POS-compatible, unambiguous matches.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


# Keep this list intentionally small and reviewable.  Values are anchor text
# after definition cleanup, not Alician headwords or database ids.  These are
# common, clear synonyms which some text2vec revisions score below the strict
# automatic threshold.
REVIEWED_ALIASES: dict[str, str] = {
    "飞起": "起飞",
    "哀愁": "悲伤",
    "瞧见": "看见",
    "协助": "帮助",
    "援助": "救助",
    "奔跑": "跑",
    "终止": "停止",
    "快速": "很快",
    "难过": "感到伤心",
    "喜爱": "爱",
    "行走": "行进",
}

# High cosine alone cannot distinguish synonymy from antonymy, part-whole,
# hypernym, event-stage, or argument-direction relations.  These candidates
# were manually reviewed from the pinned model's precision-first output and
# are kept out of the distributable alias set.
REVIEWED_REJECTIONS = frozenset(
    {
        "丑恶",
        "仰望",
        "入睡",
        "倔强",
        "凳子",
        "击溃",
        "击落",
        "卫队",
        "变革",
        "可用",
        "回声",
        "回忆录",
        "城池",
        "堡垒",
        "墓穴",
        "墓葬",
        "声波",
        "声调",
        "声道",
        "夜幕",
        "夜色",
        "大旗",
        "宴会",
        "崇敬",
        "常常",
        "床上",
        "床单",
        "应有",
        "抓好",
        "按住",
        "找出",
        "换装",
        "旗杆",
        "果树",
        "果蔬",
        "歌词",
        "歌谣",
        "毒物",
        "水底",
        "流泪",
        "液态",
        "照相机",
        "燃烧",
        "猜疑",
        "狂风",
        "睡梦",
        "碑亭",
        "竖立",
        "耸立",
        "血浆",
        "触角",
        "躯干",
        "逃往",
        "风景线",
        "飓风",
        "牙口",
        "睡着",
        "笑脸",
        "身形",
        "香味",
        "香气",
        "骗人",
        "高台",
    }
)


CJK_CLASS = r"\u3400-\u9fff"
PURE_CJK_RE = re.compile(rf"^[{CJK_CLASS}]+$")
CJK_RE = re.compile(rf"[{CJK_CLASS}]")
NUMBERED_PAREN_RE = re.compile(r"[（(]\s*\d+\s*[）)]")
PAREN_CONTENT_RE = re.compile(r"[（(][^()（）]*[）)]")
POS_RE = re.compile(
    r"\b(?:adj|adv|art|conj|interj|n|num|prep|pron|v|vi|vt)\.?",
    re.IGNORECASE,
)
DEFINITION_SPLIT_RE = re.compile(r"[,，、;；/|｜\n\r\t]+")
QUOTES_AND_BRACKETS_RE = re.compile(r"[\"'“”‘’《》<>【】\[\]{}（）()]")

SUPPORTED_DICTIONARY_POS = {
    "n": "n",
    "v": "v",
    "vt": "v",
    "vi": "v",
    "adj": "adj",
    "adv": "adv",
}

# Jieba ICTCLAS-like tags which are content-bearing enough for automatic
# aliases.  Ambiguous tags deliberately expose all compatible dictionary
# families; proper-name and numeral tags are rejected before this mapping.
JIEBA_POS_FAMILIES: dict[str, frozenset[str]] = {
    "n": frozenset({"n"}),
    "ng": frozenset({"n"}),
    "nl": frozenset({"n"}),
    "v": frozenset({"v"}),
    "vg": frozenset({"v"}),
    "vd": frozenset({"v", "adv"}),
    "vn": frozenset({"v", "n"}),
    "a": frozenset({"adj"}),
    "ag": frozenset({"adj"}),
    "ad": frozenset({"adj", "adv"}),
    "an": frozenset({"adj", "n"}),
    "d": frozenset({"adv"}),
}
PROPER_NAME_POS_PREFIXES = ("nr", "ns", "nt", "nz", "nw")
NUMERIC_POS_PREFIXES = ("m", "mq")

FUNCTION_WORDS = frozenset(
    {
        "一个",
        "一些",
        "一种",
        "这个",
        "那个",
        "这些",
        "那些",
        "这里",
        "那里",
        "其中",
        "自己",
        "我们",
        "你们",
        "他们",
        "她们",
        "它们",
        "大家",
        "别人",
        "什么",
        "怎么",
        "怎样",
        "为何",
        "为什么",
        "因为",
        "所以",
        "但是",
        "可是",
        "然而",
        "如果",
        "虽然",
        "而且",
        "以及",
        "或者",
        "还是",
        "然后",
        "于是",
        "就是",
        "只是",
        "也是",
        "都是",
        "已经",
        "正在",
        "仍然",
        "仍旧",
        "曾经",
        "将要",
        "可能",
        "可以",
        "应该",
        "必须",
        "需要",
        "没有",
        "不是",
        "不能",
        "不会",
        "不要",
        "不再",
        "并不",
        "并非",
        "对于",
        "关于",
        "由于",
        "通过",
        "按照",
        "为了",
        "除了",
        "作为",
        "随着",
        "之间",
        "之中",
        "之一",
        "等等",
        "的话",
        "一样",
        "一般",
        "如何",
        "是否",
    }
)
CHINESE_NUMERALS = frozenset("〇零一二两三四五六七八九十百千万亿兆")
NEGATION_PREFIXES = (
    "并非",
    "并不",
    "从未",
    "绝不",
    "毫不",
    "没有",
    "没能",
    "未能",
    "未曾",
    "不是",
    "不能",
    "不会",
    "不可",
    "不要",
    "不必",
    "不得",
    "不",
    "没",
    "未",
    "无",
    "非",
    "莫",
    "勿",
    "别",
)
POSITIVE_POLARITY_MARKERS = (
    "爱",
    "喜",
    "欢",
    "乐",
    "幸福",
    "美好",
    "愉快",
    "善",
)
NEGATIVE_POLARITY_MARKERS = (
    "难过",
    "厌",
    "恶",
    "恨",
    "悲",
    "哀",
    "愁",
    "伤",
    "痛",
    "苦",
    "怒",
    "怕",
    "恐",
    "惧",
    "烦",
    "坏",
    "丑",
    "恼",
    "忧",
    "哭",
    "泣",
    "死",
    "亡",
    "病",
)
ANTONYM_MARKER_PAIRS = (
    ("上", "下"),
    ("前", "后"),
    ("大", "小"),
    ("多", "少"),
    ("快", "慢"),
    ("高", "低"),
    ("好", "坏"),
    ("爱", "恨"),
    ("生", "死"),
    ("开", "关"),
    ("冷", "热"),
    ("早", "晚"),
    ("长", "短"),
    ("进", "退"),
    ("来", "去"),
    ("有", "无"),
    ("真", "假"),
    ("新", "旧"),
    ("强", "弱"),
    ("内", "外"),
    ("正", "反"),
)

NOISY_DEFINITIONS = frozenset(
    {
        "不译",
        "未找到释义",
        "未知",
        "无释义",
        "无",
        "不明",
        "待考",
        "存疑",
    }
)
UNCERTAINTY_RE = re.compile(r"(?:\(\s*\?\s*\)|（\s*[?？]\s*）|[?？])")


@dataclass(frozen=True)
class Sense:
    sense_id: int
    explanation: str
    pos_family: str
    count: int
    variety: int
    uncertain: bool


@dataclass
class AnchorCluster:
    text: str
    pos_family: str
    senses: list[Sense]
    automatic_eligible: bool


@dataclass(frozen=True)
class Candidate:
    word: str
    frequency: int
    source_pos: str
    families: frozenset[str]


@dataclass(frozen=True)
class ProposedAlias:
    candidate: Candidate
    anchor_index: int
    similarity: float
    margin: float
    method: str


@dataclass(frozen=True)
class AliasRow:
    sense_id: int
    alias: str
    similarity: float
    rank: int
    source_frequency: int
    source_pos: str
    model_name: str
    model_revision: str
    generated_at: str
    generation_method: str


@dataclass
class DictionaryData:
    anchors: list[AnchorCluster]
    direct_terms: set[str]
    dictionary_row_count: int
    dictionary_sha256: str


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def normalize_dictionary_pos(raw: object) -> str | None:
    pos = str(raw or "").strip().lower().rstrip(".")
    return SUPPORTED_DICTIONARY_POS.get(pos)


def normalize_runtime_term(raw: object) -> str:
    """Mirror TranslationService._normalize_term for direct-match exclusion."""
    term = str(raw or "").strip()
    term = QUOTES_AND_BRACKETS_RE.sub("", term)
    term = re.sub(r"\s+", "", term)
    term = term.strip("。.!?？：:；;，,、")
    if not term or not CJK_RE.search(term):
        return ""
    if term in {"不译", "未找到释义"} or len(term) > 12:
        return ""
    return term


def extract_runtime_terms(explanation: object) -> set[str]:
    """Mirror the runtime's definition-term indexing closely."""
    source = str(explanation or "")
    if not source or not CJK_RE.search(source):
        return set()
    cleaned = NUMBERED_PAREN_RE.sub("，", source)
    cleaned = POS_RE.sub("，", cleaned)
    terms: set[str] = set()
    for part in DEFINITION_SPLIT_RE.split(cleaned):
        term = normalize_runtime_term(part)
        if not term:
            continue
        terms.add(term)
        if term.startswith("表") and len(term) > 2:
            terms.add(normalize_runtime_term(term[1:]))
        if term.endswith("的") and len(term) > 1:
            terms.add(normalize_runtime_term(term[:-1]))
    terms.discard("")
    return terms


def strip_parenthetical_content(text: str) -> str:
    # Definitions do not contain deeply nested parentheses in practice, but
    # repeat so malformed nested notes cannot become part of an anchor.
    previous = ""
    while previous != text:
        previous = text
        text = PAREN_CONTENT_RE.sub("", text)
    return text


def has_semantic_parenthetical(text: str) -> bool:
    """Return whether parentheses narrow a sense instead of adding a marker."""
    for match in re.finditer(r"[（(]([^()（）]*)[）)]", str(text or "")):
        if CJK_RE.search(match.group(1)):
            return True
    return False


def normalize_anchor_piece(raw: object, pos_family: str) -> str:
    text = str(raw or "").strip()
    text = NUMBERED_PAREN_RE.sub("", text)
    text = strip_parenthetical_content(text)
    text = POS_RE.sub("", text)
    text = QUOTES_AND_BRACKETS_RE.sub("", text)
    text = re.sub(r"\s+", "", text)
    text = text.strip("。.!?？：:；;，,、…")
    text = re.sub(r"^(?:表示|意为|意思是|指的是|用于|用来)", "", text)

    if pos_family == "adj" and text.endswith("的") and len(text) > 1:
        text = text[:-1]
    elif pos_family == "adv" and text.endswith("地") and len(text) > 1:
        text = text[:-1]

    if (
        not text
        or text in NOISY_DEFINITIONS
        or not PURE_CJK_RE.fullmatch(text)
        or len(text) > 12
    ):
        return ""
    return text


def extract_anchor_pieces(explanation: object, pos_family: str) -> list[str]:
    source = str(explanation or "")
    cleaned = NUMBERED_PAREN_RE.sub("，", source)
    cleaned = POS_RE.sub("，", cleaned)
    seen: set[str] = set()
    anchors: list[str] = []
    for part in DEFINITION_SPLIT_RE.split(cleaned):
        anchor = normalize_anchor_piece(part, pos_family)
        if anchor and anchor not in seen:
            seen.add(anchor)
            anchors.append(anchor)
    return anchors


def dictionary_fingerprint(rows: Iterable[sqlite3.Row]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        fields = (
            row["id"],
            row["headword_id"],
            row["words"],
            row["explanation"],
            row["class"],
            row["sense_order"],
        )
        digest.update(
            json.dumps(
                fields,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def open_read_only_database(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def load_dictionary_data(path: Path) -> DictionaryData:
    with open_read_only_database(path) as connection:
        if not table_exists(connection, "dictionary"):
            raise RuntimeError(f"{path} has no dictionary table")
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(dictionary)").fetchall()
        }
        required = {
            "id",
            "headword_id",
            "words",
            "explanation",
            "class",
            "sense_order",
            "count",
            "variety",
        }
        missing = sorted(required - columns)
        if missing:
            raise RuntimeError(
                "dictionary table is missing required columns: "
                + ", ".join(missing)
            )

        rows = connection.execute(
            'SELECT id, headword_id, words, explanation, "class" AS "class", '
            "sense_order, count, variety FROM dictionary ORDER BY id"
        ).fetchall()
        direct_terms: set[str] = set()
        clusters: dict[tuple[str, str], list[Sense]] = defaultdict(list)

        for row in rows:
            explanation = str(row["explanation"] or "")
            direct_terms.update(extract_runtime_terms(explanation))
            pos_family = normalize_dictionary_pos(row["class"])
            if pos_family is None:
                continue
            uncertain = bool(UNCERTAINTY_RE.search(explanation))
            sense = Sense(
                sense_id=int(row["id"]),
                explanation=explanation,
                pos_family=pos_family,
                count=int(row["count"] or 0),
                variety=int(row["variety"] or 0),
                uncertain=uncertain,
            )
            for anchor in extract_anchor_pieces(explanation, pos_family):
                key = (anchor, pos_family)
                if all(existing.sense_id != sense.sense_id for existing in clusters[key]):
                    clusters[key].append(sense)

        if table_exists(connection, "phrase"):
            phrase_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(phrase)").fetchall()
            }
            if "explanation" in phrase_columns:
                for row in connection.execute(
                    "SELECT explanation FROM phrase "
                    "WHERE explanation IS NOT NULL"
                ):
                    direct_terms.update(extract_runtime_terms(row["explanation"]))

    anchors = [
        AnchorCluster(
            text=text,
            pos_family=pos_family,
            senses=sorted(
                senses,
                key=lambda sense: (
                    -sense.count,
                    -sense.variety,
                    sense.sense_id,
                ),
            ),
            automatic_eligible=any(not sense.uncertain for sense in senses),
        )
        for (text, pos_family), senses in sorted(clusters.items())
    ]
    return DictionaryData(
        anchors=anchors,
        direct_terms=direct_terms,
        dictionary_row_count=len(rows),
        dictionary_sha256=dictionary_fingerprint(rows),
    )


def read_jieba_dictionary(
    jieba_module: Any,
    override_path: Path | None,
) -> tuple[bytes, str]:
    if override_path is not None:
        if not override_path.is_file():
            raise RuntimeError(f"jieba dictionary not found: {override_path}")
        jieba_module.set_dictionary(str(override_path))
        return override_path.read_bytes(), str(override_path.resolve())

    handle = jieba_module.dt.get_dict_file()
    try:
        raw = handle.read()
        source = str(getattr(handle, "name", "<jieba-default-dictionary>"))
    finally:
        handle.close()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return bytes(raw), source


def parse_jieba_entries(raw: bytes) -> dict[str, tuple[int, set[str]]]:
    entries: dict[str, tuple[int, set[str]]] = {}
    for line_number, raw_line in enumerate(
        raw.decode("utf-8-sig").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.rsplit(maxsplit=2)
        if len(parts) < 2:
            continue
        word = parts[0].strip()
        try:
            frequency = int(parts[1])
        except ValueError:
            continue
        pos = parts[2].strip().lower() if len(parts) >= 3 else "x"
        if not word or frequency < 0:
            continue
        old_frequency, old_tags = entries.get(word, (0, set()))
        old_tags.add(pos)
        entries[word] = (max(old_frequency, frequency), old_tags)
    return entries


def candidate_families(pos_tags: Iterable[str]) -> frozenset[str]:
    tags = {str(tag).strip().lower() for tag in pos_tags if str(tag).strip()}
    if any(
        tag.startswith(PROPER_NAME_POS_PREFIXES + NUMERIC_POS_PREFIXES)
        for tag in tags
    ):
        return frozenset()
    families: set[str] = set()
    for tag in tags:
        families.update(JIEBA_POS_FAMILIES.get(tag, ()))
    return frozenset(families)


def chinese_numeric_word(word: str) -> bool:
    if word and all(character in CHINESE_NUMERALS for character in word):
        return True
    return bool(
        word.startswith("第")
        and len(word) > 1
        and all(character in CHINESE_NUMERALS for character in word[1:])
    )


def candidate_rejection_reason(
    word: str,
    pos_tags: Iterable[str],
    direct_terms: set[str],
) -> str | None:
    if not PURE_CJK_RE.fullmatch(word) or not 2 <= len(word) <= 6:
        return "shape"
    if word in REVIEWED_REJECTIONS:
        return "reviewed_false_positive"
    if word in direct_terms:
        return "already_direct"
    if word in FUNCTION_WORDS:
        return "function_word"
    if chinese_numeric_word(word):
        return "number"
    tags = {str(tag).strip().lower() for tag in pos_tags}
    if any(tag.startswith(PROPER_NAME_POS_PREFIXES) for tag in tags):
        return "proper_name"
    if any(tag.startswith(NUMERIC_POS_PREFIXES) for tag in tags):
        return "number_pos"
    if not candidate_families(tags):
        return "non_content_pos"
    return None


def infer_reviewed_pos(
    alias: str,
    posseg_module: Any,
) -> set[str]:
    try:
        tokens = list(posseg_module.cut(alias, HMM=False))
    except TypeError:
        tokens = list(posseg_module.cut(alias))
    if len(tokens) == 1 and str(tokens[0].word) == alias:
        return {str(tokens[0].flag).lower()}
    return set()


def build_candidates(
    entries: Mapping[str, tuple[int, set[str]]],
    direct_terms: set[str],
    min_frequency: int,
    max_candidates: int,
    posseg_module: Any,
) -> tuple[list[Candidate], Counter[str], int]:
    rejection_counts: Counter[str] = Counter()
    accepted: dict[str, Candidate] = {}

    ranked_entries = sorted(
        entries.items(),
        key=lambda item: (-item[1][0], item[0]),
    )
    high_frequency_seen = 0
    for word, (frequency, pos_tags) in ranked_entries:
        if frequency < min_frequency:
            break
        high_frequency_seen += 1
        reason = candidate_rejection_reason(word, pos_tags, direct_terms)
        if reason:
            rejection_counts[reason] += 1
            continue
        families = candidate_families(pos_tags)
        accepted[word] = Candidate(
            word=word,
            frequency=frequency,
            source_pos=",".join(sorted(pos_tags)),
            families=families,
        )
        if len(accepted) >= max_candidates:
            break

    # Reviewed aliases are allowed below the frequency cutoff, but they still
    # have to be unseen direct terms, pure CJK content words, and POS-valid.
    for alias in REVIEWED_ALIASES:
        if alias in accepted:
            continue
        frequency, pos_tags = entries.get(alias, (0, set()))
        if not pos_tags:
            pos_tags = infer_reviewed_pos(alias, posseg_module)
        reason = candidate_rejection_reason(alias, pos_tags, direct_terms)
        if reason:
            rejection_counts[f"reviewed_{reason}"] += 1
            log(f"warning: reviewed alias {alias!r} skipped ({reason})")
            continue
        accepted[alias] = Candidate(
            word=alias,
            frequency=frequency,
            source_pos=",".join(sorted(pos_tags)),
            families=candidate_families(pos_tags),
        )

    candidates = sorted(
        accepted.values(),
        key=lambda item: (-item.frequency, item.word),
    )
    return candidates, rejection_counts, high_frequency_seen


def lexical_negation(text: str) -> bool:
    return any(text.startswith(prefix) for prefix in NEGATION_PREFIXES)


def sentiment_polarity(text: str) -> int:
    positive = any(marker in text for marker in POSITIVE_POLARITY_MARKERS)
    negative = any(marker in text for marker in NEGATIVE_POLARITY_MARKERS)
    if positive == negative:
        return 0
    return 1 if positive else -1


def polarity_compatible(alias: str, anchor: str) -> bool:
    if lexical_negation(alias) != lexical_negation(anchor):
        return False

    alias_sentiment = sentiment_polarity(alias)
    anchor_sentiment = sentiment_polarity(anchor)
    # Precision first: when a word carries explicit affect, require the anchor
    # to carry the same affect.  This blocks failures such as 厌恶 -> 吃.
    if (
        (alias_sentiment or anchor_sentiment)
        and alias_sentiment != anchor_sentiment
    ):
        return False

    for left, right in ANTONYM_MARKER_PAIRS:
        if (left in alias and right in anchor) or (
            right in alias and left in anchor
        ):
            return False
    return True


def local_model_revision(model_path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit

    git_dir = model_path / ".git"
    head = git_dir / "HEAD"
    if head.is_file():
        head_value = head.read_text(encoding="utf-8", errors="replace").strip()
        if head_value.startswith("ref: "):
            ref_file = git_dir / head_value[5:].strip()
            if ref_file.is_file():
                commit = ref_file.read_text(
                    encoding="ascii",
                    errors="replace",
                ).strip()
                if commit:
                    return f"git:{commit}"
        elif head_value:
            return f"git:{head_value}"

    metadata_names = {
        "config.json",
        "modules.json",
        "sentence_bert_config.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
    }
    files = sorted(
        (
            path
            for path in model_path.rglob("*")
            if path.is_file() and path.name in metadata_names
        ),
        key=lambda path: path.relative_to(model_path).as_posix(),
    )
    digest = hashlib.sha256()
    if files:
        for path in files:
            digest.update(path.relative_to(model_path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    else:
        digest.update(str(model_path.resolve()).encode("utf-8"))
    return f"config-sha256:{digest.hexdigest()[:20]}"


def load_sentence_model(model_path: Path) -> Any:
    try:
        text2vec_module = importlib.import_module("text2vec")
    except ImportError as error:
        raise RuntimeError(
            "text2vec is required for generation; install the development "
            "dependency before running this script"
        ) from error
    sentence_model = getattr(text2vec_module, "SentenceModel", None)
    if sentence_model is None:
        raise RuntimeError("installed text2vec has no SentenceModel")
    return sentence_model(str(model_path))


def encode_texts(
    model: Any,
    texts: Sequence[str],
    batch_size: int,
    show_progress: bool,
    numpy_module: Any,
) -> Any:
    kwargs = {
        "batch_size": batch_size,
        "show_progress_bar": show_progress,
    }
    try:
        encoded = model.encode(list(texts), **kwargs)
    except TypeError:
        kwargs.pop("show_progress_bar")
        encoded = model.encode(list(texts), **kwargs)
    if hasattr(encoded, "detach"):
        encoded = encoded.detach()
    if hasattr(encoded, "cpu"):
        encoded = encoded.cpu()
    if hasattr(encoded, "numpy"):
        encoded = encoded.numpy()
    array = numpy_module.asarray(encoded, dtype=numpy_module.float32)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if array.ndim != 2 or array.shape[0] != len(texts):
        raise RuntimeError(
            "text2vec returned an unexpected embedding shape: "
            f"{getattr(array, 'shape', None)}"
        )
    norms = numpy_module.linalg.norm(array, axis=1, keepdims=True)
    if numpy_module.any(norms <= 1e-12):
        raise RuntimeError("text2vec returned a zero-length embedding")
    return array / norms


def required_automatic_similarity(
    candidate: Candidate,
    anchor: AnchorCluster,
    base_threshold: float,
) -> float:
    threshold = base_threshold
    if len(candidate.word) <= 2:
        threshold += 0.015
    if len(anchor.text) <= 1:
        threshold += 0.045
    return min(0.97, threshold)


def best_and_margin(
    similarities: Any,
    indices: Sequence[int],
    anchors: Sequence[AnchorCluster],
) -> tuple[int, float, float] | None:
    if not indices:
        return None
    best_index = max(indices, key=lambda index: float(similarities[index]))
    best_score = float(similarities[best_index])
    second_scores = [
        float(similarities[index])
        for index in indices
        if anchors[index].text != anchors[best_index].text
    ]
    second_score = max(second_scores) if second_scores else -1.0
    return best_index, best_score, best_score - second_score


def resolve_reviewed_targets(
    anchors: Sequence[AnchorCluster],
) -> dict[str, list[int]]:
    by_text: dict[str, list[int]] = defaultdict(list)
    for index, anchor in enumerate(anchors):
        by_text[anchor.text].append(index)
    resolved: dict[str, list[int]] = {}
    for alias, target_text in REVIEWED_ALIASES.items():
        normalized_targets = {
            normalize_anchor_piece(target_text, family)
            for family in {"n", "v", "adj", "adv"}
        }
        indices: list[int] = []
        for normalized in normalized_targets:
            if normalized:
                indices.extend(by_text.get(normalized, ()))
        if not indices:
            log(
                f"warning: reviewed alias {alias!r} target anchor "
                f"{target_text!r} does not exist"
            )
        resolved[alias] = sorted(set(indices))
    return resolved


def score_candidates(
    model: Any,
    anchors: Sequence[AnchorCluster],
    candidates: Sequence[Candidate],
    *,
    embedding_batch_size: int,
    cosine_batch_size: int,
    min_similarity: float,
    min_margin: float,
    reviewed_min_similarity: float,
    show_progress: bool,
) -> tuple[list[ProposedAlias], Counter[str]]:
    try:
        numpy_module = importlib.import_module("numpy")
    except ImportError as error:
        raise RuntimeError(
            "numpy is required for batched cosine generation"
        ) from error

    log(f"encoding {len(anchors):,} normalized anchor clusters")
    anchor_embeddings = encode_texts(
        model,
        [anchor.text for anchor in anchors],
        embedding_batch_size,
        show_progress,
        numpy_module,
    )
    automatic_by_family: dict[str, list[int]] = defaultdict(list)
    compatible_by_family: dict[str, list[int]] = defaultdict(list)
    for index, anchor in enumerate(anchors):
        compatible_by_family[anchor.pos_family].append(index)
        if anchor.automatic_eligible:
            automatic_by_family[anchor.pos_family].append(index)

    reviewed_targets = resolve_reviewed_targets(anchors)
    proposals: list[ProposedAlias] = []
    rejection_counts: Counter[str] = Counter()

    for start in range(0, len(candidates), cosine_batch_size):
        batch = candidates[start : start + cosine_batch_size]
        candidate_embeddings = encode_texts(
            model,
            [candidate.word for candidate in batch],
            embedding_batch_size,
            False,
            numpy_module,
        )
        cosine = candidate_embeddings @ anchor_embeddings.T
        for row_index, candidate in enumerate(batch):
            similarities = cosine[row_index]
            if candidate.word in REVIEWED_ALIASES:
                target_indices = [
                    index
                    for index in reviewed_targets.get(candidate.word, ())
                    if anchors[index].pos_family in candidate.families
                    and polarity_compatible(
                        candidate.word,
                        anchors[index].text,
                    )
                ]
                reviewed_result = best_and_margin(
                    similarities,
                    target_indices,
                    anchors,
                )
                if reviewed_result is None:
                    rejection_counts["reviewed_target_or_pos"] += 1
                    continue
                anchor_index, score, margin = reviewed_result
                if score < reviewed_min_similarity:
                    rejection_counts["reviewed_score"] += 1
                    log(
                        f"warning: reviewed alias {candidate.word!r} scored "
                        f"{score:.4f} below {reviewed_min_similarity:.4f}"
                    )
                    continue
                proposals.append(
                    ProposedAlias(
                        candidate=candidate,
                        anchor_index=anchor_index,
                        similarity=score,
                        margin=margin,
                        method="reviewed_text2vec_cosine",
                    )
                )
                continue

            allowed_indices = sorted(
                {
                    index
                    for family in candidate.families
                    for index in automatic_by_family.get(family, ())
                }
            )
            result = best_and_margin(similarities, allowed_indices, anchors)
            if result is None:
                rejection_counts["no_compatible_anchor"] += 1
                continue
            anchor_index, score, margin = result
            anchor = anchors[anchor_index]
            threshold = required_automatic_similarity(
                candidate,
                anchor,
                min_similarity,
            )
            if score < threshold:
                rejection_counts["score"] += 1
                continue
            if margin < min_margin:
                rejection_counts["margin"] += 1
                continue
            if not polarity_compatible(candidate.word, anchor.text):
                rejection_counts["polarity"] += 1
                continue
            # Compounds which merely contain a short anchor are usually
            # hyponyms or compositional phrases rather than substitutable
            # aliases.  Reviewed aliases may intentionally override this.
            if (
                candidate.word in anchor.text
                or anchor.text in candidate.word
            ):
                rejection_counts["substring_relation"] += 1
                continue
            proposals.append(
                ProposedAlias(
                    candidate=candidate,
                    anchor_index=anchor_index,
                    similarity=score,
                    margin=margin,
                    method="text2vec_cosine_margin",
                )
            )

        completed = min(start + len(batch), len(candidates))
        log(f"scored {completed:,}/{len(candidates):,} candidates")

    return proposals, rejection_counts


def select_aliases(
    proposals: Sequence[ProposedAlias],
    anchors: Sequence[AnchorCluster],
    *,
    max_aliases_per_anchor: int,
    model_name: str,
    model_revision: str,
    generated_at: str,
) -> tuple[list[AliasRow], int]:
    by_anchor: dict[int, list[ProposedAlias]] = defaultdict(list)
    for proposal in proposals:
        by_anchor[proposal.anchor_index].append(proposal)

    selected: list[tuple[int, int, ProposedAlias]] = []
    for anchor_index, items in by_anchor.items():
        ranked = sorted(
            items,
            key=lambda item: (
                item.method != "reviewed_text2vec_cosine",
                -item.similarity,
                -item.margin,
                -item.candidate.frequency,
                item.candidate.word,
            ),
        )[:max_aliases_per_anchor]
        for rank, proposal in enumerate(ranked, start=1):
            selected.append((anchor_index, rank, proposal))

    rows_by_key: dict[tuple[str, int], AliasRow] = {}
    for anchor_index, rank, proposal in selected:
        anchor = anchors[anchor_index]
        for sense in anchor.senses:
            # A definition such as “声音(嗓音)” is a narrowed sense.  Its base
            # text may share an embedding anchor with generic “声音”, but a
            # generic sound alias must not fan out to the voice-only word.
            if has_semantic_parenthetical(sense.explanation):
                continue
            row = AliasRow(
                sense_id=sense.sense_id,
                alias=proposal.candidate.word,
                similarity=proposal.similarity,
                rank=rank,
                source_frequency=proposal.candidate.frequency,
                source_pos=proposal.candidate.source_pos,
                model_name=model_name,
                model_revision=model_revision,
                generated_at=generated_at,
                generation_method=proposal.method,
            )
            key = (row.alias, row.sense_id)
            previous = rows_by_key.get(key)
            if previous is None or (
                row.generation_method == "reviewed_text2vec_cosine",
                row.similarity,
                -row.rank,
            ) > (
                previous.generation_method == "reviewed_text2vec_cosine",
                previous.similarity,
                -previous.rank,
            ):
                rows_by_key[key] = row

    rows = sorted(
        rows_by_key.values(),
        key=lambda row: (row.alias, row.rank, row.sense_id),
    )
    unique_aliases = len({row.alias for row in rows})
    return rows, unique_aliases


ALIAS_TABLE_SQL = """
CREATE TABLE dictionary_semantic_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sense_id INTEGER NOT NULL,
    alias TEXT NOT NULL,
    similarity REAL NOT NULL,
    rank INTEGER NOT NULL,
    source_frequency INTEGER NOT NULL,
    source_pos TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_revision TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    generation_method TEXT NOT NULL,
    UNIQUE (alias, sense_id),
    FOREIGN KEY (sense_id) REFERENCES dictionary(id) ON DELETE CASCADE
)
"""

METADATA_TABLE_SQL = """
CREATE TABLE semantic_alias_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""


def current_dictionary_fingerprint(connection: sqlite3.Connection) -> str:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        'SELECT id, headword_id, words, explanation, "class" AS "class", '
        "sense_order FROM dictionary ORDER BY id"
    ).fetchall()
    return dictionary_fingerprint(rows)


def write_database(
    path: Path,
    rows: Sequence[AliasRow],
    metadata: Mapping[str, str],
    expected_dictionary_sha256: str,
) -> None:
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        current_sha256 = current_dictionary_fingerprint(connection)
        if current_sha256 != expected_dictionary_sha256:
            raise RuntimeError(
                "dictionary changed while aliases were being generated; "
                "refusing to write stale sense ids"
            )

        connection.execute("DROP TABLE IF EXISTS dictionary_semantic_aliases")
        connection.execute(ALIAS_TABLE_SQL)
        connection.executemany(
            """
            INSERT INTO dictionary_semantic_aliases (
                sense_id,
                alias,
                similarity,
                rank,
                source_frequency,
                source_pos,
                model_name,
                model_revision,
                generated_at,
                generation_method
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.sense_id,
                    row.alias,
                    row.similarity,
                    row.rank,
                    row.source_frequency,
                    row.source_pos,
                    row.model_name,
                    row.model_revision,
                    row.generated_at,
                    row.generation_method,
                )
                for row in rows
            ],
        )
        connection.execute(
            "CREATE INDEX idx_semantic_aliases_alias "
            "ON dictionary_semantic_aliases(alias)"
        )
        connection.execute(
            "CREATE INDEX idx_semantic_aliases_sense "
            "ON dictionary_semantic_aliases(sense_id, rank)"
        )

        connection.execute("DROP TABLE IF EXISTS semantic_alias_metadata")
        connection.execute(METADATA_TABLE_SQL)
        connection.executemany(
            "INSERT INTO semantic_alias_metadata(key, value) VALUES (?, ?)",
            sorted(metadata.items()),
        )
        # Retire the v1 dataset: it contained nearest existing definitions
        # rather than new query aliases and is intentionally not consumed.
        connection.execute("DROP TABLE IF EXISTS dictionary_sense_expansions")
        connection.execute("DROP TABLE IF EXISTS semantic_expansion_metadata")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate precision-first, previously-unmatched Chinese semantic "
            "aliases with a local text2vec model and jieba's frequency lexicon."
        ),
    )
    parser.add_argument(
        "--db",
        required=True,
        type=Path,
        help="existing translated.db to update",
    )
    parser.add_argument(
        "--model-path",
        required=True,
        type=Path,
        help="local text2vec SentenceModel directory (network is never used)",
    )
    parser.add_argument(
        "--jieba-dict",
        type=Path,
        help="optional jieba-format dictionary; defaults to jieba's bundled dict",
    )
    parser.add_argument(
        "--model-name",
        help="metadata model name; defaults to model directory name",
    )
    parser.add_argument(
        "--model-revision",
        help="metadata revision; defaults to local git/config fingerprint",
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=200,
        help="minimum jieba frequency for automatic candidates (default: 200)",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=25000,
        help="maximum accepted high-frequency candidates to score (default: 25000)",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.82,
        help="automatic cosine threshold before short-word penalties (default: 0.82)",
    )
    parser.add_argument(
        "--min-margin",
        type=float,
        default=0.075,
        help="minimum top-1 versus next distinct-anchor margin (default: 0.075)",
    )
    parser.add_argument(
        "--reviewed-min-similarity",
        type=float,
        default=0.45,
        help="cosine floor for REVIEWED_ALIASES (default: 0.45)",
    )
    parser.add_argument(
        "--max-aliases-per-anchor",
        type=int,
        default=6,
        help="maximum aliases retained for one normalized anchor (default: 6)",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=64,
        help="text2vec encode batch size (default: 64)",
    )
    parser.add_argument(
        "--cosine-batch-size",
        type=int,
        default=1024,
        help="candidate rows per cosine matrix batch (default: 1024)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="generate and report results without changing the database",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="disable the model's anchor-encoding progress bar",
    )
    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if not args.db.is_file():
        parser.error(f"--db does not exist or is not a file: {args.db}")
    if not args.model_path.is_dir():
        parser.error(
            "--model-path must be an existing local model directory: "
            f"{args.model_path}"
        )
    if args.min_frequency < 0:
        parser.error("--min-frequency must be non-negative")
    if args.max_candidates < 1:
        parser.error("--max-candidates must be positive")
    for name in (
        "min_similarity",
        "min_margin",
        "reviewed_min_similarity",
    ):
        value = float(getattr(args, name))
        if not 0.0 <= value <= 1.0:
            parser.error(f"--{name.replace('_', '-')} must be between 0 and 1")
    if args.reviewed_min_similarity > args.min_similarity:
        parser.error(
            "--reviewed-min-similarity must not exceed --min-similarity"
        )
    if args.max_aliases_per_anchor < 1:
        parser.error("--max-aliases-per-anchor must be positive")
    if args.embedding_batch_size < 1 or args.cosine_batch_size < 1:
        parser.error("batch sizes must be positive")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args, parser)

    try:
        jieba_module = importlib.import_module("jieba")
        posseg_module = importlib.import_module("jieba.posseg")
    except ImportError as error:
        parser.error(
            "jieba is required for candidate frequency and POS filtering"
        )
        raise AssertionError("unreachable") from error

    log(f"reading dictionary: {args.db.resolve()}")
    dictionary_data = load_dictionary_data(args.db)
    if not dictionary_data.anchors:
        raise RuntimeError("no usable normalized dictionary anchors were found")

    jieba_raw, jieba_source = read_jieba_dictionary(
        jieba_module,
        args.jieba_dict,
    )
    jieba_sha256 = hashlib.sha256(jieba_raw).hexdigest()
    jieba_entries = parse_jieba_entries(jieba_raw)
    candidates, candidate_filter_counts, high_frequency_seen = build_candidates(
        jieba_entries,
        dictionary_data.direct_terms,
        args.min_frequency,
        args.max_candidates,
        posseg_module,
    )
    if not candidates:
        raise RuntimeError("no candidates survived the jieba/direct-term filters")

    model_path = args.model_path.resolve()
    model_revision = local_model_revision(model_path, args.model_revision)
    model_name = args.model_name or model_path.name
    log(
        f"loading local model: {model_name} ({model_revision}); "
        f"{len(candidates):,} candidates survived prefilters"
    )
    model = load_sentence_model(model_path)
    detected_model_name = getattr(model, "model_name_or_path", None)
    if not args.model_name and detected_model_name:
        detected_text = str(detected_model_name)
        # Do not put an absolute workstation path in a distributable database.
        model_name = Path(detected_text).name or model_name

    proposals, score_filter_counts = score_candidates(
        model,
        dictionary_data.anchors,
        candidates,
        embedding_batch_size=args.embedding_batch_size,
        cosine_batch_size=args.cosine_batch_size,
        min_similarity=args.min_similarity,
        min_margin=args.min_margin,
        reviewed_min_similarity=args.reviewed_min_similarity,
        show_progress=not args.no_progress,
    )
    generated_at = datetime.now(timezone.utc).isoformat(
        timespec="seconds",
    ).replace("+00:00", "Z")
    rows, unique_aliases = select_aliases(
        proposals,
        dictionary_data.anchors,
        max_aliases_per_anchor=args.max_aliases_per_anchor,
        model_name=model_name,
        model_revision=model_revision,
        generated_at=generated_at,
    )

    reviewed_generated = sorted(
        {
            row.alias
            for row in rows
            if row.generation_method == "reviewed_text2vec_cosine"
        }
    )
    threshold_strategy = {
        "policy": "precision_first_top1_cosine_with_distinct_anchor_margin",
        "automatic_min_similarity": args.min_similarity,
        "short_candidate_penalty": 0.015,
        "single_character_anchor_penalty": 0.045,
        "minimum_margin": args.min_margin,
        "reviewed_min_similarity": args.reviewed_min_similarity,
        "max_aliases_per_anchor": args.max_aliases_per_anchor,
        "filters": [
            "pure_cjk_length_2_to_6",
            "jieba_content_pos_compatible",
            "existing_runtime_terms",
            "function_words",
            "proper_names",
            "numbers",
            "lexical_negation",
            "sentiment_polarity",
            "antonym_markers",
            "substring_hyponyms",
            "reviewed_false_positives",
        ],
    }
    metadata = {
        "dataset_kind": "semantic_alias",
        "schema_version": "1",
        "generated_at": generated_at,
        "generation_method": "text2vec_cosine_margin+jieba_frequency_pos",
        "model_name": model_name,
        "model_revision": model_revision,
        "jieba_version": str(getattr(jieba_module, "__version__", "unknown")),
        "jieba_dictionary": Path(jieba_source).name,
        "jieba_dictionary_sha256": jieba_sha256,
        "dictionary_row_count": str(dictionary_data.dictionary_row_count),
        "dictionary_sha256": dictionary_data.dictionary_sha256,
        "anchor_cluster_count": str(len(dictionary_data.anchors)),
        "jieba_entry_count": str(len(jieba_entries)),
        "high_frequency_entry_count": str(high_frequency_seen),
        "candidate_count": str(len(candidates)),
        "minimum_jieba_frequency": str(args.min_frequency),
        "maximum_candidate_count": str(args.max_candidates),
        "alias_count": str(unique_aliases),
        "unique_alias_count": str(unique_aliases),
        # One normalized alias may intentionally fan out to equivalent senses.
        "sense_row_count": str(len(rows)),
        "reviewed_alias_count": str(len(reviewed_generated)),
        "reviewed_aliases": json.dumps(
            reviewed_generated,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        "candidate_filter_counts": json.dumps(
            dict(sorted(candidate_filter_counts.items())),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "score_filter_counts": json.dumps(
            dict(sorted(score_filter_counts.items())),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "threshold_strategy": json.dumps(
            threshold_strategy,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
    }

    log(
        f"selected {unique_aliases:,} unique aliases / {len(rows):,} "
        f"sense rows; reviewed={','.join(reviewed_generated) or '(none)'}"
    )
    if args.dry_run:
        log("dry-run: database was not changed")
        for row in rows[:30]:
            print(
                f"{row.alias}\tsense={row.sense_id}\t"
                f"score={row.similarity:.4f}\trank={row.rank}\t"
                f"method={row.generation_method}"
            )
        return 0

    write_database(
        args.db,
        rows,
        metadata,
        dictionary_data.dictionary_sha256,
    )
    log(f"updated semantic alias tables in {args.db.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("interrupted; database was not changed")
        raise SystemExit(130)
