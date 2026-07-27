"""
Comprehensive error handling tests for Flask application.
Tests invalid file uploads, unauthorized access, session expiration, and invalid form inputs.
Requirements: 8.1, 8.2, 8.3, 8.4
"""

import pytest
import sys
import os
from io import BytesIO
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask_app import app
import auth_flask


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def logged_in_client(client):
    """Create logged-in test client"""
    username = 'test_error_user'
    password = 'TestPass123!'
    auth_flask.add_user(username, password, is_admin=False)
    
    client.post('/login', data={'username': username, 'password': password})
    
    yield client
    
    auth_flask.delete_user(username, 'admin')


@pytest.fixture
def admin_client(client):
    """Create logged-in admin client"""
    username = 'test_error_admin'
    password = 'AdminPass123!'
    auth_flask.add_user(username, password, is_admin=True)
    
    client.post('/login', data={'username': username, 'password': password})
    
    yield client
    
    auth_flask.delete_user(username, 'admin')


class TestInvalidFileUpload:
    """Test invalid file upload handling - Requirement 8.1"""
    
    def test_upload_csv_file_rejected(self, logged_in_client):
        """Test that CSV files are rejected"""
        csv_data = BytesIO(b'col1,col2\nval1,val2')
        
        response = logged_in_client.post('/inventory/upload', data={
            'file': (csv_data, 'test.csv')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message about invalid file type
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower() or \
               'غير مسموح'.encode('utf-8') in response.data
    
    def test_upload_txt_file_rejected(self, logged_in_client):
        """Test that TXT files are rejected"""
        txt_data = BytesIO(b'This is a text file')
        
        response = logged_in_client.post('/inventory/upload', data={
            'file': (txt_data, 'test.txt')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_upload_pdf_file_rejected(self, logged_in_client):
        """Test that PDF files are rejected"""
        pdf_data = BytesIO(b'%PDF-1.4 fake pdf content')
        
        response = logged_in_client.post('/inventory/upload', data={
            'file': (pdf_data, 'test.pdf')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_upload_no_file_selected(self, logged_in_client):
        """Test uploading without selecting a file"""
        response = logged_in_client.post('/inventory/upload', data={},
                                        content_type='multipart/form-data',
                                        follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message
        assert 'لم يتم اختيار ملف'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_upload_empty_filename(self, logged_in_client):
        """Test uploading with empty filename"""
        response = logged_in_client.post('/inventory/upload', data={
            'file': (BytesIO(b''), '')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        assert 'لم يتم اختيار ملف'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_upload_corrupted_excel_file(self, logged_in_client):
        """Test uploading corrupted Excel file"""
        # Create fake Excel file with invalid content
        fake_excel = BytesIO(b'This is not a valid Excel file')
        
        response = logged_in_client.post('/inventory/upload', data={
            'file': (fake_excel, 'test.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should handle error gracefully
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_upload_excel_missing_required_sheets(self, logged_in_client):
        """Test uploading Excel file without required sheets"""
        # Create Excel file with wrong sheet names
        df = pd.DataFrame({'col1': [1, 2, 3], 'col2': [4, 5, 6]})
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='WrongSheet', index=False)
        output.seek(0)
        
        response = logged_in_client.post('/inventory/upload', data={
            'file': (output, 'test.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error about missing sheets
        assert 'خطأ'.encode('utf-8') in response.data or 'فشل'.encode('utf-8') in response.data
    
    def test_transfers_upload_invalid_file(self, logged_in_client):
        """Test transfers upload with invalid file type"""
        csv_data = BytesIO(b'col1,col2\nval1,val2')
        
        response = logged_in_client.post('/transfers/upload', data={
            'file': (csv_data, 'test.csv'),
            'branch_code': 'BR001'
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_forecasting_upload_invalid_file(self, logged_in_client):
        """Test forecasting upload with invalid file type"""
        txt_data = BytesIO(b'This is text')
        
        response = logged_in_client.post('/forecasting/upload', data={
            'file': (txt_data, 'test.txt'),
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()


class TestUnauthorizedAccess:
    """Test unauthorized access handling - Requirement 8.4"""
    
    def test_access_home_without_login(self, client):
        """Test accessing home page without login"""
        response = client.get('/', follow_redirects=True)
        assert response.status_code == 200
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_access_inventory_without_login(self, client):
        """Test accessing inventory page without login"""
        response = client.get('/inventory', follow_redirects=True)
        assert response.status_code == 200
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_access_transfers_without_login(self, client):
        """Test accessing transfers page without login"""
        response = client.get('/transfers', follow_redirects=True)
        assert response.status_code == 200
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_access_forecasting_without_login(self, client):
        """Test accessing forecasting page without login"""
        response = client.get('/forecasting', follow_redirects=True)
        assert response.status_code == 200
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_access_admin_without_login(self, client):
        """Test accessing admin page without login"""
        response = client.get('/admin', follow_redirects=True)
        assert response.status_code == 200
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_regular_user_access_admin_page(self, logged_in_client):
        """Test regular user cannot access admin page"""
        response = logged_in_client.get('/admin', follow_redirects=True)
        assert response.status_code == 403 or 'غير مصرح'.encode('utf-8') in response.data
    
    def test_regular_user_cannot_add_user(self, logged_in_client):
        """Test regular user cannot add users"""
        response = logged_in_client.post('/admin/add_user', data={
            'username': 'unauthorized_user',
            'password': 'TestPass123!',
            'is_admin': '0'
        }, follow_redirects=True)
        
        assert response.status_code in [200, 403]
        if response.status_code == 200:
            assert 'غير مصرح'.encode('utf-8') in response.data
    
    def test_regular_user_cannot_delete_user(self, logged_in_client):
        """Test regular user cannot delete users"""
        # Create a test user
        auth_flask.add_user('test_protected_user', 'TestPass123!', False)
        
        try:
            response = logged_in_client.post('/admin/delete_user', data={
                'username': 'test_protected_user'
            }, follow_redirects=True)
            
            assert response.status_code in [200, 403]
            if response.status_code == 200:
                assert 'غير مصرح'.encode('utf-8') in response.data
            
            # Verify user still exists
            users = auth_flask.get_all_users()
            usernames = [u[0] for u in users]
            assert 'test_protected_user' in usernames
        finally:
            auth_flask.delete_user('test_protected_user', 'admin')
    
    def test_regular_user_cannot_change_password(self, logged_in_client):
        """Test regular user cannot change passwords"""
        response = logged_in_client.post('/admin/change_password', data={
            'username': 'admin',
            'new_password': 'HackedPass123!'
        }, follow_redirects=True)
        
        assert response.status_code in [200, 403]
        if response.status_code == 200:
            assert 'غير مصرح'.encode('utf-8') in response.data
    
    def test_post_to_protected_routes_without_login(self, client):
        """Test POST requests to protected routes without login"""
        protected_routes = [
            '/inventory/upload',
            '/inventory/analyze',
            '/transfers/upload',
            '/transfers/analyze',
            '/forecasting/upload',
            '/forecasting/run'
        ]
        
        for route in protected_routes:
            response = client.post(route, data={}, follow_redirects=True)
            assert response.status_code == 200
            assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()


class TestSessionExpiration:
    """Test session expiration handling - Requirement 8.4"""
    
    def test_access_after_logout(self, logged_in_client):
        """Test accessing protected routes after logout"""
        # Logout
        logged_in_client.get('/logout')
        
        # Try to access protected route
        response = logged_in_client.get('/inventory', follow_redirects=True)
        assert response.status_code == 200
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_session_cleared_on_logout(self, logged_in_client):
        """Test that session is properly cleared on logout"""
        # Verify logged in
        with logged_in_client.session_transaction() as sess:
            assert sess.get('logged_in') == True
        
        # Logout
        logged_in_client.get('/logout')
        
        # Verify session cleared
        with logged_in_client.session_transaction() as sess:
            assert sess.get('logged_in') != True
            assert sess.get('username') is None
            assert sess.get('is_admin') is None
    
    def test_session_data_cleared_on_logout(self, logged_in_client):
        """Test that all session data is cleared on logout"""
        # Add some session data
        with logged_in_client.session_transaction() as sess:
            sess['inventory_data'] = {'test': 'data'}
            sess['transfer_data'] = {'test': 'data'}
        
        # Logout
        logged_in_client.get('/logout')
        
        # Verify all data cleared
        with logged_in_client.session_transaction() as sess:
            assert 'inventory_data' not in sess
            assert 'transfer_data' not in sess
    
    def test_cannot_access_with_invalid_session(self, client):
        """Test that invalid session data is rejected"""
        # Manually set invalid session
        with client.session_transaction() as sess:
            sess['logged_in'] = False
        
        response = client.get('/inventory', follow_redirects=True)
        assert response.status_code == 200
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_session_persistence_across_requests(self, logged_in_client):
        """Test that valid session persists across requests"""
        # Make multiple requests
        for _ in range(3):
            response = logged_in_client.get('/inventory')
            assert response.status_code == 200
            
            # Verify session still valid
            with logged_in_client.session_transaction() as sess:
                assert sess.get('logged_in') == True


class TestInvalidFormInputs:
    """Test invalid form input handling - Requirement 8.4"""
    
    def test_inventory_analyze_with_non_numeric_parameters(self, logged_in_client):
        """Test inventory analysis with non-numeric parameters"""
        response = logged_in_client.post('/inventory/analyze', data={
            'min_coverage': 'abc',  # Invalid: not a number
            'max_coverage': 'xyz',  # Invalid: not a number
            'forecast_days': 'invalid'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show validation error
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_inventory_analyze_with_negative_parameters(self, logged_in_client):
        """Test inventory analysis with negative parameters"""
        response = logged_in_client.post('/inventory/analyze', data={
            'min_coverage': '-10',  # Invalid: negative
            'max_coverage': '30',
            'forecast_days': '30'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_inventory_analyze_with_min_greater_than_max(self, logged_in_client):
        """Test inventory analysis with min > max"""
        response = logged_in_client.post('/inventory/analyze', data={
            'min_coverage': '90',  # Invalid: min > max
            'max_coverage': '30',
            'forecast_days': '30'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_inventory_analyze_with_invalid_date_range(self, logged_in_client):
        """Test inventory analysis with invalid date range"""
        response = logged_in_client.post('/inventory/analyze', data={
            'min_coverage': '30',
            'max_coverage': '90',
            'forecast_days': '30',
            'start_date': '2024-12-31',  # Invalid: end before start
            'end_date': '2024-01-01'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_inventory_analyze_with_malformed_dates(self, logged_in_client):
        """Test inventory analysis with malformed dates"""
        response = logged_in_client.post('/inventory/analyze', data={
            'min_coverage': '30',
            'max_coverage': '90',
            'forecast_days': '30',
            'start_date': 'not-a-date',
            'end_date': 'also-not-a-date'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_transfers_analyze_with_invalid_parameters(self, logged_in_client):
        """Test transfers analysis with invalid parameters"""
        response = logged_in_client.post('/transfers/analyze', data={
            'min_coverage': 'invalid',
            'max_coverage': 'invalid',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_forecasting_run_with_invalid_forecast_days(self, logged_in_client):
        """Test forecasting with invalid forecast days"""
        response = logged_in_client.post('/forecasting/run', data={
            'forecast_days': 'invalid'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_forecasting_run_with_excessive_forecast_days(self, logged_in_client):
        """Test forecasting with excessive forecast days"""
        response = logged_in_client.post('/forecasting/run', data={
            'forecast_days': '9999'  # Too large
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should either reject or handle gracefully
    
    def test_admin_add_user_with_empty_username(self, admin_client):
        """Test adding user with empty username"""
        response = admin_client.post('/admin/add_user', data={
            'username': '',  # Invalid: empty
            'password': 'TestPass123!',
            'is_admin': '0'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_admin_add_user_with_weak_password(self, admin_client):
        """Test adding user with weak password"""
        response = admin_client.post('/admin/add_user', data={
            'username': 'test_weak',
            'password': '123',  # Invalid: too short
            'is_admin': '0'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_admin_delete_user_with_empty_username(self, admin_client):
        """Test deleting user with empty username"""
        response = admin_client.post('/admin/delete_user', data={
            'username': ''  # Invalid: empty
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_admin_change_password_with_empty_fields(self, admin_client):
        """Test changing password with empty fields"""
        response = admin_client.post('/admin/change_password', data={
            'username': '',
            'new_password': ''
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_login_with_empty_credentials(self, client):
        """Test login with empty credentials"""
        response = client.post('/login', data={
            'username': '',
            'password': ''
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_transfers_upload_without_branch_code(self, logged_in_client):
        """Test transfers upload without branch code"""
        # Create a fake Excel file
        df = pd.DataFrame({'col1': [1, 2], 'col2': [3, 4]})
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Sheet1', index=False)
        output.seek(0)
        
        response = logged_in_client.post('/transfers/upload', data={
            'file': (output, 'test.xlsx'),
            'branch_code': ''  # Invalid: empty
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()


class TestErrorPages:
    """Test custom error pages"""
    
    def test_404_error_page(self, logged_in_client):
        """Test 404 error page is displayed"""
        response = logged_in_client.get('/nonexistent-page-xyz')
        assert response.status_code == 404
        # Should show custom 404 page
    
    def test_403_error_page(self, logged_in_client):
        """Test 403 error page is displayed"""
        response = logged_in_client.get('/admin')
        assert response.status_code == 403
        # Should show custom 403 page
    
    def test_404_page_for_invalid_route(self, client):
        """Test 404 for completely invalid route"""
        response = client.get('/this/route/does/not/exist')
        assert response.status_code == 404


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
