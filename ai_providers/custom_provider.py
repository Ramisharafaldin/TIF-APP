"""Custom OpenAI-compatible provider (Phase 3, §4.2)."""
import os
from ai_providers.openai_compatible_base import OpenAICompatibleProvider


class CustomProvider(OpenAICompatibleProvider):
    provider_name = "custom"
    default_model = "custom-model"
    models_path = "/models"

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None, timeout: int = 60):
        # Any OpenAI-compatible endpoint (vLLM, text-generation-webui, etc.)
        endpoint = os.getenv("CUSTOM_AI_ENDPOINT", "http://localhost:8000/v1")
        super().__init__(
            model=model or os.getenv("CUSTOM_AI_MODEL", self.default_model),
            api_key=api_key if api_key is not None else os.getenv("CUSTOM_AI_API_KEY", ""),
            base_url=base_url or endpoint,
            timeout=timeout,
        )
