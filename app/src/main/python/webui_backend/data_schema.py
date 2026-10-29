"""Declarative table registry and write rules for the unified data layer.

The database has 30+ tables, but only a small curated subset may be edited from
the app.  This module is the single source of truth for:

* which tables exist for the UI, and how they are grouped (core / lyric /
  semantic / system / legacy);
* which tables are writable at all;
* per-table write rules: required fields, case-insensitive uniqueness,
  maximum lengths, child tables that must be removed with the parent, and the
  fields used for a compact UI summary.

Column *types* are read from the live database (``PRAGMA table_info``) because
the shipped schema is the authority; the rules here are business rules that the
schema itself does not (and cannot) express.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

GROUP_CORE = "core"
GROUP_LYRIC = "lyric"
GROUP_SEMANTIC = "semantic"
GROUP_SYSTEM = "system"
GROUP_LEGACY = "legacy"

GROUP_ORDER: Tuple[str, ...] = (
    GROUP_CORE,
    GROUP_LYRIC,
    GROUP_SEMANTIC,
    GROUP_SYSTEM,
    GROUP_LEGACY,
)

GROUPS: Dict[str, Dict[str, str]] = {
    GROUP_CORE: {"title": "核心词典", "note": "词头、义项与短语，可编辑"},
    GROUP_LYRIC: {"title": "歌词与译文", "note": "歌曲、逐句对齐与官方译文，可编辑"},
    GROUP_SEMANTIC: {"title": "语义（只读）", "note": "由工具生成的相似度与位置统计"},
    GROUP_SYSTEM: {"title": "系统（只读）", "note": "版本标记与本地修改台账"},
    GROUP_LEGACY: {"title": "遗留表（只读）", "note": "导入期存档与旧版派生表"},
}

#: Chinese labels for the columns an editor can show.  Unknown columns fall back to
#: their raw name, so a future schema stays usable without touching this table.
FIELD_LABELS: Dict[str, str] = {
    "id": "编号",
    "words": "词形",
    "display_explanation": "展示释义",
    "display_class": "词性（展示）",
    "headword_id": "词头编号",
    "explanation": "释义",
    "class": "词性",
    "sense_order": "义项序号",
    "count": "词频",
    "variety": "泛度",
    "time": "时间",
    "english_gloss": "英文",
    "japanese_gloss": "日文",
    "PHRASE": "词组",
    "title": "歌名",
    "Album": "专辑",
    "lyric": "歌词",
    "song_id": "歌曲编号",
    "song_title": "歌曲",
    "alician_sentence": "爱丽丝语句",
    "chinese_translation": "中文",
    "alignment_status": "对齐状态",
    "match_score": "匹配分",
    "match_method": "匹配方式",
    "source_file": "来源文件",
    "notes": "备注",
    "song_sentence_order": "句序",
    "txt_sentence_order": "原句序",
    "txt_alician_sentence": "文本爱丽丝语",
    "word_glosses_text": "词注",
    "word_glosses_json": "词注（JSON）",
    "sentence": "原句",
    "english": "英文",
    "japanese": "日文",
    "korean": "韩文",
    "sense_id": "义项编号",
    "alias": "别名",
    "similarity": "相似度",
    "rank": "排名",
    "key": "键",
    "value": "值",
    "db_version": "版本",
    "published_at": "发布时间",
    "format": "格式",
}

#: Columns whose long values should be edited in a multi-line field.
MULTILINE_FIELDS = frozenset(
    {
        "lyric",
        "explanation",
        "display_explanation",
        "chinese_translation",
        "alician_sentence",
        "txt_alician_sentence",
        "word_glosses_text",
        "word_glosses_json",
        "sentence",
        "english",
        "japanese",
        "korean",
        "notes",
    }
)


def field_label(name: str) -> str:
    """Chinese label for a column, falling back to the raw column name."""
    return FIELD_LABELS.get(str(name), str(name))



@dataclass(frozen=True)
class TableSpec:
    """Write rules for one table."""

    name: str
    group: str
    label: str
    editable: bool = False
    #: columns that must be non-empty when a row is created
    required: Tuple[str, ...] = ()
    #: groups of columns that must be case-insensitively unique
    unique: Tuple[Tuple[str, ...], ...] = ()
    #: column -> maximum length (characters)
    max_length: Tuple[Tuple[str, int], ...] = ()
    #: (child_table, child_foreign_key_column, parent_column) removed with the parent
    cascade: Tuple[Tuple[str, str, str], ...] = ()
    #: (column, parent_table, parent_column) that must resolve to an existing row.
    #: Declared here because some historical tables never got a real FOREIGN KEY.
    references: Tuple[Tuple[str, str, str], ...] = ()
    #: columns shown in the compact UI summary
    display: Tuple[str, ...] = ()
    #: free-form note shown in the UI
    note: str = ""

    @property
    def key_column(self) -> str:
        """Primary key column used by the generic row editor (``id`` or ``rowid``)."""
        return "id"

    def max_length_of(self, column: str) -> int:
        for name, limit in self.max_length:
            if name == column:
                return int(limit)
        return 0


def _spec(
    name: str,
    group: str,
    label: str,
    *,
    editable: bool = False,
    required: Tuple[str, ...] = (),
    unique: Tuple[Tuple[str, ...], ...] = (),
    max_length: Tuple[Tuple[str, int], ...] = (),
    cascade: Tuple[Tuple[str, str, str], ...] = (),
    references: Tuple[Tuple[str, str, str], ...] = (),
    display: Tuple[str, ...] = (),
    note: str = "",
) -> TableSpec:
    return TableSpec(
        name=name,
        group=group,
        label=label,
        editable=editable,
        required=required,
        unique=unique,
        max_length=max_length,
        cascade=cascade,
        references=references,
        display=display,
        note=note,
    )


# ``dictionary_headwords`` is the row every editing surface ultimately targets:
# it owns the curated spelling + summary, while ``dictionary`` holds one row per
# sense.  Deleting a headword must take its senses with it (the schema already
# declares ON DELETE CASCADE; the cascade entry also keeps behaviour identical
# when foreign keys are unavailable, e.g. on an old database copy).
_HEADWORD_CASCADE: Tuple[Tuple[str, str, str], ...] = (
    ("dictionary", "headword_id", "id"),
)

# ``songs`` has no foreign keys to its aligned/translated rows, so deleting a
# song would otherwise leave orphans that the lyric viewer still tries to read.
_SONG_CASCADE: Tuple[Tuple[str, str, str], ...] = (
    ("sentence_alignments", "song_id", "id"),
    ("song_translations", "song_title", "title"),
)

TABLES: Dict[str, TableSpec] = {
    # ---- core -----------------------------------------------------------
    "dictionary_headwords": _spec(
        "dictionary_headwords",
        GROUP_CORE,
        "词头",
        editable=True,
        required=("words",),
        unique=(("words",),),
        max_length=(("words", 64), ("display_explanation", 500), ("display_class", 32)),
        cascade=_HEADWORD_CASCADE,
        display=("words", "display_explanation"),
        note="删除词头会同时删除其全部义项",
    ),
    "dictionary": _spec(
        "dictionary",
        GROUP_CORE,
        "义项",
        editable=True,
        required=("headword_id", "words", "explanation", "sense_order"),
        max_length=(("words", 64), ("explanation", 500)),
        references=(("headword_id", "dictionary_headwords", "id"),),
        display=("words", "explanation"),
        note="每条记录是一个义项，headword_id 必须指向已存在的词头",
    ),
    "phrase": _spec(
        "phrase",
        GROUP_CORE,
        "词组",
        editable=True,
        required=("PHRASE",),
        unique=(("PHRASE",),),
        max_length=(("PHRASE", 200), ("explanation", 500)),
        display=("PHRASE", "explanation"),
    ),
    # ---- lyric ----------------------------------------------------------
    "songs": _spec(
        "songs",
        GROUP_LYRIC,
        "歌曲",
        editable=True,
        required=("title",),
        unique=(("title",),),
        max_length=(("title", 200),),
        cascade=_SONG_CASCADE,
        display=("title", "Album"),
        note="删除歌曲会同时删除其逐句对齐与官方译文",
    ),
    "sentence_alignments": _spec(
        "sentence_alignments",
        GROUP_LYRIC,
        "逐句对齐",
        editable=True,
        required=("song_id", "song_title", "alician_sentence"),
        max_length=(("alician_sentence", 2000), ("chinese_translation", 2000)),
        references=(
            ("song_id", "songs", "id"),
            ("song_title", "songs", "title"),
        ),
        display=("alician_sentence", "chinese_translation"),
        note="song_id 必须指向已存在的歌曲",
    ),
    "song_translations": _spec(
        "song_translations",
        GROUP_LYRIC,
        "官方译文",
        editable=True,
        required=("song_title", "sentence"),
        unique=(("song_title", "sentence"),),
        max_length=(("song_title", 200), ("sentence", 2000), ("english", 2000), ("japanese", 2000), ("korean", 2000)),
        references=(("song_title", "songs", "title"),),
        display=("song_title", "sentence"),
        note="song_title 必须指向已存在的歌曲",
    ),
    # ---- semantic (generated, read-only) --------------------------------
    "dictionary_semantic_aliases": _spec(
        "dictionary_semantic_aliases",
        GROUP_SEMANTIC,
        "语义别名",
        note="由离线模型生成，App 内只读",
    ),
    "semantic_alias_metadata": _spec(
        "semantic_alias_metadata", GROUP_SEMANTIC, "语义元数据", note="由离线模型生成，App 内只读"
    ),
    "adverb_position_stats": _spec(
        "adverb_position_stats", GROUP_SEMANTIC, "副词位置统计", note="离线统计产物，App 内只读"
    ),
    # ---- system (read-only) ---------------------------------------------
    "database_metadata": _spec(
        "database_metadata",
        GROUP_SYSTEM,
        "数据库元数据",
        note="包含发布版本标记，编辑会破坏更新链路，因此只读",
    ),
    "Signature": _spec("Signature", GROUP_SYSTEM, "署名", note="数据来源署名"),
    "local_edits": _spec(
        "local_edits", GROUP_SYSTEM, "本地修改台账", note="由 App 自动记录，只读"
    ),
    # ---- legacy (read-only) ---------------------------------------------
    "raw": _spec("raw", GROUP_LEGACY, "原始导入存档", note="导入期原始歌词，统计脚本的历史输入"),
    "Album1": _spec("Album1", GROUP_LEGACY, "旧专辑 1"),
    "Album2": _spec("Album2", GROUP_LEGACY, "旧专辑 2"),
    "Album3": _spec("Album3", GROUP_LEGACY, "旧专辑 3"),
    "Single": _spec("Single", GROUP_LEGACY, "旧单曲表"),
    "All_words": _spec("All_words", GROUP_LEGACY, "旧全词表"),
    "Unknown": _spec("Unknown", GROUP_LEGACY, "旧未分类词表"),
    "no_class": _spec("no_class", GROUP_LEGACY, "无词性词表", note="翻译器仍会读取"),
    "test": _spec("test", GROUP_LEGACY, "测试表", note="历史遗留，可随下次数据库版本删除"),
    "n.": _spec("n.", GROUP_LEGACY, "名词表"),
    "v.": _spec("v.", GROUP_LEGACY, "动词表"),
    "adj.": _spec("adj.", GROUP_LEGACY, "形容词表"),
    "adv.": _spec("adv.", GROUP_LEGACY, "副词表"),
    "art.": _spec("art.", GROUP_LEGACY, "冠词表"),
    "conj.": _spec("conj.", GROUP_LEGACY, "连词表"),
    "interj.": _spec("interj.", GROUP_LEGACY, "感叹词表"),
    "num.": _spec("num.", GROUP_LEGACY, "数词表"),
    "prep.": _spec("prep.", GROUP_LEGACY, "介词表"),
    "pron.": _spec("pron.", GROUP_LEGACY, "代词表"),
    "vi.": _spec("vi.", GROUP_LEGACY, "不及物动词表"),
    "vt.": _spec("vt.", GROUP_LEGACY, "及物动词表"),
}


def generic_spec(table: str) -> TableSpec:
    """Read-only spec for a table the app does not know about (future schema)."""
    return TableSpec(
        name=str(table),
        group=GROUP_LEGACY,
        label=str(table),
        editable=False,
        note="未登记的表，默认只读",
    )


def spec_for(table: str) -> TableSpec:
    """Return the registered spec, or a read-only generic one."""
    return TABLES.get(str(table or ""), generic_spec(str(table or "")))


def is_editable(table: str) -> bool:
    return spec_for(table).editable


def editable_table_names() -> List[str]:
    return [name for name, spec in TABLES.items() if spec.editable]


def grouped_tables() -> List[Dict[str, object]]:
    """Groups (with labels) for the data-browser UI, in stable order."""
    grouped: List[Dict[str, object]] = []
    for group in GROUP_ORDER:
        entry = GROUPS[group]
        tables = [
            {
                "name": spec.name,
                "label": spec.label,
                "editable": spec.editable,
                "note": spec.note,
                "display": list(spec.display),
            }
            for spec in TABLES.values()
            if spec.group == group
        ]
        grouped.append(
            {
                "group": group,
                "title": entry["title"],
                "note": entry["note"],
                "tables": sorted(tables, key=lambda item: str(item["name"])),
            }
        )
    return grouped
