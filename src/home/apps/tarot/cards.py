import json
import random
from functools import cache
from pathlib import Path

from home.apps.tarot.models import Card, Draw

CARDS_FILE = Path(__file__).with_name("cards.json")


@cache
def all_cards() -> list[Card]:
    """78 cartas Rider-Waite-Smith; imagens em web/public/tarot/<id>.webp."""
    return [Card(**c) for c in json.loads(CARDS_FILE.read_text())]


def get_card(id: str) -> Card | None:
    return next((c for c in all_cards() if c.id == id), None)


def draw(rng: random.Random | None = None) -> Draw:
    rng = rng or random.SystemRandom()
    return Draw(card=rng.choice(all_cards()), reversed=rng.random() < 0.5)
