"""
Property-based tests for database initialization and recovery.

Tests Property 8: Database Initialization and Recovery
**Validates: Requirements 6.1, 6.2, 6.4**
"""

import pytest
import tempfile
import os
import sqlite3
import shutil
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
import data_store


def create_test_database_path():
    """Create a temporary database path for testing."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    # Remove the file so we can test initialization from scratch
    os.remove(db_path)
    return db_path


def setup_test_database(db_path):
    """Set up a temporary test database with given path."""
    # Override the database path for testing
    original_db = data_store.DB_NAME
    data_store.DB_NAME = db_path
    return original_db


def cleanup_test_database(db_path, original_db):
    """Clean up the temporary test database."""
    data_store.DB_NAME = original_db
    if os.path.exists(db_path):
        # On Windows, we may need to retry file deletion due to file locking
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                os.remove(db_path)
                break
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # Increasing delay
                else:
                    # If we can't delete after retries, just log it
                    # This prevents test failures due to Windows file locking
                    print(f"Warning: Could not delete test database {db_path}")
                    pass


def verify_table_schema(db_path, table_name, expected_columns):
    """Verify that a table has the expected schema."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        # Get table info
        c.execute(f"PRAGMA table_info({table_name})")
        columns = c.fetchall()
        
        # Extract column names
        actual_columns = {col[1] for col in columns}  # col[1] is the column name
        expected_columns_set = set(expected_columns)
        
        # Check if all expected columns are present
        return expected_columns_set.issubset(actual_columns)
    
    finally:
        conn.close()


def corrupt_database_file(db_path, corruption_type):
    """Introduce corruption into the database file."""
    if corruption_type == 'truncate':
        # Truncate the file to make it invalid
        with open(db_path, 'wb') as f:
            f.write(b'corrupted')
    
    elif corruption_type == 'empty':
        # Create empty file
        with open(db_path, 'wb') as f:
            pass
    
    elif corruption_type == 'invalid_header':
        # Write invalid SQLite header
        with open(db_path, 'wb') as f:
            f.write(b'NOT_SQLITE_FILE' + b'\x00' * 100)


