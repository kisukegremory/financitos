from enum import StrEnum

from pydantic import BaseModel, Field


class Origin(StrEnum):
    MANUAL = "manual"
    AI = "ai"


class GenerateMode(StrEnum):
    ORIGINAL = "original"  # frase inédita no tom do prompt base
    QUOTE = "quote"  # citações reais e conhecidas de um pensador
    INSPIRED = "inspired"  # frase inédita inspirada no pensamento de alguém


class PhraseIn(BaseModel):
    text: str = Field(min_length=1)
    author: str | None = None
    source: str | None = None  # obra de origem (ex.: "A Arte da Guerra")
    origin: Origin = Origin.MANUAL
    prompt: str | None = None  # dica usada na geração (origin=ai)
    favorite: bool = False
    note: str | None = None


class PhraseUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1)
    author: str | None = None
    source: str | None = None
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
    source: str | None = None


class Suggestions(BaseModel):
    """Formato pedido à LLM na geração de frases."""

    items: list[Suggestion]


class Thinker(BaseModel):
    name: str
    era: str  # ex.: "China, séc. V a.C."
    why: str  # por que conversa com o tema
    works: list[str]


class Thinkers(BaseModel):
    """Formato pedido à LLM na recomendação de pensadores."""

    items: list[Thinker]


class ReadingRequest(BaseModel):
    feeling: str = Field(min_length=1)


class ReadingChoice(BaseModel):
    """Formato pedido à LLM na leitura: uma frase salva (phrase_id) ou uma nova."""

    phrase_id: int | None = None
    new_phrase: str | None = None
    why: str
    card_reading: str


class ThinkerQuotes(BaseModel):
    """Formato pedido à LLM na leitura: um pensador para o momento e citações reais dele."""

    thinker: Thinker
    quotes: list[Suggestion]


class Reading(BaseModel):
    id: int
    feeling: str
    phrase: Phrase | None  # None se a frase escolhida foi apagada depois
    generated_text: str | None  # frase nova sugerida quando nenhuma salva encaixou
    why: str
    draw: Draw
    card_reading: str
    thinker: Thinker | None = None  # None se a busca do pensador falhou
    quotes: list[Suggestion] = []
    created_at: str
