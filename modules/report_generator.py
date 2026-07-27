import io
import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

# --- Base Report Class ---
class BaseReport:
    """
    Base class for all PDF reports to ensure consistent branding and layout.
    """
    def __init__(self, title="Analysis Report", author="TIF App AI System"):
        self.title = title
        self.author = author
        self.elements = []
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(name='MainTitle', parent=self.styles['Heading1'], alignment=1, fontSize=24, spaceAfter=24, textColor=colors.HexColor('#1a365d')))
        self.styles.add(ParagraphStyle(name='SectionHeader', parent=self.styles['Heading2'], fontSize=16, spaceBefore=18, spaceAfter=12, textColor=colors.HexColor('#2c5282'), borderPadding=5, borderColor=colors.HexColor('#e2e8f0'), borderWidth=0, borderRadius=5))
        self.styles.add(ParagraphStyle(name='NormalJustified', parent=self.styles['Normal'], alignment=4, spaceAfter=8))
        self.styles.add(ParagraphStyle(name='InsightBox', parent=self.styles['Normal'], backColor=colors.HexColor('#ebf8ff'), borderColor=colors.HexColor('#bee3f8'), borderWidth=1, borderPadding=10, borderRadius=5, spaceAfter=15))

    def add_header(self, subtitle=""):
        self.elements.append(Paragraph(self.title, self.styles['MainTitle']))
        if subtitle:
            self.elements.append(Paragraph(subtitle, self.styles['Heading3']))
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.elements.append(Paragraph(f"Generated on: {timestamp} | Author: {self.author}", self.styles['Normal']))
        self.elements.append(Spacer(1, 0.3 * inch))

    def add_section(self, title):
        self.elements.append(Paragraph(title, self.styles['SectionHeader']))

    def add_ai_insights(self, insights):
        """
        Standardized display for AI insights.
        """
        self.add_section("AI Analytical Insights")
        
        content = []
        if isinstance(insights, dict):
            for key, value in insights.items():
                formatted_key = key.replace('_', ' ').upper()
                if isinstance(value, list):
                    content.append(f"<b>{formatted_key}:</b><br/>" + "<br/>".join([f"• {item}" for item in value]))
                else:
                    content.append(f"<b>{formatted_key}:</b> {value}")
        elif isinstance(insights, list):
            content = [f"• {item}" for item in insights]
        else:
            content = [str(insights)]
            
        full_text = "<br/><br/>".join(content)
        self.elements.append(Paragraph(full_text, self.styles['InsightBox']))

    def add_table(self, data, headers=None, title=None):
        if title:
            self.elements.append(Paragraph(title, self.styles['Heading4']))
            
        if not data:
            self.elements.append(Paragraph("No data available for this section.", self.styles['Normal']))
            return

        table_data = []
        if headers:
            table_data.append(headers)
        
        # Ensure data is string
        for row in data:
            table_data.append([str(cell) for cell in row])

        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0'))
        ]))
        
        self.elements.append(t)
        self.elements.append(Spacer(1, 0.2 * inch))
        
    def generate(self):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
        doc.build(self.elements)
        buffer.seek(0)
        return buffer


# --- Dashboard Report ---
class DashboardReport(BaseReport):
    def __init__(self, kpis, insights):
        super().__init__(title="Executive Dashboard Summary")
        self.add_header("Business Performance Overview")
        self._build_content(kpis, insights)

    def _build_content(self, kpis, insights):
        # AI Insights First
        self.add_ai_insights(insights)
        
        # KPI Table
        self.add_section("Key Performance Indicators")
        kpi_data = [[k.replace('_', ' ').title(), v] for k, v in kpis.items()]
        self.add_table(kpi_data, headers=["Metric", "Value"])


# --- Inventory Report ---
class InventoryReport(BaseReport):
    def __init__(self, summary, insights):
        super().__init__(title="Inventory Health Analysis")
        self.add_header("Stock Optimization & Risks")
        self._build_content(summary, insights)
        
    def _build_content(self, summary, insights):
        self.add_ai_insights(insights)
        
        self.add_section("Stock Summary Details")
        if isinstance(summary, dict):
             data = [[k, v] for k, v in summary.items()]
             self.add_table(data, headers=["Category", "Details"])


# --- Transfer Report ---
class BranchTransferReport(BaseReport):
    def __init__(self, transfers, insights):
        super().__init__(title="Branch Transfer Recommendations")
        self.add_header("Smart Logistics Engine")
        self._build_content(transfers, insights)
        
    def _build_content(self, transfers, insights):
         self.add_ai_insights(insights)
         
         self.add_section("Proposed Transfers")
         if transfers and isinstance(transfers, list):
            if isinstance(transfers[0], dict):
                headers = list(transfers[0].keys())
                data = [[row.get(h, "") for h in headers] for row in transfers]
                self.add_table(data, headers=headers)


# --- Forecast Report ---
class ForecastReport(BaseReport):
    def __init__(self, forecast_df, insights, metrics):
        super().__init__(title="AI Sales Forecast")
        self.add_header("Predictive Analytics & Strategy")
        self._build_content(forecast_df, insights, metrics)
        
    def _build_content(self, forecast_df, insights, metrics):
        self.add_ai_insights(insights)
        
        self.add_section("Model Performance Metrics")
        if metrics:
            metric_data = [[k, v] for k, v in metrics.items()]
            self.add_table(metric_data, headers=["Metric", "Value"])
            
        self.add_section("Forecasted Sales Data (Next 30 Days)")
        if not forecast_df.empty:
            headers = list(forecast_df.columns)
            data = forecast_df.head(30).values.tolist()
            self.add_table(data, headers=headers)


# --- Factory Functions to maintain compatibility with existing calls ---

def report_dashboard(kpis, insights):
    report = DashboardReport(kpis, insights)
    return report.generate()

def report_inventory(summary, insights):
    report = InventoryReport(summary, insights)
    return report.generate()

def report_branch_transfer(transfers, insights):
    report = BranchTransferReport(transfers, insights)
    return report.generate()

def report_sales_forecasting(forecast_df, insights, metrics):
    report = ForecastReport(forecast_df, insights, metrics)
    return report.generate()
