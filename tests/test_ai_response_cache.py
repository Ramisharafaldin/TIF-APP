"""
Comprehensive test suite for AI Response Cache

Tests cover:
- Basic cache operations (set, get, has)
- TTL expiration
- Cost tracking
- Prompt analysis
- Memory management
- Thread safety
- Redis integration (optional)
- Cache statistics
"""

import unittest
import time
import threading
from unittest.mock import Mock, MagicMock, patch
import json

from ai_response_cache import (
    AIResponseCache,
    PromptAnalyzer,
    get_ai_cache,
    reset_ai_cache
)


class TestAIResponseCache(unittest.TestCase):
    """Basic cache operations tests."""
    
    def setUp(self):
        """Reset cache before each test."""
        reset_ai_cache()
        self.cache = AIResponseCache(ttl_hours=24)
    
    def test_cache_set_and_get(self):
        """Test basic set and get operations."""
        prompt = "What is the capital of France?"
        response = "The capital of France is Paris."
        
        success, msg = self.cache.set(prompt, response)
        self.assertTrue(success)
        
        cached = self.cache.get(prompt)
        self.assertEqual(cached, response)
    
    def test_cache_has(self):
        """Test has() method."""
        prompt = "Explain quantum mechanics"
        response = "Quantum mechanics is..."
        
        self.assertFalse(self.cache.has(prompt))
        
        self.cache.set(prompt, response)
        self.assertTrue(self.cache.has(prompt))
    
    def test_cache_miss(self):
        """Test cache miss returns None."""
        result = self.cache.get("This prompt is not cached")
        self.assertIsNone(result)
    
    def test_cache_hit_increments_hits(self):
        """Test that cache hits are tracked."""
        prompt = "Test prompt"
        response = "Test response"
        
        self.cache.set(prompt, response)
        initial_hits = self.cache._stats['hits']
        
        self.cache.get(prompt)
        
        self.assertEqual(self.cache._stats['hits'], initial_hits + 1)
    
    def test_cache_miss_increments_misses(self):
        """Test that cache misses are tracked."""
        initial_misses = self.cache._stats['misses']
        
        self.cache.get("Non-existent prompt")
        
        self.assertEqual(self.cache._stats['misses'], initial_misses + 1)
    
    def test_cache_with_different_response_types(self):
        """Test caching different response types."""
        prompts_and_responses = [
            ("Prompt 1", "String response"),
            ("Prompt 2", {"response": "Dict response"}),
            ("Prompt 3", ["List", "response"]),
            ("Prompt 4", Mock()),
        ]
        
        for prompt, response in prompts_and_responses:
            self.cache.set(prompt, response)
            cached = self.cache.get(prompt)
            self.assertEqual(cached, response)
    
    def test_cache_cost_tracking(self):
        """Test cost tracking."""
        prompt = "Test prompt"
        response = "Test response"
        cost = 0.05
        
        initial_cost = self.cache._stats['cost_saved']
        self.cache.set(prompt, response, cost=cost)
        
        self.assertEqual(self.cache._stats['cost_saved'], initial_cost + cost)
    
    def test_cache_multiple_responses(self):
        """Test caching multiple responses."""
        prompts = [f"Prompt {i}" for i in range(5)]
        responses = [f"Response {i}" for i in range(5)]
        
        for prompt, response in zip(prompts, responses):
            self.cache.set(prompt, response)
        
        self.assertEqual(self.cache.get_size(), 5)
        
        for prompt, response in zip(prompts, responses):
            self.assertEqual(self.cache.get(prompt), response)


