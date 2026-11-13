"""Renderiza a meditação num arquivo único (voz + pausas + trilha), pronto para publicar.

Espelha o tempo do Player do estúdio (LEAD/GAP/TAIL), mas no servidor: o app de consumo só
toca um arquivo, o que funciona com a tela bloqueada e em segundo plano no celular.
"""

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg

RATE = 48000
BYTES_PER_SEC = RATE * 2  # PCM 16 bits mono
LEAD = 6.0  # s só de trilha antes da primeira fala
GAP = 1.2  # s entre falas seguidas
TAIL = 10.0  # s de trilha no fim, com fade
BED_VOLUME = 0.3  # trilha sob a voz (ainda abaixada pelo sidechain enquanto ela fala)
LOUDNESS = -18  # LUFS: todas as meditações com o mesmo volume percebido

# (extensão, argumentos do codec): Opus é leve; AAC cobre aparelhos/navegadores sem Opus
FORMATS = {
    "ogg": ["-c:a", "libopus", "-b:a", "64k"],
    "m4a": ["-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart"],
}


@dataclass(frozen=True)
class Part:
    kind: str  # speech | pause
    file: Path | None = None
    seconds: float = 0


def ffmpeg(*args: str, input: bytes | None = None) -> bytes:
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args]
    done = subprocess.run(cmd, input=input, capture_output=True, check=False)
    if done.returncode:
        raise RuntimeError(f"ffmpeg falhou: {done.stderr.decode(errors='replace')[-500:]}")
    return done.stdout


def decode(file: Path) -> bytes:
    """Qualquer áudio (mp3/wav) → PCM 16 bits mono 48 kHz."""
    return ffmpeg("-i", str(file), "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-")


def silence(seconds: float) -> bytes:
    return bytes(int(seconds * RATE) * 2)


def voice_track(parts: list[Part]) -> bytes:
    """Faixa só de voz com as pausas e respiros já como silêncio."""
    out = [silence(LEAD)]
    prev = None
    for p in parts:
        if p.kind == "speech" and p.file:
            if prev == "speech":
                out.append(silence(GAP))
            out.append(decode(p.file))
        else:
            out.append(silence(p.seconds))
        prev = p.kind
    out.append(silence(TAIL))
    return b"".join(out)


def render(parts: list[Part], dest: Path, bed: Path | None = None) -> float:
    """Grava dest/audio.ogg e dest/audio.m4a; devolve a duração em segundos."""
    voice = voice_track(parts)
    total = len(voice) / BYTES_PER_SEC
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "voice.pcm"
        raw.write_bytes(voice)
        args = ["-f", "s16le", "-ar", str(RATE), "-ac", "1", "-i", str(raw)]
        norm = f"loudnorm=I={LOUDNESS}:TP=-1.5:LRA=11,aresample={RATE}"
        if bed:
            fade_out = max(total - TAIL, 0)
            args += ["-stream_loop", "-1", "-i", str(bed)]
            graph = (
                "[0:a]asplit=2[v][sc];"
                f"[1:a]aformat=sample_rates={RATE}:channel_layouts=mono,volume={BED_VOLUME},"
                f"afade=t=in:d=4,afade=t=out:st={fade_out:.2f}:d={TAIL}[b];"
                "[b][sc]sidechaincompress=threshold=0.02:ratio=4:attack=200:release=1500[bd];"
                f"[v][bd]amix=inputs=2:normalize=0:duration=first,{norm},asplit=2[o0][o1]"
            )
        else:
            graph = f"[0:a]{norm},asplit=2[o0][o1]"
        args += ["-filter_complex", graph]
        for i, (ext, codec) in enumerate(FORMATS.items()):
            args += ["-map", f"[o{i}]", *codec, str(dest / f"audio.{ext}")]
        ffmpeg(*args)
    return round(total, 1)
