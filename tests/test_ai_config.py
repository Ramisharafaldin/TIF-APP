#!/usr/bin/env python3
"""
Test script for AI configuration and API validation.
"""

def test_ai_configuration():
    """Test AI configuration loading and validation."""
    try:
        from utils.ai_config import ai_config
        from modules.ai_insights import validate_ai_service
        
        print('=== AI Configuration Test ===')
        config = ai_config.load_api_configuration()
        print(f'Features Enabled: {config["features_enabled"]}')
        print(f'API Key Present: {"Yes" if ai_config.get_api_key() else "No"}')
        print(f'Model: {config["model_name"]}')
        print(f'Timeout: {config["timeout"]}s')
        print(f'Max Retries: {config["max_retries"]}')
        print(f'Cache TTL: {config["cache_ttl"]}s')
        
        print('\n=== Feature Flags ===')
        print(f'Natural Language: {config["natural_language_enabled"]}')
        print(f'Smart Reports: {config["smart_reports_enabled"]}')
        print(f'Enhanced Forecasting: {config["enhanced_forecasting_enabled"]}')
        
        print('\n=== API Validation Test ===')
        is_valid, message = validate_ai_service()
        print(f'API Valid: {is_valid}')
        print(f'Message: {message}')
        
        if is_valid:
            print('\n✅ AI service is ready!')
        else:
            print('\n❌ AI service has issues')
            
        return is_valid
        
    except Exception as e:
        print(f'❌ Error testing AI configuration: {e}')
        return False

if __name__ == '__main__':
    test_ai_configuration()