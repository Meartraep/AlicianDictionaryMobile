from __future__ import annotations

import os
import re
import sqlite3
import threading
import logging
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Counter as CounterType, DefaultDict, Dict, List, Optional, Tuple

from webui_backend.build_mode import is_lite_build
from webui_backend.dictionary_service import _lev_ratio


_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_CJK_RUN_RE = re.compile(r"[\u3400-\u9fff]+")
_ALICIAN_PART_RE = re.compile(r"[A-Za-z][A-Za-z'-]*|\d+|\s+|[^\sA-Za-z\d]+")
_CHINESE_PART_RE = re.compile(r"[\u3400-\u9fff]+|[A-Za-z][A-Za-z'-]*|\d+|\s+|[^\sA-Za-z\d\u3400-\u9fff]+")
_POS_RE = re.compile(
    r"\b(?:adj|adv|art|conj|interj|n|num|prep|pron|v|vi|vt)\.?",
    re.IGNORECASE,
)
_TEMPLATE_SLOT_RE = re.compile(r"(?:\.{2,}|…+)")
_WORD_FRAGMENT_PARENT_RE = re.compile(
    r"([A-Za-z][A-Za-z'-]*)\s*的一部分",
    re.IGNORECASE,
)
_NO_CLASS_ALIAS_RE = re.compile(
    r"^\s*同\s*([A-Za-z][A-Za-z'-]*)",
    re.IGNORECASE,
)
_CHINESE_NEGATION_FORMS = tuple(sorted({
    "不可能", "不可以", "不会", "不能", "不可", "不要", "不必", "不得",
    "没有", "没能", "未能", "未曾", "从未", "并不", "并非", "绝不", "毫不",
    "不是", "不", "没", "未", "无", "非",
}, key=len, reverse=True))
# These words contain a character which can independently mark negation, but
# the complete word is lexicalized and must not be rewritten with Nai.  Exact
# dictionary terms are protected separately; this small list covers common
# out-of-dictionary words which tokenizers frequently return as one unit.
_CHINESE_LEXICALIZED_NEGATION_PREFIXES = (
    "非常", "非凡", "无论如何", "无论", "未免", "不妨", "不禁", "不错",
)
# “儿” is also an ordinary morpheme in these lexicalized words, not an erhua
# suffix.  Exact dictionary entries always take priority; this guard prevents
# an absent full entry from silently changing the meaning to its truncated
# prefix (for example “这儿” must not become the demonstrative “这”).
_CHINESE_NON_ERHUA_WORDS = frozenset({
    "儿", "女儿", "男儿", "婴儿", "幼儿", "孤儿",
    "这儿", "那儿", "哪儿", "哪会儿", "一会儿",
})
# Chinese function words which carry a grammatical role but have no lexical
# entry in the Alician dictionary.  Without this table a fluent sentence such
# as “花开了” leaves 了 as an unknown token, which is what forces users to
# rewrite natural Chinese into dictionary-shaped fragments.  An empty target
# means the particle is dropped from the output; a non-empty target reuses an
# attested Alician function word (for example 与/及 share the coordinator a).
_CHINESE_FUNCTION_PARTICLES: Dict[str, Tuple[str, str]] = {
    "了": ("", "aspect_particle"),
    "着": ("", "aspect_particle"),
    "过": ("", "aspect_particle"),
    "得": ("", "structural_particle"),
    "之": ("", "structural_particle"),
    "则": ("", "structural_particle"),
    "而": ("", "structural_particle"),
    "把": ("", "disposal_particle"),
    "与": ("a", "coordinator"),
    "及": ("a", "coordinator"),
    "或": ("", "alternative_particle"),
    "等": ("", "enumeration_particle"),
    "等等": ("", "enumeration_particle"),
    "呢": ("", "modal_particle"),
    "吗": ("", "modal_particle"),
    "吧": ("", "modal_particle"),
    "呀": ("", "modal_particle"),
    "嘛": ("", "modal_particle"),
    "啦": ("", "modal_particle"),
}
# Fluent Chinese compounds whose meaning is not the sum of their parts.  Their
# morphemes are individually known, so without this guard the compositional
# resolver would emit a plausible-looking but wrong reading (for example
# 东西 “thing” must not become 东 + 西 “east + west”).
_CHINESE_NON_COMPOSITIONAL_COMPOUNDS = frozenset({
    "东西", "左右", "大小", "小说", "小心", "时候", "地方",
    "知道", "觉得", "希望", "打算", "马上", "可以", "应该", "一定",
    "已经", "曾经", "正在", "刚才", "然后", "于是", "但是", "可是",
    "虽然", "如果", "因为", "所以", "而且", "或者", "还是", "不过",
    "并且", "因此", "由于", "关于", "对于", "按照", "根据", "通过",
    "除了", "作为", "随着", "重新", "只好", "再也", "当真", "一切",
    "还有", "不用", "不好", "不是", "不再", "没有", "什么", "怎么",
    "怎样", "为何", "这里", "那里", "哪里", "这个", "那个",
    "这些", "那些", "一个", "一些", "一种", "自己", "别人", "大家",
    "大概", "也许", "立刻", "突然", "忽然", "终于", "果然",
    "居然", "仍然", "仍旧", "依然", "照样", "同样", "共同", "一起",
    "一样", "一边", "一点", "一同", "一向", "一旦", "一般",
    "小人", "深刻", "当天", "当年", "心里", "眼里", "手里",
    "鱼雷", "船只", "念头", "一路", "一手", "一头", "一笔", "一脚",
    # Common proper names whose morphemes are individually known: splitting
    # them would produce a plausible but wrong literal reading.
    "北京", "上海", "天津", "重庆", "广州", "深圳", "武汉", "西安", "成都",
    "杭州", "南京", "苏州", "长沙", "郑州", "济南", "青岛", "大连", "沈阳",
    "昆明", "福州", "厦门", "合肥", "南昌", "太原", "兰州", "拉萨", "香港",
    "澳门", "台湾", "海南", "云南", "四川", "广东", "广西", "山东", "山西",
    "河南", "河北", "湖南", "湖北", "江苏", "浙江", "安徽", "福建", "江西",
    "贵州", "陕西", "甘肃", "辽宁", "吉林", "宁夏", "新疆", "西藏",
    "长江", "黄河", "西湖", "东湖", "太湖", "天门",
})
# Compositional resolution only accepts pieces which carry lexical meaning.
# The head must be nominal: verb-headed two-morpheme words are frequently
# lexicalized (听说, 再说, 真是, 像是) and their morpheme sum is not the whole
# meaning, whereas [modifier + noun] is the transparent productive pattern.
_CHINESE_COMPOUND_MODIFIER_FAMILIES = frozenset({"n", "v", "adj", "adv", "num"})
_CHINESE_COMPOUND_HEAD_FAMILIES = frozenset({"n"})
_CHINESE_COMPOUND_CONTENT_FAMILIES = frozenset({"n", "v", "adj", "adv", "num"})
_CHINESE_COMPOUND_MAX_LENGTH = 4
_CHINESE_FALLBACK_BOUNDARIES = frozenset({
    "我", "你", "他", "她", "它", "这", "那", "谁",
    "是", "有", "在", "和", "与", "或", "但", "而",
    "也", "都", "很", "更", "最", "就", "才", "又", "再", "已",
    "将", "把", "被", "从", "向", "到", "为", "给", "让",
    "要", "能", "会", "可", "的", "地", "得", "了", "着", "过",
    "吗", "呢", "吧", "啊", "呀", "哦",
})


