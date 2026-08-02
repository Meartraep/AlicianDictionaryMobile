from __future__ import annotations

from .shared import *

from .dictionary import dictionary_fingerprint

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
