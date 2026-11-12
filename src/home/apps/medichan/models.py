from typing import Literal

from pydantic import BaseModel, Field, field_validator

MIN_PAUSE, MAX_PAUSE = 2, 60  # segundos de silêncio aceitos por pausa


class Segment(BaseModel):
    """Um trecho do roteiro: fala (vira áudio) ou pausa (só tempo no player)."""

    kind: Literal["speech", "pause"]
    text: str | None = None
    seconds: int | None = None


class Script(BaseModel):
    """Formato pedido à LLM: título e trechos em ordem."""

    title: str
    segments: list[Segment] = Field(min_length=1)

    @field_validator("segments")
    @classmethod
    def clean(cls, segments: list[Segment]) -> list[Segment]:
        out = []
        for s in segments:
            if s.kind == "speech":
                text = (s.text or "").strip()
                if text:
                    out.append(Segment(kind="speech", text=text))
            else:
                seconds = min(max(s.seconds or MIN_PAUSE, MIN_PAUSE), MAX_PAUSE)
                out.append(Segment(kind="pause", seconds=seconds))
        if not any(s.kind == "speech" for s in out):
            raise ValueError("roteiro sem nenhuma fala")
        return out


class MeditationIn(BaseModel):
    feeling: str = Field(min_length=1, max_length=1000)
    voice: str = "gemini"  # id do catálogo em tts.VOICES


class SegmentOut(Segment):
    audio: str | None = None  # URL do áudio (só em fala)


class Meditation(BaseModel):
    id: int
    feeling: str
    voice: str
    title: str
    segments: list[SegmentOut]
    chars: int | None = None  # caracteres cobrados no TTS
    cost_usd: float | None = None  # custo do TTS (a LLM do roteiro fica de fora: centavos)
    created_at: str


class VoiceInfo(BaseModel):
    id: str
    provider: str
    label: str
    note: str
    model: str
    pace: str  # lento | médio | rápido
    chars_per_sec: float
    estimate_usd: float  # custo estimado de uma meditação típica
    preview: str  # URL da amostra estática
