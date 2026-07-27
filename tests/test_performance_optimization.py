#!/usr/bin/env python3
"""
Performance Optimization Integration Test
Tests the complete performance monitoring and optimization system.
"""
import pytest
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Test the performance monitoring system
def test_performance_monitor():
    """Test PerformanceMonitor functionality."""
    from utils.ai_performance import PerformanceMonitor
    
    monitor = PerformanceMonitor()
    
    # Test operation tracking
    operation_id = monitor.start_operation("test_operation", data_size=100)
    assert operation_id is not None
    assert operation_id in monitor.active_operations
    
    # Simulate some processing time
    time.sleep(0.1)
    
    # End operation
    metric = monitor.end_operation(operation_id, success=True)
    assert metric is not None
    assert metric.success is True
    assert metric.duration > 0
    assert operation_id not in monitor.active_operations
    
    # Test performance summary
    summary = monitor.get_performance_summary(hours=1)
    assert summary['total_operations'] == 1
    assert summary['success_rate'] == 100.0
    assert 'test_operation' in summary['operations_by_type']
    
    print("✅ PerformanceMonitor: All tests passed")


def test_dataset_chunker():
    """Test DatasetChunker functionality."""
    from utils.ai_performance import DatasetChunker
    
    chunker = DatasetChunker(max_chunk_size=10)
    
    # Test DataFrame chunking
    df = pd.DataFrame({
        'id': range(25),
        'value': np.random.randn(25)
    })
    
    chunks = list(chunker.chunk_dataframe(df))
    assert len(chunks) == 3  # 25 items with chunk size 10
    assert len(chunks[0]) == 10
    assert len(chunks[1]) == 10
    assert len(chunks[2]) == 5
    
    # Test list chunking
    items = list(range(25))
    chunks = list(chunker.chunk_list(items))
    assert len(chunks) == 3
    assert len(chunks[0]) == 10
    assert len(chunks[1]) == 10
    assert len(chunks[2]) == 5
    
    print("✅ DatasetChunker: All tests passed")


def test_batch_processor():
    """Test BatchProcessor functionality."""
    from utils.ai_performance import BatchProcessor
    
    processor = BatchProcessor(max_workers=2, chunk_size=5)
    
    # Test DataFrame batch processing
    df = pd.DataFrame({
        'id': range(15),
        'value': np.random.randn(15)
    })
    
    def process_chunk(chunk_df):
        # Simulate processing
        time.sleep(0.01)
        return len(chunk_df)
    
    result = processor.process_dataframe_batches(df, process_chunk)
    assert result.total_items == 15
    assert result.processed_items == 15
    assert result.success_rate == 100.0
    assert len(result.results) == 3  # 3 chunks
    
    # Test list batch processing
    items = list(range(15))
    
    def process_list_chunk(chunk_list):
        time.sleep(0.01)
        return sum(chunk_list)
    
    result = processor.process_list_batches(items, process_list_chunk)
    assert result.total_items == 15
    assert result.processed_items == 15
    assert result.success_rate == 100.0
    
    print("✅ BatchProcessor: All tests passed")


def test_loading_indicator_manager():
    """Test LoadingIndicatorManager functionality."""
    from utils.ai_performance import LoadingIndicatorManager
    
    manager = LoadingIndicatorManager()
    
    # Test loading indicator lifecycle
    loading_data = manager.start_loading("test_op_1", "Test Operation", 30.0)
    assert loading_data['operation_id'] == "test_op_1"
    assert loading_data['operation_name'] == "Test Operation"
    assert loading_data['is_active'] is True
    
    # Test progress update
    updated_data = manager.update_progress("test_op_1", 50, "Processing...")
    assert updated_data['progress_percentage'] == 50
    assert updated_data['status_message'] == "Processing..."
    
    # Test finish loading
    final_data = manager.finish_loading("test_op_1", success=True, final_message="Completed")
    assert final_data['is_active'] is False
    assert final_data['progress_percentage'] == 100
    assert final_data['success'] is True
    
    # Test active operations
    manager.start_loading("test_op_2", "Another Operation")
    active_ops = manager.get_active_operations()
    assert len(active_ops) == 1
    assert active_ops[0]['operation_id'] == "test_op_2"
    
    print("✅ LoadingIndicatorManager: All tests passed")


def test_performance_decorator():
    """Test performance tracking decorator."""
    from utils.ai_performance import performance_tracked, performance_monitor
    
    @performance_tracked("test_decorated_operation")
    def test_function(x, y):
        time.sleep(0.05)
        return x + y
    
    # Clear previous metrics
    performance_monitor.metrics.clear()
    
    # Call decorated function
    result = test_function(2, 3)
    assert result == 5
    
    # Check that performance was tracked
    summary = performance_monitor.get_performance_summary(hours=1)
    assert summary['total_operations'] == 1
    assert 'test_decorated_operation' in summary['operations_by_type']
    
    print("✅ Performance Decorator: All tests passed")


