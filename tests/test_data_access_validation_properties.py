"""
Property-based tests for data access validation.

Feature: gemini-api-integration
Tests that query processing validates user access to requested data types.
"""
import pytest
import logging
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import patch, MagicMock
import pandas as pd
from typing import Dict, List

# Import the modules to test
from utils.query_processor import QueryProcessor
from datetime import datetime


class TestDataAccessValidationProperties:
    """
    Property-based tests for data access validation.
    
    **Validates: Requirements 3.3**
    """
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create mock AI service
        self.mock_ai_service = MagicMock()
        
        # Create mock data store
        self.mock_data_store = MagicMock()
        
        # Initialize query processor
        self.processor = QueryProcessor(self.mock_ai_service, self.mock_data_store)
    
    # Strategy for generating valid usernames
    @st.composite
    def valid_usernames(draw):
        """Generate valid usernames."""
        return draw(st.text(
            min_size=1, 
            max_size=20, 
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))
        ).filter(lambda x: len(x.strip()) > 0))
    
    # Strategy for generating data type requests
    @st.composite
    def data_type_requests(draw):
        """Generate lists of data types that might be requested."""
        valid_data_types = [
            'inventory_data', 'stock_quantities', 'branch_data',
            'sales_data', 'revenue_data', 'historical_data', 'alert_data'
        ]
        
        invalid_data_types = [
            'admin_data', 'user_credentials', 'system_config',
            'financial_records', 'personal_info', 'audit_logs'
        ]
        
        # Mix of valid and potentially invalid data types
        all_types = valid_data_types + invalid_data_types
        
        # Generate a list of 1-5 data types
        num_types = draw(st.integers(min_value=1, max_value=5))
        return draw(st.lists(
            st.sampled_from(all_types),
            min_size=num_types,
            max_size=num_types,
            unique=True
        ))
    
    @given(
        user=valid_usernames(),
        requested_data=data_type_requests()
    )
    @settings(max_examples=100, deadline=5000)
    def test_data_access_validation_consistency(self, user, requested_data):
        """
        Feature: gemini-api-integration, Property 7: Data Access Validation
        For any query processing request, user permissions should be validated 
        before accessing requested data, and only accessible data should be returned.
        
        **Validates: Requirements 3.3**
        """
        # Mock data store to return branches for valid users
        self.mock_data_store.get_all_branches.return_value = ['Branch A', 'Branch B']
        
        # Test data access validation
        access_result = self.processor.validate_data_access(user, requested_data)
        
        # Verify that validation returns a boolean
        assert isinstance(access_result, bool), f"Data access validation should return boolean for user: {user}, data: {requested_data}"
        
        # Verify that the data store was called to check user access
        self.mock_data_store.get_all_branches.assert_called_with(user)
        
        # If access is granted, user should have valid branches
        if access_result:
            # Verify that only valid data types are in the request
            valid_data_types = [
                'inventory_data', 'stock_quantities', 'branch_data',
                'sales_data', 'revenue_data', 'historical_data', 'alert_data'
            ]
            
            for data_type in requested_data:
                assert data_type in valid_data_types, f"Granted access should only be for valid data types, got: {data_type}"
    
    @given(user=valid_usernames())
    @settings(max_examples=50, deadline=5000)
    def test_user_with_no_branches_denied_access(self, user):
        """
        Feature: gemini-api-integration, Property 7: Data Access Validation
        For any user with no accessible branches, data access should be denied
        regardless of the requested data types.
        
        **Validates: Requirements 3.3**
        """
        # Mock data store to return no branches for user
        self.mock_data_store.get_all_branches.return_value = []
        
        # Test with valid data types
        valid_data_types = ['inventory_data', 'sales_data']
        access_result = self.processor.validate_data_access(user, valid_data_types)
        
        # Access should be denied for users with no branches
        assert access_result is False, f"Users with no branches should be denied access: {user}"
        
        # Verify that the data store was called
        self.mock_data_store.get_all_branches.assert_called_with(user)
    
    @given(
        user=valid_usernames(),
        requested_data=st.lists(
            st.sampled_from(['admin_data', 'user_credentials', 'system_config', 'financial_records']),
            min_size=1,
            max_size=3,
            unique=True
        )
    )
    @settings(max_examples=50, deadline=5000)
    def test_invalid_data_types_denied_access(self, user, requested_data):
        """
        Feature: gemini-api-integration, Property 7: Data Access Validation
        For any request containing invalid/unauthorized data types, access should
        be denied even if the user has valid branches.
        
        **Validates: Requirements 3.3**
        """
        # Mock data store to return valid branches for user
        self.mock_data_store.get_all_branches.return_value = ['Branch A', 'Branch B']
        
        # Test data access validation with invalid data types
        access_result = self.processor.validate_data_access(user, requested_data)
        
        # Access should be denied for invalid data types
        assert access_result is False, f"Invalid data types should be denied access for user: {user}, data: {requested_data}"
    
    @given(user=valid_usernames())
    @settings(max_examples=50, deadline=5000)
    def test_valid_data_types_granted_access(self, user):
        """
        Feature: gemini-api-integration, Property 7: Data Access Validation
        For any user with valid branches requesting only valid data types,
        access should be granted.
        
        **Validates: Requirements 3.3**
        """
        # Mock data store to return valid branches for user
        self.mock_data_store.get_all_branches.return_value = ['Branch A', 'Branch B']
        
        # Test with only valid data types
        valid_data_types = ['inventory_data', 'sales_data', 'branch_data']
        access_result = self.processor.validate_data_access(user, valid_data_types)
        
        # Access should be granted for valid users with valid data types
        assert access_result is True, f"Valid users with valid data types should be granted access: {user}"
        
        # Verify that the data store was called
        self.mock_data_store.get_all_branches.assert_called_with(user)
    
    def test_empty_user_denied_access(self):
        """
        Feature: gemini-api-integration, Property 7: Data Access Validation
        For any empty or None user, data access should be denied.
        
        **Validates: Requirements 3.3**
        """
        valid_data_types = ['inventory_data', 'sales_data']
        
        # Test with empty user
        access_result = self.processor.validate_data_access("", valid_data_types)
        assert access_result is False, "Empty user should be denied access"
        
        # Test with None user
        access_result = self.processor.validate_data_access(None, valid_data_types)
        assert access_result is False, "None user should be denied access"
    
    @given(user=valid_usernames())
    @settings(max_examples=30, deadline=5000)
    def test_data_store_error_denies_access(self, user):
        """
        Feature: gemini-api-integration, Property 7: Data Access Validation
        For any data store error during validation, access should be denied
        as a security precaution.
        
        **Validates: Requirements 3.3**
        """
        # Mock data store to raise an exception
        self.mock_data_store.get_all_branches.side_effect = Exception("Database connection error")
        
        valid_data_types = ['inventory_data', 'sales_data']
        access_result = self.processor.validate_data_access(user, valid_data_types)
        
        # Access should be denied when data store errors occur
        assert access_result is False, f"Data store errors should deny access for user: {user}"
    
    @given(
        user=valid_usernames(),
        requested_data=data_type_requests()
    )
    @settings(max_examples=50, deadline=5000)
    def test_query_execution_respects_access_validation(self, user, requested_data):
        """
        Feature: gemini-api-integration, Property 7: Data Access Validation
        For any query execution, if data access validation fails, the query
        should not be executed and should return an access denied error.
        
        **Validates: Requirements 3.3**
        """
        # Create a query intent that requires the requested data
        intent = {
            'query_type': 'stock_levels',
            'data_requirements': requested_data,
            'parameters': {}
        }
        
        # Mock data store behavior based on whether access should be granted
        has_invalid_types = any(
            data_type not in ['inventory_data', 'stock_quantities', 'branch_data', 
                             'sales_data', 'revenue_data', 'historical_data', 'alert_data']
            for data_type in requested_data
        )
        
        if has_invalid_types:
            # Should deny access for invalid data types
            self.mock_data_store.get_all_branches.return_value = ['Branch A']
        else:
            # Grant access for valid data types
            self.mock_data_store.get_all_branches.return_value = ['Branch A']
            # Mock successful data retrieval
            mock_inventory = pd.DataFrame({
                'product_code': ['P001', 'P002'],
                'Last_on_hand': [50, 25]
            })
            mock_sales = pd.DataFrame({
                'product_code': ['P001', 'P002'],
                'revenue': [1000, 500]
            })
            self.mock_data_store.get_branch_data.return_value = (mock_sales, mock_inventory)
        
        # Execute the query
        result = self.processor.execute_data_query(intent, user)
        
        # Verify result structure
        assert isinstance(result, dict), f"Query result should be a dictionary for user: {user}"
        assert 'success' in result, f"Query result should contain success field for user: {user}"
        
        # If access should be denied, verify the query was not executed
        if has_invalid_types:
            assert result['success'] is False, f"Query should fail for invalid data types: {requested_data}"
            assert 'error' in result, f"Failed query should contain error message for user: {user}"
            assert 'Access denied' in result['error'], f"Error should indicate access denied for user: {user}"
        else:
            # For valid data types with valid user, query should succeed
            # (Note: might still fail due to other reasons, but not access validation)
            if not result['success'] and 'error' in result:
                assert 'Access denied' not in result['error'], f"Valid requests should not be denied access for user: {user}"
    
    @given(
        user=valid_usernames(),
        query_type=st.sampled_from(['stock_levels', 'item_locations', 'sales_trends', 'forecasts', 'alerts'])
    )
    @settings(max_examples=50, deadline=5000)
    def test_different_query_types_validate_appropriate_data(self, user, query_type):
        """
        Feature: gemini-api-integration, Property 7: Data Access Validation
        For any query type, the data access validation should check the appropriate
        data requirements for that specific query type.
        
        **Validates: Requirements 3.3**
        """
        # Mock successful user validation
        self.mock_data_store.get_all_branches.return_value = ['Branch A', 'Branch B']
        
        # Get the data requirements for this query type
        data_requirements = self.processor.data_permissions.get(query_type, [])
        
        # Validate access for this query type's data requirements
        access_result = self.processor.validate_data_access(user, data_requirements)
        
        # Should grant access for valid query types with valid data requirements
        assert access_result is True, f"Valid query type {query_type} should be granted access for user: {user}"
        
        # Verify that the correct data requirements are being checked
        assert len(data_requirements) > 0, f"Query type {query_type} should have data requirements"
        
        # All data requirements should be valid types
        valid_data_types = [
            'inventory_data', 'stock_quantities', 'branch_data',
            'sales_data', 'revenue_data', 'historical_data', 'alert_data'
        ]
        
        for data_type in data_requirements:
            assert data_type in valid_data_types, f"Query type {query_type} should only require valid data types, got: {data_type}"


if __name__ == '__main__':
    # Run the property tests
    pytest.main([__file__, '-v', '--tb=short'])