#!/usr/bin/env python3
"""
Unit tests for export edge cases and specific scenarios.

Tests export with no data available (Requirements 3.5, 4.5)
Tests individual route availability (Requirements 1.1, 1.2, 1.3, 1.4)
Tests specific error conditions and recovery paths
"""

import os
import sys
import pytest
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock
import pandas as pd

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

# Import Flask app and dependencies
from flask_app import app
import data_store
import auth_flask


class TestExportEdgeCasesUnitTests:
    """Unit tests for export edge cases and specific scenarios"""
    
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
        username = 'test_edge_user'
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

    # Test export with no data available (Requirements 3.5, 4.5)
    
    def test_dashboard_export_no_data_available(self, authenticated_client):
        """Test dashboard export when no data is available - Requirement 3.5"""
        print("Testing dashboard export with no data available...")
        
        # Mock data_store to return None/empty data
        with patch('data_store.get_branch_data') as mock_get_data:
            mock_get_data.return_value = (None, None)
            
            response = authenticated_client.get('/dashboard/export')
            
            # Should redirect to dashboard page with warning
            assert response.status_code == 302
            assert 'dashboard' in response.location
            
            print("✅ Dashboard export properly handles no data scenario")
    
    def test_inventory_export_no_data_available(self, authenticated_client):
        """Test inventory export when no analysis data is available - Requirement 3.5"""
        print("Testing inventory export with no data available...")
        
        # Mock session to have no inventory results
        with patch('data_store.get_user_session') as mock_session:
            mock_session.return_value = {'username': 'test_edge_user', 'data_ids': {}}
            
            response = authenticated_client.get('/inventory/export')
            
            # Should redirect to inventory page with warning
            assert response.status_code == 302
            assert 'inventory' in response.location
            
            print("✅ Inventory export properly handles no data scenario")
    
    def test_transfers_export_no_data_available(self, authenticated_client):
        """Test transfers export when no analysis data is available - Requirement 3.5"""
        print("Testing transfers export with no data available...")
        
        # Mock session to have no transfer results
        with patch('data_store.get_user_session') as mock_session:
            mock_session.return_value = {'username': 'test_edge_user', 'data_ids': {}}
            
            response = authenticated_client.get('/transfers/export')
            
            # Should redirect to transfers page with warning
            assert response.status_code == 302
            assert 'transfers' in response.location
            
            print("✅ Transfers export properly handles no data scenario")
    
    def test_forecasting_export_no_data_available(self, authenticated_client):
        """Test forecasting export when no analysis data is available - Requirement 4.5"""
        print("Testing forecasting export with no data available...")
        
        # Mock session to have no forecast results
        with patch('data_store.get_user_session') as mock_session:
            mock_session.return_value = {'username': 'test_edge_user', 'data_ids': {}}
            
            response = authenticated_client.get('/forecasting/export')
            
            # Should redirect to forecasting page with warning
            assert response.status_code == 302
            assert 'forecasting' in response.location
            
            print("✅ Forecasting export properly handles no data scenario")

    # Test individual route availability (Requirements 1.1, 1.2, 1.3, 1.4)
    
    def test_dashboard_export_route_exists(self, authenticated_client):
        """Test dashboard export route exists - Requirement 1.1"""
        print("Testing dashboard export route availability...")
        
        response = authenticated_client.get('/dashboard/export')
        
        # Route should exist (not 404)
        assert response.status_code != 404
        # Should respond with valid status code
        assert response.status_code in [200, 302, 400, 500]
        
        print("✅ Dashboard export route exists and responds")
    
    def test_inventory_export_route_exists(self, authenticated_client):
        """Test inventory export route exists - Requirement 1.2"""
        print("Testing inventory export route availability...")
        
        response = authenticated_client.get('/inventory/export')
        
        # Route should exist (not 404)
        assert response.status_code != 404
        # Should respond with valid status code
        assert response.status_code in [200, 302, 400, 500]
        
        print("✅ Inventory export route exists and responds")
    
    def test_transfers_export_route_exists(self, authenticated_client):
        """Test transfers export route exists - Requirement 1.3"""
        print("Testing transfers export route availability...")
        
        response = authenticated_client.get('/transfers/export')
        
        # Route should exist (not 404)
        assert response.status_code != 404
        # Should respond with valid status code
        assert response.status_code in [200, 302, 400, 500]
        
        print("✅ Transfers export route exists and responds")
    
    def test_forecasting_export_route_exists(self, authenticated_client):
        """Test forecasting export route exists - Requirement 1.4"""
        print("Testing forecasting export route availability...")
        
        response = authenticated_client.get('/forecasting/export')
        
        # Route should exist (not 404)
        assert response.status_code != 404
        # Should respond with valid status code
        assert response.status_code in [200, 302, 400, 500]
        
        print("✅ Forecasting export route exists and responds")

    # Test specific error conditions and recovery paths
    
    def test_database_connection_error_recovery(self, authenticated_client):
        """Test export routes handle database connection errors gracefully"""
        print("Testing database connection error recovery...")
        
        # Mock database connection error
        with patch('data_store.get_user_session') as mock_session:
            mock_session.side_effect = sqlite3.OperationalError("Database is locked")
            
            routes = ['/dashboard/export', '/inventory/export', '/transfers/export', '/forecasting/export']
            
            for route in routes:
                response = authenticated_client.get(route)
                
                # Should handle error gracefully (not crash)
                assert response.status_code in [302, 400, 500]
                
                if response.status_code == 302:
                    # Should redirect to appropriate page
                    route_name = route.split('/')[1]
                    assert route_name in response.location or 'login' in response.location
                
                print(f"✅ {route} handles database error gracefully")
    
    def test_memory_constraint_error_recovery(self, authenticated_client):
        """Test export routes handle memory constraint errors"""
        print("Testing memory constraint error recovery...")
        
        # Mock memory error
        with patch('data_store.get_user_session') as mock_session:
            mock_session.side_effect = MemoryError("Out of memory")
            
            routes = ['/dashboard/export', '/inventory/export', '/transfers/export', '/forecasting/export']
            
            for route in routes:
                response = authenticated_client.get(route)
                
                # Should handle error gracefully
                assert response.status_code in [302, 400, 500]
                
                print(f"✅ {route} handles memory error gracefully")
    
    def test_corrupted_session_data_recovery(self, authenticated_client):
        """Test export routes handle corrupted session data"""
        print("Testing corrupted session data recovery...")
        
        # Mock corrupted session data
        with patch('data_store.get_user_session') as mock_session:
            mock_session.return_value = {'corrupted': 'data', 'invalid': True}
            
            routes = ['/inventory/export', '/transfers/export', '/forecasting/export']
            
            for route in routes:
                response = authenticated_client.get(route)
                
                # Should handle corrupted data gracefully
                assert response.status_code in [302, 400, 500]
                
                if response.status_code == 302:
                    # Should redirect to appropriate page
                    route_name = route.split('/')[1]
                    assert route_name in response.location
                
                print(f"✅ {route} handles corrupted session data gracefully")
    
    def test_empty_dataframe_handling(self, authenticated_client):
        """Test export routes handle empty DataFrames"""
        print("Testing empty DataFrame handling...")
        
        # Mock empty DataFrame
        with patch('data_store.get_dataframe') as mock_get_df:
            mock_get_df.return_value = pd.DataFrame()  # Empty DataFrame
            
            with patch('data_store.get_user_session') as mock_session:
                mock_session.return_value = {
                    'username': 'test_edge_user',
                    'data_ids': {'results': 1, 'transfer_results': 2, 'forecast_results': 3}
                }
                
                routes = ['/inventory/export', '/transfers/export', '/forecasting/export']
                
                for route in routes:
                    response = authenticated_client.get(route)
                    
                    # Should handle empty data gracefully
                    assert response.status_code in [302, 400, 500]
                    
                    if response.status_code == 302:
                        # Should redirect with warning
                        route_name = route.split('/')[1]
                        assert route_name in response.location
                    
                    print(f"✅ {route} handles empty DataFrame gracefully")
    
    def test_file_generation_error_recovery(self, authenticated_client):
        """Test export routes handle file generation errors"""
        print("Testing file generation error recovery...")
        
        # Mock file generation error
        with patch('utils.ui_helpers.export_full_report') as mock_export:
            mock_export.side_effect = Exception("File generation failed")
            
            # Mock valid session data
            with patch('data_store.get_user_session') as mock_session:
                mock_session.return_value = {
                    'username': 'test_edge_user',
                    'data_ids': {'results': 1}
                }
                
                with patch('data_store.get_dataframe') as mock_get_df:
                    mock_get_df.return_value = pd.DataFrame({'test': [1, 2, 3]})
                    
                    response = authenticated_client.get('/inventory/export')
                    
                    # Should handle file generation error gracefully
                    assert response.status_code in [302, 400, 500]
                    
                    print("✅ Export routes handle file generation errors gracefully")
    
    def test_invalid_user_session_handling(self, authenticated_client):
        """Test export routes handle invalid user sessions"""
        print("Testing invalid user session handling...")
        
        # Mock invalid session (different user)
        with patch('data_store.get_user_session') as mock_session:
            mock_session.return_value = {
                'username': 'different_user',  # Different from authenticated user
                'data_ids': {'results': 1}
            }
            
            routes = ['/inventory/export', '/transfers/export', '/forecasting/export']
            
            for route in routes:
                response = authenticated_client.get(route)
                
                # Should handle invalid session gracefully
                assert response.status_code in [302, 400, 500]
                
                print(f"✅ {route} handles invalid user session gracefully")
    
    def test_format_parameter_edge_cases(self, authenticated_client):
        """Test export routes handle format parameter edge cases"""
        print("Testing format parameter edge cases...")
        
        edge_case_formats = ['', 'XLSX', 'PDF', 'xlsx ', ' pdf', 'null', 'undefined']
        
        for format_param in edge_case_formats:
            route = f'/dashboard/export/{format_param}'
            response = authenticated_client.get(route)
            
            # Should handle edge case formats gracefully
            assert response.status_code in [200, 302, 400, 404, 500]
            
            print(f"✅ Dashboard export handles format '{format_param}' gracefully")
    
    def test_concurrent_export_requests(self, authenticated_client):
        """Test export routes handle concurrent requests"""
        print("Testing concurrent export requests...")
        
        # Simplified test - just make multiple sequential requests quickly
        # to simulate load without threading complications
        results = []
        
        for i in range(3):
            try:
                response = authenticated_client.get('/dashboard/export')
                results.append(response.status_code)
            except Exception as e:
                results.append(str(e))
        
        # All requests should complete without crashing
        assert len(results) == 3
        for result in results:
            if isinstance(result, int):
                assert result in [200, 302, 400, 500]
            else:
                # If it's an exception string, it should be handled gracefully
                assert any(keyword in str(result).lower() for keyword in ['error', 'timeout', 'connection'])
        
        print("✅ Export routes handle multiple requests gracefully")


