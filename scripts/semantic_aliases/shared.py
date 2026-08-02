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


__all__ = [name for name in globals() if not name.startswith("_")]
