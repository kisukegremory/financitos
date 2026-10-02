from datetime import date
from decimal import Decimal

import pytest

from financitos import db
from financitos.models import Category, Transaction

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
    assert rows == [tx("Sonda", "191.27")]


def test_summary_by_category(conn):
    db.save(conn, [tx("A", "10.50"), tx("B", "5.25"), tx("C", "3.00", "Saúde")])
    assert db.summary(conn, INVOICE) == {
        Category.MERCADO: Decimal("15.75"),
        Category.SAUDE: Decimal("3.00"),
    }
