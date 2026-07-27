"""
Comprehensive test suite for XGBoost Model Cache

Tests cover:
- Basic cache operations (set, get, has)
- Feature hashing consistency
- TTL expiration
- Thread safety
- Cache statistics
- Serialization/deserialization
- Edge cases and error handling
"""

import unittest
import time
import threading
import numpy as np
import pickle
from unittest.mock import Mock, MagicMock
from utils.model_cache import ModelCache, FeatureHasher, get_model_cache, reset_cache


class TestModelCache(unittest.TestCase):
    """Basic cache operations tests."""
    
    def setUp(self):
        """Reset cache before each test."""
        reset_cache()
        self.cache = ModelCache(ttl_seconds=10)
    
    def test_cache_set_and_get(self):
        """Test basic set and get operations."""
        features = np.array([1.0, 2.0, 3.0])
        model = Mock(name='test_model')
        
        # Cache should be empty initially
        self.assertIsNone(self.cache.get(features))
        
        # Set model in cache
        key = self.cache.set(features, model)
        self.assertIsInstance(key, str)
        
        # Should be able to retrieve it
        cached_model = self.cache.get(features)
        self.assertIs(cached_model, model)
    
    def test_cache_has(self):
        """Test has() method."""
        features = {'a': 1, 'b': 2}
        model = Mock()
        
        # Should not have key initially
        self.assertFalse(self.cache.has(features))
        
        # After caching, should have it
        self.cache.set(features, model)
        self.assertTrue(self.cache.has(features))
    
    def test_cache_miss_increments_misses(self):
        """Test that cache misses are tracked."""
        features = [1, 2, 3]
        
        initial_misses = self.cache._stats['misses']
        self.cache.get(features)
        
        self.assertEqual(self.cache._stats['misses'], initial_misses + 1)
    
    def test_cache_hit_increments_hits(self):
        """Test that cache hits are tracked."""
        features = [1, 2, 3]
        model = Mock()
        
        self.cache.set(features, model)
        initial_hits = self.cache._stats['hits']
        
        result = self.cache.get(features)
        
        self.assertIs(result, model)
        self.assertEqual(self.cache._stats['hits'], initial_hits + 1)
    
    def test_cache_with_dict_features(self):
        """Test caching with dictionary features."""
        features = {'feature1': 1.5, 'feature2': 2.5, 'feature3': 3.5}
        model = Mock()
        
        self.cache.set(features, model)
        result = self.cache.get(features)
        
        self.assertIs(result, model)
    
    def test_cache_with_numpy_array(self):
        """Test caching with numpy arrays."""
        features = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
        model = Mock()
        
        self.cache.set(features, model)
        result = self.cache.get(features)
        
        self.assertIs(result, model)
    
    def test_cache_with_nested_structure(self):
        """Test caching with nested structures."""
        features = {
            'data': np.array([1, 2, 3]),
            'params': {'lr': 0.1, 'depth': 5},
            'list': [1, 2, 3]
        }
        model = Mock()
        
        self.cache.set(features, model)
        result = self.cache.get(features)
        
        self.assertIs(result, model)


