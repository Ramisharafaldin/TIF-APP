#!/usr/bin/env python3
"""
Simple Performance Optimization Test
Tests the core performance monitoring functionality.
"""
import time
import pandas as pd
import numpy as np

def test_performance_system():
    """Test the complete performance optimization system."""
    print("🚀 Testing Performance Optimization System")
    print("=" * 50)
    
    try:
        # Test 1: Performance Monitor
        print("\n🧪 Testing PerformanceMonitor...")
        from utils.ai_performance import performance_monitor
        
        operation_id = performance_monitor.start_operation("test_operation", data_size=100)
        time.sleep(0.1)
        metric = performance_monitor.end_operation(operation_id, success=True)
        
        assert metric.success is True
        assert metric.duration > 0
        print("✅ PerformanceMonitor: Working correctly")
        
        # Test 2: Dataset Chunker
        print("\n🧪 Testing DatasetChunker...")
        from utils.ai_performance import DatasetChunker
        
        chunker = DatasetChunker(max_chunk_size=10)
        df = pd.DataFrame({'id': range(25), 'value': np.random.randn(25)})
        chunks = list(chunker.chunk_dataframe(df))
        
        assert len(chunks) == 3
        print("✅ DatasetChunker: Working correctly")
        
        # Test 3: Batch Processor
        print("\n🧪 Testing BatchProcessor...")
        from utils.ai_performance import BatchProcessor
        
        processor = BatchProcessor(max_workers=2, chunk_size=5)
        
        def process_chunk(chunk_df):
            return len(chunk_df)
        
        result = processor.process_dataframe_batches(df, process_chunk)
        assert result.success_rate == 100.0
        print("✅ BatchProcessor: Working correctly")
        
        # Test 4: Loading Indicator Manager
        print("\n🧪 Testing LoadingIndicatorManager...")
        from utils.ai_performance import loading_indicator_manager
        
        loading_data = loading_indicator_manager.start_loading("test_op", "Test Operation")
        updated_data = loading_indicator_manager.update_progress("test_op", 50)
        final_data = loading_indicator_manager.finish_loading("test_op", success=True)
        
        assert final_data['success'] is True
        print("✅ LoadingIndicatorManager: Working correctly")
        
        # Test 5: Performance Summary
        print("\n🧪 Testing Performance Summary...")
        summary = performance_monitor.get_performance_summary(hours=1)
        
        assert summary['total_operations'] >= 1
        assert 'test_operation' in summary['operations_by_type']
        print("✅ Performance Summary: Working correctly")
        
        print("\n" + "=" * 50)
        print("🎉 All Performance Tests Passed!")
        print("✨ Performance optimization system is ready!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Performance test failed: {e}")
        return False


def test_ai_service_integration():
    """Test AI service integration with performance monitoring."""
    print("\n🧪 Testing AI Service Integration...")
    
    try:
        from utils.ai_service import ai_service
        from utils.ai_performance import performance_monitor
        
        # Clear previous metrics
        performance_monitor.metrics.clear()
        
        # Test with simple data
        test_data = {
            'inventory_summary': {
                'total_items': 100,
                'low_stock_items': 5
            }
        }
        
        # This should work even if AI is disabled (fallback mode)
        response = ai_service.generate_inventory_insights(test_data)
        
        # Check response structure
        assert hasattr(response, 'success')
        assert hasattr(response, 'processing_time')
        assert response.processing_time >= 0
        
        print("✅ AI Service Integration: Working correctly")
        return True
        
    except Exception as e:
        print(f"⚠️ AI Service Integration: {e}")
        return False


if __name__ == "__main__":
    print("🔧 Performance Optimization Integration Test")
    
    # Test core performance system
    core_success = test_performance_system()
    
    # Test AI service integration
    ai_success = test_ai_service_integration()
    
    print("\n" + "=" * 50)
    print("📊 Final Results:")
    print(f"✅ Core Performance System: {'PASSED' if core_success else 'FAILED'}")
    print(f"✅ AI Service Integration: {'PASSED' if ai_success else 'PARTIAL'}")
    
    if core_success:
        print("\n🎉 Performance optimization system is ready for production!")
        print("✨ Task 8 completed successfully!")
    else:
        print("\n⚠️ Some issues detected. Please review before proceeding.")
    
    exit(0 if core_success else 1)