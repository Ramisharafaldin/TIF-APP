#!/usr/bin/env python3
"""
Test script for enhanced AI service functionality.
"""

def test_enhanced_ai_service():
    """Test the enhanced AI service."""
    try:
        print('=== Enhanced AI Service Test ===')
        
        # Test basic imports
        from utils.ai_service import ai_service
        print('✅ AI service imported successfully')
        
        # Test configuration
        from utils.ai_config import ai_config
        print('✅ AI config imported successfully')
        
        # Test API connection validation
        is_valid, message = ai_service.validate_api_connection()
        print(f'API Connection: {"✅ Valid" if is_valid else "❌ Invalid"}')
        print(f'Message: {message}')
        
        # Test performance metrics
        metrics = ai_service.get_performance_metrics()
        print(f'Performance Metrics: {metrics}')
        
        # Test feature flags
        features = {
            'natural_language': ai_config.is_feature_enabled('natural_language'),
            'smart_reports': ai_config.is_feature_enabled('smart_reports'),
            'enhanced_forecasting': ai_config.is_feature_enabled('enhanced_forecasting')
        }
        print(f'Feature Flags: {features}')
        
        if is_valid:
            print('\n✅ Enhanced AI service is ready!')
            
            # Test a simple insight generation (without actual API call)
            test_data = {
                'total_products': 100,
                'low_stock_items': 15,
                'out_of_stock_items': 3
            }
            
            print(f'\nTesting with sample data: {test_data}')
            print('Note: This would normally call the Gemini API')
            
        return is_valid
        
    except Exception as e:
        print(f'❌ Error testing enhanced AI service: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_enhanced_ai_service()
    exit(0 if success else 1)