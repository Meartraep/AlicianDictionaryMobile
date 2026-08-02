from __future__ import annotations

from webui_backend.translation_alician import AlicianTranslationMixin
from webui_backend.translation_alician_syntax import AlicianSyntaxMixin
from webui_backend.translation_chinese_grammar import ChineseGrammarMixin
from webui_backend.translation_chinese_lexicon import ChineseLexiconMixin
from webui_backend.translation_common import TranslationCore, _as_int, _default_db_path
from webui_backend.translation_data import TranslationDataMixin


class TranslationService(
    TranslationDataMixin,
    ChineseGrammarMixin,
    ChineseLexiconMixin,
    AlicianTranslationMixin,
    AlicianSyntaxMixin,
    TranslationCore,
):
    """Bidirectional translator with dictionary and corpus-backed grammar."""


__all__ = ["TranslationService"]
