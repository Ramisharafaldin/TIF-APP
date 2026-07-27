#!/usr/bin/env python3
"""
Test Smart Report Integration
Tests the integration between AI service and SmartReportGenerator.
"""
import sys
import os
import json
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

def test_smart_report_integration():
    """Test smart report generation with sample data."""
    try:
        from utils.ai_service import ai_service
        from utils.ai_config import ai_config
        
        print("=== Smart Report Integration Test ===")
        print(f"AI Config Status: {ai_config.get_api_key() is not None if ai_config else 'Not available'}")
        print(f"Smart Reports Enabled: {ai_config.is_feature_enabled('smart_reports') if ai_config else 'Not available'}")
        
        # Create sample data
        sample_data = {
            'report_type': 'inventory',
            'sales_data': pd.DataFrame({
                'product_code': ['P001', 'P002', 'P003', 'P004', 'P005'],
                'revenue': [1500, 2300, 800, 1200, 950],
                'sale_date': pd.date_range('2024-01-01', periods=5, freq='D')
            }),
            'inventory_data': pd.DataFrame({
                'product_code': ['P001', 'P002', 'P003', 'P004', 'P005'],
                'product_name': ['Product A', 'Product B', 'Product C', 'Product D', 'Product E'],
                'Last_on_hand': [50, 25, 5, 0, 100],
                'inventory_value': [10.0, 15.0, 20.0, 25.0, 8.0],
                'supplier_name': ['Supplier 1', 'Supplier 2', 'Supplier 1', 'Supplier 3', 'Supplier 2'],
                'item_category1': ['Electronics', 'Clothing', 'Electronics', 'Books', 'Clothing']
            }),
            'business_context': {
                'season': 'peak',
                'market_conditions': 'stable'
            }
        }
        
        print("\n=== Sample Data Summary ===")
        print(f"Sales records: {len(sample_data['sales_data'])}")
        print(f"Inventory items: {len(sample_data['inventory_data'])}")
        print(f"Total revenue: {sample_data['sales_data']['revenue'].sum()}")
        print(f"Low stock items: {len(sample_data['inventory_data'][sample_data['inventory_data']['Last_on_hand'] < 10])}")
        
        # Test smart report generation
        print("\n=== Generating Smart Report ===")
        start_time = datetime.now()
        
        response = ai_service.generate_smart_report(sample_data, 'inventory')
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print(f"Processing time: {processing_time:.2f} seconds")
        print(f"Success: {response.success}")
        print(f"Confidence score: {response.confidence_score}")
        
        if response.success:
            report_data = response.data
            print(f"\n=== Report Summary ===")
            print(f"Title: {report_data.get('title', 'N/A')}")
            print(f"Report type: {report_data.get('report_type', 'N/A')}")
            print(f"Data quality score: {report_data.get('data_quality_score', 'N/A')}")
            print(f"Number of insights: {len(report_data.get('insights', []))}")
            print(f"Number of recommendations: {len(report_data.get('recommendations', []))}")
            
            print(f"\n=== Executive Summary ===")
            print(report_data.get('executive_summary', 'No summary available'))
            
            print(f"\n=== Key Metrics ===")
            key_metrics = report_data.get('key_metrics', {})
            for metric, value in key_metrics.items():
                print(f"- {metric}: {value}")
            
            print(f"\n=== Recommendations ===")
            recommendations = report_data.get('recommendations', [])
            for i, rec in enumerate(recommendations[:5], 1):
                print(f"{i}. {rec}")
            
            print(f"\n=== Risk Assessment ===")
            print(report_data.get('risk_assessment', 'No risk assessment available'))
            
            # Test different report types
            print(f"\n=== Testing Sales Report ===")
            sales_response = ai_service.generate_smart_report(sample_data, 'sales')
            print(f"Sales report success: {sales_response.success}")
            if sales_response.success:
                print(f"Sales report title: {sales_response.data.get('title', 'N/A')}")
            
        else:
            print(f"Error: {response.error_message}")
            
        return response.success
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_smart_report_generator_standalone():
    """Test SmartReportGenerator independently."""
    try:
        from utils.smart_report_generator import SmartReportGenerator
        from utils.ai_service import ai_service
        
        print("\n=== SmartReportGenerator Standalone Test ===")
        
        # Create generator instance
        generator = SmartReportGenerator(ai_service)
        
        # Create sample base report
        base_report = {
            'report_type': 'inventory',
            'total_products': 5,
            'inventory_data': pd.DataFrame({
                'product_code': ['P001', 'P002', 'P003'],
                'Last_on_hand': [50, 5, 0],
                'inventory_value': [10.0, 15.0, 20.0]
            }),
            'sales_data': pd.DataFrame({
                'product_code': ['P001', 'P002'],
                'revenue': [1500, 800]
            })
        }
        
        # Test executive summary generation
        summary = generator.generate_executive_summary(base_report)
        print(f"Executive summary: {summary}")
        
        # Test trend identification
        trends = generator.identify_trends_and_patterns(base_report)
        print(f"Trends identified: {len(trends.get('positive_trends', []) + trends.get('negative_trends', []))}")
        
        # Test recommendations
        analysis = {'low_stock_items': 1, 'out_of_stock_items': 1}
        business_context = {'season': 'peak'}
        recommendations = generator.generate_recommendations(analysis, business_context)
        print(f"Recommendations generated: {len(recommendations)}")
        for i, rec in enumerate(recommendations[:3], 1):
            print(f"  {i}. {rec}")
        
        return True
        
    except Exception as e:
        print(f"Standalone test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting Smart Report Integration Tests...")
    
    # Test standalone generator
    standalone_success = test_smart_report_generator_standalone()
    
    # Test full integration
    integration_success = test_smart_report_integration()
    
    print(f"\n=== Test Results ===")
    print(f"Standalone test: {'PASSED' if standalone_success else 'FAILED'}")
    print(f"Integration test: {'PASSED' if integration_success else 'FAILED'}")
    
    if standalone_success and integration_success:
        print("✅ All tests passed! Smart report integration is working.")
    else:
        print("❌ Some tests failed. Check the output above for details.")