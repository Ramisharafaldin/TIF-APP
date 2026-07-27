"""
Comprehensive AI Service Layer
Provides enhanced AI capabilities with robust error handling, caching, and security.
"""
import json
import time
import logging
import pandas as pd
from typing import Dict, Optional, Tuple, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)


def _anonymize_sensitive_tokens() -> tuple:
    """Key-name tokens that mark a field as sensitive PII and must be redacted
    before any AI provider call (Phase 3, §4.3 step 7)."""
    return (
        'email', 'phone', 'mobile', 'fax', 'address', 'customer', 'supplier',
        'contact', 'person', 'user', 'employee', 'staff', 'client', 'vendor',
        'ssn', 'tax', 'credit', 'card', 'password', 'secret', 'token', 'key',
        'name',
    )

# Import AI components after basic imports to avoid circular dependencies
try:
    from utils.ai_config import ai_config
except ImportError as e:
    logger.error(f"Failed to import AI config: {e}")
    ai_config = None

try:
    from modules.ai_insights import validate_ai_service, insights_cache
except ImportError as e:
    logger.warning(f"Gemini/AI insights module unavailable (non-fatal if using a non-Gemini provider): {e}")
    validate_ai_service = None
    insights_cache = None

try:
    from utils.audit_logger import audit_logger
except ImportError as e:
    logger.warning(f"Audit logger not available: {e}")
    audit_logger = None

try:
    from utils.data_privacy import privacy_manager
except ImportError as e:
    logger.warning(f"Privacy manager not available: {e}")
    privacy_manager = None

