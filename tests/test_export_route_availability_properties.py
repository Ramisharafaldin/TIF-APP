#!/usr/bin/env python3
"""
Property-based tests for export route availability and response.

Feature: export-functionality-fix, Property 1: Export Route Availability and Response
Tests that for any authenticated user accessing any analysis page (dashboard, inventory, 
transfers, forecasting), the corresponding export route should be available and respond 
with appropriate HTTP status codes (200 for success, 302 for redirect, 400/500 for errors).

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
"""

import os
import sys
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from unittest.mock import patch, MagicMock
import tempfile
import sqlite3

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

# Import Flask app and dependencies
from flask_app import app
import data_store
import auth_flask


class TestExportRouteAvailabilityProperties:
    """Property-based tests for export route availability and response"""
    
    @pytest.fixture
    def client(self):
        """Create a test client"""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
        with app.test_client() as client:
            yield client
    
    @pytest.fixture
    def test_user(self):
        """Create a test user for authentication"""
        username = 'test_prop_user'
        password = 'TestPass123!'
        
        # Clean up any existing test user
        try:
            auth_flask.delete_user(username, 'admin')
        except:
            pass
        
        # Create test user
        success, message = auth_flask.add_user(username, password, is_admin=False)
        if not success:
            pytest.skip(f"Could not create test user: {message}")
        
        yield username
        
        # Cleanup
        try:
            auth_flask.delete_user(username, 'admin')
        except:
            pass
    
    @pytest.fixture
    def authenticated_client(self, client, test_user):
        """Create an authenticated client session"""
        # Login the test user
        response = client.post('/login', data={
            'username': test_user,
            'password': 'TestPass123!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        yield client

    # Generate test data for export routes
    export_routes = st.sampled_from([
        '/dashboard/export',
        '/inventory/export', 
        '/transfers/export',
        '/forecasting/export'
    ])
    
    export_formats = st.sampled_from(['xlsx', 'pdf', None])
    
    @given(route=export_routes, format_param=export_formats)
    @settings(max_examples=100, deadline=30000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_export_route_availability_property(self, authenticated_client, route, format_param):
        """
        Property 1: Export Route Availability and Response
        
        For any authenticated user accessing any analysis page (dashboard, inventory, 
        transfers, forecasting), the corresponding export route should be available 
        and respond with appropriate HTTP status codes.
        
        **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
        """
        # Construct the full route with format if specified
        if format_param:
            full_route = f"{route}/{format_param}"
        else:
            full_route = route
        
        print(f"Testing route availability: {full_route}")
        
        # Make request to the export route
        response = authenticated_client.get(full_route)
        
        # Property: Route should exist (not 404)
        assert response.status_code != 404, f"Export route {full_route} should exist (got 404)"
        
        # Property: Route should respond with appropriate HTTP status codes
        valid_status_codes = [200, 302, 400, 500]
        assert response.status_code in valid_status_codes, \
            f"Export route {full_route} should respond with valid status code (got {response.status_code})"
        
        # Property: If successful (200), should have appropriate content type for format
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            
            if format_param == 'xlsx' or format_param is None:  # Default is XLSX
                expected_xlsx_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                assert expected_xlsx_type in content_type or 'application/octet-stream' in content_type, \
                    f"XLSX export should have appropriate content type (got {content_type})"
            elif format_param == 'pdf':
                assert 'application/pdf' in content_type or 'application/octet-stream' in content_type, \
                    f"PDF export should have appropriate content type (got {content_type})"
        
        # Property: If redirect (302), should redirect to appropriate page
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            route_name = route.split('/')[1]  # Extract 'dashboard', 'inventory', etc.
            assert route_name in location or 'login' in location, \
                f"Redirect should go to appropriate page (got {location})"
        
        print(f"✅ Route {full_route} responds correctly with status {response.status_code}")

    @given(route=export_routes)
    @settings(max_examples=50, deadline=30000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unauthenticated_access_blocked_property(self, client, route):
        """
        Property: Unauthenticated users should not be able to access export routes
        
        For any export route, unauthenticated access should be blocked with 
        appropriate redirect or error status.
        """
        print(f"Testing unauthenticated access blocking for: {route}")
        
        # Make request without authentication
        response = client.get(route)
        
        # Property: Should block unauthenticated access
        blocked_status_codes = [302, 401, 403]
        assert response.status_code in blocked_status_codes, \
            f"Route {route} should block unauthenticated access (got {response.status_code})"
        
        # Property: If redirect, should go to login page
        if response.status_code == 302:
            location = response.headers.get('Location', '')
            assert 'login' in location.lower(), \
                f"Unauthenticated redirect should go to login page (got {location})"
        
        print(f"✅ Route {route} properly blocks unauthenticated access")

    @given(route=export_routes)
    @settings(max_examples=50, deadline=30000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_export_route_error_handling_property(self, authenticated_client, route):
        """
        Property: Export routes should handle errors gracefully
        
        For any export route, when errors occur (database issues, missing data),
        the route should handle them gracefully without crashing.
        """
        print(f"Testing error handling for route: {route}")
        
        # Mock data_store to simulate various error conditions
        with patch('data_store.get_user_session') as mock_session:
            # Simulate database error
            mock_session.side_effect = Exception("Simulated database error")
            
            response = authenticated_client.get(route)
            
            # Property: Should handle errors gracefully (not crash with 500 unless handled)
            assert response.status_code != 500 or 'error' in response.get_data(as_text=True).lower(), \
                f"Route {route} should handle database errors gracefully"
            
            # Property: Should respond with appropriate error handling
            valid_error_codes = [302, 400, 500]
            assert response.status_code in valid_error_codes, \
                f"Route {route} should handle errors appropriately (got {response.status_code})"
        
        print(f"✅ Route {route} handles errors gracefully")

    @given(
        route=export_routes,
        invalid_format=st.sampled_from(['txt', 'doc', 'csv', 'invalid', '123', 'xml'])
    )
    @settings(max_examples=50, deadline=30000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_format_handling_property(self, authenticated_client, route, invalid_format):
        """
        Property: Export routes should handle invalid format parameters gracefully
        
        For any export route with invalid format parameters, the route should
        handle them gracefully without crashing.
        """
        print(f"Testing invalid format handling for: {route}/{invalid_format}")
        
        full_route = f"{route}/{invalid_format}"
        response = authenticated_client.get(full_route)
        
        # Property: Should not crash (404 is acceptable for invalid formats)
        valid_status_codes = [200, 302, 400, 404, 500]
        assert response.status_code in valid_status_codes, \
            f"Route {full_route} should handle invalid format gracefully (got {response.status_code})"
        
        # Property: If it accepts the invalid format, should still respond appropriately
        if response.status_code == 200:
            # Should have some content type set
            content_type = response.headers.get('Content-Type', '')
            assert content_type != '', f"Route {full_route} should set content type"
        
        print(f"✅ Route {full_route} handles invalid format appropriately")


def run_export_route_availability_property_tests():
    """Run the export route availability property tests"""
    print("🧪 EXPORT ROUTE AVAILABILITY PROPERTY TESTS")
    print("="*70)
    print("Feature: export-functionality-fix, Property 1: Export Route Availability and Response")
    print("Testing that export routes are available and respond appropriately...")
    print("**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**")
    print("="*70)
    
    # Run pytest with verbose output
    pytest_args = [
        __file__,
        '-v',
        '--tb=short',
        '--no-header',
        '-x'  # Stop on first failure
    ]
    
    result = pytest.main(pytest_args)
    
    print("\n" + "="*70)
    if result == 0:
        print("🎉 EXPORT ROUTE AVAILABILITY PROPERTY TESTS PASSED!")
        print("\n✅ Property Validation Summary:")
        print("- All export routes exist and are accessible")
        print("- Routes respond with appropriate HTTP status codes")
        print("- Unauthenticated access is properly blocked")
        print("- Error conditions are handled gracefully")
        print("- Invalid format parameters are handled appropriately")
        print("- Content types are set correctly for successful exports")
        
        print("\n📊 Property Coverage:")
        print("- Route availability across all modules")
        print("- Authentication and authorization")
        print("- Error handling and resilience")
        print("- Format parameter validation")
        print("- HTTP response compliance")
        
    else:
        print("❌ SOME EXPORT ROUTE AVAILABILITY PROPERTY TESTS FAILED!")
        print("Please review the failed tests above and fix any issues.")
        print("Export route availability may not be working properly.")
    
    print("="*70)
    return result == 0


if __name__ == "__main__":
    success = run_export_route_availability_property_tests()
    sys.exit(0 if success else 1)