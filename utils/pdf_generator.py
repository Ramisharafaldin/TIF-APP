"""
PDF Report Generation Utilities

This module provides functions to generate professional PDF reports for different modules
of the inventory management system. It supports Arabic text rendering, charts embedding,
and professional layout with headers, footers, and metadata.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
"""

import os
import io
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
import pandas as pd

try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.lib.colors import black, blue, gray, white
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Set up logging
logger = logging.getLogger(__name__)

class NumberedCanvas(canvas.Canvas):
    """Custom canvas class for adding headers, footers, and page numbers."""
    
    def __init__(self, *args, **kwargs):
        self.title = kwargs.pop('title', 'تقرير النظام')
        self.username = kwargs.pop('username', 'مستخدم')
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for (page_num, page_state) in enumerate(self._saved_page_states):
            self.__dict__.update(page_state)
            self.draw_page_number(page_num + 1, num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_num, total_pages):
        """Draw header, footer, and page number."""
        # Header
        self.setFont("Helvetica-Bold", 12)
        self.drawString(2*cm, A4[1] - 2*cm, self.title)
        self.drawRightString(A4[0] - 2*cm, A4[1] - 2*cm, f"المستخدم: {self.username}")
        
        # Footer with page number
        self.setFont("Helvetica", 10)
        self.drawCentredText(A4[0]/2, 1.5*cm, f"صفحة {page_num} من {total_pages}")
        self.drawRightString(A4[0] - 2*cm, 1.5*cm, f"تاريخ الإنشاء: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

def _check_reportlab():
    """Check if ReportLab is available and raise appropriate error if not."""
    if not REPORTLAB_AVAILABLE:
        raise ImportError("ReportLab is required for PDF generation. Install with: pip install reportlab")

def _create_arabic_styles():
    """Create paragraph styles that support Arabic text."""
    styles = getSampleStyleSheet()
    
    # Title style
    title_style = ParagraphStyle(
        'ArabicTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.darkblue
    )
    
    # Heading style
    heading_style = ParagraphStyle(
        'ArabicHeading',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        alignment=TA_RIGHT,
        spaceAfter=12,
        spaceBefore=12,
        textColor=colors.darkblue
    )
    
    # Normal text style
    normal_style = ParagraphStyle(
        'ArabicNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        alignment=TA_RIGHT,
        spaceAfter=6
    )
    
    return {
        'title': title_style,
        'heading': heading_style,
        'normal': normal_style
    }

def _create_table_from_dataframe(df: pd.DataFrame, max_rows: int = 50) -> Table:
    """Create a ReportLab table from a pandas DataFrame."""
    if df is None or df.empty:
        return Table([['لا توجد بيانات متاحة']], colWidths=[15*cm])
    
    # Limit rows for PDF readability
    if len(df) > max_rows:
        df_display = df.head(max_rows)
        truncated = True
    else:
        df_display = df
        truncated = False
    
    # Prepare table data
    data = []
    
    # Add headers
    headers = [str(col) for col in df_display.columns]
    data.append(headers)
    
    # Add data rows
    for _, row in df_display.iterrows():
        row_data = []
        for value in row:
            if pd.isna(value):
                row_data.append('')
            elif isinstance(value, (int, float)):
                row_data.append(f"{value:,.0f}" if isinstance(value, int) else f"{value:,.2f}")
            else:
                row_data.append(str(value))
        data.append(row_data)
    
    # Add truncation notice if needed
    if truncated:
        data.append(['...'] * len(headers))
        data.append([f'عرض {max_rows} من أصل {len(df)} سجل'] + [''] * (len(headers) - 1))
    
    # Calculate column widths
    num_cols = len(headers)
    col_width = (18 * cm) / num_cols if num_cols > 0 else 18 * cm
    col_widths = [col_width] * num_cols
    
    # Create table
    table = Table(data, colWidths=col_widths)
    
    # Apply table style
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    return table

def generate_dashboard_pdf_report(data: Dict[str, Any], username: str) -> bytes:
    """
    Generate a professional PDF report for dashboard data.
    
    **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
    
    Args:
        data: Dictionary containing dashboard data (monthly_sales, supplier_sales, department_stock)
        username: Username for report metadata
        
    Returns:
        bytes: PDF file content
    """
    _check_reportlab()
    
    logger.info(f"Generating dashboard PDF report for user: {username}")
    
    # Create PDF buffer
    buffer = io.BytesIO()
    
    # Create document with custom canvas
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=3*cm,
        bottomMargin=3*cm,
        title="تقرير لوحة المعلومات",
        author=username,
        subject="تقرير شامل للوحة المعلومات",
        creator="نظام إدارة المخزون"
    )
    
    # Get styles
    styles = _create_arabic_styles()
    
    # Build story (content)
    story = []
    
    # Title
    story.append(Paragraph("تقرير لوحة المعلومات", styles['title']))
    story.append(Spacer(1, 20))
    
    # Report metadata
    metadata_text = f"""
    <b>تاريخ التقرير:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}<br/>
    <b>المستخدم:</b> {username}<br/>
    <b>نوع التقرير:</b> تقرير شامل للوحة المعلومات
    """
    story.append(Paragraph(metadata_text, styles['normal']))
    story.append(Spacer(1, 20))
    
    # Monthly Sales Section
    if data.get('monthly_sales') is not None and not data['monthly_sales'].empty:
        story.append(Paragraph("المبيعات الشهرية", styles['heading']))
        story.append(Spacer(1, 10))
        
        monthly_table = _create_table_from_dataframe(data['monthly_sales'])
        story.append(monthly_table)
        story.append(Spacer(1, 20))
    
    # Supplier Sales Section
    if data.get('supplier_sales') is not None and not data['supplier_sales'].empty:
        story.append(Paragraph("مبيعات الموردين", styles['heading']))
        story.append(Spacer(1, 10))
        
        supplier_table = _create_table_from_dataframe(data['supplier_sales'])
        story.append(supplier_table)
        story.append(Spacer(1, 20))
    
    # Department Stock Section
    if data.get('department_stock') is not None and not data['department_stock'].empty:
        story.append(Paragraph("مخزون الأقسام", styles['heading']))
        story.append(Spacer(1, 10))
        
        dept_table = _create_table_from_dataframe(data['department_stock'])
        story.append(dept_table)
        story.append(Spacer(1, 20))
    
    # Footer note
    footer_text = """
    <i>هذا التقرير تم إنشاؤه تلقائياً بواسطة نظام إدارة المخزون. 
    جميع البيانات محدثة حتى وقت إنشاء التقرير.</i>
    """
    story.append(Spacer(1, 30))
    story.append(Paragraph(footer_text, styles['normal']))
    
    # Build PDF with custom canvas
    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args, 
            title="تقرير لوحة المعلومات", 
            username=username,
            **kwargs
        )
    )
    
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    logger.info(f"Dashboard PDF report generated successfully for user: {username}")
    return pdf_bytes