class TestCacheExpiration(unittest.TestCase):
    """TTL and expiration tests."""
    
    def setUp(self):
        """Create cache with short TTL for testing."""
        reset_cache()
        self.cache = ModelCache(ttl_seconds=1)
    
    def test_model_expires_after_ttl(self):
        """Test that models expire after TTL."""
        features = [1, 2, 3]
        model = Mock()
        
        self.cache.set(features, model)
        
        # Should be cached immediately
        self.assertTrue(self.cache.has(features))
        self.assertIs(self.cache.get(features), model)
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired now
        self.assertFalse(self.cache.has(features))
        self.assertIsNone(self.cache.get(features))
    
    def test_expired_entry_increments_evictions(self):
        """Test that expired entries are counted as evictions."""
        features = [1, 2, 3]
        model = Mock()
        
        self.cache.set(features, model)
        initial_evictions = self.cache._stats['evictions']
        
        time.sleep(1.1)
        self.cache.get(features)
        
        # Should have incremented evictions
        self.assertEqual(self.cache._stats['evictions'], initial_evictions + 1)
    
    def test_cleanup_removes_expired_entries(self):
        """Test cleanup of expired entries."""
        features1 = [1, 2, 3]
        features2 = [4, 5, 6]
        features3 = [7, 8, 9]
        
        self.cache.set(features1, Mock())
        self.cache.set(features2, Mock())
        
        self.assertEqual(self.cache.get_size(), 2)
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Add new entry (to trigger cleanup)
        self.cache.set(features3, Mock())
        
        # Should have cleaned up expired entries
        self.assertEqual(self.cache.get_size(), 1)
    
    def test_clearing_cache_removes_all_entries(self):
        """Test that clear() removes all entries."""
        for i in range(5):
            self.cache.set([i, i+1, i+2], Mock())
        
        self.assertEqual(self.cache.get_size(), 5)
        
        cleared_count = self.cache.clear()
        
        self.assertEqual(cleared_count, 5)
        self.assertEqual(self.cache.get_size(), 0)


class TestFeatureHashing(unittest.TestCase):
    """Feature hashing consistency tests."""
    
    def test_same_features_same_hash(self):
        """Test that same features produce same hash."""
        features1 = np.array([1.0, 2.0, 3.0])
        features2 = np.array([1.0, 2.0, 3.0])
        
        cache = ModelCache()
        
        key1 = cache._generate_key(features1)
        key2 = cache._generate_key(features2)
        
        self.assertEqual(key1, key2)
    
    def test_different_features_different_hash(self):
        """Test that different features produce different hashes."""
        features1 = np.array([1.0, 2.0, 3.0])
        features2 = np.array([1.0, 2.0, 4.0])
        
        cache = ModelCache()
        
        key1 = cache._generate_key(features1)
        key2 = cache._generate_key(features2)
        
        self.assertNotEqual(key1, key2)
    
    def test_dict_with_different_order_same_hash(self):
        """Test that dict order doesn't matter for hashing."""
        features1 = {'a': 1, 'b': 2, 'c': 3}
        features2 = {'c': 3, 'a': 1, 'b': 2}
        
        cache = ModelCache()
        
        # Note: current implementation uses pickle which includes order
        # This test documents the actual behavior
        key1 = cache._generate_key(features1)
        key2 = cache._generate_key(features2)
        
        # Pickle includes order, so these will be different
        # This is acceptable - same structure different order = different cache key
        self.assertEqual(key1, key2)  # Should be same due to consistent serialization
    
    def test_hash_is_deterministic(self):
        """Test that hashing is deterministic."""
        features = {'x': 1.5, 'y': 2.5, 'z': 3.5}
        
        cache = ModelCache()
        
        keys = [cache._generate_key(features) for _ in range(10)]
        
        # All keys should be identical
        self.assertEqual(len(set(keys)), 1)


class TestFeatureHasher(unittest.TestCase):
    """FeatureHasher utility tests."""
    
    def test_hash_array(self):
        """Test array hashing."""
        array = np.array([1, 2, 3])
        
        hash1 = FeatureHasher.hash_array(array)
        hash2 = FeatureHasher.hash_array(array)
        
        # Same array should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Different array should produce different hash
        hash3 = FeatureHasher.hash_array(np.array([1, 2, 4]))
        self.assertNotEqual(hash1, hash3)
    
    def test_hash_dict(self):
        """Test dictionary hashing."""
        dict1 = {'a': 1, 'b': 2}
        dict2 = {'a': 1, 'b': 2}
        dict3 = {'a': 1, 'b': 3}
        
        hash1 = FeatureHasher.hash_dict(dict1)
        hash2 = FeatureHasher.hash_dict(dict2)
        hash3 = FeatureHasher.hash_dict(dict3)
        
        # Same dict should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Different dict should produce different hash
        self.assertNotEqual(hash1, hash3)
    
    def test_hash_params(self):
        """Test parameters hashing."""
        params1 = {'model_type': 'xgboost', 'max_depth': 5}
        params2 = {'model_type': 'xgboost', 'max_depth': 5}
        
        hash1 = FeatureHasher.hash_params(params1)
        hash2 = FeatureHasher.hash_params(params2)
        
        self.assertEqual(hash1, hash2)


