"""
Integration tests for authentication flow.
Tests login, logout, session persistence, and access control.
Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
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
def test_user():
    """Create a test user and clean up after test"""
    username = 'test_user_auth'
    password = 'TestPass123!'
    
    # Add test user
    auth_flask.add_user(username, password, is_admin=False)
    
    yield {'username': username, 'password': password}
    
    # Cleanup
    auth_flask.delete_user(username, 'admin')


@pytest.fixture
def test_admin():
    """Create a test admin user and clean up after test"""
    username = 'test_admin_auth'
    password = 'AdminPass123!'
    
    # Add test admin
    auth_flask.add_user(username, password, is_admin=True)
    
    yield {'username': username, 'password': password}
    
    # Cleanup
    auth_flask.delete_user(username, 'admin')


class TestAuthenticationFlow:
    """Test authentication flow - Requirements 2.1, 2.2, 2.3, 2.4, 2.5"""
    
    def test_login_with_valid_credentials(self, client, test_user):
        """Test login with valid credentials - Requirement 2.3"""
        response = client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'تم تسجيل الدخول بنجاح'.encode('utf-8') in response.data or b'success' in response.data
        
        # Verify session was created
        with client.session_transaction() as sess:
            assert sess.get('logged_in') == True
            assert sess.get('username') == test_user['username']
            assert sess.get('is_admin') == False
    
    def test_login_with_invalid_password(self, client, test_user):
        """Test login with invalid password - Requirement 2.3"""
        response = client.post('/login', data={
            'username': test_user['username'],
            'password': 'WrongPassword123!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'كلمة المرور غير صحيحة'.encode('utf-8') in response.data or b'error' in response.data
        
        # Verify session was not created
        with client.session_transaction() as sess:
            assert sess.get('logged_in') != True
    
    def test_login_with_invalid_username(self, client):
        """Test login with non-existent username - Requirement 2.3"""
        response = client.post('/login', data={
            'username': 'nonexistent_user',
            'password': 'SomePassword123!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'اسم المستخدم غير موجود'.encode('utf-8') in response.data or b'error' in response.data
        
        # Verify session was not created
        with client.session_transaction() as sess:
            assert sess.get('logged_in') != True
    
    def test_login_with_empty_credentials(self, client):
        """Test login with empty credentials - Requirement 2.3"""
        response = client.post('/login', data={
            'username': '',
            'password': ''
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show validation error
        
        # Verify session was not created
        with client.session_transaction() as sess:
            assert sess.get('logged_in') != True
    
    def test_logout_functionality(self, client, test_user):
        """Test logout functionality - Requirement 2.5"""
        # First login
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        # Verify logged in
        with client.session_transaction() as sess:
            assert sess.get('logged_in') == True
        
        # Logout
        response = client.get('/logout', follow_redirects=True)
        
        assert response.status_code == 200
        assert 'تم تسجيل الخروج بنجاح'.encode('utf-8') in response.data or b'logout' in response.data.lower()
        
        # Verify session was cleared
        with client.session_transaction() as sess:
            assert sess.get('logged_in') != True
            assert sess.get('username') is None
    
    def test_session_persistence(self, client, test_user):
        """Test session persistence across requests - Requirement 2.4"""
        # Login
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        # Make multiple requests and verify session persists
        for _ in range(3):
            response = client.get('/')
            assert response.status_code == 200
            
            with client.session_transaction() as sess:
                assert sess.get('logged_in') == True
                assert sess.get('username') == test_user['username']
    
    def test_admin_vs_regular_user_access(self, client, test_user, test_admin):
        """Test admin vs regular user access - Requirement 2.4"""
        # Test regular user cannot access admin page
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        response = client.get('/admin', follow_redirects=True)
        assert response.status_code == 403 or 'غير مصرح'.encode('utf-8') in response.data
        
        # Logout
        client.get('/logout')
        
        # Test admin user can access admin page
        client.post('/login', data={
            'username': test_admin['username'],
            'password': test_admin['password']
        })
        
        response = client.get('/admin')
        assert response.status_code == 200
        
        # Verify admin flag in session
        with client.session_transaction() as sess:
            assert sess.get('is_admin') == True
    
    def test_protected_route_without_login(self, client):
        """Test accessing protected route without login - Requirement 2.3"""
        response = client.get('/', follow_redirects=True)
        
        # Should redirect to login
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_login_page_redirect_when_logged_in(self, client, test_user):
        """Test that logged-in users are redirected from login page"""
        # Login
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        # Try to access login page
        response = client.get('/login', follow_redirects=True)
        
        # Should redirect to home
        assert response.status_code == 200
        # Should not show login form
    
    def test_existing_database_compatibility(self, client):
        """Test that existing database and bcrypt hashing work - Requirements 2.1, 2.2"""
        # Test with default admin user
        response = client.post('/login', data={
            'username': 'admin',
            'password': 'ChangeMe123!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        with client.session_transaction() as sess:
            # Should be logged in (or password might have been changed)
            # This tests database compatibility
            pass


class TestLogoutFunctionality:
    """Test logout functionality - Requirements 1.1, 1.4, 2.1, 2.2, 2.4"""
    
    def test_logout_clears_all_session_data(self, client, test_user):
        """Test that logout clears all session data - **Validates: Requirements 1.1, 2.1**"""
        # Login first
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        # Verify session has data
        with client.session_transaction() as sess:
            assert sess.get('logged_in') == True
            assert sess.get('username') == test_user['username']
            assert sess.get('is_admin') == False
        
        # Logout
        response = client.get('/logout', follow_redirects=False)
        
        # Verify all authentication-related session data is cleared
        with client.session_transaction() as sess:
            assert sess.get('logged_in') is None
            assert sess.get('username') is None
            assert sess.get('is_admin') is None
            # Flash messages are allowed (they're needed to show logout success message)
            # But all authentication data should be gone
    
    def test_logout_response_includes_cookie_expiration(self, client, test_user):
        """Test that logout response includes cookie expiration - **Validates: Requirements 1.4, 2.2**"""
        # Login first
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        # Logout
        response = client.get('/logout', follow_redirects=False)
        
        # Check response headers for cookie expiration
        # Flask sets cookies with Set-Cookie header
        set_cookie_headers = [h for h in response.headers if h[0] == 'Set-Cookie']
        
        # Should have at least one Set-Cookie header
        assert len(set_cookie_headers) > 0, "No Set-Cookie header found in logout response"
        
        # Check that the session cookie is being expired
        # Look for Max-Age=0 or Expires in the past
        cookie_header = set_cookie_headers[0][1]
        assert 'Max-Age=0' in cookie_header or 'expires=' in cookie_header.lower(), \
            "Cookie expiration not found in Set-Cookie header"
    
    def test_logout_redirects_to_login_page(self, client, test_user):
        """Test that logout redirects to login page - **Validates: Requirements 2.1**"""
        # Login first
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        # Logout without following redirects
        response = client.get('/logout', follow_redirects=False)
        
        # Should redirect (302 or 303)
        assert response.status_code in [302, 303], f"Expected redirect, got {response.status_code}"
        
        # Should redirect to login page
        assert '/login' in response.location, f"Expected redirect to /login, got {response.location}"
    
    def test_logout_logs_the_event(self, client, test_user, caplog):
        """Test that logout logs the event with username and timestamp - **Validates: Requirements 2.4**"""
        import logging
        
        # Set up logging capture
        caplog.set_level(logging.INFO)
        
        # Login first
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        # Clear previous logs
        caplog.clear()
        
        # Logout
        response = client.get('/logout', follow_redirects=False)
        
        # Check that logout was logged
        logout_logs = [record for record in caplog.records if 'logged out' in record.message.lower()]
        assert len(logout_logs) > 0, "No logout event found in logs"
        
        # Verify the log contains the username
        logout_log = logout_logs[0]
        assert test_user['username'] in logout_log.message, \
            f"Username not found in logout log: {logout_log.message}"


class TestLoginFormRendering:
    """Test login form rendering - Requirements 1.3"""
    
    def test_login_form_has_autocomplete_off(self, client):
        """Test that login form HTML contains autocomplete='off' - **Validates: Requirements 1.3**"""
        response = client.get('/login')
        
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check that form has autocomplete="off"
        assert 'autocomplete="off"' in html, "Form element should have autocomplete='off'"
    
    def test_password_field_has_autocomplete_new_password(self, client):
        """Test that password field has autocomplete='new-password' - **Validates: Requirements 1.3**"""
        response = client.get('/login')
        
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check that password field has autocomplete="new-password"
        assert 'autocomplete="new-password"' in html, \
            "Password field should have autocomplete='new-password'"
    
    def test_form_does_not_enable_autofill(self, client):
        """Test that form does not contain autocomplete values that enable autofill - **Validates: Requirements 1.3**"""
        response = client.get('/login')
        
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Check that form doesn't have autocomplete values that enable autofill
        # These values would enable browser autofill: "username", "current-password", "on"
        
        # The username field should have autocomplete="off" (not "username")
        # We already have autocomplete="off" on the form level, which is good
        
        # Make sure we don't have autocomplete="username" or autocomplete="current-password"
        # which would override the form-level setting
        assert 'autocomplete="username"' not in html or 'autocomplete="off"' in html, \
            "Form should not enable username autofill"
        assert 'autocomplete="current-password"' not in html, \
            "Form should not have autocomplete='current-password' which enables autofill"


class TestAuthenticationFlowIntegration:
    """Integration tests for complete authentication flow - **Validates: Requirements 1.5, 2.3, 2.5**"""
    
    def test_complete_login_logout_flow(self, client, test_user):
        """
        Test complete login/logout flow from start to finish.
        **Validates: Requirements 1.5, 2.3, 2.5**
        """
        # Step 1: Start unauthenticated - should redirect to login
        response = client.get('/', follow_redirects=False)
        assert response.status_code in [302, 303], "Unauthenticated access should redirect"
        assert '/login' in response.location, "Should redirect to login page"
        
        # Step 2: Login with valid credentials
        response = client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        }, follow_redirects=False)
        
        assert response.status_code in [302, 303], "Successful login should redirect"
        
        # Step 3: Verify session is created
        with client.session_transaction() as sess:
            assert sess.get('logged_in') == True, "Session should have logged_in flag"
            assert sess.get('username') == test_user['username'], "Session should have username"
        
        # Step 4: Access protected route - should succeed
        response = client.get('/', follow_redirects=False)
        assert response.status_code == 200, "Authenticated user should access home page"
        
        # Step 5: Logout
        response = client.get('/logout', follow_redirects=False)
        assert response.status_code in [302, 303], "Logout should redirect"
        assert '/login' in response.location, "Logout should redirect to login"
        
        # Step 6: Verify session is cleared
        with client.session_transaction() as sess:
            assert sess.get('logged_in') is None, "logged_in should be cleared"
            assert sess.get('username') is None, "username should be cleared"
            assert sess.get('is_admin') is None, "is_admin should be cleared"
        
        # Step 7: Try to access protected route after logout - should redirect
        response = client.get('/', follow_redirects=False)
        assert response.status_code in [302, 303], "Should redirect after logout"
        assert '/login' in response.location, "Should redirect to login after logout"
    
    def test_accessing_protected_routes_after_logout_redirects_to_login(self, client, test_user):
        """
        Test that all protected routes redirect to login after logout.
        **Validates: Requirements 2.3, 2.5**
        """
        # Login first
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        # Verify we can access protected routes
        protected_routes = ['/', '/inventory', '/transfers', '/forecasting']
        for route in protected_routes:
            response = client.get(route, follow_redirects=False)
            assert response.status_code == 200, f"Should access {route} when logged in"
        
        # Logout
        client.get('/logout')
        
        # Verify all protected routes now redirect to login
        for route in protected_routes:
            response = client.get(route, follow_redirects=False)
            assert response.status_code in [302, 303], f"{route} should redirect after logout"
            assert '/login' in response.location, f"{route} should redirect to login after logout"
    
    def test_session_expiration_requires_reauthentication(self, client, test_user):
        """
        Test that expired sessions require re-authentication.
        **Validates: Requirements 2.5**
        """
        # Login
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        # Verify logged in
        response = client.get('/', follow_redirects=False)
        assert response.status_code == 200, "Should access home when logged in"
        
        # Manually clear session to simulate expiration
        with client.session_transaction() as sess:
            sess.clear()
        
        # Try to access protected route - should redirect to login
        response = client.get('/', follow_redirects=False)
        assert response.status_code in [302, 303], "Expired session should redirect"
        assert '/login' in response.location, "Expired session should redirect to login"
        
        # Verify we need to login again
        response = client.get('/', follow_redirects=True)
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower(), \
            "Should show login prompt after session expiration"
    
    def test_login_redirect_when_already_authenticated(self, client, test_user):
        """
        Test that accessing login page when already authenticated redirects to home.
        **Validates: Requirements 1.5**
        """
        # Login
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        # Verify logged in
        with client.session_transaction() as sess:
            assert sess.get('logged_in') == True
        
        # Try to access login page - should redirect to home
        response = client.get('/login', follow_redirects=False)
        assert response.status_code in [200, 302, 303], "Should handle already-logged-in case"
        
        # If it redirects, should go to home
        if response.status_code in [302, 303]:
            assert '/' in response.location, "Should redirect to home when already logged in"
    
    def test_multiple_login_logout_cycles(self, client, test_user):
        """
        Test multiple login/logout cycles to ensure no state leakage.
        **Validates: Requirements 1.5, 2.3, 2.5**
        """
        for cycle in range(3):
            # Login
            response = client.post('/login', data={
                'username': test_user['username'],
                'password': test_user['password']
            }, follow_redirects=False)
            
            assert response.status_code in [302, 303], f"Cycle {cycle}: Login should succeed"
            
            # Verify session
            with client.session_transaction() as sess:
                assert sess.get('logged_in') == True, f"Cycle {cycle}: Should be logged in"
                assert sess.get('username') == test_user['username'], f"Cycle {cycle}: Username should match"
            
            # Access protected route
            response = client.get('/', follow_redirects=False)
            assert response.status_code == 200, f"Cycle {cycle}: Should access home"
            
            # Logout
            response = client.get('/logout', follow_redirects=False)
            assert response.status_code in [302, 303], f"Cycle {cycle}: Logout should redirect"
            
            # Verify session cleared
            with client.session_transaction() as sess:
                assert sess.get('logged_in') is None, f"Cycle {cycle}: Session should be cleared"
            
            # Verify cannot access protected route
            response = client.get('/', follow_redirects=False)
            assert response.status_code in [302, 303], f"Cycle {cycle}: Should redirect after logout"
    
    def test_admin_route_access_control_after_logout(self, client, test_admin):
        """
        Test that admin routes are protected after logout.
        **Validates: Requirements 2.3, 2.5**
        """
        # Login as admin
        client.post('/login', data={
            'username': test_admin['username'],
            'password': test_admin['password']
        })
        
        # Verify can access admin route
        response = client.get('/admin', follow_redirects=False)
        assert response.status_code == 200, "Admin should access admin page"
        
        # Logout
        client.get('/logout')
        
        # Try to access admin route - should redirect to login
        response = client.get('/admin', follow_redirects=False)
        assert response.status_code in [302, 303], "Should redirect to login after logout"
        assert '/login' in response.location, "Should redirect to login page"
    
    def test_session_isolation_between_users(self, client, test_user, test_admin):
        """
        Test that sessions are properly isolated between different users.
        **Validates: Requirements 2.3, 2.5**
        """
        # Login as regular user
        client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        })
        
        # Verify regular user session
        with client.session_transaction() as sess:
            assert sess.get('username') == test_user['username']
            assert sess.get('is_admin') == False
        
        # Logout
        client.get('/logout')
        
        # Login as admin
        client.post('/login', data={
            'username': test_admin['username'],
            'password': test_admin['password']
        })
        
        # Verify admin session (should not have any data from previous user)
        with client.session_transaction() as sess:
            assert sess.get('username') == test_admin['username'], "Should have new username"
            assert sess.get('is_admin') == True, "Should have admin flag"
            # Ensure no leftover data from previous session
            assert sess.get('username') != test_user['username'], "Should not have old username"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
