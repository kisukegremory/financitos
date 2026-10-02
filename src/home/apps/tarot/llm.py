from openai import OpenAI

from home.apps.tarot.models import Draw, Phrase, ReadingChoice, Suggestions
from home.core.config import Settings
from home.core.llm import LLM

FORMAT = """Gere {count} frases inéditas (não cite frases famosas existentes).
Responda APENAS com JSON no formato: {{"items": [{{"text": "..."}}]}}"""


def build_messages(
    base_prompt: str, hint: str | None, count: int, examples: list[str]
) -> list[dict[str, str]]:
    user = []
    if examples:
        user.append("Frases que me marcaram (para captar o tom, não para copiar):")
        user += [f"- {e}" for e in examples]
    user.append(f"Tema ou dica: {hint}" if hint else "Tema livre.")
    return [
        {"role": "system", "content": f"{base_prompt}\n\n{FORMAT.format(count=count)}"},
        {"role": "user", "content": "\n".join(user)},
    ]


class PhraseWriter:
    def __init__(self, settings: Settings, client: OpenAI | None = None):
        self.llm = LLM(settings, client)

    def generate(
        self, base_prompt: str, hint: str | None, count: int, examples: list[str]
    ) -> Suggestions:
        messages = build_messages(base_prompt, hint, count, examples)
        return self.llm.complete_json(messages, Suggestions, temperature=0.9)


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
