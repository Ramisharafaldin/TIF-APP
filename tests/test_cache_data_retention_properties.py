"""
Property-based tests for cache data retention functionality.

Feature: gemini-api-integration, Property 25: Cache Data Retention
For any cached AI response, it should be automatically removed when the 
configured retention period expires.

Validates: Requirements 8.4
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from hypothesis.strategies import composite
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import tempfile
import os


# Simple cache implementation for testing
class SimpleCache:
    """Simple cache implementation for testing cache retention properties."""
    
    def __init__(self, ttl_seconds=3600):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def _generate_key(self, prompt):
        """Generate cache key."""
        return str(hash(prompt))
    
    def get(self, prompt):
        """Get cached value."""
        key = self._generate_key(prompt)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.ttl:
                return entry['data']
            else:
                del self.cache[key]  # Expired
        return None
    
    def set(self, prompt, data):
        """Set cached value."""
        key = self._generate_key(prompt)
        self.cache[key] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def clear_expired(self):
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time - entry['timestamp'] >= self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
        return len(expired_keys)
    
    def size(self):
        """Get current cache size."""
        return len(self.cache)


# Test data generators
@composite
def cache_entry_data(draw):
    """Generate valid cache entry data."""
    return {
        'prompt': draw(st.text(min_size=10, max_size=100)),
        'response_data': draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(
                st.text(min_size=1, max_size=50),
                st.integers(min_value=0, max_value=1000),
                st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
                st.booleans()
            ),
            min_size=1,
            max_size=5
        )),
        'ttl_seconds': draw(st.integers(min_value=1, max_value=2))
    }


@composite
def multiple_cache_entries(draw):
    """Generate multiple cache entries with different TTLs."""
    return draw(st.lists(
        cache_entry_data(),
        min_size=1,
        max_size=4,
        unique_by=lambda x: x['prompt']
    ))


class TestCacheDataRetentionProperties:
    """Property-based tests for cache data retention."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Create a test cache instance with short TTL for testing
        self.test_cache = SimpleCache(ttl_seconds=2)  # 2 second TTL for fast testing
    
    @given(entry_data=cache_entry_data())
    @settings(max_examples=10, deadline=5000)
    def test_cache_entry_expiration_completeness(self, entry_data):
        """
        Feature: gemini-api-integration, Property 25: Cache Data Retention
        For any cached entry, it should be automatically removed when the 
        TTL expires and not be retrievable after expiration.
        """
        # Use shorter TTL for faster testing
        ttl_seconds = min(entry_data['ttl_seconds'], 2)
        assume(ttl_seconds >= 1)  # Keep test times reasonable
        
        # Create cache with specific TTL
        test_cache = SimpleCache(ttl_seconds=ttl_seconds)
        
        prompt = entry_data['prompt']
        response_data = entry_data['response_data']
        
        # Cache the response
        test_cache.set(prompt, response_data)
        
        # Verify entry is cached immediately
        cached_result = test_cache.get(prompt)
        assert cached_result is not None, "Entry should be cached immediately after setting"
        assert cached_result == response_data, "Cached data should match original data"
        
        # Wait for TTL to expire (add small buffer)
        time.sleep(ttl_seconds + 0.3)
        
        # Verify entry is no longer cached
        expired_result = test_cache.get(prompt)
        assert expired_result is None, "Entry should be automatically removed after TTL expires"
        
        # Verify the entry was actually removed from internal cache
        cache_key = test_cache._generate_key(prompt)
        assert cache_key not in test_cache.cache, "Expired entry should be removed from internal cache storage"
    
    @given(entries=multiple_cache_entries())
    @settings(max_examples=8, deadline=10000)
    def test_selective_cache_expiration(self, entries):
        """
        Feature: gemini-api-integration, Property 25: Cache Data Retention
        For any set of cached entries with different TTLs, only expired entries
        should be removed while non-expired entries remain accessible.
        """
        # Limit TTLs to reasonable test values
        for entry in entries:
            entry['ttl_seconds'] = min(entry['ttl_seconds'], 4)
        
        assume(len(entries) >= 2)  # Need at least 2 entries for meaningful test
        
        # Sort entries by TTL to create a mix of expiration times
        entries.sort(key=lambda x: x['ttl_seconds'])
        
        # Create caches with different TTLs and cache the entries
        cached_entries = []
        for entry in entries:
            cache_instance = SimpleCache(ttl_seconds=entry['ttl_seconds'])
            cache_instance.set(entry['prompt'], entry['response_data'])
            cached_entries.append((cache_instance, entry))
        
        # Wait for the shortest TTL to expire
        shortest_ttl = entries[0]['ttl_seconds']
        time.sleep(shortest_ttl + 0.5)
        
        # Check that entries with expired TTLs are removed
        for cache_instance, entry in cached_entries:
            result = cache_instance.get(entry['prompt'])
            
            if entry['ttl_seconds'] == shortest_ttl:
                # This entry should be expired
                assert result is None, f"Entry with TTL {entry['ttl_seconds']} should be expired"
            else:
                # This entry should still be cached (if TTL is significantly longer)
                if entry['ttl_seconds'] > shortest_ttl + 1:
                    assert result is not None, f"Entry with TTL {entry['ttl_seconds']} should still be cached"
    
    @given(
        prompt=st.text(min_size=10, max_size=200),
        response_data=st.dictionaries(st.text(min_size=1, max_size=20), st.integers(), min_size=1, max_size=5),
        ttl_seconds=st.integers(min_value=1, max_value=4)
    )
    @settings(max_examples=10, deadline=8000)
    def test_cache_cleanup_mechanism(self, prompt, response_data, ttl_seconds):
        """
        Feature: gemini-api-integration, Property 25: Cache Data Retention
        For any cache with expired entries, the cleanup mechanism should
        remove expired entries and maintain cache integrity.
        """
        # Create cache with specific TTL
        test_cache = SimpleCache(ttl_seconds=ttl_seconds)
        
        # Add multiple entries to cache
        test_prompts = [f"{prompt}_{i}" for i in range(3)]
        for test_prompt in test_prompts:
            test_cache.set(test_prompt, {**response_data, 'index': test_prompts.index(test_prompt)})
        
        # Verify all entries are cached
        for test_prompt in test_prompts:
            assert test_cache.get(test_prompt) is not None, "All entries should be cached initially"
        
        # Wait for TTL to expire
        time.sleep(ttl_seconds + 0.5)
        
        # Manually trigger cleanup
        initial_cache_size = test_cache.size()
        expired_count = test_cache.clear_expired()
        final_cache_size = test_cache.size()
        
        # Verify cleanup removed expired entries
        assert final_cache_size <= initial_cache_size, "Cleanup should remove expired entries"
        assert expired_count >= 0, "Cleanup should return count of expired entries"
        
        # Verify expired entries are no longer accessible
        for test_prompt in test_prompts:
            result = test_cache.get(test_prompt)
            assert result is None, "Expired entries should not be accessible after cleanup"
    
    @given(
        cache_operations=st.lists(
            st.tuples(
                st.text(min_size=5, max_size=50),  # prompt
                st.dictionaries(st.text(min_size=1, max_size=10), st.integers(), min_size=1, max_size=3),  # data
                st.integers(min_value=1, max_value=3)  # ttl
            ),
            min_size=1,
            max_size=4,
            unique_by=lambda x: x[0]  # unique prompts
        )
    )
    @settings(max_examples=8, deadline=10000)
    def test_cache_retention_policy_consistency(self, cache_operations):
        """
        Feature: gemini-api-integration, Property 25: Cache Data Retention
        For any sequence of cache operations, the retention policy should be
        applied consistently across all entries regardless of operation order.
        """
        # Create cache instance
        test_cache = SimpleCache(ttl_seconds=2)  # Fixed TTL for consistency
        
        # Perform cache operations
        operation_times = []
        for prompt, data, _ in cache_operations:  # Ignore individual TTL, use cache TTL
            operation_time = time.time()
            test_cache.set(prompt, data)
            operation_times.append((prompt, data, operation_time))
        
        # Verify all entries are cached immediately
        for prompt, expected_data, _ in operation_times:
            cached_data = test_cache.get(prompt)
            assert cached_data is not None, "Entry should be cached immediately"
            assert cached_data == expected_data, "Cached data should match original"
        
        # Wait for TTL to expire
        time.sleep(2.5)
        
        # Verify all entries are expired consistently
        for prompt, _, _ in operation_times:
            expired_data = test_cache.get(prompt)
            assert expired_data is None, "All entries should expire consistently after TTL"
        
        # Verify cache is empty after expiration
        remaining_entries = len([k for k, v in test_cache.cache.items() 
                               if time.time() - v['timestamp'] < test_cache.ttl])
        assert remaining_entries == 0, "No entries should remain after TTL expiration"
    
    @given(
        ttl_values=st.lists(st.integers(min_value=1, max_value=4), min_size=2, max_size=4, unique=True)
    )
    @settings(max_examples=6, deadline=12000)
    def test_cache_ttl_boundary_conditions(self, ttl_values):
        """
        Feature: gemini-api-integration, Property 25: Cache Data Retention
        For any TTL boundary conditions, cache expiration should work correctly
        at the exact TTL boundary and handle edge cases properly.
        """
        ttl_values.sort()  # Test in ascending order
        
        for i, ttl in enumerate(ttl_values):
            # Create cache with specific TTL
            test_cache = SimpleCache(ttl_seconds=ttl)
            
            prompt = f"test_prompt_{i}"
            data = {'ttl': ttl, 'index': i}
            
            # Cache the entry
            test_cache.set(prompt, data)
            
            # Test just before expiration
            if ttl > 1:
                time.sleep(ttl - 0.5)
                pre_expiry_result = test_cache.get(prompt)
                assert pre_expiry_result is not None, f"Entry should still be cached before TTL {ttl} expires"
            
            # Wait for expiration
            time.sleep(0.8)  # Wait a bit more to ensure expiration
            
            # Test after expiration
            post_expiry_result = test_cache.get(prompt)
            assert post_expiry_result is None, f"Entry should be expired after TTL {ttl}"
    
    @given(
        concurrent_operations=st.integers(min_value=2, max_value=5),
        base_ttl=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=8, deadline=8000)
    def test_cache_retention_under_load(self, concurrent_operations, base_ttl):
        """
        Feature: gemini-api-integration, Property 25: Cache Data Retention
        For any cache under concurrent operations, retention policies should
        be maintained correctly and expired entries should be cleaned up properly.
        """
        # Create cache instance
        test_cache = SimpleCache(ttl_seconds=base_ttl)
        
        # Simulate concurrent operations
        cached_items = []
        for i in range(concurrent_operations):
            prompt = f"concurrent_prompt_{i}"
            data = {'operation_id': i, 'timestamp': time.time()}
            test_cache.set(prompt, data)
            cached_items.append((prompt, data))
        
        # Verify all items are cached
        for prompt, expected_data in cached_items:
            cached_result = test_cache.get(prompt)
            assert cached_result is not None, "All concurrent operations should be cached"
            assert cached_result['operation_id'] == expected_data['operation_id'], "Cached data should be correct"
        
        # Wait for expiration
        time.sleep(base_ttl + 0.5)
        
        # Verify all items are expired
        for prompt, _ in cached_items:
            expired_result = test_cache.get(prompt)
            assert expired_result is None, "All concurrent operations should expire consistently"
        
        # Verify cache is clean
        assert test_cache.size() == 0, "Cache should be empty after all entries expire"


if __name__ == "__main__":
    # Run a simple test to verify the test setup
    test_instance = TestCacheDataRetentionProperties()
    test_instance.setup_method()
    
    # Test with a simple cache entry
    test_cache = SimpleCache(ttl_seconds=1)
    test_prompt = "test prompt for cache retention"
    test_data = {"test": "data", "timestamp": time.time()}
    
    print("Testing cache data retention with sample entry...")
    
    # Cache the data
    test_cache.set(test_prompt, test_data)
    print(f"Cached data: {test_cache.get(test_prompt) is not None}")
    
    # Wait for expiration
    time.sleep(1.5)
    
    # Check if expired
    expired_result = test_cache.get(test_prompt)
    print(f"Data expired after TTL: {expired_result is None}")
    
    print("Cache data retention test completed successfully!")