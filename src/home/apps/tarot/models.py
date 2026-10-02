from enum import StrEnum

from pydantic import BaseModel, Field


class Origin(StrEnum):
    MANUAL = "manual"
    AI = "ai"


class PhraseIn(BaseModel):
    text: str = Field(min_length=1)
    author: str | None = None
    origin: Origin = Origin.MANUAL
    prompt: str | None = None  # dica usada na geração (origin=ai)
    favorite: bool = False
    note: str | None = None


class PhraseUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1)
    author: str | None = None
    favorite: bool | None = None
    note: str | None = None


class Phrase(PhraseIn):
    id: int
    created_at: str


class Card(BaseModel):
    id: str
    name: str
    arcana: str
    suit: str | None
    number: int
    keywords: list[str]
    upright: str
    reversed: str


class Draw(BaseModel):
    card: Card
    reversed: bool


class Suggestion(BaseModel):
    text: str
    author: str | None = None


class Suggestions(BaseModel):
    """Formato pedido à LLM na geração de frases."""

    items: list[Suggestion]
