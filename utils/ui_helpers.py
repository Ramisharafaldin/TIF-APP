import pandas as pd
import numpy as np
from io import BytesIO

ARABIC_HEADERS = {
    'product_code': 'كود الصنف',
    'product_name': 'اسم الصنف',
    'Last_on_hand': 'المخزون الحالي',
    'quantity_sold': 'الكمية المباعة',
    'daily_sales': 'المبيعات اليومية',
    'coverage_days': 'أيام التغطية',
    'expected_demand': 'الطلب المتوقع',
    'Stock_Is_Sufficient': 'كفاية المخزون',
    'abc_classification': 'تصنيف ABC',
    'recommendations': 'التوصيات',
    'item_category1': 'القسم',
    'item_category2': 'القسم الفرعي',
    'supplier_name': 'اسم المورد',
    'supplier_code': 'كود المورد',
    'branch_code': 'الفرع',
    'Inventory_valueunit': 'قيمة المخزون للوحدة',
    'sale_days': 'عدد أيام البيع',
    'is_stagnant': 'راكد',
    # Transfers specific
    'source_branch': 'الفرع المصدر',
    'destination_branch': 'الفرع المستلم',
    'transfer_quantity': 'كمية التحويل',
    'reason': 'سبب التحويل',
    # Forecasting specific
    'forecast_quantity': 'الكمية المتوقعة',
    'confidence': 'درجة الثقة',
    'confidence_lower': 'الحد الأدنى للثقة',
    'confidence_upper': 'الحد الأقصى للثقة',
    'trend': 'الاتجاه',
    'seasonality': 'الموسمية'
}

def _add_insights_sheet(writer, ai_insights):
    """Helper to add AI insights sheet to Excel workbook."""
    if not ai_insights:
        return

    workbook = writer.book
    # Handle both wrapped and unwrapped formats
    data = ai_insights.get('data', ai_insights) if isinstance(ai_insights, dict) else {}
    
    insights_data = []
    
    # Executive Summary
    summary = data.get('executive_summary') or data.get('stock_health')
    if summary:
        insights_data.append(['الملخص التنفيذي', str(summary)])
    
    # Insights
    recs = data.get('recommendations') or data.get('replenishment_advice')
    if recs:
        if isinstance(recs, list):
            insights_data.append(['التوصيات الذكية', ''])
            for r in recs:
                insights_data.append(['', f"• {str(r)}"])
        else:
            insights_data.append(['التوصيات الذكية', str(recs)])
    
    # Risks
    risks = data.get('risks') or data.get('insights')
    if risks:
        if isinstance(risks, list):
            insights_data.append(['الرؤى والتحذيرات', ''])
            for r in risks:
                insights_data.append(['', f"• {str(r)}"])
        else:
            insights_data.append(['الرؤى والتحذيرات', str(risks)])
    
    if insights_data:
        insights_df = pd.DataFrame(insights_data, columns=['المجال', 'التفاصيل'])
        insights_df.to_excel(writer, sheet_name='رؤى الذكاء الاصطناعي', index=False)
        
        # Formatting the insights sheet
        sheet_name = 'رؤى الذكاء الاصطناعي'
        if sheet_name in writer.sheets:
            try:
                worksheet = writer.sheets[sheet_name]
                engine = getattr(writer, 'engine', None)
                if engine == 'xlsxwriter':
                    format_wrap = workbook.add_format({'text_wrap': True, 'align': 'top'})
                    worksheet.set_column('A:A', 20)
                    worksheet.set_column('B:B', 80, format_wrap)
                else: 
                    # Default/OpenPyXL
                    from openpyxl.styles import Alignment
                    if hasattr(worksheet, 'column_dimensions'):
                        worksheet.column_dimensions['A'].width = 20
                        worksheet.column_dimensions['B'].width = 80
                    if hasattr(worksheet, '__getitem__'):
                        for cell in worksheet['B']:
                            cell.alignment = Alignment(wrap_text=True, vertical='top')
            except Exception:
                pass

def export_full_report(results, params, ai_insights=None):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # --- AI Insights Sheet ---
        _add_insights_sheet(writer, ai_insights)

        # --- Data Sheets ---
        export_columns_order = [
            'product_code', 'product_name', 'item_category1', 'item_category2', 'branch_code', 'Last_on_hand', 
            'Inventory_valueunit', 'supplier_name', 'supplier_code', 'quantity_sold', 
            'sale_days', 'daily_sales', 'coverage_days', 'expected_demand', 
            'is_stagnant', 'abc_classification', 'recommendations'
        ]
        existing_export_cols = [col for col in export_columns_order if col in results.columns]
        
        # KILL SWITCH: Force empty values for Sufficient or Stagnant items
        mask = (results['Stock_Is_Sufficient'] == True) | (results['is_stagnant'] == True)
        results.loc[mask, 'expected_demand'] = None
        results.loc[mask, 'recommended_order'] = None

        main_report_df = results[results['quantity_sold'] > 0].copy()
        if not main_report_df.empty:
            main_report = main_report_df[existing_export_cols].rename(columns=ARABIC_HEADERS)
            main_report.to_excel(writer, sheet_name='التقرير الشامل', index=False, na_rep='')

        critical_items_df = results[(results['coverage_days'] < params['min_coverage']) & (results['daily_sales'] > 0)].copy()
        if not critical_items_df.empty:
            critical_report = critical_items_df[existing_export_cols].rename(columns=ARABIC_HEADERS)
            critical_report.to_excel(writer, sheet_name='المخزون الحرج', index=False, na_rep='')

        stagnant_items_df = results[results['is_stagnant']].copy()
        if not stagnant_items_df.empty:
            stagnant_report = stagnant_items_df[existing_export_cols].rename(columns=ARABIC_HEADERS)
            stagnant_report.to_excel(writer, sheet_name='الأصناف الراكدة', index=False, na_rep='')

    return output.getvalue()

