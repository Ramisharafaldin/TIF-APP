"""
End-to-end integration testing and validation for data upload workflow - Task 8
Tests end-to-end upload workflow with real Excel files, UI display verification, and error scenarios.
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
from utils import validation


class TestEndToEndUploadValidation:
    """End-to-end integration testing and validation"""
    
    def setup_method(self):
        """Set up test environment"""
        self.test_username = 'test_e2e_user'
        self.test_password = 'TestPass123!'
        auth_flask.add_user(self.test_username, self.test_password, is_admin=False)
    
    def teardown_method(self):
        """Clean up test environment"""
        try:
            auth_flask.delete_user(self.test_username, 'admin')
        except:
            pass
    
    def create_real_excel_file(self, branch_name="TestBranch", num_transactions=100):
        """Create a realistic Excel file with substantial data"""
        import random
        from datetime import datetime, timedelta
        
        # Generate realistic transaction data
        base_date = datetime(2024, 1, 1)
        transactions_data = {
            'Date': [(base_date + timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d') for _ in range(num_transactions)],
            'Item Code': [f'ITEM{str(i).zfill(3)}' for i in range(1, num_transactions + 1)],
            'Item Name': [f'Product {chr(65 + (i % 26))}' for i in range(num_transactions)],
            'Quantity': [random.randint(1, 100) for _ in range(num_transactions)],
            'Unit Price': [round(random.uniform(10.0, 1000.0), 2) for _ in range(num_transactions)],
            'Total': []
        }
        
        # Calculate totals
        for i in range(num_transactions):
            total = transactions_data['Quantity'][i] * transactions_data['Unit Price'][i]
            transactions_data['Total'].append(round(total, 2))
        
        # Generate realistic item info data
        item_info_data = {
            'Item Code': [f'ITEM{str(i).zfill(3)}' for i in range(1, num_transactions + 1)],
            'Item Name': [f'Product {chr(65 + (i % 26))}' for i in range(num_transactions)],
            'Category': [random.choice(['Electronics', 'Clothing', 'Books', 'Food', 'Tools']) for _ in range(num_transactions)],
            'Unit': [random.choice(['PCS', 'KG', 'LTR', 'BOX', 'SET']) for _ in range(num_transactions)],
            'Cost Price': [round(random.uniform(5.0, 800.0), 2) for _ in range(num_transactions)]
        }
        
        # Create Excel file in memory
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(transactions_data).to_excel(writer, sheet_name='Transactions', index=False)
            pd.DataFrame(item_info_data).to_excel(writer, sheet_name='Item info', index=False)
        
        excel_buffer.seek(0)
        return excel_buffer.getvalue(), len(transactions_data['Date']), len(item_info_data['Item Code'])
    
    def test_end_to_end_upload_workflow_with_real_excel(self):
        """
        Test complete end-to-end upload workflow with realistic Excel files - Requirement 2.4
        """
        branch_name = 'RealBranch_E2E'
        filename = 'realistic_data.xlsx'
        
        # Create realistic Excel file with substantial data
        file_data, expected_transactions, expected_items = self.create_real_excel_file(branch_name, 50)
        
        # Step 1: Upload the file
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
        
        # Step 2: Verify file appears in branch list
        branches = data_store.get_all_branches(self.test_username)
        assert branch_name in branches, f"Branch {branch_name} should appear in branches list"
        
        # Step 3: Verify data was processed correctly
        sales_data, inventory_data = data_store.get_branch_data(self.test_username, branch_name)
        
        assert sales_data is not None, "Sales data should be retrieved"
        assert inventory_data is not None, "Inventory data should be retrieved"
        assert len(sales_data) == expected_transactions, f"Expected {expected_transactions} sales records, got {len(sales_data)}"
        assert len(inventory_data) == expected_items, f"Expected {expected_items} inventory records, got {len(inventory_data)}"
        
        # Step 4: Verify data integrity
        # Check that required columns exist (use actual column names from processing)
        # The data processing module transforms column names
        expected_sales_columns = ['sale_date', 'product_code', 'product_name', 'Last_on_hand', 'Unit_Price', 'Total']
        for col in expected_sales_columns:
            assert col in sales_data.columns, f"Sales data should have column: {col}"
        
        expected_inventory_columns = ['product_code', 'product_name', 'Category', 'Unit', 'inventory_value']
        for col in expected_inventory_columns:
            assert col in inventory_data.columns, f"Inventory data should have column: {col}"
        
        # Verify data types and values (use actual column names)
        assert sales_data['Last_on_hand'].dtype in ['int64', 'float64'], "Quantity should be numeric"
        assert sales_data['Unit_Price'].dtype in ['float64'], "Unit Price should be float"
        assert sales_data['Total'].dtype in ['float64'], "Total should be float"
        
        # Verify no null values in critical columns (use actual column names)
        assert not sales_data['product_code'].isnull().any(), "Product Code should not have null values"
        assert not inventory_data['product_code'].isnull().any(), "Product Code should not have null values"
    
    def test_ui_display_verification_simulation(self):
        """
        Test UI display verification through data retrieval - Requirement 2.4
        Simulates what the UI would display by testing data retrieval functions
        """
        branch_name = 'UITestBranch'
        filename = 'ui_test_data.xlsx'
        
        # Upload test data
        file_data, _, _ = self.create_real_excel_file(branch_name, 25)
        
        file_id, sales_id, inventory_id = data_store.save_branch_data(
            username=self.test_username,
            branch_name=branch_name,
            filename=filename,
            file_data=file_data
        )
        
        # Test what the UI would display
        
        # 1. Branch list for data management page
        branches = data_store.get_all_branches(self.test_username)
        assert branch_name in branches, "Branch should appear in UI branch list"
        
        # 2. Branch data for analysis pages
        sales_data, inventory_data = data_store.get_branch_data(self.test_username, branch_name)
        
        # Verify UI would have data to display
        assert len(sales_data) > 0, "UI should have sales data to display"
        assert len(inventory_data) > 0, "UI should have inventory data to display"
        
        # 3. Test data formatting for UI display
        # Verify data can be converted to display formats
        sales_dict = sales_data.to_dict('records')
        inventory_dict = inventory_data.to_dict('records')
        
        assert isinstance(sales_dict, list), "Sales data should convert to list for UI"
        assert isinstance(inventory_dict, list), "Inventory data should convert to list for UI"
        assert len(sales_dict) > 0, "Sales data list should not be empty"
        assert len(inventory_dict) > 0, "Inventory data list should not be empty"
        
        # 4. Test data summary for dashboard (use actual column names)
        total_sales = sales_data['Total'].sum()
        item_count = len(inventory_data)
        avg_price = sales_data['Unit_Price'].mean()
        
        assert total_sales > 0, "Total sales should be positive for UI display"
        assert item_count > 0, "Item count should be positive for UI display"
        assert avg_price > 0, "Average price should be positive for UI display"
    
    def test_error_scenarios_and_user_feedback(self):
        """
        Test error scenarios and user feedback mechanisms - Requirement 2.5
        """
        
        # Test 1: Invalid Excel structure
        invalid_data = {'Wrong Sheet': ['data1', 'data2', 'data3']}
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(invalid_data).to_excel(writer, sheet_name='Wrong Sheet', index=False)
        
        invalid_file_data = excel_buffer.getvalue()
        
        with pytest.raises(Exception) as exc_info:
            data_store.save_branch_data(
                username=self.test_username,
                branch_name='TestBranch',
                filename='invalid_structure.xlsx',
                file_data=invalid_file_data
            )
        
        # Verify error message is meaningful
        error_message = str(exc_info.value)
        assert 'Excel' in error_message or 'sheet' in error_message.lower(), "Error should mention Excel structure issue"
        
        # Test 2: Empty branch name
        file_data, _, _ = self.create_real_excel_file()
        
        with pytest.raises(Exception) as exc_info:
            data_store.save_branch_data(
                username=self.test_username,
                branch_name='',  # Empty branch name
                filename='test.xlsx',
                file_data=file_data
            )
        
        error_message = str(exc_info.value)
        assert 'branch' in error_message.lower() or 'فرع' in error_message, "Error should mention branch name issue"
        
        # Test 3: Invalid file extension
        with pytest.raises(Exception) as exc_info:
            data_store.save_branch_data(
                username=self.test_username,
                branch_name='TestBranch',
                filename='test.txt',  # Wrong extension
                file_data=file_data
            )
        
        error_message = str(exc_info.value)
        assert 'extension' in error_message.lower() or 'نوع' in error_message, "Error should mention file type issue"
        
        # Test 4: File too small
        tiny_file = b'tiny'
        
        with pytest.raises(Exception) as exc_info:
            data_store.save_branch_data(
                username=self.test_username,
                branch_name='TestBranch',
                filename='tiny.xlsx',
                file_data=tiny_file
            )
        
        error_message = str(exc_info.value)
        assert 'size' in error_message.lower() or 'حجم' in error_message, "Error should mention file size issue"
    
    def test_large_file_handling(self):
        """
        Test handling of larger Excel files - Requirement 2.4
        """
        branch_name = 'LargeFileBranch'
        filename = 'large_data.xlsx'
        
        # Create a larger Excel file (500 records)
        file_data, expected_transactions, expected_items = self.create_real_excel_file(branch_name, 500)
        
        # Should handle larger files successfully
        try:
            file_id, sales_id, inventory_id = data_store.save_branch_data(
                username=self.test_username,
                branch_name=branch_name,
                filename=filename,
                file_data=file_data
            )
            
            assert file_id is not None, "Large file should be processed successfully"
            
            # Verify data was processed correctly
            sales_data, inventory_data = data_store.get_branch_data(self.test_username, branch_name)
            
            assert len(sales_data) == expected_transactions, f"All {expected_transactions} transactions should be processed"
            assert len(inventory_data) == expected_items, f"All {expected_items} items should be processed"
            
        except Exception as e:
            pytest.fail(f"Large file processing failed: {str(e)}")
    
    def test_multiple_branch_workflow(self):
        """
        Test workflow with multiple branches - Requirement 2.4
        """
        branches_to_create = ['Branch_A', 'Branch_B', 'Branch_C']
        
        # Upload files for multiple branches
        for i, branch_name in enumerate(branches_to_create):
            file_data, _, _ = self.create_real_excel_file(branch_name, 20 + i * 10)
            
            file_id, sales_id, inventory_id = data_store.save_branch_data(
                username=self.test_username,
                branch_name=branch_name,
                filename=f'{branch_name}_data.xlsx',
                file_data=file_data
            )
            
            assert file_id is not None, f"Upload should succeed for {branch_name}"
        
        # Verify all branches appear in the list
        all_branches = data_store.get_all_branches(self.test_username)
        
        for branch_name in branches_to_create:
            assert branch_name in all_branches, f"Branch {branch_name} should appear in list"
        
        # Verify each branch has its own data
        for branch_name in branches_to_create:
            sales_data, inventory_data = data_store.get_branch_data(self.test_username, branch_name)
            
            assert sales_data is not None, f"Sales data should exist for {branch_name}"
            assert inventory_data is not None, f"Inventory data should exist for {branch_name}"
            assert len(sales_data) > 0, f"Sales data should not be empty for {branch_name}"
            assert len(inventory_data) > 0, f"Inventory data should not be empty for {branch_name}"
    
    def test_data_consistency_validation(self):
        """
        Test data consistency and validation - Requirement 2.5
        """
        branch_name = 'ConsistencyTestBranch'
        filename = 'consistency_test.xlsx'
        
        # Create Excel file with known data
        file_data, expected_transactions, expected_items = self.create_real_excel_file(branch_name, 30)
        
        # Upload and process
        file_id, sales_id, inventory_id = data_store.save_branch_data(
            username=self.test_username,
            branch_name=branch_name,
            filename=filename,
            file_data=file_data
        )
        
        # Retrieve and validate data consistency
        sales_data, inventory_data = data_store.get_branch_data(self.test_username, branch_name)
        
        # Test data consistency rules
        
        # 1. All item codes in sales should exist in inventory
        sales_item_codes = set(sales_data['product_code'].unique())
        inventory_item_codes = set(inventory_data['product_code'].unique())
        
        # Note: In our test data, we create matching item codes, so this should pass
        missing_items = sales_item_codes - inventory_item_codes
        assert len(missing_items) == 0, f"Sales data contains item codes not in inventory: {missing_items}"
        
        # 2. Totals should be calculated correctly (use actual column names)
        for _, row in sales_data.iterrows():
            expected_total = row['Last_on_hand'] * row['Unit_Price']
            actual_total = row['Total']
            # Allow for small floating point differences
            assert abs(expected_total - actual_total) < 0.01, f"Total calculation error for item {row['product_code']}"
        
        # 3. No negative quantities or prices (use actual column names)
        assert (sales_data['Last_on_hand'] >= 0).all(), "Quantities should not be negative"
        assert (sales_data['Unit_Price'] >= 0).all(), "Unit prices should not be negative"
        assert (inventory_data['inventory_value'] >= 0).all(), "Inventory values should not be negative"
        
        # 4. Required fields should not be empty (use actual column names)
        assert not sales_data['product_code'].isnull().any(), "Product codes should not be null"
        assert not sales_data['product_name'].isnull().any(), "Product names should not be null"
        assert not inventory_data['product_code'].isnull().any(), "Inventory product codes should not be null"
        assert not inventory_data['product_name'].isnull().any(), "Inventory product names should not be null"
    
    def test_performance_with_realistic_data(self):
        """
        Test performance with realistic data sizes - Requirement 2.4
        """
        import time
        
        branch_name = 'PerformanceTestBranch'
        filename = 'performance_test.xlsx'
        
        # Create moderately large file (200 records)
        file_data, expected_transactions, expected_items = self.create_real_excel_file(branch_name, 200)
        
        # Measure upload and processing time
        start_time = time.time()
        
        file_id, sales_id, inventory_id = data_store.save_branch_data(
            username=self.test_username,
            branch_name=branch_name,
            filename=filename,
            file_data=file_data
        )
        
        upload_time = time.time() - start_time
        
        # Measure retrieval time
        start_time = time.time()
        
        sales_data, inventory_data = data_store.get_branch_data(self.test_username, branch_name)
        
        retrieval_time = time.time() - start_time
        
        # Performance assertions (reasonable thresholds)
        assert upload_time < 30.0, f"Upload should complete within 30 seconds, took {upload_time:.2f}s"
        assert retrieval_time < 5.0, f"Retrieval should complete within 5 seconds, took {retrieval_time:.2f}s"
        
        # Verify data integrity after performance test
        assert len(sales_data) == expected_transactions, "All data should be processed correctly"
        assert len(inventory_data) == expected_items, "All data should be processed correctly"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])