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


def _first_day_of_month(v: object) -> object:
    if isinstance(v, str):
        return parse_invoice(v)
    if isinstance(v, date):
        return v.replace(day=1)
    return v


CategorySource = Literal["llm", "manual"]


class Transaction(ParsedItem):
    source: str
    invoice: date  # first day of the invoice month
    category_source: CategorySource = "llm"  # 'manual' quando eu corrijo a caixinha
    note: str | None = None  # comentário livre, para lembrar do que se trata

    @field_validator("note", mode="before")
    @classmethod
    def _blank_note(cls, v: object) -> object:
        return (v.strip() or None) if isinstance(v, str) else v

    _invoice = field_validator("invoice", mode="before")(_first_day_of_month)


class StoredTransaction(Transaction):
    id: int


class TransactionUpdate(BaseModel):
    """Campos omitidos não mudam; `note` vazio/null apaga o comentário."""

    date: dt.date | None = None
    amount: Decimal | None = None
    category: Category | None = None
    description: str | None = None
    source: str | None = None
    invoice: dt.date | None = None
    note: str | None = None

    _invoice = field_validator("invoice", mode="before")(_first_day_of_month)


class PaymentIn(BaseModel):
    """Valor puxado de uma caixinha para pagar a fatura."""

    invoice: date
    source: str
    category: Category
    amount: Decimal
    paid_at: dt.date = Field(default_factory=dt.date.today)
    note: str | None = None

    _invoice = field_validator("invoice", mode="before")(_first_day_of_month)

    @field_validator("amount", mode="before")
    @classmethod
    def _round(cls, v: object) -> Decimal:
        return Decimal(str(v)).quantize(Decimal("0.01"))


class Payment(PaymentIn):
    id: int


class CategoryBalance(BaseModel):
    category: Category
    total: Decimal  # devido (soma dos lançamentos)
    paid: Decimal
    remaining: Decimal


class InvoiceSummary(BaseModel):
    invoice: str  # AAAA-MM
    categories: list[CategoryBalance]
    total: Decimal
    paid: Decimal
    remaining: Decimal