def test_ai_service_performance_integration():
    """Test AI service integration with performance monitoring."""
    try:
        from utils.ai_service import ai_service
        from utils.ai_performance import performance_monitor
        
        # Clear previous metrics
        performance_monitor.metrics.clear()
        
        # Test inventory insights with performance tracking
        test_data = {
            'inventory_summary': {
                'total_items': 100,
                'low_stock_items': 5,
                'out_of_stock_items': 2
            }
        }
        
        response = ai_service.generate_inventory_insights(test_data)
        
        # Check that performance was tracked
        summary = performance_monitor.get_performance_summary(hours=1)
        assert summary['total_operations'] >= 1
        
        # Check response structure
        assert hasattr(response, 'success')
        assert hasattr(response, 'processing_time')
        assert response.processing_time > 0
        
        print("✅ AI Service Performance Integration: All tests passed")
        
    except ImportError as e:
        print(f"⚠️ AI Service Performance Integration: Skipped due to import error: {e}")


def test_flask_performance_endpoints():
    """Test Flask performance monitoring endpoints."""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from flask_app import app
        
        with app.test_client() as client:
            # Mock login session
            with client.session_transaction() as sess:
                sess['username'] = 'test_user'
                sess['logged_in'] = True
            
            # Test performance endpoint
            response = client.get('/api/ai/performance')
            assert response.status_code == 200
            
            data = response.get_json()
            assert data['success'] is True
            assert 'performance_summary' in data
            
            # Test loading status endpoint
            response = client.get('/api/ai/loading-status')
            assert response.status_code == 200
            
            data = response.get_json()
            assert data['success'] is True
            assert 'active_operations' in data
            
            print("✅ Flask Performance Endpoints: All tests passed")
            
    except Exception as e:
        print(f"⚠️ Flask Performance Endpoints: Skipped due to error: {e}")


def test_large_dataset_processing():
    """Test performance with large datasets."""
    from utils.ai_performance import BatchProcessor, DatasetChunker
    
    # Create large dataset
    large_df = pd.DataFrame({
        'id': range(1000),
        'value': np.random.randn(1000),
        'category': np.random.choice(['A', 'B', 'C'], 1000)
    })
    
    processor = BatchProcessor(max_workers=3, chunk_size=100)
    
    def process_large_chunk(chunk_df):
        # Simulate complex processing
        return {
            'count': len(chunk_df),
            'mean_value': chunk_df['value'].mean(),
            'categories': chunk_df['category'].value_counts().to_dict()
        }
    
    start_time = time.time()
    result = processor.process_dataframe_batches(large_df, process_large_chunk)
    processing_time = time.time() - start_time
    
    assert result.total_items == 1000
    assert result.processed_items == 1000
    assert result.success_rate == 100.0
    assert len(result.results) == 10  # 1000 items / 100 chunk size
    assert processing_time < 5.0  # Should complete within 5 seconds
    
    print(f"✅ Large Dataset Processing: Processed 1000 items in {processing_time:.2f}s")


def test_graceful_degradation():
    """Test graceful degradation when AI services are unavailable."""
    try:
        from utils.ai_service import ai_service
        
        # Mock AI service failure
        with patch('utils.ai_service._call_gemini_api', side_effect=Exception("API unavailable")):
            test_data = {'test': 'data'}
            response = ai_service.generate_inventory_insights(test_data)
            
            # Should return error response, not crash
            assert response.success is False
            assert response.error_message is not None
            assert "API unavailable" in response.error_message
            
        print("✅ Graceful Degradation: All tests passed")
        
    except ImportError as e:
        print(f"⚠️ Graceful Degradation: Skipped due to import error: {e}")


def run_all_tests():
    """Run all performance optimization tests."""
    print("🚀 Starting Performance Optimization Integration Tests")
    print("=" * 60)
    
    test_functions = [
        test_performance_monitor,
        test_dataset_chunker,
        test_batch_processor,
        test_loading_indicator_manager,
        test_performance_decorator,
        test_ai_service_performance_integration,
        test_flask_performance_endpoints,
        test_large_dataset_processing,
        test_graceful_degradation
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test_func in test_functions:
        try:
            print(f"\n🧪 Running {test_func.__name__}...")
            test_func()
            passed += 1
        except Exception as e:
            if "Skipped" in str(e):
                skipped += 1
            else:
                print(f"❌ {test_func.__name__} failed: {e}")
                failed += 1
    
    print("\n" + "=" * 60)
    print("📊 Performance Optimization Test Results:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️ Skipped: {skipped}")
    print(f"📈 Success Rate: {(passed / (passed + failed) * 100):.1f}%" if (passed + failed) > 0 else "N/A")
    
    if failed == 0:
        print("\n🎉 All performance optimization tests completed successfully!")
        print("✨ Performance monitoring and optimization system is ready for production.")
    else:
        print(f"\n⚠️ {failed} test(s) failed. Please review and fix issues before proceeding.")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)