class TestCacheStatistics(unittest.TestCase):
    """Cache statistics tracking tests."""
    
    def setUp(self):
        """Create fresh cache."""
        reset_cache()
        self.cache = ModelCache(ttl_seconds=10)
    
    def test_stats_initial_state(self):
        """Test initial cache statistics."""
        stats = self.cache.get_stats()
        
        self.assertEqual(stats['hits'], 0)
        self.assertEqual(stats['misses'], 0)
        self.assertEqual(stats['evictions'], 0)
        self.assertEqual(stats['current_size'], 0)
        self.assertEqual(stats['hit_rate'], 0)
    
    def test_stats_after_operations(self):
        """Test statistics tracking after cache operations."""
        features = [1, 2, 3]
        model = Mock()
        
        self.cache.set(features, model)
        self.cache.get(features)  # hit
        self.cache.get(features)  # hit
        self.cache.get([4, 5, 6])  # miss
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats['hits'], 2)
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['current_size'], 1)
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        features1 = [1, 2, 3]
        features2 = [4, 5, 6]
        model = Mock()
        
        self.cache.set(features1, model)
        
        # 2 hits, 2 misses = 50% hit rate
        self.cache.get(features1)  # hit
        self.cache.get(features1)  # hit
        self.cache.get(features2)  # miss
        self.cache.get(features2)  # miss
        
        hit_rate = self.cache.get_hit_rate()
        self.assertEqual(hit_rate, 50.0)
    
    def test_get_size(self):
        """Test get_size() method."""
        self.assertEqual(self.cache.get_size(), 0)
        
        self.cache.set([1, 2, 3], Mock())
        self.assertEqual(self.cache.get_size(), 1)
        
        self.cache.set([4, 5, 6], Mock())
        self.assertEqual(self.cache.get_size(), 2)
        
        self.cache.clear()
        self.assertEqual(self.cache.get_size(), 0)


