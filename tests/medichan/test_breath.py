import json

from home.apps.medichan import breath
from home.apps.medichan.llm import ScriptWriter, expand_breathing
from home.apps.medichan.models import Profile, Script
from home.apps.medichan.tts import Speaker
from tests.financitos.test_core import fake_client, settings
from tests.medichan.test_api import BASE, fake_tts, setup  # noqa: F401 (fixture)


def phase_seconds(segments):
    """Duração de cada fase = ~1 s da deixa falada + pausa seguinte."""
    return [
        (s.text, breath.CUE_SECONDS + segments[i + 1].seconds)
        for i, s in enumerate(segments)
        if s.kind == "speech" and i + 1 < len(segments) and segments[i + 1].kind == "pause"
    ]


def test_hold_never_exceeds_profile():
    for max_hold in (0, 2, 3, 10):
        for t in breath.TECHNIQUES.values():
            segs = breath.expand(t.id, 99, max_hold)
            holds = [sec for text, sec in phase_seconds(segs) if "egure" in text or "azio" in text]
            assert all(h <= max(max_hold, breath.CUE_SECONDS + breath.MIN_PAUSE) for h in holds)
            if max_hold == 0:
                assert holds == []


def test_cycles_are_clamped_and_cues_shorten():
    segs = breath.expand("expiracao_longa", 99, 3)
    lo, hi = breath.TECHNIQUES["expiracao_longa"].cycles
    texts = [s.text for s in segs if s.kind == "speech"]
    assert len(texts) == hi * 2
    assert texts[0] == "Inspire pelo nariz, devagar…" and texts[2] == "Inspire…"
    assert phase_seconds(segs)[:2] == [(texts[0], 4), (texts[1], 6)]
    assert breath.expand("nao-existe", None, 3)  # cai na ressonante


def test_writer_expands_breath_and_uses_profile():
    script = {
        "title": "t",
        "segments": [
            {"kind": "speech", "text": "Vamos respirar."},
            {"kind": "breath", "technique": "pausa_cheia", "cycles": 3},
            {"kind": "speech", "text": "Volte ao natural."},
        ],
    }
    w = ScriptWriter(settings(), client=fake_client(json.dumps(script)))
    out = w.write("ansioso", Profile(about="Trabalho com dados, tenho dois gatos.", max_hold=2))
    assert all(s.kind in ("speech", "pause") for s in out.segments)
    holds = [sec for text, sec in phase_seconds(out.segments) if "egure" in text]
    assert holds and all(h <= 2 for h in holds)


def test_expand_keeps_other_segments():
    s = Script.model_validate({"title": "x", "segments": [{"kind": "speech", "text": "oi"}]})
    assert expand_breathing(s, 3).segments == s.segments


def test_repeated_cues_are_synthesized_once(tmp_path):
    calls: list[dict] = []
    script = expand_breathing(
        Script.model_validate(
            {
                "title": "x",
                "segments": [
                    {"kind": "speech", "text": "oi"},
                    {"kind": "breath", "technique": "ressonante", "cycles": 5},
                ],
            }
        ),
        3,
    )
    syn = Speaker(settings(), client=fake_tts(calls)).synthesize(script, "gemini", tmp_path)
    assert len(calls) == 1 + 4  # oi + 2 deixas longas + 2 curtas
    files = [f for f in syn.files if f]
    assert len(files) == 1 + 10 and len(set(files)) == 5
    assert all((tmp_path / f).exists() for f in set(files))


def test_profile_roundtrip(setup):  # noqa: F811
    c = setup.client
    assert c.get(f"{BASE}/profile").json() == {"about": "", "max_hold": 3}
    saved = c.put(f"{BASE}/profile", json={"about": "Moro em SP.", "max_hold": 0}).json()
    assert saved == {"about": "Moro em SP.", "max_hold": 0}
    assert c.put(f"{BASE}/profile", json={"about": "", "max_hold": 30}).status_code == 422
    assert c.get(f"{BASE}/profile").json()["max_hold"] == 0
