import base64
import logging
from dataclasses import dataclass
from typing import Literal

from openai import OpenAI

from home.core.config import Settings

log = logging.getLogger(__name__)

TrackKind = Literal["clip", "pro"]


@dataclass(frozen=True)
class Length:
    model: str
    label: str
    usd: float  # preço por geração (OpenRouter, 2026-11-12)
    wait: str  # tempo típico de geração


LENGTHS: dict[TrackKind, Length] = {
    "clip": Length("google/lyria-3-clip-preview", "Clip · ~30 s (loop)", 0.04, "~10 s"),
    "pro": Length("google/lyria-3-pro-preview", "Peça completa · ~3 min", 0.08, "~2,5 min"),
}

# Lyria entende melhor descrições em inglês; o rótulo fica em português na UI
PRESETS: dict[str, tuple[str, str]] = {
    "chuva": ("Chuva serena", "soft rain-like textures, warm analog pads, gentle low drones"),
    "oceano": ("Oceano", "slow swelling pads like ocean waves, deep warm bass drone, airy shimmer"),
    "floresta": (
        "Floresta",
        "gentle forest atmosphere, soft wooden flute, distant birds, light breeze",
    ),
    "tigelas": ("Tigelas tibetanas", "tibetan singing bowls, long resonant tones, soft drone"),
    "piano": ("Piano contemplativo", "sparse soft felt piano notes, long reverb, warm pads"),
    "cosmos": ("Cosmos", "deep cosmic drone, slowly evolving shimmering textures, vast space"),
    "sono": (
        "Sono profundo",
        "very slow, very low and quiet drones, dark warm pads, for deep sleep",
    ),
}

BASE = (
    "Instrumental ambient meditation music. {style}. Slow tempo around 60 bpm, no drums, "
    "no percussion, no vocals, no lyrics. Calm, spacious, steady and seamless, suitable as "
    "background for guided meditation."
)

ATTEMPTS = 2  # às vezes o stream termina sem áudio: tentamos de novo


def build_prompt(preset: str | None, extra: str | None) -> str:
    parts = [PRESETS[preset][1]] if preset in PRESETS else []
    if extra and extra.strip():
        parts.append(extra.strip())
    return BASE.format(style=", ".join(parts) or "warm pads and soft drones")


class Composer:
    """Gera música com o Lyria 3 (chat com saída de áudio, só em streaming; devolve MP3)."""

    def __init__(self, settings: Settings, client: OpenAI | None = None):
        self.client = client or OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key.get_secret_value(),
        )

    def compose(self, prompt: str, kind: TrackKind) -> bytes:
        for attempt in range(ATTEMPTS):
            data = ""
            stream = self.client.chat.completions.create(
                model=LENGTHS[kind].model,
                stream=True,
                modalities=["text", "audio"],
                messages=[{"role": "user", "content": prompt}],
            )  # type: ignore[call-overload]
            for chunk in stream:
                if not chunk.choices:
                    continue
                audio = (chunk.choices[0].delta.model_extra or {}).get("audio")
                if audio:
                    data += audio.get("data") or ""
            if data:
                return base64.b64decode(data)
            log.warning("lyria sem áudio (tentativa %d)", attempt + 1)
        raise RuntimeError("o Lyria não devolveu áudio")


MP3_BITRATES = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]  # MPEG-1 L3


def mp3_seconds(mp3: bytes) -> float | None:
    """Duração aproximada de um MP3 CBR (o do Lyria é 192 kbps), sem dependências."""
    start = 0
    if mp3[:3] == b"ID3":  # tag ID3v2: tamanho "syncsafe" nos bytes 6..9
        size = 0
        for b in mp3[6:10]:
            size = (size << 7) | (b & 0x7F)
        start = 10 + size
    header = mp3[start : start + 4]
    if len(header) < 4 or header[0] != 0xFF or (header[1] & 0xE0) != 0xE0:
        return None
    index = header[2] >> 4
    if not 0 < index < len(MP3_BITRATES):
        return None
    return round((len(mp3) - start) * 8 / (MP3_BITRATES[index] * 1000), 1)
