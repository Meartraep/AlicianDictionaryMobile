from .shared import *
from .dictionary import (
    build_candidates,
    candidate_families,
    candidate_rejection_reason,
    chinese_numeric_word,
    dictionary_fingerprint,
    extract_anchor_pieces,
    extract_runtime_terms,
    has_semantic_parenthetical,
    infer_reviewed_pos,
    load_dictionary_data,
    normalize_anchor_piece,
    normalize_dictionary_pos,
    normalize_runtime_term,
    open_read_only_database,
    parse_jieba_entries,
    read_jieba_dictionary,
    strip_parenthetical_content,
    table_exists,
)
from .scoring import (
    best_and_margin,
    encode_texts,
    lexical_negation,
    load_sentence_model,
    local_model_revision,
    polarity_compatible,
    required_automatic_similarity,
    resolve_reviewed_targets,
    score_candidates,
    select_aliases,
    sentiment_polarity,
)
from .storage import current_dictionary_fingerprint, write_database
from .cli import build_parser, main, validate_args


__all__ = [name for name in globals() if not name.startswith("_")]
