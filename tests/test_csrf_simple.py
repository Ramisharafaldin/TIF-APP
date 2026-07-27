"""
Simple test to verify CSRF token presence on pages.
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from flask_app import app
    import auth_flask
    FLASK_AVAILABLE = True
except ImportError as e:
    print(f"Flask app import failed: {e}")
    FLASK_AVAILABLE = False


@pytest.fixture
def client():
    """Create test client"""
    if not FLASK_AVAILABLE:
        pytest.skip("Flask app not available")
    
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = True  # Enable CSRF for this test
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def logged_in_client(client):
    """Create logged-in test client"""
    # Create test user
    username = 'test_csrf_user'
    password = 'TestPass123!'
    auth_flask.add_user(username, password, is_admin=False)
    
    # Login
    client.post('/login', data={
        'username': username,
        'password': password
    }, follow_redirects=True)
    
    yield client
    
    # Cleanup
    try:
        auth_flask.delete_user(username, 'admin')
    except:
        pass


def test_csrf_token_on_dashboard_page(logged_in_client):
    """Test CSRF token presence on dashboard page"""
    response = logged_in_client.get('/dashboard')
    assert response.status_code == 200
    
    # Check for CSRF token meta tag in response data
    response_text = response.data.decode('utf-8')
    assert 'name="csrf-token"' in response_text, "CSRF token meta tag not found on dashboard page"
    assert 'content=' in response_text, "CSRF token content not found on dashboard page"


def test_csrf_token_on_inventory_page(logged_in_client):
    """Test CSRF token presence on inventory page"""
    response = logged_in_client.get('/inventory')
    assert response.status_code == 200
    
    # Check for CSRF token meta tag in response data
    response_text = response.data.decode('utf-8')
    assert 'name="csrf-token"' in response_text, "CSRF token meta tag not found on inventory page"
    assert 'content=' in response_text, "CSRF token content not found on inventory page"


def test_csrf_token_on_transfers_page(logged_in_client):
    """Test CSRF token presence on transfers page"""
    response = logged_in_client.get('/transfers')
    assert response.status_code == 200
    
    # Check for CSRF token meta tag in response data
    response_text = response.data.decode('utf-8')
    assert 'name="csrf-token"' in response_text, "CSRF token meta tag not found on transfers page"
    assert 'content=' in response_text, "CSRF token content not found on transfers page"


def test_csrf_token_on_forecasting_page(logged_in_client):
    """Test CSRF token presence on forecasting page"""
    response = logged_in_client.get('/forecasting')
    assert response.status_code == 200
    
    # Check for CSRF token meta tag in response data
    response_text = response.data.decode('utf-8')
    assert 'name="csrf-token"' in response_text, "CSRF token meta tag not found on forecasting page"
    assert 'content=' in response_text, "CSRF token content not found on forecasting page"


def test_ai_features_script_inclusion(logged_in_client):
    """Test that AI features JavaScript is included on all AI-enabled pages"""
    pages = ['/dashboard', '/inventory', '/transfers', '/forecasting']
    
    for page in pages:
        response = logged_in_client.get(page)
        assert response.status_code == 200, f"Failed to access {page}"
        
        response_text = response.data.decode('utf-8')
        # Check for AI features script inclusion
        assert 'ai_features.js' in response_text, f"AI features script not included on {page}"
        
        # Check for AI loader div
        assert 'ai-loader' in response_text, f"AI loader not found on {page}"