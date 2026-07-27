"""
Smart Report Generator
Creates AI-enhanced reports with executive summaries and intelligent analysis.
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)


class SmartReportGenerator:
    """
    Generates AI-enhanced reports with contextual analysis and recommendations.
    
    Provides executive summary generation, trend identification, and
    business intelligence for inventory and sales reports.
    """
    
    def __init__(self, ai_service):
        """
        Initialize the smart report generator.
        
        Args:
            ai_service: AI service instance for generating insights
        """
        self.ai_service = ai_service
        
        # Define report templates
        self.report_templates = {
            'inventory': {
                'title': 'تقرير المخزون الذكي',
                'sections': ['executive_summary', 'stock_analysis', 'trends', 'recommendations'],
                'metrics': ['total_products', 'stock_value', 'turnover_rate', 'low_stock_alerts']
            },
            'sales': {
                'title': 'تقرير المبيعات الذكي',
                'sections': ['executive_summary', 'revenue_analysis', 'trends', 'recommendations'],
                'metrics': ['total_revenue', 'transaction_count', 'avg_transaction', 'growth_rate']
            },
            'performance': {
                'title': 'تقرير الأداء الذكي',
                'sections': ['executive_summary', 'kpi_analysis', 'trends', 'recommendations'],
                'metrics': ['efficiency_score', 'target_achievement', 'trend_direction', 'risk_factors']
            },
            'forecast': {
                'title': 'تقرير التنبؤات الذكي',
                'sections': ['executive_summary', 'forecast_analysis', 'confidence_intervals', 'recommendations'],
                'metrics': ['predicted_demand', 'confidence_score', 'risk_assessment', 'action_items']
            }
        }
    
    def generate_executive_summary(self, data: Dict) -> str:
        """
        Generate executive summary for report data.
        
        Args:
            data: Report data dictionary
            
        Returns:
            Executive summary text
        """
        try:
            # Extract key metrics
            key_metrics = self._extract_key_metrics(data)
            
            # Generate summary based on data type
            report_type = data.get('report_type', 'general')
            
            if report_type == 'inventory':
                return self._generate_inventory_summary(key_metrics)
            elif report_type == 'sales':
                return self._generate_sales_summary(key_metrics)
            elif report_type == 'performance':
                return self._generate_performance_summary(key_metrics)
            elif report_type == 'forecast':
                return self._generate_forecast_summary(key_metrics)
            else:
                return self._generate_general_summary(key_metrics)
                
        except Exception as e:
            logger.error(f"Error generating executive summary: {e}")
            return "تعذر إنشاء الملخص التنفيذي. يرجى المحاولة مرة أخرى."
    
    def identify_trends_and_patterns(self, data: Dict) -> Dict:
        """
        Identify key trends and patterns in the data.
        
        Args:
            data: Report data dictionary
            
        Returns:
            Dict containing identified trends and patterns
        """
        try:
            trends = {
                'positive_trends': [],
                'negative_trends': [],
                'patterns': [],
                'anomalies': [],
                'seasonal_effects': []
            }
            
            # Analyze different data types
            if 'sales_data' in data:
                sales_trends = self._analyze_sales_trends(data['sales_data'])
                trends.update(sales_trends)
            
            if 'inventory_data' in data:
                inventory_trends = self._analyze_inventory_trends(data['inventory_data'])
                trends.update(inventory_trends)
            
            if 'time_series_data' in data:
                time_trends = self._analyze_time_series_trends(data['time_series_data'])
                trends.update(time_trends)
            
            # Analyze performance data
            if 'efficiency_score' in data or 'kpi_metrics' in data:
                performance_trends = self._analyze_performance_trends(data)
                trends.update(performance_trends)
            
            # Analyze forecast data
            if 'forecast_data' in data:
                forecast_trends = self._analyze_forecast_trends(data['forecast_data'])
                trends.update(forecast_trends)
            
            return trends
            
        except Exception as e:
            logger.error(f"Error identifying trends and patterns: {e}")
            return {
                'positive_trends': [],
                'negative_trends': [],
                'patterns': [],
                'anomalies': [],
                'seasonal_effects': []
            }
    
    def generate_recommendations(self, analysis: Dict, business_context: Dict) -> List[str]:
        """
        Generate actionable recommendations based on analysis.
        
        Args:
            analysis: Analysis results dictionary
            business_context: Business context information
            
        Returns:
            List of actionable recommendations
        """
        try:
            recommendations = []
            
            # Generate recommendations based on trends
            trends = analysis.get('trends', {})
            
            # Inventory recommendations
            if 'low_stock_items' in analysis:
                low_stock = analysis['low_stock_items']
                if low_stock > 0:
                    recommendations.append(f"إعادة تخزين {low_stock} منتج بمستوى مخزون منخفض")
            
            # Sales recommendations
            if 'declining_products' in trends:
                declining = trends['declining_products']
                if declining:
                    recommendations.append("مراجعة استراتيجية التسويق للمنتجات ذات المبيعات المتراجعة")
            
            # Performance recommendations
            if 'efficiency_score' in analysis:
                efficiency = analysis['efficiency_score']
                if efficiency < 70:
                    recommendations.append("تحسين كفاءة العمليات لزيادة الإنتاجية")
            
            # Risk-based recommendations
            if 'risk_factors' in analysis:
                risks = analysis['risk_factors']
                for risk in risks:
                    if 'stock_out' in risk.lower():
                        recommendations.append("تطوير نظام تنبيهات مبكرة لنفاد المخزون")
                    elif 'demand_fluctuation' in risk.lower():
                        recommendations.append("تحسين دقة التنبؤ بالطلب")
            
            # Business context recommendations
            season = business_context.get('season', '')
            if season == 'peak':
                recommendations.append("زيادة مستويات المخزون استعداداً لموسم الذروة")
            elif season == 'low':
                recommendations.append("تحسين إدارة التدفق النقدي خلال الموسم المنخفض")
            
            # Default recommendations if none generated
            if not recommendations:
                recommendations = [
                    "مراجعة دورية لمستويات المخزون",
                    "تحليل اتجاهات المبيعات الشهرية",
                    "تحسين دقة التنبؤات"
                ]
            
            return recommendations[:10]  # Limit to top 10 recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return ["مراجعة البيانات وتحليل الأداء العام"]
    
    def create_enhanced_report(self, base_report: Dict, ai_insights: Dict) -> Dict:
        """
        Create enhanced report combining base data with AI insights.
        
        Args:
            base_report: Base report data
            ai_insights: AI-generated insights
            
        Returns:
            Enhanced report dictionary
        """
        try:
            report_type = base_report.get('report_type', 'general')
            template = self.report_templates.get(report_type, self.report_templates['inventory'])
            
            # Create enhanced report structure
            enhanced_report = {
                'title': template['title'],
                'generated_at': datetime.now().isoformat(),
                'report_type': report_type,
                'executive_summary': '',
                'key_metrics': {},
                'trends_and_patterns': {},
                'insights': [],
                'recommendations': [],
                'risk_assessment': '',
                'data_quality_score': 0,
                'confidence_score': 0,
                'sections': {}
            }
            
            # Generate executive summary
            enhanced_report['executive_summary'] = self.generate_executive_summary(base_report)
            
            # Extract key metrics
            enhanced_report['key_metrics'] = self._extract_key_metrics(base_report)
            
            # Identify trends and patterns
            enhanced_report['trends_and_patterns'] = self.identify_trends_and_patterns(base_report)
            
            # Generate insights
            enhanced_report['insights'] = self._generate_insights(base_report, ai_insights)
            
            # Generate recommendations
            business_context = base_report.get('business_context', {})
            analysis = {
                'trends': enhanced_report['trends_and_patterns'],
                **enhanced_report['key_metrics']
            }
            enhanced_report['recommendations'] = self.generate_recommendations(analysis, business_context)
            
            # Generate risk assessment
            enhanced_report['risk_assessment'] = self._generate_risk_assessment(base_report)
            
            # Calculate quality and confidence scores
            enhanced_report['data_quality_score'] = self._calculate_data_quality_score(base_report)
            enhanced_report['confidence_score'] = self._calculate_confidence_score(enhanced_report)
            
            # Create detailed sections
            for section in template['sections']:
                enhanced_report['sections'][section] = self._generate_section_content(
                    section, base_report, enhanced_report
                )
            
            return enhanced_report
            
        except Exception as e:
            logger.error(f"Error creating enhanced report: {e}")
            return {
                'title': 'تقرير ذكي',
                'generated_at': datetime.now().isoformat(),
                'error': str(e),
                'executive_summary': 'تعذر إنشاء التقرير المحسن',
                'recommendations': ['يرجى المحاولة مرة أخرى']
            }
    
    def _extract_key_metrics(self, data: Dict) -> Dict:
        """Extract key metrics from report data."""
        metrics = {}
        
        try:
            # Extract common metrics
            if 'total_products' in data:
                metrics['total_products'] = data['total_products']
            
            if 'total_revenue' in data:
                metrics['total_revenue'] = data['total_revenue']
            
            if 'inventory_value' in data:
                metrics['inventory_value'] = data['inventory_value']
            
            # Calculate derived metrics
            if 'sales_data' in data and isinstance(data['sales_data'], (list, pd.DataFrame)):
                sales_data = data['sales_data']
                if isinstance(sales_data, pd.DataFrame):
                    metrics['transaction_count'] = len(sales_data)
                    if 'revenue' in sales_data.columns:
                        metrics['avg_transaction'] = sales_data['revenue'].mean()
                        metrics['total_revenue'] = sales_data['revenue'].sum()
            
            if 'inventory_data' in data and isinstance(data['inventory_data'], (list, pd.DataFrame)):
                inventory_data = data['inventory_data']
                if isinstance(inventory_data, pd.DataFrame):
                    metrics['total_products'] = len(inventory_data)
                    
                    # Find stock quantity column
                    stock_cols = [col for col in inventory_data.columns 
                                if any(term in col.lower() for term in ['stock', 'quantity', 'on_hand'])]
                    if stock_cols:
                        stock_col = stock_cols[0]
                        metrics['low_stock_items'] = len(inventory_data[inventory_data[stock_col] < 10])
                        metrics['out_of_stock_items'] = len(inventory_data[inventory_data[stock_col] == 0])
            
        except Exception as e:
            logger.error(f"Error extracting key metrics: {e}")
        
        return metrics
    
    def _generate_inventory_summary(self, metrics: Dict) -> str:
        """Generate inventory-specific executive summary."""
        total_products = metrics.get('total_products', 0)
        low_stock = metrics.get('low_stock_items', 0)
        out_of_stock = metrics.get('out_of_stock_items', 0)
        
        summary = f"تحليل المخزون يظهر وجود {total_products} منتج في النظام. "
        
        if low_stock > 0 or out_of_stock > 0:
            summary += f"هناك {low_stock} منتج بمستوى مخزون منخفض و {out_of_stock} منتج نفد من المخزون. "
            summary += "يتطلب الأمر اتخاذ إجراءات فورية لإعادة التخزين."
        else:
            summary += "جميع المنتجات في مستوى مخزون مناسب."
        
        return summary
    
    def _generate_sales_summary(self, metrics: Dict) -> str:
        """Generate sales-specific executive summary."""
        total_revenue = metrics.get('total_revenue', 0)
        transaction_count = metrics.get('transaction_count', 0)
        avg_transaction = metrics.get('avg_transaction', 0)
        
        summary = f"تحليل المبيعات يظهر إجمالي إيرادات قدرها {total_revenue:,.2f} من {transaction_count} معاملة. "
        summary += f"متوسط قيمة المعاملة الواحدة {avg_transaction:,.2f}. "
        
        if avg_transaction > 100:
            summary += "الأداء جيد مع متوسط معاملات مرتفع."
        else:
            summary += "هناك فرصة لتحسين قيمة المعاملة الواحدة."
        
        return summary
    
    def _generate_performance_summary(self, metrics: Dict) -> str:
        """Generate performance-specific executive summary."""
        return "تحليل الأداء العام يظهر مؤشرات متنوعة تتطلب المراجعة والتحسين المستمر."
    
    def _generate_forecast_summary(self, metrics: Dict) -> str:
        """Generate forecast-specific executive summary."""
        return "تحليل التنبؤات يوفر رؤى مستقبلية لاتخاذ قرارات استراتيجية مدروسة."
    
    def _generate_general_summary(self, metrics: Dict) -> str:
        """Generate general executive summary."""
        return "التحليل العام للبيانات يوفر نظرة شاملة على الأداء الحالي والفرص المتاحة للتحسين."
    
    def _analyze_sales_trends(self, sales_data) -> Dict:
        """Analyze sales trends from data."""
        trends = {
            'positive_trends': [],
            'negative_trends': []
        }
        
        try:
            if isinstance(sales_data, pd.DataFrame) and 'revenue' in sales_data.columns:
                # Simple trend analysis
                recent_avg = sales_data['revenue'].tail(10).mean()
                overall_avg = sales_data['revenue'].mean()
                
                if recent_avg > overall_avg * 1.1:
                    trends['positive_trends'].append('اتجاه تصاعدي في المبيعات الأخيرة')
                elif recent_avg < overall_avg * 0.9:
                    trends['negative_trends'].append('انخفاض في المبيعات الأخيرة')
        except Exception as e:
            logger.error(f"Error analyzing sales trends: {e}")
        
        return trends
    
    def _analyze_inventory_trends(self, inventory_data) -> Dict:
        """Analyze inventory trends from data."""
        trends = {
            'patterns': []
        }
        
        try:
            if isinstance(inventory_data, pd.DataFrame):
                # Find stock columns
                stock_cols = [col for col in inventory_data.columns 
                            if any(term in col.lower() for term in ['stock', 'quantity', 'on_hand'])]
                
                if stock_cols:
                    stock_col = stock_cols[0]
                    low_stock_ratio = len(inventory_data[inventory_data[stock_col] < 10]) / len(inventory_data)
                    
                    if low_stock_ratio > 0.2:
                        trends['patterns'].append('نسبة عالية من المنتجات بمستوى مخزون منخفض')
                    elif low_stock_ratio < 0.05:
                        trends['patterns'].append('مستويات مخزون صحية عبر معظم المنتجات')
        except Exception as e:
            logger.error(f"Error analyzing inventory trends: {e}")
        
        return trends
    
    def _analyze_time_series_trends(self, time_series_data) -> Dict:
        """Analyze time series trends."""
        return {'seasonal_effects': ['تحليل الاتجاهات الزمنية متاح']}
    
    def _analyze_performance_trends(self, data: Dict) -> Dict:
        """Analyze performance trends from data."""
        trends = {
            'positive_trends': [],
            'negative_trends': [],
            'patterns': []
        }
        
        try:
            # Analyze efficiency score
            efficiency_score = data.get('efficiency_score', 0)
            if efficiency_score >= 80:
                trends['positive_trends'].append('مستوى كفاءة عالي في الأداء')
            elif efficiency_score <= 50:
                trends['negative_trends'].append('مستوى كفاءة منخفض يحتاج تحسين')
            else:
                trends['patterns'].append('مستوى كفاءة متوسط مع إمكانية للتحسين')
            
            # Analyze target achievement
            target_achievement = data.get('target_achievement', 0)
            if target_achievement >= 1.2:
                trends['positive_trends'].append('تجاوز الأهداف المحددة بشكل ممتاز')
            elif target_achievement >= 1.0:
                trends['positive_trends'].append('تحقيق الأهداف المحددة')
            elif target_achievement >= 0.8:
                trends['patterns'].append('اقتراب من تحقيق الأهداف')
            else:
                trends['negative_trends'].append('عدم تحقيق الأهداف المطلوبة')
            
            # Analyze KPI metrics
            kpi_metrics = data.get('kpi_metrics', {})
            if kpi_metrics:
                avg_kpi = sum(kpi_metrics.values()) / len(kpi_metrics)
                if avg_kpi >= 85:
                    trends['positive_trends'].append('مؤشرات الأداء الرئيسية ممتازة')
                elif avg_kpi >= 70:
                    trends['patterns'].append('مؤشرات الأداء الرئيسية جيدة')
                else:
                    trends['negative_trends'].append('مؤشرات الأداء الرئيسية تحتاج تحسين')
        
        except Exception as e:
            logger.error(f"Error analyzing performance trends: {e}")
        
        return trends
    
    def _analyze_forecast_trends(self, forecast_data) -> Dict:
        """Analyze forecast trends from data."""
        trends = {
            'patterns': [],
            'seasonal_effects': []
        }
        
        try:
            if isinstance(forecast_data, list) and len(forecast_data) > 0:
                # Analyze demand patterns
                total_demand = sum(f.get('predicted_demand', 0) for f in forecast_data)
                if total_demand > 0:
                    trends['patterns'].append('توقعات طلب إيجابية للفترة القادمة')
                
                # Check for seasonal patterns (simplified)
                if len(forecast_data) >= 12:  # Monthly data
                    trends['seasonal_effects'].append('تحليل الأنماط الموسمية متاح')
        
        except Exception as e:
            logger.error(f"Error analyzing forecast trends: {e}")
        
        return trends
    
    def _generate_insights(self, base_report: Dict, ai_insights: Dict) -> List[str]:
        """Generate insights from base report and AI analysis."""
        insights = []
        
        # Extract insights from AI response
        if isinstance(ai_insights, dict):
            if 'insights' in ai_insights:
                insights.extend(ai_insights['insights'])
            if 'key_findings' in ai_insights:
                insights.extend(ai_insights['key_findings'])
        
        # Generate insights from data patterns
        metrics = self._extract_key_metrics(base_report)
        
        if metrics.get('low_stock_items', 0) > 0:
            insights.append(f"يوجد {metrics['low_stock_items']} منتج يحتاج إعادة تخزين")
        
        if metrics.get('total_revenue', 0) > 10000:
            insights.append("الأداء المالي يظهر نتائج إيجابية")
        
        return insights[:5]  # Limit to top 5 insights
    
    def _generate_risk_assessment(self, base_report: Dict) -> str:
        """Generate risk assessment for the report."""
        risks = []
        
        metrics = self._extract_key_metrics(base_report)
        
        if metrics.get('out_of_stock_items', 0) > 0:
            risks.append('مخاطر نفاد المخزون')
        
        if metrics.get('low_stock_items', 0) > metrics.get('total_products', 1) * 0.3:
            risks.append('مخاطر عدم كفاية المخزون')
        
        if not risks:
            return "مستوى المخاطر منخفض - الوضع مستقر"
        
        return f"مخاطر محددة: {', '.join(risks)}"
    
    def _calculate_data_quality_score(self, data: Dict) -> int:
        """Calculate data quality score (0-100)."""
        score = 100
        
        # Deduct points for missing data
        sales_data = data.get('sales_data')
        if sales_data is None or (hasattr(sales_data, 'empty') and sales_data.empty):
            score -= 20
        
        inventory_data = data.get('inventory_data')
        if inventory_data is None or (hasattr(inventory_data, 'empty') and inventory_data.empty):
            score -= 20
        
        # Check data completeness
        if isinstance(inventory_data, pd.DataFrame) and not inventory_data.empty:
            df = inventory_data
            missing_ratio = df.isnull().sum().sum() / (len(df) * len(df.columns))
            score -= int(missing_ratio * 30)
        
        return max(0, min(100, score))
    
    def _calculate_confidence_score(self, report: Dict) -> int:
        """Calculate confidence score for the report (0-100)."""
        base_score = 75
        
        # Increase confidence based on data quality
        data_quality = report.get('data_quality_score', 50)
        confidence_adjustment = (data_quality - 50) * 0.3
        
        # Adjust based on number of insights
        insights_count = len(report.get('insights', []))
        if insights_count >= 3:
            confidence_adjustment += 10
        
        final_score = base_score + confidence_adjustment
        return max(0, min(100, int(final_score)))
    
    def _generate_section_content(self, section: str, base_report: Dict, enhanced_report: Dict) -> Dict:
        """Generate content for a specific report section."""
        if section == 'executive_summary':
            return {
                'title': 'الملخص التنفيذي',
                'content': enhanced_report['executive_summary']
            }
        elif section == 'stock_analysis':
            return {
                'title': 'تحليل المخزون',
                'content': self._generate_stock_analysis_content(base_report)
            }
        elif section == 'trends':
            return {
                'title': 'الاتجاهات والأنماط',
                'content': enhanced_report['trends_and_patterns']
            }
        elif section == 'recommendations':
            return {
                'title': 'التوصيات',
                'content': enhanced_report['recommendations']
            }
        else:
            return {
                'title': section.replace('_', ' ').title(),
                'content': f'محتوى قسم {section}'
            }
    
    def _generate_stock_analysis_content(self, base_report: Dict) -> str:
        """Generate stock analysis content."""
        metrics = self._extract_key_metrics(base_report)
        
        content = f"تحليل تفصيلي للمخزون:\n"
        content += f"- إجمالي المنتجات: {metrics.get('total_products', 0)}\n"
        content += f"- منتجات بمخزون منخفض: {metrics.get('low_stock_items', 0)}\n"
        content += f"- منتجات نفدت من المخزون: {metrics.get('out_of_stock_items', 0)}\n"
        
        return content