#!/usr/bin/env python3
"""
Test Enhanced Forecasting System
Tests the integration of AI-powered forecasting enhancements.
"""
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

def test_enhanced_forecasting_system():
    """Test the enhanced forecasting system with sample data."""
    try:
        from utils.enhanced_forecasting import enhanced_forecasting_system
        from utils.ai_service import ai_service
        
        print("=== Enhanced Forecasting System Test ===")
        
        # Create sample forecast data
        forecast_dates = pd.date_range('2024-02-01', periods=30, freq='D')
        forecast_df = pd.DataFrame({
            'كود الصنف': ['P001', 'P002', 'P003'] * 10,
            'اسم الصنف': ['Product A', 'Product B', 'Product C'] * 10,
            'تاريخ البيع': forecast_dates,
            'الكمية المتوقعة': [50, 75, 30, 45, 80, 25, 60, 70, 35, 55] * 3,
            'السعر': [10.0, 15.0, 20.0] * 10,
            'القسم': ['Electronics', 'Clothing', 'Books'] * 10
        })
        
        forecast_data = {
            'forecast_df': forecast_df,
            'total_products': 3,
            'forecast_period': 30,
            'business_context': {
                'season': 'peak',
                'promotional_period': True,
                'market_conditions': 'stable'
            }
        }
        
        # Create sample historical data
        historical_dates = pd.date_range('2024-01-01', periods=30, freq='D')
        historical_df = pd.DataFrame({
            'product_code': ['P001', 'P002', 'P003'] * 10,
            'quantity_sold': [45, 70, 28, 40, 75, 22, 55, 65, 32, 50] * 3,
            'sale_date': historical_dates,
            'revenue': [450, 1050, 560, 400, 1125, 440, 550, 975, 640, 500] * 3
        })
        
        historical_data = {
            'sales_data': historical_df,
            'total_sales': historical_df['quantity_sold'].sum(),
            'average_daily_sales': historical_df['quantity_sold'].mean()
        }
        
        print(f"Forecast data: {len(forecast_df)} records, {forecast_data['total_products']} products")
        print(f"Historical data: {len(historical_df)} records, total sales: {historical_data['total_sales']}")
        
        # Test enhanced forecasting
        print("\n=== Running Enhanced Forecasting ===")
        start_time = datetime.now()
        
        enhancement = enhanced_forecasting_system.enhance_forecast_with_ai(
            forecast_data, historical_data, forecast_data['business_context']
        )
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print(f"Processing time: {processing_time:.2f} seconds")
        print(f"Enhancement confidence score: {enhancement.confidence_score:.1f}%")
        
        # Display results
        print(f"\n=== Enhancement Results ===")
        print(f"Confidence intervals: {enhancement.confidence_intervals}")
        print(f"Risk factors ({len(enhancement.risk_factors)}):")
        for i, risk in enumerate(enhancement.risk_factors, 1):
            print(f"  {i}. {risk}")
        
        print(f"\nExternal factors ({len(enhancement.external_factors)}):")
        for i, factor in enumerate(enhancement.external_factors, 1):
            print(f"  {i}. {factor}")
        
        print(f"\nAdjustments ({len(enhancement.adjustments)}):")
        for i, adjustment in enumerate(enhancement.adjustments, 1):
            print(f"  {i}. {adjustment}")
        
        print(f"\nRecommendations ({len(enhancement.recommendations)}):")
        for i, rec in enumerate(enhancement.recommendations[:5], 1):
            print(f"  {i}. {rec}")
        
        return True
        
    except Exception as e:
        print(f"Enhanced forecasting test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ai_service_integration():
    """Test AI service integration with enhanced forecasting."""
    try:
        from utils.ai_service import ai_service
        
        print("\n=== AI Service Integration Test ===")
        
        # Create sample data
        forecast_data = {
            'forecast_df': pd.DataFrame({
                'product_code': ['P001', 'P002'],
                'predicted_quantity': [100, 150],
                'forecast_date': pd.date_range('2024-02-01', periods=2)
            }),
            'total_predicted_quantity': 250,
            'average_prediction': 125,
            'prediction_variance': 625
        }
        
        historical_data = {
            'sales_data': pd.DataFrame({
                'product_code': ['P001', 'P002'],
                'quantity_sold': [90, 140],
                'sale_date': pd.date_range('2024-01-01', periods=2)
            }),
            'historical_average': 115,
            'historical_variance': 625
        }
        
        # Test AI service enhance_forecast method
        response = ai_service.enhance_forecast(forecast_data, historical_data)
        
        print(f"AI service response success: {response.success}")
        print(f"AI service confidence score: {response.confidence_score}")
        print(f"AI service processing time: {response.processing_time:.3f}s")
        
        if response.success:
            data = response.data
            print(f"\nResponse data keys: {list(data.keys())}")
            
            if 'forecast_validation' in data:
                print(f"Forecast validation: {data['forecast_validation']}")
            
            if 'confidence_intervals' in data:
                print(f"Confidence intervals: {data['confidence_intervals']}")
            
            if 'risk_factors' in data:
                print(f"Risk factors: {len(data['risk_factors'])} identified")
            
            if 'recommendations' in data:
                print(f"Recommendations: {len(data['recommendations'])} generated")
        else:
            print(f"Error: {response.error_message}")
        
        return response.success
        
    except Exception as e:
        print(f"AI service integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_existing_forecast_integration():
    """Test integration with existing forecast files."""
    try:
        from utils.enhanced_forecasting import enhanced_forecasting_system
        
        print("\n=== Existing Forecast Integration Test ===")
        
        # Check if existing forecast file exists
        forecast_file = 'forecast_modules/forecast_summary_model_A.csv'
        
        # Always create a fresh sample file for testing
        print(f"Creating sample forecast file: {forecast_file}")
        
        # Create sample forecast file
        sample_forecast = pd.DataFrame({
            'كود الصنف': ['P001', 'P002', 'P003'],
            'اسم الصنف': ['Product A', 'Product B', 'Product C'],
            'الكمية المتوقعة': [100, 150, 75],
            'تاريخ البيع': ['2024-02-01', '2024-02-02', '2024-02-03'],
            'متوسط البيع اليومي': [90, 140, 70],
            'معدل النمو': [11.1, 7.1, 7.1],
            'الملاحظات': ['فرصة نمو ✅', 'أداء مستقر 🔄', 'أداء مستقر 🔄']
        })
        
        os.makedirs('forecast_modules', exist_ok=True)
        sample_forecast.to_csv(forecast_file, index=False, encoding='utf-8-sig')
        print(f"Sample forecast file created with {len(sample_forecast)} records")
        
        # Verify file was created correctly
        try:
            test_df = pd.read_csv(forecast_file, encoding='utf-8-sig')
            print(f"File verification: {len(test_df)} rows, {len(test_df.columns)} columns")
            print(f"Columns: {list(test_df.columns)}")
        except Exception as verify_error:
            print(f"File verification failed: {verify_error}")
            return False
        
        # Test integration
        historical_data = {
            'sales_data': pd.DataFrame({
                'product_code': ['P001', 'P002', 'P003'],
                'quantity_sold': [85, 135, 65],
                'revenue': [850, 2025, 1300]
            })
        }
        
        enhanced_output = enhanced_forecasting_system.integrate_with_existing_forecast(
            forecast_file, historical_data
        )
        
        print(f"Integration success: {enhanced_output.get('export_ready', False)}")
        
        if enhanced_output.get('export_ready'):
            print(f"Original forecast products: {enhanced_output['original_forecast'].get('total_products', 0)}")
            
            if 'enhancement' in enhanced_output and enhanced_output['enhancement']:
                enhancement = enhanced_output['enhancement']
                print(f"Enhancement confidence: {enhancement.confidence_score:.1f}%")
                print(f"Risk factors: {len(enhancement.risk_factors)}")
                print(f"Recommendations: {len(enhancement.recommendations)}")
            
            if 'summary' in enhanced_output:
                summary = enhanced_output['summary']
                print(f"Summary: {summary.get('summary_text', 'N/A')}")
        else:
            print(f"Integration error: {enhanced_output.get('error', 'Unknown error')}")
        
        return enhanced_output.get('export_ready', False)
        
    except Exception as e:
        print(f"Existing forecast integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting Enhanced Forecasting Tests...")
    
    # Test enhanced forecasting system
    system_success = test_enhanced_forecasting_system()
    
    # Test AI service integration
    ai_integration_success = test_ai_service_integration()
    
    # Test existing forecast integration
    existing_integration_success = test_existing_forecast_integration()
    
    print(f"\n=== Test Results ===")
    print(f"Enhanced forecasting system: {'PASSED' if system_success else 'FAILED'}")
    print(f"AI service integration: {'PASSED' if ai_integration_success else 'FAILED'}")
    print(f"Existing forecast integration: {'PASSED' if existing_integration_success else 'FAILED'}")
    
    if system_success and ai_integration_success and existing_integration_success:
        print("✅ All enhanced forecasting tests passed!")
    else:
        print("❌ Some tests failed. Check the output above for details.")