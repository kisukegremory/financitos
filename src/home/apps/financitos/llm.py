from datetime import date

from openai import OpenAI

from home.apps.financitos.models import Category, ParsedItems
from home.core.config import Settings
from home.core.llm import LLM

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
        self.llm = LLM(settings, client)

    def parse(self, text: str, invoice: date) -> ParsedItems:
        return self.llm.complete_json(build_messages(text, invoice), ParsedItems)
