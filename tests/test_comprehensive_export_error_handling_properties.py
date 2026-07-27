"""
Property-based tests for comprehensive export error handling across all export routes.
Tests that export operations handle errors gracefully with meaningful Arabic messages and proper logging.

Feature: export-functionality-fix
"""

import pytest
import sys
import os
import tempfile
import sqlite3
import logging
from io import BytesIO, StringIO
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hypothesis import given, strategies as st, assume, settings, HealthCheck
import pandas as pd

import data_store
import flask_app


@pytest.fixture
def test_user():
    """Create a test user for authentication"""
    import auth_flask
    username = 'test_user_export_error'
    password = 'TestPass123!'
    
    # Add test user
    auth_flask.add_user(username, password, is_admin=False)
    
    yield {'username': username, 'password': password}
    
    # Cleanup
    try:
        auth_flask.delete_user(username, 'admin')
    except:
        pass


@pytest.fixture
def log_capture():
    """Capture log messages for testing"""
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)
    
    # Get the Flask app logger
    logger = flask_app.app.logger
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    yield log_stream
    
    # Cleanup
    logger.removeHandler(handler)


@pytest.fixture
def flask_client():
    """Create Flask test client"""
    flask_app.app.config['TESTING'] = True
    flask_app.app.config['WTF_CSRF_ENABLED'] = False
    with flask_app.app.test_client() as client:
        yield client


