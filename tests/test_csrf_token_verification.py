"""
Test CSRF token presence and validation across all AI-enabled pages.

This test verifies that the CSRF token meta tag is properly rendered on all pages
that use AI features, ensuring the JavaScript can access it without errors.

Requirements: 3.1, 3.2
"""

import pytest
import re
import sys
import os
from bs4 import BeautifulSoup

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask_app import app
import auth_flask


@pytest.fixture
def client():
    """Create test client"""
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


class TestCSRFTokenVerification:
    """Test CSRF token presence on all AI-enabled pages - Requirements 3.1, 3.2"""
    
    def test_csrf_token_on_dashboard_page(self, logged_in_client):
        """Test CSRF token presence on dashboard page - Requirement 3.1"""
        response = logged_in_client.get('/dashboard')
        assert response.status_code == 200
        
        # Parse HTML content
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Find CSRF token meta tag
        csrf_meta = soup.find('meta', {'name': 'csrf-token'})
        assert csrf_meta is not None, "CSRF token meta tag not found on dashboard page"
        
        # Validate token content
        token_content = csrf_meta.get('content')
        assert token_content is not None, "CSRF token content is None on dashboard page"
        assert token_content.strip() != '', "CSRF token content is empty on dashboard page"
        assert len(token_content) > 10, "CSRF token appears too short on dashboard page"
        
        # Validate token format (should be alphanumeric with possible special chars)
        assert re.match(r'^[A-Za-z0-9._-]+$', token_content), "CSRF token has invalid format on dashboard page"
    
    def test_csrf_token_on_inventory_page(self, logged_in_client):
        """Test CSRF token presence on inventory page - Requirement 3.1"""
        response = logged_in_client.get('/inventory')
        assert response.status_code == 200
        
        # Parse HTML content
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Find CSRF token meta tag
        csrf_meta = soup.find('meta', {'name': 'csrf-token'})
        assert csrf_meta is not None, "CSRF token meta tag not found on inventory page"
        
        # Validate token content
        token_content = csrf_meta.get('content')
        assert token_content is not None, "CSRF token content is None on inventory page"
        assert token_content.strip() != '', "CSRF token content is empty on inventory page"
        assert len(token_content) > 10, "CSRF token appears too short on inventory page"
        
        # Validate token format
        assert re.match(r'^[A-Za-z0-9._-]+$', token_content), "CSRF token has invalid format on inventory page"
    
    def test_csrf_token_on_transfers_page(self, logged_in_client):
        """Test CSRF token presence on transfers page - Requirement 3.1"""
        response = logged_in_client.get('/transfers')
        assert response.status_code == 200
        
        # Parse HTML content
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Find CSRF token meta tag
        csrf_meta = soup.find('meta', {'name': 'csrf-token'})
        assert csrf_meta is not None, "CSRF token meta tag not found on transfers page"
        
        # Validate token content
        token_content = csrf_meta.get('content')
        assert token_content is not None, "CSRF token content is None on transfers page"
        assert token_content.strip() != '', "CSRF token content is empty on transfers page"
        assert len(token_content) > 10, "CSRF token appears too short on transfers page"
        
        # Validate token format
        assert re.match(r'^[A-Za-z0-9._-]+$', token_content), "CSRF token has invalid format on transfers page"
    
    def test_csrf_token_on_forecasting_page(self, logged_in_client):
        """Test CSRF token presence on forecasting page - Requirement 3.1"""
        response = logged_in_client.get('/forecasting')
        assert response.status_code == 200
        
        # Parse HTML content
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Find CSRF token meta tag
        csrf_meta = soup.find('meta', {'name': 'csrf-token'})
        assert csrf_meta is not None, "CSRF token meta tag not found on forecasting page"
        
        # Validate token content
        token_content = csrf_meta.get('content')
        assert token_content is not None, "CSRF token content is None on forecasting page"
        assert token_content.strip() != '', "CSRF token content is empty on forecasting page"
        assert len(token_content) > 10, "CSRF token appears too short on forecasting page"
        
        # Validate token format
        assert re.match(r'^[A-Za-z0-9._-]+$', token_content), "CSRF token has invalid format on forecasting page"
    
    def test_csrf_token_consistency_across_pages(self, logged_in_client):
        """Test CSRF token consistency across all AI-enabled pages - Requirement 3.2"""
        pages = ['/dashboard', '/inventory', '/transfers', '/forecasting']
        tokens = []
        
        for page in pages:
            response = logged_in_client.get(page)
            assert response.status_code == 200, f"Failed to access {page}"
            
            # Parse HTML content
            soup = BeautifulSoup(response.data, 'html.parser')
            
            # Find CSRF token meta tag
            csrf_meta = soup.find('meta', {'name': 'csrf-token'})
            assert csrf_meta is not None, f"CSRF token meta tag not found on {page}"
            
            token_content = csrf_meta.get('content')
            assert token_content is not None, f"CSRF token content is None on {page}"
            assert token_content.strip() != '', f"CSRF token content is empty on {page}"
            
            tokens.append(token_content)
        
        # All tokens should be the same within the same session
        assert len(set(tokens)) == 1, "CSRF tokens are not consistent across pages in the same session"
    
    def test_csrf_token_meta_tag_placement(self, logged_in_client):
        """Test that CSRF token meta tag is properly placed in HTML head section - Requirement 3.1"""
        response = logged_in_client.get('/dashboard')
        assert response.status_code == 200
        
        # Parse HTML content
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Find head section
        head = soup.find('head')
        assert head is not None, "HTML head section not found"
        
        # Find CSRF token meta tag within head
        csrf_meta = head.find('meta', {'name': 'csrf-token'})
        assert csrf_meta is not None, "CSRF token meta tag not found in HTML head section"
        
        # Verify it's not in the body
        body = soup.find('body')
        if body:
            csrf_in_body = body.find('meta', {'name': 'csrf-token'})
            assert csrf_in_body is None, "CSRF token meta tag should not be in body section"
    
    def test_csrf_token_javascript_accessibility(self, logged_in_client):
        """Test that CSRF token can be accessed by JavaScript selector - Requirement 3.2"""
        response = logged_in_client.get('/inventory')
        assert response.status_code == 200
        
        # Parse HTML content
        soup = BeautifulSoup(response.data, 'html.parser')
        
        # Find CSRF token meta tag using the same selector as JavaScript
        csrf_meta = soup.select('meta[name="csrf-token"]')
        assert len(csrf_meta) == 1, "CSRF token meta tag not found with JavaScript selector"
        
        # Verify the tag has the correct attributes
        meta_tag = csrf_meta[0]
        assert meta_tag.get('name') == 'csrf-token', "Meta tag name attribute is incorrect"
        assert meta_tag.get('content') is not None, "Meta tag content attribute is missing"
        assert meta_tag.get('content').strip() != '', "Meta tag content attribute is empty"
    
    def test_ai_features_script_inclusion(self, logged_in_client):
        """Test that AI features JavaScript is included on all AI-enabled pages - Requirement 3.2"""
        pages = ['/dashboard', '/inventory', '/transfers', '/forecasting']
        
        for page in pages:
            response = logged_in_client.get(page)
            assert response.status_code == 200, f"Failed to access {page}"
            
            # Check for AI features script inclusion
            assert b'ai_features.js' in response.data, f"AI features script not included on {page}"
            
            # Check for AI loader div
            assert b'ai-loader' in response.data, f"AI loader not found on {page}"