"""
AI Configuration Manager
Handles secure loading and validation of AI service configuration.
"""
import os
import logging
from typing import Dict, Tuple, Optional, Any, List
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class AIConfigManager:
    """
    Manages AI service configuration with security and validation.
    
    Provides secure loading of API keys, configuration validation,
    and feature toggle management for AI services.
    """
    
    def __init__(self):
        """Initialize the configuration manager."""
        self._config_cache = None
        self._api_key_validated = False
        self._environment = os.getenv('FLASK_ENV', 'development')
        
    def load_api_configuration(self) -> Dict:
        """
        Load AI API configuration from environment variables.
        
        Returns:
            Dict containing AI configuration settings
            
        Note:
            API key is masked in returned configuration for security
        """
        if self._config_cache is not None:
            return self._config_cache
            
        config = {
            'api_key': os.getenv('GEMINI_API_KEY', ''),
            'model_name': os.getenv('GEMINI_MODEL_NAME', 'gemini-2.0-flash-exp'),
            'timeout': self._get_env_specific_setting('GEMINI_TIMEOUT', 30),
            'max_retries': int(os.getenv('GEMINI_MAX_RETRIES', '3')),
            'cache_ttl': int(os.getenv('GEMINI_CACHE_TTL', '3600')),
            'retry_delay': float(os.getenv('GEMINI_RETRY_DELAY', '1.0')),
            'backoff_factor': float(os.getenv('GEMINI_BACKOFF_FACTOR', '2.0')),
            'features_enabled': os.getenv('AI_FEATURES_ENABLED', 'true').lower() == 'true',
            'natural_language_enabled': os.getenv('AI_NATURAL_LANGUAGE_ENABLED', 'true').lower() == 'true',
            'smart_reports_enabled': os.getenv('AI_SMART_REPORTS_ENABLED', 'true').lower() == 'true',
            'enhanced_forecasting_enabled': os.getenv('AI_ENHANCED_FORECASTING_ENABLED', 'true').lower() == 'true',
            'dashboard_insights_enabled': os.getenv('AI_DASHBOARD_INSIGHTS_ENABLED', 'true').lower() == 'true',
            'cache_max_size_mb': int(os.getenv('AI_CACHE_MAX_SIZE_MB', '100')),
            'enable_compression': os.getenv('AI_ENABLE_COMPRESSION', 'true').lower() == 'true',
            'circuit_breaker_enabled': os.getenv('AI_CIRCUIT_BREAKER_ENABLED', 'true').lower() == 'true',
            'circuit_breaker_threshold': int(os.getenv('AI_CIRCUIT_BREAKER_THRESHOLD', '5')),
            'circuit_breaker_timeout': int(os.getenv('AI_CIRCUIT_BREAKER_TIMEOUT', '60')),
            'content_safety_enabled': os.getenv('AI_CONTENT_SAFETY_ENABLED', 'true').lower() == 'true',
            'content_safety_threshold': os.getenv('AI_CONTENT_SAFETY_THRESHOLD', 'MEDIUM'),
            'block_harmful_content': os.getenv('AI_BLOCK_HARMFUL_CONTENT', 'true').lower() == 'true'
        }
        
        # Cache configuration (with masked API key for security)
        self._config_cache = config.copy()
        if config['api_key']:
            self._config_cache['api_key'] = self._mask_api_key(config['api_key'])
            
        return self._config_cache
    
    def _get_env_specific_setting(self, setting_name: str, default_value: Any) -> Any:
        """
        Get environment-specific setting with fallback to general setting.
        
        Args:
            setting_name: Base setting name
            default_value: Default value if no setting found
            
        Returns:
            Environment-specific or general setting value
        """
        # Try environment-specific setting first
        env_specific_key = f"{self._environment.upper()}_{setting_name}"
        env_specific_value = os.getenv(env_specific_key)
        
        if env_specific_value is not None:
            # Convert to appropriate type based on default_value
            if isinstance(default_value, int):
                return int(env_specific_value)
            elif isinstance(default_value, float):
                return float(env_specific_value)
            elif isinstance(default_value, bool):
                return env_specific_value.lower() == 'true'
            return env_specific_value
        
        # Fall back to general setting
        general_value = os.getenv(setting_name, str(default_value))
        
        # Convert to appropriate type
        if isinstance(default_value, int):
            return int(general_value)
        elif isinstance(default_value, float):
            return float(general_value)
        elif isinstance(default_value, bool):
            return general_value.lower() == 'true'
        return general_value
    
    def get_api_key(self) -> str:
        """
        Get the raw API key for actual API calls.
        
        Returns:
            The unmasked API key
            
        Warning:
            This method returns the actual API key. Use with caution.
        """
        return os.getenv('GEMINI_API_KEY', '')
    
    def validate_api_key(self, api_key: Optional[str] = None) -> Tuple[bool, str]:
        """
        Validate the API key format and presence.
        
        Args:
            api_key: Optional API key to validate. If None, uses environment key.
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if api_key is None:
            api_key = self.get_api_key()
            
        if not api_key:
            return False, "Gemini API key is missing. Please set GEMINI_API_KEY environment variable."
            
        # Check for null bytes and other problematic characters
        if '\x00' in api_key or any(ord(c) < 32 for c in api_key if c not in '\t\n\r'):
            return False, "Invalid Gemini API key format. Key contains invalid control characters."
            
        if not api_key.startswith('AIza'):
            return False, "Invalid Gemini API key format. Key should start with 'AIza'."
            
        if len(api_key) < 30:
            return False, "Gemini API key appears to be too short. Please verify the key."
            
        # Additional format validation - allow alphanumeric, underscore, and hyphen
        if not re.match(r'^AIza[A-Za-z0-9_-]+$', api_key):
            return False, "Invalid Gemini API key format. Key contains invalid characters."
            
        self._api_key_validated = True
        return True, "API key validation successful."
    
    def validate_configuration(self) -> Tuple[bool, List[str]]:
        """
        Validate the complete AI configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate API key
        is_key_valid, key_error = self.validate_api_key()
        if not is_key_valid:
            errors.append(key_error)
        
        # Validate model name
        config = self.load_api_configuration()
        valid_models = ['gemini-2.0-flash-exp', 'gemini-1.5-pro', 'gemini-1.5-flash']
        if config['model_name'] not in valid_models:
            errors.append(f"Invalid model name: {config['model_name']}. Valid options: {', '.join(valid_models)}")
        
        # Validate timeout settings
        if config['timeout'] < 5 or config['timeout'] > 300:
            errors.append(f"Invalid timeout: {config['timeout']}. Must be between 5 and 300 seconds.")
        
        # Validate retry settings
        if config['max_retries'] < 0 or config['max_retries'] > 10:
            errors.append(f"Invalid max_retries: {config['max_retries']}. Must be between 0 and 10.")
        
        # Validate cache settings
        if config['cache_ttl'] < 0:
            errors.append(f"Invalid cache_ttl: {config['cache_ttl']}. Must be non-negative.")
        
        if config['cache_max_size_mb'] < 1 or config['cache_max_size_mb'] > 1000:
            errors.append(f"Invalid cache_max_size_mb: {config['cache_max_size_mb']}. Must be between 1 and 1000 MB.")
        
        # Validate rate limiting
        rate_limits = self.get_rate_limit_settings()
        if rate_limits['requests_per_minute'] < 1 or rate_limits['requests_per_minute'] > 1000:
            errors.append(f"Invalid requests_per_minute: {rate_limits['requests_per_minute']}. Must be between 1 and 1000.")
        
        # Validate content safety threshold
        valid_thresholds = ['LOW', 'MEDIUM', 'HIGH']
        if config['content_safety_threshold'] not in valid_thresholds:
            errors.append(f"Invalid content_safety_threshold: {config['content_safety_threshold']}. Valid options: {', '.join(valid_thresholds)}")
        
        return len(errors) == 0, errors
    
    def get_rate_limit_settings(self) -> Dict:
        """
        Get rate limiting configuration.
        
        Returns:
            Dict containing rate limit settings
        """
        return {
            'requests_per_minute': self._get_env_specific_setting('GEMINI_RATE_LIMIT_RPM', 60),
            'requests_per_day': int(os.getenv('GEMINI_RATE_LIMIT_RPD', '1000')),
            'burst_limit': int(os.getenv('GEMINI_BURST_LIMIT', '10'))
        }
    
    def get_timeout_settings(self) -> Dict:
        """
        Get timeout and retry configuration.
        
        Returns:
            Dict containing timeout settings
        """
        config = self.load_api_configuration()
        return {
            'timeout': config['timeout'],
            'max_retries': config['max_retries'],
            'retry_delay': config['retry_delay'],
            'backoff_factor': config['backoff_factor']
        }
    
    def is_ai_enabled(self) -> bool:
        """
        Check if AI features are enabled.
        
        Returns:
            True if AI features are enabled and API key is valid
        """
        config = self.load_api_configuration()
        if not config['features_enabled']:
            return False
            
        # Validate API key if not already validated
        if not self._api_key_validated:
            is_valid, _ = self.validate_api_key()
            return is_valid
            
        return True
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """
        Check if a specific AI feature is enabled.
        
        Args:
            feature_name: Name of the feature to check
            
        Returns:
            True if the feature is enabled
        """
        if not self.is_ai_enabled():
            return False
            
        config = self.load_api_configuration()
        feature_map = {
            'natural_language': config['natural_language_enabled'],
            'smart_reports': config['smart_reports_enabled'],
            'enhanced_forecasting': config['enhanced_forecasting_enabled'],
            'dashboard_insights': config['dashboard_insights_enabled']
        }
        
        return feature_map.get(feature_name, False)
    
    def get_security_settings(self) -> Dict:
        """
        Get security-related configuration.
        
        Returns:
            Dict containing security settings
        """
        return {
            'mask_sensitive_data': os.getenv('AI_MASK_SENSITIVE_DATA', 'true').lower() == 'true',
            'log_api_calls': os.getenv('AI_LOG_API_CALLS', 'true').lower() == 'true',
            'audit_enabled': os.getenv('AI_AUDIT_ENABLED', 'true').lower() == 'true',
            'data_retention_days': int(os.getenv('AI_DATA_RETENTION_DAYS', '30')),
            'auto_purge_cache': os.getenv('AI_AUTO_PURGE_CACHE', 'true').lower() == 'true',
            'debug_logging': os.getenv('AI_DEBUG_LOGGING', 'false').lower() == 'true',
            'performance_monitoring': os.getenv('AI_PERFORMANCE_MONITORING', 'true').lower() == 'true',
            'log_performance_metrics': os.getenv('AI_LOG_PERFORMANCE_METRICS', 'true').lower() == 'true'
        }
    
    def get_environment_config(self) -> Dict:
        """
        Get environment-specific configuration summary.
        
        Returns:
            Dict containing environment-specific settings
        """
        return {
            'environment': self._environment,
            'is_development': self._environment == 'development',
            'is_production': self._environment == 'production',
            'debug_mode': self._environment == 'development',
            'strict_validation': self._environment == 'production'
        }
    
    def get_provider_name(self) -> str:
        """
        Return the active AI provider short name (Phase 3, §4.4).

        Defaults to 'gemini' for backward compatibility with the existing
        GEMINI_* configuration.
        """
        return os.getenv('AI_PROVIDER', 'gemini').lower()

    def get_provider_config(self) -> Dict:
        """
        Return provider-specific configuration for the active provider.

        Reads the env-var sets documented in §4.4 so each provider can be
        configured independently while keeping all legacy GEMINI_* vars.
        """
        provider = self.get_provider_name()
        env = {
            'ollama': {
                'host': os.getenv('OLLAMA_HOST', 'http://localhost:11434'),
                'model': os.getenv('OLLAMA_MODEL', 'llama3'),
            },
            'lmstudio': {
                'endpoint': os.getenv('LMSTUDIO_ENDPOINT', 'http://localhost:1234/v1'),
                'model': os.getenv('LMSTUDIO_MODEL', 'local-model'),
                'api_key': os.getenv('LMSTUDIO_API_KEY', 'lm-studio'),
            },
            'openrouter': {
                'api_key': os.getenv('OPENROUTER_API_KEY', ''),
                'model': os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini'),
                'base_url': os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
            },
            'openai': {
                'api_key': os.getenv('OPENAI_API_KEY', ''),
                'model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                'base_url': os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
            },
            'azure_openai': {
                'endpoint': os.getenv('AZURE_OPENAI_ENDPOINT', '').rstrip('/'),
                'deployment': os.getenv('AZURE_OPENAI_DEPLOYMENT', ''),
                'api_key': os.getenv('AZURE_OPENAI_API_KEY', ''),
                'api_version': os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview'),
            },
            'custom': {
                'endpoint': os.getenv('CUSTOM_AI_ENDPOINT', 'http://localhost:8000/v1'),
                'api_key': os.getenv('CUSTOM_AI_API_KEY', ''),
                'model': os.getenv('CUSTOM_AI_MODEL', 'custom-model'),
            },
            'gemini': {
                'api_key': os.getenv('GEMINI_API_KEY', ''),
                'model': os.getenv('GEMINI_MODEL_NAME', 'gemini-2.0-flash-exp'),
            },
        }
        return env.get(provider, {'model': self.load_api_configuration().get('model_name')})

    def _mask_api_key(self, api_key: str) -> str:
        """
        Mask API key for logging and display purposes.
        
        Args:
            api_key: The API key to mask
            
        Returns:
            Masked API key showing only first 8 and last 4 characters
        """
        if len(api_key) < 12:
            return "***INVALID***"
        return f"{api_key[:8]}...{api_key[-4:]}"
    
    def log_configuration_status(self) -> None:
        """Log the current configuration status for debugging."""
        config = self.load_api_configuration()
        security = self.get_security_settings()
        env_config = self.get_environment_config()
        
        logger.info("AI Configuration Status:")
        logger.info(f"  Environment: {env_config['environment']}")
        logger.info(f"  Features Enabled: {config['features_enabled']}")
        logger.info(f"  API Key Present: {'Yes' if self.get_api_key() else 'No'}")
        logger.info(f"  Model: {config['model_name']}")
        logger.info(f"  Timeout: {config['timeout']}s")
        logger.info(f"  Max Retries: {config['max_retries']}")
        logger.info(f"  Cache TTL: {config['cache_ttl']}s")
        logger.info(f"  Natural Language: {config['natural_language_enabled']}")
        logger.info(f"  Smart Reports: {config['smart_reports_enabled']}")
        logger.info(f"  Enhanced Forecasting: {config['enhanced_forecasting_enabled']}")
        logger.info(f"  Dashboard Insights: {config['dashboard_insights_enabled']}")
        logger.info(f"  Circuit Breaker: {config['circuit_breaker_enabled']}")
        logger.info(f"  Content Safety: {config['content_safety_enabled']}")
        logger.info(f"  Audit Enabled: {security['audit_enabled']}")
        logger.info(f"  Performance Monitoring: {security['performance_monitoring']}")
    
    def get_production_checklist(self) -> Dict[str, bool]:
        """
        Get production readiness checklist.
        
        Returns:
            Dict with checklist items and their status
        """
        config = self.load_api_configuration()
        security = self.get_security_settings()
        env_config = self.get_environment_config()
        
        checklist = {
            'api_key_set': bool(self.get_api_key()),
            'api_key_valid': self.validate_api_key()[0],
            'production_environment': env_config['is_production'],
            'debug_logging_disabled': not security['debug_logging'],
            'audit_enabled': security['audit_enabled'],
            'content_safety_enabled': config['content_safety_enabled'],
            'circuit_breaker_enabled': config['circuit_breaker_enabled'],
            'data_retention_configured': security['data_retention_days'] > 0,
            'rate_limits_configured': self.get_rate_limit_settings()['requests_per_minute'] > 0
        }
        
        return checklist
    
    def validate_production_readiness(self) -> Tuple[bool, List[str]]:
        """
        Validate production readiness.
        
        Returns:
            Tuple of (is_ready, list_of_issues)
        """
        checklist = self.get_production_checklist()
        issues = []
        
        if not checklist['api_key_set']:
            issues.append("Gemini API key is not set")
        
        if not checklist['api_key_valid']:
            issues.append("Gemini API key is invalid")
        
        if not checklist['production_environment']:
            issues.append("Environment is not set to production")
        
        if checklist['debug_logging_disabled'] is False:
            issues.append("Debug logging should be disabled in production")
        
        if not checklist['audit_enabled']:
            issues.append("Audit logging should be enabled in production")
        
        if not checklist['content_safety_enabled']:
            issues.append("Content safety should be enabled in production")
        
        if not checklist['circuit_breaker_enabled']:
            issues.append("Circuit breaker should be enabled in production")
        
        return len(issues) == 0, issues


# Global configuration manager instance
ai_config = AIConfigManager()