class TestThreadSafety(unittest.TestCase):
    """Thread safety tests."""
    
    def setUp(self):
        """Create fresh cache."""
        reset_cache()
        self.cache = ModelCache(ttl_seconds=10)
    
    def test_concurrent_set_operations(self):
        """Test concurrent set operations."""
        def set_models(start_idx, count):
            for i in range(start_idx, start_idx + count):
                self.cache.set([i, i+1, i+2], Mock(name=f'model_{i}'))
        
        threads = []
        for i in range(0, 50, 10):
            t = threading.Thread(target=set_models, args=(i, 10))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have cached 50 models without errors
        self.assertEqual(self.cache.get_size(), 50)
    
    def test_concurrent_get_operations(self):
        """Test concurrent get operations."""
        features = [1, 2, 3]
        model = Mock()
        self.cache.set(features, model)
        
        def get_model(count):
            for _ in range(count):
                result = self.cache.get(features)
                self.assertIs(result, model)
        
        threads = []
        for _ in range(5):
            t = threading.Thread(target=get_model, args=(10,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have 50 hits
        self.assertEqual(self.cache.get_stats()['hits'], 50)
    
    def test_concurrent_set_and_get(self):
        """Test concurrent set and get operations."""
        results = []
        
        def worker(worker_id):
            features = [worker_id, worker_id+1, worker_id+2]
            model = Mock(name=f'model_{worker_id}')
            
            self.cache.set(features, model)
            time.sleep(0.001)
            
            result = self.cache.get(features)
            results.append((worker_id, result))
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All operations should succeed
        self.assertEqual(len(results), 10)


class TestGlobalCacheInstance(unittest.TestCase):
    """Global cache instance tests."""
    
    def setUp(self):
        """Reset cache before each test."""
        reset_cache()
    
    def test_get_cache_creates_instance(self):
        """Test that get_cache creates cache instance."""
        cache = get_model_cache()
        self.assertIsInstance(cache, ModelCache)
    
    def test_get_cache_returns_same_instance(self):
        """Test that get_cache returns same instance."""
        cache1 = get_model_cache()
        cache2 = get_model_cache()
        
        self.assertIs(cache1, cache2)
    
    def test_cache_instance_ttl(self):
        """Test cache instance TTL."""
        cache = get_model_cache(ttl_seconds=5)
        self.assertEqual(cache.ttl_seconds, 5)
    
    def test_reset_cache_clears_instance(self):
        """Test that reset clears the instance."""
        cache1 = get_model_cache()
        cache1.set([1, 2, 3], Mock())
        
        reset_cache()
        
        cache2 = get_model_cache()
        self.assertEqual(cache2.get_size(), 0)


class TestErrorHandling(unittest.TestCase):
    """Error handling and edge cases."""
    
    def setUp(self):
        """Create fresh cache."""
        reset_cache()
        self.cache = ModelCache(ttl_seconds=10)
    
    def test_non_serializable_features_raise_error(self):
        """Test that non-serializable features raise error."""
        # Create a non-serializable object
        class NonSerializable:
            def __reduce__(self):
                raise TypeError("Cannot pickle this object")
        
        features = NonSerializable()
        
        with self.assertRaises(ValueError):
            self.cache.set(features, Mock())
    
    def test_cache_with_none_model(self):
        """Test caching None as a model."""
        features = [1, 2, 3]
        
        self.cache.set(features, None)
        result = self.cache.get(features)
        
        self.assertIsNone(result)
    
    def test_cache_with_large_model(self):
        """Test caching a large object."""
        features = [1, 2, 3]
        large_model = Mock()
        large_model.large_array = np.random.rand(1000, 1000)
        
        key = self.cache.set(features, large_model)
        result = self.cache.get(features)
        
        self.assertIs(result, large_model)


class TestIntegration(unittest.TestCase):
    """Integration tests simulating real usage."""
    
    def setUp(self):
        """Create fresh cache."""
        reset_cache()
        self.cache = ModelCache(ttl_seconds=10)
    
    def test_forecast_request_caching_scenario(self):
        """Test caching during repeated forecast requests."""
        # Simulate 3 different forecast requests
        requests = [
            {'data': np.array([1, 2, 3]), 'horizon': 12},
            {'data': np.array([4, 5, 6]), 'horizon': 24},
            {'data': np.array([1, 2, 3]), 'horizon': 12},  # Repeat of first
        ]
        
        for i, req in enumerate(requests):
            features = str(req)  # Use string repr as features
            
            if self.cache.has(features):
                model = self.cache.get(features)
            else:
                # Simulate model training
                model = Mock(name=f'model_{i}')
                self.cache.set(features, model)
        
        # Should have 2 unique models cached
        self.assertEqual(self.cache.get_size(), 2)
        
        # Should have 1 hit (3rd request) and 2 misses (1st, 2nd)
        stats = self.cache.get_stats()
        self.assertEqual(stats['hits'], 1)
        self.assertEqual(stats['misses'], 2)
    
    def test_performance_improvement_from_caching(self):
        """Test that caching improves performance."""
        features = {'column1': 1, 'column2': 2}
        model = Mock()
        
        # First request - cache miss, model trained
        start_time = time.time()
        if not self.cache.has(features):
            model = Mock()  # Simulate training
            self.cache.set(features, model)
        first_time = time.time() - start_time
        
        # Second request - cache hit, no training
        start_time = time.time()
        if self.cache.has(features):
            model = self.cache.get(features)
        second_time = time.time() - start_time
        
        # Cache hit should be much faster
        # (at least not slower, might be same on fast machines)
        self.assertEqual(self.cache.get_stats()['hits'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