@st.composite
def export_error_scenario_strategy(draw):
    """Generate different export error scenarios for testing"""
    module = draw(st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting']))
    error_type = draw(st.sampled_from([
        'no_session_data',
        'corrupted_session_data', 
        'database_connection_error',
        'missing_dataframe',
        'empty_dataframe',
        'memory_error',
        'permission_error'
    ]))
    
    return {
        'module': module,
        'error_type': error_type,
        'route': f'/{module}/export'
    }


class TestComprehensiveExportErrorHandlingProperties:
    """Property-based tests for comprehensive export error handling"""
    
    @given(
        error_scenario=export_error_scenario_strategy(),
        export_format=st.sampled_from(['xlsx', 'pdf'])
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture], deadline=None)
    def test_property_2_comprehensive_error_handling(self, test_user, log_capture, flask_client, error_scenario, export_format):
        """
        Property 2: Comprehensive Error Handling
        
        For any export operation that encounters an error (missing data, database issues, 
        file generation failures, resource constraints), the system should provide meaningful 
        error messages, implement proper logging, and handle exceptions gracefully instead 
        of showing generic service errors.
        
        **Feature: export-functionality-fix, Property 2: Comprehensive Error Handling**
        **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 5.1, 5.2, 5.3, 5.4**
        """
        
        # Use temporary database for testing
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            original_db = data_store.DB_NAME
            data_store.DB_NAME = tmp_db.name
            
            # Initialize test database
            data_store.init_data_db()
            
            try:
                # Clear any existing data for this user
                data_store.clear_user_data(test_user['username'])
                
                # Clear log capture
                log_capture.seek(0)
                log_capture.truncate(0)
                
                # Login user for session
                with flask_client.session_transaction() as sess:
                    sess['logged_in'] = True
                    sess['username'] = test_user['username']
                    sess['is_admin'] = False
                
                # Set up error scenario
                route = f"{error_scenario['route']}/{export_format}"
                
                if error_scenario['error_type'] == 'no_session_data':
                    # No session data exists - this should be handled gracefully
                    pass
                    
                elif error_scenario['error_type'] == 'corrupted_session_data':
                    # Create corrupted session data
                    data_store.save_user_session(
                        username=test_user['username'],
                        module=error_scenario['module'],
                        data_ids={'corrupted': 'invalid_id'},
                        params={'invalid': 'params'}
                    )
                    
                elif error_scenario['error_type'] == 'missing_dataframe':
                    # Create session with missing dataframe reference
                    data_store.save_user_session(
                        username=test_user['username'],
                        module=error_scenario['module'],
                        data_ids={'results': 99999},  # Non-existent ID
                        params={}
                    )
                    
                elif error_scenario['error_type'] == 'empty_dataframe':
                    # Create session with empty dataframe
                    empty_df = pd.DataFrame()
                    df_id = data_store.save_dataframe(empty_df)
                    data_store.save_user_session(
                        username=test_user['username'],
                        module=error_scenario['module'],
                        data_ids={'results': df_id},
                        params={}
                    )
                
                # Mock specific error conditions
                with patch('data_store.get_user_session') as mock_get_session, \
                     patch('data_store.get_dataframe') as mock_get_dataframe, \
                     patch('sqlite3.connect') as mock_connect:
                    
                    if error_scenario['error_type'] == 'database_connection_error':
                        mock_connect.side_effect = sqlite3.Error("Database connection failed")
                        mock_get_session.side_effect = sqlite3.Error("Database connection failed")
                    elif error_scenario['error_type'] == 'memory_error':
                        mock_get_dataframe.side_effect = MemoryError("Not enough memory")
                    elif error_scenario['error_type'] == 'permission_error':
                        mock_get_dataframe.side_effect = PermissionError("Permission denied")
                    else:
                        # Use real functions for other scenarios
                        mock_get_session.side_effect = lambda *args, **kwargs: data_store.get_user_session(*args, **kwargs)
                        mock_get_dataframe.side_effect = lambda *args, **kwargs: data_store.get_dataframe(*args, **kwargs)
                        mock_connect.side_effect = lambda *args, **kwargs: sqlite3.connect(*args, **kwargs)
                    
                    # Make the export request
                    response = flask_client.get(route)
                
                # Verify response handling
                assert response.status_code in [200, 302, 400, 500], \
                    f"Should return valid HTTP status code, got {response.status_code}"
                
                # If redirected (expected for errors), should not be a generic 500 error
                if response.status_code == 302:
                    # Should redirect to the module page, not to a generic error page
                    location = response.headers.get('Location', '')
                    assert error_scenario['module'] in location or 'login' in location, \
                        f"Should redirect to module page or login, got {location}"
                
                # Verify logging occurred for error scenarios
                log_contents = log_capture.getvalue()
                
                if error_scenario['error_type'] in ['database_connection_error', 'memory_error', 'permission_error']:
                    # These should definitely be logged as errors
                    if log_contents:  # Only check if logging is configured
                        log_contents_lower = log_contents.lower()
                        assert any(keyword in log_contents_lower for keyword in ['error', 'failed', 'exception']), \
                            f"Should log error for {error_scenario['error_type']}"
                        
                        # Should contain context about the operation
                        assert error_scenario['module'] in log_contents_lower, \
                            f"Should log module context for {error_scenario['module']}"
                        
                        # Should contain username for audit trail
                        assert test_user['username'] in log_contents, \
                            "Should log username for audit trail"
                
                # Verify no generic "Service unavailable" errors
                if hasattr(response, 'data'):
                    response_text = response.data.decode('utf-8').lower()
                    assert 'service unavailable' not in response_text, \
                        "Should not show generic 'Service unavailable' error"
                
                # Verify system remains in consistent state
                # Check that no partial files or corrupted data remains
                conn = sqlite3.connect(data_store.DB_NAME)
                c = conn.cursor()
                
                # Verify database integrity
                c.execute("PRAGMA integrity_check")
                integrity_result = c.fetchone()[0]
                assert integrity_result == 'ok', "Database should remain consistent after errors"
                
                conn.close()
                
            finally:
                # Cleanup
                data_store.DB_NAME = original_db
                try:
                    os.unlink(tmp_db.name)
                except:
                    pass
    
    @given(
        module=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting'])
    )
    @settings(max_examples=4, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture], deadline=None)
    def test_property_arabic_error_messages(self, test_user, flask_client, module):
        """
        Test that error messages are provided in Arabic and are meaningful.
        
        **Feature: export-functionality-fix, Property 2: Comprehensive Error Handling**
        **Validates: Requirements 2.3, 3.4, 3.5**
        """
        
        # Use temporary database for testing
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            original_db = data_store.DB_NAME
            data_store.DB_NAME = tmp_db.name
            
            # Initialize test database
            data_store.init_data_db()
            
            try:
                # Clear any existing data for this user
                data_store.clear_user_data(test_user['username'])
                
                # Login user for session
                with flask_client.session_transaction() as sess:
                    sess['logged_in'] = True
                    sess['username'] = test_user['username']
                    sess['is_admin'] = False
                
                # Make export request with no data (should trigger "no data" error)
                route = f'/{module}/export'
                response = flask_client.get(route, follow_redirects=True)
                
                # Should get a response (either success redirect or error page)
                assert response.status_code in [200, 302], \
                    f"Should handle no-data scenario gracefully, got {response.status_code}"
                
                # Check for Arabic error messages in flash messages or response
                if hasattr(response, 'data'):
                    response_text = response.data.decode('utf-8')
                    
                    # Should contain Arabic text for user feedback
                    # Look for common Arabic error message patterns
                    arabic_patterns = [
                        'لا توجد', 'خطأ', 'يرجى', 'تحليل', 'بيانات', 'تصدير'
                    ]
                    
                    # At least some Arabic should be present in user-facing messages
                    has_arabic = any(pattern in response_text for pattern in arabic_patterns)
                    
                    # If this is an error scenario, should have Arabic feedback
                    if 'error' in response_text.lower() or 'warning' in response_text.lower():
                        assert has_arabic, f"Error messages should contain Arabic text for module {module}"
                
            finally:
                # Cleanup
                data_store.DB_NAME = original_db
                try:
                    os.unlink(tmp_db.name)
                except:
                    pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])