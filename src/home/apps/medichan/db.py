import json
import sqlite3

from home.apps.medichan.models import (
    AudioFiles,
    Meditation,
    Profile,
    PublishedRow,
    Script,
    SegmentOut,
    Track,
)
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

-- Músicas ambientes (Lyria): geradas em segundo plano; MP3 em data/medichan/music/<id>.mp3
CREATE TABLE IF NOT EXISTS medichan_tracks (
    id         INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    kind       TEXT NOT NULL,              -- clip | pro
    preset     TEXT,
    prompt     TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',  -- pending | ready | error
    error      TEXT,
    seconds    REAL,
    cost_usd   REAL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Publicadas: áudio final mixado em data/medichan/public/<slug>/ e listado no catalog.json
CREATE TABLE IF NOT EXISTS medichan_published (
    slug          TEXT PRIMARY KEY,
    meditation_id INTEGER,  -- origem (pode ter sido apagada; o áudio final segue publicado)
    track_id      INTEGER,
    title         TEXT NOT NULL,
    summary       TEXT NOT NULL DEFAULT '',
    tags          TEXT NOT NULL DEFAULT '[]',  -- JSON
    access        TEXT NOT NULL DEFAULT 'free',  -- free | private
    duration_s    REAL NOT NULL,
    published_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Perfil "sobre mim": uma linha só (id = 1)
CREATE TABLE IF NOT EXISTS medichan_profile (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    about      TEXT NOT NULL DEFAULT '',
    max_hold   INTEGER NOT NULL DEFAULT 3,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
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


def source(conn: sqlite3.Connection, id: int) -> tuple[str, list[dict]] | None:
    """(pasta, trechos crus com `file`) para renderizar a versão final."""
    row = conn.execute(
        "SELECT folder, segments FROM medichan_meditations WHERE id = ?", (id,)
    ).fetchone()
    return (row["folder"], json.loads(row["segments"])) if row else None


def delete(conn: sqlite3.Connection, id: int) -> str | None:
    """Apaga e devolve a pasta dos áudios (para remover do disco)."""
    row = conn.execute("SELECT folder FROM medichan_meditations WHERE id = ?", (id,)).fetchone()
    if not row:
        return None
    with conn:
        conn.execute("DELETE FROM medichan_meditations WHERE id = ?", (id,))
    return row["folder"]


# --- músicas ---


def track_audio_url(id: int) -> str:
    return f"/api/medichan/music/{id}/audio"


def _to_track(row: sqlite3.Row) -> Track:
    data = dict(row)
    return Track(**data, audio=track_audio_url(row["id"]) if row["status"] == "ready" else None)


def create_track(
    conn: sqlite3.Connection, title: str, kind: str, preset: str | None, prompt: str
) -> Track:
    with conn:
        cur = conn.execute(
            "INSERT INTO medichan_tracks (title, kind, preset, prompt) VALUES (?, ?, ?, ?)",
            (title, kind, preset, prompt),
        )
    return get_track(conn, cur.lastrowid)  # type: ignore[arg-type, return-value]


def finish_track(
    conn: sqlite3.Connection,
    id: int,
    *,
    seconds: float | None = None,
    cost_usd: float | None = None,
    error: str | None = None,
) -> None:
    with conn:
        conn.execute(
            "UPDATE medichan_tracks SET status = ?, seconds = ?, cost_usd = ?, error = ?"
            " WHERE id = ?",
            ("error" if error else "ready", seconds, cost_usd, error, id),
        )


def get_track(conn: sqlite3.Connection, id: int) -> Track | None:
    row = conn.execute("SELECT * FROM medichan_tracks WHERE id = ?", (id,)).fetchone()
    return _to_track(row) if row else None


STALE_MINUTES = 10  # pending mais velho que isso: o servidor caiu no meio da composição


def list_tracks(conn: sqlite3.Connection) -> list[Track]:
    with conn:
        conn.execute(
            "UPDATE medichan_tracks SET status = 'error', error = 'interrompida (servidor reiniciou)'"
            " WHERE status = 'pending' AND created_at < strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?)",
            (f"-{STALE_MINUTES} minutes",),
        )
    rows = conn.execute("SELECT * FROM medichan_tracks ORDER BY id DESC")
    return [_to_track(r) for r in rows.fetchall()]


def delete_track(conn: sqlite3.Connection, id: int) -> bool:
    with conn:
        return conn.execute("DELETE FROM medichan_tracks WHERE id = ?", (id,)).rowcount > 0


# --- publicadas ---


def _to_published(row: sqlite3.Row) -> PublishedRow:
    data = dict(row)
    slug = data["slug"]
    return PublishedRow(
        **{**data, "tags": json.loads(data["tags"])},
        audio=AudioFiles(ogg=f"{slug}/audio.ogg", m4a=f"{slug}/audio.m4a"),
    )


def save_published(
    conn: sqlite3.Connection,
    *,
    slug: str,
    meditation_id: int | None,
    track_id: int | None,
    title: str,
    summary: str,
    tags: list[str],
    access: str,
    duration_s: float,
) -> PublishedRow:
    """Cria ou republica (mesmo slug): a data vai para agora."""
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO medichan_published"
            " (slug, meditation_id, track_id, title, summary, tags, access, duration_s)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                slug,
                meditation_id,
                track_id,
                title,
                summary,
                json.dumps(tags, ensure_ascii=False),
                access,
                duration_s,
            ),
        )
    return get_published(conn, slug)  # type: ignore[return-value]


def get_published(conn: sqlite3.Connection, slug: str) -> PublishedRow | None:
    row = conn.execute("SELECT * FROM medichan_published WHERE slug = ?", (slug,)).fetchone()
    return _to_published(row) if row else None


def list_published(conn: sqlite3.Connection) -> list[PublishedRow]:
    rows = conn.execute("SELECT * FROM medichan_published ORDER BY published_at DESC, slug")
    return [_to_published(r) for r in rows.fetchall()]


def delete_published(conn: sqlite3.Connection, slug: str) -> bool:
    with conn:
        return conn.execute("DELETE FROM medichan_published WHERE slug = ?", (slug,)).rowcount > 0


# --- perfil ---


def get_profile(conn: sqlite3.Connection) -> Profile:
    row = conn.execute("SELECT about, max_hold FROM medichan_profile WHERE id = 1").fetchone()
    return Profile(about=row["about"], max_hold=row["max_hold"]) if row else Profile()


def save_profile(conn: sqlite3.Connection, profile: Profile) -> Profile:
    with conn:
        conn.execute(
            "INSERT INTO medichan_profile (id, about, max_hold) VALUES (1, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET about = excluded.about, max_hold = excluded.max_hold,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')",
            (profile.about, profile.max_hold),
        )
    return get_profile(conn)
