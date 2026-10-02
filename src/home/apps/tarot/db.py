import sqlite3

from home.apps.tarot.models import Phrase, PhraseIn, PhraseUpdate
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

CREATE TABLE IF NOT EXISTS tarot_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_BASE_PROMPT = """Você cria frases curtas e marcantes, no estilo de aforismos: \
diretas, poéticas sem serem piegas, que fazem a pessoa parar e pensar. \
Escreva em português do Brasil. Evite clichês de autoajuda."""


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


core_db.register(init)


def _to_phrase(row: sqlite3.Row) -> Phrase:
    return Phrase(**{**dict(row), "favorite": bool(row["favorite"])})


def list_phrases(
    conn: sqlite3.Connection, q: str | None = None, favorite: bool | None = None
) -> list[Phrase]:
    clauses, params = [], []
    if q:
        clauses.append("(text LIKE ? OR author LIKE ?)")
        params += [f"%{q}%"] * 2
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
            "INSERT INTO tarot_phrases (text, author, origin, prompt, favorite, note)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (p.text.strip(), p.author or None, p.origin.value, p.prompt, int(p.favorite), p.note),
        )
    return get_phrase(conn, cur.lastrowid)  # type: ignore[arg-type, return-value]


def update_phrase(conn: sqlite3.Connection, id: int, changes: PhraseUpdate) -> Phrase | None:
    patch = changes.model_dump(exclude_unset=True)
    if "favorite" in patch:
        patch["favorite"] = int(bool(patch["favorite"]))
    for key in ("author", "note"):  # "" apaga
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
