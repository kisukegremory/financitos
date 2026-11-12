import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated

import typer

from home.apps.medichan.llm import ScriptWriter
from home.apps.medichan.tts import PREVIEW_TEXT, VOICES, Speaker
from home.core.config import get_settings

app = typer.Typer(no_args_is_help=True, help="Meditações guiadas em áudio.")

PUBLIC = Path("web/public/medichan")
VoiceOpt = Annotated[list[str] | None, typer.Option("--voice", help="Id da voz (repetível)")]


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug if len(slug) <= 40 else slug[:40].rsplit("-", 1)[0]


def pick_voices(voices: list[str] | None) -> list[str]:
    unknown = set(voices or []) - set(VOICES)
    if unknown:
        raise typer.BadParameter(f"vozes desconhecidas: {', '.join(sorted(unknown))}")
    return voices or list(VOICES)


@app.command()
def sample(
    feeling: Annotated[str, typer.Argument(help="Como a pessoa está se sentindo")],
    voices: VoiceOpt = None,
    out: Annotated[Path, typer.Option(help="Pasta dos exemplos")] = PUBLIC / "samples",
) -> None:
    """Gera UM roteiro e grava uma versão por voz, como exemplo estático da UI."""
    chosen = pick_voices(voices)
    settings = get_settings()
    script = ScriptWriter(settings).write(feeling)
    typer.echo(f"roteiro: {script.title} ({len(script.segments)} trechos)", err=True)

    index_path = out / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else []
    speaker = Speaker(settings)
    for voice in chosen:
        slug = f"{slugify(feeling)}-{voice}"
        result = speaker.synthesize(script, voice, out / slug)
        base = f"/medichan/samples/{slug}"
        meditation = {
            "slug": slug,
            "feeling": feeling,
            "voice": voice,
            "title": script.title,
            "chars": result.chars,
            "cost_usd": result.cost_usd,
            "segments": [
                {**s.model_dump(), "audio": f"{base}/{f}" if f else None}
                for s, f in zip(script.segments, result.files, strict=True)
            ],
        }
        (out / slug / "meditation.json").write_text(
            json.dumps(meditation, ensure_ascii=False, indent=2) + "\n"
        )
        index = [i for i in index if i["slug"] != slug] + [
            {
                "slug": slug,
                "title": script.title,
                "feeling": feeling,
                "voice": voice,
                "cost_usd": result.cost_usd,
            }
        ]
        typer.echo(f"ok: {out / slug} (US$ {result.cost_usd:.4f})", err=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")


@app.command()
def voices(
    voices: VoiceOpt = None,
    force: Annotated[bool, typer.Option(help="Regrava amostras existentes")] = False,
    out: Annotated[Path, typer.Option(help="Pasta das amostras")] = PUBLIC / "voices",
) -> None:
    """Grava uma amostra curta (mesmo texto) de cada voz do catálogo, para comparar na UI."""
    out.mkdir(parents=True, exist_ok=True)
    todo = [v for v in pick_voices(voices) if force or not (out / f"{v}.{VOICES[v].ext}").exists()]
    speaker = Speaker(get_settings())

    def one(voice: str) -> str:
        try:
            spoken = speaker.speak(PREVIEW_TEXT, voice)
        except Exception as e:
            return f"ERRO {voice}: {e}"
        (out / f"{voice}.{VOICES[voice].ext}").write_bytes(spoken.audio)
        return f"ok: {voice} (US$ {VOICES[voice].cost(spoken.chars, spoken.seconds):.4f})"

    with ThreadPoolExecutor(max_workers=6) as pool:
        for line in pool.map(one, todo):
            typer.echo(line, err=True)
