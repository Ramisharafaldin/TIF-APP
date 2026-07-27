"""
Ollama provider (Phase 3, §4.2).

Ollama exposes its own local REST API (not OpenAI-compatible by default):
  - POST {host}/api/generate  (prompt -> response)
  - GET  {host}/api/tags       (list local models)
The model is instructed to return JSON; we parse defensively.
"""

import os
import json
import time
import logging
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from ai_providers.base import AIProviderInterface, AIResponse

logger = logging.getLogger(__name__)


class OllamaProvider(AIProviderInterface):
    provider_name = "ollama"

    def __init__(self, model: str = None, host: str = None, timeout: int = 120):
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3")
        self.timeout = timeout

    def _generate(self, prompt: str, temperature: float = 0.1) -> Dict:
        if requests is None:
            raise RuntimeError("The 'requests' package is required for Ollama. pip install requests")
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": temperature},
        }
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()
        content = body.get("response", "")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            cleaned = content.strip().strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            return json.loads(cleaned.strip())

    def validate_connection(self) -> Tuple[bool, str]:
        try:
            models = self.list_models()
            if not models:
                return False, "Ollama reachable but no models installed (run: ollama pull <model>)"
            if self.model not in models:
                return False, f"Model '{self.model}' not found locally. Available: {', '.join(models)}"
            return True, f"Ollama connection OK (model: {self.model})"
        except Exception as e:
            return False, f"Ollama connection failed: {str(e)}"

    def list_models(self) -> List[str]:
        try:
            if requests is None:
                return [self.model]
            resp = requests.get(f"{self.host}/api/tags", timeout=self.timeout)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception as e:
            logger.warning(f"Ollama list_models failed: {e}")
            return [self.model]

    def _run(self, prompt: str) -> Tuple[bool, Dict, Optional[str]]:
        start = time.time()
        try:
            return True, self._generate(prompt), None
        except Exception as e:
            return False, {}, str(e)

    def generate_inventory_insights(self, data: Dict, user_id: str = None) -> AIResponse:
        start = time.time()
        ok, result, err = self._run(self.build_insights_prompt(data))
        if not ok:
            return self._err(err, start)
        return AIResponse(success=True, data=result, error_message=None,
                          confidence_score=self.calculate_confidence(result),
                          processing_time=time.time() - start, cached=False,
                          timestamp=__import__('datetime').datetime.now())

    def process_natural_language_query(self, query: str, context: Dict, user_id: str = None) -> AIResponse:
        start = time.time()
        ok, result, err = self._run(self.build_query_prompt(query, context))
        if not ok:
            return self._err(err, start)
        return AIResponse(success=True, data=result, error_message=None,
                          confidence_score=self.calculate_confidence(result),
                          processing_time=time.time() - start, cached=False,
                          timestamp=__import__('datetime').datetime.now())

    def generate_smart_report(self, data: Dict, report_type: str, user_id: str = None) -> AIResponse:
        start = time.time()
        ok, result, err = self._run(self.build_report_prompt(data, report_type))
        if not ok:
            return self._err(err, start)
        return AIResponse(success=True, data=result, error_message=None,
                          confidence_score=self.calculate_confidence(result),
                          processing_time=time.time() - start, cached=False,
                          timestamp=__import__('datetime').datetime.now())

    def enhance_forecast(self, forecast_data: Dict, historical_data: Dict, user_id: str = None) -> AIResponse:
        start = time.time()
        ok, result, err = self._run(self.build_forecast_prompt(forecast_data, historical_data))
        if not ok:
            return self._err(err, start)
        return AIResponse(success=True, data=result, error_message=None,
                          confidence_score=self.calculate_confidence(result),
                          processing_time=time.time() - start, cached=False,
                          timestamp=__import__('datetime').datetime.now())

    @staticmethod
    def _err(message: str, start: float) -> AIResponse:
        return AIResponse(success=False, data={}, error_message=message,
                          confidence_score=None, processing_time=time.time() - start,
                          cached=False, timestamp=__import__('datetime').datetime.now())