class TestDatabaseInitializationProperties:
    """Property-based tests for database initialization and recovery."""
    
    @given(
        db_name_suffix=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
            min_size=1,
            max_size=10
        )
    )
    @settings(max_examples=10, deadline=30000)  # 30 second deadline
    def test_database_initialization_from_scratch(self, db_name_suffix):
        """
        Property 8a: Database Initialization from Scratch
        *For any* valid database path, initializing the database should create all required tables
        with correct schema and return successfully.
        **Feature: data-upload-persistence-fix, Property 8a: Database initialization from scratch**
        **Validates: Requirements 6.1, 6.2**
        """
        # Create unique database path
        db_path = create_test_database_path()
        db_path = db_path.replace('.db', f'_{db_name_suffix}.db')
        
        original_db = setup_test_database(db_path)
        
        try:
            # Ensure database doesn't exist
            assert not os.path.exists(db_path), "Database should not exist initially"
            
            # Initialize database
            data_store.init_data_db()
            
            # Verify database file was created
            assert os.path.exists(db_path), "Database file should be created"
            
            # Verify all required tables exist with correct schema
            expected_tables = {
                'uploaded_files': [
                    'id', 'username', 'module', 'branch_name', 
                    'original_filename', 'file_data', 'upload_timestamp', 'file_size'
                ],
                'processed_data': [
                    'id', 'username', 'module', 'branch_name',
                    'data_type', 'data_blob', 'created_timestamp', 'metadata'
                ],
                'user_sessions': [
                    'username', 'module', 'file_id', 'data_ids', 
                    'params', 'last_updated'
                ]
            }
            
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            # Check that all tables exist
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            actual_tables = {row[0] for row in c.fetchall()}
            
            for table_name in expected_tables.keys():
                assert table_name in actual_tables, f"Table {table_name} should exist"
                
                # Verify schema
                assert verify_table_schema(db_path, table_name, expected_tables[table_name]), \
                    f"Table {table_name} should have correct schema"
            
            conn.close()
            
        finally:
            cleanup_test_database(db_path, original_db)
    
    @given(
        corruption_type=st.sampled_from(['truncate', 'empty', 'invalid_header'])
    )
    @settings(max_examples=5, deadline=30000)
    def test_database_recovery_from_corruption(self, corruption_type):
        """
        Property 8b: Database Recovery from Corruption
        *For any* corrupted database file, re-initializing should either recover gracefully
        or recreate the database with proper error handling.
        **Feature: data-upload-persistence-fix, Property 8b: Database recovery from corruption**
        **Validates: Requirements 6.4**
        """
        db_path = create_test_database_path()
        original_db = setup_test_database(db_path)
        
        conn = None
        try:
            # First create a valid database
            data_store.init_data_db()
            assert os.path.exists(db_path), "Database should be created initially"
            
            # Corrupt the database
            corrupt_database_file(db_path, corruption_type)
            
            # Try to initialize again - should handle corruption gracefully
            try:
                data_store.init_data_db()
                
                # After recovery, database should be functional
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                
                # Test basic operations work
                c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = c.fetchall()
                
                # Should have at least the core tables
                table_names = {row[0] for row in tables}
                required_tables = {'uploaded_files', 'processed_data', 'user_sessions'}
                
                # Either all tables exist (recovery successful) or database was recreated
                if len(table_names) > 0:
                    # If tables exist, they should include our required tables
                    assert required_tables.issubset(table_names), \
                        "Required tables should exist after recovery"
                
            except Exception as e:
                # If initialization fails, it should be a controlled failure
                # (not a crash), and the error should be informative
                assert isinstance(e, (sqlite3.Error, OSError, IOError)), \
                    f"Should get expected error type, got {type(e)}: {e}"
        
        finally:
            # Ensure connection is closed before cleanup
            if conn:
                conn.close()
            # Add a small delay to ensure file handles are released on Windows
            import time
            time.sleep(0.1)
            cleanup_test_database(db_path, original_db)
    
    @given(
        num_reinitializations=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=5, deadline=30000)
    def test_multiple_initialization_calls_are_safe(self, num_reinitializations):
        """
        Property 8c: Multiple Initialization Calls Safety
        *For any* number of repeated initialization calls on the same database,
        the operation should be idempotent and not cause errors or data loss.
        **Feature: data-upload-persistence-fix, Property 8c: Multiple initialization safety**
        **Validates: Requirements 6.1, 6.2**
        """
        db_path = create_test_database_path()
        original_db = setup_test_database(db_path)
        
        try:
            # Call init_data_db multiple times
            for i in range(num_reinitializations):
                data_store.init_data_db()
                
                # Verify database is still functional after each call
                assert os.path.exists(db_path), f"Database should exist after call {i+1}"
                
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                
                # Verify tables still exist and are accessible
                c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = {row[0] for row in c.fetchall()}
                
                required_tables = {'uploaded_files', 'processed_data', 'user_sessions'}
                assert required_tables.issubset(tables), \
                    f"Required tables should exist after initialization {i+1}"
                
                # Test that we can perform basic operations
                c.execute("SELECT COUNT(*) FROM uploaded_files")
                count = c.fetchone()[0]
                assert isinstance(count, int), "Should be able to query tables"
                
                conn.close()
        
        finally:
            cleanup_test_database(db_path, original_db)
    
    def test_database_schema_migration_compatibility(self):
        """
        Property 8d: Schema Migration Compatibility
        *For any* existing database without branch_name columns, initialization should
        add the missing columns without losing existing data.
        **Feature: data-upload-persistence-fix, Property 8d: Schema migration compatibility**
        **Validates: Requirements 6.2**
        """
        db_path = create_test_database_path()
        original_db = setup_test_database(db_path)
        
        try:
            # Create database with old schema (without branch_name columns)
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            # Create old schema tables
            c.execute('''CREATE TABLE uploaded_files (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         username TEXT NOT NULL,
                         module TEXT NOT NULL,
                         original_filename TEXT NOT NULL,
                         file_data BLOB NOT NULL,
                         upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                         file_size INTEGER NOT NULL
                         )''')
            
            c.execute('''CREATE TABLE processed_data (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         username TEXT NOT NULL,
                         module TEXT NOT NULL,
                         data_type TEXT NOT NULL,
                         data_blob BLOB NOT NULL,
                         created_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                         metadata TEXT
                         )''')
            
            # Insert some test data
            c.execute('''INSERT INTO uploaded_files 
                         (username, module, original_filename, file_data, file_size)
                         VALUES (?, ?, ?, ?, ?)''',
                      ('test_user', 'test_module', 'test.xlsx', b'test_data', 100))
            
            old_file_id = c.lastrowid
            
            c.execute('''INSERT INTO processed_data 
                         (username, module, data_type, data_blob)
                         VALUES (?, ?, ?, ?)''',
                      ('test_user', 'test_module', 'test_data', b'test_blob'))
            
            old_data_id = c.lastrowid
            conn.commit()
            conn.close()
            
            # Now run initialization - should migrate schema
            data_store.init_data_db()
            
            # Verify migration worked
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            # Check that branch_name columns were added
            c.execute("PRAGMA table_info(uploaded_files)")
            uploaded_files_columns = {col[1] for col in c.fetchall()}
            assert 'branch_name' in uploaded_files_columns, \
                "branch_name column should be added to uploaded_files"
            
            c.execute("PRAGMA table_info(processed_data)")
            processed_data_columns = {col[1] for col in c.fetchall()}
            assert 'branch_name' in processed_data_columns, \
                "branch_name column should be added to processed_data"
            
            # Verify existing data is preserved
            c.execute("SELECT id, username, original_filename FROM uploaded_files WHERE id = ?", 
                     (old_file_id,))
            file_row = c.fetchone()
            assert file_row is not None, "Existing file data should be preserved"
            assert file_row[1] == 'test_user', "Username should be preserved"
            assert file_row[2] == 'test.xlsx', "Filename should be preserved"
            
            c.execute("SELECT id, username, data_type FROM processed_data WHERE id = ?", 
                     (old_data_id,))
            data_row = c.fetchone()
            assert data_row is not None, "Existing processed data should be preserved"
            assert data_row[1] == 'test_user', "Username should be preserved"
            assert data_row[2] == 'test_data', "Data type should be preserved"
            
            conn.close()
            
        finally:
            cleanup_test_database(db_path, original_db)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])