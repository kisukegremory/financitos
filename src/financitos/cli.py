import logging
import sys
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from financitos.config import get_settings
from financitos.llm import Categorizer
from financitos.models import Transaction
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
) -> None:
    """Lê o texto da fatura e imprime os lançamentos categorizados."""
    invoice_date = parse_invoice(invoice)
    text = file.read_text() if file else sys.stdin.read()
    if not text.strip():
        raise typer.BadParameter("texto da fatura vazio")

    parsed = Categorizer(get_settings()).parse(text, invoice_date)
    transactions = [
        Transaction(**item.model_dump(), source=source, invoice=invoice_date)
        for item in parsed.items
    ]

    typer.echo(render(transactions, fmt.value, header=not no_header), nl=False)
    total = sum((t.amount for t in transactions), start=0)
    typer.echo(f"\n{len(transactions)} lançamentos · total R$ {format_amount(total)}", err=True)
