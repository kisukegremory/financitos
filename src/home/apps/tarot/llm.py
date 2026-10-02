from openai import OpenAI

from home.apps.tarot.models import Suggestions
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
