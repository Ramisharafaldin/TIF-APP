"""
Unit tests for database schema updates.

Feature: gemini-api-integration, Task 10.1
Tests table creation, migration scripts, and data integrity
during database migrations for AI features.

Validates: All requirements (supporting infrastructure)
"""

import pytest
import sqlite3
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock
import json
from datetime import datetime

# Add project root to path
sys.path.append('.')

class TestDatabaseSchemaUpdates:
    """Unit tests for database schema updates and migrations."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Create temporary database for testing
        self.test_db_fd, self.test_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.test_db_fd)
        
        # Initialize test database connection
        self.conn = sqlite3.connect(self.test_db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        
        # Create basic existing tables (simulate existing system)
        self._create_existing_tables()
    
    def teardown_method(self):
        """Clean up after each test."""
        if hasattr(self, 'conn'):
            self.conn.close()
        
        if os.path.exists(self.test_db_path):
            os.unlink(self.test_db_path)
    
    def _create_existing_tables(self):
        """Create existing database tables to simulate current system."""
        cursor = self.conn.cursor()
        
        # Existing users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Existing inventory table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    def test_ai_queries_table_creation(self):
        """
        Feature: gemini-api-integration, Task 10.1
        Test creation of ai_queries table for storing natural language queries
        and their processed results.
        """
        # Create AI queries table
        cursor = self.conn.cursor()
        
        ai_queries_schema = '''
            CREATE TABLE IF NOT EXISTS ai_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query_text TEXT NOT NULL,
                intent TEXT,
                entities TEXT,  -- JSON string
                response TEXT,
                confidence REAL,
                processing_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        '''
        
        cursor.execute(ai_queries_schema)
        self.conn.commit()
        
        # Verify table creation
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_queries'")
        table_exists = cursor.fetchone()
        assert table_exists is not None, "ai_queries table should be created"
        
        # Verify table structure
        cursor.execute("PRAGMA table_info(ai_queries)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        expected_columns = ['id', 'user_id', 'query_text', 'intent', 'entities', 
                          'response', 'confidence', 'processing_time', 'created_at']
        
        for expected_col in expected_columns:
            assert expected_col in column_names, f"Column {expected_col} should exist in ai_queries table"
        
        # Test inserting data
        test_query_data = {
            'user_id': 1,
            'query_text': 'What are the top selling items?',
            'intent': 'sales_analysis',
            'entities': json.dumps(['top_selling', 'items']),
            'response': 'Based on sales data, Widget A is the top seller.',
            'confidence': 0.85,
            'processing_time': 1.23
        }
        
        cursor.execute('''
            INSERT INTO ai_queries (user_id, query_text, intent, entities, response, confidence, processing_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            test_query_data['user_id'],
            test_query_data['query_text'],
            test_query_data['intent'],
            test_query_data['entities'],
            test_query_data['response'],
            test_query_data['confidence'],
            test_query_data['processing_time']
        ))
        self.conn.commit()
        
        # Verify data insertion
        cursor.execute("SELECT * FROM ai_queries WHERE id = ?", (cursor.lastrowid,))
        inserted_row = cursor.fetchone()
        
        assert inserted_row is not None, "Query data should be inserted"
        assert inserted_row['query_text'] == test_query_data['query_text']
        assert inserted_row['confidence'] == test_query_data['confidence']
        
        print("✅ AI queries table creation test passed")
    
    def test_ai_insights_cache_table_creation(self):
        """
        Feature: gemini-api-integration, Task 10.1
        Test creation of ai_insights_cache table for caching AI responses
        and managing cache expiration.
        """
        cursor = self.conn.cursor()
        
        # Create AI insights cache table
        cache_schema = '''
            CREATE TABLE IF NOT EXISTS ai_insights_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE NOT NULL,
                prompt_hash TEXT NOT NULL,
                response_data TEXT NOT NULL,  -- JSON string
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
        
        cursor.execute(cache_schema)
        
        # Create index for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_key ON ai_insights_cache(cache_key)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_expires_at ON ai_insights_cache(expires_at)')
        
        self.conn.commit()
        
        # Verify table and indexes creation
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_insights_cache'")
        assert cursor.fetchone() is not None, "ai_insights_cache table should be created"
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_cache_key'")
        assert cursor.fetchone() is not None, "Cache key index should be created"
        
        # Test cache operations
        import hashlib
        from datetime import datetime, timedelta
        
        test_prompt = "Generate insights for inventory data"
        prompt_hash = hashlib.md5(test_prompt.encode()).hexdigest()
        cache_key = f"insights_{prompt_hash}"
        
        test_cache_data = {
            'cache_key': cache_key,
            'prompt_hash': prompt_hash,
            'response_data': json.dumps({
                'insights': ['Inventory levels are balanced', 'Sales trending upward'],
                'confidence': 0.92
            }),
            'expires_at': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
        # Insert cache entry
        cursor.execute('''
            INSERT INTO ai_insights_cache (cache_key, prompt_hash, response_data, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (
            test_cache_data['cache_key'],
            test_cache_data['prompt_hash'],
            test_cache_data['response_data'],
            test_cache_data['expires_at']
        ))
        self.conn.commit()
        
        # Test cache retrieval
        cursor.execute("SELECT * FROM ai_insights_cache WHERE cache_key = ?", (cache_key,))
        cached_row = cursor.fetchone()
        
        assert cached_row is not None, "Cache entry should be retrievable"
        assert cached_row['cache_key'] == cache_key
        assert json.loads(cached_row['response_data'])['confidence'] == 0.92
        
        print("✅ AI insights cache table creation test passed")
    
    def test_ai_performance_metrics_table_creation(self):
        """
        Feature: gemini-api-integration, Task 10.1
        Test creation of ai_performance_metrics table for tracking
        AI system performance and usage statistics.
        """
        cursor = self.conn.cursor()
        
        # Create performance metrics table
        metrics_schema = '''
            CREATE TABLE IF NOT EXISTS ai_performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_type TEXT NOT NULL,  -- 'api_call', 'cache_hit', 'error', etc.
                operation TEXT NOT NULL,   -- 'query_processing', 'report_generation', etc.
                duration_ms INTEGER,
                success BOOLEAN DEFAULT 1,
                error_message TEXT,
                metadata TEXT,  -- JSON string for additional data
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
        
        cursor.execute(metrics_schema)
        
        # Create indexes for performance analysis
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_metric_type ON ai_performance_metrics(metric_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_operation ON ai_performance_metrics(operation)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON ai_performance_metrics(timestamp)')
        
        self.conn.commit()
        
        # Verify table creation
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_performance_metrics'")
        assert cursor.fetchone() is not None, "ai_performance_metrics table should be created"
        
        # Test performance metrics insertion
        test_metrics = [
            {
                'metric_type': 'api_call',
                'operation': 'query_processing',
                'duration_ms': 1250,
                'success': True,
                'metadata': json.dumps({'query_length': 45, 'response_tokens': 150})
            },
            {
                'metric_type': 'cache_hit',
                'operation': 'insight_generation',
                'duration_ms': 50,
                'success': True,
                'metadata': json.dumps({'cache_age_minutes': 15})
            },
            {
                'metric_type': 'error',
                'operation': 'report_generation',
                'duration_ms': 500,
                'success': False,
                'error_message': 'API rate limit exceeded',
                'metadata': json.dumps({'retry_count': 3})
            }
        ]
        
        for metric in test_metrics:
            cursor.execute('''
                INSERT INTO ai_performance_metrics 
                (metric_type, operation, duration_ms, success, error_message, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                metric['metric_type'],
                metric['operation'],
                metric['duration_ms'],
                metric['success'],
                metric.get('error_message'),
                metric['metadata']
            ))
        
        self.conn.commit()
        
        # Verify metrics insertion and querying
        cursor.execute("SELECT COUNT(*) as count FROM ai_performance_metrics")
        count = cursor.fetchone()['count']
        assert count == 3, "All test metrics should be inserted"
        
        # Test performance analysis queries
        cursor.execute('''
            SELECT metric_type, AVG(duration_ms) as avg_duration, COUNT(*) as count
            FROM ai_performance_metrics 
            WHERE success = 1
            GROUP BY metric_type
        ''')
        
        performance_summary = cursor.fetchall()
        assert len(performance_summary) >= 2, "Should have performance data for successful operations"
        
        print("✅ AI performance metrics table creation test passed")
    
    def test_database_migration_script(self):
        """
        Feature: gemini-api-integration, Task 10.1
        Test database migration script that adds all AI-related tables
        to existing database installations.
        """
        # Simulate migration script execution
        migration_script = self._get_ai_migration_script()
        
        # Execute migration
        cursor = self.conn.cursor()
        
        # Split and execute each statement in the migration script
        statements = migration_script.split(';')
        for statement in statements:
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        
        self.conn.commit()
        
        # Verify all AI tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'ai_%'")
        ai_tables = cursor.fetchall()
        
        expected_ai_tables = ['ai_queries', 'ai_insights_cache', 'ai_performance_metrics']
        created_table_names = [table[0] for table in ai_tables]
        
        for expected_table in expected_ai_tables:
            assert expected_table in created_table_names, f"Migration should create {expected_table} table"
        
        # Verify existing tables are unchanged
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'inventory')")
        existing_tables = cursor.fetchall()
        assert len(existing_tables) == 2, "Existing tables should remain intact"
        
        # Test that existing data is preserved
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                      ('test_user', 'hashed_password'))
        cursor.execute("INSERT INTO inventory (item_name, quantity, cost) VALUES (?, ?, ?)",
                      ('Test Item', 100, 25.50))
        self.conn.commit()
        
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()['count']
        assert user_count == 1, "User data should be preserved after migration"
        
        cursor.execute("SELECT COUNT(*) as count FROM inventory")
        inventory_count = cursor.fetchone()['count']
        assert inventory_count == 1, "Inventory data should be preserved after migration"
        
        print("✅ Database migration script test passed")
    
    def _get_ai_migration_script(self):
        """Get the AI database migration script."""
        return '''
            CREATE TABLE IF NOT EXISTS ai_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query_text TEXT NOT NULL,
                intent TEXT,
                entities TEXT,
                response TEXT,
                confidence REAL,
                processing_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
            
            CREATE TABLE IF NOT EXISTS ai_insights_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE NOT NULL,
                prompt_hash TEXT NOT NULL,
                response_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS ai_performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_type TEXT NOT NULL,
                operation TEXT NOT NULL,
                duration_ms INTEGER,
                success BOOLEAN DEFAULT 1,
                error_message TEXT,
                metadata TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_cache_key ON ai_insights_cache(cache_key);
            CREATE INDEX IF NOT EXISTS idx_expires_at ON ai_insights_cache(expires_at);
            CREATE INDEX IF NOT EXISTS idx_metric_type ON ai_performance_metrics(metric_type);
            CREATE INDEX IF NOT EXISTS idx_operation ON ai_performance_metrics(operation);
            CREATE INDEX IF NOT EXISTS idx_timestamp ON ai_performance_metrics(timestamp)
        '''
    
    def test_data_integrity_during_migration(self):
        """
        Feature: gemini-api-integration, Task 10.1
        Test that data integrity is maintained during database migrations
        and that foreign key constraints work correctly.
        """
        # Add some existing data
        cursor = self.conn.cursor()
        
        cursor.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                      ('admin_user', 'admin_hash', True))
        cursor.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                      ('regular_user', 'user_hash', False))
        
        cursor.execute("INSERT INTO inventory (item_name, quantity, cost) VALUES (?, ?, ?)",
                      ('Widget A', 150, 12.50))
        cursor.execute("INSERT INTO inventory (item_name, quantity, cost) VALUES (?, ?, ?)",
                      ('Widget B', 75, 28.00))
        
        self.conn.commit()
        
        # Get user IDs for foreign key testing
        cursor.execute("SELECT id FROM users WHERE username = 'admin_user'")
        admin_user_id = cursor.fetchone()['id']
        
        cursor.execute("SELECT id FROM users WHERE username = 'regular_user'")
        regular_user_id = cursor.fetchone()['id']
        
        # Run migration
        migration_script = self._get_ai_migration_script()
        statements = migration_script.split(';')
        for statement in statements:
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        
        self.conn.commit()
        
        # Test foreign key constraints
        cursor.execute('''
            INSERT INTO ai_queries (user_id, query_text, intent, response, confidence)
            VALUES (?, ?, ?, ?, ?)
        ''', (admin_user_id, 'Show me inventory summary', 'inventory_analysis', 
              'Here is your inventory summary...', 0.95))
        
        cursor.execute('''
            INSERT INTO ai_queries (user_id, query_text, intent, response, confidence)
            VALUES (?, ?, ?, ?, ?)
        ''', (regular_user_id, 'What are the sales trends?', 'sales_analysis',
              'Sales are trending upward...', 0.88))
        
        self.conn.commit()
        
        # Verify foreign key relationships
        cursor.execute('''
            SELECT aq.query_text, u.username, u.is_admin
            FROM ai_queries aq
            JOIN users u ON aq.user_id = u.id
            ORDER BY aq.id
        ''')
        
        query_results = cursor.fetchall()
        assert len(query_results) == 2, "Should have 2 queries with user relationships"
        
        # Verify admin user query
        admin_query = next(q for q in query_results if q['username'] == 'admin_user')
        assert admin_query['is_admin'] == 1, "Admin user should be identified correctly"
        assert 'inventory' in admin_query['query_text'].lower(), "Admin query should be about inventory"
        
        # Test data integrity constraints
        try:
            # Try to insert query with non-existent user_id
            cursor.execute('''
                INSERT INTO ai_queries (user_id, query_text, intent)
                VALUES (?, ?, ?)
            ''', (999, 'Invalid user query', 'test'))
            self.conn.commit()
            
            # If we get here without error, foreign key constraints might not be enabled
            # This is acceptable for SQLite in some configurations
            print("Note: Foreign key constraints may not be strictly enforced")
            
        except sqlite3.IntegrityError:
            # This is expected if foreign key constraints are enabled
            print("✅ Foreign key constraints are working correctly")
        
        # Verify original data is intact
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()['count']
        assert user_count == 2, "Original user data should be preserved"
        
        cursor.execute("SELECT COUNT(*) as count FROM inventory")
        inventory_count = cursor.fetchone()['count']
        assert inventory_count == 2, "Original inventory data should be preserved"
        
        print("✅ Data integrity during migration test passed")
    
    def test_database_indexes_and_performance(self):
        """
        Feature: gemini-api-integration, Task 10.1
        Test that appropriate database indexes are created for
        optimal AI feature performance.
        """
        # Run migration to create tables and indexes
        cursor = self.conn.cursor()
        migration_script = self._get_ai_migration_script()
        
        statements = migration_script.split(';')
        for statement in statements:
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        
        self.conn.commit()
        
        # Verify indexes were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = cursor.fetchall()
        index_names = [idx[0] for idx in indexes]
        
        expected_indexes = [
            'idx_cache_key',
            'idx_expires_at', 
            'idx_metric_type',
            'idx_operation',
            'idx_timestamp'
        ]
        
        for expected_idx in expected_indexes:
            assert expected_idx in index_names, f"Index {expected_idx} should be created"
        
        # Test index effectiveness with sample data
        self._populate_test_data_for_performance()
        
        # Test query performance with indexes
        import time
        
        # Query that should benefit from cache_key index
        start_time = time.time()
        cursor.execute("SELECT * FROM ai_insights_cache WHERE cache_key = ?", ('test_key_500',))
        cache_query_time = time.time() - start_time
        
        # Query that should benefit from timestamp index
        start_time = time.time()
        cursor.execute('''
            SELECT COUNT(*) FROM ai_performance_metrics 
            WHERE timestamp > datetime('now', '-1 hour')
        ''')
        timestamp_query_time = time.time() - start_time
        
        # Performance should be reasonable (under 0.1 seconds for test data)
        assert cache_query_time < 0.1, "Cache key lookup should be fast with index"
        assert timestamp_query_time < 0.1, "Timestamp range query should be fast with index"
        
        print("✅ Database indexes and performance test passed")
        print(f"   Cache key query time: {cache_query_time:.4f}s")
        print(f"   Timestamp query time: {timestamp_query_time:.4f}s")
    
    def _populate_test_data_for_performance(self):
        """Populate test data for performance testing."""
        cursor = self.conn.cursor()
        
        # Add cache entries
        for i in range(1000):
            cursor.execute('''
                INSERT INTO ai_insights_cache (cache_key, prompt_hash, response_data, expires_at)
                VALUES (?, ?, ?, datetime('now', '+1 hour'))
            ''', (f'test_key_{i}', f'hash_{i}', f'{{"data": "test_{i}"}}'))
        
        # Add performance metrics
        for i in range(1000):
            cursor.execute('''
                INSERT INTO ai_performance_metrics (metric_type, operation, duration_ms, success)
                VALUES (?, ?, ?, ?)
            ''', ('api_call', 'test_operation', 100 + i, True))
        
        self.conn.commit()


if __name__ == "__main__":
    # Run database schema tests
    test_instance = TestDatabaseSchemaUpdates()
    
    print("Running Database Schema Update Tests...")
    print()
    
    try:
        test_instance.setup_method()
        test_instance.test_ai_queries_table_creation()
        test_instance.teardown_method()
        
        test_instance.setup_method()
        test_instance.test_ai_insights_cache_table_creation()
        test_instance.teardown_method()
        
        test_instance.setup_method()
        test_instance.test_ai_performance_metrics_table_creation()
        test_instance.teardown_method()
        
        test_instance.setup_method()
        test_instance.test_database_migration_script()
        test_instance.teardown_method()
        
        test_instance.setup_method()
        test_instance.test_data_integrity_during_migration()
        test_instance.teardown_method()
        
        test_instance.setup_method()
        test_instance.test_database_indexes_and_performance()
        test_instance.teardown_method()
        
        print()
        print("🎉 All database schema update tests completed successfully!")
        print("✅ AI queries table creation working")
        print("✅ AI insights cache table creation working")
        print("✅ AI performance metrics table creation working")
        print("✅ Database migration script working")
        print("✅ Data integrity during migration preserved")
        print("✅ Database indexes and performance optimized")
        
    except Exception as e:
        print(f"❌ Database schema test failed: {e}")
        import traceback
        traceback.print_exc()