import json

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from home.apps.financitos.api import get_categorizer
from home.apps.financitos.llm import Categorizer
from home.core.config import Settings, get_settings
from home.main import app
from tests.financitos.test_core import fake_client

ITEM = {"date": "2026-09-15", "amount": 42.9, "category": "Mercado", "description": "SONDA"}


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        openrouter_api_key=SecretStr("x"),
        database_url=f"sqlite:///{tmp_path}/api.db",
        api_token=SecretStr("secret"),
        _env_file=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_categorizer] = lambda: Categorizer(
        settings, client=fake_client(json.dumps({"items": [ITEM]}))
    )
    with TestClient(app, headers={"Authorization": "Bearer secret"}) as c:
        yield c
    app.dependency_overrides.clear()


def test_requires_token(client):
    assert (
        client.get(
            "/api/financitos/transactions", headers={"Authorization": "Bearer nope"}
        ).status_code
        == 401
    )
    assert client.get("/api/health", headers={"Authorization": ""}).status_code == 200


def test_parse_save_and_summary(client):
    body = {"text": "fatura", "source": "PicPay", "invoice": "2026-10", "save": True}
    resp = client.post("/api/financitos/parse", json=body).json()
    assert resp["inserted"] == 1 and resp["total"] == "42.90"

    summary = client.get("/api/financitos/invoices/2026-10/summary").json()
    assert summary["categories"] == [
        {"category": "Mercado", "total": "42.90", "paid": "0.00", "remaining": "42.90"}
    ]

    paid = client.post("/api/financitos/invoices/2026-10/pay", json={"source": "PicPay"}).json()
    assert [p["amount"] for p in paid] == ["42.90"]
    assert client.get("/api/financitos/invoices/2026-10/summary").json()["remaining"] == "0.00"

    (payment,) = client.get("/api/financitos/payments", params={"invoice": "2026-10"}).json()
    assert client.delete(f"/api/financitos/payments/{payment['id']}").status_code == 204
    assert client.get("/api/financitos/invoices/2026-10/summary").json()["remaining"] == "42.90"


def test_crud(client):
    created = client.post(
        "/api/financitos/transactions", json={**ITEM, "source": "Nubank", "invoice": "2026-10"}
    ).json()
    assert created["invoice"] == "2026-10-01"

    updated = client.put(
        f"/api/financitos/transactions/{created['id']}", json={"category": "Casa"}
    ).json()
    assert updated["category"] == "Casa" and updated["category_source"] == "manual"

    assert (
        len(client.get("/api/financitos/transactions", params={"invoice": "2026-10"}).json()) == 1
    )
    assert client.delete(f"/api/financitos/transactions/{created['id']}").status_code == 204
    assert client.get(f"/api/financitos/transactions/{created['id']}").status_code == 404


def test_rejects_bad_invoice(client):
    assert client.get("/api/financitos/invoices/2026-1/summary").status_code == 422


def test_bulk_save_skips_duplicates(client):
    items = [{**ITEM, "source": "PicPay", "invoice": "2026-10"}] * 2
    assert client.post("/api/financitos/transactions/bulk", json=items).json() == {
        "inserted": 2,
        "skipped": 0,
    }
    assert client.post("/api/financitos/transactions/bulk", json=items).json() == {
        "inserted": 0,
        "skipped": 2,
    }


def test_bulk_keeps_manual_category_source(client):
    item = {**ITEM, "source": "PicPay", "invoice": "2026-10", "category_source": "manual"}
    client.post("/api/financitos/transactions/bulk", json=[item])
    assert client.get("/api/financitos/transactions").json()[0]["category_source"] == "manual"


def test_balances(client):
    assert len(client.get("/api/financitos/balances").json()) == 10
    resp = client.put(
        "/api/financitos/balances/Higiene e Estética", json={"amount": "250.5"}
    ).json()
    assert resp["amount"] == "250.50"
    assert client.put("/api/financitos/balances/Lazer", json={"amount": 1}).status_code == 422


def test_spa_fallback(tmp_path):
    from fastapi import FastAPI

    from home.main import mount_web

    (tmp_path / "index.html").write_text("<html>spa</html>")
    (tmp_path / "logo.svg").write_text("<svg/>")
    web = FastAPI()
    mount_web(web, tmp_path)
    c = TestClient(web)
    assert c.get("/tarot").text == "<html>spa</html>"
    assert c.get("/logo.svg").text == "<svg/>"
    assert c.get("/../pyproject.toml").text == "<html>spa</html>"
    assert c.get("/api/nope").status_code == 404
