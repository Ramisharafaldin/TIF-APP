# utils/data_processing.py

import pandas as pd
import numpy as np
import re
import logging

# Configure logging
logger = logging.getLogger(__name__)

def clean_column_names(df):
    """تنظيف أسماء الأعمدة من المسافات والحروف غير المرغوب فيها"""
    df.columns = [re.sub(r'\s+', '_', col.strip()) for col in df.columns]
    df.columns = [re.sub(r'[^\w_]', '', col) for col in df.columns]
    return df

def normalize_columns(df):
    """Normalize column names to handle different variations."""
    df.columns = [col.replace(' ', '_') for col in df.columns] # First, replace spaces
    df = clean_column_names(df)
    
    column_map = {
        'sale_date': ['تاريخ', 'sale_date', 'date', 'Date'],
        'quantity_sold': ['الكمية_المباعة', 'quantity_sold', 'quantity', 'Quantity_sold'],
        'revenue': ['إجمالي_الإيراد', 'revenue', 'total_revenue', 'Transaction_revenue', 'Sales_Amount', 'Amount', 'Total_Amount', 'total_price', 'Total_Price'],
        'discount': ['قيمة_الخصم', 'discount', 'promo'],
        'product_code': ['كود_الصنف', 'product_code', 'item_code', 'Item_code'],
        'branch_code': ['الفرع', 'branch_code', 'location', 'branch', 'Location'],
        'product_name': ['اسم_الصنف', 'product_name', 'item_name', 'Item_description'],
        'item_category1': ['item_category1', 'category1', 'القسم', 'Item_category1'],
        'item_category2': ['item_category2', 'category2', 'القسم_الفرعي', 'Item_category2'],
        'Last_on_hand': ['المخزون_الحالي', 'current_stock', 'stock', 'Last_on_hand', 'qty', 'quantity', 'on_hand', 'count', 'inventory_count', 'balance', 'stock_balance'],
        'inventory_value': ['inventory_value', 'Inventory_value/unit', 'Cost', 'Average_Cost', 'Unit_Cost', 'cost_price', 'Average_cost', 'price', 'purchase_price', 'buying_price', 'cost_per_unit', 'unit_value', 'value', 'item_cost'],
        'supplier_name': ['supplier_name', 'Supplier_Name'],
        'supplier_code': ['supplier_code', 'Supplier_code']
    }

    # Create a reverse map for renaming
    rename_map = {}
    for standard_name, variations in column_map.items():
        for variation in variations:
            variation_clean = re.sub(r'\s+', '_', variation.strip().lower())
            for col in df.columns:
                if re.sub(r'\s+', '_', col.strip().lower()) == variation_clean:
                    rename_map[col] = standard_name
                    break
    
    df.rename(columns=rename_map, inplace=True)
    
    # Convert numeric columns to proper numeric types to prevent string comparison errors
    numeric_columns = ['Last_on_hand', 'quantity_sold', 'inventory_value', 'revenue', 'discount']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df

def process_new_format(file):
    """
    Process the new two-sheet Excel file format.
    
    Args:
        file: File path or file-like object
        
    Returns:
        Tuple of (transactions_df, items_df)
        
    Note:
        Properly closes file handles to avoid Windows file locking issues.
    """
    xls = None
    try:
        logger.info('Reading "Transactions" and "Item info" sheets...')
        xls = pd.ExcelFile(file)
        
        transactions_sheet = next((s for s in xls.sheet_names if 'transaction' in s.lower() or 'sale' in s.lower()), None)
        item_info_sheet = next((s for s in xls.sheet_names if 'item' in s.lower() or 'inventory' in s.lower()), None)

        if not transactions_sheet or not item_info_sheet:
            error_msg = "Could not find 'Transactions'/'Sales' or 'Item info'/'Inventory' sheets in the Excel file."
            logger.error(error_msg)
            raise ValueError(error_msg)

        df_trans = pd.read_excel(xls, sheet_name=transactions_sheet)
        df_items = pd.read_excel(xls, sheet_name=item_info_sheet)

        logger.info('Normalizing columns and processing data...')
        df_trans = normalize_columns(df_trans)
        df_items = normalize_columns(df_items)

        logger.info("Successfully processed the new Excel file format.")
        return df_trans, df_items

    except Exception as e:
        logger.error(f"An error occurred while processing the new format: {e}")
        raise
    finally:
        # Ensure file handle is closed
        if xls is not None:
            xls.close()


