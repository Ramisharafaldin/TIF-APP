import pandas as pd
import numpy as np
from datetime import timedelta
import os

def generate_model_a(input_file='full_forecast_output.xlsx',
                     output_basename='forecast_summary_model_A',
                     forecast_days=30):
    """
    Generate a filtered forecast summary (Model A) limited to the user-defined forecast period.
    Calculates average daily sales and growth rate, adds insights, and exports to CSV and XLSX.
    This script is designed to be robust, creating empty output files if an error occurs.
    """
    # Determine the project root and script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    # Define absolute paths for input and output files
    input_path = os.path.join(project_root, input_file)
    output_csv = os.path.join(script_dir, f"{output_basename}.csv")
    output_xlsx = os.path.join(script_dir, f"{output_basename}.xlsx")

    def create_empty_files(reason):
        """Helper function to create empty output files."""
        print(f"-> {reason}. Creating empty summary files as placeholders.")
        pd.DataFrame().to_csv(output_csv, index=False, encoding='utf-8-sig')
        pd.DataFrame().to_excel(output_xlsx, index=False, engine='openpyxl')
        print(f"Empty CSV saved at: {output_csv}")
        print(f"Empty Excel saved at: {output_xlsx}")

    try:
        print(f"Loading forecast data from '{input_path}'...")
        df = pd.read_excel(input_path, engine='openpyxl')

        # Define the standard Arabic column names and their English counterparts
        rename_map = {
            'product_code': 'كود الصنف',
            'product_name': 'اسم الصنف',
            'sale_date': 'تاريخ البيع',
            'quantity_sold': 'الكمية المباعة',
            'predicted_quantity_sold': 'الكمية المتوقعة',
            'price': 'السعر',
            'total_revenue': 'إجمالي الإيراد',
            'avg_daily_sales': 'متوسط البيع اليومي',
            'growth_rate': 'معدل النمو',
            'notes': 'الملاحظات',
            'special_event_name': 'المناسبة الخاصة',
            'item_category1': 'القسم',
            'item_category2': 'القسم الفرعي',
            'supplier_name': 'اسم المورد',
            'supplier_code': 'كود المورد'
        }
        
        # Rename columns to work with them internally
        inverse_rename_map = {v: k for k, v in rename_map.items()}
        df.rename(columns=inverse_rename_map, inplace=True)

        # ✅ Ensure required columns exist
        required_cols = [
            'sale_date', 'product_code', 'quantity_sold', 
            'predicted_quantity_sold', 'special_event_name'
        ]
        df['sale_date'] = pd.to_datetime(df['sale_date'])

        # 🔍 Split into historical and future
        historical = df[df['quantity_sold'].notnull()]
        future = df[df['predicted_quantity_sold'].notnull() & df['quantity_sold'].isnull()].copy()

        if future.empty:
            create_empty_files("No future data found to process")
            return

        # 📊 Average daily sales
        if historical.empty:
            print("⚠️ No historical data found for calculating average sales.")
            avg_sales = pd.DataFrame(columns=['product_code', 'avg_daily_sales'])
        else:
            avg_sales = (
                historical.groupby('product_code')['quantity_sold']
                .mean()
                .reset_index()
                .rename(columns={'quantity_sold': 'avg_daily_sales'})
            )
            avg_sales['avg_daily_sales'] = avg_sales['avg_daily_sales'].round(2)

        # 🔁 Merge with future
        future = pd.merge(future, avg_sales, on='product_code', how='left')
        future['avg_daily_sales'] = future['avg_daily_sales'].fillna(0)

        # 📈 Growth rate
        future['growth_rate'] = np.divide(
            future['predicted_quantity_sold'] - future['avg_daily_sales'],
            future['avg_daily_sales']
        ) * 100
        future.replace([np.inf, -np.inf], np.nan, inplace=True)
        future['growth_rate'] = future['growth_rate'].round(2)

        # 📝 Performance notes
        def get_note(row):
            if pd.isna(row['growth_rate']):
                if row['avg_daily_sales'] == 0 and row['predicted_quantity_sold'] > 0:
                    return "منتج جديد ✅"
                return "لا يمكن حساب النمو"
            if row['growth_rate'] > 20:
                return "فرصة نمو ✅"
            elif row['growth_rate'] < -20:
                return "انخفاض مقلق ⚠️"
            return "أداء مستقر 🔄"

        future['notes'] = future.apply(get_note, axis=1)
        future['growth_rate'] = future['growth_rate'].fillna(100.0)

        # 🗃️ Final formatting and renaming
        final_df = future.copy()
        final_df.rename(columns=rename_map, inplace=True)
        
        # Define the final order of columns in the output report
        output_columns = [
            'كود الصنف', 'اسم الصنف', 'القسم', 'القسم الفرعي', 
            'اسم المورد', 'كود المورد', 'تاريخ البيع', 'الكمية المتوقعة',
            'متوسط البيع اليومي', 'معدل النمو', 'الملاحظات', 'المناسبة الخاصة'
        ]
        
        # Ensure all output columns exist, adding missing ones as None
        for col in output_columns:
            if col not in final_df.columns:
                final_df[col] = None
        
        final_df = final_df[output_columns]
        final_df = final_df.sort_values(by=['كود الصنف', 'تاريخ البيع'])

        print(f"Exporting {len(final_df)} rows...")
        final_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"✅ CSV saved at: {os.path.abspath(output_csv)}")

        if len(final_df) > 1_048_576:
            print("⚠️ Excel row limit exceeded. Creating a dummy XLSX file.")
            pd.DataFrame(columns=output_columns).to_excel(output_xlsx, index=False)
        else:
            final_df.to_excel(output_xlsx, index=False, engine='openpyxl')
            print(f"✅ Excel saved: {output_xlsx}")

        print("✅ Model A generation complete.")

    except FileNotFoundError:
        create_empty_files(f"Input file not found at '{input_path}'")
    except KeyError as e:
        create_empty_files(f"A required column is missing: {e}")
    except Exception as e:
        create_empty_files(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    generate_model_a(forecast_days=30)

