import json

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from financitos.api import app, get_categorizer
from financitos.config import Settings, get_settings
from financitos.llm import Categorizer
from tests.test_core import fake_client

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
        client.get("/api/transactions", headers={"Authorization": "Bearer nope"}).status_code == 401
    )
    assert client.get("/api/health", headers={"Authorization": ""}).status_code == 200


def test_parse_save_and_summary(client):
    body = {"text": "fatura", "source": "PicPay", "invoice": "2026-10", "save": True}
    resp = client.post("/api/parse", json=body).json()
    assert resp["inserted"] == 1 and resp["total"] == "42.90"

    summary = client.get("/api/invoices/2026-10/summary").json()
    assert summary["categories"] == [{"category": "Mercado", "total": "42.90"}]


def test_crud(client):
    created = client.post(
        "/api/transactions", json={**ITEM, "source": "Nubank", "invoice": "2026-10"}
    ).json()
    assert created["invoice"] == "2026-10-01"

    updated = client.put(f"/api/transactions/{created['id']}", json={"category": "Casa"}).json()
    assert updated["category"] == "Casa" and updated["category_source"] == "manual"

    assert len(client.get("/api/transactions", params={"invoice": "2026-10"}).json()) == 1
    assert client.delete(f"/api/transactions/{created['id']}").status_code == 204
    assert client.get(f"/api/transactions/{created['id']}").status_code == 404


def test_rejects_bad_invoice(client):
    assert client.get("/api/invoices/2026-1/summary").status_code == 422


def test_bulk_save_skips_duplicates(client):
    items = [{**ITEM, "source": "PicPay", "invoice": "2026-10"}] * 2
    assert client.post("/api/transactions/bulk", json=items).json() == {"inserted": 2, "skipped": 0}
    assert client.post("/api/transactions/bulk", json=items).json() == {"inserted": 0, "skipped": 2}