def process_new_format_bytes(file_data: bytes):
    """
    Process an Excel file supplied as raw bytes (used by the MongoDB backend,
    which stores uploaded files as binary blobs in GridFS).

    Writes the bytes to a temporary file and delegates to
    :func:`process_new_format`.

    Args:
        file_data: Raw Excel file bytes

    Returns:
        Tuple of (transactions_df, items_df)
    """
    import tempfile
    import os as _os
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        tmp.write(file_data)
        tmp_path = tmp.name
    try:
        return process_new_format(tmp_path)
    finally:
        try:
            if _os.path.exists(tmp_path):
                _os.remove(tmp_path)
        except Exception:
            pass


def load_unified_data(file):
    """
    Process the unified Excel file with Sales and Inventory sheets.
    
    Args:
        file: File path or file-like object
        
    Returns:
        Merged DataFrame with sales and inventory data
        
    Note:
        Properly closes file handles to avoid Windows file locking issues.
    """
    xls = None
    try:
        logger.info('Reading "Sales" and "Inventory" sheets...')
        xls = pd.ExcelFile(file)
        sales_sheet = next((s for s in xls.sheet_names if 'sale' in s.lower() or 'transaction' in s.lower()), None)
        inventory_sheet = next((s for s in xls.sheet_names if 'inventory' in s.lower() or 'item' in s.lower()), None)

        if not sales_sheet or not inventory_sheet:
            error_msg = "Could not find 'Sales'/'Transactions' or 'Inventory'/'Item' sheets."
            logger.error(error_msg)
            raise ValueError(error_msg)

        df_sales = pd.read_excel(xls, sheet_name=sales_sheet)
        df_inventory = pd.read_excel(xls, sheet_name=inventory_sheet)

        logger.info('Cleaning and merging data...')
        df_sales = normalize_columns(df_sales)
        df_inventory = normalize_columns(df_inventory)

        # Data Cleaning and Processing
        df_sales.dropna(subset=['product_code', 'branch_code', 'sale_date', 'quantity_sold'], inplace=True)
        df_inventory.dropna(subset=['product_code', 'branch_code', 'Last_on_hand'], inplace=True)
        
        df_sales = df_sales[df_sales['quantity_sold'] > 0]
        df_inventory = df_inventory[df_inventory['Last_on_hand'] > 0]

        df_sales.drop_duplicates(inplace=True)
        df_inventory.drop_duplicates(subset=['product_code', 'branch_code'], inplace=True)

        # Merge data
        merged_df = pd.merge(df_sales, df_inventory, on=['product_code', 'branch_code'], how='inner')
        
        # OPTIMIZATION 2: Vectorized price calculation (3-10x faster than apply)
        merged_df['price'] = merged_df['revenue'] / merged_df['quantity_sold'].replace(0, 1)
        merged_df.loc[merged_df['quantity_sold'] == 0, 'price'] = 0
        
        merged_df['sale_date'] = pd.to_datetime(merged_df['sale_date'], errors='coerce')
        merged_df.dropna(subset=['sale_date'], inplace=True)

        logger.info("Successfully processed and merged data.")
        return merged_df
    
    except Exception as e:
        logger.error(f"An error occurred while loading unified data: {e}")
        raise
    finally:
        # Ensure file handle is closed
        if xls is not None:
            xls.close()

def validate_data(df, data_type):
    """التحقق من وجود الأعمدة المطلوبة في البيانات"""
    required_cols = {
        'sales': ['branch_code', 'product_code', 'sale_date', 'quantity_sold', 'price'],
        'inventory': ['product_code', 'product_name', 'Last_on_hand'],
        'forecast': ['date', 'product_code', 'quantity_sold']
    }
    missing_cols = [col for col in required_cols[data_type] if col not in df.columns]
    if missing_cols:
        raise ValueError(f"ملف {data_type} ينقصه الأعمدة التالية: {', '.join(missing_cols)}")
    return df

def find_sheets_by_type(file, sheet_type):
    """البحث عن الشيتات المناسبة حسب نوع البيانات المطلوبة"""
    from io import BytesIO
    import pandas as pd

    if isinstance(file, BytesIO):
        file.seek(0)

    xls = pd.ExcelFile(file)
    required_cols = {
        'sales': ['branch_code', 'product_code', 'sale_date', 'quantity_sold', 'price'],
        'inventory': ['product_code', 'product_name', 'Last_on_hand']
    }[sheet_type]

    valid_sheets = []
    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name, nrows=1)
            df = normalize_columns(df)
            if all(col in df.columns for col in required_cols):
                valid_sheets.append(sheet_name)
        except Exception as e:
            logger.warning(f"⚠️ خطأ في قراءة شيت {sheet_name}: {str(e)}")
            continue

    if sheet_type == 'sales':
        for sheet in valid_sheets:
            if sheet.lower().startswith(('sales', 'مبيعات')):
                return [sheet]
        return valid_sheets[:1] if valid_sheets else []
    elif sheet_type == 'inventory':
        for sheet in valid_sheets:
            if sheet.lower().startswith(('inventory', 'مخزون')):
                return [sheet]
        return valid_sheets[:1] if valid_sheets else []
    return []