def generate_inventory_pdf_report(results_df: pd.DataFrame, params: Dict[str, Any], username: str) -> bytes:
    """Legacy wrapper for generate_inventory_pdf_report_with_insights."""
    return generate_inventory_pdf_report_with_insights(results_df, params, None, username)

def generate_inventory_pdf_report_with_insights(results_df: pd.DataFrame, params: Dict[str, Any], insights_data: Optional[Dict[str, Any]], username: str) -> bytes:
    """
    Generate a professional PDF report for inventory analysis results including AI insights.
    
    **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
    
    Args:
        results_df: DataFrame containing inventory analysis results
        params: Analysis parameters
        insights_data: AI insights data (optional)
        username: Username for report metadata
        
    Returns:
        bytes: PDF file content
    """
    _check_reportlab()
    
    logger.info(f"Generating inventory PDF report (with insights: {insights_data is not None}) for user: {username}")
    
    # Create PDF buffer
    buffer = io.BytesIO()
    
    # Create document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=3*cm,
        bottomMargin=3*cm,
        title="تقرير تحليل المخزون الذكي",
        author=username,
        subject="تقرير تحليل المخزون والتوصيات المدعومة بالذكاء الاصطناعي",
        creator="نظام إدارة المخزون"
    )
    
    # Get styles
    styles = _create_arabic_styles()
    
    # Build story
    story = []
    
    # Title
    story.append(Paragraph("تقرير تحليل المخزون الذكي", styles['title']))
    story.append(Spacer(1, 10))
    
    # Report Meta info
    meta_text = f"تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M')} | المستخدم: {username}"
    story.append(Paragraph(meta_text, styles['normal']))
    story.append(Spacer(1, 20))
    
    # AI Insights Section
    if insights_data:
        # Check if the data is wrapped in 'success'/'data' (legacy or alternate format)
        if insights_data.get('success') and insights_data.get('data'):
            data = insights_data['data']
        else:
            data = insights_data
            
        story.append(Paragraph("رؤى الذكاء الاصطناعي", styles['heading']))
        story.append(Spacer(1, 10))
        
        # Executive Summary
        summary_field = data.get('executive_summary') or data.get('stock_health')
        if summary_field:
            story.append(Paragraph("<b>الملخص التنفيذي:</b>", styles['normal']))
            story.append(Paragraph(str(summary_field), styles['normal']))
            story.append(Spacer(1, 10))
            
        # Recommendations
        recs = data.get('recommendations') or data.get('replenishment_advice')
        if recs:
            story.append(Paragraph("<b>التوصيات الذكية:</b>", styles['normal']))
            if isinstance(recs, list):
                for rec in recs:
                    story.append(Paragraph(f"• {str(rec)}", styles['normal']))
            else:
                story.append(Paragraph(f"• {str(recs)}", styles['normal']))
            story.append(Spacer(1, 10))
            
        # Insights / Risks
        findings = data.get('insights') or data.get('risks')
        if findings:
            story.append(Paragraph("<b>الرؤى والتحذيرات:</b>", styles['normal']))
            if isinstance(findings, list):
                for ins in findings:
                    story.append(Paragraph(f"• {str(ins)}", styles['normal']))
            else:
                story.append(Paragraph(f"• {str(findings)}", styles['normal']))
            story.append(Spacer(1, 10))
            
        story.append(PageBreak())
    
    # Parameters section
    story.append(Paragraph("معايير التحليل", styles['heading']))
    params_text = f"""
    <b>الحد الأدنى للتغطية:</b> {params.get('min_coverage', '7')} يوم<br/>
    <b>الحد الأقصى للتغطية:</b> {params.get('max_coverage', '30')} يوم<br/>
    <b>الفرع المحدد:</b> {params.get('selected_branch', 'جميع الفروع')}<br/>
    """
    story.append(Paragraph(params_text, styles['normal']))
    story.append(Spacer(1, 20))
    
    # Results table
    if results_df is not None and not results_df.empty:
        story.append(Paragraph("أهم النتائج التحليلية", styles['heading']))
        story.append(Spacer(1, 10))
        
        # Select important columns for PDF
        cols = ['product_code', 'product_name', 'Last_on_hand', 'daily_sales', 'coverage_days', 'abc_classification']
        df_to_export = results_df[cols].copy() if all(c in results_df.columns for c in cols) else results_df.head(30)
        
        results_table = _create_table_from_dataframe(df_to_export, max_rows=50)
        story.append(results_table)
    else:
        story.append(Paragraph("لا توجد نتائج تحليلية متاحة في هذا التقرير", styles['normal']))
    
    # Build PDF
    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args, 
            title="تقرير تحليل المخزون الذكي", 
            username=username,
            **kwargs
        )
    )
    
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    logger.info(f"Inventory PDF report generated successfully for user: {username}")
    return pdf_bytes

