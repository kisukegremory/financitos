import array
import base64
import io
import json
import wave
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from home.apps.medichan.api import get_speaker, get_writer
from home.apps.medichan.llm import ScriptWriter
from home.apps.medichan.models import Script
from home.apps.medichan.tts import VOICES, Speaker, trim_silence
from home.core.config import Settings, get_settings
from home.main import app
from tests.financitos.test_core import fake_client

BASE = "/api/medichan"

SCRIPT = {
    "title": "Antes de decidir",
    "segments": [
        {"kind": "speech", "text": "Respire fundo..."},
        {"kind": "pause", "seconds": 120},
        {"kind": "speech", "text": "   "},
        {"kind": "speech", "text": "O que você já sabe?"},
    ],
}


def fake_tts(calls: list[dict], fail: bool = False):
    def create(**kwargs):
        if fail:
            raise RuntimeError("boom")
        calls.append(kwargs)
        return SimpleNamespace(content=b"\x00\x01" * 10)

    return SimpleNamespace(audio=SimpleNamespace(speech=SimpleNamespace(create=create)))


@pytest.fixture
def setup(tmp_path):
    settings = Settings(
        openrouter_api_key=SecretStr("x"),
        database_url=f"sqlite:///{tmp_path}/home.db",
        _env_file=None,
    )
    calls: list[dict] = []
    state = {"fail": False}
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_writer] = lambda: ScriptWriter(
        settings, client=fake_client(json.dumps(SCRIPT))
    )
    app.dependency_overrides[get_speaker] = lambda: Speaker(
        settings, client=fake_tts(calls, state["fail"])
    )
    with TestClient(app) as c:
        yield SimpleNamespace(client=c, calls=calls, state=state, root=tmp_path / "medichan")
    app.dependency_overrides.clear()


def test_script_cleans_segments():
    script = Script.model_validate(SCRIPT)
    assert [s.kind for s in script.segments] == ["speech", "pause", "speech"]
    assert script.segments[1].seconds == 60  # pausa limitada
    with pytest.raises(ValidationError):
        Script.model_validate({"title": "x", "segments": [{"kind": "pause", "seconds": 5}]})


def test_create_and_play(setup):
    c = setup.client
    resp = c.post(f"{BASE}/meditations", json={"feeling": " ansioso ", "voice": "gemini"})
    assert resp.status_code == 201
    m = resp.json()
    assert m["feeling"] == "ansioso" and m["title"] == "Antes de decidir"
    assert [s["audio"] is not None for s in m["segments"]] == [True, False, True]
    assert len(setup.calls) == 2 and all(k["response_format"] == "pcm" for k in setup.calls)
    # Gemini cobra texto + segundos de áudio: 2 falas de 10 amostras a 24 kHz
    chars = len("Respire fundo...") + len("O que você já sabe?")
    assert m["chars"] == chars
    assert m["cost_usd"] == round(VOICES["gemini"].cost(chars, 20 / 24000), 5)

    audio = c.get(m["segments"][0]["audio"])
    assert audio.status_code == 200 and audio.headers["content-type"] == "audio/wav"
    with wave.open(io.BytesIO(audio.content)) as w:  # PCM do Gemini virou WAV válido
        assert w.getframerate() == 24000 and w.getnframes() == 10

    assert c.get(f"{BASE}/meditations/{m['id']}/audio/1").status_code == 404  # pausa
    assert c.get(f"{BASE}/meditations/{m['id']}/audio/9").status_code == 404
    assert [x["id"] for x in c.get(f"{BASE}/meditations").json()] == [m["id"]]

    assert c.delete(f"{BASE}/meditations/{m['id']}").status_code == 204
    assert list(setup.root.iterdir()) == []
    assert c.get(f"{BASE}/meditations/{m['id']}").status_code == 404


def test_elevenlabs_is_mp3(setup):
    m = setup.client.post(
        f"{BASE}/meditations", json={"feeling": "cansado", "voice": "elevenlabs"}
    ).json()
    assert setup.calls[0]["model"].startswith("elevenlabs/")
    assert setup.calls[0]["extra_body"] == {"speed": 0.75}  # desacelerada
    assert setup.client.get(m["segments"][0]["audio"]).headers["content-type"] == "audio/mpeg"


def test_style_tags_are_billed(setup):
    m = setup.client.post(
        f"{BASE}/meditations", json={"feeling": "cansado", "voice": "eleven-v4"}
    ).json()
    assert setup.calls[0]["input"] == "[calm, soft, slow] Respire fundo..."
    assert m["cost_usd"] == round(m["chars"] / 1000 * 0.08, 5)


