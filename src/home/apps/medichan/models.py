from typing import Literal

from pydantic import BaseModel, Field, field_validator

MIN_PAUSE, MAX_PAUSE = 2, 60  # segundos de silêncio aceitos por pausa


class Segment(BaseModel):
    """Um trecho do roteiro: fala (vira áudio) ou pausa (só tempo no player)."""

    kind: Literal["speech", "pause", "breath"]
    text: str | None = None
    seconds: int | None = None
    technique: str | None = None  # só em breath: id de breath.TECHNIQUES
    cycles: int | None = None


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
            elif s.kind == "breath":
                out.append(Segment(kind="breath", technique=s.technique, cycles=s.cycles))
            else:
                seconds = min(max(s.seconds or MIN_PAUSE, MIN_PAUSE), MAX_PAUSE)
                out.append(Segment(kind="pause", seconds=seconds))
        if not any(s.kind == "speech" for s in out):
            raise ValueError("roteiro sem nenhuma fala")
        return out


class Profile(BaseModel):
    """Contexto pessoal que personaliza os roteiros."""

    about: str = Field(default="", max_length=6000)
    max_hold: int = Field(default=3, ge=0, le=10)  # retenção máxima de ar, em segundos


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


class TrackIn(BaseModel):
    kind: Literal["clip", "pro"] = "clip"
    preset: str | None = None  # chave de music.PRESETS
    extra: str | None = Field(default=None, max_length=500)  # descrição livre (em inglês, melhor)
    title: str | None = Field(default=None, max_length=80)


class Track(BaseModel):
    id: int
    title: str
    kind: Literal["clip", "pro"]
    preset: str | None
    prompt: str
    status: Literal["pending", "ready", "error"]
    error: str | None = None
    seconds: float | None = None
    cost_usd: float | None = None
    audio: str | None = None  # URL quando pronta
    created_at: str


class MusicOption(BaseModel):
    id: str
    label: str
    detail: str


class MusicCatalog(BaseModel):
    presets: list[MusicOption]
    lengths: list[MusicOption]
    prices: dict[str, float]


# --- publicação (contrato com o app de consumo; ver docs/medichan-catalog.md) ---

Access = Literal["free", "private"]
SLUG = r"^[a-z0-9]+(-[a-z0-9]+)*$"


class PublishIn(BaseModel):
    slug: str | None = Field(default=None, max_length=60, pattern=SLUG)  # padrão: do título
    title: str | None = Field(default=None, max_length=120)  # padrão: o da meditação
    summary: str = Field(default="", max_length=300)
    tags: list[str] = Field(default_factory=list, max_length=8)
    access: Access = "free"
    track_id: int | None = None  # música Lyria por baixo da voz; None = só voz


class AudioFiles(BaseModel):
    """Caminhos relativos ao catalog.json (funciona igual em disco local, CDN ou bucket)."""

    ogg: str
    m4a: str


class PublishedItem(BaseModel):
    slug: str
    title: str
    summary: str
    tags: list[str]
    access: Access
    duration_s: float
    audio: AudioFiles
    published_at: str


class Catalog(BaseModel):
    schema_version: int = 1
    updated_at: str
    items: list[PublishedItem]


class PublishedRow(PublishedItem):
    """Visão do estúdio: inclui a origem (não vai para o catálogo público)."""

    meditation_id: int | None
    track_id: int | None
