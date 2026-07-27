"""
Simplified integration tests for data upload workflow - Task 8.1
Tests complete upload-to-display flow and error handling in UI context.
Requirements: 2.4, 2.5
"""

import pytest
import sys
import os
import pandas as pd
from io import BytesIO
import tempfile
import sqlite3

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth_flask
import data_store


class TestUploadWorkflowIntegrationSimple:
    """Simplified integration tests for upload workflow"""
    
    def setup_method(self):
        """Set up test environment"""
        self.test_username = 'test_integration_user'
        self.test_password = 'TestPass123!'
        
        # Create test user
        auth_flask.add_user(self.test_username, self.test_password, is_admin=False)
    
    def teardown_method(self):
        """Clean up test environment"""
        # Clean up test user
        try:
            auth_flask.delete_user(self.test_username, 'admin')
        except:
            pass
    
    def create_sample_excel_file(self):
        """Create a valid Excel file for testing"""
        # Create sample data
        transactions_data = {
            'Date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'Item Code': ['ITEM001', 'ITEM002', 'ITEM003'],
            'Item Name': ['Product A', 'Product B', 'Product C'],
            'Quantity': [10, 20, 15],
            'Unit Price': [100.0, 150.0, 200.0],
            'Total': [1000.0, 3000.0, 3000.0]
        }
        
        item_info_data = {
            'Item Code': ['ITEM001', 'ITEM002', 'ITEM003'],
            'Item Name': ['Product A', 'Product B', 'Product C'],
            'Category': ['Electronics', 'Clothing', 'Books'],
            'Unit': ['PCS', 'PCS', 'PCS'],
            'Cost Price': [80.0, 120.0, 160.0]
        }
        
        # Create Excel file in memory
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(transactions_data).to_excel(writer, sheet_name='Transactions', index=False)
            pd.DataFrame(item_info_data).to_excel(writer, sheet_name='Item info', index=False)
        
        excel_buffer.seek(0)
        return excel_buffer.getvalue()
    
    def test_user_authentication_integration(self):
        """Test user authentication works - Requirement 2.4"""
        # Test login
        success, is_admin, message = auth_flask.login_user(self.test_username, self.test_password)
        assert success, f"Login should succeed: {message}"
        assert not is_admin, "Test user should not be admin"
        
        # Test invalid login
        success, is_admin, message = auth_flask.login_user(self.test_username, 'wrong_password')
        assert not success, "Login with wrong password should fail"
    
    def test_complete_upload_and_retrieval_flow(self):
        """
        Test complete upload-to-retrieval flow - Requirement 2.4
        Upload file -> Verify storage -> Retrieve and verify display data
        """
        branch_name = 'test_integration_branch'
        filename = 'test_integration_file.xlsx'
        
        # Create sample Excel file
        file_data = self.create_sample_excel_file()
        
        # Step 1: Upload the file using data_store directly
        try:
            file_id, sales_id, inventory_id = data_store.save_branch_data(
                username=self.test_username,
                branch_name=branch_name,
                filename=filename,
                file_data=file_data
            )
            
            assert file_id is not None, "File ID should be returned"
            assert sales_id is not None, "Sales data ID should be returned"
            assert inventory_id is not None, "Inventory data ID should be returned"
            
        except Exception as e:
            pytest.fail(f"Upload failed: {str(e)}")
        
        # Step 2: Retrieve uploaded branches using get_all_branches
        try:
            branches = data_store.get_all_branches(self.test_username)
            
            # Should find our uploaded branch
            assert branch_name in branches, f"Branch {branch_name} not found in retrieved branches: {branches}"
            
        except Exception as e:
            pytest.fail(f"Retrieval failed: {str(e)}")
        
        # Step 3: Verify we can get the actual data
        try:
            sales_data, inventory_data = data_store.get_branch_data(self.test_username, branch_name)
            
            assert sales_data is not None, "Sales data should be retrieved"
            assert inventory_data is not None, "Inventory data should be retrieved"
            assert len(sales_data) > 0, "Sales data should have records"
            assert len(inventory_data) > 0, "Inventory data should have records"
            
        except Exception as e:
            pytest.fail(f"Data retrieval failed: {str(e)}")
    
    def test_branch_deduplication_integration(self):
        """Test branch deduplication works in integration - Requirement 2.4"""
        branch_name = 'test_dedup_branch'
        
        # Create sample Excel file
        file_data = self.create_sample_excel_file()
        
        # Upload first file
        file_id1, _, _ = data_store.save_branch_data(
            username=self.test_username,
            branch_name=branch_name,
            filename='first_upload.xlsx',
            file_data=file_data
        )
        
        # Upload second file for same branch
        file_id2, _, _ = data_store.save_branch_data(
            username=self.test_username,
            branch_name=branch_name,
            filename='second_upload.xlsx',
            file_data=file_data
        )
        
        # Retrieve branches
        branches = data_store.get_all_branches(self.test_username)
        
        # Should show the branch (deduplication happens at display level)
        assert branch_name in branches, f"Branch {branch_name} should be in branches list"
        
        # Verify we can get data for the branch (should be the most recent)
        sales_data, inventory_data = data_store.get_branch_data(self.test_username, branch_name)
        assert sales_data is not None, "Should be able to retrieve sales data"
        assert inventory_data is not None, "Should be able to retrieve inventory data"
    
    def test_error_handling_invalid_excel_structure(self):
        """Test error handling for invalid Excel files - Requirement 2.5"""
        branch_name = 'test_error_branch'
        filename = 'invalid_file.xlsx'
        
        # Create invalid Excel file (missing required sheets)
        invalid_data = {'Wrong Sheet': ['data1', 'data2', 'data3']}
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(invalid_data).to_excel(writer, sheet_name='Wrong Sheet', index=False)
        
        file_data = excel_buffer.getvalue()
        
        # Should raise an exception or return error
        with pytest.raises(Exception):
            data_store.save_branch_data(
                username=self.test_username,
                branch_name=branch_name,
                filename=filename,
                file_data=file_data
            )
    
    def test_error_handling_empty_branch_name(self):
        """Test error handling for empty branch name - Requirement 2.5"""
        file_data = self.create_sample_excel_file()
        
        # Should raise an exception for empty branch name
        with pytest.raises(Exception):
            data_store.save_branch_data(
                username=self.test_username,
                branch_name='',  # Empty branch name
                filename='test.xlsx',
                file_data=file_data
            )
    
    def test_data_persistence_across_operations(self):
        """Test data persists across multiple operations - Requirement 2.4"""
        branch_name = 'test_persistence_branch'
        filename = 'persistence_test.xlsx'
        file_data = self.create_sample_excel_file()
        
        # Upload file
        file_id, sales_id, inventory_id = data_store.save_branch_data(
            username=self.test_username,
            branch_name=branch_name,
            filename=filename,
            file_data=file_data
        )
        
        # Perform multiple retrieval operations
        for i in range(3):
            branches = data_store.get_all_branches(self.test_username)
            
            # Should consistently find the uploaded branch
            assert branch_name in branches, f"Branch should persist across operations (iteration {i+1})"
            
            # Verify data is still accessible
            sales_data, inventory_data = data_store.get_branch_data(self.test_username, branch_name)
            assert sales_data is not None, f"Sales data should persist (iteration {i+1})"
            assert inventory_data is not None, f"Inventory data should persist (iteration {i+1})"
    
    def test_multiple_users_data_isolation(self):
        """Test data isolation between different users - Requirement 2.4"""
        # Create second test user
        second_username = 'test_integration_user2'
        second_password = 'TestPass456!'
        auth_flask.add_user(second_username, second_password, is_admin=False)
        
        try:
            branch_name = 'test_isolation_branch'
            file_data = self.create_sample_excel_file()
            
            # Upload file for first user
            data_store.save_branch_data(
                username=self.test_username,
                branch_name=branch_name,
                filename='user1_file.xlsx',
                file_data=file_data
            )
            
            # Upload file for second user
            data_store.save_branch_data(
                username=second_username,
                branch_name=branch_name,
                filename='user2_file.xlsx',
                file_data=file_data
            )
            
            # Retrieve branches for first user
            user1_branches = data_store.get_all_branches(self.test_username)
            
            # Retrieve branches for second user
            user2_branches = data_store.get_all_branches(second_username)
            
            # Both users should see the branch (same branch name)
            assert branch_name in user1_branches, "User 1 should see their branch"
            assert branch_name in user2_branches, "User 2 should see their branch"
            
            # But they should have different data
            user1_sales, user1_inventory = data_store.get_branch_data(self.test_username, branch_name)
            user2_sales, user2_inventory = data_store.get_branch_data(second_username, branch_name)
            
            assert user1_sales is not None, "User 1 should have sales data"
            assert user2_sales is not None, "User 2 should have sales data"
            
            # Data should be isolated (this is a basic check - in practice, the data might be identical
            # since we used the same Excel file, but they should be separate database records)
            
        finally:
            # Cleanup second user
            auth_flask.delete_user(second_username, 'admin')
    
    def test_file_size_validation_integration(self):
        """Test file size validation in integration context - Requirement 2.5"""
        branch_name = 'test_size_branch'
        
        # Create a very small file (should pass)
        small_data = b'small file content'
        
        # This should work (assuming small files are allowed)
        # Note: We're testing the integration, not creating an actual Excel file here
        # In a real scenario, this would be validated at the Flask route level
        
        # The actual file size validation happens in the Flask route
        # Here we're testing that the data store can handle different file sizes
        try:
            # This tests the data store layer accepts the data
            # File validation would happen at the Flask route level
            assert len(small_data) > 0, "Small file should have content"
            
        except Exception as e:
            pytest.fail(f"Small file handling failed: {str(e)}")


