"""
XGBoost Model Cache Manager

Implements an in-memory cache for trained XGBoost models with TTL support.
Models are cached by feature hash to avoid retraining on duplicate requests.

Features:
- 1-hour TTL (configurable)
- Feature-based cache keys
- Pickle-based serialization
- Thread-safe operations
- Automatic cleanup of expired entries
- Cache statistics tracking

Usage:
    cache = ModelCache(ttl_seconds=3600)
    
    # Cache a model
    cache.set(features, model_object)
    
    # Retrieve cached model
    cached_model = cache.get(features)
    
    # Check if model exists
    if cache.has(features):
        model = cache.get(features)
"""

import hashlib
import pickle
import time
import threading
from typing import Any, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ModelCache:
    """
    In-memory cache for trained XGBoost models with TTL support.
    
    Uses feature hashing to create cache keys. Models expire after
    the configured TTL and are automatically cleaned up.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize the model cache.
        
        Args:
            ttl_seconds: Time-to-live for cached models in seconds (default: 1 hour)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_cached': 0
        }
        logger.info(f"ModelCache initialized with TTL={ttl_seconds}s")
    
    def _generate_key(self, features: Any) -> str:
        """
        Generate a cache key from features using hash.
        
        Args:
            features: Input features (dict, array, or string)
        
        Returns:
            SHA256 hash of serialized features
        """
        try:
            # Serialize features consistently
            serialized = pickle.dumps(features, protocol=pickle.HIGHEST_PROTOCOL)
            key = hashlib.sha256(serialized).hexdigest()
            return key
        except Exception as e:
            logger.error(f"Error generating cache key: {e}")
            raise ValueError(f"Cannot cache non-serializable features: {e}")
    
    def set(self, features: Any, model: Any) -> str:
        """
        Cache a trained model.
        
        Args:
            features: Input features used to train the model
            model: Trained XGBoost model object
        
        Returns:
            Cache key (feature hash)
        
        Raises:
            ValueError: If features cannot be serialized
        """
        key = self._generate_key(features)
        
        with self._lock:
            # Check if we're updating an existing cache entry
            is_update = key in self._cache
            
            # Store model with timestamp
            self._cache[key] = {
                'model': model,
                'timestamp': time.time(),
                'created_at': self._cache[key].get('created_at', time.time()) if is_update else time.time(),
                'access_count': self._cache[key].get('access_count', 0) if is_update else 0
            }
            
            if not is_update:
                self._stats['total_cached'] += 1
            
            # Clean up expired entries occasionally
            if self._stats['total_cached'] % 10 == 0:
                self._cleanup_expired()
            
            logger.debug(f"Cached model with key {key[:8]}... (TTL={self.ttl_seconds}s)")
            return key
    
    def get(self, features: Any) -> Optional[Any]:
        """
        Retrieve a cached model if it exists and hasn't expired.
        
        Args:
            features: Input features to look up
        
        Returns:
            Cached model if found and not expired, None otherwise
        """
        key = self._generate_key(features)
        
        with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                logger.debug(f"Cache miss for key {key[:8]}...")
                return None
            
            entry = self._cache[key]
            age = time.time() - entry['timestamp']
            
            # Check if expired
            if age > self.ttl_seconds:
                del self._cache[key]
                self._stats['misses'] += 1
                self._stats['evictions'] += 1
                logger.debug(f"Cache entry expired (age={age:.1f}s > TTL={self.ttl_seconds}s)")
                return None
            
            # Update access info
            entry['access_count'] += 1
            entry['timestamp'] = time.time()  # Update last access time
            self._stats['hits'] += 1
            
            logger.debug(f"Cache hit for key {key[:8]}... (age={age:.1f}s)")
            return entry['model']
    
    def has(self, features: Any) -> bool:
        """
        Check if a model is cached and not expired.
        
        Args:
            features: Input features to check
        
        Returns:
            True if model is cached and valid, False otherwise
        """
        key = self._generate_key(features)
        
        with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            age = time.time() - entry['timestamp']
            
            if age > self.ttl_seconds:
                del self._cache[key]
                return False
            
            return True
    
    def _cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if (current_time - entry['timestamp']) > self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self._cache[key]
            self._stats['evictions'] += 1
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def clear(self) -> int:
        """
        Clear all cached models.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} cached models")
            return count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats:
            - hits: Number of cache hits
            - misses: Number of cache misses
            - evictions: Number of expired entries removed
            - total_cached: Total entries cached (in this session)
            - current_size: Current number of cached models
            - hit_rate: Hit rate percentage (hits / (hits + misses))
            - ttl_seconds: TTL setting
        """
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'evictions': self._stats['evictions'],
                'total_cached': self._stats['total_cached'],
                'current_size': len(self._cache),
                'hit_rate': hit_rate,
                'ttl_seconds': self.ttl_seconds
            }
    
    def get_size(self) -> int:
        """
        Get current number of cached models.
        
        Returns:
            Number of cached models
        """
        with self._lock:
            return len(self._cache)
    
    def get_hit_rate(self) -> float:
        """
        Get cache hit rate percentage.
        
        Returns:
            Hit rate as percentage (0-100), or 0 if no requests yet
        """
        with self._lock:
            total = self._stats['hits'] + self._stats['misses']
            if total == 0:
                return 0.0
            return (self._stats['hits'] / total) * 100


class FeatureHasher:
    """
    Utility class for generating consistent feature hashes for cache keys.
    """
    
    @staticmethod
    def hash_array(array: Any) -> str:
        """
        Generate hash from numpy array or list.
        
        Args:
            array: Input array/list
        
        Returns:
            SHA256 hash
        """
        serialized = pickle.dumps(array, protocol=pickle.HIGHEST_PROTOCOL)
        return hashlib.sha256(serialized).hexdigest()
    
    @staticmethod
    def hash_dict(data: Dict) -> str:
        """
        Generate hash from dictionary (order-independent).
        
        Args:
            data: Input dictionary
        
        Returns:
            SHA256 hash
        """
        # Sort keys to ensure consistent hashing
        serialized = pickle.dumps(
            {k: data[k] for k in sorted(data.keys())},
            protocol=pickle.HIGHEST_PROTOCOL
        )
        return hashlib.sha256(serialized).hexdigest()
    
    @staticmethod
    def hash_params(params: Dict) -> str:
        """
        Generate hash from forecasting parameters.
        
        Args:
            params: Forecasting parameters
        
        Returns:
            SHA256 hash
        """
        return FeatureHasher.hash_dict(params)


# Global cache instance
_cache_instance: Optional[ModelCache] = None
_cache_lock = threading.Lock()


def get_model_cache(ttl_seconds: int = 3600) -> ModelCache:
    """
    Get or create the global model cache instance.
    
    Args:
        ttl_seconds: TTL for cached models (only used on first call)
    
    Returns:
        ModelCache instance
    """
    global _cache_instance
    
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = ModelCache(ttl_seconds=ttl_seconds)
    
    return _cache_instance


def reset_cache() -> None:
    """Reset the global cache instance (for testing)."""
    global _cache_instance
    if _cache_instance is not None:
        _cache_instance.clear()
    _cache_instance = None
