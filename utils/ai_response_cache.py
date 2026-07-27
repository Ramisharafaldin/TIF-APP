"""
AI Response Caching System

Implements a hybrid caching layer for Gemini API responses.
Uses in-memory cache for speed with optional Redis persistence.

Features:
- Full-prompt text cache keys
- 24-hour TTL (configurable)
- Dual-layer caching (in-memory + optional Redis)
- Cost reduction (avoid repeated API calls)
- Latency reduction (<1ms for cache hits)
- Automatic cleanup of expired entries
- Cache statistics and monitoring

Usage:
    cache = AIResponseCache()
    
    # Cache an API response
    cache.set(prompt, response)
    
    # Retrieve cached response
    cached_response = cache.get(prompt)
    
    # Check if response is cached
    if cache.has(prompt):
        response = cache.get(prompt)
"""

import hashlib
import json
import time
import threading
from typing import Any, Dict, Optional, List, Tuple
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AIResponseCache:
    """
    Hybrid caching system for AI API responses.
    
    Features:
    - In-memory cache for fast access
    - Optional Redis backend for persistence
    - Full-prompt text cache keys
    - 24-hour TTL (configurable)
    - Automatic cleanup
    - Cost tracking
    """
    
    def __init__(self, ttl_hours: int = 24, redis_client=None):
        """
        Initialize the AI response cache.
        
        Args:
            ttl_hours: Time-to-live in hours (default: 24)
            redis_client: Optional Redis client for persistent storage
        """
        self.ttl_seconds = ttl_hours * 3600
        self.redis_client = redis_client
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_cached': 0,
            'cost_saved': 0.0,  # Estimated API cost saved
            'redis_syncs': 0
        }
        
        logger.info(f"AIResponseCache initialized with TTL={ttl_hours}h, Redis={'enabled' if redis_client else 'disabled'}")
    
    def _generate_key(self, prompt: str) -> str:
        """
        Generate cache key from prompt text.
        Uses full prompt text for accuracy.
        
        Args:
            prompt: The prompt text
        
        Returns:
            Cache key (full prompt text, trimmed)
        """
        # Normalize prompt (strip whitespace, lowercase)
        normalized = prompt.strip()
        
        # For very long prompts, use hash + first part
        if len(normalized) > 1000:
            key = normalized[:500] + "..." + hashlib.sha256(normalized.encode()).hexdigest()
            logger.debug(f"Generated composite key for long prompt (orig: {len(normalized)} chars)")
            return key
        
        return normalized
    
    def set(self, prompt: str, response: Any, cost: float = 0.01) -> Tuple[bool, str]:
        """
        Cache an AI response.
        
        Args:
            prompt: The prompt text
            response: The API response object
            cost: Estimated cost of the API call (for tracking)
        
        Returns:
            Tuple of (success, message)
        """
        key = self._generate_key(prompt)
        timestamp = time.time()
        
        try:
            with self._lock:
                is_update = key in self._memory_cache
                
                # Store in memory
                self._memory_cache[key] = {
                    'response': response,
                    'prompt': prompt,
                    'timestamp': timestamp,
                    'created_at': self._memory_cache[key].get('created_at', timestamp) if is_update else timestamp,
                    'access_count': self._memory_cache[key].get('access_count', 0) if is_update else 0,
                    'cost': cost
                }
                
                if not is_update:
                    self._stats['total_cached'] += 1
                    self._stats['cost_saved'] += cost
                
                # Also store in Redis if available
                if self.redis_client:
                    try:
                        self._sync_to_redis(key, self._memory_cache[key])
                        self._stats['redis_syncs'] += 1
                    except Exception as e:
                        logger.warning(f"Failed to sync to Redis: {e}")
                
                logger.debug(f"Cached AI response with key (len={len(key)})")
                return True, f"Cached response (cost saved: ${cost:.4f})"
        
        except Exception as e:
            logger.error(f"Error caching AI response: {e}")
            return False, f"Error: {str(e)}"
    
    def get(self, prompt: str) -> Optional[Any]:
        """
        Retrieve cached AI response.
        
        Args:
            prompt: The prompt text
        
        Returns:
            Cached response if found and not expired, None otherwise
        """
        key = self._generate_key(prompt)
        
        with self._lock:
            # Check memory cache first
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                age = time.time() - entry['timestamp']
                
                # Check if expired
                if age > self.ttl_seconds:
                    del self._memory_cache[key]
                    self._stats['evictions'] += 1
                    self._stats['misses'] += 1
                    logger.debug(f"Memory cache expired (age={age:.1f}s)")
                    return None
                
                # Update access info
                entry['access_count'] += 1
                entry['timestamp'] = time.time()  # Update last access
                self._stats['hits'] += 1
                
                logger.debug(f"Memory cache hit (age={age:.1f}s)")
                return entry['response']
            
            # Try Redis if available
            if self.redis_client:
                try:
                    cached = self._get_from_redis(key)
                    if cached:
                        # Also update memory cache
                        self._memory_cache[key] = cached
                        self._stats['hits'] += 1
                        logger.debug("Cache hit from Redis (synced to memory)")
                        return cached['response']
                except Exception as e:
                    logger.warning(f"Failed to get from Redis: {e}")
            
            self._stats['misses'] += 1
            logger.debug(f"Cache miss for key")
            return None
    
    def has(self, prompt: str) -> bool:
        """
        Check if response is cached and not expired.
        
        Args:
            prompt: The prompt text
        
        Returns:
            True if cached and valid, False otherwise
        """
        key = self._generate_key(prompt)
        
        with self._lock:
            # Check memory
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                age = time.time() - entry['timestamp']
                
                if age > self.ttl_seconds:
                    del self._memory_cache[key]
                    return False
                
                return True
            
            # Check Redis
            if self.redis_client:
                try:
                    return self._exists_in_redis(key)
                except Exception as e:
                    logger.warning(f"Failed to check Redis: {e}")
            
            return False
    
    def _sync_to_redis(self, key: str, entry: Dict[str, Any]) -> None:
        """
        Sync cache entry to Redis.
        
        Args:
            key: Cache key
            entry: Cache entry dict
        """
        if not self.redis_client:
            return
        
        try:
            # Serialize entry for Redis storage
            serialized = json.dumps({
                'response': str(entry['response']),  # Convert to string
                'prompt': entry['prompt'],
                'timestamp': entry['timestamp'],
                'created_at': entry['created_at'],
                'access_count': entry['access_count'],
                'cost': entry['cost']
            })
            
            # Set with expiration
            self.redis_client.setex(
                f"ai_response:{key}",
                self.ttl_seconds,
                serialized
            )
        except Exception as e:
            logger.error(f"Error syncing to Redis: {e}")
    
    def _get_from_redis(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve entry from Redis.
        
        Args:
            key: Cache key
        
        Returns:
            Cache entry dict or None
        """
        if not self.redis_client:
            return None
        
        try:
            data = self.redis_client.get(f"ai_response:{key}")
            if data:
                entry = json.loads(data)
                # Reconstruct entry
                return {
                    'response': entry['response'],
                    'prompt': entry['prompt'],
                    'timestamp': entry['timestamp'],
                    'created_at': entry['created_at'],
                    'access_count': entry['access_count'],
                    'cost': entry['cost']
                }
        except Exception as e:
            logger.warning(f"Error retrieving from Redis: {e}")
        
        return None
    
    def _exists_in_redis(self, key: str) -> bool:
        """
        Check if key exists in Redis.
        
        Args:
            key: Cache key
        
        Returns:
            True if exists, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            return self.redis_client.exists(f"ai_response:{key}") > 0
        except Exception as e:
            logger.warning(f"Error checking Redis: {e}")
            return False
    
    def clear(self) -> int:
        """
        Clear all cached responses.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            count = len(self._memory_cache)
            self._memory_cache.clear()
            
            # Clear Redis
            if self.redis_client:
                try:
                    # Delete all ai_response: keys
                    pattern = "ai_response:*"
                    keys = self.redis_client.keys(pattern)
                    if keys:
                        self.redis_client.delete(*keys)
                except Exception as e:
                    logger.warning(f"Error clearing Redis: {e}")
            
            logger.info(f"Cleared {count} cached responses")
            return count
    
    def _cleanup_expired(self) -> int:
        """
        Remove all expired entries from memory cache.
        
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._memory_cache.items()
            if (current_time - entry['timestamp']) > self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self._memory_cache[key]
            self._stats['evictions'] += 1
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats:
            - hits: Number of cache hits
            - misses: Number of cache misses
            - evictions: Number of expired entries removed
            - total_cached: Total entries cached (in this session)
            - current_size: Current number of cached responses
            - hit_rate: Hit rate percentage
            - cost_saved: Estimated cost saved in dollars
            - redis_syncs: Number of Redis synchronizations
            - ttl_hours: TTL setting
        """
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'evictions': self._stats['evictions'],
                'total_cached': self._stats['total_cached'],
                'current_size': len(self._memory_cache),
                'hit_rate': hit_rate,
                'cost_saved': self._stats['cost_saved'],
                'redis_syncs': self._stats['redis_syncs'],
                'ttl_hours': self.ttl_seconds // 3600,
                'memory_keys': list(self._memory_cache.keys())[:5]  # Sample of cached prompts
            }
    
    def get_size(self) -> int:
        """Get current number of cached responses."""
        with self._lock:
            return len(self._memory_cache)
    
    def get_hit_rate(self) -> float:
        """Get cache hit rate percentage."""
        with self._lock:
            total = self._stats['hits'] + self._stats['misses']
            if total == 0:
                return 0.0
            return (self._stats['hits'] / total) * 100
    
    def get_cost_saved(self) -> float:
        """Get estimated cost saved in dollars."""
        with self._lock:
            return self._stats['cost_saved']
    
    def export_stats(self) -> str:
        """
        Export statistics as formatted string.
        
        Returns:
            Formatted statistics report
        """
        stats = self.get_stats()
        
        report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI Response Cache Statistics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cache Hits:              {stats['hits']}
Cache Misses:            {stats['misses']}
Hit Rate:                {stats['hit_rate']:.1f}%
Current Size:            {stats['current_size']} responses
Total Cached (session):  {stats['total_cached']}
Evictions:               {stats['evictions']}
Cost Saved:              ${stats['cost_saved']:.2f}
Redis Syncs:             {stats['redis_syncs']}
TTL:                     {stats['ttl_hours']} hours
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return report


class PromptAnalyzer:
    """
    Utility class for analyzing and categorizing prompts.
    Helps identify cacheable vs. non-cacheable prompts.
    """
    
    # Keywords that suggest non-cacheable (user-specific) prompts
    DYNAMIC_KEYWORDS = [
        'today', 'now', 'current', 'latest', 'real-time',
        'live', 'recent', 'update', 'yesterday', 'tomorrow',
        'my ', 'your ', 'user', 'specific', 'custom'
    ]
    
    @staticmethod
    def is_cacheable(prompt: str) -> Tuple[bool, str]:
        """
        Analyze if prompt is suitable for caching.
        
        Args:
            prompt: The prompt text
        
        Returns:
            Tuple of (is_cacheable, reason)
        """
        lower_prompt = prompt.lower()
        
        # Check for dynamic keywords
        for keyword in PromptAnalyzer.DYNAMIC_KEYWORDS:
            if keyword in lower_prompt:
                return False, f"Contains dynamic keyword: '{keyword}'"
        
        # Check for very short prompts
        if len(prompt.strip()) < 10:
            return False, "Prompt too short (< 10 chars)"
        
        return True, "Suitable for caching"
    
    @staticmethod
    def get_cost_estimate(prompt_length: int, response_length: int = 500) -> float:
        """
        Estimate API cost for a request.
        Based on token count (rough estimate: 4 chars = 1 token).
        
        Args:
            prompt_length: Length of prompt in characters
            response_length: Estimated response length
        
        Returns:
            Estimated cost in dollars
        """
        # Gemini API: ~$0.000075 per input token, $0.0003 per output token
        input_tokens = prompt_length / 4
        output_tokens = response_length / 4
        
        input_cost = input_tokens * 0.000075
        output_cost = output_tokens * 0.0003
        
        return input_cost + output_cost


# Global cache instance
_cache_instance: Optional[AIResponseCache] = None
_cache_lock = threading.Lock()


def get_ai_cache(ttl_hours: int = 24, redis_client=None) -> AIResponseCache:
    """
    Get or create the global AI response cache instance.
    
    Args:
        ttl_hours: TTL in hours (only used on first call)
        redis_client: Optional Redis client (only used on first call)
    
    Returns:
        AIResponseCache instance
    """
    global _cache_instance
    
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = AIResponseCache(ttl_hours=ttl_hours, redis_client=redis_client)
    
    return _cache_instance


def reset_ai_cache() -> None:
    """Reset the global AI cache instance (for testing)."""
    global _cache_instance
    if _cache_instance is not None:
        _cache_instance.clear()
    _cache_instance = None