def test_unknown_voice(setup):
    resp = setup.client.post(f"{BASE}/meditations", json={"feeling": "x", "voice": "nope"})
    assert resp.status_code == 422


def test_tts_failure_saves_nothing(setup):
    setup.state["fail"] = True
    resp = setup.client.post(f"{BASE}/meditations", json={"feeling": "x"})
    assert resp.status_code == 502
    assert setup.client.get(f"{BASE}/meditations").json() == []
    assert not any(setup.root.iterdir())


def test_voices(setup):
    voices = setup.client.get(f"{BASE}/voices").json()
    assert {v["id"] for v in voices} == set(VOICES)
    by_id = {v["id"]: v for v in voices}
    assert by_id["mai-luana"]["pace"] == "lento"
    assert by_id["gemini"]["preview"] == "/medichan/voices/gemini.wav"
    # estimativa coerente: gpt-audio é a mais cara, Kokoro a mais barata
    ranked = sorted(voices, key=lambda v: v["estimate_usd"])
    assert ranked[0]["id"] == "kokoro-dora" and ranked[-1]["id"].startswith("gpt-audio-")


LOUD = array.array("h", [8000, -8000] * 12000).tobytes()  # 1 s de "voz"
QUIET = bytes(2 * 24000)  # 1 s de silêncio


def chat_tts(transcripts: list[str], calls: list[dict], silences: list[int] | None = None):
    """Fake do chat com áudio (gpt-audio): streaming de PCM + transcrição + custo no fim."""
    said = iter(transcripts)
    tails = iter(silences or [0] * len(transcripts))

    def create(**kwargs):
        calls.append(kwargs)
        pcm = base64.b64encode(LOUD + QUIET * next(tails)).decode()
        delta = SimpleNamespace(audio={"data": pcm, "transcript": next(said)}, model_extra={})
        yield SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=delta)])
        yield SimpleNamespace(usage=SimpleNamespace(model_extra={"cost": 0.01}), choices=[])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_chat_voice_reads_verbatim_with_real_cost():
    calls: list[dict] = []
    speaker = Speaker(
        Settings(openrouter_api_key=SecretStr("x"), _env_file=None),
        client=chat_tts(["Respire, fundo!"], calls),
    )
    spoken = speaker.speak("Respire fundo...", "gpt-audio-marin")
    assert calls[0]["audio"] == {"voice": "marin", "format": "pcm16"}
    assert spoken.cost_usd == 0.01 and spoken.seconds == 1
    assert calls[0]["max_tokens"] < 1000  # teto proporcional ao texto
    with wave.open(io.BytesIO(spoken.audio)) as w:
        assert w.getframerate() == 24000


def test_chat_voice_retries_when_it_improvises():
    calls: list[dict] = []
    speaker = Speaker(
        Settings(openrouter_api_key=SecretStr("x"), _env_file=None),
        client=chat_tts(["Claro! Vamos meditar juntos hoje.", "Respire fundo"], calls),
    )
    spoken = speaker.speak("Respire fundo...", "gpt-audio-mini-ash")
    assert len(calls) == 2
    assert spoken.cost_usd == 0.02  # as duas tentativas são cobradas


def test_chat_voice_trims_silence_when_it_hangs():
    calls: list[dict] = []
    # 1ª tentativa: fala certa + 1 min de silêncio "travado"; 2ª: normal
    client = chat_tts(["Respire fundo", "Respire fundo"], calls, silences=[60, 0])
    speaker = Speaker(Settings(openrouter_api_key=SecretStr("x"), _env_file=None), client=client)
    spoken = speaker.speak("Respire fundo...", "gpt-audio-marin")
    assert len(calls) == 1  # silêncio no fim é cortado, sem precisar repetir
    assert spoken.seconds == 1.5  # fala + 0,5 s de respiro


def test_trim_silence_keeps_speech():
    pcm = QUIET + LOUD + QUIET * 30
    assert len(trim_silence(pcm)) == len(QUIET + LOUD) + 24000  # +0,5 s
    assert trim_silence(QUIET * 3) == bytes(24000)  # só silêncio: sobra o respiro


def test_trim_silence_ignores_late_click():
    click = array.array("h", [1000, -1000] * 600).tobytes()  # estalo de 50 ms, baixo
    pcm = LOUD + QUIET * 20 + click + QUIET
    assert len(trim_silence(pcm)) == len(LOUD) + 24000
