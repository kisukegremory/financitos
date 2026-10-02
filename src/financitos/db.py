import sqlite3
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from financitos.models import Category, Transaction

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id              INTEGER PRIMARY KEY,
    date            TEXT    NOT NULL,  -- ISO 8601 (AAAA-MM-DD)
    amount_cents    INTEGER NOT NULL,
    category        TEXT    NOT NULL,
    description     TEXT    NOT NULL,
    source          TEXT    NOT NULL,
    invoice         TEXT    NOT NULL,  -- ISO 8601, 1º dia do mês
    seq             INTEGER NOT NULL DEFAULT 0,  -- n-ésima ocorrência idêntica na fatura
    category_source TEXT    NOT NULL DEFAULT 'llm',
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (date, amount_cents, description, source, invoice, seq)
);
CREATE INDEX IF NOT EXISTS ix_transactions_invoice ON transactions (invoice, source);
"""


@dataclass
class SaveResult:
    inserted: int
    skipped: int


def path_from_url(url: str) -> Path:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ValueError(f"DATABASE_URL não suportada: {url}")
    return Path(url.removeprefix(prefix))


def connect(url: str) -> sqlite3.Connection:
    path = path_from_url(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _cents(amount: Decimal) -> int:
    return int(amount * 100)


def save(conn: sqlite3.Connection, transactions: Iterable[Transaction]) -> SaveResult:
    """Insere ignorando duplicatas. Lançamentos idênticos na mesma fatura
    (ex.: duas compras iguais no mesmo dia) são diferenciados por `seq`."""
    seen: Counter[tuple] = Counter()
    inserted = skipped = 0
    with conn:
        for t in transactions:
            key = (
                t.date.isoformat(),
                _cents(t.amount),
                t.description,
                t.source,
                t.invoice.isoformat(),
            )
            seq = seen[key]
            seen[key] += 1
            cur = conn.execute(
                "INSERT OR IGNORE INTO transactions"
                " (date, amount_cents, description, source, invoice, seq, category)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (*key, seq, t.category.value),
            )
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1
    return SaveResult(inserted, skipped)


def _to_transaction(row: sqlite3.Row) -> Transaction:
    return Transaction(
        date=date.fromisoformat(row["date"]),
        amount=Decimal(row["amount_cents"]) / 100,
        category=Category(row["category"]),
        description=row["description"],
        source=row["source"],
        invoice=date.fromisoformat(row["invoice"]),
    )


def _filters(invoice: date | None, source: str | None, category: Category | None):
    clauses, params = [], []
    if invoice:
        clauses.append("invoice = ?")
        params.append(invoice.isoformat())
    if source:
        clauses.append("source = ? COLLATE NOCASE")
        params.append(source)
    if category:
        clauses.append("category = ?")
        params.append(category.value)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def list_transactions(
    conn: sqlite3.Connection,
    invoice: date | None = None,
    source: str | None = None,
    category: Category | None = None,
) -> list[Transaction]:
    where, params = _filters(invoice, source, category)
    rows = conn.execute(
        f"SELECT * FROM transactions{where} ORDER BY date DESC, id", params
    ).fetchall()
    return [_to_transaction(r) for r in rows]


def summary(
    conn: sqlite3.Connection, invoice: date, source: str | None = None
) -> dict[Category, Decimal]:
    where, params = _filters(invoice, source, None)
    rows = conn.execute(
        f"SELECT category, SUM(amount_cents) AS cents FROM transactions{where}"
        " GROUP BY category ORDER BY cents DESC",
        params,
    ).fetchall()
    return {Category(r["category"]): Decimal(r["cents"]) / 100 for r in rows}
