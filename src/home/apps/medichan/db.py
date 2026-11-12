import json
import sqlite3

from home.apps.medichan.models import Meditation, Script, SegmentOut
from home.apps.medichan.tts import Synthesis
from home.core import db as core_db

SCHEMA = """
-- Meditações geradas: o roteiro fica aqui; os áudios em data/medichan/<folder>/
CREATE TABLE IF NOT EXISTS medichan_meditations (
    id         INTEGER PRIMARY KEY,
    feeling    TEXT NOT NULL,
    voice      TEXT NOT NULL,
    title      TEXT NOT NULL,
    segments   TEXT NOT NULL,  -- JSON: [{kind, text, seconds, file}]
    folder     TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""


# Colunas adicionadas depois da criação da tabela: (nome, definição)
MIGRATIONS = [("chars", "INTEGER"), ("cost_usd", "REAL")]


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    core_db.add_columns(conn, "medichan_meditations", MIGRATIONS)


core_db.register(init)


def audio_url(id: int, index: int) -> str:
    return f"/api/medichan/meditations/{id}/audio/{index}"


def _to_meditation(row: sqlite3.Row) -> Meditation:
    segments = [
        SegmentOut(
            kind=s["kind"],
            text=s.get("text"),
            seconds=s.get("seconds"),
            audio=audio_url(row["id"], i) if s.get("file") else None,
        )
        for i, s in enumerate(json.loads(row["segments"]))
    ]
    return Meditation(
        id=row["id"],
        feeling=row["feeling"],
        voice=row["voice"],
        title=row["title"],
        segments=segments,
        chars=row["chars"],
        cost_usd=row["cost_usd"],
        created_at=row["created_at"],
    )


def create(
    conn: sqlite3.Connection,
    feeling: str,
    voice: str,
    script: Script,
    synthesis: Synthesis,
    folder: str,
) -> Meditation:
    segments = [
        {**s.model_dump(), "file": f} for s, f in zip(script.segments, synthesis.files, strict=True)
    ]
    with conn:
        cur = conn.execute(
            "INSERT INTO medichan_meditations"
            " (feeling, voice, title, segments, folder, chars, cost_usd)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                feeling,
                voice,
                script.title,
                json.dumps(segments, ensure_ascii=False),
                folder,
                synthesis.chars,
                synthesis.cost_usd,
            ),
        )
    return get(conn, cur.lastrowid)  # type: ignore[arg-type, return-value]


def get(conn: sqlite3.Connection, id: int) -> Meditation | None:
    row = conn.execute("SELECT * FROM medichan_meditations WHERE id = ?", (id,)).fetchone()
    return _to_meditation(row) if row else None


def list_all(conn: sqlite3.Connection, limit: int = 50) -> list[Meditation]:
    rows = conn.execute("SELECT * FROM medichan_meditations ORDER BY id DESC LIMIT ?", (limit,))
    return [_to_meditation(r) for r in rows.fetchall()]


def audio_file(conn: sqlite3.Connection, id: int, index: int) -> tuple[str, str] | None:
    """(pasta, arquivo) do áudio do trecho `index`, se existir."""
    row = conn.execute(
        "SELECT folder, segments FROM medichan_meditations WHERE id = ?", (id,)
    ).fetchone()
    if not row:
        return None
    segments = json.loads(row["segments"])
    if not 0 <= index < len(segments) or not segments[index].get("file"):
        return None
    return row["folder"], segments[index]["file"]


def delete(conn: sqlite3.Connection, id: int) -> str | None:
    """Apaga e devolve a pasta dos áudios (para remover do disco)."""
    row = conn.execute("SELECT folder FROM medichan_meditations WHERE id = ?", (id,)).fetchone()
    if not row:
        return None
    with conn:
        conn.execute("DELETE FROM medichan_meditations WHERE id = ?", (id,))
    return row["folder"]
