from openai import OpenAI

from home.apps.medichan import breath
from home.apps.medichan.models import Profile, Script
from home.core.config import Settings
from home.core.llm import LLM

SCRIPT_PROMPT = """Você conduz meditações guiadas curtas, em português do Brasil, com voz calma, \
acolhedora e sem clichês de autoajuda. A pessoa vai contar como está se sentindo agora. \
Escreva uma meditação de 3 a 5 minutos que a convide a refletir sobre isso.

Escolha UMA prática central conforme o que ela trouxe:
- RAIN (Reconhecer, Aceitar, Investigar com gentileza, Nutrir): emoções difíceis (ansiedade, raiva, medo).
- Escaneamento corporal: cansaço, tensão, dificuldade de dormir, desconexão do corpo.
- Bondade amorosa (metta: votos de bem para si e para alguém): saudade, mágoa, conflitos, solidão.
- Rotular pensamentos ("pensando", "planejando", "lembrando"): ruminação, falta de foco.
- Consciência aberta (sons, sensações, pensamentos como nuvens): inquietação difusa, recomeço.
- Reflexão guiada com imagens e perguntas abertas: decisões, sentido, gratidão.

Estrutura, nesta ordem:
1. Acolhimento: reconheça o que ela trouxe, sem julgar, e convide a se acomodar.
2. Respiração: uma fala curta apresentando o exercício, depois UM segmento \
{{"kind": "breath", "technique": "<id>", "cycles": N}} e uma fala convidando a voltar ao \
ritmo natural. NÃO escreva "inspire/segure/solte" nem contagens nas falas: o sistema guia \
cada ciclo com os tempos certos. Técnicas disponíveis:
{techniques}
3. Prática central (a parte mais longa), alternando falas e silêncios.
4. Fechamento: traga a atenção de volta ao corpo e deixe UMA pergunta ou intenção para ela \
levar no dia, seguida de uma pausa final.

Regras:
- Fale com a pessoa (você), frases curtas, ritmo lento. Use reticências para respirar.
- Cada fala (speech) tem de 2 a 5 frases. Escreva de 14 a 20 falas, somando NO MÍNIMO 400 \
palavras faladas (até 600): roteiros curtos demais não sustentam a meditação.
- Pausas (pause) em segundos: 5 a 12 entre instruções da prática, 15 a 30 depois de perguntas \
de reflexão. Nunca peça para prender a respiração fora do segmento breath.
- Não dê conselhos médicos nem diagnósticos.
- title: um título curto e delicado para a meditação.
{about}
Responda APENAS com JSON no formato:
{{"title": "...", "segments": [{{"kind": "speech", "text": "..."}}, \
{{"kind": "breath", "technique": "ressonante", "cycles": 4}}, {{"kind": "pause", "seconds": 8}}]}}"""

ABOUT = """
Sobre a pessoa (contexto que ela escreveu; use com delicadeza para tornar imagens, exemplos e \
perguntas pessoais, sem recitar estes fatos de volta nem supor o que não está escrito):
<sobre>
{text}
</sobre>
"""


class ScriptWriter:
    def __init__(self, settings: Settings, client: OpenAI | None = None):
        self.llm = LLM(settings, client)

    def write(self, feeling: str, profile: Profile | None = None) -> Script:
        profile = profile or Profile()
        about = ABOUT.format(text=profile.about.strip()) if profile.about.strip() else ""
        system = SCRIPT_PROMPT.format(
            techniques=breath.catalog_for_prompt(profile.max_hold), about=about
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Como estou agora: {feeling}"},
        ]
        script = self.llm.complete_json(messages, Script, temperature=0.8)
        return expand_breathing(script, profile.max_hold)


def expand_breathing(script: Script, max_hold: int) -> Script:
    """Troca cada segmento breath por falas curtas e pausas com tempos fixos."""
    segments = []
    for s in script.segments:
        if s.kind == "breath":
            segments += breath.expand(s.technique, s.cycles, max_hold)
        else:
            segments.append(s)
    return script.model_copy(update={"segments": segments})