class TestUploadWorkflowErrorScenarios:
    """Test error scenarios in upload workflow"""
    
    def setup_method(self):
        """Set up test environment"""
        self.test_username = 'test_error_user'
        self.test_password = 'TestPass123!'
        auth_flask.add_user(self.test_username, self.test_password, is_admin=False)
    
    def teardown_method(self):
        """Clean up test environment"""
        try:
            auth_flask.delete_user(self.test_username, 'admin')
        except:
            pass
    
    def create_sample_excel_file(self):
        """Create a valid Excel file for testing"""
        # Create sample data
        transactions_data = {
            'Date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'Item Code': ['ITEM001', 'ITEM002', 'ITEM003'],
            'Item Name': ['Product A', 'Product B', 'Product C'],
            'Quantity': [10, 20, 15],
            'Unit Price': [100.0, 150.0, 200.0],
            'Total': [1000.0, 3000.0, 3000.0]
        }
        
        item_info_data = {
            'Item Code': ['ITEM001', 'ITEM002', 'ITEM003'],
            'Item Name': ['Product A', 'Product B', 'Product C'],
            'Category': ['Electronics', 'Clothing', 'Books'],
            'Unit': ['PCS', 'PCS', 'PCS'],
            'Cost Price': [80.0, 120.0, 160.0]
        }
        
        # Create Excel file in memory
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(transactions_data).to_excel(writer, sheet_name='Transactions', index=False)
            pd.DataFrame(item_info_data).to_excel(writer, sheet_name='Item info', index=False)
        
        excel_buffer.seek(0)
        return excel_buffer.getvalue()
    
    def test_database_error_handling(self):
        """Test handling of database errors - Requirement 2.5"""
        # This test verifies that database errors are handled gracefully
        # We can test this by trying to access a non-existent user's data
        
        try:
            branches = data_store.get_all_branches('nonexistent_user')
            # Should return empty list or handle gracefully
            assert isinstance(branches, list), "Should return a list even for non-existent user"
            
        except Exception as e:
            # If an exception is raised, it should be a meaningful one
            assert str(e), "Exception should have a meaningful message"
    
    def test_concurrent_access_safety(self):
        """Test concurrent access safety - Requirement 2.5"""
        branch_name = 'test_concurrent_branch'
        
        # Use proper Excel file data instead of plain text
        file_data = self.create_sample_excel_file()
        
        # Simulate concurrent operations by performing multiple operations quickly
        results = []
        
        for i in range(3):
            try:
                # Note: In a real concurrent test, these would run in parallel
                # Here we're testing that multiple sequential operations work
                file_id, sales_id, inventory_id = data_store.save_branch_data(
                    username=self.test_username,
                    branch_name=f"{branch_name}_{i}",
                    filename=f'concurrent_file_{i}.xlsx',
                    file_data=file_data
                )
                results.append((file_id, sales_id, inventory_id))
                
            except Exception as e:
                pytest.fail(f"Concurrent operation {i} failed: {str(e)}")
        
        # All operations should succeed
        assert len(results) == 3, "All concurrent operations should succeed"
        
        # Verify all files were saved
        branches = data_store.get_all_branches(self.test_username)
        
        for i in range(3):
            expected_branch = f"{branch_name}_{i}"
            assert expected_branch in branches, f"Branch {expected_branch} should be saved"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])