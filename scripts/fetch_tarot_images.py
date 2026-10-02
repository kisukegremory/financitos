"""Baixa as 78 cartas Rider-Waite-Smith (1909, domínio público) num zip só, do
repositório github.com/metabismuth/tarot-json, e salva em web/public/tarot/<id>.webp,
reduzidas para versionar no repo.

    uv run --with pillow --with httpx scripts/fetch_tarot_images.py
"""

import io
import json
import zipfile
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "src/home/apps/tarot/cards.json"
OUT = ROOT / "web/public/tarot"
WIDTH = 360
ZIP_URL = "https://github.com/metabismuth/tarot-json/archive/refs/heads/master.zip"

# no zip: m00..m21 (arcanos maiores), w/c/s/p01..14 (paus, copas, espadas, ouros)
PREFIX = {"wands": "w", "cups": "c", "swords": "s", "pentacles": "p"}


def zip_name(card: dict) -> str:
    prefix = "m" if card["arcana"] == "major" else PREFIX[card["suit"]]
    return f"tarot-json-master/cards/{prefix}{card['number']:02d}.jpg"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cards = json.loads(CARDS.read_text())
    resp = httpx.get(ZIP_URL, follow_redirects=True, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for card in cards:
            img = Image.open(zf.open(zip_name(card))).convert("RGB")
            img.thumbnail((WIDTH, WIDTH * 2))
            img.save(OUT / f"{card['id']}.webp", "WEBP", quality=80)
    print(f"{len(cards)} cartas em {OUT}")


if __name__ == "__main__":
    main()
