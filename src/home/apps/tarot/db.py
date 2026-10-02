import json
import sqlite3

from home.apps.tarot import cards
from home.apps.tarot.models import (
    Draw,
    Phrase,
    PhraseIn,
    PhraseUpdate,
    Reading,
    Suggestion,
    Thinker,
)
from home.core import db as core_db

SCHEMA = """
CREATE TABLE IF NOT EXISTS tarot_phrases (
    id         INTEGER PRIMARY KEY,
    text       TEXT    NOT NULL,
    author     TEXT,
    origin     TEXT    NOT NULL DEFAULT 'manual',  -- manual | ai
    prompt     TEXT,                               -- dica usada na geração por IA
    favorite   INTEGER NOT NULL DEFAULT 0,
    note       TEXT,
    created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Leituras do "como estou hoje": sentimento -> frase + carta
CREATE TABLE IF NOT EXISTS tarot_readings (
    id             INTEGER PRIMARY KEY,
    feeling        TEXT    NOT NULL,
    phrase_id      INTEGER REFERENCES tarot_phrases (id) ON DELETE SET NULL,
    generated_text TEXT,
    why            TEXT    NOT NULL,
    card_id        TEXT    NOT NULL,
    reversed       INTEGER NOT NULL,
    card_reading   TEXT    NOT NULL,
    created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS tarot_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_BASE_PROMPT = """Você cria frases curtas e marcantes, no estilo de aforismos: \
diretas, poéticas sem serem piegas, que fazem a pessoa parar e pensar. \
Escreva em português do Brasil. Evite clichês de autoajuda."""


# Colunas adicionadas depois da criação da tabela: (nome, definição)
PHRASE_MIGRATIONS = [("source", "TEXT")]
READING_MIGRATIONS = [("thinker", "TEXT"), ("quotes", "TEXT")]  # JSON


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    core_db.add_columns(conn, "tarot_phrases", PHRASE_MIGRATIONS)
    core_db.add_columns(conn, "tarot_readings", READING_MIGRATIONS)


core_db.register(init)


def _to_phrase(row: sqlite3.Row) -> Phrase:
    return Phrase(**{**dict(row), "favorite": bool(row["favorite"])})


def list_phrases(
    conn: sqlite3.Connection, q: str | None = None, favorite: bool | None = None
) -> list[Phrase]:
    clauses, params = [], []
    if q:
        clauses.append("(text LIKE ? OR author LIKE ? OR source LIKE ?)")
        params += [f"%{q}%"] * 3
    if favorite is not None:
        clauses.append("favorite = ?")
        params.append(int(favorite))
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM tarot_phrases{where} ORDER BY id DESC", params)
    return [_to_phrase(r) for r in rows]


def get_phrase(conn: sqlite3.Connection, id: int) -> Phrase | None:
    row = conn.execute("SELECT * FROM tarot_phrases WHERE id = ?", (id,)).fetchone()
    return _to_phrase(row) if row else None


def create_phrase(conn: sqlite3.Connection, p: PhraseIn) -> Phrase:
    with conn:
        cur = conn.execute(
            "INSERT INTO tarot_phrases (text, author, source, origin, prompt, favorite, note)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                p.text.strip(),
                p.author or None,
                p.source or None,
                p.origin.value,
                p.prompt,
                int(p.favorite),
                p.note,
            ),
        )
    return get_phrase(conn, cur.lastrowid)  # type: ignore[arg-type, return-value]


def update_phrase(conn: sqlite3.Connection, id: int, changes: PhraseUpdate) -> Phrase | None:
    patch = changes.model_dump(exclude_unset=True)
    if "favorite" in patch:
        patch["favorite"] = int(bool(patch["favorite"]))
    for key in ("author", "source", "note"):  # "" apaga
        if key in patch and not patch[key]:
            patch[key] = None
    if patch.get("text") is None:
        patch.pop("text", None)
    if patch:
        sets = ", ".join(f"{k} = ?" for k in patch)
        with conn:
            conn.execute(f"UPDATE tarot_phrases SET {sets} WHERE id = ?", (*patch.values(), id))
    return get_phrase(conn, id)


def delete_phrase(conn: sqlite3.Connection, id: int) -> bool:
    with conn:
        # sem PRAGMA foreign_keys, o ON DELETE SET NULL não dispara sozinho
        conn.execute("UPDATE tarot_readings SET phrase_id = NULL WHERE phrase_id = ?", (id,))
        return conn.execute("DELETE FROM tarot_phrases WHERE id = ?", (id,)).rowcount > 0


def get_base_prompt(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM tarot_settings WHERE key = 'base_prompt'").fetchone()
    return row["value"] if row else DEFAULT_BASE_PROMPT


def set_base_prompt(conn: sqlite3.Connection, value: str) -> str:
    with conn:
        conn.execute(
            "INSERT INTO tarot_settings (key, value) VALUES ('base_prompt', ?)"
            " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (value,),
        )
    return value


# --- leituras ---


def create_reading(
    conn: sqlite3.Connection,
    feeling: str,
    phrase_id: int | None,
    generated_text: str | None,
    why: str,
    draw: Draw,
    card_reading: str,
    thinker: Thinker | None = None,
    quotes: list[Suggestion] | None = None,
) -> Reading:
    with conn:
        cur = conn.execute(
            "INSERT INTO tarot_readings (feeling, phrase_id, generated_text, why, card_id,"
            " reversed, card_reading, thinker, quotes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                feeling,
                phrase_id,
                generated_text,
                why,
                draw.card.id,
                int(draw.reversed),
                card_reading,
                thinker.model_dump_json() if thinker else None,
                json.dumps([q.model_dump() for q in quotes or []], ensure_ascii=False),
            ),
        )
    return get_reading(conn, cur.lastrowid)  # type: ignore[arg-type, return-value]


def _to_reading(conn: sqlite3.Connection, row: sqlite3.Row) -> Reading:
    card = cards.get_card(row["card_id"])
    return Reading(
        id=row["id"],
        feeling=row["feeling"],
        phrase=get_phrase(conn, row["phrase_id"]) if row["phrase_id"] else None,
        generated_text=row["generated_text"],
        why=row["why"],
        draw=Draw(card=card, reversed=bool(row["reversed"])),  # type: ignore[arg-type]
        card_reading=row["card_reading"],
        thinker=Thinker.model_validate_json(row["thinker"]) if row["thinker"] else None,
        quotes=[Suggestion(**q) for q in json.loads(row["quotes"] or "[]")],
        created_at=row["created_at"],
    )


def get_reading(conn: sqlite3.Connection, id: int) -> Reading | None:
    row = conn.execute("SELECT * FROM tarot_readings WHERE id = ?", (id,)).fetchone()
    return _to_reading(conn, row) if row else None


def list_readings(conn: sqlite3.Connection, limit: int = 30) -> list[Reading]:
    rows = conn.execute("SELECT * FROM tarot_readings ORDER BY id DESC LIMIT ?", (limit,))
    return [_to_reading(conn, r) for r in rows.fetchall()]


def delete_reading(conn: sqlite3.Connection, id: int) -> bool:
    with conn:
        return conn.execute("DELETE FROM tarot_readings WHERE id = ?", (id,)).rowcount > 0
