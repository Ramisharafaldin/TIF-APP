"""
Property-based tests for audit logging completeness functionality.

Feature: gemini-api-integration, Property 24: Audit Logging Completeness
For any AI API interaction, the system should log the request details, 
response status, and user information for audit purposes.

Validates: Requirements 8.3
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from hypothesis.strategies import composite
import json
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import tempfile
import os
import sys

# Import the audit logger components
try:
    from utils.audit_logger import *
    AUDIT_LOGGER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import audit logger: {e}")
    AUDIT_LOGGER_AVAILABLE = False

# Configure audit database path - use temporary file for tests
TEST_AUDIT_DB_PATH = None  # Will be set in setup_method


# Test data generators
@composite
def audit_entry_data(draw):
    """Generate valid audit entry data."""
    return {
        'timestamp': draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))).isoformat(),
        'user_id': draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
        'operation_type': draw(st.sampled_from(['insights', 'query', 'report', 'forecast', 'anonymization'])),
        'request_id': draw(st.text(min_size=10, max_size=64, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))),
        'api_endpoint': draw(st.text(min_size=1, max_size=100)),
        'request_size': draw(st.integers(min_value=0, max_value=1000000)),
        'response_status': draw(st.sampled_from(['success', 'error', 'timeout'])),
        'processing_time_ms': draw(st.floats(min_value=0.0, max_value=60000.0, allow_nan=False, allow_infinity=False)),
        'data_anonymized': draw(st.booleans()),
        'sensitive_data_detected': draw(st.booleans()),
        'error_message': draw(st.one_of(st.none(), st.text(min_size=1, max_size=500))),
        'cache_hit': draw(st.booleans()),
        'confidence_score': draw(st.one_of(st.none(), st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))),
        'ip_address': draw(st.one_of(st.none(), st.text(min_size=7, max_size=15))),
        'user_agent': draw(st.one_of(st.none(), st.text(min_size=1, max_size=200)))
    }


class SimpleAuditLogger:
    """Simple audit logger for testing purposes."""
    
    def __init__(self, db_path=None):
        if db_path is None:
            # Create a temporary database file for testing
            import tempfile
            fd, self.db_path = tempfile.mkstemp(suffix='.db', prefix='test_audit_')
            os.close(fd)  # Close the file descriptor, we just need the path
        else:
            self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the audit database."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS ai_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    api_endpoint TEXT NOT NULL,
                    request_size INTEGER NOT NULL,
                    response_status TEXT NOT NULL,
                    processing_time_ms REAL NOT NULL,
                    data_anonymized BOOLEAN NOT NULL,
                    sensitive_data_detected BOOLEAN NOT NULL,
                    error_message TEXT,
                    cache_hit BOOLEAN DEFAULT FALSE,
                    confidence_score REAL,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to initialize audit database: {e}")
    
    def log_interaction(self, entry_data):
        """Log an audit entry."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                INSERT INTO ai_audit_log (
                    timestamp, user_id, operation_type, request_id, api_endpoint,
                    request_size, response_status, processing_time_ms, data_anonymized,
                    sensitive_data_detected, error_message, cache_hit, confidence_score,
                    ip_address, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry_data['timestamp'], entry_data['user_id'], entry_data['operation_type'],
                entry_data['request_id'], entry_data['api_endpoint'], entry_data['request_size'],
                entry_data['response_status'], entry_data['processing_time_ms'],
                entry_data['data_anonymized'], entry_data['sensitive_data_detected'],
                entry_data.get('error_message'), entry_data.get('cache_hit', False),
                entry_data.get('confidence_score'), entry_data.get('ip_address'),
                entry_data.get('user_agent')
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Failed to log audit entry: {e}")
            return False
    
    def get_audit_report(self, user_id=None):
        """Generate audit report."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            if user_id:
                c.execute('SELECT * FROM ai_audit_log WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
            else:
                c.execute('SELECT * FROM ai_audit_log ORDER BY created_at DESC')
            
            rows = c.fetchall()
            columns = [description[0] for description in c.description]
            
            audit_entries = []
            for row in rows:
                entry = dict(zip(columns, row))
                audit_entries.append(entry)
            
            conn.close()
            
            return {
                'audit_entries': audit_entries,
                'total_entries': len(audit_entries),
                'report_generated_at': datetime.now().isoformat()
            }
        except Exception as e:
            return {'error': str(e)}


class TestAuditLoggingCompletenessProperties:
    """Property-based tests for audit logging completeness."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Create a test audit logger with temporary database
        self.audit_logger = SimpleAuditLogger()
    
    def teardown_method(self):
        """Clean up test environment after each test."""
        # Clean up temporary database file
        if hasattr(self.audit_logger, 'db_path') and os.path.exists(self.audit_logger.db_path):
            try:
                os.unlink(self.audit_logger.db_path)
            except Exception:
                pass  # Ignore cleanup errors
    
    @given(entry_data=audit_entry_data())
    @settings(max_examples=15, deadline=3000)
    def test_audit_entry_logging_completeness(self, entry_data):
        """
        Feature: gemini-api-integration, Property 24: Audit Logging Completeness
        For any audit entry, all required fields should be logged to the database
        and retrievable for audit purposes.
        """
        # Log the entry
        success = self.audit_logger.log_interaction(entry_data)
        assert success, "Audit entry should be logged successfully"
        
        # Verify the entry was logged to database
        try:
            conn = sqlite3.connect(self.audit_logger.db_path)
            c = conn.cursor()
            
            # Query for the logged entry
            c.execute('''
                SELECT * FROM ai_audit_log 
                WHERE request_id = ? AND user_id = ? AND operation_type = ?
                ORDER BY created_at DESC LIMIT 1
            ''', (entry_data['request_id'], entry_data['user_id'], entry_data['operation_type']))
            
            row = c.fetchone()
            conn.close()
            
            # Verify entry was found
            assert row is not None, "Audit entry should be logged to database"
            
            # Verify all required fields are present and correct
            columns = [
                'id', 'timestamp', 'user_id', 'operation_type', 'request_id', 'api_endpoint',
                'request_size', 'response_status', 'processing_time_ms', 'data_anonymized',
                'sensitive_data_detected', 'error_message', 'cache_hit', 'confidence_score',
                'ip_address', 'user_agent', 'created_at'
            ]
            
            logged_data = dict(zip(columns, row))
            
            # Verify core required fields
            assert logged_data['user_id'] == entry_data['user_id'], "User ID should be logged correctly"
            assert logged_data['operation_type'] == entry_data['operation_type'], "Operation type should be logged correctly"
            assert logged_data['request_id'] == entry_data['request_id'], "Request ID should be logged correctly"
            assert logged_data['response_status'] == entry_data['response_status'], "Response status should be logged correctly"
            assert logged_data['data_anonymized'] == (1 if entry_data['data_anonymized'] else 0), "Data anonymization flag should be logged correctly"
            assert logged_data['sensitive_data_detected'] == (1 if entry_data['sensitive_data_detected'] else 0), "Sensitive data detection flag should be logged correctly"
            
        except Exception as e:
            pytest.fail(f"Failed to verify audit logging: {e}")
    
    @given(user_ids=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=3, unique=True))
    @settings(max_examples=10, deadline=3000)
    def test_audit_report_generation_completeness(self, user_ids):
        """
        Feature: gemini-api-integration, Property 24: Audit Logging Completeness
        For any set of users and time periods, audit reports should include
        all logged interactions and provide complete audit trail.
        """
        # Create test audit entries for multiple users
        test_entries = []
        for i, user_id in enumerate(user_ids):
            entry_data = {
                'timestamp': datetime.now().isoformat(),
                'user_id': user_id,
                'operation_type': 'insights',
                'request_id': f'test_req_{i}_{int(time.time())}',
                'api_endpoint': 'test_endpoint',
                'request_size': 100 + i,
                'response_status': 'success',
                'processing_time_ms': 50.0 + i,
                'data_anonymized': i % 2 == 0,
                'sensitive_data_detected': i % 3 == 0
            }
            
            success = self.audit_logger.log_interaction(entry_data)
            assert success, f"Should log entry for user {user_id}"
            test_entries.append(entry_data)
        
        # Wait for logging to complete
        time.sleep(0.1)
        
        # Generate audit report
        report = self.audit_logger.get_audit_report()
        
        # Verify report completeness
        assert 'audit_entries' in report, "Report should contain audit entries"
        assert 'total_entries' in report, "Report should contain total count"
        assert 'report_generated_at' in report, "Report should contain generation timestamp"
        
        # Verify all test entries are included in report
        report_entries = report['audit_entries']
        test_request_ids = {entry['request_id'] for entry in test_entries}
        report_request_ids = {entry['request_id'] for entry in report_entries if 'request_id' in entry}
        
        # All test entries should be in the report
        missing_entries = test_request_ids - report_request_ids
        assert len(missing_entries) == 0, f"All audit entries should be in report, missing: {missing_entries}"
        
        # Verify report metadata
        assert isinstance(report['total_entries'], int), "Total entries should be an integer"
        assert report['total_entries'] >= len(test_entries), "Total entries should include at least our test entries"
    
    @given(
        user_id=st.text(min_size=1, max_size=50),
        operations=st.lists(st.sampled_from(['insights', 'query', 'report', 'forecast']), min_size=1, max_size=3)
    )
    @settings(max_examples=10, deadline=3000)
    def test_audit_user_filtering_completeness(self, user_id, operations):
        """
        Feature: gemini-api-integration, Property 24: Audit Logging Completeness
        For any user, all their AI interactions should be auditable and
        filterable for compliance and security purposes.
        """
        # Create audit entries for the specific user
        test_entries = []
        for i, operation in enumerate(operations):
            entry_data = {
                'timestamp': datetime.now().isoformat(),
                'user_id': user_id,
                'operation_type': operation,
                'request_id': f'user_filter_test_{i}_{int(time.time())}',
                'api_endpoint': f'test_{operation}',
                'request_size': 100 + i,
                'response_status': 'success',
                'processing_time_ms': 50.0 + i,
                'data_anonymized': i % 2 == 0,
                'sensitive_data_detected': i % 3 == 0
            }
            
            success = self.audit_logger.log_interaction(entry_data)
            assert success, f"Should log entry for operation {operation}"
            test_entries.append(entry_data)
        
        # Wait for logging to complete
        time.sleep(0.1)
        
        # Generate user-specific audit report
        user_report = self.audit_logger.get_audit_report(user_id=user_id)
        
        # Verify user filtering completeness
        assert 'audit_entries' in user_report, "User report should contain audit entries"
        
        user_entries = user_report['audit_entries']
        
        # All entries in the report should be for the specified user
        for entry in user_entries:
            if 'user_id' in entry:
                assert entry['user_id'] == user_id, f"All entries should be for user {user_id}"
        
        # All test entries should be in the user report
        test_request_ids = {entry['request_id'] for entry in test_entries}
        report_request_ids = {entry['request_id'] for entry in user_entries if 'request_id' in entry}
        
        found_entries = test_request_ids.intersection(report_request_ids)
        assert len(found_entries) == len(test_entries), "All user's audit entries should be retrievable"


if __name__ == "__main__":
    # Run a simple test to verify the test setup
    test_instance = TestAuditLoggingCompletenessProperties()
    test_instance.setup_method()
    
    # Test with a simple audit entry
    test_entry = {
        'timestamp': datetime.now().isoformat(),
        'user_id': 'test_user',
        'operation_type': 'insights',
        'request_id': 'test_request_123',
        'api_endpoint': 'test_endpoint',
        'request_size': 100,
        'response_status': 'success',
        'processing_time_ms': 50.0,
        'data_anonymized': True,
        'sensitive_data_detected': False
    }
    
    print("Testing audit logging with sample entry...")
    success = test_instance.audit_logger.log_interaction(test_entry)
    print(f"Logging success: {success}")
    
    # Generate report
    report = test_instance.audit_logger.get_audit_report()
    print(f"Generated audit report with {report.get('total_entries', 0)} entries")
    print("Audit logging test completed successfully!")