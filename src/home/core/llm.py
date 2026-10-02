import json
import logging

from openai import OpenAI
from pydantic import BaseModel

from home.core.config import Settings

log = logging.getLogger(__name__)


class LLM:
    """Cliente OpenRouter (API compatível com OpenAI) com modelo de fallback."""

    def __init__(self, settings: Settings, client: OpenAI | None = None):
        self.settings = settings
        self.client = client or OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key.get_secret_value(),
        )

    def _call[T: BaseModel](
        self, model: str, messages: list[dict[str, str]], schema: type[T], temperature: float
    ) -> T:
        resp = self.client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or ""
        return schema.model_validate(json.loads(content))

    def complete_json[T: BaseModel](
        self, messages: list[dict[str, str]], schema: type[T], temperature: float = 0
    ) -> T:
        """Pede JSON e valida no `schema`; se o modelo principal falhar, tenta o fallback."""
        models = [self.settings.openrouter_model]
        if self.settings.openrouter_fallback_model:
            models.append(self.settings.openrouter_fallback_model)

        last_error: Exception | None = None
        for model in models:
            try:
                return self._call(model, messages, schema, temperature)
            except Exception as e:
                log.warning("model %s failed: %s", model, e)
                last_error = e
        raise RuntimeError(f"all models failed: {last_error}") from last_error
