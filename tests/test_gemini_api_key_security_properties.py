"""
Property-based tests for Gemini API key security.

Feature: gemini-api-integration
Tests API key security properties to ensure sensitive credentials are properly protected.
"""
import os
import pytest
import logging
from hypothesis import given, strategies as st, settings
from unittest.mock import patch, MagicMock
import tempfile
import json

# Import the modules to test
from utils.ai_config import AIConfigManager


class TestAPIKeySecurityProperties:
    """
    Property-based tests for API key security.
    
    **Validates: Requirements 1.1, 1.3**
    """
    
    @given(api_key=st.text(min_size=30, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    @settings(max_examples=10, deadline=3000)  # Reduced examples for faster execution
    def test_api_key_never_appears_in_logs(self, api_key):
        """
        Feature: gemini-api-integration, Property 1: API Key Security
        For any application startup, the Gemini API key should be loaded from 
        environment variables and never appear in plain text in logs or error messages.
        
        **Validates: Requirements 1.1, 1.3**
        """
        # Create a simple log capture
        log_messages = []
        
        # Mock the logger to capture messages
        with patch('utils.ai_config.logger') as mock_logger:
            mock_logger.info.side_effect = lambda msg: log_messages.append(str(msg))
            mock_logger.warning.side_effect = lambda msg: log_messages.append(str(msg))
            mock_logger.error.side_effect = lambda msg: log_messages.append(str(msg))
            mock_logger.debug.side_effect = lambda msg: log_messages.append(str(msg))
            
            # Test with environment variable
            with patch.dict(os.environ, {'GEMINI_API_KEY': api_key}, clear=False):
                config_manager = AIConfigManager()
                
                # Load configuration (this should mask the API key)
                config = config_manager.load_api_configuration()
                
                # Check that the API key never appears in captured logs
                for log_message in log_messages:
                    assert api_key not in log_message, f"API key found in log: {log_message}"
                
                # Check that the returned configuration has masked API key
                if 'api_key' in config and config['api_key']:
                    assert config['api_key'] != api_key, "API key should be masked in configuration"
                    # Should be masked with dots or asterisks
                    assert ('...' in config['api_key'] or '*' in config['api_key'] or 
                           'INVALID' in config['api_key']), f"API key should be masked, got: {config['api_key']}"
    
    @given(api_key=st.text(min_size=30, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    @settings(max_examples=10, deadline=3000)
    def test_api_key_validation_security(self, api_key):
        """
        Feature: gemini-api-integration, Property 1: API Key Security
        For any API key validation, sensitive information should not be exposed
        in validation results.
        
        **Validates: Requirements 1.1, 1.3**
        """
        config_manager = AIConfigManager()
        
        # Test key validation - message should not contain the actual key
        is_valid, message = config_manager.validate_api_key(api_key)
        assert api_key not in message, f"API key found in validation message: {message}"
        
        # Test with obviously invalid key
        invalid_key = "obviously_invalid_key_12345"
        is_valid, message = config_manager.validate_api_key(invalid_key)
        assert invalid_key not in message, f"Invalid API key found in validation message: {message}"
    
    @given(api_key=st.text(min_size=30, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    @settings(max_examples=10, deadline=3000)
    def test_api_key_environment_loading(self, api_key):
        """
        Feature: gemini-api-integration, Property 1: API Key Security
        For any configuration, the API key should be loaded from environment variables
        and stored securely without exposure.
        
        **Validates: Requirements 1.1**
        """
        with patch.dict(os.environ, {'GEMINI_API_KEY': api_key}, clear=False):
            config_manager = AIConfigManager()
            
            # Load configuration
            config = config_manager.load_api_configuration()
            
            # Verify API key is loaded but masked in config
            if 'api_key' in config and config['api_key']:
                assert config['api_key'] != api_key, "API key should be masked in returned config"
            
            # Verify raw API key can be retrieved securely (for actual API calls)
            raw_key = config_manager.get_api_key()
            assert raw_key == api_key, "Raw API key should match environment variable"


if __name__ == '__main__':
    # Run the property tests
    pytest.main([__file__, '-v', '--tb=short'])