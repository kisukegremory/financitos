import logging
import sys
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from financitos import db
from financitos.config import get_settings
from financitos.llm import Categorizer
from financitos.models import Category, Transaction
from financitos.output import format_amount, render

app = typer.Typer(no_args_is_help=True, help="Categoriza faturas nas caixinhas do PicPay.")


class OutputFormat(StrEnum):
    TSV = "tsv"
    CSV = "csv"


@app.callback()
def main() -> None:
    logging.basicConfig(level=get_settings().log_level, stream=sys.stderr)
    for noisy in ("httpx", "httpx2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def parse_invoice(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m").date()
    except ValueError as e:
        raise typer.BadParameter("use o formato AAAA-MM") from e


@app.command()
def parse(
    source: Annotated[str, typer.Option("--source", "-s", help="PicPay, Nubank...")],
    invoice: Annotated[str, typer.Option("--invoice", "-i", help="Mês da fatura (AAAA-MM)")],
    file: Annotated[Path | None, typer.Argument(help="Texto da fatura (padrão: stdin)")] = None,
    fmt: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.TSV,
    no_header: Annotated[bool, typer.Option("--no-header")] = False,
    save: Annotated[bool, typer.Option("--save", help="Salva os lançamentos no SQLite")] = False,
) -> None:
    """Lê o texto da fatura e imprime os lançamentos categorizados."""
    invoice_date = parse_invoice(invoice)
    text = file.read_text() if file else sys.stdin.read()
    if not text.strip():
        raise typer.BadParameter("texto da fatura vazio")

    # abre o banco antes da LLM para falhar cedo, sem gastar a chamada
    conn = db.connect(get_settings().database_url) if save else None

    parsed = Categorizer(get_settings()).parse(text, invoice_date)
    transactions = [
        Transaction(**item.model_dump(), source=source, invoice=invoice_date)
        for item in parsed.items
    ]

    typer.echo(render(transactions, fmt.value, header=not no_header), nl=False)
    print_total(transactions)

    if conn:
        with closing(conn):
            result = db.save(conn, transactions)
        typer.echo(f"salvos: {result.inserted} · duplicados ignorados: {result.skipped}", err=True)


@app.command("list")
def list_(
    invoice: Annotated[str | None, typer.Option("--invoice", "-i", help="AAAA-MM")] = None,
    source: Annotated[str | None, typer.Option("--source", "-s")] = None,
    category: Annotated[Category | None, typer.Option("--category", "-c")] = None,
    fmt: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.TSV,
    no_header: Annotated[bool, typer.Option("--no-header")] = False,
) -> None:
    """Lista lançamentos salvos."""
    invoice_date = parse_invoice(invoice) if invoice else None
    with closing(db.connect(get_settings().database_url)) as conn:
        transactions = db.list_transactions(conn, invoice_date, source, category)
    typer.echo(render(transactions, fmt.value, header=not no_header), nl=False)
    print_total(transactions)


@app.command()
def summary(
    invoice: Annotated[str, typer.Option("--invoice", "-i", help="AAAA-MM")],
    source: Annotated[str | None, typer.Option("--source", "-s")] = None,
) -> None:
    """Total por caixinha de uma fatura (quanto tirar de cada uma)."""
    with closing(db.connect(get_settings().database_url)) as conn:
        totals = db.summary(conn, parse_invoice(invoice), source)
    if not totals:
        typer.echo("nenhum lançamento encontrado", err=True)
        raise typer.Exit(1)
    width = max(len(c.value) for c in totals)
    for category, amount in totals.items():
        typer.echo(f"{category.value:<{width}}  R$ {format_amount(amount):>10}")
    typer.echo(
        f"{'Total':<{width}}  R$ {format_amount(sum(totals.values(), start=Decimal(0))):>10}"
    )


def print_total(transactions: list[Transaction]) -> None:
    total = sum((t.amount for t in transactions), start=Decimal(0))
    typer.echo(f"\n{len(transactions)} lançamentos · total R$ {format_amount(total)}", err=True)