class TestCacheExpiration(unittest.TestCase):
    """TTL and expiration tests."""
    
    def setUp(self):
        """Create cache with short TTL for testing."""
        reset_ai_cache()
        self.cache = AIResponseCache(ttl_hours=0.001)  # ~3.6 seconds
    
    def test_response_expires_after_ttl(self):
        """Test that responses expire after TTL."""
        prompt = "Test prompt"
        response = "Test response"
        
        self.cache.set(prompt, response)
        
        # Should be cached immediately
        self.assertTrue(self.cache.has(prompt))
        self.assertIsNotNone(self.cache.get(prompt))
        
        # Wait for expiration
        time.sleep(4)
        
        # Should be expired now
        self.assertFalse(self.cache.has(prompt))
        self.assertIsNone(self.cache.get(prompt))
    
    def test_expired_entry_increments_evictions(self):
        """Test that expired entries are counted."""
        prompt = "Test prompt"
        response = "Test response"
        
        self.cache.set(prompt, response)
        initial_evictions = self.cache._stats['evictions']
        
        time.sleep(4)
        self.cache.get(prompt)
        
        self.assertGreater(self.cache._stats['evictions'], initial_evictions)
    
    def test_clearing_cache_removes_all_entries(self):
        """Test that clear() removes all entries."""
        for i in range(5):
            self.cache.set(f"Prompt {i}", f"Response {i}")
        
        self.assertEqual(self.cache.get_size(), 5)
        
        cleared = self.cache.clear()
        
        self.assertEqual(cleared, 5)
        self.assertEqual(self.cache.get_size(), 0)


class TestPromptAnalyzer(unittest.TestCase):
    """Prompt analysis tests."""
    
    def test_is_cacheable_valid_prompt(self):
        """Test that valid prompts are marked cacheable."""
        prompt = "Explain the theory of relativity"
        
        is_cacheable, reason = PromptAnalyzer.is_cacheable(prompt)
        
        self.assertTrue(is_cacheable)
    
    def test_is_cacheable_short_prompt(self):
        """Test that short prompts are not cacheable."""
        prompt = "Hi"
        
        is_cacheable, reason = PromptAnalyzer.is_cacheable(prompt)
        
        self.assertFalse(is_cacheable)
        self.assertIn("short", reason.lower())
    
    def test_is_cacheable_dynamic_keyword(self):
        """Test that dynamic prompts are not cacheable."""
        dynamic_prompts = [
            "What is the current time?",
            "Tell me today's weather",
            "Show me the latest news",
            "What is the real-time stock price?"
        ]
        
        for prompt in dynamic_prompts:
            is_cacheable, reason = PromptAnalyzer.is_cacheable(prompt)
            self.assertFalse(is_cacheable, f"Prompt '{prompt}' should not be cacheable")
    
    def test_cost_estimation(self):
        """Test cost estimation."""
        prompt_length = 100
        response_length = 500
        
        cost = PromptAnalyzer.get_cost_estimate(prompt_length, response_length)
        
        # Should be a positive number
        self.assertGreater(cost, 0)
        self.assertLess(cost, 1.0)  # Should be less than $1
    
    def test_cost_estimation_scales_with_length(self):
        """Test that cost scales with input length."""
        cost_short = PromptAnalyzer.get_cost_estimate(50, 100)
        cost_long = PromptAnalyzer.get_cost_estimate(500, 100)
        
        self.assertGreater(cost_long, cost_short)


class TestCacheStatistics(unittest.TestCase):
    """Cache statistics tests."""
    
    def setUp(self):
        """Create fresh cache."""
        reset_ai_cache()
        self.cache = AIResponseCache(ttl_hours=24)
    
    def test_stats_initial_state(self):
        """Test initial statistics."""
        stats = self.cache.get_stats()
        
        self.assertEqual(stats['hits'], 0)
        self.assertEqual(stats['misses'], 0)
        self.assertEqual(stats['evictions'], 0)
        self.assertEqual(stats['current_size'], 0)
        self.assertEqual(stats['hit_rate'], 0)
    
    def test_stats_after_operations(self):
        """Test statistics tracking."""
        self.cache.set("Prompt 1", "Response 1")
        self.cache.set("Prompt 2", "Response 2")
        
        self.cache.get("Prompt 1")  # hit
        self.cache.get("Prompt 1")  # hit
        self.cache.get("Prompt 3")  # miss
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats['hits'], 2)
        self.assertEqual(stats['misses'], 1)
        self.assertEqual(stats['current_size'], 2)
    
    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        self.cache.set("Prompt 1", "Response 1")
        
        # 2 hits, 2 misses = 50%
        self.cache.get("Prompt 1")  # hit
        self.cache.get("Prompt 1")  # hit
        self.cache.get("Prompt 2")  # miss
        self.cache.get("Prompt 3")  # miss
        
        hit_rate = self.cache.get_hit_rate()
        self.assertEqual(hit_rate, 50.0)
    
    def test_cost_saved_tracking(self):
        """Test cost saved tracking."""
        self.cache.set("Prompt 1", "Response 1", cost=0.05)
        self.cache.set("Prompt 2", "Response 2", cost=0.03)
        
        cost_saved = self.cache.get_cost_saved()
        
        self.assertAlmostEqual(cost_saved, 0.08, places=2)
    
    def test_export_stats(self):
        """Test statistics export."""
        self.cache.set("Test prompt", "Test response")
        
        report = self.cache.export_stats()
        
        self.assertIn("Cache Hits", report)
        self.assertIn("Hit Rate", report)
        self.assertIn("Cost Saved", report)