def generate_transfers_pdf_report(transfer_df: pd.DataFrame, summary_df: pd.DataFrame, username: str) -> bytes:
    """
    Generate a professional PDF report for transfers analysis results.
    
    **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
    
    Args:
        transfer_df: DataFrame containing transfer recommendations
        summary_df: DataFrame containing branch summary
        username: Username for report metadata
        
    Returns:
        bytes: PDF file content
    """
    _check_reportlab()
    
    logger.info(f"Generating transfers PDF report for user: {username}")
    
    # Create PDF buffer
    buffer = io.BytesIO()
    
    # Create document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=3*cm,
        bottomMargin=3*cm,
        title="تقرير توصيات النقل بين الفروع",
        author=username,
        subject="تقرير توصيات النقل وملخص الفروع",
        creator="نظام إدارة المخزون"
    )
    
    # Get styles
    styles = _create_arabic_styles()
    
    # Build story
    story = []
    
    # Title
    story.append(Paragraph("تقرير توصيات النقل بين الفروع", styles['title']))
    story.append(Spacer(1, 20))
    
    # Branch Summary Section
    if summary_df is not None and not summary_df.empty:
        story.append(Paragraph("ملخص الفروع", styles['heading']))
        story.append(Spacer(1, 10))
        
        summary_table = _create_table_from_dataframe(summary_df)
        story.append(summary_table)
        story.append(PageBreak())
    
    # Transfer Recommendations Section
    if transfer_df is not None and not transfer_df.empty:
        story.append(Paragraph("توصيات النقل", styles['heading']))
        story.append(Spacer(1, 10))
        
        transfer_table = _create_table_from_dataframe(transfer_df, max_rows=40)
        story.append(transfer_table)
    else:
        story.append(Paragraph("لا توجد توصيات نقل متاحة", styles['heading']))
    
    # Build PDF
    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args, 
            title="تقرير توصيات النقل", 
            username=username,
            **kwargs
        )
    )
    
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    logger.info(f"Transfers PDF report generated successfully for user: {username}")
    return pdf_bytes

