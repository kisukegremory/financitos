from openai import OpenAI

from home.apps.tarot.models import (
    Draw,
    GenerateMode,
    Phrase,
    ReadingChoice,
    Suggestions,
    Thinkers,
)
from home.core.config import Settings
from home.core.llm import LLM

FORMAT = """Responda APENAS com JSON no formato:
{{"items": [{{"text": "...", "author": "..." ou null, "source": "..." ou null}}]}}"""

MODES = {
    GenerateMode.ORIGINAL: """Gere {count} frases inéditas (não cite frases famosas existentes).
Use author e source null.""",
    GenerateMode.QUOTE: """Traga {count} citações REAIS e conhecidas de {thinker}, traduzidas para \
o português do Brasil. Em author, o nome do autor; em source, a obra de onde vem a citação.
Nunca invente citações nem atribua a {thinker} algo que não seja dele: se não tiver certeza, \
traga menos itens. Se nenhum pensador foi indicado, escolha pensadores clássicos que conversem \
com o tema (ex.: Sun Tzu, Platão, Sêneca, Marco Aurélio, Lao-Tsé, Nietzsche).""",
    GenerateMode.INSPIRED: """Gere {count} frases inéditas inspiradas no pensamento e no estilo de \
{thinker}, aplicando as ideias dele ao tema, como se fossem ensinamentos dele para hoje.
Não copie frases reais. Use author "inspirado em <nome>" e source null.""",
}


def build_messages(
    base_prompt: str,
    hint: str | None,
    count: int,
    examples: list[str],
    mode: GenerateMode = GenerateMode.ORIGINAL,
    thinker: str | None = None,
) -> list[dict[str, str]]:
    user = []
    if examples and mode is GenerateMode.ORIGINAL:
        user.append("Frases que me marcaram (para captar o tom, não para copiar):")
        user += [f"- {e}" for e in examples]
    user.append(f"Tema ou dica: {hint}" if hint else "Tema livre.")
    instructions = MODES[mode].format(count=count, thinker=thinker or "um pensador clássico")
    # o prompt base pede frases inéditas: em citações ele briga com o pedido de frases reais
    system = instructions if mode is GenerateMode.QUOTE else f"{base_prompt}\n\n{instructions}"
    return [
        {"role": "system", "content": f"{system}\n{FORMAT}"},
        {"role": "user", "content": "\n".join(user)},
    ]


THINKERS_PROMPT = """Você conhece bem filosofia, estratégia e literatura clássica do Ocidente e do \
Oriente. A partir do tema ou momento da pessoa, recomende {count} pensadores (de épocas e \
tradições variadas) cujas ideias conversam com ele. Para cada um: name, era (lugar e época), \
why (1 a 2 frases, em português do Brasil, ligando as ideias dele ao tema) e works (1 a 3 obras \
reais para ler). Responda APENAS com JSON no formato:
{{"items": [{{"name": "...", "era": "...", "why": "...", "works": ["..."]}}]}}"""


class PhraseWriter:
    def __init__(self, settings: Settings, client: OpenAI | None = None):
        self.llm = LLM(settings, client)

    def generate(
        self,
        base_prompt: str,
        hint: str | None,
        count: int,
        examples: list[str],
        mode: GenerateMode = GenerateMode.ORIGINAL,
        thinker: str | None = None,
    ) -> Suggestions:
        messages = build_messages(base_prompt, hint, count, examples, mode, thinker)
        # citações reais pedem precisão, não criatividade
        temperature = 0.3 if mode is GenerateMode.QUOTE else 0.9
        result = self.llm.complete_json(messages, Suggestions, temperature=temperature)
        items = result.items
        if mode is GenerateMode.QUOTE:  # citação sem autor não é citação
            items = [i for i in items if i.author]
        return Suggestions(items=items[:count])

    def recommend(self, topic: str | None, count: int) -> Thinkers:
        messages = [
            {"role": "system", "content": THINKERS_PROMPT.format(count=count)},
            {"role": "user", "content": f"Tema: {topic}" if topic else "Tema livre: surpreenda."},
        ]
        return self.llm.complete_json(messages, Thinkers, temperature=0.7)


READING_PROMPT = """Você é um leitor sensível e direto, que ajuda a pessoa a refletir sobre o momento dela.
Ela vai contar como está se sentindo. Você recebe:
- a coleção de frases que marcaram a pessoa (com id);
- a carta de tarot sorteada para ela, com orientação e significado.

Tarefas:
1. Escolha da coleção a frase que mais conversa com o momento dela (phrase_id).
   Se nenhuma encaixar de verdade, ou a coleção estiver vazia, deixe phrase_id null e escreva
   uma frase nova, curta e marcante, em new_phrase.
2. why: em 2 a 4 frases, explique como a frase se relaciona com o que ela está vivendo.
3. card_reading: em 2 a 4 frases, interprete a carta (respeitando a orientação) à luz do momento dela.

Fale com a pessoa (você), em português do Brasil, com acolhimento e sem clichês. Não faça previsões
nem dê conselhos médicos. Responda APENAS com JSON no formato:
{"phrase_id": 1, "new_phrase": null, "why": "...", "card_reading": "..."}"""


def build_reading_messages(feeling: str, phrases: list[Phrase], draw: Draw) -> list[dict[str, str]]:
    card = draw.card
    collection = "\n".join(
        f"[{p.id}] {p.text}" + (f" — {p.author}" if p.author else "") for p in phrases
    )
    user = f"""Como estou: {feeling}

Frases da coleção:
{collection or "(vazia)"}

Carta sorteada: {card.name} ({"invertida" if draw.reversed else "normal"})
Palavras-chave: {", ".join(card.keywords)}
Significado: {card.reversed if draw.reversed else card.upright}"""
    return [
        {"role": "system", "content": READING_PROMPT},
        {"role": "user", "content": user},
    ]


class Reader:
    def __init__(self, settings: Settings, client: OpenAI | None = None):
        self.llm = LLM(settings, client)

    def read(self, feeling: str, phrases: list[Phrase], draw: Draw) -> ReadingChoice:
        messages = build_reading_messages(feeling, phrases, draw)
        return self.llm.complete_json(messages, ReadingChoice, temperature=0.7)
