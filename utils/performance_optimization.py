"""
Performance optimisation module for Dynamic Inventory Alerts.

Phase 4 cleanup (§3.6): DuckDB-specific index creation is replaced with a
no-op since MongoDB manages indexes via auto-created schemas and the TTL
indexes already set up in ``MongoDataStore``. The monitoring and caching
features remain available for alert-service callers.
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class PerformanceOptimizer:
    """
    Performance optimisation utilities for inventory alerts system.
    """
    
    def __init__(self):
        self.performance_metrics = {}
        self.query_cache = {}
        self.cache_hit_count = 0
        self.cache_miss_count = 0
    
    def create_database_indexes(self) -> Tuple[bool, str]:
        """
        MongoDB manages indexes itself — no app-side index creation needed.

        Returns:
            Tuple of (success, message)
        """
        return True, "Index creation skipped: MongoDB manages indexes automatically."
    
    def analyze_query_performance(self, username: str, branch_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyse query performance for alert generation.

        With MongoDB this is a no-op — the database manages its own query
        plans. Returns a stub result for backward compatibility.
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'username': username,
            'branch_filter': branch_filter,
            'queries': [],
            'recommendations': ['MongoDB manages query plans automatically.'],
        }

    def optimize_alert_queries(self) -> Tuple[bool, str]:
        """
        Optimise database queries used for alert generation.

        No-op for MongoDB — indexes and query plans are managed by the
        database engine.
        """
        return True, "Query optimisation skipped: MongoDB manages query plans automatically."
    
    def monitor_performance_metrics(self, operation_name: str, duration: float, 
                                  additional_metrics: Optional[Dict[str, Any]] = None):
        """
        Monitor and log performance metrics for alert operations.
        
        Args:
            operation_name: Name of the operation being monitored
            duration: Duration of the operation in seconds
            additional_metrics: Optional additional metrics to log
        """
        try:
            timestamp = datetime.now()
            
            # Store metrics in memory
            if operation_name not in self.performance_metrics:
                self.performance_metrics[operation_name] = []
            
            metric_entry = {
                'timestamp': timestamp.isoformat(),
                'duration': duration,
                'additional_metrics': additional_metrics or {}
            }
            
            self.performance_metrics[operation_name].append(metric_entry)
            
            # Keep only last 100 entries per operation
            if len(self.performance_metrics[operation_name]) > 100:
                self.performance_metrics[operation_name] = self.performance_metrics[operation_name][-100:]
            
            # Log performance metrics
            logger.info(f"Performance metric - {operation_name}: {duration:.3f}s", 
                       extra={'performance_metric': metric_entry})
            
            # Log warnings for slow operations
            if duration > 2.0:
                logger.warning(f"Slow operation detected - {operation_name}: {duration:.3f}s")
            
        except Exception as e:
            logger.error(f"Error monitoring performance metrics: {e}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get summary of performance metrics.
        
        Returns:
            Dictionary with performance summary
        """
        try:
            summary = {
                'timestamp': datetime.now().isoformat(),
                'operations': {},
                'cache_stats': {
                    'hit_count': self.cache_hit_count,
                    'miss_count': self.cache_miss_count,
                    'hit_ratio': self.cache_hit_count / max(self.cache_hit_count + self.cache_miss_count, 1)
                }
            }
            
            for operation_name, metrics in self.performance_metrics.items():
                if not metrics:
                    continue
                
                durations = [m['duration'] for m in metrics]
                
                operation_summary = {
                    'total_calls': len(metrics),
                    'avg_duration': sum(durations) / len(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations),
                    'last_call': metrics[-1]['timestamp']
                }
                
                # Calculate percentiles
                sorted_durations = sorted(durations)
                n = len(sorted_durations)
                if n > 0:
                    operation_summary['p50_duration'] = sorted_durations[n // 2]
                    operation_summary['p95_duration'] = sorted_durations[int(n * 0.95)]
                    operation_summary['p99_duration'] = sorted_durations[int(n * 0.99)]
                
                summary['operations'][operation_name] = operation_summary
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def clear_performance_metrics(self):
        """Clear stored performance metrics."""
        self.performance_metrics.clear()
        self.cache_hit_count = 0
        self.cache_miss_count = 0
        logger.info("Cleared performance metrics")


# Global performance optimizer instance
performance_optimizer = PerformanceOptimizer()


def initialize_performance_optimizations() -> Tuple[bool, str]:
    """
    Initialize all performance optimizations for the alert system.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        results = []
        
        # Create database indexes
        index_success, index_message = performance_optimizer.create_database_indexes()
        results.append(f"Indexes: {index_message}")
        
        # Optimize queries
        query_success, query_message = performance_optimizer.optimize_alert_queries()
        results.append(f"Query optimization: {query_message}")
        
        overall_success = index_success and query_success
        overall_message = "; ".join(results)
        
        if overall_success:
            logger.info(f"Performance optimizations initialized successfully: {overall_message}")
        else:
            logger.warning(f"Some performance optimizations failed: {overall_message}")
        
        return overall_success, overall_message
        
    except Exception as e:
        logger.error(f"Error initializing performance optimizations: {e}", exc_info=True)
        return False, f"Error initializing optimizations: {str(e)}"


def monitor_alert_generation_performance(func):
    """
    Decorator to monitor performance of alert generation functions.
    
    Args:
        func: Function to monitor
        
    Returns:
        Wrapped function with performance monitoring
    """
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Extract metrics from function arguments
            additional_metrics = {}
            if args:
                if len(args) > 0:
                    additional_metrics['username'] = args[0]
                if len(args) > 1:
                    additional_metrics['branch_filter'] = args[1]
                if len(args) > 2:
                    additional_metrics['limit'] = args[2]
            
            if isinstance(result, list):
                additional_metrics['alert_count'] = len(result)
            
            # Monitor performance
            performance_optimizer.monitor_performance_metrics(
                operation_name=func.__name__,
                duration=duration,
                additional_metrics=additional_metrics
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            performance_optimizer.monitor_performance_metrics(
                operation_name=f"{func.__name__}_error",
                duration=duration,
                additional_metrics={'error': str(e)}
            )
            raise
    
    return wrapper


def get_database_performance_stats() -> Dict[str, Any]:
    """Get database performance stats — delegates to data_store health."""
    try:
        import data_store
        return data_store.get_database_health()
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {'error': str(e)}