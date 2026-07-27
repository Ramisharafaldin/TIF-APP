"""OpenRouter provider (Phase 3, §4.2)."""
import os
from ai_providers.openai_compatible_base import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    provider_name = "openrouter"
    base_url = "https://openrouter.ai/api/v1"
    default_model = "openai/gpt-4o-mini"
    models_path = "/models"

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None, timeout: int = 60):
        super().__init__(
            model=model or os.getenv("OPENROUTER_MODEL", self.default_model),
            api_key=api_key if api_key is not None else os.getenv("OPENROUTER_API_KEY", ""),
            base_url=base_url or os.getenv("OPENROUTER_BASE_URL", self.base_url),
            timeout=timeout,
        )

    def _auth_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            # OpenRouter uses a Referer/Title header set for attribution (optional).
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["HTTP-Referer"] = os.getenv("OPENROUTER_REFERER", "")
            headers["X-Title"] = os.getenv("OPENROUTER_TITLE", "TIF-AI")
        return headers
