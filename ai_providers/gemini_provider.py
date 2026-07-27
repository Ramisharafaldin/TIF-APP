"""
Gemini provider (Phase 3, §4.2 step 2).

The existing ``_call_gemini_api`` logic from ``modules/ai_insights`` is reused
verbatim here, wrapped to satisfy ``AIProviderInterface``. This is a pure
refactor: the Gemini call path and its caching/anonymization/audit behaviour
are unchanged. The service layer now talks to this class through the interface
instead of importing ``_call_gemini_api`` directly.

Requires ``google.generativeai`` (the package already used by the app).
"""

import time
import logging
from typing import Dict, List, Optional, Tuple

from ai_providers.base import AIProviderInterface, AIResponse

logger = logging.getLogger(__name__)


class GeminiProvider(AIProviderInterface):
    provider_name = "gemini"

    def __init__(self, model: str = None, api_key: str = None):
        # Reuse ai_insights' configured model/cache/audit plumbing so behaviour
        # is identical to the pre-refactor call site.
        from utils.ai_config import ai_config
        from modules.ai_insights import (
            AI_AVAILABLE, insights_cache, _log_api_interaction,
        )
        self._ai_available = AI_AVAILABLE
        self._cache = insights_cache
        self._log_api_interaction = _log_api_interaction
        config = ai_config.load_api_configuration()
        self.model = model or config['model_name']
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Core Gemini call (verbatim semantics from _call_gemini_api)
    # ------------------------------------------------------------------
    def _call_gemini_api(self, prompt: str) -> Dict:
        from modules.ai_insights import genai, MODEL_NAME
        from utils.ai_config import ai_config

        if not self._ai_available:
            logger.warning("AI features are disabled due to configuration issues")
            return {"error": "AI features are currently unavailable",
                    "details": "Please check API configuration"}

        cached_result = self._cache.get(prompt)
        if cached_result:
            return cached_result

        start_time = time.time()
        timeout_settings = ai_config.get_timeout_settings()
        security_settings = ai_config.get_security_settings()

        try:
            if security_settings['log_api_calls']:
                preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
                anonymized_prompt = self._cache._anonymize_sensitive_data(preview)
                logger.info(f"Making Gemini API call: {anonymized_prompt}")

            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "max_output_tokens": 2048,
                    "temperature": 0.1,
                },
            )

            result = __import__('json').loads(response.text)
            self._cache.set(prompt, result)

            duration = time.time() - start_time
            logger.info(f"Gemini API call successful. Duration: {duration:.2f}s")
            if security_settings['audit_enabled']:
                self._log_api_interaction(prompt, result, duration, success=True)
            return result

        except __import__('json').JSONDecodeError as e:
            duration = time.time() - start_time
            error_msg = f"Failed to parse Gemini API response as JSON: {str(e)}"
            logger.error(error_msg)
            if security_settings['audit_enabled']:
                self._log_api_interaction(prompt, None, duration, success=False, error=error_msg)
            return {"error": "Invalid response format from AI service",
                    "details": "The AI service returned an unexpected response format"}

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Gemini API Error: {str(e)}"
            logger.error(error_msg)
            if security_settings['audit_enabled']:
                self._log_api_interaction(prompt, None, duration, success=False, error=error_msg)
            return {"error": "Unable to generate insights",
                    "details": "The AI service is temporarily unavailable. Please try again later."}

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------
    def validate_connection(self) -> Tuple[bool, str]:
        from utils.ai_config import ai_config
        if not self._ai_available:
            return False, "Gemini API key not configured"
        is_valid, message = ai_config.validate_api_key()
        if not is_valid:
            return False, message
        try:
            from modules.ai_insights import validate_ai_service
            return validate_ai_service()
        except Exception as e:
            return False, f"Gemini validation failed: {str(e)}"

    def list_models(self) -> List[str]:
        return ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"]

    def generate_inventory_insights(self, data: Dict, user_id: str = None) -> AIResponse:
        start = time.time()
        result = self._call_gemini_api(self.build_insights_prompt(data))
        if "error" in result:
            return AIResponse(success=False, data={}, error_message=result.get("details", result["error"]),
                              confidence_score=None, processing_time=time.time() - start,
                              cached=False, timestamp=__import__('datetime').datetime.now())
        return AIResponse(success=True, data=result, error_message=None,
                          confidence_score=self.calculate_confidence(result),
                          processing_time=time.time() - start, cached=False,
                          timestamp=__import__('datetime').datetime.now())

    def process_natural_language_query(self, query: str, context: Dict, user_id: str = None) -> AIResponse:
        start = time.time()
        result = self._call_gemini_api(self.build_query_prompt(query, context))
        if "error" in result:
            return AIResponse(success=False, data={}, error_message=result.get("details", result["error"]),
                              confidence_score=None, processing_time=time.time() - start,
                              cached=False, timestamp=__import__('datetime').datetime.now())
        return AIResponse(success=True, data=result, error_message=None,
                          confidence_score=self.calculate_confidence(result),
                          processing_time=time.time() - start, cached=False,
                          timestamp=__import__('datetime').datetime.now())

    def generate_smart_report(self, data: Dict, report_type: str, user_id: str = None) -> AIResponse:
        start = time.time()
        result = self._call_gemini_api(self.build_report_prompt(data, report_type))
        if "error" in result:
            return AIResponse(success=False, data={}, error_message=result.get("details", result["error"]),
                              confidence_score=None, processing_time=time.time() - start,
                              cached=False, timestamp=__import__('datetime').datetime.now())
        return AIResponse(success=True, data=result, error_message=None,
                          confidence_score=self.calculate_confidence(result),
                          processing_time=time.time() - start, cached=False,
                          timestamp=__import__('datetime').datetime.now())

    def enhance_forecast(self, forecast_data: Dict, historical_data: Dict, user_id: str = None) -> AIResponse:
        start = time.time()
        result = self._call_gemini_api(self.build_forecast_prompt(forecast_data, historical_data))
        if "error" in result:
            return AIResponse(success=False, data={}, error_message=result.get("details", result["error"]),
                              confidence_score=None, processing_time=time.time() - start,
                              cached=False, timestamp=__import__('datetime').datetime.now())
        return AIResponse(success=True, data=result, error_message=None,
                          confidence_score=self.calculate_confidence(result),
                          processing_time=time.time() - start, cached=False,
                          timestamp=__import__('datetime').datetime.now())
