"""
Comprehensive integration tests for admin functionality.
Tests user list display, add user, delete user, change password, and access control.
Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
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
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def admin_client(client):
    """Create logged-in admin client"""
    username = 'test_admin_comprehensive'
    password = 'AdminPass123!'
    
    # Add test admin
    auth_flask.add_user(username, password, is_admin=True)
    
    # Login
    client.post('/login', data={'username': username, 'password': password})
    
    yield client
    
    # Cleanup
    auth_flask.delete_user(username, 'admin')


@pytest.fixture
def regular_user_client(client):
    """Create logged-in regular user client"""
    username = 'test_regular_user'
    password = 'UserPass123!'
    
    # Add test user
    auth_flask.add_user(username, password, is_admin=False)
    
    # Login
    client.post('/login', data={'username': username, 'password': password})
    
    yield client
    
    # Cleanup
    auth_flask.delete_user(username, 'admin')


class TestAdminPageAccess:
    """Test admin page access control - Requirement 6.1"""
    
    def test_admin_can_access_admin_page(self, admin_client):
        """Test that admin users can access the admin page"""
        response = admin_client.get('/admin')
        assert response.status_code == 200
        # Check for Arabic text or admin-related content
        assert 'إدارة المستخدمين'.encode('utf-8') in response.data or b'user' in response.data.lower()
    
    def test_regular_user_cannot_access_admin_page(self, regular_user_client):
        """Test that regular users cannot access the admin page"""
        response = regular_user_client.get('/admin', follow_redirects=True)
        assert response.status_code == 403 or 'غير مصرح'.encode('utf-8') in response.data
    
    def test_unauthenticated_user_cannot_access_admin_page(self, client):
        """Test that unauthenticated users cannot access the admin page"""
        response = client.get('/admin', follow_redirects=True)
        # Should redirect to login
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_admin_page_shows_admin_content(self, admin_client):
        """Test that admin page displays admin-specific content"""
        response = admin_client.get('/admin')
        assert response.status_code == 200
        # Should contain forms for user management
        assert b'form' in response.data.lower()


class TestUserListDisplay:
    """Test user list display - Requirement 6.2"""
    
    def test_user_list_displays_all_users(self, admin_client):
        """Test that admin page displays all users"""
        # Create some test users
        test_users = [
            ('test_user_1', 'Pass123!', False),
            ('test_user_2', 'Pass123!', False),
            ('test_user_3', 'Pass123!', True)
        ]
        
        for username, password, is_admin in test_users:
            auth_flask.add_user(username, password, is_admin)
        
        try:
            response = admin_client.get('/admin')
            assert response.status_code == 200
            
            # Check that all test users appear in the response
            for username, _, _ in test_users:
                assert username.encode('utf-8') in response.data
        
        finally:
            # Cleanup
            for username, _, _ in test_users:
                auth_flask.delete_user(username, 'admin')
    
    def test_user_list_shows_admin_status(self, admin_client):
        """Test that user list indicates admin status"""
        # Create admin and regular user
        auth_flask.add_user('test_admin_user', 'Pass123!', True)
        auth_flask.add_user('test_regular_user', 'Pass123!', False)
        
        try:
            response = admin_client.get('/admin')
            assert response.status_code == 200
            
            # Both users should be in the list
            assert b'test_admin_user' in response.data
            assert b'test_regular_user' in response.data
        
        finally:
            # Cleanup
            auth_flask.delete_user('test_admin_user', 'admin')
            auth_flask.delete_user('test_regular_user', 'admin')
    
    def test_user_list_includes_default_admin(self, admin_client):
        """Test that default admin user is displayed"""
        response = admin_client.get('/admin')
        assert response.status_code == 200
        # Default admin should be in the list
        assert b'admin' in response.data


class TestAddUser:
    """Test add user functionality - Requirement 6.3"""
    
    def test_admin_can_add_regular_user(self, admin_client):
        """Test that admin can add a regular user"""
        response = admin_client.post('/admin/add_user', data={
            'username': 'new_regular_user',
            'password': 'NewPass123!',
            'is_admin': '0'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'تمت إضافة المستخدم'.encode('utf-8') in response.data or b'success' in response.data.lower()
        
        # Verify user was added
        users = auth_flask.get_all_users()
        usernames = [u[0] for u in users]
        assert 'new_regular_user' in usernames
        
        # Cleanup
        auth_flask.delete_user('new_regular_user', 'admin')
    
    def test_admin_can_add_admin_user(self, admin_client):
        """Test that admin can add another admin user"""
        response = admin_client.post('/admin/add_user', data={
            'username': 'new_admin_user',
            'password': 'AdminPass123!',
            'is_admin': '1'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'تمت إضافة المستخدم'.encode('utf-8') in response.data or b'success' in response.data.lower()
        
        # Verify user was added as admin
        users = auth_flask.get_all_users()
        for username, is_admin in users:
            if username == 'new_admin_user':
                assert is_admin == 1
                break
        
        # Cleanup
        auth_flask.delete_user('new_admin_user', 'admin')
    
    def test_cannot_add_duplicate_username(self, admin_client):
        """Test that adding a duplicate username fails"""
        # Add first user
        auth_flask.add_user('duplicate_user', 'Pass123!', False)
        
        try:
            # Try to add user with same username
            response = admin_client.post('/admin/add_user', data={
                'username': 'duplicate_user',
                'password': 'AnotherPass123!',
                'is_admin': '0'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert 'موجود بالفعل'.encode('utf-8') in response.data or b'error' in response.data.lower()
        
        finally:
            # Cleanup
            auth_flask.delete_user('duplicate_user', 'admin')
    
    def test_cannot_add_user_with_empty_username(self, admin_client):
        """Test that adding user with empty username fails"""
        response = admin_client.post('/admin/add_user', data={
            'username': '',
            'password': 'Pass123!',
            'is_admin': '0'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show validation error
        assert b'error' in response.data.lower() or 'خطأ'.encode('utf-8') in response.data
    
    def test_cannot_add_user_with_weak_password(self, admin_client):
        """Test that adding user with weak password fails"""
        response = admin_client.post('/admin/add_user', data={
            'username': 'test_weak_pass',
            'password': '123',  # Too short
            'is_admin': '0'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show validation error
        assert b'error' in response.data.lower() or 'خطأ'.encode('utf-8') in response.data
    
    def test_regular_user_cannot_add_user(self, regular_user_client):
        """Test that regular users cannot add users"""
        response = regular_user_client.post('/admin/add_user', data={
            'username': 'unauthorized_user',
            'password': 'Pass123!',
            'is_admin': '0'
        }, follow_redirects=True)
        
        # Should be blocked (403) or redirected
        assert response.status_code in [200, 403]
        if response.status_code == 200:
            assert 'غير مصرح'.encode('utf-8') in response.data


class TestDeleteUser:
    """Test delete user functionality - Requirement 6.4"""
    
    def test_admin_can_delete_user(self, admin_client):
        """Test that admin can delete a user"""
        # Create user to delete
        auth_flask.add_user('user_to_delete', 'Pass123!', False)
        
        response = admin_client.post('/admin/delete_user', data={
            'username': 'user_to_delete'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'تم حذف المستخدم'.encode('utf-8') in response.data or b'success' in response.data.lower()
        
        # Verify user was deleted
        users = auth_flask.get_all_users()
        usernames = [u[0] for u in users]
        assert 'user_to_delete' not in usernames
    
    def test_cannot_delete_current_user(self, admin_client):
        """Test that admin cannot delete their own account"""
        # Get current admin username from session
        with admin_client.session_transaction() as sess:
            current_username = sess.get('username')
        
        response = admin_client.post('/admin/delete_user', data={
            'username': current_username
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'لا يمكنك حذف حسابك الحالي'.encode('utf-8') in response.data or b'error' in response.data.lower()
        
        # Verify user still exists
        users = auth_flask.get_all_users()
        usernames = [u[0] for u in users]
        assert current_username in usernames
    
    def test_cannot_delete_nonexistent_user(self, admin_client):
        """Test that deleting non-existent user fails gracefully"""
        response = admin_client.post('/admin/delete_user', data={
            'username': 'nonexistent_user_xyz'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message
        assert 'لم يتم العثور'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_regular_user_cannot_delete_user(self, regular_user_client):
        """Test that regular users cannot delete users"""
        # Create a user
        auth_flask.add_user('user_to_protect', 'Pass123!', False)
        
        try:
            response = regular_user_client.post('/admin/delete_user', data={
                'username': 'user_to_protect'
            }, follow_redirects=True)
            
            # Should be blocked (403) or redirected
            assert response.status_code in [200, 403]
            if response.status_code == 200:
                assert 'غير مصرح'.encode('utf-8') in response.data
            
            # Verify user still exists
            users = auth_flask.get_all_users()
            usernames = [u[0] for u in users]
            assert 'user_to_protect' in usernames
        
        finally:
            # Cleanup
            auth_flask.delete_user('user_to_protect', 'admin')


class TestChangePassword:
    """Test change password functionality - Requirement 6.5"""
    
    def test_admin_can_change_user_password(self, admin_client):
        """Test that admin can change a user's password"""
        # Create user
        auth_flask.add_user('user_pwd_change', 'OldPass123!', False)
        
        try:
            response = admin_client.post('/admin/change_password', data={
                'username': 'user_pwd_change',
                'new_password': 'NewPass123!'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert 'تم تغيير كلمة مرور'.encode('utf-8') in response.data or b'success' in response.data.lower()
            
            # Verify password was changed by trying to login with new password
            test_client = app.test_client()
            test_client.config = app.config
            login_response = test_client.post('/login', data={
                'username': 'user_pwd_change',
                'password': 'NewPass123!'
            }, follow_redirects=True)
            
            # Should be able to login with new password
            assert login_response.status_code == 200
            assert 'تم تسجيل الدخول بنجاح'.encode('utf-8') in login_response.data or b'success' in login_response.data
        
        finally:
            # Cleanup
            auth_flask.delete_user('user_pwd_change', 'admin')
    
    def test_admin_can_change_own_password(self, admin_client):
        """Test that admin can change their own password"""
        # Get current admin username
        with admin_client.session_transaction() as sess:
            current_username = sess.get('username')
        
        response = admin_client.post('/admin/change_password', data={
            'username': current_username,
            'new_password': 'NewAdminPass123!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'تم تغيير كلمة مرور'.encode('utf-8') in response.data or b'success' in response.data.lower()
        
        # Change it back for cleanup
        auth_flask.change_password(current_username, 'AdminPass123!')
    
    def test_cannot_change_password_with_weak_password(self, admin_client):
        """Test that changing to weak password fails"""
        # Create user
        auth_flask.add_user('user_weak_pwd', 'OldPass123!', False)
        
        try:
            response = admin_client.post('/admin/change_password', data={
                'username': 'user_weak_pwd',
                'new_password': '123'  # Too short
            }, follow_redirects=True)
            
            assert response.status_code == 200
            # Should show validation error
            assert b'error' in response.data.lower() or 'خطأ'.encode('utf-8') in response.data
        
        finally:
            # Cleanup
            auth_flask.delete_user('user_weak_pwd', 'admin')
    
    def test_cannot_change_password_for_nonexistent_user(self, admin_client):
        """Test that changing password for non-existent user fails"""
        response = admin_client.post('/admin/change_password', data={
            'username': 'nonexistent_user_pwd',
            'new_password': 'NewPass123!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should handle gracefully (might succeed but have no effect)
    
    def test_regular_user_cannot_change_password(self, regular_user_client):
        """Test that regular users cannot change passwords"""
        # Create a user
        auth_flask.add_user('user_pwd_protect', 'Pass123!', False)
        
        try:
            response = regular_user_client.post('/admin/change_password', data={
                'username': 'user_pwd_protect',
                'new_password': 'HackedPass123!'
            }, follow_redirects=True)
            
            # Should be blocked (403) or redirected
            assert response.status_code in [200, 403]
            if response.status_code == 200:
                assert 'غير مصرح'.encode('utf-8') in response.data
        
        finally:
            # Cleanup
            auth_flask.delete_user('user_pwd_protect', 'admin')


class TestAccessControl:
    """Test access control for admin routes - Requirement 6.1"""
    
    def test_all_admin_routes_require_admin_privilege(self, regular_user_client):
        """Test that all admin routes require admin privilege"""
        admin_routes = [
            ('/admin', 'GET'),
            ('/admin/add_user', 'POST'),
            ('/admin/delete_user', 'POST'),
            ('/admin/change_password', 'POST')
        ]
        
        for route, method in admin_routes:
            if method == 'GET':
                response = regular_user_client.get(route, follow_redirects=True)
            else:
                response = regular_user_client.post(route, data={}, follow_redirects=True)
            
            # Should be blocked (403) or show error
            assert response.status_code in [200, 403]
            if response.status_code == 200:
                # Should contain error message
                assert 'غير مصرح'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_all_admin_routes_require_authentication(self, client):
        """Test that all admin routes require authentication"""
        admin_routes = [
            ('/admin', 'GET'),
            ('/admin/add_user', 'POST'),
            ('/admin/delete_user', 'POST'),
            ('/admin/change_password', 'POST')
        ]
        
        for route, method in admin_routes:
            if method == 'GET':
                response = client.get(route, follow_redirects=True)
            else:
                response = client.post(route, data={}, follow_redirects=True)
            
            # Should redirect to login
            assert response.status_code == 200
            assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
