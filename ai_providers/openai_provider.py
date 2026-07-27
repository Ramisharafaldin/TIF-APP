"""OpenAI provider (Phase 3, §4.2)."""
import os
from ai_providers.openai_compatible_base import OpenAICompatibleProvider


class OpenAIProvider(OpenAICompatibleProvider):
    provider_name = "openai"
    base_url = "https://api.openai.com/v1"
    default_model = "gpt-4o-mini"
    models_path = "/models"

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None, timeout: int = 60):
        super().__init__(
            model=model or os.getenv("OPENAI_MODEL", self.default_model),
            api_key=api_key if api_key is not None else os.getenv("OPENAI_API_KEY", ""),
            base_url=base_url or os.getenv("OPENAI_BASE_URL", self.base_url),
            timeout=timeout,
        )
