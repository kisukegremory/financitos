import csv
import io
from collections.abc import Iterable
from decimal import Decimal

from financitos.models import Transaction

HEADER = ["Data", "Gasto", "Caixinha", "Descrição", "Fonte", "Fatura"]


def format_amount(amount: Decimal) -> str:
    return f"{amount:.2f}".replace(".", ",")


def to_row(t: Transaction) -> list[str]:
    return [
        t.date.strftime("%d/%m/%Y"),
        format_amount(t.amount),
        t.category.value,
        t.description,
        t.source,
        t.invoice.strftime("%Y-%m"),
    ]


def render(transactions: Iterable[Transaction], fmt: str = "tsv", header: bool = True) -> str:
    buf = io.StringIO()
    delimiter = "\t" if fmt == "tsv" else ";"
    writer = csv.writer(buf, delimiter=delimiter, lineterminator="\n")
    if header:
        writer.writerow(HEADER)
    writer.writerows(to_row(t) for t in transactions)
    return buf.getvalue()