def export_transfers_report(transfer_df, summary_df, ai_insights=None):
    """Export transfers report to Excel."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        _add_insights_sheet(writer, ai_insights)
        
        has_data = False
        if summary_df is not None and not summary_df.empty:
            summary_df.rename(columns=ARABIC_HEADERS).to_excel(writer, sheet_name='ملخص الفروع', index=False, na_rep='')
            has_data = True
            
        if transfer_df is not None and not transfer_df.empty:
            transfer_df.rename(columns=ARABIC_HEADERS).to_excel(writer, sheet_name='توصيات النقل', index=False, na_rep='')
            has_data = True
            
        # Ensure at least one sheet exists if no data and no insights
        if not has_data and not ai_insights:
            pd.DataFrame({'ملاحظة': ['لا توجد بيانات متاحة للتصدير']}).to_excel(writer, sheet_name='التقرير', index=False)
            
    return output.getvalue()

def export_forecasting_report(summary_df, params, ai_insights=None):
    """Export forecasting report to Excel with proper null handling."""
    output = BytesIO()
    
    # Handle NaN values before export
    if summary_df is not None and not summary_df.empty:
        # Create a copy to avoid modifying original
        summary_df = summary_df.copy()
        
        # Replace Inf values first (both positive and negative infinity)
        summary_df = summary_df.replace([np.inf, -np.inf], np.nan)
        
        # Convert confidence to percentage format if it exists (0.85 → 85%)
        if 'confidence' in summary_df.columns:
            # Ensure it's numeric and preserve the actual dynamic values
            summary_df['confidence'] = pd.to_numeric(summary_df['confidence'], errors='coerce')
            
            # If values are in [0, 1] range, convert to [0, 100] for percentage view
            # Check if max is <= 1 to determine if scaling is needed
            is_decimal = summary_df['confidence'].max() <= 1.01 
            if is_decimal:
                summary_df['confidence'] = summary_df['confidence'] * 100
                
            # 🚨 ZERO-TOLERANCE for hardcoded clip(50, 99). 
            # We use a much wider range [1, 99] to show real model uncertainty.
            summary_df['confidence'] = summary_df['confidence'].fillna(75).clip(1, 99)
            summary_df['confidence'] = summary_df['confidence'].round(2)
        
        # Fill NaN values with appropriate defaults
        for col in summary_df.columns:
            if col == 'forecast_quantity' or col == 'expected_demand':
                # Leave these blank if they were NaN (sufficient stock)
                continue
            if pd.api.types.is_numeric_dtype(summary_df[col]):
                # Fill other numeric columns with 0
                summary_df[col] = summary_df[col].fillna(0)
            else:
                # Fill text columns with "غير متوفر" (Not available in Arabic)
                summary_df[col] = summary_df[col].fillna('غير متوفر')
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        _add_insights_sheet(writer, ai_insights)
        
        # Add parameters sheet
        params_data = [[k, str(v)] for k, v in params.items()]
        pd.DataFrame(params_data, columns=['المعيار', 'القيمة']).to_excel(writer, sheet_name='معايير التنبؤ', index=False)
        
        if summary_df is not None and not summary_df.empty:
            # Rename columns to Arabic
            summary_df_arabic = summary_df.rename(columns=ARABIC_HEADERS)
            # Export with explicit na_rep to handle any remaining NaN
            summary_df_arabic.to_excel(writer, sheet_name='نتائج التنبؤ', index=False, na_rep='')
            
    return output.getvalue()

def export_dashboard_report(monthly_sales, supplier_sales, dept_stock, ai_insights=None):
    """Export dashboard report to Excel."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        _add_insights_sheet(writer, ai_insights)
        
        has_data = False
        
        if monthly_sales is not None and not monthly_sales.empty:
            # Rename columns if they exist, otherwise use as is
            cols = {col: col for col in monthly_sales.columns}
            if 'month' in monthly_sales.columns: cols['month'] = 'الشهر'
            if 'revenue' in monthly_sales.columns: cols['revenue'] = 'المبيعات'
            
            monthly_sales.rename(columns=cols).to_excel(writer, sheet_name='المبيعات الشهرية', index=False)
            has_data = True
            
        if supplier_sales is not None and not supplier_sales.empty:
            cols = {col: col for col in supplier_sales.columns}
            if 'supplier_name' in supplier_sales.columns: cols['supplier_name'] = 'المورد'
            if 'revenue' in supplier_sales.columns: cols['revenue'] = 'المبيعات'
            
            supplier_sales.rename(columns=cols).to_excel(writer, sheet_name='مبيعات الموردين', index=False)
            has_data = True
            
        if dept_stock is not None and not dept_stock.empty:
            cols = {col: col for col in dept_stock.columns}
            if 'item_category1' in dept_stock.columns: cols['item_category1'] = 'القسم'
            if 'Last_on_hand' in dept_stock.columns: cols['Last_on_hand'] = 'المخزون'
            
            dept_stock.rename(columns=cols).to_excel(writer, sheet_name='مخزون الأقسام', index=False)
            has_data = True
            
        # Ensure at least one sheet exists
        if not has_data and not ai_insights:
            pd.DataFrame({'ملاحظة': ['لا توجد بيانات متاحة للتصدير']}).to_excel(writer, sheet_name='التقرير', index=False)
            
    return output.getvalue()
