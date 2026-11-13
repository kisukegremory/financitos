"""Publicação: do estúdio para o catálogo que o app de consumo lê.

O contrato é `catalog.json` + `<slug>/audio.{ogg,m4a}`, com caminhos relativos ao catálogo.
Hoje fica em disco (data/medichan/public/); trocar por bucket/CDN é trocar o `Storage`.
"""

import re
import shutil
import sqlite3
import tempfile
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from home.apps.medichan import db, render
from home.apps.medichan.models import Catalog, PublishedItem, PublishedRow, PublishIn

CATALOG = "catalog.json"


class Storage(Protocol):
    def put_dir(self, prefix: str, src: Path) -> None: ...
    def put_text(self, key: str, text: str) -> None: ...
    def remove(self, prefix: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def put_dir(self, prefix: str, src: Path) -> None:
        dest = self.root / prefix
        shutil.rmtree(dest, ignore_errors=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)

    def put_text(self, key: str, text: str) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(text)
        tmp.replace(path)  # atômico: o app nunca lê um catálogo pela metade

    def remove(self, prefix: str) -> None:
        shutil.rmtree(self.root / prefix, ignore_errors=True)


class PublishError(ValueError):
    pass


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug if len(slug) <= 40 else slug[:40].rsplit("-", 1)[0]


def publish(
    conn: sqlite3.Connection, root: Path, storage: Storage, meditation_id: int, req: PublishIn
) -> PublishedRow:
    """Renderiza o áudio final, grava no storage e atualiza o catálogo."""
    found = db.source(conn, meditation_id)
    meditation = db.get(conn, meditation_id)
    if found is None or meditation is None:
        raise LookupError(f"meditação {meditation_id} não encontrada")
    folder, segments = found
    bed = None
    if req.track_id is not None:
        track = db.get_track(conn, req.track_id)
        bed = root / "music" / f"{req.track_id}.mp3"
        if track is None or track.status != "ready" or not bed.is_file():
            raise PublishError(f"música {req.track_id} não está pronta")
    parts = [
        render.Part(
            kind=s["kind"],
            file=root / folder / s["file"] if s.get("file") else None,
            seconds=s.get("seconds") or 0,
        )
        for s in segments
    ]
    title = (req.title or "").strip() or meditation.title
    slug = req.slug or slugify(title) or f"meditacao-{meditation_id}"
    with tempfile.TemporaryDirectory() as tmp:
        duration = render.render(parts, Path(tmp), bed)
        storage.put_dir(slug, Path(tmp))
    row = db.save_published(
        conn,
        slug=slug,
        meditation_id=meditation_id,
        track_id=req.track_id,
        title=title,
        summary=req.summary.strip(),
        tags=[t.strip().lower() for t in req.tags if t.strip()],
        access=req.access,
        duration_s=duration,
    )
    rebuild_catalog(conn, storage)
    return row


def unpublish(conn: sqlite3.Connection, storage: Storage, slug: str) -> bool:
    if not db.delete_published(conn, slug):
        return False
    storage.remove(slug)
    rebuild_catalog(conn, storage)
    return True


def catalog(conn: sqlite3.Connection) -> Catalog:
    items = [PublishedItem.model_validate(r.model_dump()) for r in db.list_published(conn)]
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return Catalog(updated_at=now, items=items)


def rebuild_catalog(conn: sqlite3.Connection, storage: Storage) -> None:
    storage.put_text(CATALOG, catalog(conn).model_dump_json(indent=2) + "\n")
