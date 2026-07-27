"""
Enhanced Forecasting System
Integrates AI capabilities with existing forecasting modules for improved accuracy and insights.
"""
import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ForecastEnhancement:
    """Enhanced forecast result with AI insights."""
    original_forecast: Dict
    enhanced_forecast: Dict
    confidence_intervals: Dict
    risk_factors: List[str]
    external_factors: List[str]
    adjustments: List[str]
    recommendations: List[str]
    confidence_score: float
    processing_time: float
    timestamp: datetime


class EnhancedForecastingSystem:
    """
    Enhanced forecasting system that combines traditional forecasting with AI insights.
    
    Provides confidence intervals, risk assessments, and external factor analysis
    for comprehensive demand planning.
    """
    
    def __init__(self, ai_service=None):
        """
        Initialize the enhanced forecasting system.
        
        Args:
            ai_service: AI service instance for generating insights
        """
        self.ai_service = ai_service
        
        # Define forecast enhancement templates
        self.enhancement_templates = {
            'confidence_intervals': {
                'high_confidence': {'lower': 0.85, 'upper': 1.15},
                'medium_confidence': {'lower': 0.70, 'upper': 1.30},
                'low_confidence': {'lower': 0.50, 'upper': 1.50}
            },
            'risk_factors': [
                'seasonal_variation',
                'market_volatility',
                'supply_chain_disruption',
                'competitor_activity',
                'economic_conditions',
                'weather_impact',
                'promotional_effects'
            ],
            'external_factors': [
                'holidays_and_events',
                'market_trends',
                'economic_indicators',
                'weather_patterns',
                'competitor_actions',
                'regulatory_changes'
            ]
        }
    
    def enhance_forecast_with_ai(self, forecast_data: Dict, historical_data: Dict, 
                                business_context: Dict = None) -> ForecastEnhancement:
        """
        Enhance forecast using AI analysis and traditional statistical methods.
        
        Args:
            forecast_data: Current forecast data
            historical_data: Historical sales/demand data
            business_context: Additional business context information
            
        Returns:
            ForecastEnhancement with enhanced predictions and insights
        """
        start_time = datetime.now()
        
        try:
            # Prepare data for analysis
            prepared_forecast = self._prepare_forecast_data(forecast_data)
            prepared_historical = self._prepare_historical_data(historical_data)
            
            # Calculate confidence intervals using statistical methods
            confidence_intervals = self._calculate_confidence_intervals(
                prepared_forecast, prepared_historical
            )
            
            # Identify risk factors
            risk_factors = self._identify_risk_factors(
                prepared_forecast, prepared_historical, business_context
            )
            
            # Analyze external factors
            external_factors = self._analyze_external_factors(
                prepared_forecast, business_context
            )
            
            # Generate AI-powered insights if available
            ai_insights = {}
            if self.ai_service is not None:
                try:
                    # Route forecast enhancement through the active AI provider
                    # (Phase 3, §4): circuit breaker + anonymization are already
                    # handled by the provider-backed service. No direct Gemini
                    # coupling remains here.
                    anonymized_forecast = self.ai_service._anonymize_inventory_data(forecast_data)
                    anonymized_historical = self.ai_service._anonymize_inventory_data(historical_data)
                    provider = getattr(self.ai_service, 'provider', None)
                    if provider is not None:
                        resp = provider.enhance_forecast(
                            anonymized_forecast, anonymized_historical)
                        if getattr(resp, 'success', False) and isinstance(resp.data, dict):
                            ai_insights = resp.data
                        elif getattr(resp, 'data', None) and isinstance(resp.data, dict):
                            ai_insights = resp.data
                        else:
                            ai_insights = {'error': getattr(resp, 'error_message', 'provider returned no data')}
                    else:
                        raise ImportError("No AI provider available")
                except Exception:
                    logger.warning("AI forecast enhancement provider unavailable, using fallback insights")
                    ai_insights = {
                        'forecast_validation': 'AI insights not available',
                        'confidence_score': 70,
                        'recommendations': ['تحسين دقة البيانات', 'مراجعة النماذج دورياً']
                    }

            
            # Generate adjustments and recommendations
            adjustments = self._generate_forecast_adjustments(
                prepared_forecast, confidence_intervals, risk_factors, ai_insights
            )
            
            recommendations = self._generate_forecast_recommendations(
                prepared_forecast, risk_factors, external_factors, ai_insights
            )
            
            # Create enhanced forecast
            enhanced_forecast = self._create_enhanced_forecast(
                prepared_forecast, adjustments, confidence_intervals
            )
            
            # Calculate overall confidence score
            confidence_score = self._calculate_overall_confidence_score(
                confidence_intervals, risk_factors, ai_insights
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return ForecastEnhancement(
                original_forecast=prepared_forecast,
                enhanced_forecast=enhanced_forecast,
                confidence_intervals=confidence_intervals,
                risk_factors=risk_factors,
                external_factors=external_factors,
                adjustments=adjustments,
                recommendations=recommendations,
                confidence_score=confidence_score,
                processing_time=processing_time,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Enhanced forecasting failed: {e}")
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Return fallback enhancement
            return ForecastEnhancement(
                original_forecast=forecast_data,
                enhanced_forecast=forecast_data,
                confidence_intervals={'lower': 0.8, 'upper': 1.2},
                risk_factors=['تعذر تحليل المخاطر'],
                external_factors=['تعذر تحليل العوامل الخارجية'],
                adjustments=['لا توجد تعديلات متاحة'],
                recommendations=['مراجعة البيانات وإعادة المحاولة'],
                confidence_score=50.0,
                processing_time=processing_time,
                timestamp=datetime.now()
            )
    
    def integrate_with_existing_forecast(self, forecast_file_path: str, 
                                       historical_data: Dict = None) -> Dict:
        """
        Integrate AI enhancements with existing forecast files.
        
        Args:
            forecast_file_path: Path to existing forecast file
            historical_data: Historical data for context
            
        Returns:
            Enhanced forecast data dictionary
        """
        try:
            # Load existing forecast
            if forecast_file_path.endswith('.xlsx'):
                forecast_df = pd.read_excel(forecast_file_path)
            elif forecast_file_path.endswith('.csv'):
                forecast_df = pd.read_csv(forecast_file_path)
            else:
                raise ValueError(f"Unsupported file format: {forecast_file_path}")
            
            # Convert to dictionary format
            forecast_data = {
                'forecast_df': forecast_df,
                'file_path': forecast_file_path,
                'total_products': len(forecast_df),
                'forecast_period': self._extract_forecast_period(forecast_df)
            }
            
            # Enhance the forecast
            enhancement = self.enhance_forecast_with_ai(forecast_data, historical_data or {})
            
            # Create enhanced output
            enhanced_output = {
                'original_forecast': forecast_data,
                'enhancement': enhancement,
                'enhanced_df': self._create_enhanced_dataframe(forecast_df, enhancement),
                'summary': self._create_forecast_summary(enhancement),
                'export_ready': True
            }
            
            return enhanced_output
            
        except Exception as e:
            logger.error(f"Failed to integrate with existing forecast: {e}")
            return {
                'error': str(e),
                'original_forecast': {},
                'enhancement': None,
                'export_ready': False
            }
    
    def _prepare_forecast_data(self, forecast_data: Dict) -> Dict:
        """Prepare forecast data for analysis."""
        prepared = forecast_data.copy()
        
        # Extract key metrics if DataFrame is present
        if 'forecast_df' in prepared and isinstance(prepared['forecast_df'], pd.DataFrame):
            df = prepared['forecast_df']
            
            # Calculate summary metrics
            prepared['total_predicted_quantity'] = 0
            prepared['average_prediction'] = 0
            prepared['prediction_variance'] = 0
            
            # Find quantity columns
            quantity_cols = [col for col in df.columns 
                           if any(term in col.lower() for term in ['predicted', 'quantity', 'forecast'])]
            
            if quantity_cols:
                quantity_col = quantity_cols[0]
                if quantity_col in df.columns:
                    prepared['total_predicted_quantity'] = df[quantity_col].sum()
                    prepared['average_prediction'] = df[quantity_col].mean()
                    prepared['prediction_variance'] = df[quantity_col].var()
        
        return prepared
    
    def _prepare_historical_data(self, historical_data: Dict) -> Dict:
        """Prepare historical data for analysis."""
        prepared = historical_data.copy()
        
        # Add historical analysis if data is available
        if 'sales_data' in prepared and isinstance(prepared['sales_data'], pd.DataFrame):
            df = prepared['sales_data']
            
            # Calculate historical trends
            if 'quantity_sold' in df.columns:
                prepared['historical_average'] = df['quantity_sold'].mean()
                prepared['historical_variance'] = df['quantity_sold'].var()
                prepared['historical_trend'] = self._calculate_trend(df['quantity_sold'])
        
        return prepared
    
    def _calculate_confidence_intervals(self, forecast_data: Dict, historical_data: Dict) -> Dict:
        """Calculate confidence intervals for forecast predictions."""
        try:
            # Default confidence intervals
            confidence_intervals = {
                'lower_bound': 0.8,
                'upper_bound': 1.2,
                'confidence_level': 0.80
            }
            
            # Adjust based on historical variance
            if 'historical_variance' in historical_data and 'prediction_variance' in forecast_data:
                hist_var = historical_data.get('historical_variance', 0)
                pred_var = forecast_data.get('prediction_variance', 0)
                
                # Higher variance = wider confidence intervals
                variance_factor = min(2.0, max(0.5, (hist_var + pred_var) / 100))
                
                confidence_intervals['lower_bound'] = max(0.3, 1.0 - (0.2 * variance_factor))
                confidence_intervals['upper_bound'] = min(3.0, 1.0 + (0.2 * variance_factor))
                
                # Adjust confidence level based on data quality
                if hist_var > 0 and pred_var > 0:
                    confidence_intervals['confidence_level'] = min(0.95, 0.60 + (0.3 / variance_factor))
            
            return confidence_intervals
            
        except Exception as e:
            logger.warning(f"Failed to calculate confidence intervals: {e}")
            return {'lower_bound': 0.7, 'upper_bound': 1.3, 'confidence_level': 0.70}
    
    def _identify_risk_factors(self, forecast_data: Dict, historical_data: Dict, 
                              business_context: Dict = None) -> List[str]:
        """Identify potential risk factors affecting forecast accuracy."""
        risk_factors = []
        
        try:
            # Check for high variance
            if forecast_data.get('prediction_variance', 0) > 100:
                risk_factors.append('تقلبات عالية في التنبؤات')
            
            # Check for seasonal patterns
            if business_context and business_context.get('season') in ['peak', 'low']:
                risk_factors.append('تأثيرات موسمية')
            
            # Check for data quality issues
            if 'forecast_df' in forecast_data:
                df = forecast_data['forecast_df']
                try:
                    if hasattr(df, 'isnull'):
                        missing_ratio = df.isnull().sum().sum() / (len(df) * len(df.columns))
                    elif isinstance(df, list):
                        n = len(df)
                        missing = sum(
                            1 for row in df
                            if not isinstance(row, dict) or any(
                                v is None or (isinstance(v, float) and pd.isna(v))
                                for v in row.values()
                            )
                        )
                        missing_ratio = (missing / (n * max(len(df[0]), 1))) if n and isinstance(df[0], dict) else (1.0 if missing else 0.0)
                    else:
                        missing_ratio = 0.0
                    if missing_ratio > 0.1:
                        risk_factors.append('جودة البيانات منخفضة')
                except Exception as e:
                    logger.warning(f"Risk factor data-quality check skipped: {e}")
            
            # Check for trend changes
            if 'historical_trend' in historical_data:
                trend = historical_data['historical_trend']
                if abs(trend) > 0.1:
                    risk_factors.append('تغيرات في الاتجاه العام')
            
            # Default risk factors if none identified
            if not risk_factors:
                risk_factors = ['مخاطر السوق العامة', 'تقلبات الطلب']
            
        except Exception as e:
            logger.warning(f"Risk factor identification failed: {e}")
            risk_factors = ['تعذر تحليل المخاطر']
        
        return risk_factors[:5]  # Limit to top 5 risk factors
    
    def _analyze_external_factors(self, forecast_data: Dict, 
                                 business_context: Dict = None) -> List[str]:
        """Analyze external factors that might affect forecast."""
        external_factors = []
        
        try:
            # Seasonal factors
            current_month = datetime.now().month
            if current_month in [11, 12, 1]:  # Winter season
                external_factors.append('موسم الشتاء والأعياد')
            elif current_month in [6, 7, 8]:  # Summer season
                external_factors.append('موسم الصيف والإجازات')
            
            # Business context factors
            if business_context:
                if business_context.get('promotional_period'):
                    external_factors.append('فترة عروض ترويجية')
                
                if business_context.get('new_product_launch'):
                    external_factors.append('إطلاق منتجات جديدة')
                
                if business_context.get('market_expansion'):
                    external_factors.append('توسع في السوق')
            
            # Economic factors (general)
            external_factors.extend([
                'الظروف الاقتصادية العامة',
                'تقلبات أسعار الصرف',
                'المنافسة في السوق'
            ])
            
        except Exception as e:
            logger.warning(f"External factor analysis failed: {e}")
            external_factors = ['عوامل السوق العامة']
        
        return external_factors[:5]  # Limit to top 5 factors
    
    def _generate_forecast_adjustments(self, forecast_data: Dict, confidence_intervals: Dict,
                                     risk_factors: List[str], ai_insights: Dict) -> List[str]:
        """Generate forecast adjustments based on analysis."""
        adjustments = []
        
        try:
            # Confidence-based adjustments
            lower_bound = confidence_intervals.get('lower_bound', 0.8)
            upper_bound = confidence_intervals.get('upper_bound', 1.2)
            
            if lower_bound < 0.7:
                adjustments.append('تقليل التنبؤات بنسبة 10-20% للمنتجات عالية المخاطر')
            
            if upper_bound > 1.5:
                adjustments.append('زيادة هامش الأمان للمنتجات ذات الطلب المتقلب')
            
            # Risk-based adjustments
            if 'تقلبات عالية في التنبؤات' in risk_factors:
                adjustments.append('تطبيق نموذج تنبؤ محافظ للمنتجات عالية التقلب')
            
            if 'تأثيرات موسمية' in risk_factors:
                adjustments.append('تعديل التنبؤات وفقاً للأنماط الموسمية')
            
            # AI-based adjustments
            if ai_insights and 'adjustments' in ai_insights:
                ai_adjustments = ai_insights['adjustments']
                if isinstance(ai_adjustments, list):
                    adjustments.extend(ai_adjustments[:2])  # Add top 2 AI adjustments
            
            # Default adjustments
            if not adjustments:
                adjustments = [
                    'مراجعة دورية للتنبؤات كل أسبوعين',
                    'تطبيق هامش أمان 15% للمنتجات الجديدة'
                ]
            
        except Exception as e:
            logger.warning(f"Adjustment generation failed: {e}")
            adjustments = ['مراجعة التنبؤات بناءً على الأداء الفعلي']
        
        return adjustments[:5]  # Limit to top 5 adjustments
    
    def _generate_forecast_recommendations(self, forecast_data: Dict, risk_factors: List[str],
                                         external_factors: List[str], ai_insights: Dict) -> List[str]:
        """Generate strategic recommendations for forecast management."""
        recommendations = []
        
        try:
            # Risk-based recommendations
            if 'تقلبات عالية في التنبؤات' in risk_factors:
                recommendations.append('تطوير نظام تنبؤ متعدد النماذج لتحسين الدقة')
            
            if 'جودة البيانات منخفضة' in risk_factors:
                recommendations.append('تحسين عمليات جمع وتنظيف البيانات')
            
            # External factor recommendations
            if 'موسم الشتاء والأعياد' in external_factors:
                recommendations.append('زيادة المخزون للمنتجات الموسمية قبل الذروة')
            
            if 'فترة عروض ترويجية' in external_factors:
                recommendations.append('تعديل التنبؤات لتشمل تأثير العروض الترويجية')
            
            # AI-based recommendations
            if ai_insights and 'recommendations' in ai_insights:
                ai_recommendations = ai_insights['recommendations']
                if isinstance(ai_recommendations, list):
                    recommendations.extend(ai_recommendations[:2])
            
            # General recommendations
            recommendations.extend([
                'مراقبة مؤشرات الأداء الرئيسية للتنبؤات',
                'تطوير خطط طوارئ للسيناريوهات المختلفة',
                'تحسين التعاون بين فرق المبيعات والتخطيط'
            ])
            
        except Exception as e:
            logger.warning(f"Recommendation generation failed: {e}")
            recommendations = ['مراجعة استراتيجية التنبؤ بشكل دوري']
        
        return recommendations[:7]  # Limit to top 7 recommendations
    
    def _create_enhanced_forecast(self, original_forecast: Dict, adjustments: List[str],
                                confidence_intervals: Dict) -> Dict:
        """Create enhanced forecast with adjustments applied."""
        enhanced = original_forecast.copy()
        
        try:
            # Apply confidence interval adjustments
            lower_bound = confidence_intervals.get('lower_bound', 0.8)
            upper_bound = confidence_intervals.get('upper_bound', 1.2)
            
            enhanced['confidence_lower'] = lower_bound
            enhanced['confidence_upper'] = upper_bound
            enhanced['adjustments_applied'] = adjustments
            enhanced['enhancement_timestamp'] = datetime.now().isoformat()
            
            # If DataFrame is present, add confidence columns
            if 'forecast_df' in enhanced and isinstance(enhanced['forecast_df'], pd.DataFrame):
                df = enhanced['forecast_df'].copy()
                
                # Find predicted quantity column
                quantity_cols = [col for col in df.columns 
                               if any(term in col.lower() for term in ['predicted', 'quantity', 'forecast'])]
                
                if quantity_cols:
                    quantity_col = quantity_cols[0]
                    df[f'{quantity_col}_lower'] = df[quantity_col] * lower_bound
                    df[f'{quantity_col}_upper'] = df[quantity_col] * upper_bound
                    df['confidence_level'] = confidence_intervals.get('confidence_level', 0.8)
                
                enhanced['forecast_df'] = df
            
        except Exception as e:
            logger.warning(f"Enhanced forecast creation failed: {e}")
        
        return enhanced
    
    def _calculate_overall_confidence_score(self, confidence_intervals: Dict, 
                                          risk_factors: List[str], ai_insights: Dict) -> float:
        """Calculate overall confidence score for the forecast."""
        try:
            base_score = 75.0
            
            # Adjust based on confidence interval width
            lower_bound = confidence_intervals.get('lower_bound', 0.8)
            upper_bound = confidence_intervals.get('upper_bound', 1.2)
            interval_width = upper_bound - lower_bound
            
            # Narrower intervals = higher confidence
            if interval_width < 0.3:
                base_score += 15
            elif interval_width > 0.8:
                base_score -= 15
            
            # Adjust based on risk factors
            risk_penalty = min(20, len(risk_factors) * 4)
            base_score -= risk_penalty
            
            # Adjust based on AI insights confidence
            if ai_insights and 'confidence_score' in ai_insights:
                ai_confidence = ai_insights['confidence_score']
                if isinstance(ai_confidence, (int, float)):
                    base_score = (base_score + ai_confidence) / 2
            
            return max(0, min(100, base_score))
            
        except Exception as e:
            logger.warning(f"Confidence score calculation failed: {e}")
            return 70.0
    
    def _calculate_trend(self, series: pd.Series) -> float:
        """Calculate trend direction from time series data."""
        try:
            if len(series) < 2:
                return 0.0
            
            # Simple linear trend calculation
            x = np.arange(len(series))
            y = series.values
            
            # Remove NaN values
            mask = ~np.isnan(y)
            if mask.sum() < 2:
                return 0.0
            
            x_clean = x[mask]
            y_clean = y[mask]
            
            # Calculate slope
            slope = np.polyfit(x_clean, y_clean, 1)[0]
            
            # Normalize slope relative to mean
            mean_value = np.mean(y_clean)
            if mean_value != 0:
                normalized_slope = slope / mean_value
            else:
                normalized_slope = 0.0
            
            return normalized_slope
            
        except Exception as e:
            logger.warning(f"Trend calculation failed: {e}")
            return 0.0
    
    def _extract_forecast_period(self, forecast_df: pd.DataFrame) -> Dict:
        """Extract forecast period information from DataFrame."""
        try:
            period_info = {
                'start_date': None,
                'end_date': None,
                'duration_days': 0
            }
            
            # Find date columns
            date_cols = [col for col in forecast_df.columns 
                        if any(term in col.lower() for term in ['date', 'تاريخ'])]
            
            if date_cols:
                date_col = date_cols[0]
                dates = pd.to_datetime(forecast_df[date_col], errors='coerce')
                valid_dates = dates.dropna()
                
                if not valid_dates.empty:
                    period_info['start_date'] = valid_dates.min().isoformat()
                    period_info['end_date'] = valid_dates.max().isoformat()
                    period_info['duration_days'] = (valid_dates.max() - valid_dates.min()).days
            
            return period_info
            
        except Exception as e:
            logger.warning(f"Forecast period extraction failed: {e}")
            return {'start_date': None, 'end_date': None, 'duration_days': 0}
    
    def _create_enhanced_dataframe(self, original_df: pd.DataFrame, 
                                  enhancement: ForecastEnhancement) -> pd.DataFrame:
        """Create enhanced DataFrame with AI insights."""
        try:
            enhanced_df = original_df.copy()
            
            # Add confidence intervals
            confidence_intervals = enhancement.confidence_intervals
            enhanced_df['confidence_lower'] = confidence_intervals.get('lower_bound', 0.8)
            enhanced_df['confidence_upper'] = confidence_intervals.get('upper_bound', 1.2)
            enhanced_df['confidence_level'] = confidence_intervals.get('confidence_level', 0.8)
            
            # Add risk assessment
            enhanced_df['risk_level'] = 'متوسط'  # Default risk level
            if len(enhancement.risk_factors) > 3:
                enhanced_df['risk_level'] = 'عالي'
            elif len(enhancement.risk_factors) < 2:
                enhanced_df['risk_level'] = 'منخفض'
            
            # Add enhancement metadata
            enhanced_df['enhancement_score'] = enhancement.confidence_score
            enhanced_df['enhancement_timestamp'] = enhancement.timestamp.isoformat()
            
            return enhanced_df
            
        except Exception as e:
            logger.warning(f"Enhanced DataFrame creation failed: {e}")
            return original_df
    
    def _create_forecast_summary(self, enhancement: ForecastEnhancement) -> Dict:
        """Create summary of forecast enhancement."""
        return {
            'confidence_score': enhancement.confidence_score,
            'confidence_intervals': enhancement.confidence_intervals,
            'risk_factors_count': len(enhancement.risk_factors),
            'external_factors_count': len(enhancement.external_factors),
            'adjustments_count': len(enhancement.adjustments),
            'recommendations_count': len(enhancement.recommendations),
            'processing_time': enhancement.processing_time,
            'enhancement_timestamp': enhancement.timestamp.isoformat(),
            'summary_text': f"تم تحسين التنبؤ بدرجة ثقة {enhancement.confidence_score:.1f}% مع تحديد {len(enhancement.risk_factors)} عوامل مخاطرة و {len(enhancement.recommendations)} توصية"
        }


# Global instance for easy access
enhanced_forecasting_system = EnhancedForecastingSystem()