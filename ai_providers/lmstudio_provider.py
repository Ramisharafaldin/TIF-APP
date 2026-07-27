"""LM Studio provider (Phase 3, §4.2). Local OpenAI-compatible server."""
import os
from ai_providers.openai_compatible_base import OpenAICompatibleProvider


class LMStudioProvider(OpenAICompatibleProvider):
    provider_name = "lmstudio"
    default_model = "local-model"
    models_path = "/v1/models"

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None, timeout: int = 120):
        # LM Studio serves OpenAI-compatible API under /v1 by default.
        endpoint = os.getenv("LMSTUDIO_ENDPOINT", "http://localhost:1234/v1")
        super().__init__(
            model=model or os.getenv("LMSTUDIO_MODEL", self.default_model),
            # LM Studio uses a dummy key locally.
            api_key=api_key if api_key is not None else os.getenv("LMSTUDIO_API_KEY", "lm-studio"),
            base_url=base_url or endpoint,
            timeout=timeout,
        )
