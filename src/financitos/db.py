import sqlite3
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from financitos.models import Category, StoredTransaction, Transaction, TransactionUpdate

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
    note            TEXT,
    UNIQUE (date, amount_cents, description, source, invoice, seq)
);
CREATE INDEX IF NOT EXISTS ix_transactions_invoice ON transactions (invoice, source);
"""

# Colunas adicionadas depois da criação da tabela: (nome, definição)
MIGRATIONS = [("note", "TEXT")]

KEY_COLUMNS = ("date", "amount_cents", "description", "source", "invoice")


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
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(transactions)")}
    with conn:
        for name, definition in MIGRATIONS:
            if name not in existing:
                conn.execute(f"ALTER TABLE transactions ADD COLUMN {name} {definition}")


def _cents(amount: Decimal) -> int:
    return int(amount * 100)


def _from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))


def _key(t: Transaction) -> tuple:
    return (t.date.isoformat(), _cents(t.amount), t.description, t.source, t.invoice.isoformat())


def save(conn: sqlite3.Connection, transactions: Iterable[Transaction]) -> SaveResult:
    """Insere ignorando duplicatas. Lançamentos idênticos na mesma fatura
    (ex.: duas compras iguais no mesmo dia) são diferenciados por `seq`."""
    seen: Counter[tuple] = Counter()
    inserted = skipped = 0
    with conn:
        for t in transactions:
            key = _key(t)
            seq = seen[key]
            seen[key] += 1
            cur = conn.execute(
                "INSERT OR IGNORE INTO transactions"
                " (date, amount_cents, description, source, invoice, seq, category,"
                " category_source, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*key, seq, t.category.value, t.category_source, t.note),
            )
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1
    return SaveResult(inserted, skipped)


def _next_seq(conn: sqlite3.Connection, key: tuple, exclude_id: int | None = None) -> int:
    where = " AND ".join(f"{c} = ?" for c in KEY_COLUMNS)
    row = conn.execute(
        f"SELECT COALESCE(MAX(seq) + 1, 0) FROM transactions WHERE {where} AND id IS NOT ?",
        (*key, exclude_id),
    ).fetchone()
    return row[0]


def create(conn: sqlite3.Connection, t: Transaction) -> StoredTransaction:
    """Insere manualmente (sempre insere: idênticos ganham o próximo `seq`)."""
    key = _key(t)
    with conn:
        cur = conn.execute(
            "INSERT INTO transactions"
            " (date, amount_cents, description, source, invoice, seq, category,"
            " category_source, note) VALUES (?, ?, ?, ?, ?, ?, ?, 'manual', ?)",
            (*key, _next_seq(conn, key), t.category.value, t.note),
        )
    return get(conn, cur.lastrowid)  # type: ignore[arg-type, return-value]


def get(conn: sqlite3.Connection, id: int) -> StoredTransaction | None:
    row = conn.execute("SELECT * FROM transactions WHERE id = ?", (id,)).fetchone()
    return _to_transaction(row) if row else None


def update(
    conn: sqlite3.Connection, id: int, changes: TransactionUpdate
) -> StoredTransaction | None:
    current = get(conn, id)
    if current is None:
        return None
    patch = {
        k: v
        for k, v in changes.model_dump(exclude_unset=True).items()
        if v is not None or k == "note"  # note=None apaga o comentário
    }
    if not patch:
        return current
    merged = Transaction(**{**current.model_dump(), **patch})
    key = _key(merged)
    category_source = "manual" if "category" in patch else current.category_source
    with conn:
        conn.execute(
            "UPDATE transactions SET date = ?, amount_cents = ?, description = ?, source = ?,"
            " invoice = ?, seq = ?, category = ?, category_source = ?, note = ?,"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            (
                *key,
                _next_seq(conn, key, id),
                merged.category.value,
                category_source,
                merged.note,
                id,
            ),
        )
    return get(conn, id)


def delete(conn: sqlite3.Connection, id: int) -> bool:
    with conn:
        return conn.execute("DELETE FROM transactions WHERE id = ?", (id,)).rowcount > 0


def _to_transaction(row: sqlite3.Row) -> StoredTransaction:
    return StoredTransaction(
        id=row["id"],
        date=date.fromisoformat(row["date"]),
        amount=_from_cents(row["amount_cents"]),
        category=Category(row["category"]),
        description=row["description"],
        source=row["source"],
        invoice=date.fromisoformat(row["invoice"]),
        category_source=row["category_source"],
        note=row["note"],
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
) -> list[StoredTransaction]:
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
    return {Category(r["category"]): _from_cents(r["cents"]) for r in rows}
