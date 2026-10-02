import sys
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from home.apps.financitos import db, models
from home.apps.financitos.llm import Categorizer
from home.apps.financitos.models import Category, Transaction
from home.apps.financitos.output import format_amount, render
from home.core.config import get_settings

app = typer.Typer(no_args_is_help=True, help="Categoriza faturas nas caixinhas do PicPay.")


class OutputFormat(StrEnum):
    TSV = "tsv"
    CSV = "csv"


def parse_invoice(value: str) -> date:
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError as e:
        raise typer.BadParameter("use o formato AAAA-MM") from e
    return models.parse_invoice(value)


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
    """Devido, pago e o que falta por caixinha numa fatura."""
    with closing(db.connect(get_settings().database_url)) as conn:
        s = db.summary(conn, parse_invoice(invoice), source)
    if not s.categories:
        typer.echo("nenhum lançamento encontrado", err=True)
        raise typer.Exit(1)
    rows = [(c.category.value, c.total, c.paid, c.remaining) for c in s.categories]
    rows.append(("Total", s.total, s.paid, s.remaining))
    width = max(len(r[0]) for r in rows)
    typer.echo(f"{'Caixinha':<{width}}  {'Devido':>12}  {'Pago':>12}  {'Falta':>12}")
    for name, *values in rows:
        cols = "  ".join(f"{format_amount(v):>12}" for v in values)
        typer.echo(f"{name:<{width}}  {cols}")


@app.command()
def pay(
    invoice: Annotated[str, typer.Option("--invoice", "-i", help="AAAA-MM")],
    source: Annotated[str, typer.Option("--source", "-s")],
    paid_at: Annotated[
        str | None,
        typer.Option("--date", "-d", help="Data do pagamento (AAAA-MM-DD, padrão: hoje)"),
    ] = None,
) -> None:
    """Registra o pagamento do que falta em cada caixinha (vale para antecipado)."""
    when = date.fromisoformat(paid_at) if paid_at else None
    with closing(db.connect(get_settings().database_url)) as conn:
        payments = db.pay_remaining(conn, parse_invoice(invoice), source, when)
    if not payments:
        typer.echo("nada a pagar: a fatura já está quitada", err=True)
        return
    for p in payments:
        typer.echo(f"{p.category.value}: R$ {format_amount(p.amount)}")
    total = sum((p.amount for p in payments), start=Decimal(0))
    typer.echo(f"pago: R$ {format_amount(total)}", err=True)


@app.command()
def balances(
    set_: Annotated[
        tuple[Category, str] | None,
        typer.Option("--set", help='Atualiza um saldo: --set "Mercado" 1500,00'),
    ] = None,
) -> None:
    """Mostra (ou atualiza) o saldo atual de cada caixinha."""
    with closing(db.connect(get_settings().database_url)) as conn:
        if set_:
            category, raw = set_
            db.set_balance(conn, category, parse_amount(raw))
        rows = db.list_balances(conn)
    width = max(len(b.category.value) for b in rows)
    for b in rows:
        when = b.updated_at[:10] if b.updated_at else "nunca informado"
        typer.echo(f"{b.category.value:<{width}}  R$ {format_amount(b.amount):>12}  ({when})")
    total = sum((b.amount for b in rows), start=Decimal(0))
    typer.echo(f"{'Total':<{width}}  R$ {format_amount(total):>12}")


def parse_amount(raw: str) -> Decimal:
    """Aceita '1.500,00', '1500,00' e '1500.00'."""
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return Decimal(raw)
    except ArithmeticError as e:
        raise typer.BadParameter(f"valor inválido: {raw}") from e


def print_total(transactions: list[Transaction]) -> None:
    total = sum((t.amount for t in transactions), start=Decimal(0))
    typer.echo(f"\n{len(transactions)} lançamentos · total R$ {format_amount(total)}", err=True)
