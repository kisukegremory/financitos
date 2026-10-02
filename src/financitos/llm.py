import json
import logging
from datetime import date

from openai import OpenAI
from pydantic import ValidationError

from financitos.config import Settings
from financitos.models import Category, ParsedItems

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você extrai lançamentos de faturas de cartão de crédito brasileiras.
Receberá o texto bruto de uma fatura (copiado de app, PDF ou CSV).

Para cada lançamento, retorne:
- date: data da compra em ISO (AAAA-MM-DD). Se o ano não aparecer, deduza pela fatura de referência.
- amount: valor numérico com ponto decimal. Gastos positivos; estornos/créditos negativos.
- category: exatamente uma destas caixinhas: {categories}
- description: o texto do lançamento exatamente como aparece (inclua "Parcela x/y" se houver).

Ignore linhas que não são lançamentos (totais, pagamentos da fatura anterior, saldo, limites).
Responda APENAS com JSON no formato: {{"items": [{{"date": "...", "amount": 0.0, "category": "...", "description": "..."}}]}}"""


def build_messages(text: str, invoice: date) -> list[dict[str, str]]:
    categories = ", ".join(c.value for c in Category)
    return [
        {"role": "system", "content": SYSTEM_PROMPT.format(categories=categories)},
        {
            "role": "user",
            "content": f"Fatura de referência: {invoice:%Y-%m}\n\n{text}",
        },
    ]


class Categorizer:
    def __init__(self, settings: Settings, client: OpenAI | None = None):
        self.settings = settings
        self.client = client or OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key.get_secret_value(),
        )

    def _call(self, model: str, messages: list[dict[str, str]]) -> ParsedItems:
        resp = self.client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or ""
        return ParsedItems.model_validate(json.loads(content))

    def parse(self, text: str, invoice: date) -> ParsedItems:
        messages = build_messages(text, invoice)
        models = [self.settings.openrouter_model]
        if self.settings.openrouter_fallback_model:
            models.append(self.settings.openrouter_fallback_model)

        last_error: Exception | None = None
        for model in models:
            try:
                return self._call(model, messages)
            except (ValidationError, json.JSONDecodeError, Exception) as e:  # noqa: B014
                log.warning("model %s failed: %s", model, e)
                last_error = e
        raise RuntimeError(f"all models failed: {last_error}") from last_error
