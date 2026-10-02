import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import SecretStr, ValidationError

from home.apps.financitos.llm import Categorizer
from home.apps.financitos.models import Category, ParsedItem, Transaction
from home.apps.financitos.output import render
from home.core.config import Settings


def fake_client(*payloads: str):
    calls = iter(payloads)

    def create(**kwargs):
        content = next(calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def settings(**kw) -> Settings:
    return Settings(openrouter_api_key=SecretStr("x"), _env_file=None, **kw)


ITEM = {
    "date": "2026-09-15",
    "amount": 42.9,
    "category": "Mercado",
    "description": "SUPERMERCADO XPTO",
}


def test_rejects_unknown_category():
    with pytest.raises(ValidationError):
        ParsedItem(**{**ITEM, "category": "Lazer"})


def test_categorizer_parses_json():
    c = Categorizer(settings(), client=fake_client(json.dumps({"items": [ITEM]})))
    result = c.parse("texto", date(2026, 10, 1))
    assert result.items[0].amount == Decimal("42.90")
    assert result.items[0].category is Category.MERCADO


def test_categorizer_uses_fallback():
    c = Categorizer(
        settings(openrouter_fallback_model="other"),
        client=fake_client("not json", json.dumps({"items": [ITEM]})),
    )
    assert len(c.parse("texto", date(2026, 10, 1)).items) == 1


def test_render_formats_brazilian_output():
    t = Transaction(**ITEM, source="PicPay", invoice=date(2026, 10, 1))
    out = render([t], "tsv")
    assert out.splitlines()[1] == "15/09/2026\t42,90\tMercado\tSUPERMERCADO XPTO\tPicPay\t2026-10"
