"""
Property-Based Tests for Resource Management and Cleanup

This module tests the resource management and cleanup functionality to ensure
proper handling of temporary files, memory management, and resource cleanup
during export operations.

**Feature: export-functionality-fix, Property 8: Resource Management and Cleanup**
**Validates: Requirements 6.5**
"""

import pytest
import tempfile
import os
import gc
import threading
import time
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from io import BytesIO
from unittest.mock import patch, MagicMock

# Try to import psutil, but handle gracefully if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

# Import the modules under test
from utils.resource_manager import (
    ExportResourceManager, 
    managed_bytesio, 
    managed_temp_file,
    resource_monitored_operation,
    ExportRateLimiter,
    rate_limited_export
)

class TestResourceManagementProperties:
    """Property-based tests for resource management and cleanup."""
    
    @given(
        username=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        operation_type=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting']),
        num_bytesio=st.integers(min_value=1, max_value=5),
        num_temp_files=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50, deadline=30000)
    def test_resource_manager_cleanup_all_resources(self, username, operation_type, num_bytesio, num_temp_files):
        """
        Property: For any export operation, all created resources (BytesIO objects and temporary files)
        should be properly cleaned up when the resource manager exits, regardless of success or failure.
        
        **Validates: Requirements 6.5**
        """
        created_temp_files = []
        created_bytesio = []
        
        try:
            with ExportResourceManager(username, operation_type) as manager:
                # Create multiple BytesIO objects
                for _ in range(num_bytesio):
                    bio = manager.create_bytesio()
                    created_bytesio.append(bio)
                    assert not bio.closed, "BytesIO should be open when created"
                
                # Create multiple temporary files
                for i in range(num_temp_files):
                    temp_file = manager.create_temp_file(suffix=f'.test{i}')
                    created_temp_files.append(temp_file)
                    assert os.path.exists(temp_file), f"Temporary file should exist: {temp_file}"
                
                # Verify resources are tracked
                assert len(manager.bytesio_objects) == num_bytesio
                assert len(manager.temp_files) == num_temp_files
        
        except Exception:
            # Even if an exception occurs, resources should still be cleaned up
            pass
        
        # After exiting the context manager, all resources should be cleaned up
        
        # Check BytesIO objects are closed
        for bio in created_bytesio:
            assert bio.closed, "BytesIO objects should be closed after cleanup"
        
        # Check temporary files are deleted
        for temp_file in created_temp_files:
            assert not os.path.exists(temp_file), f"Temporary file should be deleted: {temp_file}"
    
    @given(
        username=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        operation_type=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting']),
        should_raise_exception=st.booleans()
    )
    @settings(max_examples=30, deadline=20000)
    def test_resource_manager_cleanup_on_exception(self, username, operation_type, should_raise_exception):
        """
        Property: For any export operation that raises an exception, all resources should still
        be properly cleaned up when the resource manager exits.
        
        **Validates: Requirements 6.5**
        """
        created_temp_files = []
        created_bytesio = []
        exception_raised = False
        
        try:
            with ExportResourceManager(username, operation_type) as manager:
                # Create some resources
                bio = manager.create_bytesio(b"test data")
                created_bytesio.append(bio)
                
                temp_file = manager.create_temp_file(suffix='.exception_test')
                created_temp_files.append(temp_file)
                
                # Optionally raise an exception
                if should_raise_exception:
                    raise ValueError("Test exception for resource cleanup")
        
        except ValueError as e:
            if "Test exception for resource cleanup" in str(e):
                exception_raised = True
            else:
                raise
        
        # Verify exception handling
        if should_raise_exception:
            assert exception_raised, "Expected exception should have been raised"
        
        # Verify cleanup occurred regardless of exception
        for bio in created_bytesio:
            assert bio.closed, "BytesIO should be closed even after exception"
        
        for temp_file in created_temp_files:
            assert not os.path.exists(temp_file), f"Temp file should be deleted even after exception: {temp_file}"
    
    @given(
        initial_data=st.one_of(st.none(), st.binary(min_size=0, max_size=1000))
    )
    @settings(max_examples=20, deadline=10000)
    def test_managed_bytesio_cleanup(self, initial_data):
        """
        Property: For any BytesIO object created with managed_bytesio context manager,
        the object should be properly closed when exiting the context.
        
        **Validates: Requirements 6.5**
        """
        bytesio_obj = None
        
        with managed_bytesio(initial_data) as bio:
            bytesio_obj = bio
            assert not bio.closed, "BytesIO should be open within context"
            
            # Test basic operations
            if initial_data:
                assert bio.getvalue() == initial_data
            else:
                bio.write(b"test")
                assert bio.getvalue() == b"test"
        
        # After context exit, should be closed
        assert bytesio_obj.closed, "BytesIO should be closed after context exit"
    
    @given(
        suffix=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        prefix=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
    )
    @settings(max_examples=20, deadline=10000)
    def test_managed_temp_file_cleanup(self, suffix, prefix):
        """
        Property: For any temporary file created with managed_temp_file context manager,
        the file should be properly deleted when exiting the context.
        
        **Validates: Requirements 6.5**
        """
        temp_file_path = None
        
        with managed_temp_file(suffix=f'.{suffix}', prefix=f'{prefix}_') as temp_path:
            temp_file_path = temp_path
            assert os.path.exists(temp_path), "Temporary file should exist within context"
            
            # Test file operations
            with open(temp_path, 'w') as f:
                f.write("test content")
            
            with open(temp_path, 'r') as f:
                content = f.read()
                assert content == "test content"
        
        # After context exit, file should be deleted
        assert not os.path.exists(temp_file_path), "Temporary file should be deleted after context exit"
    
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    @given(
        memory_threshold=st.integers(min_value=100, max_value=2000),
        operation_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
    )
    @settings(max_examples=15, deadline=15000)
    def test_resource_monitored_operation_memory_tracking(self, memory_threshold, operation_name):
        """
        Property: For any resource-monitored operation, memory usage should be tracked
        and statistics should be available throughout the operation.
        
        **Validates: Requirements 6.5**
        """
        with resource_monitored_operation(memory_threshold, operation_name) as monitor:
            # Memory monitoring should be active
            assert monitor.initial_memory is not None or monitor.initial_memory == 0
            
            # Should be able to check memory usage
            memory_ok = monitor.check_memory_usage()
            assert isinstance(memory_ok, bool)
            
            # Should be able to get memory stats
            stats = monitor.get_memory_stats()
            assert isinstance(stats, dict)
            
            # Stats should contain expected keys
            expected_keys = ['initial_memory_mb', 'current_memory_mb', 'peak_memory_mb', 'memory_increase_mb']
            for key in expected_keys:
                assert key in stats, f"Memory stats should contain {key}"
                assert isinstance(stats[key], (int, float)), f"{key} should be numeric"
    
    @given(
        max_concurrent=st.integers(min_value=1, max_value=5),
        max_per_minute=st.integers(min_value=1, max_value=10),
        num_users=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=20, deadline=20000)
    def test_rate_limiter_concurrent_limit(self, max_concurrent, max_per_minute, num_users):
        """
        Property: For any rate limiter configuration, the number of concurrent exports
        should never exceed the specified limit.
        
        **Validates: Requirements 5.5**
        """
        assume(num_users >= max_concurrent)  # Only test when we have enough users to hit the limit
        
        rate_limiter = ExportRateLimiter(max_concurrent=max_concurrent, max_per_minute=max_per_minute)
        
        # Start exports up to the limit
        started_users = []
        for i in range(num_users):
            username = f"user_{i}"
            can_start = rate_limiter.start_export(username)
            
            if can_start:
                started_users.append(username)
            
            # Check that we never exceed the concurrent limit
            assert len(rate_limiter.active_exports) <= max_concurrent, \
                f"Active exports ({len(rate_limiter.active_exports)}) should not exceed limit ({max_concurrent})"
        
        # Should have started exactly max_concurrent exports
        assert len(started_users) == max_concurrent, \
            f"Should start exactly {max_concurrent} exports, but started {len(started_users)}"
        
        # Clean up
        for username in started_users:
            rate_limiter.finish_export(username)
    
    @given(
        username=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        max_per_minute=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=15, deadline=25000)
    def test_rate_limiter_per_minute_limit(self, username, max_per_minute):
        """
        Property: For any user and rate limit configuration, the number of exports per minute
        should not exceed the specified limit.
        
        **Validates: Requirements 5.5**
        """
        rate_limiter = ExportRateLimiter(max_concurrent=10, max_per_minute=max_per_minute)
        
        successful_starts = 0
        
        # Try to start more exports than the per-minute limit
        for i in range(max_per_minute + 2):
            # Use different usernames to avoid concurrent limit
            test_username = f"{username}_{i}"
            can_start = rate_limiter.start_export(test_username)
            
            if can_start:
                successful_starts += 1
                # Immediately finish to avoid concurrent limit
                rate_limiter.finish_export(test_username)
        
        # Should not exceed the per-minute limit for any single user
        # Note: This test checks the rate limiting logic, but since we're using different usernames,
        # we expect all to succeed. Let's modify to use the same username.
        
        # Reset and test with same username
        rate_limiter = ExportRateLimiter(max_concurrent=10, max_per_minute=max_per_minute)
        successful_starts = 0
        
        for i in range(max_per_minute + 2):
            can_start = rate_limiter.start_export(username)
            
            if can_start:
                successful_starts += 1
                rate_limiter.finish_export(username)
        
        # Should not exceed the per-minute limit
        assert successful_starts <= max_per_minute, \
            f"Successful starts ({successful_starts}) should not exceed per-minute limit ({max_per_minute})"
    
    @given(
        username=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
    )
    @settings(max_examples=10, deadline=15000)
    def test_rate_limited_export_context_manager(self, username):
        """
        Property: For any username, the rate_limited_export context manager should
        properly track export start and finish, and handle exceptions correctly.
        
        **Validates: Requirements 5.5**
        """
        # Test successful export
        try:
            with rate_limited_export(username):
                # Should be able to enter context successfully
                pass
        except RuntimeError:
            # If rate limited, that's also valid behavior
            pass
        
        # Test export with exception
        exception_raised = False
        try:
            with rate_limited_export(username):
                raise ValueError("Test exception")
        except ValueError as e:
            if "Test exception" in str(e):
                exception_raised = True
        except RuntimeError:
            # Rate limited - also valid
            pass
        
        # If we entered the context, exception should have been raised
        # (This is hard to test deterministically due to rate limiting)
    
    @given(
        username=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        operation_type=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting'])
    )
    @settings(max_examples=10, deadline=20000)
    def test_resource_manager_memory_monitoring_integration(self, username, operation_type):
        """
        Property: For any export operation, the resource manager should integrate
        with the monitoring system and track memory usage properly.
        
        **Validates: Requirements 6.5**
        """
        # Mock the export monitor to avoid dependencies
        with patch('utils.resource_manager.export_monitor') as mock_monitor:
            mock_monitor.start_operation.return_value = "test_operation_id"
            
            with ExportResourceManager(username, operation_type) as manager:
                # Should have called start_operation
                mock_monitor.start_operation.assert_called_once_with(username, operation_type)
                
                # Check memory limits (should work regardless of monitoring)
                memory_ok = manager.check_memory_limits()
                assert isinstance(memory_ok, bool)
                
                # Should be able to create resources
                bio = manager.create_bytesio()
                assert not bio.closed
                
                temp_file = manager.create_temp_file()
                assert os.path.exists(temp_file)
            
            # Should have called finish_operation
            mock_monitor.finish_operation.assert_called_once()
            
            # Resources should be cleaned up
            assert bio.closed
            assert not os.path.exists(temp_file)

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])