def _default_db_path() -> str:
    env_db = os.environ.get("ALICIAN_DB_PATH")
    if env_db:
        return os.path.abspath(env_db)
    return str(Path(__file__).resolve().parent.parent / "translated.db")


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


class TranslationCore:
    """Shared lifecycle, result, and token helpers for translation."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        enable_fallback_matching: Optional[bool] = None,
        enable_composition: Optional[bool] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._db_path = db_path or _default_db_path()
        self._enable_fallback_matching = (
            not is_lite_build()
            if enable_fallback_matching is None
            else bool(enable_fallback_matching)
        )
        # Chinese particles and compositional compounds are resolved from the
        # dictionary alone, so unlike the text2vec fallback they stay available
        # in the lite (Android) build and are on by default.
        self._enable_composition = (
            True if enable_composition is None else bool(enable_composition)
        )
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._entries: List[Dict[str, Any]] = []
        self._word_entries: List[Dict[str, Any]] = []
        self._word_by_lower: Dict[str, List[Dict[str, Any]]] = {}
        self._word_by_sense_id: Dict[int, Dict[str, Any]] = {}
        self._phrases: List[Dict[str, Any]] = []
        self._no_class_templates: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._chinese_sentence_templates: List[Dict[str, Any]] = []
        self._fragment_parents: DefaultDict[str, set[str]] = defaultdict(set)
        self._no_class_aliases: Dict[str, str] = {}
        self._no_class_unknown_words: set[str] = set()
        self._passive_words: set[str] = set()
        self._term_candidates: Dict[str, List[Dict[str, Any]]] = {}
        self._max_term_len = 1
        self._sentence_patterns: DefaultDict[
            Tuple[Tuple[str, int], ...], CounterType[Tuple[str, ...]]
        ] = defaultdict(Counter)
        self._core_sentence_patterns: DefaultDict[
            Tuple[Tuple[str, int], ...], CounterType[Tuple[str, ...]]
        ] = defaultdict(Counter)
        self._sentence_pattern_examples: Dict[Tuple[str, ...], str] = {}
        self._adverb_position_stats: Dict[str, Dict[str, Any]] = {}
        self._semantic_expansions: List[Dict[str, Any]] = []
        self._semantic_expansion_pairs: set[Tuple[str, str]] = set()
        self._semantic_term_candidates: Dict[str, List[Dict[str, Any]]] = {}
        self._max_semantic_term_len = 1
        self._semantic_dataset_kind = ""
        self._use_semantic_expansions = False
        self._similarity_matcher = (
            self._create_similarity_matcher()
            if self._enable_fallback_matching else None
        )
        self._similarity_index_built = False
        self._similarity_index_uses_expansions = False
        self._jieba: Any = None
        self._load_entries()
        self._load_semantic_expansions()
        self._load_adverb_position_stats()
        self._load_sentence_patterns()
        self._try_load_jieba()

    @staticmethod

    def _create_similarity_matcher() -> Any:
        try:
            from importlib import import_module

            module = import_module("webui_backend.similarity_matcher")
            return module.SimilarityMatcher()
        except Exception:
            logging.getLogger(__name__).info(
                "翻译器语义匹配模块不可用，已使用严格词典匹配模式。",
                exc_info=True,
            )
            return None

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def translate(
        self,
        text: str,
        direction: str = "auto",
        use_semantic_expansions: bool = False,
    ) -> Dict[str, Any]:
        source = str(text or "").strip()
        expansions_enabled = bool(use_semantic_expansions)
        if not source:
            return {
                "ok": False,
                "direction": direction or "auto",
                "source_text": "",
                "result_text": "",
                "tokens": [],
                "stats": {"exact": 0, "approximate": 0, "unknown": 0},
                "semantic_expansions_enabled": expansions_enabled,
                "semantic_expansions_available": bool(self._semantic_term_candidates),
                "semantic_expansion_count": len(self._semantic_term_candidates),
                "message": "请输入要翻译的内容。",
            }

        normalized_direction = self._normalize_direction(direction, source)
        with self._lock:
            self._use_semantic_expansions = expansions_enabled
            if normalized_direction == "alician_to_zh":
                result = self._translate_alician_to_zh(source, normalized_direction)
            else:
                result = self._translate_zh_to_alician(source, normalized_direction)
            result["semantic_expansions_enabled"] = expansions_enabled
            result["semantic_expansions_available"] = bool(self._semantic_term_candidates)
            result["semantic_expansion_count"] = len(self._semantic_term_candidates)
            return result

    def _normalize_direction(self, direction: str, text: str) -> str:
        value = str(direction or "auto").strip()
        if value in {"zh_to_alician", "alician_to_zh"}:
            return value
        return "zh_to_alician" if _CJK_RE.search(text) else "alician_to_zh"

    def _entry_to_token(self, source: str, entry: Dict[str, Any], status: str) -> Dict[str, Any]:
        method = "dictionary_term" if status == "exact" else "meaning_overlap"
        return self._token(
            source=source,
            target=entry["target"],
            status=status,
            method=method,
            confidence=1.0 if status == "exact" else 0.7,
            explanation=entry["explanation"],
            word_class=entry["word_class"],
            count=entry["count"],
            variety=entry["variety"],
            alternatives=[self._alternative(entry, 1.0)],
            note="词典释义直接命中。" if status == "exact" else "",
        )

    def _entry_to_chinese_token(
        self, entry: Dict[str, Any], source: str, status: str, method: str,
    ) -> Dict[str, Any]:
        surface = self._clean_surface_gloss(entry["explanation"])
        unresolved = not surface
        return self._token(
            source=source,
            target=surface or f"〔{source}〕",
            status="unknown" if unresolved else status,
            method="unresolved_dictionary_gloss" if unresolved else method,
            confidence=0.0 if unresolved else (1.0 if status == "exact" else 0.7),
            explanation=entry["explanation"],
            word_class=entry["word_class"],
            count=entry["count"],
            variety=entry["variety"],
            alternatives=[self._alternative(entry, 1.0)],
            note=(
                "词典仅有未知占位或未绑定句式，未把它计作精确译文。"
                if unresolved
                else "词典词条命中。" if status == "exact" else ""
            ),
        )

    @staticmethod
    def _clean_surface_gloss(value: Any) -> str:
        """Keep lexical meaning while removing dictionary/editorial labels.

        The original explanation remains on the token for inspection.  Only
        the surface target is normalized, so labels such as ``(pl.)`` and
        ``(后加名词)`` cannot appear as if they were translation text.
        """
        surface = str(value or "").strip()
        editorial = re.compile(
            r"^(?:\?+|pl\.?|程度|位置|祈使语气|作主语|与动词并列|"
            r"后加名词|贱称|敬称|也可.*|不与.*|疑为.*|好像是.*|表厌恶)$",
            flags=re.IGNORECASE,
        )
        inline_supplements = {"事物", "故事", "手", "目光", "我", "声音", "衣服"}

        def replace_parenthetical(match: re.Match[str]) -> str:
            content = str(match.group(1) or "").strip()
            if editorial.fullmatch(content):
                return ""
            # Leading semantic supplements belong to the gloss; a small
            # whitelist also preserves verb arguments such as 拍(手).  Other
            # trailing parentheses are alternative names or editor notes.
            if match.start() == 0 or content in inline_supplements:
                return content
            return ""

        previous = None
        while previous != surface:
            previous = surface
            surface = re.sub(r"[（(]([^（）()]*)[）)]", replace_parenthetical, surface)
        surface = re.sub(r"\s+", "", surface).strip()
        if re.search(r"(?:\.{2,}|…+)", surface):
            # Unbound dictionary slots must never leak literally.  Attested
            # templates are handled explicitly by the parser; unsupported
            # ones remain visibly unresolved instead of emitting “……”.
            return ""
        if re.match(
            r"^(?:引导|提示一个动作|用于(?:过去|完成)|常置于|表示施事者|"
            r"(?:用)?在动词后|动词前表|助动词|语气词|后缀|与动词构成|同[A-Za-z])",
            surface,
            flags=re.IGNORECASE,
        ):
            return ""
        return surface

    def _token(
        self,
        source: str,
        target: str,
        status: str,
        method: str,
        confidence: float,
        explanation: str = "",
        word_class: str = "",
        count: int = 0,
        variety: int = 0,
        alternatives: Optional[List[Dict[str, Any]]] = None,
        note: str = "",
    ) -> Dict[str, Any]:
        return {
            "source": source,
            "target": target,
            "status": status,
            "method": method,
            "confidence": round(float(confidence), 4),
            "explanation": explanation,
            "word_class": word_class,
            "count": int(count),
            "variety": int(variety),
            "alternatives": alternatives or [],
            "note": note,
        }

    def _punct_token(self, source: str) -> Dict[str, Any]:
        return self._token(source, source, "punct", "punct", 1.0)

    def _alternative(self, entry: Dict[str, Any], score: float) -> Dict[str, Any]:
        return {
            "target": entry["target"],
            "explanation": entry["explanation"],
            "word_class": entry["word_class"],
            "score": round(float(score), 4),
        }

    def _compose_alician_result(self, tokens: List[Dict[str, Any]]) -> str:
        out: List[str] = []
        tight_after_opening = False
        opening_punctuation = set("（([《【〈“‘")
        for token in tokens:
            if token.get("omit_from_result"):
                continue
            status = token.get("status")
            target = str(token.get("resolved_target") or token.get("target") or "")
            if not target:
                continue
            if status == "space":
                if out and out[-1] not in {" ", "\n"}:
                    out.append(" ")
                continue
            if status == "punct":
                while out and out[-1] == " ":
                    out.pop()
                out.append(target)
                tight_after_opening = target[-1:] in opening_punctuation
                if not tight_after_opening:
                    out.append(" ")
                continue
            if out and out[-1] not in {" ", "\n"} and not tight_after_opening:
                out.append(" ")
            out.append(target)
            tight_after_opening = False
        return "".join(out).strip()

    @staticmethod

    def _clean_sentence_template(explanation: str) -> str:
        template = str(explanation or "").strip()
        template = re.sub(r"^[（(][^）)]*[）)]", "", template).strip()
        template = re.sub(r"[（(]\?+[）)]", "", template)
        return template

    def _template_argument_target(
        self, token: Dict[str, Any], template: str,
    ) -> str:
        if token.get("method") == "grammar_function":
            return str(token.get("resolved_target") or token.get("target") or "")
        source = str(token.get("source") or "")
        candidates = self._word_by_lower.get(source.lower()) or []
        if not candidates:
            return str(token.get("target") or "")
        if (template.startswith("一") and "就" in template) or template.startswith(("来", "请")):
            preferred_families = {"v", "adj", "adv"}
        else:
            preferred_families = {"n", "pron", "num"}
        preferred = [
            entry for entry in candidates
            if self._pos_family(entry.get("word_class", "")) in preferred_families
        ]
        chosen = min(
            preferred or candidates,
            key=lambda entry: (entry.get("sense_order", 1), -entry.get("count", 0)),
        )
        surface = self._clean_surface_gloss(chosen["explanation"])
        token["template_resolved_target"] = surface
        token["template_resolved_class"] = chosen["word_class"]
        return str(surface or token.get("target") or "")

    def _compose_chinese_result(
        self, tokens: List[Dict[str, Any]], resolve_templates: bool = False,
    ) -> str:
        out: List[str] = []
        consumed = set()
        for index, token in enumerate(tokens):
            if index in consumed:
                continue
            if token.get("omit_from_result"):
                continue
            status = token.get("status")
            target = str(token.get("resolved_target") or token.get("target") or "")
            if status == "space":
                continue
            if (
                resolve_templates
                and token.get("allow_template_resolution")
                and status not in {"space", "punct"}
            ):
                explanation = str(token.get("explanation") or "")
                arity = self._template_arity(explanation)
                if arity:
                    argument_indexes: List[int] = []
                    for next_index in range(index + 1, len(tokens)):
                        next_status = tokens[next_index].get("status")
                        if next_status == "punct":
                            break
                        if (
                            next_status == "space"
                            or next_index in consumed
                            or tokens[next_index].get("omit_from_result")
                        ):
                            continue
                        argument_indexes.append(next_index)
                        if len(argument_indexes) >= arity:
                            break
                    if len(argument_indexes) == arity:
                        template = self._clean_sentence_template(explanation)
                        arguments = [
                            self._template_argument_target(tokens[arg], template)
                            for arg in argument_indexes
                        ]
                        iterator = iter(arguments)
                        target = _TEMPLATE_SLOT_RE.sub(lambda _: next(iterator), template)
                        consumed.update(argument_indexes)
                        token["resolved_target"] = target
                        token["template_arguments"] = arguments
                        token["note"] = f"已按词典句式填充 {arity} 个论元并调整中文语序。"
                        token["method"] = "sentence_template"
                    else:
                        template = self._clean_sentence_template(explanation)
                        target = _TEMPLATE_SLOT_RE.sub("", template)
                        token["note"] = f"该句式需要 {arity} 个论元，当前输入不完整。"
                        token["method"] = "sentence_template_incomplete"
            # A result/inference or contrastive connective opening a new
            # clause mid-sentence is separated by a comma in attested
            # references (e.g. “…，所以…”, “…，但…”); sentence-initial uses
            # stay bare.
            if (
                target
                and str(token.get("source") or "").casefold() in {"elize", "gout"}
                and out
                and out[-1]
                and out[-1][-1] not in "，。！？；：、…—,.!?;:(（[\"'“‘「『【《"
            ):
                out.append("，")
            out.append(target)
            # A postposed frame particle (Chinese 连 … 都) travels with the
            # token it follows, so reordering cannot separate the pair.
            trailing = str(token.get("trailing_particle") or "")
            if trailing:
                out.append(trailing)
        return "".join(out).strip()

    def _stats(self, tokens: List[Dict[str, Any]]) -> Dict[str, int]:
        exact = approximate = unknown = 0
        for token in tokens:
            status = token.get("status")
            if status == "exact":
                exact += 1
            elif status == "approximate":
                approximate += 1
            elif status == "unknown":
                unknown += 1
        return {"exact": exact, "approximate": approximate, "unknown": unknown}

    def _message(self, stats: Dict[str, int]) -> str:
        if stats.get("unknown"):
            return "翻译完成，但仍有词未解决。"
        if stats.get("approximate"):
            return "翻译完成，其中部分词使用了近似匹配。"
        return "翻译完成。"