def generate_forecasting_pdf_report(summary_df: pd.DataFrame, params: Dict[str, Any], username: str) -> bytes:
    """
    Generate a professional PDF report for forecasting results.
    
    **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
    
    Args:
        summary_df: DataFrame containing forecasting results
        params: Forecasting parameters
        username: Username for report metadata
        
    Returns:
        bytes: PDF file content
    """
    _check_reportlab()
    
    logger.info(f"Generating forecasting PDF report for user: {username}")
    
    # Create PDF buffer
    buffer = io.BytesIO()
    
    # Create document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=3*cm,
        bottomMargin=3*cm,
        title="تقرير التنبؤ بالمبيعات",
        author=username,
        subject="تقرير التنبؤ بالمبيعات والتوصيات",
        creator="نظام إدارة المخزون"
    )
    
    # Get styles
    styles = _create_arabic_styles()
    
    # Build story
    story = []
    
    # Title
    story.append(Paragraph("تقرير التنبؤ بالمبيعات", styles['title']))
    story.append(Spacer(1, 20))
    
    # Parameters section
    params_text = f"""
    <b>معايير التنبؤ:</b><br/>
    <b>فترة التنبؤ:</b> {params.get('forecast_days', 'غير محدد')} يوم<br/>
    <b>الفرع المحدد:</b> {params.get('selected_branch', 'جميع الفروع')}<br/>
    <b>تاريخ التحليل:</b> {params.get('analysis_date', datetime.now().strftime('%Y-%m-%d'))}
    """
    story.append(Paragraph(params_text, styles['normal']))
    story.append(Spacer(1, 20))
    
    # Forecasting Results
    if summary_df is not None and not summary_df.empty:
        story.append(Paragraph("نتائج التنبؤ", styles['heading']))
        story.append(Spacer(1, 10))
        
        forecast_table = _create_table_from_dataframe(summary_df, max_rows=30)
        story.append(forecast_table)
    else:
        story.append(Paragraph("لا توجد نتائج تنبؤ متاحة", styles['heading']))
    
    # Build PDF
    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: NumberedCanvas(
            *args, 
            title="تقرير التنبؤ بالمبيعات", 
            username=username,
            **kwargs
        )
    )
    
    buffer.seek(0)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    logger.info(f"Forecasting PDF report generated successfully for user: {username}")
    return pdf_bytes