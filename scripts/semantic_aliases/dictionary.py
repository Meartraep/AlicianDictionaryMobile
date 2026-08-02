from __future__ import annotations

from .shared import *

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
