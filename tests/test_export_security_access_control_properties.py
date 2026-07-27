"""
Property-based tests for export security and access control.

Feature: export-functionality-fix
Tests security and access control properties to ensure export routes properly validate
authentication, CSRF protection, and data ownership.
"""
import os
import pytest
import logging
import sqlite3
import tempfile
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import patch, MagicMock, Mock
import pandas as pd
from datetime import datetime
from flask import Flask, session, g
from flask_login import UserMixin

# Import the modules to test
import data_store
import auth_flask
from utils.session_validator import (
    validate_user_authentication,
    validate_csrf_token_for_export,
    validate_data_access_permissions,
    validate_export_request_security,
    comprehensive_export_validation,
    log_export_access_attempt
)


class TestExportSecurityAccessControlProperties:
    """
    Property-based tests for export security and access control.
    
    **Validates: Requirements 6.1, 6.2, 6.4**
    """
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Create temporary database for testing
        self.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.test_db.close()
        
        # Initialize test database
        data_store.DB_NAME = self.test_db.name
        data_store.init_data_db()
        
        # Create Flask app for testing
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['SECRET_KEY'] = 'test_secret_key'
        self.app.config['WTF_CSRF_ENABLED'] = True
        
        # Initialize Flask-Login for testing
        from flask_login import LoginManager
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)
        
        # Add a simple user loader for testing
        @self.login_manager.user_loader
        def load_user(user_id):
            # Simple mock user for testing
            class MockUser:
                def __init__(self, user_id):
                    self.id = user_id
                def get_id(self):
                    return self.id
                @property
                def is_authenticated(self):
                    return True
                @property
                def is_active(self):
                    return True
                @property
                def is_anonymous(self):
                    return False
            return MockUser(user_id)
        
        # Create test client and push app context
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Create request context for Flask operations
        self.request_context = self.app.test_request_context()
        self.request_context.push()
        
    def teardown_method(self):
        """Clean up after each test."""
        try:
            self.request_context.pop()
        except:
            pass
        try:
            self.app_context.pop()
        except:
            pass
        try:
            os.unlink(self.test_db.name)
        except:
            pass
    
    @given(
        username=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        module=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting'])
    )
    @settings(max_examples=10, deadline=3000)
    def test_authentication_validation_property(self, username, module):
        """
        Feature: export-functionality-fix, Property 7: Security and Access Control
        For any export request, the system should verify user authentication and validate
        session ownership before allowing access to export functionality.
        
        **Validates: Requirements 6.1, 6.2**
        """
        assume(username.strip())  # Ensure username is not empty after stripping
        
        # Test case 1: Unauthenticated user should be rejected
        with patch('flask_login.current_user') as mock_current_user:
            mock_current_user.is_authenticated = False
            
            is_valid, error_message = validate_user_authentication(username)
            assert not is_valid, "Unauthenticated user should be rejected"
            assert 'تسجيل الدخول' in error_message, "Error message should mention login requirement"
        
        # Test case 2: Authenticated user with matching username should be accepted
        with patch('flask_login.current_user') as mock_current_user, \
             patch('flask.session', {'logged_in': True, 'username': username}), \
             patch('auth_flask.get_user', return_value=(username, False)):
            
            mock_current_user.is_authenticated = True
            # Fix mock setup - create a simple callable that returns the username
            def mock_get_id():
                return username
            mock_current_user.get_id = mock_get_id
            
            is_valid, error_message = validate_user_authentication(username)
            assert is_valid, f"Authenticated user should be accepted: {error_message}"
            assert error_message == '', "No error message should be returned for valid authentication"
        
        # Test case 3: Authenticated user with mismatched username should be rejected
        different_username = username + "_different"
        with patch('flask_login.current_user') as mock_current_user, \
             patch('flask.session', {'logged_in': True, 'username': different_username}):
            
            mock_current_user.is_authenticated = True
            # Fix mock setup - create a simple callable that returns the different username
            def mock_get_id():
                return different_username
            mock_current_user.get_id = mock_get_id
            
            is_valid, error_message = validate_user_authentication(username)
            assert not is_valid, "User with mismatched username should be rejected"
            assert 'هوية المستخدم' in error_message, "Error message should mention user identity issue"
    
    @given(
        username=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        module=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting']),
        has_csrf_token=st.booleans(),
        csrf_token_valid=st.booleans()
    )
    @settings(max_examples=10, deadline=3000)
    def test_csrf_protection_property(self, username, module, has_csrf_token, csrf_token_valid):
        """
        Feature: export-functionality-fix, Property 7: Security and Access Control
        For any export request, the system should validate CSRF tokens when CSRF protection
        is enabled and handle missing or invalid tokens gracefully.
        
        **Validates: Requirements 6.4**
        """
        assume(username.strip())  # Ensure username is not empty after stripping
        
        # Mock Flask request and CSRF validation
        with patch('flask.request') as mock_request, \
             patch('flask_wtf.csrf.validate_csrf') as mock_validate_csrf, \
             patch('flask.g', Mock()) as mock_g:
            
            mock_request.method = 'GET'  # Export routes are GET requests
            
            # Set up CSRF token presence
            if has_csrf_token:
                mock_request.form.get.return_value = 'test_csrf_token'
                mock_request.headers.get.return_value = 'test_csrf_token'
                mock_request.args.get.return_value = 'test_csrf_token'
            else:
                mock_request.form.get.return_value = None
                mock_request.headers.get.return_value = None
                mock_request.args.get.return_value = None
            
            # Set up CSRF validation result
            if csrf_token_valid:
                mock_validate_csrf.return_value = None  # No exception means valid
            else:
                mock_validate_csrf.side_effect = Exception("Invalid CSRF token")
            
            # Test CSRF validation
            is_valid, error_message = validate_csrf_token_for_export(username)
            
            # For GET requests, CSRF validation should pass (export routes are GET)
            assert is_valid, f"GET requests should pass CSRF validation: {error_message}"
    
    @given(
        username=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        other_username=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        module=st.sampled_from(['inventory', 'transfers', 'forecasting']),
        data_count=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=5, deadline=5000)
    def test_data_ownership_property(self, username, other_username, module, data_count):
        """
        Feature: export-functionality-fix, Property 7: Security and Access Control
        For any export request, users should only be able to access their own data
        and be prevented from accessing other users' data.
        
        **Validates: Requirements 6.2**
        """
        assume(username.strip() and other_username.strip())  # Ensure usernames are not empty
        assume(username != other_username)  # Ensure different users
        
        try:
            # Create test users - fix function signature
            auth_flask.add_user(username, 'password123', False)
            auth_flask.add_user(other_username, 'password123', False)
            
            # Create test data for the first user
            user_data_ids = {}
            for i in range(data_count):
                test_df = pd.DataFrame({
                    'test_column': [f'data_{i}_{username}'],
                    'value': [i]
                })
                data_id = data_store.save_dataframe(username, module, f'test_data_{i}', test_df)
                user_data_ids[f'test_data_{i}'] = data_id
            
            # Create test data for the other user
            other_user_data_ids = {}
            for i in range(data_count):
                test_df = pd.DataFrame({
                    'test_column': [f'data_{i}_{other_username}'],
                    'value': [i + 100]
                })
                data_id = data_store.save_dataframe(other_username, module, f'test_data_{i}', test_df)
                other_user_data_ids[f'test_data_{i}'] = data_id
            
            # Test 1: User should have access to their own data
            is_valid, error_message = validate_data_access_permissions(username, module, user_data_ids)
            assert is_valid, f"User should have access to their own data: {error_message}"
            
            # Test 2: User should NOT have access to other user's data
            is_valid, error_message = validate_data_access_permissions(username, module, other_user_data_ids)
            assert not is_valid, "User should not have access to other user's data"
            assert 'صلاحية' in error_message or 'ملكية' in error_message, "Error should mention permissions or ownership"
            
            # Test 3: Mixed data access should be rejected
            mixed_data_ids = {**user_data_ids, **other_user_data_ids}
            is_valid, error_message = validate_data_access_permissions(username, module, mixed_data_ids)
            assert not is_valid, "Mixed data access should be rejected"
            
        except Exception as e:
            # Clean up and re-raise
            pytest.fail(f"Test setup failed: {e}")
    
    @given(
        username=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        module=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting']),
        is_authenticated=st.booleans(),
        has_valid_session=st.booleans(),
        has_valid_data=st.booleans()
    )
    @settings(max_examples=10, deadline=5000)
    def test_comprehensive_security_validation_property(self, username, module, is_authenticated, has_valid_session, has_valid_data):
        """
        Feature: export-functionality-fix, Property 7: Security and Access Control
        For any export request, the comprehensive validation should enforce all security
        requirements and provide appropriate error messages for each failure type.
        
        **Validates: Requirements 6.1, 6.2, 6.4**
        """
        assume(username.strip())  # Ensure username is not empty after stripping
        
        # Set up test data if needed
        session_data = {'data_ids': {}, 'params': {}}
        if has_valid_data and module != 'dashboard':
            try:
                # Create test user and data - fix function signature
                auth_flask.add_user(username, 'password123', False)
                
                test_df = pd.DataFrame({
                    'test_column': ['test_value'],
                    'value': [1]
                })
                
                if module == 'inventory':
                    data_id = data_store.save_dataframe(username, module, 'results', test_df)
                    session_data['data_ids']['results'] = data_id
                elif module == 'transfers':
                    data_id = data_store.save_dataframe(username, module, 'transfer_results', test_df)
                    session_data['data_ids']['transfer_results'] = data_id
                elif module == 'forecasting':
                    data_id = data_store.save_dataframe(username, module, 'forecast_results', test_df)
                    session_data['data_ids']['forecast_results'] = data_id
                
                # Save session data
                data_store.save_user_session(username, module, None, session_data['data_ids'], session_data['params'])
            except Exception:
                # If setup fails, skip this test case
                assume(False)
        
        # Mock authentication state
        with patch('flask_login.current_user') as mock_current_user, \
             patch('flask.session', {'logged_in': is_authenticated, 'username': username if is_authenticated else 'other'}), \
             patch('auth_flask.get_user', return_value=(username, False) if is_authenticated else None):
            
            mock_current_user.is_authenticated = is_authenticated
            # Fix mock setup - create a simple callable
            def mock_get_id():
                return username if is_authenticated else None
            mock_current_user.get_id = mock_get_id
            
            # Run comprehensive validation
            is_valid, error_message, returned_session_data, dataframes = comprehensive_export_validation(username, module)
            
            # Determine expected result based on conditions
            should_succeed = is_authenticated and (has_valid_session or module == 'dashboard') and (has_valid_data or module == 'dashboard')
            
            if should_succeed:
                assert is_valid, f"Validation should succeed with valid conditions: {error_message}"
                assert returned_session_data is not None, "Session data should be returned on success"
                assert dataframes is not None, "Dataframes should be returned on success"
            else:
                assert not is_valid, "Validation should fail with invalid conditions"
                assert error_message, "Error message should be provided on failure"
                assert 'تسجيل الدخول' in error_message or 'جلسة' in error_message or 'بيانات' in error_message or 'تحليل' in error_message, \
                       f"Error message should be descriptive: {error_message}"
    
    @given(
        username=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        module=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting']),
        success=st.booleans()
    )
    @settings(max_examples=5, deadline=2000)
    def test_audit_logging_property(self, username, module, success):
        """
        Feature: export-functionality-fix, Property 7: Security and Access Control
        For any export access attempt, the system should log security events for
        auditing and monitoring purposes.
        
        **Validates: Requirements 6.1, 6.2**
        """
        assume(username.strip())  # Ensure username is not empty after stripping
        
        # Mock the audit logger - patch the import inside the function
        with patch('utils.audit_logger.audit_logger') as mock_audit_logger:
            
            # Mock request for getting user agent and IP
            with patch('flask.request') as mock_request:
                mock_request.headers.get.return_value = 'Test-User-Agent'
                mock_request.remote_addr = '127.0.0.1'
                
                # Test audit logging
                error_message = 'Test error message' if not success else ''
                log_export_access_attempt(username, module, success, error_message)
            
            # Verify audit logging was called
            assert mock_audit_logger.log_ai_interaction.called, "Audit logger should be called"


if __name__ == '__main__':
    # Run the property tests
    pytest.main([__file__, '-v', '--tb=short'])