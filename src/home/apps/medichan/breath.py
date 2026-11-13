"""Técnicas de respiração com tempos fixos.

A LLM só escolhe a técnica e quantos ciclos; os tempos vêm daqui e viram falas curtas + pausas
exatas. Assim a retenção nunca passa do limite do perfil (antes a LLM inventava "segure..." com
pausas de até 8 s, somadas ao tempo da própria fala).

Base: respiração lenta/ressonante (~5,5-6 resp/min) aumenta a VFC e relaxa; expirações mais longas
que a inspiração favorecem o parassimpático; o suspiro cíclico (Balban et al., Cell Rep Med 2023)
melhorou o humor mais que mindfulness em 5 min/dia. Retenção (kumbhaka) se introduz aos poucos,
sem esforço, e para na primeira tontura: por isso fica curta e limitada pelo perfil.
"""

from dataclasses import dataclass

from home.apps.medichan.models import Segment

# fala da deixa ocupa ~1 s da fase; a pausa cobre o resto
CUE_SECONDS = 1
MIN_PAUSE = 1
DEFAULT_MAX_HOLD = 3


@dataclass(frozen=True)
class Technique:
    id: str
    label: str
    when: str  # para a LLM escolher
    inhale: int
    hold: int  # retenção com ar (0 = sem)
    exhale: int
    hold_out: int = 0  # retenção sem ar (só na quadrada)
    sigh: bool = False  # suspiro: segunda inspiração curta antes de soltar
    cycles: tuple[int, int] = (3, 5)


TECHNIQUES = {
    t.id: t
    for t in [
        Technique(
            "ressonante",
            "respiração ressonante (5 · 5)",
            "base neutra, cansaço, antes de dormir, para aterrissar no corpo",
            5,
            0,
            5,
        ),
        Technique(
            "expiracao_longa",
            "expiração alongada (4 · 6)",
            "ansiedade leve, agitação, raiva: soltar mais do que entra acalma",
            4,
            0,
            6,
        ),
        Technique(
            "suspiro",
            "suspiro cíclico (2 + 1 · 6)",
            "ansiedade forte, aperto no peito, estresse agudo",
            2,
            0,
            6,
            sigh=True,
            cycles=(3, 4),
        ),
        Technique(
            "quadrada_suave",
            "quadrada suave (4 · 2 · 4 · 2)",
            "falta de foco, mente dispersa, preparar uma decisão",
            4,
            2,
            4,
            hold_out=2,
        ),
        Technique(
            "pausa_cheia",
            "inspira, pausa breve, solta longo (4 · 3 · 6)",
            "recomeço, gratidão, quando quer sentir o corpo cheio e depois esvaziar",
            4,
            3,
            6,
        ),
    ]
}

CUES = {
    "inhale": ("Inspire pelo nariz, devagar…", "Inspire…"),
    "sigh": ("E mais um pouquinho de ar, por cima…", "Mais um pouco…"),
    "hold": ("Segure suavemente, sem esforço…", "Segure…"),
    "exhale": ("Solte devagar, pela boca…", "Solte…"),
    "hold_out": ("Fique um instante vazio…", "Vazio…"),
}


def catalog_for_prompt(max_hold: int) -> str:
    lines = []
    for t in TECHNIQUES.values():
        hold = min(t.hold, max_hold)
        lo, hi = t.cycles
        lines.append(
            f'- "{t.id}": {t.label}; use para {t.when}; {lo} a {hi} ciclos'
            + (f" (retenção limitada a {hold}s)" if t.hold else "")
        )
    return "\n".join(lines)


def expand(technique: str | None, cycles: int | None, max_hold: int) -> list[Segment]:
    """Transforma a técnica em falas curtas e pausas com os tempos certos."""
    t = TECHNIQUES.get(technique or "", TECHNIQUES["ressonante"])
    lo, hi = t.cycles
    n = min(max(cycles or lo, lo), hi)
    hold = min(t.hold, max_hold)
    hold_out = min(t.hold_out, max_hold)
    phases = [("inhale", t.inhale)]
    if t.sigh:
        phases.append(("sigh", 1 + CUE_SECONDS))  # ~1 s de ar extra
    if hold:
        phases.append(("hold", hold))
    phases.append(("exhale", t.exhale))
    if hold_out:
        phases.append(("hold_out", hold_out))

    out: list[Segment] = []
    for c in range(n):
        for name, seconds in phases:
            out.append(Segment(kind="speech", text=CUES[name][0 if c == 0 else 1]))
            out.append(Segment(kind="pause", seconds=max(seconds - CUE_SECONDS, MIN_PAUSE)))
    return out
