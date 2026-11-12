import base64
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from home.apps.medichan import db, music
from home.apps.medichan.api import get_composer
from home.apps.medichan.music import Composer, build_prompt, mp3_seconds
from home.core import db as core_db
from home.core.config import Settings, get_settings
from home.main import app

BASE = "/api/medichan"

# MP3 mínimo: tag ID3 vazia + cabeçalho de frame MPEG-1 L3 a 192 kbps + 24 kB (= 1 s)
FAKE_MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\xb0\x00" + bytes(24000 - 4)


def lyria(results: list[bytes | None], calls: list[dict]):
    """Fake do Lyria: stream com '<instrumental>' e depois o MP3 em base64 (ou nada)."""
    outputs = iter(results)

    def chunk(**delta_extra):
        delta = SimpleNamespace(content=None, model_extra=delta_extra)
        return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

    def create(**kwargs):
        calls.append(kwargs)
        mp3 = next(outputs)
        yield chunk()
        if mp3 is not None:
            yield chunk(audio={"data": base64.b64encode(mp3).decode()})

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


@pytest.fixture
def setup(tmp_path):
    settings = Settings(
        openrouter_api_key=SecretStr("x"),
        database_url=f"sqlite:///{tmp_path}/home.db",
        _env_file=None,
    )
    calls: list[dict] = []
    state = {"results": [FAKE_MP3] * 5}
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_composer] = lambda: Composer(
        settings, client=lyria(state["results"], calls)
    )
    with TestClient(app) as c:
        yield SimpleNamespace(client=c, calls=calls, state=state, tmp=tmp_path, settings=settings)
    app.dependency_overrides.clear()


def test_compose_in_background(setup):
    c = setup.client
    resp = c.post(f"{BASE}/music", json={"kind": "pro", "preset": "oceano"})
    assert resp.status_code == 202 and resp.json()["status"] == "pending"
    # o TestClient roda a tarefa de fundo antes de devolver a resposta
    track = c.get(f"{BASE}/music").json()[0]
    assert track["status"] == "ready" and track["title"] == "Oceano"
    assert track["seconds"] == 1.0 and track["cost_usd"] == 0.08
    assert setup.calls[0]["model"] == "google/lyria-3-pro-preview"
    assert "no vocals" in setup.calls[0]["messages"][0]["content"]

    audio = c.get(track["audio"])
    assert audio.status_code == 200 and audio.content == FAKE_MP3

    assert c.delete(f"{BASE}/music/{track['id']}").status_code == 204
    assert c.get(track["audio"]).status_code == 404


def test_retries_when_stream_has_no_audio(setup):
    setup.state["results"] = [None, FAKE_MP3]
    setup.client.post(f"{BASE}/music", json={"preset": "chuva"})
    track = setup.client.get(f"{BASE}/music").json()[0]
    assert track["status"] == "ready" and len(setup.calls) == 2
    assert track["cost_usd"] == 0.04  # clip


def test_failure_is_recorded(setup):
    setup.state["results"] = [None, None]
    setup.client.post(f"{BASE}/music", json={"extra": "rain on a tin roof"})
    track = setup.client.get(f"{BASE}/music").json()[0]
    assert track["status"] == "error" and "não devolveu" in track["error"]
    assert track["title"] == "rain on a tin roof" and track["audio"] is None


def test_validation(setup):
    assert setup.client.post(f"{BASE}/music", json={}).status_code == 422
    assert setup.client.post(f"{BASE}/music", json={"preset": "nope"}).status_code == 422


def test_stale_pending_becomes_error(setup):
    conn = core_db.connect(setup.settings.database_url)
    track = db.create_track(conn, "x", "pro", None, "p")
    conn.execute(
        "UPDATE medichan_tracks SET created_at = '2020-01-01T00:00:00Z' WHERE id = ?", (track.id,)
    )
    conn.commit()
    assert db.list_tracks(conn)[0].status == "error"
    conn.close()


def test_catalog_and_prompt(setup):
    catalog = setup.client.get(f"{BASE}/music/catalog").json()
    assert {p["id"] for p in catalog["presets"]} == set(music.PRESETS)
    assert catalog["prices"] == {"clip": 0.04, "pro": 0.08}
    assert "tibetan singing bowls, long resonant tones, soft drone, with rain." in build_prompt(
        "tigelas", " with rain "
    )


def test_mp3_seconds():
    assert mp3_seconds(FAKE_MP3) == 1.0
    assert mp3_seconds(b"not an mp3") is None
