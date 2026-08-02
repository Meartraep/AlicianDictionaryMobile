from __future__ import annotations

from .shared import *

from .dictionary import (
    build_candidates,
    load_dictionary_data,
    parse_jieba_entries,
    read_jieba_dictionary,
)
from .scoring import (
    load_sentence_model,
    local_model_revision,
    score_candidates,
    select_aliases,
)
from .storage import write_database

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
