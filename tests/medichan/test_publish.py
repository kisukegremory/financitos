import io
import math
import struct
import wave

import pytest
from pydantic import SecretStr

from home.apps.medichan import render
from home.core.config import get_settings
from home.main import app
from tests.medichan.test_api import BASE, setup  # noqa: F401 (fixture)


def tone_wav(seconds: float, rate: int = 24000) -> bytes:
    n = int(seconds * rate)
    frames = b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / rate))) for i in range(n)
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


def test_voice_track_timing(tmp_path):
    a = tmp_path / "a.wav"
    a.write_bytes(tone_wav(1))
    parts = [
        render.Part("speech", a),
        render.Part("speech", a),
        render.Part("pause", seconds=5),
        render.Part("speech", a),
    ]
    seconds = len(render.voice_track(parts)) / render.BYTES_PER_SEC
    expected = render.LEAD + 1 + render.GAP + 1 + 5 + 1 + render.TAIL
    assert seconds == pytest.approx(expected, abs=0.05)


@pytest.fixture
def published(setup):  # noqa: F811
    c = setup.client
    m = c.post(f"{BASE}/meditations", json={"feeling": "ansioso", "voice": "gemini"}).json()
    # o fake de TTS grava bytes inválidos: troca por áudio de verdade para o ffmpeg
    for f in (setup.root).glob("*/*.wav"):
        f.write_bytes(tone_wav(0.5))
    return setup, m


def test_publish_flow(published):
    env, m = published
    c = env.client
    resp = c.post(
        f"{BASE}/meditations/{m['id']}/publish",
        json={"summary": " Para decidir com calma ", "tags": [" Ansiedade "]},
    )
    assert resp.status_code == 201, resp.text
    item = resp.json()
    assert item["slug"] == "antes-de-decidir" and item["access"] == "free"
    assert item["tags"] == ["ansiedade"] and item["summary"] == "Para decidir com calma"
    assert item["duration_s"] == pytest.approx(render.LEAD + 0.5 + 60 + 0.5 + render.TAIL, abs=0.2)

    cat = c.get(f"{BASE}/public/catalog.json").json()
    assert cat["schema_version"] == 1
    entry = cat["items"][0]
    assert entry["audio"] == {
        "ogg": "antes-de-decidir/audio.ogg",
        "m4a": "antes-de-decidir/audio.m4a",
    }
    assert "meditation_id" not in entry  # origem fica só no estúdio

    for name, ctype in (("audio.ogg", "audio/ogg"), ("audio.m4a", "audio/mp4")):
        r = c.get(f"{BASE}/public/antes-de-decidir/{name}")
        assert r.status_code == 200 and r.headers["content-type"] == ctype
    ranged = c.get(f"{BASE}/public/antes-de-decidir/audio.ogg", headers={"Range": "bytes=0-99"})
    assert ranged.status_code == 206 and len(ranged.content) == 100
    assert c.get(f"{BASE}/public/antes-de-decidir/x.mp3").status_code == 404

    # republicar com o mesmo slug substitui; apagar a origem não derruba a publicada
    c.post(f"{BASE}/meditations/{m['id']}/publish", json={"access": "private"})
    assert [p["access"] for p in c.get(f"{BASE}/published").json()] == ["private"]
    c.delete(f"{BASE}/meditations/{m['id']}")
    assert c.get(f"{BASE}/public/antes-de-decidir/audio.m4a").status_code == 200

    assert c.delete(f"{BASE}/published/antes-de-decidir").status_code == 204
    assert c.get(f"{BASE}/public/catalog.json").json()["items"] == []
    assert not (env.root / "public" / "antes-de-decidir").exists()


def test_private_needs_token(published):
    env, m = published
    c = env.client
    c.post(f"{BASE}/meditations/{m['id']}/publish", json={"slug": "so-meu", "access": "private"})
    settings = app.dependency_overrides[get_settings]()
    settings.api_token = SecretStr("t")
    assert c.get(f"{BASE}/public/catalog.json").status_code == 200  # catálogo é aberto
    assert c.get(f"{BASE}/public/so-meu/audio.m4a").status_code == 401
    ok = c.get(f"{BASE}/public/so-meu/audio.m4a", headers={"Authorization": "Bearer t"})
    assert ok.status_code == 200


def test_publish_errors(published):
    env, m = published
    c = env.client
    assert c.post(f"{BASE}/meditations/999/publish", json={}).status_code == 404
    bad_track = c.post(f"{BASE}/meditations/{m['id']}/publish", json={"track_id": 7})
    assert bad_track.status_code == 422
    assert (
        c.post(f"{BASE}/meditations/{m['id']}/publish", json={"slug": "Não Vale"}).status_code
        == 422
    )