def filter_sales_by_date(df_sales, start_date, end_date):
    """
    Filter sales data by date range.
    
    Args:
        df_sales: Sales DataFrame
        start_date: Start date (datetime object)
        end_date: End date (datetime object)
        
    Returns:
        Filtered DataFrame
    """
    try:
        # Ensure sale_date column exists and is datetime
        if 'sale_date' not in df_sales.columns:
            logger.error("Column 'sale_date' not found in sales data")
            return df_sales
        
        # Convert sale_date to datetime if not already
        df_sales['sale_date'] = pd.to_datetime(df_sales['sale_date'], errors='coerce')
        
        # Remove rows with invalid dates
        df_sales = df_sales.dropna(subset=['sale_date'])
        
        # Filter by date range
        filtered_df = df_sales[
            (df_sales['sale_date'] >= start_date) & 
            (df_sales['sale_date'] <= end_date)
        ].copy()
        
        logger.info(f"Filtered sales data from {len(df_sales)} to {len(filtered_df)} records for date range {start_date} to {end_date}")
        return filtered_df
        
    except Exception as e:
        logger.error(f"Error filtering sales by date: {e}")
        return df_sales


def analyze_inventory(df_sales, df_inventory, min_coverage=7, max_coverage=30, 
                     forecast_days=30, safety_stock=0, reorder_point=0, stagnant_period=90):
    """
    Perform comprehensive inventory analysis.
    
    Args:
        df_sales: Sales DataFrame
        df_inventory: Inventory DataFrame
        min_coverage: Minimum coverage days
        max_coverage: Maximum coverage days
        forecast_days: Days to forecast
        safety_stock: Safety stock level
        reorder_point: Reorder point
        stagnant_period: Days to consider item stagnant
        
    Returns:
        Analysis results DataFrame
    """
    try:
        logger.info("Starting inventory analysis...")
        
        # Apply performance filter before analysis processing
        from utils.performance_filter import filter_inactive_items_with_fallback
        df_sales_filtered, df_inventory_filtered, filter_stats = filter_inactive_items_with_fallback(
            df_sales, df_inventory, log_stats=True
        )
        
        # Log filtering results
        if filter_stats.get('items_filtered', 0) > 0:
            logger.info(f"Performance filter applied: {filter_stats['items_filtered']} inactive items filtered "
                       f"({filter_stats['filtering_percentage']:.1f}% reduction)")
        
        # Use filtered data for analysis
        df_sales = df_sales_filtered
        df_inventory = df_inventory_filtered
        
        # Validate required columns
        required_sales_cols = ['product_code', 'quantity_sold', 'sale_date']
        required_inventory_cols = ['product_code', 'Last_on_hand']
        
        missing_sales_cols = [col for col in required_sales_cols if col not in df_sales.columns]
        missing_inventory_cols = [col for col in required_inventory_cols if col not in df_inventory.columns]
        
        if missing_sales_cols:
            raise ValueError(f"Missing required sales columns: {missing_sales_cols}")
        if missing_inventory_cols:
            raise ValueError(f"Missing required inventory columns: {missing_inventory_cols}")
        
        # Calculate sales statistics
        sales_stats = df_sales.groupby('product_code').agg({
            'quantity_sold': ['sum', 'mean', 'count'],
            'sale_date': ['min', 'max']
        })
        
        # Round numeric quantities (sum, mean, count)
        sales_stats['quantity_sold'] = sales_stats['quantity_sold'].round(2)
        
        # Flatten column names
        sales_stats.columns = ['_'.join(col).strip() for col in sales_stats.columns]
        sales_stats = sales_stats.reset_index()
        
        # Calculate daily average sales
        sales_stats['days_in_period'] = (
            pd.to_datetime(sales_stats['sale_date_max']) - 
            pd.to_datetime(sales_stats['sale_date_min'])
        ).dt.days + 1
        
        sales_stats['daily_sales'] = (
            sales_stats['quantity_sold_sum'] / sales_stats['days_in_period']
        ).fillna(0)
        
        # Merge with inventory data (handle missing columns gracefully)
        inventory_columns = ['product_code', 'product_name', 'Last_on_hand', 'branch_code']
        optional_columns = ['item_category1', 'item_category2', 'supplier_name']
        
        # Add optional columns if they exist
        for col in optional_columns:
            if col in df_inventory.columns:
                inventory_columns.append(col)
        
        results = pd.merge(
            df_inventory[inventory_columns],
            sales_stats,
            on='product_code',
            how='left'
        )
        
        # Add missing optional columns with default values
        for col in optional_columns:
            if col not in results.columns:
                results[col] = '-'
        
        # Fill missing values
        results = results.fillna({
            'quantity_sold_sum': 0,
            'quantity_sold_mean': 0,
            'quantity_sold_count': 0,
            'daily_sales': 0,
            'days_in_period': forecast_days
        })
        
        # Ensure Last_on_hand is numeric before calculation
        results['Last_on_hand'] = pd.to_numeric(results['Last_on_hand'], errors='coerce').fillna(0)
        
        # Calculate coverage days (vectorized with safe division)
        results['coverage_days'] = results['Last_on_hand'] / results['daily_sales'].replace(0, 1)
        results.loc[results['daily_sales'] == 0, 'coverage_days'] = float('inf')
        results['coverage_days'] = results['coverage_days'].replace(float('inf'), 9999)
        
        # Calculate forecasted demand (expected_demand for template compatibility)
        results['expected_demand'] = results['daily_sales'] * forecast_days
        results['forecasted_demand'] = results['expected_demand']
        
        # OPTIMIZATION 2: Vectorized recommended order calculation
        results['recommended_order'] = (
            (results['forecasted_demand'] + safety_stock - results['Last_on_hand'])
            .clip(lower=0)
        )
        results.loc[results['daily_sales'] == 0, 'recommended_order'] = 0
        
        # OPTIMIZATION 2: Vectorized status classification with np.select
        conditions = [
            results['Last_on_hand'] == 0,
            results['coverage_days'] < min_coverage,
            (results['daily_sales'] == 0) & (results['Last_on_hand'] > 0),
            (results['daily_sales'] > 0) & (results['coverage_days'] > stagnant_period),
            results['coverage_days'] > max_coverage
        ]
        choices = ['نفد المخزون', 'مخزون منخفض', 'راكد', 'راكد', 'مخزون زائد']
        results['status'] = np.select(conditions, choices, default='طبيعي')
        
        # Add is_stagnant flag for filtering
        results['is_stagnant'] = results['status'] == 'راكد'
        
        # OPTIMIZATION 2: Vectorized priority scoring with map
        priority_map = {
            'نفد المخزون': 1,
            'مخزون منخفض': 2,
            'مخزون زائد': 3,
            'راكد': 4,
            'طبيعي': 5
        }
        results['priority_score'] = results['status'].map(priority_map)
        
        # Add quantity_sold for template compatibility
        results['quantity_sold'] = results['quantity_sold_sum']
        
        # OPTIMIZATION 2: Vectorized ABC classification
        results['abc_classification'] = np.select(
            [results['daily_sales'] > 10, results['daily_sales'] > 1],
            ['A', 'B'],
            default='C'
        )
        
        # Add recommendations (still needs apply but more efficient with vectorized status)
        def generate_recommendations(row):
            if row['status'] == 'نفد المخزون':
                return 'طلب عاجل - نفد المخزون'
            elif row['status'] == 'مخزون منخفض':
                return f'إعادة طلب - يكفي {row["coverage_days"]:.0f} يوم'
            elif row['status'] == 'مخزون زائد':
                return 'تقليل الطلبات - مخزون زائد'
            elif row['status'] == 'راكد':
                if row['daily_sales'] == 0:
                    return 'مراجعة المنتج - لا توجد مبيعات'
                else:
                    return f'مراجعة المنتج - مبيعات ضعيفة ({row["coverage_days"]:.0f} يوم تغطية)'
            else:
                return 'مستوى طبيعي'
        
        results['recommendations'] = results.apply(generate_recommendations, axis=1)
        
        # Sort by priority and coverage days
        results = results.sort_values(['priority_score', 'coverage_days']).reset_index(drop=True)

        # ULTIMATUM KILL SWITCH: IF Sufficient is True OR Stagnant is True, THEN the "Expected Order" MUST BE COMPLETELY EMPTY.
        # This is the HARDCODE FIX requested by the USER.
        results['Stock_Is_Sufficient'] = results['Last_on_hand'] >= results['expected_demand']
        kill_mask = (results['Stock_Is_Sufficient'] == True) | (results['is_stagnant'] == True)
        results.loc[kill_mask, 'expected_demand'] = None
        results.loc[kill_mask, 'recommended_order'] = None
        
        # Round numerical columns
        numerical_cols = ['Last_on_hand', 'daily_sales', 'coverage_days', 
                         'forecasted_demand', 'recommended_order']
        for col in numerical_cols:
            if col in results.columns:
                results[col] = results[col].round(2)
        
        logger.info(f"Inventory analysis completed. Generated {len(results)} product analyses.")
        return results
        
    except Exception as e:
        logger.error(f"Error in inventory analysis: {e}")
        raise
