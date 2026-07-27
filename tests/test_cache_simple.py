#!/usr/bin/env python3
"""
Simple test to verify cache data retention functionality works.
"""

import time
import sys

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


def test_basic_cache_retention():
    """Test basic cache retention functionality."""
    print("Testing basic cache retention...")
    
    # Create cache with 1 second TTL
    cache = SimpleCache(ttl_seconds=1)
    
    # Test data
    test_prompt = "test prompt for cache retention"
    test_data = {"test": "data", "timestamp": time.time()}
    
    # Cache the data
    cache.set(test_prompt, test_data)
    
    # Verify it's cached immediately
    cached_result = cache.get(test_prompt)
    assert cached_result is not None, "Data should be cached immediately"
    assert cached_result == test_data, "Cached data should match original"
    print("✓ Data cached successfully")
    
    # Wait for expiration
    print("Waiting for TTL expiration...")
    time.sleep(1.2)
    
    # Verify it's expired
    expired_result = cache.get(test_prompt)
    assert expired_result is None, "Data should be expired after TTL"
    print("✓ Data expired correctly after TTL")
    
    print("Basic cache retention test PASSED!")
    return True


def test_cleanup_mechanism():
    """Test cache cleanup mechanism."""
    print("\nTesting cache cleanup mechanism...")
    
    cache = SimpleCache(ttl_seconds=1)
    
    # Add multiple entries
    for i in range(3):
        cache.set(f"test_prompt_{i}", {"index": i, "data": f"value_{i}"})
    
    # Verify all are cached
    assert cache.size() == 3, "All entries should be cached"
    print("✓ Multiple entries cached")
    
    # Wait for expiration
    time.sleep(1.2)
    
    # Trigger cleanup
    expired_count = cache.clear_expired()
    assert expired_count >= 0, "Cleanup should return expired count"
    assert cache.size() == 0, "Cache should be empty after cleanup"
    print("✓ Cleanup mechanism works correctly")
    
    print("Cleanup mechanism test PASSED!")
    return True


if __name__ == "__main__":
    try:
        test_basic_cache_retention()
        test_cleanup_mechanism()
        print("\n🎉 All cache retention tests PASSED!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)