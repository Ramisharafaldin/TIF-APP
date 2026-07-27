"""
Property-Based Tests for System Resilience and Load Handling

This module tests the system's ability to handle resource constraints,
high load scenarios, and recovery mechanisms during export operations.

**Feature: export-functionality-fix, Property 6: System Resilience and Load Handling**
**Validates: Requirements 5.2, 5.3, 5.4, 5.5**
"""

import pytest
import pandas as pd
import numpy as np
from hypothesis import given, strategies as st, settings, assume, example
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant
import threading
import time
from datetime import datetime, timedelta
from io import BytesIO
import gc
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Import the modules to test
from utils.resource_manager import (
    ExportResourceManager, 
    ResourceMonitor, 
    export_rate_limiter,
    rate_limited_export,
    ExportFallbackStrategies,
    timeout_handler
)
from utils.export_fallback import (
    ExportFallbackHandler,
    ExportRecoveryManager,
    create_fallback_export_response
)

# Handle optional psutil dependency
try:
    from utils.export_monitor import export_monitor
    EXPORT_MONITOR_AVAILABLE = True
except ImportError:
    EXPORT_MONITOR_AVAILABLE = False
    export_monitor = None

class TestSystemResilienceProperties:
    """Test system resilience under various load and constraint scenarios."""
    
    @given(
        memory_threshold=st.integers(min_value=100, max_value=2000),
        data_size=st.integers(min_value=10, max_value=10000),
        concurrent_users=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100, deadline=30000)
    def test_memory_constraint_handling_property(self, memory_threshold, data_size, concurrent_users):
        """
        Property: For any memory threshold and data size, the system should handle
        memory constraints gracefully without crashing.
        
        **Validates: Requirements 5.3**
        """
        # Generate test data
        test_data = pd.DataFrame({
            'product_code': [f'PROD_{i:04d}' for i in range(data_size)],
            'product_name': [f'Product {i}' for i in range(data_size)],
            'quantity': np.random.randint(1, 1000, data_size),
            'price': np.random.uniform(10.0, 1000.0, data_size),
            'category': np.random.choice(['A', 'B', 'C', 'D'], data_size)
        })
        
        # Test memory monitoring
        monitor = ResourceMonitor(memory_threshold_mb=memory_threshold)
        monitor.start_monitoring()
        
        # Memory usage should be trackable
        memory_ok, memory_info = monitor.check_memory_usage()
        assert isinstance(memory_ok, bool)
        assert isinstance(memory_info, dict)
        assert 'current_memory_mb' in memory_info or 'status' in memory_info
        
        # Test fallback strategies for large data
        if data_size > 1000:
            reduced_data, reduction_info = ExportFallbackStrategies.reduce_data_size(
                test_data, max_rows=500, strategy='sample'
            )
            
            # Reduced data should be smaller or equal
            assert len(reduced_data) <= len(test_data)
            assert reduction_info['original_rows'] == len(test_data)
            
            if reduction_info['reduced']:
                assert reduction_info['final_rows'] <= 500
                assert reduction_info['reduction_percent'] >= 0
        
        # Test memory constraint recovery
        recovery_success, recovered_data, recovery_message = ExportRecoveryManager.handle_memory_constraint_recovery(
            test_data, f'test_user_{concurrent_users}', 'test_operation'
        )
        
        # Recovery should always succeed with some data
        assert recovery_success is True
        assert recovered_data is not None
        assert len(recovered_data) > 0
        assert len(recovered_data) <= len(test_data)
        assert isinstance(recovery_message, str)
        assert len(recovery_message) > 0
    
    @given(
        timeout_seconds=st.integers(min_value=1, max_value=10),
        processing_delay=st.floats(min_value=0.1, max_value=15.0)
    )
    @settings(max_examples=50, deadline=20000)
    def test_timeout_handling_property(self, timeout_seconds, processing_delay):
        """
        Property: For any timeout setting and processing delay, the system should
        handle timeouts gracefully and provide appropriate recovery information.
        
        **Validates: Requirements 5.3**
        """
        username = f'test_user_{int(time.time())}'
        
        # Test timeout handler context manager
        timeout_occurred = False
        
        try:
            with timeout_handler(timeout_seconds=timeout_seconds, operation_name="test_export"):
                # Simulate processing delay
                if processing_delay > timeout_seconds:
                    # This should timeout
                    time.sleep(processing_delay)
                else:
                    # This should complete normally
                    time.sleep(min(processing_delay, timeout_seconds - 0.1))
        except Exception as e:
            if processing_delay > timeout_seconds:
                # Timeout expected
                timeout_occurred = True
                assert "timed out" in str(e).lower()
            else:
                # Timeout not expected, re-raise
                raise
        
        # Verify timeout behavior
        if processing_delay > timeout_seconds:
            assert timeout_occurred, "Timeout should have occurred but didn't"
        
        # Test timeout recovery
        if timeout_occurred or processing_delay > 5:
            recovery_info = ExportRecoveryManager.handle_timeout_recovery(
                username, 'test_operation', processing_delay
            )
            
            assert recovery_info['timeout_occurred'] is True
            assert recovery_info['elapsed_time'] == processing_delay
            assert isinstance(recovery_info['user_message'], str)
            assert len(recovery_info['user_message']) > 0
            assert isinstance(recovery_info['recovery_suggestions'], list)
            assert len(recovery_info['recovery_suggestions']) > 0
    
    @given(
        num_concurrent_requests=st.integers(min_value=1, max_value=8),
        request_interval=st.floats(min_value=0.1, max_value=2.0)
    )
    @settings(max_examples=30, deadline=15000)
    def test_rate_limiting_property(self, num_concurrent_requests, request_interval):
        """
        Property: For any number of concurrent requests, the rate limiter should
        enforce limits and prevent system overload.
        
        **Validates: Requirements 5.5**
        """
        # Reset rate limiter state
        export_rate_limiter.active_exports.clear()
        export_rate_limiter.export_history.clear()
        
        successful_exports = []
        failed_exports = []
        
        def attempt_export(user_id):
            username = f'test_user_{user_id}'
            try:
                with rate_limited_export(username):
                    # Simulate export work
                    time.sleep(request_interval)
                    successful_exports.append(username)
            except RuntimeError as e:
                failed_exports.append((username, str(e)))
        
        # Start concurrent export attempts
        threads = []
        for i in range(num_concurrent_requests):
            thread = threading.Thread(target=attempt_export, args=(i,))
            threads.append(thread)
            thread.start()
            # Small delay between starts to simulate realistic timing
            time.sleep(0.05)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)
        
        total_attempts = len(successful_exports) + len(failed_exports)
        
        # At least some requests should be processed
        assert total_attempts > 0
        
        # Rate limiting should prevent too many concurrent operations
        if num_concurrent_requests > export_rate_limiter.max_concurrent:
            assert len(failed_exports) > 0, "Rate limiting should have rejected some requests"
        
        # All successful exports should have unique usernames (no double-processing)
        assert len(set(successful_exports)) == len(successful_exports)
        
        # Failed exports should have meaningful error messages
        for username, error_msg in failed_exports:
            assert len(error_msg) > 0
            assert any(keyword in error_msg for keyword in ['مشغول', 'انتظار', 'حد', 'تجاوز'])
    
    @given(
        data_rows=st.integers(min_value=100, max_value=5000),
        data_columns=st.integers(min_value=5, max_value=20),
        failure_scenario=st.sampled_from(['memory', 'timeout', 'permission', 'disk_space', 'unknown'])
    )
    @settings(max_examples=50, deadline=20000)
    def test_export_fallback_mechanisms_property(self, data_rows, data_columns, failure_scenario):
        """
        Property: For any data size and failure scenario, the fallback mechanisms
        should provide alternative export methods or meaningful error recovery.
        
        **Validates: Requirements 5.4**
        """
        # Generate test data
        test_data = pd.DataFrame({
            f'column_{i}': np.random.choice(['A', 'B', 'C'], data_rows) if i % 2 == 0 
            else np.random.uniform(0, 1000, data_rows)
            for i in range(data_columns)
        })
        
        username = f'test_user_{int(time.time())}'
        fallback_handler = ExportFallbackHandler(username, 'test_operation')
        
        # Test CSV fallback
        csv_success, csv_buffer, csv_message = fallback_handler.attempt_csv_fallback(
            test_data, 'test_export'
        )
        
        # CSV fallback should generally succeed for reasonable data sizes
        if data_rows <= 2000 and data_columns <= 15:
            assert csv_success is True
            assert csv_buffer is not None
            assert isinstance(csv_message, str)
            assert len(csv_message) > 0
            
            # Verify CSV content
            csv_buffer.seek(0)
            csv_content = csv_buffer.read().decode('utf-8-sig')
            assert len(csv_content) > 0
            # Should contain header row
            lines = csv_content.split('\n')
            assert len(lines) >= 2  # At least header + one data row
        
        # Test JSON fallback
        json_success, json_buffer, json_message = fallback_handler.attempt_json_fallback(
            test_data, 'test_export'
        )
        
        # JSON fallback should succeed for smaller datasets
        if data_rows <= 1000:
            assert json_success is True
            assert json_buffer is not None
            assert isinstance(json_message, str)
            
            # Verify JSON content structure
            json_buffer.seek(0)
            json_content = json_buffer.read().decode('utf-8')
            assert 'metadata' in json_content
            assert 'data' in json_content
            assert username in json_content
        
        # Test partial export for large datasets
        if data_rows > 1000:
            partial_success, partial_data, partial_message = fallback_handler.attempt_partial_export(
                test_data, max_rows=500
            )
            
            assert partial_success is True
            assert partial_data is not None
            assert len(partial_data) <= 501  # 500 + summary row
            assert isinstance(partial_message, str)
        
        # Test comprehensive fallback strategy
        fallback_success, fallback_buffer, content_type, fallback_message = ExportRecoveryManager.attempt_export_with_fallbacks(
            test_data, username, 'test_operation', 'xlsx'
        )
        
        # Some fallback method should always succeed
        assert fallback_success is True
        assert fallback_buffer is not None
        assert content_type in ['text/csv', 'application/json', 'application/xlsx']
        assert isinstance(fallback_message, str)
        assert len(fallback_message) > 0
        
        # Test error response generation
        test_error = Exception(f"Test {failure_scenario} error")
        user_message, technical_message = create_fallback_export_response(
            username, 'test_operation', test_error, {'data_size': data_rows}
        )
        
        assert isinstance(user_message, str)
        assert len(user_message) > 0
        assert isinstance(technical_message, str)
        assert username in technical_message
    
    @given(
        resource_usage_percent=st.integers(min_value=50, max_value=95),
        concurrent_operations=st.integers(min_value=1, max_value=6)
    )
    @settings(max_examples=30, deadline=15000)
    def test_resource_monitoring_property(self, resource_usage_percent, concurrent_operations):
        """
        Property: For any resource usage level and concurrent operations, the
        monitoring system should track resources and provide accurate information.
        
        **Validates: Requirements 5.2, 5.5**
        """
        # Test resource manager with multiple operations
        managers = []
        
        try:
            for i in range(concurrent_operations):
                username = f'test_user_{i}'
                manager = ExportResourceManager(username, f'test_operation_{i}', timeout_seconds=30)
                managers.append(manager)
            
            # Start all managers
            for manager in managers:
                manager.__enter__()
            
            # Test resource monitoring
            for manager in managers:
                # Memory limits check should work
                memory_ok = manager.check_memory_limits()
                assert isinstance(memory_ok, bool)
                
                # Timeout check should work
                timeout_ok = manager.check_timeout()
                assert isinstance(timeout_ok, bool)
                
                # Remaining time should be reasonable
                remaining_time = manager.get_remaining_time()
                assert remaining_time >= 0
                assert remaining_time <= 30  # Should not exceed timeout
                
                # Fallback mode detection should work
                fallback_mode = manager.should_use_fallback()
                assert isinstance(fallback_mode, bool)
            
            # Test data processing capability assessment
            test_data_size = 100  # MB
            for manager in managers:
                can_process, reason = manager.can_process_data_size(test_data_size)
                assert isinstance(can_process, bool)
                assert isinstance(reason, str)
                
                if not can_process:
                    # Reason should be meaningful
                    assert any(keyword in reason.lower() for keyword in 
                              ['memory', 'time', 'timeout', 'insufficient'])
        
        finally:
            # Clean up all managers
            for manager in managers:
                try:
                    manager.__exit__(None, None, None)
                except Exception:
                    pass  # Ignore cleanup errors in tests
        
        # Verify no resource leaks
        gc.collect()
    
    @example(operation_count=5, failure_rate=0.2)
    @given(
        operation_count=st.integers(min_value=1, max_value=10),
        failure_rate=st.floats(min_value=0.0, max_value=0.5)
    )
    @settings(max_examples=20, deadline=10000)
    def test_system_recovery_under_load_property(self, operation_count, failure_rate):
        """
        Property: For any number of operations with various failure rates, the
        system should maintain stability and provide recovery mechanisms.
        
        **Validates: Requirements 5.2, 5.4**
        """
        successful_operations = 0
        failed_operations = 0
        recovery_attempts = 0
        
        for i in range(operation_count):
            username = f'load_test_user_{i}'
            
            # Simulate random failures based on failure rate
            should_fail = np.random.random() < failure_rate
            
            try:
                if should_fail:
                    # Simulate various failure scenarios
                    failure_types = ['memory', 'timeout', 'permission', 'disk']
                    failure_type = np.random.choice(failure_types)
                    
                    if failure_type == 'memory':
                        raise MemoryError("Simulated memory error")
                    elif failure_type == 'timeout':
                        raise TimeoutError("Simulated timeout error")
                    elif failure_type == 'permission':
                        raise PermissionError("Simulated permission error")
                    else:
                        raise OSError("Simulated disk error")
                else:
                    # Simulate successful operation
                    with ExportResourceManager(username, 'load_test', timeout_seconds=10) as manager:
                        # Check that manager is working
                        assert manager.check_memory_limits() is not None
                        assert manager.check_timeout() is True
                        successful_operations += 1
            
            except (MemoryError, TimeoutError, PermissionError, OSError) as e:
                failed_operations += 1
                recovery_attempts += 1
                
                # Test recovery mechanisms
                if isinstance(e, MemoryError):
                    # Test memory recovery
                    test_data = pd.DataFrame({'col1': range(100), 'col2': range(100)})
                    recovery_success, recovered_data, message = ExportRecoveryManager.handle_memory_constraint_recovery(
                        test_data, username, 'load_test'
                    )
                    assert recovery_success is True
                    assert recovered_data is not None
                
                elif isinstance(e, TimeoutError):
                    # Test timeout recovery
                    recovery_info = ExportRecoveryManager.handle_timeout_recovery(
                        username, 'load_test', 15.0
                    )
                    assert recovery_info['timeout_occurred'] is True
                    assert len(recovery_info['recovery_suggestions']) > 0
                
                # Test fallback response generation
                user_message, technical_message = create_fallback_export_response(
                    username, 'load_test', e, {'operation_index': i}
                )
                assert isinstance(user_message, str)
                assert len(user_message) > 0
        
        # System should handle the load appropriately
        total_operations = successful_operations + failed_operations
        assert total_operations == operation_count
        
        # If there were failures, recovery should have been attempted
        if failed_operations > 0:
            assert recovery_attempts == failed_operations
        
        # Success rate should be reasonable given the failure rate
        actual_success_rate = successful_operations / total_operations if total_operations > 0 else 0
        expected_success_rate = 1.0 - failure_rate
        
        # Allow some tolerance for randomness
        assert abs(actual_success_rate - expected_success_rate) <= 0.3

if __name__ == "__main__":
    # Run the property tests
    pytest.main([__file__, "-v", "--tb=short"])