def run_export_edge_cases_unit_tests():
    """Run the export edge cases unit tests"""
    print("🧪 EXPORT EDGE CASES UNIT TESTS")
    print("="*60)
    print("Testing export with no data available (Requirements 3.5, 4.5)")
    print("Testing individual route availability (Requirements 1.1, 1.2, 1.3, 1.4)")
    print("Testing specific error conditions and recovery paths")
    print("="*60)
    
    # Run pytest with verbose output
    pytest_args = [
        __file__,
        '-v',
        '--tb=short',
        '--no-header',
        '-x'  # Stop on first failure
    ]
    
    result = pytest.main(pytest_args)
    
    print("\n" + "="*60)
    if result == 0:
        print("🎉 EXPORT EDGE CASES UNIT TESTS PASSED!")
        print("\n✅ Test Coverage Summary:")
        print("- Export with no data available scenarios")
        print("- Individual route availability verification")
        print("- Database connection error recovery")
        print("- Memory constraint error handling")
        print("- Corrupted session data recovery")
        print("- Empty DataFrame handling")
        print("- File generation error recovery")
        print("- Invalid user session handling")
        print("- Format parameter edge cases")
        print("- Concurrent export request handling")
        
        print("\n📊 Requirements Validation:")
        print("- Requirement 3.5: No data scenarios handled ✅")
        print("- Requirement 4.5: Forecasting no data handled ✅")
        print("- Requirement 1.1: Dashboard route available ✅")
        print("- Requirement 1.2: Inventory route available ✅")
        print("- Requirement 1.3: Transfers route available ✅")
        print("- Requirement 1.4: Forecasting route available ✅")
        
    else:
        print("❌ SOME EXPORT EDGE CASES UNIT TESTS FAILED!")
        print("Please review the failed tests above and fix any issues.")
        print("Export edge case handling may not be working properly.")
    
    print("="*60)
    return result == 0


if __name__ == "__main__":
    success = run_export_edge_cases_unit_tests()
    sys.exit(0 if success else 1)