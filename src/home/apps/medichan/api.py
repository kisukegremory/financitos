import shutil
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from home.apps.medichan import db, tts
from home.apps.medichan.llm import ScriptWriter
from home.apps.medichan.models import Meditation, MeditationIn, VoiceInfo
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
