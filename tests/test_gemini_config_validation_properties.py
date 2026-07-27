"""
Property-based tests for Gemini API configuration validation.

Feature: gemini-api-integration
Tests API configuration validation properties without importing AI service dependencies.
"""
import os
import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import patch

# Import only the configuration manager to avoid dependency issues
from utils.ai_config import AIConfigManager


class TestAPIConfigValidationProperties:
    """
    Property-based tests for API configuration validation.
    
    **Validates: Requirements 1.2, 1.3**
    """
    
    @given(
        api_key=st.one_of(
            st.text(min_size=10, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-')).map(lambda x: 'AIza' + x),  # Valid format
            st.text(min_size=10, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),  # Invalid format (no AIza prefix)
            st.just(''),  # Empty
            st.just('invalid_key')  # Obviously invalid
        )
    )
    @settings(max_examples=8, deadline=2000)
    def test_api_key_validation_consistency(self, api_key):
        """
        Feature: gemini-api-integration, Property 2: API Connection Validation
        For any API key configuration, validation should return consistent results
        based on the key format.
        
        **Validates: Requirements 1.2, 1.3**
        """
        config_manager = AIConfigManager()
        
        # Test key format validation
        is_valid, message = config_manager.validate_api_key(api_key)
        
        # Should always return proper types
        assert isinstance(is_valid, bool), "Should return boolean status"
        assert isinstance(message, str), "Should return string message"
        assert len(message) > 0, "Message should not be empty"
        
        # Check validation logic consistency
        if api_key and api_key.startswith('AIza') and len(api_key) >= 30:
            assert is_valid, f"Valid format key should pass validation: {api_key[:10]}..."
            assert "success" in message.lower(), f"Success message should indicate success: {message}"
        else:
            assert not is_valid, f"Invalid format key should fail validation: {api_key[:10]}..."
            assert any(word in message.lower() for word in ['invalid', 'missing', 'short', 'format']), \
                   f"Error message should be descriptive: {message}"
    
    @given(
        api_key=st.text(min_size=10, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-')).map(lambda x: 'AIza' + x),
        config_values=st.dictionaries(
            keys=st.sampled_from(['timeout', 'max_retries', 'cache_ttl']),
            values=st.integers(min_value=1, max_value=100)
        )
    )
    @settings(max_examples=6, deadline=2000)
    def test_configuration_loading_consistency(self, api_key, config_values):
        """
        Feature: gemini-api-integration, Property 3: Configuration Consistency
        For any configuration settings, the settings should be applied consistently
        across all AI service operations.
        
        **Validates: Requirements 1.4, 1.5**
        """
        # Create environment with API key and config values
        env_vars = {'GEMINI_API_KEY': api_key}
        for key, value in config_values.items():
            env_vars[f'GEMINI_{key.upper()}'] = str(value)
        
        with patch.dict(os.environ, env_vars, clear=False):
            config_manager = AIConfigManager()
            
            # Load configuration
            config = config_manager.load_api_configuration()
            
            # Verify all configuration values are loaded correctly
            for key, expected_value in config_values.items():
                assert config[key] == expected_value, f"Configuration {key} should be {expected_value}, got {config[key]}"
            
            # Verify API key is present but masked
            assert 'api_key' in config, "API key should be in configuration"
            if config['api_key']:
                assert config['api_key'] != api_key, "API key should be masked in configuration"
            
            # Verify timeout and retry settings are accessible
            timeout_settings = config_manager.get_timeout_settings()
            assert isinstance(timeout_settings, dict), "Timeout settings should be a dictionary"
            assert 'timeout' in timeout_settings, "Timeout should be in timeout settings"
            assert 'max_retries' in timeout_settings, "Max retries should be in timeout settings"
    
    @given(
        api_key=st.text(min_size=10, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='_-')).map(lambda x: 'AIza' + x)
    )
    @settings(max_examples=5, deadline=2000)
    def test_configuration_validation_completeness(self, api_key):
        """
        Feature: gemini-api-integration, Property 3: Configuration Consistency
        For any valid API key, configuration validation should check all required settings.
        
        **Validates: Requirements 1.4, 1.5**
        """
        with patch.dict(os.environ, {'GEMINI_API_KEY': api_key}, clear=False):
            config_manager = AIConfigManager()
            
            # Test complete configuration validation
            is_valid, errors = config_manager.validate_configuration()
            
            # Should return proper types
            assert isinstance(is_valid, bool), "Should return boolean validation result"
            assert isinstance(errors, list), "Should return list of errors"
            
            # If configuration is valid, errors should be empty
            if is_valid:
                assert len(errors) == 0, f"Valid configuration should have no errors, got: {errors}"
            else:
                assert len(errors) > 0, "Invalid configuration should have error messages"
                # Each error should be a non-empty string
                for error in errors:
                    assert isinstance(error, str), "Each error should be a string"
                    assert len(error) > 0, "Each error message should not be empty"
    
    @given(
        feature_name=st.sampled_from(['natural_language', 'smart_reports', 'enhanced_forecasting', 'dashboard_insights'])
    )
    @settings(max_examples=4, deadline=2000)
    def test_feature_toggle_consistency(self, feature_name):
        """
        Feature: gemini-api-integration, Property 3: Configuration Consistency
        For any feature toggle, the configuration should consistently report feature status.
        
        **Validates: Requirements 1.4, 1.5**
        """
        api_key = 'AIzaTestKey123456789012345678901234567890'
        
        # Test with feature enabled
        env_vars_enabled = {
            'GEMINI_API_KEY': api_key,
            'AI_FEATURES_ENABLED': 'true',
            f'AI_{feature_name.upper()}_ENABLED': 'true'
        }
        
        with patch.dict(os.environ, env_vars_enabled, clear=False):
            config_manager = AIConfigManager()
            
            # Feature should be enabled
            assert config_manager.is_ai_enabled(), "AI should be enabled"
            assert config_manager.is_feature_enabled(feature_name), f"{feature_name} should be enabled"
        
        # Test with feature disabled
        env_vars_disabled = {
            'GEMINI_API_KEY': api_key,
            'AI_FEATURES_ENABLED': 'true',
            f'AI_{feature_name.upper()}_ENABLED': 'false'
        }
        
        with patch.dict(os.environ, env_vars_disabled, clear=False):
            config_manager = AIConfigManager()
            
            # AI should be enabled but specific feature should be disabled
            assert config_manager.is_ai_enabled(), "AI should be enabled"
            assert not config_manager.is_feature_enabled(feature_name), f"{feature_name} should be disabled"


if __name__ == '__main__':
    # Run the property tests
    pytest.main([__file__, '-v', '--tb=short'])