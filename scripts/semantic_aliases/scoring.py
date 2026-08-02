from __future__ import annotations

from .shared import *

from .dictionary import has_semantic_parenthetical

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
