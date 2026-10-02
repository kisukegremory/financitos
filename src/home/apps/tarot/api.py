import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from home.apps.tarot import cards, db
from home.apps.tarot.llm import PhraseWriter
from home.apps.tarot.models import Card, Draw, Phrase, PhraseIn, PhraseUpdate, Suggestion
from home.core.config import Settings, get_settings
from home.core.deps import Conn

EXAMPLES = 8  # frases salvas mandadas à LLM como referência de tom

router = APIRouter(tags=["tarot"])


def get_writer(settings: Annotated[Settings, Depends(get_settings)]) -> PhraseWriter:
    return PhraseWriter(settings)


class GenerateRequest(BaseModel):
    hint: str | None = None
    count: int = Field(default=3, ge=1, le=5)


class BasePrompt(BaseModel):
    value: str = Field(min_length=1)


def _not_found(id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"frase {id} não encontrada")


@router.get("/phrases")
def list_phrases(conn: Conn, q: str | None = None, favorite: bool | None = None) -> list[Phrase]:
    return db.list_phrases(conn, q, favorite)


@router.post("/phrases", status_code=status.HTTP_201_CREATED)
def create_phrase(p: PhraseIn, conn: Conn) -> Phrase:
    return db.create_phrase(conn, p)


@router.post("/phrases/generate")
def generate_phrases(
    req: GenerateRequest, conn: Conn, writer: Annotated[PhraseWriter, Depends(get_writer)]
) -> list[Suggestion]:
    """Sugestões da IA (não salva: revise e salve via POST /phrases)."""
    saved = db.list_phrases(conn)
    favorites = [p.text for p in saved if p.favorite] or [p.text for p in saved]
    examples = random.sample(favorites, min(EXAMPLES, len(favorites)))
    return writer.generate(db.get_base_prompt(conn), req.hint, req.count, examples).items


@router.put("/phrases/{id}")
def update_phrase(id: int, changes: PhraseUpdate, conn: Conn) -> Phrase:
    updated = db.update_phrase(conn, id, changes)
    if updated is None:
        raise _not_found(id)
    return updated


@router.delete("/phrases/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_phrase(id: int, conn: Conn) -> None:
    if not db.delete_phrase(conn, id):
        raise _not_found(id)


@router.get("/settings/base-prompt")
def get_base_prompt(conn: Conn) -> BasePrompt:
    return BasePrompt(value=db.get_base_prompt(conn))


@router.put("/settings/base-prompt")
def set_base_prompt(body: BasePrompt, conn: Conn) -> BasePrompt:
    return BasePrompt(value=db.set_base_prompt(conn, body.value))


@router.get("/cards")
def list_cards() -> list[Card]:
    return cards.all_cards()


@router.get("/cards/draw")
def draw_card() -> Draw:
    return cards.draw()
