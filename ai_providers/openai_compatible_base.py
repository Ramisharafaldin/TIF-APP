"""
Shared OpenAI-compatible chat-completions base (Phase 3, §4.2).

OpenAI, Azure OpenAI, LM Studio, OpenRouter and most "custom" endpoints all
speak the OpenAI chat-completions schema. This base implements the full
``AIProviderInterface`` once; each concrete provider only overrides:
  - ``base_url``           (API root)
  - ``_auth_headers()``    (auth scheme)
  - ``list_models()``      (model enumeration; many local servers lack this)
  - ``default_model``      (fallback when no model env var is set)
"""

import os
import json
import time
import logging
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:  # pragma: no cover - dependency guidance
    requests = None

from ai_providers.base import AIProviderInterface, AIResponse

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(AIProviderInterface):
    """Base for any OpenAI chat-completions compatible endpoint."""

    provider_name = "openai_compatible"

    #: Subclasses override these.
    base_url: str = "https://api.openai.com/v1"
    default_model: str = "gpt-4o-mini"
    #: Path appended to base_url for chat completions.
    chat_path: str = "/chat/completions"
    #: Path appended to base_url for listing models (may be None if unsupported).
    models_path: Optional[str] = "/models"

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None,
                 timeout: int = 60):
        self.model = model or self.default_model
        self.api_key = api_key
        self.timeout = timeout
        if base_url:
            self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Override hooks
    # ------------------------------------------------------------------
    def _auth_headers(self) -> Dict[str, str]:
        """Return auth headers. Default: OpenAI Bearer token."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ------------------------------------------------------------------
    # Core completion call
    # ------------------------------------------------------------------
    def _complete(self, prompt: str, temperature: float = 0.1,
                  max_tokens: int = 2048) -> Dict:
        """Call chat/completions and return parsed JSON dict."""
        if requests is None:
            raise RuntimeError(
                "The 'requests' package is required for OpenAI-compatible providers. "
                "Install with: pip install requests"
            )
        url = f"{self.base_url}{self.chat_path}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(
            url, headers=self._auth_headers(), json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Some models wrap JSON in markdown fences.
            cleaned = content.strip().strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            return json.loads(cleaned.strip())

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------
    def validate_connection(self) -> Tuple[bool, str]:
        try:
            # A tiny completion proves connectivity + auth.
            self._complete("Reply with JSON: {\"status\":\"ok\"}", max_tokens=32)
            return True, f"{self.provider_name} connection OK (model: {self.model})"
        except Exception as e:
            return False, f"{self.provider_name} connection failed: {str(e)}"

    def list_models(self) -> List[str]:
        if not self.models_path:
            return [self.model]
        try:
            if requests is None:
                return [self.model]
            url = f"{self.base_url}{self.models_path}"
            resp = requests.get(url, headers=self._auth_headers(), timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if "data" in data:
                return [m.get("id") for m in data["data"] if m.get("id")]
            if isinstance(data, list):
                return [m.get("id") for m in data if m.get("id")]
            return [self.model]
        except Exception as e:
            logger.warning(f"{self.provider_name} list_models failed: {e}")
            return [self.model]

    def _run(self, prompt: str) -> Tuple[bool, Dict, Optional[str]]:
        start = time.time()
        try:
            result = self._complete(prompt)
            return True, result, None
        except Exception as e:
            return False, {}, str(e)

    def generate_inventory_insights(self, data: Dict, user_id: str = None) -> AIResponse:
        start = time.time()
        ok, result, err = self._run(self.build_insights_prompt(data))
        if not ok:
            return self._err(err, start)
        return AIResponse(
            success=True, data=result, error_message=None,
            confidence_score=self.calculate_confidence(result),
            processing_time=time.time() - start, cached=False,
            timestamp=__import__('datetime').datetime.now(),
        )

    def process_natural_language_query(self, query: str, context: Dict, user_id: str = None) -> AIResponse:
        start = time.time()
        ok, result, err = self._run(self.build_query_prompt(query, context))
        if not ok:
            return self._err(err, start)
        return AIResponse(
            success=True, data=result, error_message=None,
            confidence_score=self.calculate_confidence(result),
            processing_time=time.time() - start, cached=False,
            timestamp=__import__('datetime').datetime.now(),
        )

    def generate_smart_report(self, data: Dict, report_type: str, user_id: str = None) -> AIResponse:
        start = time.time()
        ok, result, err = self._run(self.build_report_prompt(data, report_type))
        if not ok:
            return self._err(err, start)
        return AIResponse(
            success=True, data=result, error_message=None,
            confidence_score=self.calculate_confidence(result),
            processing_time=time.time() - start, cached=False,
            timestamp=__import__('datetime').datetime.now(),
        )

    def enhance_forecast(self, forecast_data: Dict, historical_data: Dict, user_id: str = None) -> AIResponse:
        start = time.time()
        ok, result, err = self._run(self.build_forecast_prompt(forecast_data, historical_data))
        if not ok:
            return self._err(err, start)
        return AIResponse(
            success=True, data=result, error_message=None,
            confidence_score=self.calculate_confidence(result),
            processing_time=time.time() - start, cached=False,
            timestamp=__import__('datetime').datetime.now(),
        )

    @staticmethod
    def _err(message: str, start: float) -> AIResponse:
        return AIResponse(
            success=False, data={}, error_message=message,
            confidence_score=None, processing_time=time.time() - start,
            cached=False, timestamp=__import__('datetime').datetime.now(),
        )
