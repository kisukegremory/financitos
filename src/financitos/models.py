import datetime as dt
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Category(StrEnum):
    VIAGEM = "Viagem"
    PESSOAL = "Pessoal"
    MERCADO = "Mercado"
    BUFFER_ANUAL = "Buffer Anual"
    BUFFER_MENSAL = "Buffer Mensal"
    ESTUDO = "Estudo"
    CASA = "Casa"
    SAUDE = "Saúde"
    CONTAS_ASSINATURAS = "Contas e assinaturas"
    HIGIENE_ESTETICA = "Higiene e Estética"


class ParsedItem(BaseModel):
    """Item as returned by the LLM (before source/invoice are attached)."""

    date: date
    amount: Decimal = Field(decimal_places=2)
    category: Category
    description: str

    @field_validator("amount", mode="before")
    @classmethod
    def _round(cls, v: object) -> Decimal:
        return Decimal(str(v)).quantize(Decimal("0.01"))


class ParsedItems(BaseModel):
    items: list[ParsedItem]


def parse_invoice(value: str) -> date:
    """'AAAA-MM' (ou data ISO) -> primeiro dia do mês."""
    return date.fromisoformat(value[:7] + "-01")


CategorySource = Literal["llm", "manual"]


class Transaction(ParsedItem):
    source: str
    invoice: date  # first day of the invoice month
    category_source: CategorySource = "llm"  # 'manual' quando eu corrijo a caixinha

    @field_validator("invoice", mode="before")
    @classmethod
    def _first_day(cls, v: object) -> object:
        if isinstance(v, str):
            return parse_invoice(v)
        if isinstance(v, date):
            return v.replace(day=1)
        return v


class StoredTransaction(Transaction):
    id: int


class TransactionUpdate(BaseModel):
    date: dt.date | None = None
    amount: Decimal | None = None
    category: Category | None = None
    description: str | None = None
    source: str | None = None
    invoice: dt.date | None = None

    @field_validator("invoice", mode="before")
    @classmethod
    def _first_day(cls, v: object) -> object:
        return parse_invoice(v) if isinstance(v, str) else v
