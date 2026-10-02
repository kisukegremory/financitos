import json
import random

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from home.apps.tarot import cards
from home.apps.tarot.api import get_writer
from home.apps.tarot.llm import PhraseWriter
from home.core.config import Settings, get_settings
from home.main import app
from tests.financitos.test_core import fake_client

BASE = "/api/tarot"


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        openrouter_api_key=SecretStr("x"),
        database_url=f"sqlite:///{tmp_path}/tarot.db",
        _env_file=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_writer] = lambda: PhraseWriter(
        settings, client=fake_client(json.dumps({"items": [{"text": "O que pesa também ensina."}]}))
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_phrase_crud(client):
    created = client.post(f"{BASE}/phrases", json={"text": " Tudo passa. ", "author": "Chico"})
    assert created.status_code == 201
    p = created.json()
    assert p["text"] == "Tudo passa." and p["origin"] == "manual" and p["favorite"] is False

    updated = client.put(f"{BASE}/phrases/{p['id']}", json={"favorite": True, "author": ""}).json()
    assert updated["favorite"] is True and updated["author"] is None

    assert len(client.get(f"{BASE}/phrases", params={"q": "passa"}).json()) == 1
    assert client.get(f"{BASE}/phrases", params={"favorite": False}).json() == []
    assert client.delete(f"{BASE}/phrases/{p['id']}").status_code == 204
    assert client.put(f"{BASE}/phrases/{p['id']}", json={"note": "x"}).status_code == 404


def test_generate_does_not_save(client):
    client.post(f"{BASE}/phrases", json={"text": "Tudo passa.", "favorite": True})
    resp = client.post(f"{BASE}/phrases/generate", json={"hint": "recomeço"}).json()
    assert resp == [{"text": "O que pesa também ensina.", "author": None}]
    assert len(client.get(f"{BASE}/phrases").json()) == 1


def test_base_prompt_default_and_update(client):
    assert "aforismos" in client.get(f"{BASE}/settings/base-prompt").json()["value"]
    client.put(f"{BASE}/settings/base-prompt", json={"value": "Seja estoico."})
    assert client.get(f"{BASE}/settings/base-prompt").json() == {"value": "Seja estoico."}


def test_cards(client):
    all_cards = client.get(f"{BASE}/cards").json()
    assert len(all_cards) == 78 and len({c["id"] for c in all_cards}) == 78
    assert sum(c["arcana"] == "major" for c in all_cards) == 22
    drawn = client.get(f"{BASE}/cards/draw").json()
    assert drawn["card"]["id"] in {c["id"] for c in all_cards}
    assert isinstance(drawn["reversed"], bool)


def test_draw_is_seedable():
    assert cards.draw(random.Random(1)) == cards.draw(random.Random(1))


def use_reader(choice: dict):
    from home.apps.tarot.api import get_reader
    from home.apps.tarot.llm import Reader

    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_reader] = lambda: Reader(
        settings, client=fake_client(json.dumps(choice))
    )


def test_reading_picks_saved_phrase(client):
    p = client.post(f"{BASE}/phrases", json={"text": "Tudo passa."}).json()
    use_reader({"phrase_id": p["id"], "why": "porque passa", "card_reading": "a carta diz"})

    reading = client.post(f"{BASE}/readings", json={"feeling": "ansioso"})
    assert reading.status_code == 201
    r = reading.json()
    assert r["phrase"]["text"] == "Tudo passa." and r["generated_text"] is None
    assert r["why"] == "porque passa" and r["draw"]["card"]["id"]

    client.delete(f"{BASE}/phrases/{p['id']}")
    (listed,) = client.get(f"{BASE}/readings").json()
    assert listed["phrase"] is None and listed["feeling"] == "ansioso"


def test_reading_with_unknown_id_falls_back_to_new_phrase(client):
    use_reader({"phrase_id": 999, "new_phrase": "Respira.", "why": "w", "card_reading": "c"})
    r = client.post(f"{BASE}/readings", json={"feeling": "cansado"}).json()
    assert r["phrase"] is None and r["generated_text"] == "Respira."


def test_reading_without_any_phrase_is_an_error(client):
    use_reader({"phrase_id": 999, "why": "w", "card_reading": "c"})
    assert client.post(f"{BASE}/readings", json={"feeling": "x"}).status_code == 502
    assert client.get(f"{BASE}/readings").json() == []
