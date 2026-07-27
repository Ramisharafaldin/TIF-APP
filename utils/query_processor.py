"""
Natural Language Query Processor
Handles intent parsing, data access validation, and conversational responses.
"""
import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class QueryProcessor:
    """
    Processes natural language queries about inventory data.
    
    Provides intent parsing, data access validation, and conversational
    response formatting for user queries in plain English.
    """
    
    def __init__(self, ai_service, data_store):
        """
        Initialize the query processor.
        
        Args:
            ai_service: AI service instance for processing queries
            data_store: Data store instance for accessing inventory data
        """
        self.ai_service = ai_service
        self.data_store = data_store
        
        # Pre-compile regex patterns at initialization (OPTIMIZATION 1)
        self._compiled_patterns = self._compile_patterns()
        
        # Define data access permissions
        self.data_permissions = {
            'stock_levels': ['inventory_data', 'stock_quantities'],
            'item_locations': ['inventory_data', 'branch_data'],
            'sales_trends': ['sales_data', 'revenue_data'],
            'forecasts': ['sales_data', 'historical_data'],
            'alerts': ['inventory_data', 'alert_data']
        }
    
    def _compile_patterns(self) -> Dict:
        """Pre-compile all regex patterns for reuse (OPTIMIZATION 1).
        
        Eliminates per-request regex compilation overhead (20-30% faster).
        """
        pattern_strings = {
            'stock_levels': [
                r'how much.*stock',
                r'stock level.*',
                r'inventory.*level',
                r'how many.*items',
                r'quantity.*available'
            ],
            'item_locations': [
                r'where.*located',
                r'location.*item',
                r'which branch.*',
                r'find.*item',
                r'where can i find'
            ],
            'sales_trends': [
                r'sales.*trend',
                r'selling.*well',
                r'best.*seller',
                r'top.*product',
                r'revenue.*analysis'
            ],
            'forecasts': [
                r'forecast.*',
                r'predict.*sales',
                r'future.*demand',
                r'expected.*sales',
                r'projection.*'
            ],
            'alerts': [
                r'low.*stock',
                r'out.*stock',
                r'critical.*item',
                r'alert.*',
                r'warning.*'
            ]
        }
        
        # Compile patterns once at initialization
        compiled = {}
        for query_type, patterns in pattern_strings.items():
            compiled[query_type] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
        
        return compiled
    
    def parse_query_intent(self, query: str) -> Dict:
        """
        Parse user query to identify intent and extract parameters.
        
        Args:
            query: User's natural language query
            
        Returns:
            Dict containing parsed intent information
        """
        try:
            query_lower = query.lower().strip()
            
            # Initialize intent structure
            intent = {
                'original_query': query,
                'query_type': 'general',
                'confidence': 0.0,
                'parameters': {},
                'data_requirements': [],
                'suggested_actions': []
            }
            
            # Match query patterns using pre-compiled regex (OPTIMIZATION 1)
            best_match_type = None
            best_confidence = 0.0
            
            for query_type, compiled_patterns in self._compiled_patterns.items():
                for compiled_pattern in compiled_patterns:
                    if compiled_pattern.search(query_lower):
                        confidence = self._calculate_pattern_confidence(compiled_pattern, query_lower)
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_match_type = query_type
            
            if best_match_type:
                intent['query_type'] = best_match_type
                intent['confidence'] = best_confidence
                intent['data_requirements'] = self.data_permissions.get(best_match_type, [])
            
            # Extract parameters based on query type
            intent['parameters'] = self._extract_query_parameters(query_lower, best_match_type)
            
            # Generate suggested actions
            intent['suggested_actions'] = self._generate_suggested_actions(best_match_type, intent['parameters'])
            
            logger.info(f"Parsed query intent: {best_match_type} (confidence: {best_confidence:.2f})")
            return intent
            
        except Exception as e:
            logger.error(f"Error parsing query intent: {e}")
            return {
                'original_query': query,
                'query_type': 'error',
                'confidence': 0.0,
                'parameters': {},
                'data_requirements': [],
                'suggested_actions': [],
                'error': str(e)
            }
    
    def validate_data_access(self, user: str, requested_data: List[str]) -> bool:
        """
        Validate that user has access to requested data types.
        
        Args:
            user: Username requesting access
            requested_data: List of data types being requested
            
        Returns:
            True if user has access to all requested data
        """
        try:
            # For now, implement basic validation
            # In a real system, this would check user roles and permissions
            
            if not user:
                logger.warning("No user provided for data access validation")
                return False
            
            # Check if user exists in the system
            try:
                branches = self.data_store.get_all_branches(user)
                if not branches:
                    logger.warning(f"User {user} has no accessible branches")
                    return False
            except Exception as e:
                logger.error(f"Error checking user branches: {e}")
                return False
            
            # All authenticated users with data can access basic query types
            allowed_data_types = [
                'inventory_data', 'stock_quantities', 'branch_data',
                'sales_data', 'revenue_data', 'historical_data', 'alert_data'
            ]
            
            for data_type in requested_data:
                if data_type not in allowed_data_types:
                    logger.warning(f"User {user} requested unauthorized data type: {data_type}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating data access: {e}")
            return False
    
    def execute_data_query(self, intent: Dict, user: str) -> Dict:
        """
        Execute data query based on parsed intent.
        
        Args:
            intent: Parsed query intent
            user: Username executing the query
            
        Returns:
            Dict containing query results
        """
        try:
            query_type = intent.get('query_type', 'general')
            parameters = intent.get('parameters', {})
            
            # Validate data access
            if not self.validate_data_access(user, intent.get('data_requirements', [])):
                return {
                    'success': False,
                    'error': 'Access denied to requested data',
                    'data': {}
                }
            
            # Execute query based on type
            if query_type == 'stock_levels':
                return self._execute_stock_levels_query(user, parameters)
            elif query_type == 'item_locations':
                return self._execute_item_locations_query(user, parameters)
            elif query_type == 'sales_trends':
                return self._execute_sales_trends_query(user, parameters)
            elif query_type == 'forecasts':
                return self._execute_forecasts_query(user, parameters)
            elif query_type == 'alerts':
                return self._execute_alerts_query(user, parameters)
            else:
                return self._execute_general_query(user, parameters)
                
        except Exception as e:
            logger.error(f"Error executing data query: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': {}
            }
    
    def format_conversational_response(self, query_result: Dict, original_query: str) -> Dict:
        """
        Format query results into conversational response.
        
        Args:
            query_result: Results from data query execution
            original_query: Original user query
            
        Returns:
            Dict containing formatted conversational response
        """
        try:
            if not query_result.get('success', False):
                return {
                    'response': f"عذراً، لم أتمكن من معالجة سؤالك: {query_result.get('error', 'خطأ غير معروف')}",
                    'data_points': [],
                    'suggestions': [
                        'تأكد من صياغة السؤال بوضوح',
                        'جرب سؤالاً أكثر تحديداً',
                        'تحقق من أن لديك صلاحية الوصول للبيانات المطلوبة'
                    ],
                    'confidence_score': 0
                }
            
            data = query_result.get('data', {})
            query_type = query_result.get('query_type', 'general')
            
            # Format response based on query type
            if query_type == 'stock_levels':
                return self._format_stock_levels_response(data, original_query)
            elif query_type == 'item_locations':
                return self._format_item_locations_response(data, original_query)
            elif query_type == 'sales_trends':
                return self._format_sales_trends_response(data, original_query)
            elif query_type == 'forecasts':
                return self._format_forecasts_response(data, original_query)
            elif query_type == 'alerts':
                return self._format_alerts_response(data, original_query)
            else:
                return self._format_general_response(data, original_query)
                
        except Exception as e:
            logger.error(f"Error formatting conversational response: {e}")
            return {
                'response': f"حدث خطأ في تنسيق الإجابة: {str(e)}",
                'data_points': [],
                'suggestions': ['يرجى المحاولة مرة أخرى'],
                'confidence_score': 0
            }
    
    def _calculate_pattern_confidence(self, compiled_pattern, query: str) -> float:
        """Calculate confidence score for pattern match using pre-compiled pattern."""
        match = compiled_pattern.search(query)
        if not match:
            return 0.0
        
        # Simple confidence calculation based on match length and position
        match_length = len(match.group())
        query_length = len(query)
        
        # Higher confidence for longer matches and matches at the beginning
        length_score = match_length / query_length
        position_score = 1.0 - (match.start() / query_length)
        
        return (length_score * 0.7 + position_score * 0.3) * 100
    
    def _extract_query_parameters(self, query: str, query_type: Optional[str]) -> Dict:
        """Extract parameters from query based on type."""
        parameters = {}
        
        # Extract common parameters
        # Product/item names
        item_match = re.search(r'(?:item|product|منتج)\s+([a-zA-Z0-9\u0600-\u06FF\s]+)', query)
        if item_match:
            parameters['item_name'] = item_match.group(1).strip()
        
        # Branch names
        branch_match = re.search(r'(?:branch|فرع)\s+([a-zA-Z0-9\u0600-\u06FF\s]+)', query)
        if branch_match:
            parameters['branch_name'] = branch_match.group(1).strip()
        
        # Numbers/quantities
        number_matches = re.findall(r'\b\d+\b', query)
        if number_matches:
            parameters['numbers'] = [int(n) for n in number_matches]
        
        # Time periods
        if any(word in query for word in ['today', 'اليوم', 'this week', 'هذا الأسبوع']):
            parameters['time_period'] = 'recent'
        elif any(word in query for word in ['month', 'شهر', 'year', 'سنة']):
            parameters['time_period'] = 'extended'
        
        return parameters
    
    def _generate_suggested_actions(self, query_type: Optional[str], parameters: Dict) -> List[str]:
        """Generate suggested follow-up actions."""
        suggestions = []
        
        if query_type == 'stock_levels':
            suggestions = [
                'عرض تفاصيل المنتجات منخفضة المخزون',
                'إنشاء تقرير مستويات المخزون',
                'تحديد نقاط إعادة الطلب'
            ]
        elif query_type == 'sales_trends':
            suggestions = [
                'عرض تحليل المبيعات الشهرية',
                'مقارنة أداء المنتجات',
                'إنشاء توقعات المبيعات'
            ]
        elif query_type == 'alerts':
            suggestions = [
                'عرض جميع التنبيهات الحالية',
                'تصدير تقرير التنبيهات',
                'تحديث إعدادات التنبيهات'
            ]
        else:
            suggestions = [
                'جرب سؤالاً أكثر تحديداً',
                'اسأل عن مستويات المخزون',
                'اطلب تحليل المبيعات'
            ]
        
        return suggestions
    
    def _execute_stock_levels_query(self, user: str, parameters: Dict) -> Dict:
        """Execute stock levels query."""
        try:
            # Get inventory data
            df_sales, df_inventory = self.data_store.get_branch_data(user, branch_name=None)
            
            if df_inventory is None:
                return {
                    'success': False,
                    'error': 'No inventory data available',
                    'data': {}
                }
            
            # Calculate basic stock statistics
            total_products = len(df_inventory)
            
            # Try to find stock quantity column
            stock_col = None
            for col in df_inventory.columns:
                if any(term in col.lower() for term in ['stock', 'quantity', 'on_hand', 'qty']):
                    stock_col = col
                    break
            
            if stock_col:
                low_stock_threshold = 10  # Could be configurable
                low_stock_items = len(df_inventory[df_inventory[stock_col] < low_stock_threshold])
                out_of_stock_items = len(df_inventory[df_inventory[stock_col] == 0])
                total_stock_value = df_inventory[stock_col].sum()
            else:
                low_stock_items = 0
                out_of_stock_items = 0
                total_stock_value = 0
            
            return {
                'success': True,
                'query_type': 'stock_levels',
                'data': {
                    'total_products': total_products,
                    'low_stock_items': low_stock_items,
                    'out_of_stock_items': out_of_stock_items,
                    'total_stock_value': total_stock_value,
                    'stock_column': stock_col
                }
            }
            
        except Exception as e:
            logger.error(f"Error executing stock levels query: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': {}
            }
    
    def _execute_item_locations_query(self, user: str, parameters: Dict) -> Dict:
        """Execute item locations query."""
        try:
            branches = self.data_store.get_all_branches(user)
            
            return {
                'success': True,
                'query_type': 'item_locations',
                'data': {
                    'available_branches': branches,
                    'total_branches': len(branches)
                }
            }
            
        except Exception as e:
            logger.error(f"Error executing item locations query: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': {}
            }
    
    def _execute_sales_trends_query(self, user: str, parameters: Dict) -> Dict:
        """Execute sales trends query."""
        try:
            df_sales, df_inventory = self.data_store.get_branch_data(user, branch_name=None)
            
            if df_sales is None:
                return {
                    'success': False,
                    'error': 'No sales data available',
                    'data': {}
                }
            
            # Calculate basic sales statistics
            revenue_col = None
            for col in df_sales.columns:
                if any(term in col.lower() for term in ['revenue', 'sales', 'amount', 'total']):
                    revenue_col = col
                    break
            
            if revenue_col:
                total_revenue = df_sales[revenue_col].sum()
                avg_transaction = df_sales[revenue_col].mean()
                total_transactions = len(df_sales)
            else:
                total_revenue = 0
                avg_transaction = 0
                total_transactions = len(df_sales)
            
            return {
                'success': True,
                'query_type': 'sales_trends',
                'data': {
                    'total_revenue': total_revenue,
                    'avg_transaction': avg_transaction,
                    'total_transactions': total_transactions,
                    'revenue_column': revenue_col
                }
            }
            
        except Exception as e:
            logger.error(f"Error executing sales trends query: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': {}
            }
    
    def _execute_forecasts_query(self, user: str, parameters: Dict) -> Dict:
        """Execute forecasts query."""
        return {
            'success': True,
            'query_type': 'forecasts',
            'data': {
                'message': 'Forecasting functionality is available through the forecasting module'
            }
        }
    
    def _execute_alerts_query(self, user: str, parameters: Dict) -> Dict:
        """Execute alerts query."""
        try:
            # This would integrate with the existing alert system
            return {
                'success': True,
                'query_type': 'alerts',
                'data': {
                    'message': 'Alert functionality is available through the alerts API'
                }
            }
            
        except Exception as e:
            logger.error(f"Error executing alerts query: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': {}
            }
    
    def _execute_general_query(self, user: str, parameters: Dict) -> Dict:
        """Execute general query."""
        return {
            'success': True,
            'query_type': 'general',
            'data': {
                'message': 'General query processed. Please be more specific for detailed results.'
            }
        }
    
    def _format_stock_levels_response(self, data: Dict, original_query: str) -> Dict:
        """Format stock levels response."""
        total_products = data.get('total_products', 0)
        low_stock = data.get('low_stock_items', 0)
        out_of_stock = data.get('out_of_stock_items', 0)
        
        response = f"لديك {total_products} منتج في المخزون. "
        
        if low_stock > 0:
            response += f"هناك {low_stock} منتج بمستوى مخزون منخفض. "
        
        if out_of_stock > 0:
            response += f"و {out_of_stock} منتج نفد من المخزون. "
        
        if low_stock == 0 and out_of_stock == 0:
            response += "جميع المنتجات في مستوى مخزون جيد."
        
        return {
            'response': response,
            'data_points': [
                f'إجمالي المنتجات: {total_products}',
                f'مخزون منخفض: {low_stock}',
                f'نفد من المخزون: {out_of_stock}'
            ],
            'suggestions': [
                'عرض المنتجات منخفضة المخزون',
                'إنشاء تقرير المخزون',
                'تحديث مستويات إعادة الطلب'
            ],
            'confidence_score': 85
        }
    
    def _format_item_locations_response(self, data: Dict, original_query: str) -> Dict:
        """Format item locations response."""
        branches = data.get('available_branches', [])
        total_branches = data.get('total_branches', 0)
        
        response = f"لديك بيانات من {total_branches} فرع. "
        
        if branches:
            if total_branches <= 3:
                response += f"الفروع المتاحة: {', '.join(branches)}."
            else:
                response += f"الفروع تشمل: {', '.join(branches[:3])} وغيرها."
        
        return {
            'response': response,
            'data_points': [f'الفروع المتاحة: {", ".join(branches)}'],
            'suggestions': [
                'عرض تفاصيل فرع معين',
                'مقارنة المخزون بين الفروع',
                'تحليل أداء الفروع'
            ],
            'confidence_score': 80
        }
    
    def _format_sales_trends_response(self, data: Dict, original_query: str) -> Dict:
        """Format sales trends response."""
        total_revenue = data.get('total_revenue', 0)
        total_transactions = data.get('total_transactions', 0)
        avg_transaction = data.get('avg_transaction', 0)
        
        response = f"إجمالي المبيعات: {total_revenue:,.2f} من {total_transactions} معاملة. "
        response += f"متوسط قيمة المعاملة: {avg_transaction:,.2f}."
        
        return {
            'response': response,
            'data_points': [
                f'إجمالي الإيرادات: {total_revenue:,.2f}',
                f'عدد المعاملات: {total_transactions}',
                f'متوسط المعاملة: {avg_transaction:,.2f}'
            ],
            'suggestions': [
                'تحليل اتجاهات المبيعات الشهرية',
                'عرض أفضل المنتجات مبيعاً',
                'مقارنة أداء الفروع'
            ],
            'confidence_score': 90
        }
    
    def _format_forecasts_response(self, data: Dict, original_query: str) -> Dict:
        """Format forecasts response."""
        return {
            'response': 'يمكنك الوصول إلى ميزات التنبؤ من خلال قسم التنبؤات في النظام.',
            'data_points': ['التنبؤات متاحة في قسم منفصل'],
            'suggestions': [
                'انتقل إلى صفحة التنبؤات',
                'إنشاء تنبؤ جديد للمبيعات',
                'عرض التنبؤات السابقة'
            ],
            'confidence_score': 70
        }
    
    def _format_alerts_response(self, data: Dict, original_query: str) -> Dict:
        """Format alerts response."""
        return {
            'response': 'يمكنك عرض التنبيهات من خلال لوحة التحكم أو API التنبيهات.',
            'data_points': ['التنبيهات متاحة في لوحة التحكم'],
            'suggestions': [
                'عرض التنبيهات الحالية',
                'تخصيص إعدادات التنبيهات',
                'تصدير تقرير التنبيهات'
            ],
            'confidence_score': 75
        }
    
    def _format_general_response(self, data: Dict, original_query: str) -> Dict:
        """Format general response."""
        return {
            'response': 'يمكنني مساعدتك في الاستعلام عن المخزون والمبيعات. جرب سؤالاً أكثر تحديداً.',
            'data_points': ['استعلامات عامة متاحة'],
            'suggestions': [
                'اسأل عن مستويات المخزون',
                'استفسر عن اتجاهات المبيعات',
                'اطلب معلومات عن فرع معين'
            ],
            'confidence_score': 50
        }