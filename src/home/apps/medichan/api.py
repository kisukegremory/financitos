import shutil
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse

from home.apps.medichan import db, music, tts
from home.apps.medichan.llm import ScriptWriter
from home.apps.medichan.models import (
    Meditation,
    MeditationIn,
    MusicCatalog,
    MusicOption,
    Track,
    TrackIn,
    VoiceInfo,
)
from home.apps.medichan.music import Composer
from home.apps.medichan.tts import Speaker
from home.core import db as core_db
from home.core.config import Settings, get_settings
from home.core.deps import Conn

router = APIRouter(tags=["medichan"])

MEDIA_TYPES = {".mp3": "audio/mpeg", ".wav": "audio/wav"}


def get_writer(settings: Annotated[Settings, Depends(get_settings)]) -> ScriptWriter:
    return ScriptWriter(settings)


def get_speaker(settings: Annotated[Settings, Depends(get_settings)]) -> Speaker:
    return Speaker(settings)


def get_composer(settings: Annotated[Settings, Depends(get_settings)]) -> Composer:
    return Composer(settings)


def audio_root(settings: Annotated[Settings, Depends(get_settings)]) -> Path:
    """Áudios ficam ao lado do banco: data/medichan/."""
    return core_db.path_from_url(settings.database_url).parent / "medichan"


AudioRoot = Annotated[Path, Depends(audio_root)]


def _not_found(id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"meditação {id} não encontrada")


@router.get("/voices")
def list_voices() -> list[VoiceInfo]:
    return tts.voices()


@router.post("/meditations", status_code=status.HTTP_201_CREATED)
def create_meditation(
    req: MeditationIn,
    conn: Conn,
    root: AudioRoot,
    writer: Annotated[ScriptWriter, Depends(get_writer)],
    speaker: Annotated[Speaker, Depends(get_speaker)],
) -> Meditation:
    """Escreve o roteiro (LLM) e dá voz às falas (TTS); as pausas ficam para o player."""
    if req.voice not in tts.VOICES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"voz desconhecida: {req.voice}")
    feeling = req.feeling.strip()
    script = writer.write(feeling)
    folder = uuid.uuid4().hex
    try:
        synthesis = speaker.synthesize(script, req.voice, root / folder)
    except Exception as e:
        shutil.rmtree(root / folder, ignore_errors=True)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"falha ao gerar a voz: {e}") from e
    return db.create(conn, feeling, req.voice, script, synthesis, folder)


@router.get("/meditations")
def list_meditations(conn: Conn) -> list[Meditation]:
    return db.list_all(conn)


@router.get("/meditations/{id}")
def get_meditation(id: int, conn: Conn) -> Meditation:
    found = db.get(conn, id)
    if found is None:
        raise _not_found(id)
    return found


@router.get("/meditations/{id}/audio/{index}")
def get_audio(id: int, index: int, conn: Conn, root: AudioRoot) -> FileResponse:
    found = db.audio_file(conn, id, index)
    path = root / found[0] / found[1] if found else None
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "áudio não encontrado")
    return FileResponse(path, media_type=MEDIA_TYPES.get(path.suffix))


@router.delete("/meditations/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meditation(id: int, conn: Conn, root: AudioRoot) -> None:
    folder = db.delete(conn, id)
    if folder is None:
        raise _not_found(id)
    shutil.rmtree(root / folder, ignore_errors=True)


# --- músicas ambientes (Lyria) ---


@router.get("/music/catalog")
def music_catalog() -> MusicCatalog:
    return MusicCatalog(
        presets=[
            MusicOption(id=k, label=label, detail=style)
            for k, (label, style) in music.PRESETS.items()
        ],
        lengths=[
            MusicOption(id=k, label=v.label, detail=f"US$ {v.usd:.2f} · gera em {v.wait}")
            for k, v in music.LENGTHS.items()
        ],
        prices={k: v.usd for k, v in music.LENGTHS.items()},
    )


def compose_track(
    id: int, prompt: str, kind: music.TrackKind, composer: Composer, database_url: str, root: Path
) -> None:
    """Roda depois da resposta: a peça completa leva uns 2,5 min para ficar pronta."""
    conn = core_db.connect(database_url)
    try:
        mp3 = composer.compose(prompt, kind)
        root.mkdir(parents=True, exist_ok=True)
        if db.get_track(conn, id) is None:  # apagada enquanto compunha
            return
        (root / f"{id}.mp3").write_bytes(mp3)
        cost = music.LENGTHS[kind].usd
        db.finish_track(conn, id, seconds=music.mp3_seconds(mp3), cost_usd=cost)
    except Exception as e:
        db.finish_track(conn, id, error=str(e)[:300])
    finally:
        conn.close()


@router.post("/music", status_code=status.HTTP_202_ACCEPTED)
def create_track(
    req: TrackIn,
    conn: Conn,
    root: AudioRoot,
    tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    composer: Annotated[Composer, Depends(get_composer)],
) -> Track:
    """Agenda a composição e responde na hora (status pending); a UI acompanha pela lista."""
    if req.preset and req.preset not in music.PRESETS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"preset desconhecido: {req.preset}"
        )
    if not req.preset and not (req.extra or "").strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "escolha um estilo ou descreva a música"
        )
    prompt = music.build_prompt(req.preset, req.extra)
    title = (req.title or "").strip() or (
        music.PRESETS[req.preset][0] if req.preset else (req.extra or "").strip()[:40]
    )
    track = db.create_track(conn, title, req.kind, req.preset, prompt)
    tasks.add_task(
        compose_track, track.id, prompt, req.kind, composer, settings.database_url, root / "music"
    )
    return track


@router.get("/music")
def list_tracks(conn: Conn) -> list[Track]:
    return db.list_tracks(conn)


@router.get("/music/{id}/audio")
def get_track_audio(id: int, root: AudioRoot) -> FileResponse:
    path = root / "music" / f"{id}.mp3"
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "música não encontrada")
    return FileResponse(path, media_type="audio/mpeg")


@router.delete("/music/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_track(id: int, conn: Conn, root: AudioRoot) -> None:
    if not db.delete_track(conn, id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"música {id} não encontrada")
    (root / "music" / f"{id}.mp3").unlink(missing_ok=True)
