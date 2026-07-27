"""Azure OpenAI provider (Phase 3, §4.2)."""
import os
from ai_providers.openai_compatible_base import OpenAICompatibleProvider


class AzureOpenAIProvider(OpenAICompatibleProvider):
    provider_name = "azure_openai"
    default_model = ""
    models_path = "/openai/deployments"

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None, timeout: int = 60):
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        # Azure chat completions URL form:
        # {endpoint}/openai/deployments/{deployment}/chat/completions?api-version=...
        base = f"{endpoint}/openai/deployments/{deployment}" if endpoint else None
        super().__init__(
            model=model or deployment,
            api_key=api_key if api_key is not None else os.getenv("AZURE_OPENAI_API_KEY", ""),
            base_url=base_url or base,
            timeout=timeout,
        )
        self.api_version = api_version

    def _auth_headers(self) -> dict:
        headers = {"Content-Type": "application/json",
                   "api-key": self.api_key}
        return headers

    def _complete(self, prompt: str, temperature: float = 0.1, max_tokens: int = 2048) -> dict:
        import requests  # local import; requests guaranteed by base
        import json
        url = f"{self.base_url}/chat/completions?api-version={self.api_version}"
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(url, headers=self._auth_headers(), json=payload, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            cleaned = content.strip().strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            return json.loads(cleaned.strip())
