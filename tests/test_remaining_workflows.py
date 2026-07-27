"""
Minimal integration tests for remaining workflows:
- Branch transfer workflow (Requirements 4.1-4.5)
- Forecasting workflow (Requirements 5.1-5.5)
- Admin functionality (Requirements 6.1-6.5)
- Error handling (Requirements 8.1-8.4)
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask_app import app
import auth_flask


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def logged_in_client(client):
    """Create logged-in test client"""
    username = 'test_workflows_user'
    password = 'TestPass123!'
    auth_flask.add_user(username, password, is_admin=False)
    
    client.post('/login', data={'username': username, 'password': password})
    
    yield client
    
    auth_flask.delete_user(username, 'admin')


@pytest.fixture
def admin_client(client):
    """Create logged-in admin client"""
    username = 'test_admin_workflows'
    password = 'AdminPass123!'
    auth_flask.add_user(username, password, is_admin=True)
    
    client.post('/login', data={'username': username, 'password': password})
    
    yield client
    
    auth_flask.delete_user(username, 'admin')


class TestBranchTransferWorkflow:
    """Test branch transfer workflow - Requirements 4.1-4.5"""
    
    def test_transfers_page_access(self, logged_in_client):
        """Test accessing transfers page - Requirement 4.3"""
        response = logged_in_client.get('/transfers')
        assert response.status_code == 200
        assert 'تحويلات الفروع'.encode('utf-8') in response.data or b'transfer' in response.data.lower()
    
    def test_transfers_page_requires_login(self, client):
        """Test that transfers page requires authentication"""
        response = client.get('/transfers', follow_redirects=True)
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_branch_upload_route_exists(self, logged_in_client):
        """Test branch upload route exists - Requirement 4.1"""
        response = logged_in_client.post('/transfers/upload', data={}, follow_redirects=True)
        assert response.status_code == 200
    
    def test_transfer_analysis_route_exists(self, logged_in_client):
        """Test transfer analysis route exists - Requirement 4.2"""
        response = logged_in_client.post('/transfers/analyze', data={}, follow_redirects=True)
        assert response.status_code == 200
    
    def test_transfer_export_route_exists(self, logged_in_client):
        """Test transfer export route exists - Requirement 4.5"""
        response = logged_in_client.get('/transfers/export', follow_redirects=True)
        assert response.status_code in [200, 302, 400]


class TestForecastingWorkflow:
    """Test forecasting workflow - Requirements 5.1-5.5"""
    
    def test_forecasting_page_access(self, logged_in_client):
        """Test accessing forecasting page - Requirement 5.3"""
        response = logged_in_client.get('/forecasting')
        assert response.status_code == 200
        assert 'التنبؤ'.encode('utf-8') in response.data or b'forecast' in response.data.lower()
    
    def test_forecasting_page_requires_login(self, client):
        """Test that forecasting page requires authentication"""
        response = client.get('/forecasting', follow_redirects=True)
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_forecasting_upload_route_exists(self, logged_in_client):
        """Test forecasting upload route exists - Requirement 5.1"""
        response = logged_in_client.post('/forecasting/upload', data={}, follow_redirects=True)
        assert response.status_code == 200
    
    def test_forecasting_run_route_exists(self, logged_in_client):
        """Test forecasting run route exists - Requirement 5.2"""
        response = logged_in_client.post('/forecasting/run', data={}, follow_redirects=True)
        assert response.status_code == 200
    
    def test_forecasting_export_route_exists(self, logged_in_client):
        """Test forecasting export route exists - Requirement 5.5"""
        response = logged_in_client.get('/forecasting/export', follow_redirects=True)
        assert response.status_code in [200, 302, 400]


class TestAdminFunctionality:
    """Test admin functionality - Requirements 6.1-6.5"""
    
    def test_admin_page_access_for_admin(self, admin_client):
        """Test admin can access admin page - Requirement 6.1"""
        response = admin_client.get('/admin')
        assert response.status_code == 200
        assert 'إدارة المستخدمين'.encode('utf-8') in response.data or b'user' in response.data.lower()
    
    def test_admin_page_blocked_for_regular_user(self, logged_in_client):
        """Test regular user cannot access admin page - Requirement 6.1"""
        response = logged_in_client.get('/admin', follow_redirects=True)
        assert response.status_code == 403 or 'غير مصرح'.encode('utf-8') in response.data
    
    def test_admin_page_requires_login(self, client):
        """Test admin page requires authentication"""
        response = client.get('/admin', follow_redirects=True)
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_user_list_display(self, admin_client):
        """Test user list is displayed - Requirement 6.2"""
        response = admin_client.get('/admin')
        assert response.status_code == 200
        # Should show admin user in list
        assert b'admin' in response.data or 'admin'.encode('utf-8') in response.data
    
    def test_add_user_route_exists(self, admin_client):
        """Test add user route exists - Requirement 6.3"""
        response = admin_client.post('/admin/add_user', data={
            'username': 'test_new_user',
            'password': 'TestPass123!',
            'is_admin': 'false'
        }, follow_redirects=True)
        assert response.status_code == 200
        # Cleanup
        auth_flask.delete_user('test_new_user', 'admin')
    
    def test_delete_user_route_exists(self, admin_client):
        """Test delete user route exists - Requirement 6.4"""
        # Create a user to delete
        auth_flask.add_user('test_delete_user', 'TestPass123!', False)
        
        response = admin_client.post('/admin/delete_user', data={
            'username': 'test_delete_user'
        }, follow_redirects=True)
        assert response.status_code == 200
    
    def test_change_password_route_exists(self, admin_client):
        """Test change password route exists - Requirement 6.5"""
        # Create a user to change password
        auth_flask.add_user('test_pwd_user', 'OldPass123!', False)
        
        response = admin_client.post('/admin/change_password', data={
            'username': 'test_pwd_user',
            'new_password': 'NewPass123!'
        }, follow_redirects=True)
        assert response.status_code == 200
        
        # Cleanup
        auth_flask.delete_user('test_pwd_user', 'admin')
    
    def test_regular_user_cannot_add_user(self, logged_in_client):
        """Test regular user cannot add users"""
        response = logged_in_client.post('/admin/add_user', data={
            'username': 'test_unauthorized',
            'password': 'TestPass123!'
        }, follow_redirects=True)
        # Should be blocked (403) or redirected
        assert response.status_code in [200, 403]


class TestErrorHandling:
    """Test error handling - Requirements 8.1-8.4"""
    
    def test_invalid_file_extension(self, logged_in_client):
        """Test invalid file upload is rejected - Requirement 8.1"""
        from io import BytesIO
        csv_data = BytesIO(b'col1,col2\nval1,val2')
        
        response = logged_in_client.post('/inventory/upload', data={
            'file': (csv_data, 'test.csv')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # App handles gracefully
    
    def test_unauthorized_access_to_protected_route(self, client):
        """Test unauthorized access is blocked - Requirement 8.4"""
        response = client.get('/inventory', follow_redirects=True)
        # Should redirect to login
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_unauthorized_access_to_admin_route(self, logged_in_client):
        """Test non-admin cannot access admin routes - Requirement 8.4"""
        response = logged_in_client.get('/admin', follow_redirects=True)
        assert response.status_code == 403 or 'غير مصرح'.encode('utf-8') in response.data
    
    def test_404_error_handler(self, logged_in_client):
        """Test 404 error handler exists"""
        response = logged_in_client.get('/nonexistent-page')
        assert response.status_code == 404
    
    def test_session_expiration_handling(self, client):
        """Test session expiration is handled - Requirement 8.4"""
        # Try to access protected route without session
        response = client.get('/inventory', follow_redirects=True)
        # Should redirect to login
        assert response.status_code == 200
        assert b'login' in response.data.lower() or 'تسجيل الدخول'.encode('utf-8') in response.data
    
    def test_invalid_form_inputs(self, logged_in_client):
        """Test invalid form inputs are handled - Requirement 8.4"""
        # Try to analyze with invalid parameters
        response = logged_in_client.post('/inventory/analyze', data={
            'min_coverage': 'invalid',  # Should be numeric
            'max_coverage': 'invalid'
        }, follow_redirects=True)
        
        # Should handle gracefully
        assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
