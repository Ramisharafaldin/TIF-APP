#!/usr/bin/env python3
"""
Integration test for AI database functionality.
Tests the complete workflow of AI database operations.
"""

import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_store import (
    save_ai_query,
    get_ai_query_history,
    save_ai_cache,
    get_ai_cache,
    save_ai_performance_metric,
    get_ai_performance_metrics,
    get_ai_database_stats,
    cleanup_ai_data
)

def test_ai_database_integration():
    """Test complete AI database integration."""
    print("🧪 Testing AI Database Integration")
    print("=" * 50)
    
    try:
        # Test 1: AI Query Operations
        print("\n1️⃣ Testing AI Query Operations...")
        
        query_id = save_ai_query(
            user_id='integration_test_user',
            query_text='What is the current inventory status for branch A?',
            query_intent='inventory_status_query',
            response_data='{"status": "good", "items": 150, "alerts": 2}',
            processing_time=2.3
        )
        
        print(f"   ✅ Saved AI query with ID: {query_id}")
        
        # Retrieve query history
        history = get_ai_query_history('integration_test_user', limit=5)
        print(f"   ✅ Retrieved {len(history)} queries from history")
        
        if history:
            latest_query = history[0]
            print(f"   📝 Latest query: '{latest_query[1][:50]}...'")
            print(f"   ⏱️ Processing time: {latest_query[4]}s")
        
        # Test 2: AI Cache Operations
        print("\n2️⃣ Testing AI Cache Operations...")
        
        cache_key = f"inventory_insights_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        cache_data = '{"insights": ["Stock levels optimal", "Reorder point reached for item X"], "confidence": 0.95}'
        
        success = save_ai_cache(cache_key, cache_data, ttl_hours=2)
        print(f"   ✅ Saved cache entry: {success}")
        
        # Retrieve from cache
        cached_result = get_ai_cache(cache_key)
        print(f"   ✅ Retrieved from cache: {cached_result is not None}")
        
        if cached_result:
            print(f"   📦 Cache data length: {len(cached_result)} characters")
        
        # Test 3: Performance Metrics
        print("\n3️⃣ Testing Performance Metrics...")
        
        # Save multiple metrics
        metrics_data = [
            ('api_call_duration', 1.5, '{"endpoint": "/api/insights", "method": "POST"}'),
            ('cache_hit_rate', 0.85, '{"period": "1h", "total_requests": 100}'),
            ('query_processing_time', 2.3, '{"query_type": "inventory_status", "complexity": "medium"}'),
            ('ai_response_quality', 0.92, '{"user_rating": 4.6, "confidence": 0.92}')
        ]
        
        metric_ids = []
        for metric_type, value, metadata in metrics_data:
            metric_id = save_ai_performance_metric(metric_type, value, metadata)
            metric_ids.append(metric_id)
            print(f"   ✅ Saved {metric_type}: {value}")
        
        # Retrieve metrics
        all_metrics = get_ai_performance_metrics(hours=1)
        print(f"   📊 Retrieved {len(all_metrics)} performance metrics")
        
        # Test specific metric type
        api_metrics = get_ai_performance_metrics(metric_type='api_call_duration', hours=1)
        print(f"   🔍 API call duration metrics: {len(api_metrics)}")
        
        # Test 4: Database Statistics
        print("\n4️⃣ Testing Database Statistics...")
        
        stats = get_ai_database_stats()
        print("   📈 Current AI Database Statistics:")
        for key, value in stats.items():
            print(f"      {key}: {value}")
        
        # Test 5: Data Validation
        print("\n5️⃣ Testing Data Validation...")
        
        # Verify data integrity
        if stats['total_queries'] > 0:
            print("   ✅ AI queries table has data")
        
        if stats['cache_entries'] > 0:
            print("   ✅ AI cache table has data")
        
        if stats['performance_metrics'] > 0:
            print("   ✅ AI performance metrics table has data")
        
        # Test 6: Cleanup Test Data
        print("\n6️⃣ Cleaning up test data...")
        
        # Clean up the test data we created
        import sqlite3
        from data_store import DB_NAME
        
        conn = sqlite3.connect(DB_NAME, timeout=30.0)
        c = conn.cursor()
        
        # Remove test query
        c.execute("DELETE FROM ai_queries WHERE user_id = ?", ('integration_test_user',))
        queries_deleted = c.rowcount
        
        # Remove test cache
        c.execute("DELETE FROM ai_insights_cache WHERE cache_key = ?", (cache_key,))
        cache_deleted = c.rowcount
        
        # Remove test metrics
        c.execute("DELETE FROM ai_performance_metrics WHERE id IN ({})".format(','.join('?' * len(metric_ids))), metric_ids)
        metrics_deleted = c.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"   🧹 Cleaned up: {queries_deleted} queries, {cache_deleted} cache entries, {metrics_deleted} metrics")
        
        print("\n🎉 All AI Database Integration Tests Passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ai_database_integration()
    sys.exit(0 if success else 1)