#!/usr/bin/env python3
"""
Test script for natural language query processor.
"""

def test_query_processor():
    """Test the natural language query processor."""
    try:
        print('=== Natural Language Query Processor Test ===')
        
        # Test basic imports
        from utils.query_processor import QueryProcessor
        print('✅ Query processor imported successfully')
        
        # Create mock AI service and data store
        class MockAIService:
            def process_natural_language_query(self, query, context):
                return {'response': f'Processed: {query}'}
        
        class MockDataStore:
            def get_all_branches(self, user):
                return ['Branch A', 'Branch B', 'Branch C']
            
            def get_branch_data(self, user, branch_name=None):
                import pandas as pd
                # Mock inventory data
                inventory_data = pd.DataFrame({
                    'product_code': ['P001', 'P002', 'P003'],
                    'product_name': ['Product 1', 'Product 2', 'Product 3'],
                    'Last_on_hand': [50, 5, 0],
                    'branch_code': ['A', 'B', 'C']
                })
                # Mock sales data
                sales_data = pd.DataFrame({
                    'product_code': ['P001', 'P002', 'P003'],
                    'revenue': [1000, 500, 200],
                    'sale_date': ['2024-01-01', '2024-01-02', '2024-01-03']
                })
                return sales_data, inventory_data
        
        # Initialize query processor
        mock_ai_service = MockAIService()
        mock_data_store = MockDataStore()
        processor = QueryProcessor(mock_ai_service, mock_data_store)
        
        print('✅ Query processor initialized successfully')
        
        # Test query intent parsing
        test_queries = [
            "How much stock do we have?",
            "What are the sales trends?",
            "Where can I find product P001?",
            "Show me low stock alerts",
            "What's the forecast for next month?"
        ]
        
        print('\n=== Testing Query Intent Parsing ===')
        for query in test_queries:
            intent = processor.parse_query_intent(query)
            print(f'Query: "{query}"')
            print(f'  Type: {intent["query_type"]}')
            print(f'  Confidence: {intent["confidence"]:.1f}%')
            print(f'  Data Requirements: {intent["data_requirements"]}')
            print()
        
        # Test data access validation
        print('=== Testing Data Access Validation ===')
        test_user = 'test_user'
        test_data_types = ['inventory_data', 'sales_data']
        
        access_granted = processor.validate_data_access(test_user, test_data_types)
        print(f'Access for {test_user}: {"✅ Granted" if access_granted else "❌ Denied"}')
        
        # Test query execution
        print('\n=== Testing Query Execution ===')
        stock_intent = {
            'query_type': 'stock_levels',
            'data_requirements': ['inventory_data'],
            'parameters': {}
        }
        
        result = processor.execute_data_query(stock_intent, test_user)
        print(f'Stock levels query result: {result["success"]}')
        if result['success']:
            data = result['data']
            print(f'  Total products: {data.get("total_products", 0)}')
            print(f'  Low stock items: {data.get("low_stock_items", 0)}')
            print(f'  Out of stock items: {data.get("out_of_stock_items", 0)}')
        
        # Test conversational response formatting
        print('\n=== Testing Conversational Response ===')
        response = processor.format_conversational_response(result, "How much stock do we have?")
        print(f'Response: {response["response"]}')
        print(f'Confidence: {response["confidence_score"]}%')
        print(f'Suggestions: {response["suggestions"]}')
        
        print('\n✅ Natural language query processor test completed successfully!')
        return True
        
    except Exception as e:
        print(f'❌ Error testing query processor: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_query_processor()
    exit(0 if success else 1)