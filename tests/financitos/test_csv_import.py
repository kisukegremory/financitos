import json
from datetime import date
from decimal import Decimal

import pytest

from home.apps.financitos import csv_import, db
from home.apps.financitos.llm import Categorizer
from home.apps.financitos.models import Category, Transaction, TransactionUpdate
from tests.financitos.test_core import fake_client, settings

NUBANK = '''date,title,amount
2026-11-10,Dl *Uberrides,"13,97"
2026-11-10,Dl *Uberrides,"13,97"
2026-10-28,"IOF de ""Hostinger.Com""","4,95"
2026-10-27,Pagamento recebido,"-1.500,00"
2026-10-26,Estorno Loja,"-19,90"
2026-10-25,Loja Cara,"1.234,56"
'''


def test_parse_nubank():
    rows = csv_import.parse_nubank(NUBANK)
    assert [r.description for r in rows] == [
        "Dl *Uberrides",
        "Dl *Uberrides",
        'IOF de "Hostinger.Com"',
        "Estorno Loja",
        "Loja Cara",
    ]
    assert rows[0].date == date(2026, 11, 10)
    assert [r.amount for r in rows[2:]] == [Decimal("4.95"), Decimal("-19.90"), Decimal("1234.56")]


def test_parse_nubank_rejects_other_format():
    with pytest.raises(csv_import.CsvError):
        csv_import.parse_nubank("Data;Valor\n01/10/2026;10,00\n")


def test_invoice_from_filename():
    assert csv_import.invoice_from_filename("Nubank_2026-12-16.csv") == "2026-12"
    assert csv_import.invoice_from_filename("fatura.csv") is None


def test_categorize_uses_history_and_dedupes(tmp_path):
    conn = db.connect(f"sqlite:///{tmp_path}/t.db")
    db.save(
        conn,
        [
            Transaction(
                date=date(2026, 9, 1),
                amount=Decimal("10"),
                description="Dl *Uberrides",
                category=Category.PESSOAL,
                source="Nubank",
                invoice=date(2026, 9, 1),
            )
        ],
    )
    (old,) = db.list_transactions(conn)
    db.update(conn, old.id, TransactionUpdate(category=Category.VIAGEM))  # correção manual

    rows = csv_import.parse_nubank(NUBANK)
    known = db.known_categories(conn, (r.description for r in rows), "Nubank")
    assert known == {"Dl *Uberrides": Category.VIAGEM}

    sent = []
    llm_reply = {
        "items": [{"i": 0, "category": "Contas e assinaturas"}, {"i": 2, "category": "Casa"}]
    }
    categorizer = Categorizer(settings(), client=fake_client(json.dumps(llm_reply)))
    original = categorizer.categorize
    categorizer.categorize = lambda entries: sent.append(entries) or original(entries)

    categories, from_llm = csv_import.categorize(rows, known, categorizer)
    assert from_llm == 3  # Uber veio do histórico; o resto, deduplicado, numa chamada só
    assert [d for d, _ in sent[0]] == ['IOF de "Hostinger.Com"', "Estorno Loja", "Loja Cara"]

    items = csv_import.to_transactions([(date(2026, 12, 1), rows)], categories, "Nubank")
    assert [t.category for t in items] == [
        Category.VIAGEM,
        Category.VIAGEM,
        Category.CONTAS_ASSINATURAS,
        csv_import.FALLBACK_CATEGORY,  # LLM não respondeu o índice 1
        Category.CASA,
    ]


def test_categorize_skips_llm_when_all_known():
    rows = csv_import.parse_nubank(NUBANK)
    known = {r.description: Category.CASA for r in rows}
    categorizer = Categorizer(settings(), client=fake_client())  # qualquer chamada quebraria
    categories, from_llm = csv_import.categorize(rows, known, categorizer)
    assert from_llm == 0 and categories == known
