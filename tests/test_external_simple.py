#!/usr/bin/env python3
"""
Simple test for external factor integration property.
"""
import pandas as pd
from utils.enhanced_forecasting import EnhancedForecastingSystem
from unittest.mock import MagicMock

def test_external_factor_integration():
    """Test that external factors are integrated when available."""
    
    # Create test data with external factors
    forecast_data = {
        'forecast_df': pd.DataFrame([
            {'product_id': 'TEST_001', 'predicted_quantity': 100},
            {'product_id': 'TEST_002', 'predicted_quantity': 200}
        ]),
        'business_context': {
            'promotional_period': True,
            'season': 'peak',
            'new_product_launch': True
        }
    }
    
    historical_data = {'sales_data': pd.DataFrame()}
    
    # Create system with mock AI service
    mock_ai = MagicMock()
    mock_ai._anonymize_inventory_data.side_effect = lambda x: x
    mock_ai._create_forecast_enhancement_prompt.return_value = 'test prompt'
    mock_ai.circuit_breaker.call.return_value = {
        'external_factors': ['promotional impact', 'seasonal trends'],
        'confidence_score': 85
    }
    
    system = EnhancedForecastingSystem(ai_service=mock_ai)
    
    # Test the enhancement
    enhancement = system.enhance_forecast_with_ai(
        forecast_data, historical_data, forecast_data['business_context']
    )
    
    # Verify external factors are identified
    assert len(enhancement.external_factors) > 0, "External factors should be identified"
    
    # Check that external factors mention relevant terms
    external_factor_text = ' '.join(enhancement.external_factors).lower()
    
    # Should mention promotional or seasonal factors
    has_relevant_factors = any(keyword in external_factor_text for keyword in [
        'ترويج', 'عرض', 'موسم', 'promotion', 'season'
    ])
    
    assert has_relevant_factors, f"External factors should mention relevant terms. Got: {enhancement.external_factors}"
    
    print("✅ External factor integration test passed!")
    print(f"External factors identified: {enhancement.external_factors}")
    return True

if __name__ == "__main__":
    test_external_factor_integration()