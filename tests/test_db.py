from datetime import date
from decimal import Decimal

import pytest

from financitos import db
from financitos.models import Category, Transaction, TransactionUpdate

INVOICE = date(2026, 10, 1)


def tx(desc: str, amount: str, category: str = "Mercado", day: int = 15) -> Transaction:
    return Transaction(
        date=date(2026, 9, day),
        amount=Decimal(amount),
        category=category,
        description=desc,
        source="PicPay",
        invoice=INVOICE,
    )


@pytest.fixture
def conn(tmp_path):
    c = db.connect(f"sqlite:///{tmp_path}/test.db")
    yield c
    c.close()


def test_save_keeps_identical_purchases_and_skips_reimport(conn):
    batch = [tx("Shimizu Comercial", "19.00", "Casa"), tx("Shimizu Comercial", "19.00", "Casa")]
    assert db.save(conn, batch) == db.SaveResult(inserted=2, skipped=0)
    assert db.save(conn, batch) == db.SaveResult(inserted=0, skipped=2)


def test_list_roundtrip_and_filters(conn):
    db.save(conn, [tx("Sonda", "191.27"), tx("Spotify", "40.90", "Contas e assinaturas")])
    rows = db.list_transactions(conn, INVOICE, "picpay", Category.MERCADO)
    assert [Transaction(**r.model_dump(exclude={"id", "category_source"})) for r in rows] == [
        tx("Sonda", "191.27")
    ]


def test_summary_by_category(conn):
    db.save(conn, [tx("A", "10.50"), tx("B", "5.25"), tx("C", "3.00", "Saúde")])
    s = db.summary(conn, INVOICE)
    assert [(c.category, c.total) for c in s.categories] == [
        (Category.MERCADO, Decimal("15.75")),
        (Category.SAUDE, Decimal("3.00")),
    ]
    assert s.total == s.remaining == Decimal("18.75")


def test_early_payment_then_new_transactions(conn):
    db.save(conn, [tx("A", "100.00"), tx("B", "20.00", "Saúde")])
    paid = db.pay_remaining(conn, INVOICE, "PicPay")
    assert sum(p.amount for p in paid) == Decimal("120.00")
    assert db.summary(conn, INVOICE).remaining == 0

    # fatura ainda aberta: entra uma compra nova depois do pagamento antecipado
    db.save(conn, [tx("C", "30.00", day=20)])
    s = db.summary(conn, INVOICE)
    mercado = next(c for c in s.categories if c.category is Category.MERCADO)
    assert (mercado.total, mercado.paid, mercado.remaining) == (
        Decimal("130.00"),
        Decimal("100.00"),
        Decimal("30.00"),
    )
    assert [p.amount for p in db.pay_remaining(conn, INVOICE, "PicPay")] == [Decimal("30.00")]
    assert db.pay_remaining(conn, INVOICE, "PicPay") == []


def test_update_category_marks_manual_and_keeps_identical_rows_apart(conn):
    db.save(conn, [tx("Shimizu", "19.00", "Casa"), tx("Shimizu", "19.00", "Casa")])
    first, second = db.list_transactions(conn)
    updated = db.update(conn, first.id, TransactionUpdate(category=Category.PESSOAL))
    assert updated.category is Category.PESSOAL
    assert updated.category_source == "manual"
    assert db.get(conn, second.id).category is Category.CASA


def test_create_and_delete(conn):
    created = db.create(conn, tx("Manual", "7.00"))
    assert created.category_source == "manual"
    assert db.delete(conn, created.id)
    assert db.get(conn, created.id) is None


def test_note_set_and_clear(conn):
    db.save(conn, [tx("Abolicao", "58.00", "Pessoal")])
    (row,) = db.list_transactions(conn)
    assert (
        db.update(conn, row.id, TransactionUpdate(note="  bar com a Ana ")).note == "bar com a Ana"
    )
    assert (
        db.update(conn, row.id, TransactionUpdate(category=Category.PESSOAL)).note
        == "bar com a Ana"
    )
    assert db.update(conn, row.id, TransactionUpdate(note="")).note is None


def test_migrates_old_database_without_note(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(db.SCHEMA.replace("    note            TEXT,\n", ""))
    old.close()
    c = db.connect(f"sqlite:///{path}")
    assert "note" in {r["name"] for r in c.execute("PRAGMA table_info(transactions)")}
    c.close()


def test_balances_start_zeroed_and_update(conn):
    balances = db.list_balances(conn)
    assert [b.category for b in balances] == list(Category)
    assert all(b.amount == 0 and b.updated_at is None for b in balances)

    updated = db.set_balance(conn, Category.MERCADO, Decimal("1500.00"))
    assert updated.amount == Decimal("1500.00") and updated.updated_at
    assert db.set_balance(conn, Category.MERCADO, Decimal("1200.50")).amount == Decimal("1200.50")
