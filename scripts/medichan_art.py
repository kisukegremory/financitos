"""Gera as artes do medichan via OpenRouter (modelo de imagem) em web/public/medichan/art/.

uv run python scripts/medichan_art.py [nome ...]   # sem argumentos gera todas que faltam
Sai em PNG (~1,3 MB); converter para .webp (o app usa <nome>.webp):
  uv run --with pillow python -c "from PIL import Image; Image.open('x.png').save('x.webp', quality=78)"
"""

import base64
import sys
from pathlib import Path

from openai import OpenAI

from home.core.config import get_settings

MODEL = "google/gemini-3.1-flash-image"
OUT = Path(__file__).resolve().parents[1] / "web/public/medichan/art"

STYLE = (
    "Soft painterly digital illustration, serene and meditative, muted dusk palette of deep indigo, "
    "dusty violet, sage green and warm moonlight gold, gentle haze and film grain, minimal detail, "
    "lots of calm negative space, no people, no text, no logos, no borders."
)

ARTS = {
    "hero": ("21:9", "A misty mountain lake at blue hour, a pale full moon low over layered "
             "silhouetted hills, faint reflections on still water. Darker toward the bottom."),
    "player": ("16:9", "A vast calm night sky over a quiet sea, a soft glowing moon at the center "
               "with a subtle halo, faint stars, very dark edges fading to deep indigo."),
    "create": ("16:9", "A single lotus flower floating on dark still water at dawn, ripples, "
               "soft mist, warm gold light on the petals."),
    "music": ("16:9", "Gentle rain over a forest of pine trees in fog, dusk light, soft and quiet."),
    "mascot": ("1:1", "MASCOT"),
}

# mascote/logo: estilo próprio (não usa STYLE das paisagens)
MASCOT = (
    "Original pixel art character sprite, chibi proportions, in the style of late-1990s/2000s isometric "
    "MMORPG sprites: a cute calico (tricolor white, orange and black patches) cat girl dressed as a "
    "Buddhist monk, saffron and maroon robe, small prayer beads, sitting in calm lotus meditation pose "
    "with eyes gently closed and a tiny smile. Crisp visible pixels, limited palette, dark 1px outline, "
    "soft shading. Centered, full body, on a plain solid flat white background, no shadow on ground, "
    "no text."
)


def generate(client: OpenAI, name: str) -> None:
    ratio, scene = ARTS[name]
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": MASCOT if scene == "MASCOT" else f"{scene} {STYLE}"}],
        extra_body={"modalities": ["image", "text"], "image_config": {"aspect_ratio": ratio}},
    )
    images = getattr(resp.choices[0].message, "images", None) or []
    if not images:
        raise RuntimeError(f"{name}: nenhuma imagem na resposta")
    url = images[0]["image_url"]["url"]
    data = base64.b64decode(url.split(",", 1)[1])
    ext = "jpg" if "jpeg" in url[:30] else "png"
    path = OUT / f"{name}.{ext}"
    path.write_bytes(data)
    print(f"{path.relative_to(OUT.parents[3])} ({len(data) // 1024} KB)")


def main() -> None:
    s = get_settings()
    client = OpenAI(base_url=s.openrouter_base_url, api_key=s.openrouter_api_key.get_secret_value())
    OUT.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or [n for n in ARTS if not any(OUT.glob(f"{n}.*"))]
    for name in names:
        generate(client, name)


if __name__ == "__main__":
    main()
