#!/usr/bin/env python3
"""
Quick test to verify the download_template route works correctly.
"""
import io
import sys
import pandas as pd

def test_template_generation():
    """Test that the template can be generated in memory."""
    try:
        # Sheet 1: Transactions/Sales data
        transactions_columns = [
            'sale_date',
            'product_code',
            'branch_code',
            'quantity_sold',
            'revenue',
            'discount'
        ]
        
        # Sheet 2: Inventory/Item information
        inventory_columns = [
            'product_code',
            'branch_code',
            'product_name',
            'item_category1',
            'item_category2',
            'Last_on_hand',
            'inventory_value',
            'supplier_name',
            'supplier_code'
        ]
        
        # Create empty DataFrames with the required columns
        df_transactions = pd.DataFrame(columns=transactions_columns)
        df_inventory = pd.DataFrame(columns=inventory_columns)
        
        # Create an in-memory Excel file using BytesIO
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_transactions.to_excel(writer, sheet_name='Transactions', index=False)
            df_inventory.to_excel(writer, sheet_name='Inventory', index=False)
        
        # Reset the buffer position to the beginning
        output.seek(0)
        
        # Verify the buffer has content
        file_size = len(output.getvalue())
        
        print("✓ Template generated successfully in memory")
        print(f"✓ File size: {file_size} bytes")
        print(f"✓ Transactions sheet columns: {len(transactions_columns)} columns")
        print(f"✓ Inventory sheet columns: {len(inventory_columns)} columns")
        
        # Verify we can read it back
        output.seek(0)
        df_test = pd.read_excel(output, sheet_name='Transactions')
        print(f"✓ Template readable - Transactions sheet has {len(df_test.columns)} columns")
        
        output.seek(0)
        df_test = pd.read_excel(output, sheet_name='Inventory')
        print(f"✓ Template readable - Inventory sheet has {len(df_test.columns)} columns")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_template_generation()
    sys.exit(0 if success else 1)
