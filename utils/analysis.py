import pandas as pd
import numpy as np
import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)

def generate_recommendations(row, params):
    if row['daily_sales'] <= 0:
        return "🛑 إيقاف التوريد"
    
    coverage_days = pd.to_numeric(row['coverage_days'], errors='coerce')
    if pd.isna(coverage_days):
        return "❓ بيانات غير كافية"

    if row['abc_classification'] == 'A':
        if coverage_days < params['min_coverage']: return "⚠️ زيادة عاجلة"
        if coverage_days > params['max_coverage']: return "⬇️ تخفيض تدريجي"
        return "✅ مستوى مثالي"
    
    elif row['abc_classification'] == 'B':
        if coverage_days < params['min_coverage']: return "⬆️ زيادة محدودة"
        if coverage_days > params['max_coverage']: return "⬇️ تخفيض جزئي"
        return "✅ حافظ على المستوى"
    
    elif row['abc_classification'] == 'C':
        if coverage_days < params['min_coverage']: return "⬆️ طلب صغير"
        if coverage_days > params['max_coverage']: return "⏳ تصفية المخزون"
        return "➖ لا إجراء"

    return "❓ غير معروف"

def perform_analysis(df_sales, df_inventory, params, start_date, end_date):
    try:
        if df_sales.empty or df_inventory.empty:
            error_msg = "Sales or inventory data is empty."
            logger.error(error_msg)
            raise ValueError(error_msg)

        df_sales['sale_date'] = pd.to_datetime(df_sales['sale_date']).dt.date
        start_date = pd.to_datetime(start_date).date()
        end_date = pd.to_datetime(end_date).date()

        df_sales_filtered = df_sales[(df_sales['sale_date'] >= start_date) & (df_sales['sale_date'] <= end_date)].copy()

        df_sales_filtered['product_code'] = df_sales_filtered['product_code'].astype(str).str.strip()
        df_inventory['product_code'] = df_inventory['product_code'].astype(str).str.strip()

        # Daily aggregation (no revenue)
        daily_sales_summary = df_sales_filtered.groupby(['product_code', 'sale_date']).agg(
            quantity_sold=('quantity_sold', 'sum')
        ).reset_index()

        # Total aggregation
        sales_agg = daily_sales_summary.groupby('product_code').agg(
            quantity_sold=('quantity_sold', 'sum'),
            sale_days=('sale_date', 'nunique')
        ).reset_index()

        df_merged = pd.merge(df_inventory, sales_agg, on='product_code', how='left')
        df_merged[['quantity_sold', 'sale_days']] = df_merged[['quantity_sold', 'sale_days']].fillna(0)

        # Calculations
        df_merged['daily_sales'] = np.where(df_merged['sale_days'] > 0, df_merged['quantity_sold'] / df_merged['sale_days'], 0)
        df_merged['coverage_days'] = np.where(df_merged['daily_sales'] > 0, (df_merged['Last_on_hand'] / df_merged['daily_sales']).round(1), 999)

        predicted_demand = df_merged['daily_sales'] * params['forecast_days']
        demand_deficit = predicted_demand - df_merged['Last_on_hand']
        df_merged['expected_demand'] = np.where(demand_deficit > 0, demand_deficit.round(0), np.nan)
        df_merged['Stock_Is_Sufficient'] = (demand_deficit <= 0).astype(bool)

        df_merged['is_stagnant'] = (df_merged['quantity_sold'] == 0) & (df_merged['Last_on_hand'] > 0)
        df_merged.loc[df_merged['is_stagnant'] == True, 'expected_demand'] = np.nan

        # ABC Classification based on quantity_sold
        df_with_sales = df_merged[df_merged['quantity_sold'] > 0].copy()
        df_with_sales = df_with_sales.sort_values(by='quantity_sold', ascending=False)
        total_quantity = df_with_sales['quantity_sold'].sum()

        if total_quantity > 0:
            df_with_sales['cumulative_qty_pct'] = df_with_sales['quantity_sold'].cumsum() / total_quantity
            conditions = [
                df_with_sales['cumulative_qty_pct'] <= 0.80,
                df_with_sales['cumulative_qty_pct'] <= 0.95,
            ]
            df_with_sales['abc_classification'] = np.select(conditions, ['A', 'B'], default='C')
        else:
            df_with_sales['abc_classification'] = 'C'

        df_merged = pd.merge(df_merged, df_with_sales[['product_code', 'abc_classification']], on='product_code', how='left')
        df_merged['abc_classification'].fillna('C', inplace=True)

        df_merged['recommendations'] = df_merged.apply(lambda row: generate_recommendations(row, params), axis=1)

        final_df = df_merged[~((df_merged['quantity_sold'] == 0) & (df_merged['Last_on_hand'] == 0))].copy()

        if final_df.empty:
            warning_msg = "No products with sales or stock in the selected period."
            logger.warning(warning_msg)
            raise ValueError(warning_msg)

        return final_df

    except KeyError as e:
        logger.error(f"Missing required column: {e}")
        raise
    except Exception as e:
        logger.error(f"An error occurred during analysis: {e}")
        raise
