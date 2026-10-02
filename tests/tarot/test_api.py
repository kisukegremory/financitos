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
    assert resp == [{"text": "O que pesa também ensina.", "author": None, "source": None}]
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


SENECA = {"name": "Sêneca", "era": "Roma, séc. I", "why": "w", "works": ["Cartas a Lucílio"]}
QUOTE = {"text": "Sofremos mais na imaginação.", "author": None, "source": "Cartas a Lucílio"}


def routing_client(choice: dict, thinker: dict | None):
    """Fake da LLM que responde conforme o prompt (as duas chamadas da leitura são paralelas)."""
    from types import SimpleNamespace

    def create(messages, **kwargs):
        if "UM pensador" in messages[0]["content"]:
            if thinker is None:
                raise RuntimeError("fora do ar")
            payload = thinker
        else:
            payload = choice
        msg = SimpleNamespace(content=json.dumps(payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def use_reader(choice: dict, thinker: dict | None = None):
    from home.apps.tarot.api import get_reader
    from home.apps.tarot.llm import Reader

    if thinker is None:
        thinker = {"thinker": SENECA, "quotes": [QUOTE]}
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_reader] = lambda: Reader(
        settings, client=routing_client(choice, thinker or None)
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


def use_writer(*payloads: dict):
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_writer] = lambda: PhraseWriter(
        settings, client=fake_client(*(json.dumps(p) for p in payloads))
    )


def test_generate_quote_keeps_author_and_source(client):
    quote = {"text": "Conhece teu inimigo.", "author": "Sun Tzu", "source": "A Arte da Guerra"}
    use_writer({"items": [{"text": "inventada"}, quote]})
    body = {"mode": "quote", "thinker": "Sun Tzu", "hint": "estratégia", "count": 1}
    (s,) = client.post(f"{BASE}/phrases/generate", json=body).json()
    assert s == quote

    saved = client.post(f"{BASE}/phrases", json={**s, "origin": "ai"}).json()
    assert saved["source"] == "A Arte da Guerra"
    assert len(client.get(f"{BASE}/phrases", params={"q": "Arte da"}).json()) == 1


def test_generate_inspired_requires_thinker(client):
    resp = client.post(f"{BASE}/phrases/generate", json={"mode": "inspired", "thinker": " "})
    assert resp.status_code == 422


def test_recommend_thinkers(client):
    thinker = {"name": "Sêneca", "era": "Roma, séc. I", "why": "w", "works": ["Cartas a Lucílio"]}
    use_writer({"items": [thinker]})
    assert client.post(f"{BASE}/thinkers/recommend", json={"topic": "ansiedade"}).json() == [
        thinker
    ]


def test_mode_prompts():
    from home.apps.tarot.llm import build_messages
    from home.apps.tarot.models import GenerateMode

    msgs = build_messages("base", "tema", 2, ["ex"], GenerateMode.QUOTE, "Platão")
    assert "REAIS" in msgs[0]["content"] and "Platão" in msgs[0]["content"]
    assert "ex" not in msgs[1]["content"]  # exemplos de tom só no modo original
    assert "base" not in msgs[0]["content"]  # prompt base (frases inéditas) fica de fora


def test_reading_brings_thinker_quotes(client):
    use_reader({"new_phrase": "Respira.", "why": "w", "card_reading": "c"})
    r = client.post(f"{BASE}/readings", json={"feeling": "ansioso"}).json()
    assert r["thinker"]["name"] == "Sêneca"
    assert r["quotes"] == [{**QUOTE, "author": "Sêneca"}]  # autor preenchido com o pensador
    (listed,) = client.get(f"{BASE}/readings").json()
    assert listed["thinker"] == r["thinker"] and listed["quotes"] == r["quotes"]


def test_reading_survives_thinker_failure(client):
    use_reader({"new_phrase": "Respira.", "why": "w", "card_reading": "c"}, thinker={})
    r = client.post(f"{BASE}/readings", json={"feeling": "ansioso"})
    assert r.status_code == 201
    assert r.json()["thinker"] is None and r.json()["quotes"] == []
