from datetime import date
from decimal import Decimal
from enum import StrEnum

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


class Transaction(ParsedItem):
    source: str
    invoice: date  # first day of the invoice month