class TestThreadSafety(unittest.TestCase):
    """Thread safety tests."""
    
    def setUp(self):
        """Create fresh cache."""
        reset_ai_cache()
        self.cache = AIResponseCache(ttl_hours=24)
    
    def test_concurrent_set_operations(self):
        """Test concurrent set operations."""
        def set_responses(start_idx, count):
            for i in range(start_idx, start_idx + count):
                self.cache.set(f"Prompt {i}", f"Response {i}")
        
        threads = []
        for i in range(0, 50, 10):
            t = threading.Thread(target=set_responses, args=(i, 10))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have cached 50 responses without errors
        self.assertEqual(self.cache.get_size(), 50)
    
    def test_concurrent_get_operations(self):
        """Test concurrent get operations."""
        prompt = "Test prompt"
        response = "Test response"
        self.cache.set(prompt, response)
        
        def get_response(count):
            for _ in range(count):
                result = self.cache.get(prompt)
                self.assertEqual(result, response)
        
        threads = []
        for _ in range(5):
            t = threading.Thread(target=get_response, args=(10,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have 50 hits
        self.assertEqual(self.cache._stats['hits'], 50)
    
    def test_concurrent_mixed_operations(self):
        """Test concurrent set and get operations."""
        results = []
        
        def worker(worker_id):
            prompt = f"Prompt {worker_id}"
            response = f"Response {worker_id}"
            
            self.cache.set(prompt, response)
            time.sleep(0.001)
            
            result = self.cache.get(prompt)
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
        reset_ai_cache()
    
    def test_get_cache_creates_instance(self):
        """Test that get_cache creates instance."""
        cache = get_ai_cache()
        self.assertIsInstance(cache, AIResponseCache)
    
    def test_get_cache_returns_same_instance(self):
        """Test that get_cache returns same instance."""
        cache1 = get_ai_cache()
        cache2 = get_ai_cache()
        
        self.assertIs(cache1, cache2)
    
    def test_cache_instance_ttl(self):
        """Test cache instance TTL."""
        cache = get_ai_cache(ttl_hours=12)
        self.assertEqual(cache.ttl_seconds, 12 * 3600)
    
    def test_reset_cache_clears_instance(self):
        """Test that reset clears the instance."""
        cache1 = get_ai_cache()
        cache1.set("Test prompt", "Test response")
        
        reset_ai_cache()
        
        cache2 = get_ai_cache()
        self.assertEqual(cache2.get_size(), 0)


class TestCacheKeyGeneration(unittest.TestCase):
    """Cache key generation tests."""
    
    def setUp(self):
        """Create fresh cache."""
        reset_ai_cache()
        self.cache = AIResponseCache(ttl_hours=24)
    
    def test_same_prompt_same_key(self):
        """Test that same prompt generates same key."""
        prompt = "Test prompt"
        
        key1 = self.cache._generate_key(prompt)
        key2 = self.cache._generate_key(prompt)
        
        self.assertEqual(key1, key2)
    
    def test_different_prompt_different_key(self):
        """Test that different prompts generate different keys."""
        prompt1 = "Test prompt 1"
        prompt2 = "Test prompt 2"
        
        key1 = self.cache._generate_key(prompt1)
        key2 = self.cache._generate_key(prompt2)
        
        self.assertNotEqual(key1, key2)
    
    def test_whitespace_normalization(self):
        """Test that whitespace is normalized."""
        prompt1 = "Test prompt"
        prompt2 = "  Test prompt  "
        
        key1 = self.cache._generate_key(prompt1)
        key2 = self.cache._generate_key(prompt2)
        
        self.assertEqual(key1, key2)
    
    def test_long_prompt_handling(self):
        """Test handling of very long prompts."""
        long_prompt = "A" * 2000
        
        key = self.cache._generate_key(long_prompt)
        
        # Should be manageable length
        self.assertIsInstance(key, str)
        self.assertGreater(len(key), 0)


class TestIntegration(unittest.TestCase):
    """Integration tests simulating real usage."""
    
    def setUp(self):
        """Create fresh cache."""
        reset_ai_cache()
        self.cache = AIResponseCache(ttl_hours=24)
    
    def test_gemini_response_caching_scenario(self):
        """Test caching during repeated Gemini API calls."""
        # Simulate 3 AI requests
        requests = [
            {"prompt": "Explain quantum computing", "cost": 0.02},
            {"prompt": "What is machine learning?", "cost": 0.02},
            {"prompt": "Explain quantum computing", "cost": 0.02},  # Repeat
        ]
        
        for i, req in enumerate(requests):
            prompt = req["prompt"]
            cost = req["cost"]
            
            if self.cache.has(prompt):
                # Cache hit - no API call needed
                response = self.cache.get(prompt)
            else:
                # Cache miss - simulate API call
                response = f"Response to: {prompt}"
                self.cache.set(prompt, response, cost=cost)
        
        # Should have 2 unique responses cached
        self.assertEqual(self.cache.get_size(), 2)
        
        # Should have 1 hit (3rd request)
        stats = self.cache.get_stats()
        self.assertEqual(stats['hits'], 1)
    
    def test_cost_savings_calculation(self):
        """Test cost savings calculation."""
        # Simulate 10 identical requests
        prompt = "Explain artificial intelligence"
        response = "AI is the simulation of human intelligence..."
        cost = 0.015
        
        # First request - cache miss
        self.cache.set(prompt, response, cost=cost)
        
        # Next 9 requests - cache hits
        for _ in range(9):
            if self.cache.has(prompt):
                self.cache.get(prompt)
        
        # Total cost saved = 9 API calls × $0.015 = $0.135
        cost_saved = self.cache.get_cost_saved()
        
        # Should have saved ~$0.135
        self.assertAlmostEqual(cost_saved, 0.135, places=2)


class TestMockRedisIntegration(unittest.TestCase):
    """Tests for Redis integration (with mock)."""
    
    def setUp(self):
        """Create cache with mock Redis."""
        reset_ai_cache()
        self.mock_redis = MagicMock()
        self.cache = AIResponseCache(ttl_hours=24, redis_client=self.mock_redis)
    
    def test_redis_sync_on_set(self):
        """Test that set operation syncs to Redis."""
        prompt = "Test prompt"
        response = "Test response"
        
        self.cache.set(prompt, response)
        
        # Redis setex should be called
        self.mock_redis.setex.assert_called()
    
    def test_redis_get_fallback(self):
        """Test fallback to Redis when memory cache miss."""
        prompt = "Test prompt"
        response = "Test response"
        
        # Configure mock to return data
        self.mock_redis.get.return_value = json.dumps({
            'response': response,
            'prompt': prompt,
            'timestamp': time.time(),
            'created_at': time.time(),
            'access_count': 1,
            'cost': 0.01
        }).encode()
        
        # First get from memory (miss)
        result = self.cache.get(prompt)
        self.assertIsNone(result)
        
        # Redis get should be called
        self.mock_redis.get.assert_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