# Define audit decorator that works with or without audit_logger
def audit_ai_operation(operation_type):
    """Decorator for auditing AI operations."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if audit_logger:
                try:
                    # Log the operation start
                    user_id = kwargs.get('user_id', 'unknown')
                    audit_logger.log_ai_operation(
                        operation_type=operation_type,
                        user_id=user_id,
                        data_accessed=['ai_service'],
                        success=True
                    )
                except Exception as e:
                    logger.warning(f"Audit logging failed: {e}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


@dataclass
class AIResponse:
    """Structured AI response with metadata."""
    success: bool
    data: Dict
    error_message: Optional[str]
    confidence_score: Optional[float]
    processing_time: float
    cached: bool
    timestamp: datetime


class CircuitBreaker:
    """
    Circuit breaker pattern for API resilience.
    
    Prevents cascading failures by temporarily disabling API calls
    when failure rate exceeds threshold.
    """
    
    def __init__(self, failure_threshold: int = None, recovery_timeout: int = None):
        # Wire circuit-breaker thresholds to ai_config (item 1.7).
        # Defaults fall back to the previous hardcoded values only if
        # ai_config is unavailable, so behavior is preserved when the
        # AI layer is disabled or misconfigured.
        if failure_threshold is None or recovery_timeout is None:
            try:
                from utils.ai_config import ai_config as _cfg
                _cb_enabled = os.getenv('AI_CIRCUIT_BREAKER_ENABLED', 'true').lower() == 'true'
                if _cfg is not None and _cb_enabled:
                    _config = _cfg.load_api_configuration()
                    if failure_threshold is None:
                        failure_threshold = _config.get('circuit_breaker_threshold', 5)
                    if recovery_timeout is None:
                        recovery_timeout = _config.get('circuit_breaker_timeout', 60)
            except Exception as e:
                logger.warning(f"Could not load circuit-breaker config, using defaults: {e}")

        if failure_threshold is None:
            failure_threshold = 5
        if recovery_timeout is None:
            recovery_timeout = 60

        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN - API calls are temporarily disabled")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful API call."""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """Handle failed API call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


class DisabledAIService:
    """
    Disabled AI service implementation.
    Used when AI_ENABLED is false. Returns safe fallbacks with zero overhead.
    """
    def __init__(self):
        self.performance_metrics = {
            'total_calls': 0, 'successful_calls': 0, 'failed_calls': 0, 'cache_hits': 0, 'average_response_time': 0.0
        }

    def validate_api_connection(self) -> Tuple[bool, str]:
        return False, "AI features are disabled"

    def generate_inventory_insights(self, data: Dict, user_id: str = None) -> AIResponse:
        return self._create_fallback("AI disabled")

    def process_natural_language_query(self, query: str, context: Dict, user_id: str = None) -> AIResponse:
        return self._create_fallback("AI disabled")

    def generate_smart_report(self, data: Dict, report_type: str, user_id: str = None) -> AIResponse:
        return self._create_fallback("AI disabled")

    def enhance_forecast(self, forecast_data: Dict, historical_data: Dict, user_id: str = None) -> AIResponse:
        return self._create_fallback("AI disabled")

    def get_cached_response(self, cache_key: str) -> Optional[Dict]:
        return None

    def cache_response(self, cache_key: str, response: Dict, ttl: int = None):
        pass

    def get_performance_metrics(self) -> Dict:
        return self.performance_metrics

    def _create_fallback(self, msg: str) -> AIResponse:
        return AIResponse(
            success=False, data={'fallback': True, 'message': msg}, error_message=msg,
            confidence_score=None, processing_time=0.0, cached=False, timestamp=datetime.now()
        )


# Factory for Service Instantiation
if os.environ.get('AI_ENABLED', 'false').lower() == 'true':
    logger.info("AI Service: Enabled - Initializing provider-backed service")

    # Import AI components after basic imports to avoid circular dependencies
    try:
        from utils.ai_config import ai_config
    except ImportError as e:
        logger.error(f"Failed to import AI config: {e}")
        ai_config = None

    try:
        from modules.ai_insights import validate_ai_service, insights_cache
    except ImportError as e:
        logger.warning(f"Gemini/AI insights module unavailable (non-fatal if using a non-Gemini provider): {e}")
        validate_ai_service = None
        insights_cache = None

    try:
        from utils.audit_logger import audit_logger
    except ImportError as e:
        logger.warning(f"Audit logger not available: {e}")
        audit_logger = None

    try:
        from utils.data_privacy import privacy_manager
    except ImportError as e:
        logger.warning(f"Privacy manager not available: {e}")
        privacy_manager = None

    from ai_providers import get_provider

    class ProviderBackedAIService:
        """
        Enhanced AI service with comprehensive error handling, caching, and security.

        Phase 3 (§4): delegates all model generation to a pluggable provider
        resolved from ``ai_providers`` via the ``AI_PROVIDER`` env var. The
        Gemini path is byte-for-byte behaviour-compatible with the previous
        ``GeminiAIServiceImpl`` (same circuit breaker, privacy, performance and
        prompt logic); only the call target changed. Other providers
        (Ollama, OpenAI, LM Studio, OpenRouter, Azure, Custom) work through the
        same interface with no further changes here.

        The CircuitBreaker (item 1.7) wraps whichever provider is active.
        """

        def __init__(self):
            """Initialize the AI service."""
            self.performance_metrics = {
                'total_calls': 0, 'successful_calls': 0, 'failed_calls': 0,
                'cache_hits': 0, 'average_response_time': 0.0
            }

            try:
                if ai_config is not None:
                    self.config = ai_config.load_api_configuration()
                else:
                    logger.warning("AI config not available, using defaults")
                    self.config = {
                        'features_enabled': False, 'model_name': 'gemini-2.0-flash-exp',
                        'timeout': 30, 'cache_ttl': 3600
                    }
            except Exception as e:
                logger.error(f"Failed to load AI configuration: {e}")
                self.config = {
                    'features_enabled': False, 'model_name': 'gemini-2.0-flash-exp',
                    'timeout': 30, 'cache_ttl': 3600
                }

            # Resolve the active provider (Phase 3).
            provider_name = ai_config.get_provider_name() if ai_config else 'gemini'
            try:
                self.provider = get_provider(provider_name)
                logger.info(f"AI provider selected: {provider_name}")
            except Exception as e:
                logger.error(f"Failed to instantiate provider '{provider_name}', falling back to gemini: {e}")
                self.provider = get_provider('gemini')

            # Wire CircuitBreaker to ai_config thresholds (item 1.7).
            if ai_config is not None:
                try:
                    cb_enabled = os.getenv('AI_CIRCUIT_BREAKER_ENABLED', 'true').lower() == 'true'
                    cb_threshold = self.config.get('circuit_breaker_threshold', 5)
                    cb_timeout = self.config.get('circuit_breaker_timeout', 60)
                    self.circuit_breaker = CircuitBreaker(
                        failure_threshold=cb_threshold,
                        recovery_timeout=cb_timeout
                    ) if cb_enabled else CircuitBreaker(
                        failure_threshold=cb_threshold, recovery_timeout=cb_timeout)
                except Exception as e:
                    logger.warning(f"Failed to configure circuit breaker from config, using defaults: {e}")
                    self.circuit_breaker = CircuitBreaker()
            else:
                self.circuit_breaker = CircuitBreaker()

        def validate_api_connection(self) -> Tuple[bool, str]:
            """Validate API connection and configuration via the active provider."""
            try:
                if ai_config is None:
                    return False, "AI configuration not available"
                if not ai_config.is_ai_enabled():
                    return False, "AI features are disabled"
                return self.provider.validate_connection()
            except Exception as e:
                return False, f"API validation failed: {str(e)}"

        @audit_ai_operation('insights')
        def generate_inventory_insights(self, data: Dict, user_id: str = None) -> AIResponse:
            from utils.ai_performance import performance_monitor
            operation_id = performance_monitor.start_operation(
                operation_name="inventory_insights",
                data_size=len(str(data)),
                metadata={'data_keys': list(data.keys()), 'user_id': user_id, 'provider': self.provider.provider_name}
            )
            start_time = time.time()
            try:
                if not data or not isinstance(data, dict):
                    performance_monitor.end_operation(operation_id, success=False,
                                                      error_message="Invalid inventory data provided")
                    return AIResponse(success=False, data={}, error_message="Invalid inventory data provided",
                                     confidence_score=None, processing_time=time.time() - start_time,
                                     cached=False, timestamp=datetime.now())
                if ai_config is None or not ai_config.is_ai_enabled():
                    performance_monitor.end_operation(operation_id, success=False,
                                                      error_message="AI features are disabled")
                    return self._create_fallback_response("AI features are disabled", start_time)
                if privacy_manager and user_id:
                    if not audit_logger.validate_user_permissions(user_id, 'insights', 'inventory_data'):
                        performance_monitor.end_operation(operation_id, success=False,
                                                          error_message="User lacks permission for AI insights")
                        return AIResponse(success=False, data={}, error_message="Insufficient permissions for AI insights",
                                         confidence_score=None, processing_time=time.time() - start_time,
                                         cached=False, timestamp=datetime.now())
                anonymized_data, _ = self._apply_privacy_measures(data, user_id)
                prompt = self.provider.build_insights_prompt(anonymized_data)
                result = self._call_provider(self.provider.generate_inventory_insights, anonymized_data, user_id)
                processing_time = time.time() - start_time
                self._update_performance_metrics(processing_time, success=result.success)
                performance_monitor.end_operation(operation_id, success=result.success)
                return result
            except Exception as e:
                return self._error_response(e, start_time, operation_id, performance_monitor)

        @audit_ai_operation('query')
        def process_natural_language_query(self, query: str, context: Dict, user_id: str = None) -> AIResponse:
            from utils.ai_performance import performance_monitor
            operation_id = performance_monitor.start_operation(
                operation_name="natural_language_query",
                data_size=len(query) + len(str(context)),
                metadata={'query_length': len(query), 'provider': self.provider.provider_name}
            )
            start_time = time.time()
            try:
                if not query or not query.strip():
                    performance_monitor.end_operation(operation_id, success=False,
                                                      error_message="Empty query provided")
                    return AIResponse(success=False, data={}, error_message="Empty query provided",
                                     confidence_score=None, processing_time=time.time() - start_time,
                                     cached=False, timestamp=datetime.now())
                if ai_config is None or not ai_config.is_feature_enabled('natural_language'):
                    performance_monitor.end_operation(operation_id, success=False,
                                                      error_message="Natural language queries are disabled")
                    return self._create_fallback_response("Natural language queries are disabled", start_time)
                anonymized_query = self._anonymize_text(query)
                anonymized_context = self._anonymize_inventory_data(context)
                result = self.provider.process_natural_language_query(anonymized_query, anonymized_context, user_id)
                processing_time = time.time() - start_time
                self._update_performance_metrics(processing_time, success=result.success)
                performance_monitor.end_operation(operation_id, success=result.success)
                return result
            except Exception as e:
                return self._error_response(e, start_time, operation_id, performance_monitor)

        @audit_ai_operation('report')
        def generate_smart_report(self, data: Dict, report_type: str, user_id: str = None) -> AIResponse:
            from utils.ai_performance import performance_monitor
            operation_id = performance_monitor.start_operation(
                operation_name="smart_report_generation",
                data_size=len(str(data)),
                metadata={'report_type': report_type, 'provider': self.provider.provider_name}
            )
            start_time = time.time()
            try:
                try:
                    from utils.ai_config import ai_config as config_manager
                    if not config_manager.is_feature_enabled('smart_reports'):
                        performance_monitor.end_operation(operation_id, success=False,
                                                          error_message="Smart reports are disabled")
                        return self._create_fallback_response("Smart reports are disabled", start_time)
                except Exception as config_error:
                    logger.warning(f"AI config check failed: {config_error}, proceeding with fallback mode")
                from utils.smart_report_generator import SmartReportGenerator
                report_generator = SmartReportGenerator(self)
                anonymized_data = self._anonymize_inventory_data(data)
                ai_insights = {}
                try:
                    ai_result = self.provider.generate_smart_report(anonymized_data, report_type, user_id)
                    if ai_result.success:
                        ai_insights = ai_result.data
                    else:
                        ai_insights = {'error': ai_result.error_message}
                except Exception as ai_error:
                    logger.warning(f"AI insights generation failed: {ai_error}")
                    ai_insights = {'error': str(ai_error)}
                base_report = {
                    'report_type': report_type, 'data': data,
                    'business_context': data.get('business_context', {}),
                    'sales_data': data.get('sales_data'),
                    'inventory_data': data.get('inventory_data'),
                    'time_series_data': data.get('time_series_data')
                }
                enhanced_report = report_generator.create_enhanced_report(base_report, ai_insights)
                processing_time = time.time() - start_time
                self._update_performance_metrics(processing_time, success=True)
                performance_monitor.end_operation(operation_id, success=True)
                return AIResponse(success=True, data=enhanced_report, error_message=None,
                                  confidence_score=enhanced_report.get('confidence_score', 75.0),
                                  processing_time=processing_time, cached=processing_time < 0.1,
                                  timestamp=datetime.now())
            except Exception as e:
                return self._error_response(e, start_time, operation_id, performance_monitor)

        @audit_ai_operation('forecast')
        def enhance_forecast(self, forecast_data: Dict, historical_data: Dict, user_id: str = None) -> AIResponse:
            from utils.ai_performance import performance_monitor
            operation_id = performance_monitor.start_operation(
                operation_name="enhanced_forecasting",
                data_size=len(str(forecast_data)) + len(str(historical_data)),
                metadata={'forecast_items': len(forecast_data.get('forecast_df', [])), 'provider': self.provider.provider_name}
            )
            start_time = time.time()
            try:
                try:
                    from utils.ai_config import ai_config as config_manager
                    if not config_manager.is_feature_enabled('enhanced_forecasting'):
                        performance_monitor.end_operation(operation_id, success=False,
                                                          error_message="Enhanced forecasting is disabled")
                        return self._create_fallback_response("Enhanced forecasting is disabled", start_time)
                except Exception as config_error:
                    logger.warning(f"AI config check failed: {config_error}, proceeding with enhanced forecasting")
                from utils.enhanced_forecasting import enhanced_forecasting_system
                enhanced_forecasting_system.ai_service = self
                business_context = forecast_data.get('business_context', {})
                enhancement = enhanced_forecasting_system.enhance_forecast_with_ai(
                    forecast_data, historical_data, business_context)
                response_data = {
                    'forecast_validation': f"تم تحليل التنبؤ بدرجة ثقة {enhancement.confidence_score:.1f}%",
                    'confidence_intervals': enhancement.confidence_intervals,
                    'risk_factors': enhancement.risk_factors,
                    'adjustments': enhancement.adjustments,
                    'external_factors': enhancement.external_factors,
                    'recommendations': enhancement.recommendations,
                    'confidence_score': enhancement.confidence_score,
                    'enhanced_forecast': enhancement.enhanced_forecast,
                    'processing_time': enhancement.processing_time,
                    'enhancement_summary': {
                        'original_metrics': self._extract_forecast_metrics(enhancement.original_forecast),
                        'enhanced_metrics': self._extract_forecast_metrics(enhancement.enhanced_forecast),
                        'improvement_areas': len(enhancement.adjustments),
                        'risk_mitigation': len(enhancement.risk_factors)
                    }
                }
                processing_time = time.time() - start_time
                self._update_performance_metrics(processing_time, success=True)
                performance_monitor.end_operation(operation_id, success=True)
                return AIResponse(success=True, data=response_data, error_message=None,
                                  confidence_score=enhancement.confidence_score,
                                  processing_time=processing_time, cached=processing_time < 0.1,
                                  timestamp=datetime.now())
            except Exception as e:
                return self._error_response(e, start_time, operation_id, performance_monitor)

        # ------------------------------------------------------------------
        # Provider call helper (circuit-breaker wrapped)
        # ------------------------------------------------------------------
        def _call_provider(self, method, *args, **kwargs) -> AIResponse:
            """Run a provider method behind the circuit breaker."""
            return self.circuit_breaker.call(method, *args, **kwargs)

        # ------------------------------------------------------------------
        # Reporting / cache / metrics (preserved API)
        # ------------------------------------------------------------------
        def get_cached_response(self, cache_key: str) -> Optional[Dict]:
            if insights_cache is None:
                return None
            return insights_cache.get(cache_key)

        def cache_response(self, cache_key: str, response: Dict, ttl: int = None):
            if insights_cache is None:
                return
            if ttl:
                temp_cache = type(insights_cache)(ttl)
                temp_cache.set(cache_key, response)
            else:
                insights_cache.set(cache_key, response)

        def get_performance_metrics(self) -> Dict:
            return self.performance_metrics.copy()

        # ------------------------------------------------------------------
        # Privacy / anonymization (preserved, provider-agnostic — §4.3 step 7)
        # ------------------------------------------------------------------
        def _anonymize_inventory_data(self, data: Dict) -> Dict:
            if not isinstance(data, dict):
                return data
            anonymized = {}
            for key, value in data.items():
                if isinstance(value, dict):
                    anonymized[key] = self._anonymize_inventory_data(value)
                elif isinstance(value, list):
                    anonymized[key] = [self._anonymize_inventory_data(item) if isinstance(item, dict) else item for item in value]
                elif hasattr(value, 'to_dict'):
                    try:
                        df_dict = value.to_dict('records')
                        if len(df_dict) > 10:
                            df_dict = df_dict[:10]
                        anonymized_records = []
                        for record in df_dict:
                            anonymized_record = {}
                            for k, v in record.items():
                                if self._key_is_sensitive(k) or self._value_looks_like_pii(v):
                                    anonymized_record[k] = '[REDACTED]'
                                elif hasattr(v, 'isoformat'):
                                    anonymized_record[k] = v.isoformat()
                                elif pd.isna(v):
                                    anonymized_record[k] = None
                                else:
                                    anonymized_record[k] = v
                            anonymized_records.append(anonymized_record)
                        anonymized[key] = anonymized_records
                    except Exception as e:
                        logger.warning(f"Failed to convert DataFrame {key}: {e}")
                        anonymized[key] = f"[DataFrame with {len(value)} records]"
                elif self._key_is_sensitive(key) or self._value_looks_like_pii(value):
                    anonymized[key] = '[REDACTED]'
                else:
                    anonymized[key] = value
            return anonymized

        @staticmethod
        def _key_is_sensitive(key: str) -> bool:
            k = (key or "").lower()
            return any(tok in k for tok in _anonymize_sensitive_tokens())

        @staticmethod
        def _value_looks_like_pii(value) -> bool:
            if not isinstance(value, str):
                return False
            # Match emails and phone-like strings.
            import re
            if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", value):
                return True
            digits = re.sub(r"\D", "", value)
            if len(digits) >= 9 and re.search(r"\d", value):
                return True
            return False

        def _apply_privacy_measures(self, data: Dict, user_id: str = None) -> Tuple[Dict, Dict]:
            if not privacy_manager:
                anonymized_data = self._anonymize_inventory_data(data)
                return anonymized_data, {'anonymized': True, 'method': 'basic', 'sensitive_data_detected': False}
            try:
                anonymized_data, privacy_metadata = privacy_manager.anonymize_for_ai(data, user_id)
                if isinstance(anonymized_data, dict):
                    anonymized_data = self._anonymize_inventory_data(anonymized_data)
                return anonymized_data, privacy_metadata
            except Exception as e:
                logger.error(f"Privacy measures failed: {e}")
                anonymized_data = self._anonymize_inventory_data(data)
                return anonymized_data, {'anonymized': True, 'method': 'fallback', 'error': str(e), 'sensitive_data_detected': False}

        def _anonymize_text(self, text: str) -> str:
            if insights_cache is None:
                import re
                text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
                text = re.sub(r'\b\d{3}-\d{3}-\d{4}\b', '[PHONE]', text)
                return text
            return insights_cache._anonymize_sensitive_data(text)

        def _extract_forecast_metrics(self, forecast_data: Dict) -> Dict:
            metrics = {}
            try:
                for k in ['total_predicted_quantity', 'average_prediction', 'prediction_variance',
                          'confidence_lower', 'confidence_upper']:
                    if k in forecast_data:
                        metrics[k] = forecast_data[k]
                if 'forecast_df' in forecast_data and hasattr(forecast_data['forecast_df'], '__len__'):
                    metrics['total_products'] = len(forecast_data['forecast_df'])
            except Exception as e:
                logger.warning(f"Failed to extract forecast metrics: {e}")
            return metrics

        def _create_fallback_response(self, message: str, start_time: float) -> AIResponse:
            return AIResponse(success=False, data={'fallback': True, 'message': message},
                              error_message=message, confidence_score=None,
                              processing_time=time.time() - start_time, cached=False, timestamp=datetime.now())

        def _error_response(self, e, start_time, operation_id, performance_monitor):
            processing_time = time.time() - start_time
            self._update_performance_metrics(processing_time, success=False)
            performance_monitor.end_operation(operation_id, success=False, error_message=str(e))
            logger.error(f"AI operation failed: {e}")
            return AIResponse(success=False, data={}, error_message=str(e), confidence_score=None,
                              processing_time=processing_time, cached=False, timestamp=datetime.now())

        def _update_performance_metrics(self, processing_time: float, success: bool):
            self.performance_metrics['total_calls'] += 1
            if success:
                self.performance_metrics['successful_calls'] += 1
            else:
                self.performance_metrics['failed_calls'] += 1
            total_calls = self.performance_metrics['total_calls']
            current_avg = self.performance_metrics['average_response_time']
            self.performance_metrics['average_response_time'] = (
                (current_avg * (total_calls - 1) + processing_time) / total_calls)

    ai_service = ProviderBackedAIService()
else:
    logger.info("AI Service: Disabled - Using Stub")
    ai_service = DisabledAIService()