"""Importação de faturas exportadas em CSV (Nubank).

O CSV já vem estruturado, então datas, valores e descrições são lidos direto do
arquivo; a LLM só é usada para escolher a caixinha das descrições inéditas.
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from home.apps.financitos.llm import Categorizer
from home.apps.financitos.models import Category, Transaction

# Linhas que não são gastos (pagamento da fatura anterior)
IGNORED_TITLES = ("pagamento recebido",)

FILENAME_INVOICE = re.compile(r"(\d{4})-(\d{2})-\d{2}")


class CsvError(ValueError):
    pass


@dataclass
class CsvRow:
    date: date
    amount: Decimal
    description: str


def parse_amount(raw: str) -> Decimal:
    """Aceita '1.234,56', '184,99', '-19,90' e '184.99'."""
    raw = raw.strip().replace("R$", "").replace(" ", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return Decimal(raw).quantize(Decimal("0.01"))
    except InvalidOperation as e:
        raise CsvError(f"valor inválido: {raw!r}") from e


def parse_nubank(text: str) -> list[CsvRow]:
    """CSV do Nubank: `date,title,amount` (data ISO, valor com vírgula decimal)."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if not reader.fieldnames or not {"date", "title", "amount"} <= set(reader.fieldnames):
        raise CsvError("CSV sem as colunas esperadas: date,title,amount")
    rows = []
    for line, r in enumerate(reader, start=2):
        title = (r["title"] or "").strip()
        if not title or title.lower().startswith(IGNORED_TITLES):
            continue
        try:
            when = date.fromisoformat(r["date"].strip())
        except (ValueError, AttributeError) as e:
            raise CsvError(f"linha {line}: data inválida {r['date']!r}") from e
        rows.append(CsvRow(when, parse_amount(r["amount"] or ""), title))
    return rows


def invoice_from_filename(name: str) -> str | None:
    """'Nubank_2026-12-16.csv' -> '2026-12' (mês do vencimento)."""
    m = FILENAME_INVOICE.search(name)
    return f"{m[1]}-{m[2]}" if m else None


def categorize(
    rows: list[CsvRow],
    known: dict[str, Category],
    categorizer: Categorizer,
) -> tuple[dict[str, Category], int]:
    """Completa `known` com a LLM para descrições inéditas (deduplicadas, 1 chamada).
    Retorna o mapa descrição -> caixinha e quantas descrições foram para a LLM."""
    pending: dict[str, Decimal] = {}
    for r in rows:
        if r.description not in known:
            pending.setdefault(r.description, r.amount)
    guessed = categorizer.categorize(list(pending.items()))
    return {**known, **guessed}, len(pending)


# Caixinha usada se a LLM deixar alguma descrição sem resposta (dá para corrigir na revisão)
FALLBACK_CATEGORY = Category.PESSOAL


def to_transactions(
    batches: list[tuple[date, list[CsvRow]]], categories: dict[str, Category], source: str
) -> list[Transaction]:
    return [
        Transaction(
            date=r.date,
            amount=r.amount,
            description=r.description,
            category=categories.get(r.description, FALLBACK_CATEGORY),
            source=source,
            invoice=invoice,
        )
        for invoice, rows in batches
        for r in rows
    ]
