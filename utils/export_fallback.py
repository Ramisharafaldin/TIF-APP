"""
Export Fallback and Recovery Mechanisms

This module provides alternative error handling paths, fallback file generation methods,
and recovery mechanisms for failed export operations.

**Validates: Requirements 5.4**
"""

import logging
import pandas as pd
import json
import csv
from io import BytesIO, StringIO
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)

class ExportFallbackHandler:
    """
    Handles fallback scenarios for export operations when primary methods fail.
    
    **Validates: Requirements 5.4**
    """
    
    def __init__(self, username: str, operation_type: str):
        self.username = username
        self.operation_type = operation_type
        self.fallback_attempts = []
        self.recovery_log = []
    
    def attempt_csv_fallback(self, data: pd.DataFrame, filename_base: str) -> Tuple[bool, Optional[BytesIO], str]:
        """
        Attempt to create CSV file as fallback when Excel generation fails.
        
        Args:
            data: DataFrame to export
            filename_base: Base filename without extension
            
        Returns:
            (success, file_buffer, message)
        """
        try:
            logger.info(f"Attempting CSV fallback for {self.username} - {self.operation_type}")
            
            output = BytesIO()
            
            # Convert DataFrame to CSV with Arabic support
            csv_string = data.to_csv(index=False, encoding='utf-8-sig')
            output.write(csv_string.encode('utf-8-sig'))
            output.seek(0)
            
            message = f"تم إنشاء ملف CSV بدلاً من Excel بسبب مشكلة تقنية"
            self.fallback_attempts.append({
                'method': 'csv_fallback',
                'success': True,
                'timestamp': datetime.now(),
                'rows': len(data),
                'message': message
            })
            
            logger.info(f"CSV fallback successful for {self.username}: {len(data)} rows")
            return True, output, message
            
        except Exception as e:
            error_msg = f"CSV fallback failed: {str(e)}"
            logger.error(f"CSV fallback failed for {self.username}: {e}", exc_info=True)
            
            self.fallback_attempts.append({
                'method': 'csv_fallback',
                'success': False,
                'timestamp': datetime.now(),
                'error': str(e),
                'message': error_msg
            })
            
            return False, None, error_msg
    
    def attempt_json_fallback(self, data: pd.DataFrame, filename_base: str) -> Tuple[bool, Optional[BytesIO], str]:
        """
        Attempt to create JSON file as fallback when other formats fail.
        
        Args:
            data: DataFrame to export
            filename_base: Base filename without extension
            
        Returns:
            (success, file_buffer, message)
        """
        try:
            logger.info(f"Attempting JSON fallback for {self.username} - {self.operation_type}")
            
            output = BytesIO()
            
            # Convert DataFrame to JSON with Arabic support
            json_data = {
                'metadata': {
                    'export_date': datetime.now().isoformat(),
                    'username': self.username,
                    'operation_type': self.operation_type,
                    'total_records': len(data),
                    'columns': list(data.columns)
                },
                'data': data.to_dict('records')
            }
            
            json_string = json.dumps(json_data, ensure_ascii=False, indent=2)
            output.write(json_string.encode('utf-8'))
            output.seek(0)
            
            message = f"تم إنشاء ملف JSON بدلاً من التنسيق المطلوب بسبب مشكلة تقنية"
            self.fallback_attempts.append({
                'method': 'json_fallback',
                'success': True,
                'timestamp': datetime.now(),
                'rows': len(data),
                'message': message
            })
            
            logger.info(f"JSON fallback successful for {self.username}: {len(data)} rows")
            return True, output, message
            
        except Exception as e:
            error_msg = f"JSON fallback failed: {str(e)}"
            logger.error(f"JSON fallback failed for {self.username}: {e}", exc_info=True)
            
            self.fallback_attempts.append({
                'method': 'json_fallback',
                'success': False,
                'timestamp': datetime.now(),
                'error': str(e),
                'message': error_msg
            })
            
            return False, None, error_msg
    
    def attempt_partial_export(self, data: pd.DataFrame, max_rows: int = 1000) -> Tuple[bool, Optional[pd.DataFrame], str]:
        """
        Attempt to create partial export when full export fails due to size.
        
        Args:
            data: DataFrame to export
            max_rows: Maximum number of rows to include
            
        Returns:
            (success, partial_data, message)
        """
        try:
            logger.info(f"Attempting partial export for {self.username} - {self.operation_type}")
            
            if len(data) <= max_rows:
                message = "البيانات صغيرة بما فيه الكفاية للتصدير الكامل"
                return True, data, message
            
            # Create partial dataset
            partial_data = data.head(max_rows).copy()
            
            # Add summary row
            summary_row = {}
            for col in data.columns:
                if data[col].dtype in ['int64', 'float64']:
                    summary_row[col] = f"المجموع: {data[col].sum():.2f}"
                else:
                    summary_row[col] = f"إجمالي السجلات: {len(data)}"
            
            # Add summary as last row
            partial_data = pd.concat([partial_data, pd.DataFrame([summary_row])], ignore_index=True)
            
            message = f"تم تصدير أول {max_rows} سجل من أصل {len(data)} سجل بسبب حجم البيانات الكبير"
            self.fallback_attempts.append({
                'method': 'partial_export',
                'success': True,
                'timestamp': datetime.now(),
                'original_rows': len(data),
                'exported_rows': max_rows,
                'message': message
            })
            
            logger.info(f"Partial export successful for {self.username}: {max_rows} of {len(data)} rows")
            return True, partial_data, message
            
        except Exception as e:
            error_msg = f"Partial export failed: {str(e)}"
            logger.error(f"Partial export failed for {self.username}: {e}", exc_info=True)
            
            self.fallback_attempts.append({
                'method': 'partial_export',
                'success': False,
                'timestamp': datetime.now(),
                'error': str(e),
                'message': error_msg
            })
            
            return False, None, error_msg
    
    def create_error_report(self, original_error: Exception, context: Dict[str, Any]) -> Tuple[bool, Optional[BytesIO], str]:
        """
        Create an error report file when all export methods fail.
        
        Args:
            original_error: The original error that caused the failure
            context: Additional context information
            
        Returns:
            (success, file_buffer, message)
        """
        try:
            logger.info(f"Creating error report for {self.username} - {self.operation_type}")
            
            output = BytesIO()
            
            # Create error report
            error_report = {
                'تقرير الخطأ': {
                    'المستخدم': self.username,
                    'نوع العملية': self.operation_type,
                    'وقت الخطأ': datetime.now().isoformat(),
                    'رسالة الخطأ': str(original_error),
                    'تفاصيل الخطأ': traceback.format_exc(),
                    'السياق': context,
                    'محاولات الاسترداد': self.fallback_attempts
                },
                'الإجراءات المقترحة': [
                    'تحقق من حجم البيانات وقم بتطبيق فلاتر لتقليلها',
                    'تأكد من وجود مساحة كافية على القرص الصلب',
                    'أعد المحاولة بعد بضع دقائق',
                    'اتصل بالدعم الفني إذا استمرت المشكلة'
                ]
            }
            
            # Convert to JSON
            json_string = json.dumps(error_report, ensure_ascii=False, indent=2)
            output.write(json_string.encode('utf-8'))
            output.seek(0)
            
            message = "تم إنشاء تقرير خطأ مفصل. يرجى مراجعته والاتصال بالدعم الفني"
            
            self.recovery_log.append({
                'action': 'error_report_created',
                'timestamp': datetime.now(),
                'success': True,
                'message': message
            })
            
            logger.info(f"Error report created for {self.username}")
            return True, output, message
            
        except Exception as e:
            error_msg = f"Failed to create error report: {str(e)}"
            logger.error(f"Error report creation failed for {self.username}: {e}", exc_info=True)
            
            self.recovery_log.append({
                'action': 'error_report_creation',
                'timestamp': datetime.now(),
                'success': False,
                'error': str(e),
                'message': error_msg
            })
            
            return False, None, error_msg
    
    def get_recovery_summary(self) -> Dict[str, Any]:
        """Get summary of all recovery attempts."""
        return {
            'username': self.username,
            'operation_type': self.operation_type,
            'fallback_attempts': len(self.fallback_attempts),
            'successful_fallbacks': len([a for a in self.fallback_attempts if a.get('success', False)]),
            'recovery_actions': len(self.recovery_log),
            'attempts': self.fallback_attempts,
            'recovery_log': self.recovery_log
        }

class ExportRecoveryManager:
    """
    Manages recovery mechanisms for failed export operations.
    
    **Validates: Requirements 5.4**
    """
    
    @staticmethod
    def attempt_export_with_fallbacks(data: pd.DataFrame, username: str, operation_type: str, 
                                    preferred_format: str = 'xlsx') -> Tuple[bool, Optional[BytesIO], str, str]:
        """
        Attempt export with multiple fallback strategies.
        
        Args:
            data: DataFrame to export
            username: Username for logging
            operation_type: Type of operation
            preferred_format: Preferred export format
            
        Returns:
            (success, file_buffer, content_type, message)
        """
        fallback_handler = ExportFallbackHandler(username, operation_type)
        
        # Strategy 1: Try preferred format first (handled by caller)
        # This method is called when preferred format already failed
        
        # Strategy 2: Try partial export if data is too large
        if len(data) > 5000:  # Large dataset threshold
            logger.info(f"Large dataset detected ({len(data)} rows), attempting partial export")
            success, partial_data, message = fallback_handler.attempt_partial_export(data, max_rows=2000)
            
            if success and partial_data is not None:
                # Try CSV with partial data
                csv_success, csv_buffer, csv_message = fallback_handler.attempt_csv_fallback(
                    partial_data, f"{operation_type}_partial"
                )
                if csv_success:
                    combined_message = f"{message}. {csv_message}"
                    return True, csv_buffer, 'text/csv', combined_message
        
        # Strategy 3: Try CSV fallback with original data
        logger.info(f"Attempting CSV fallback for {username}")
        csv_success, csv_buffer, csv_message = fallback_handler.attempt_csv_fallback(data, operation_type)
        if csv_success:
            return True, csv_buffer, 'text/csv', csv_message
        
        # Strategy 4: Try JSON fallback
        logger.info(f"Attempting JSON fallback for {username}")
        json_success, json_buffer, json_message = fallback_handler.attempt_json_fallback(data, operation_type)
        if json_success:
            return True, json_buffer, 'application/json', json_message
        
        # Strategy 5: Create error report
        logger.error(f"All export methods failed for {username}, creating error report")
        error_context = {
            'data_shape': data.shape if data is not None else 'None',
            'data_columns': list(data.columns) if data is not None else [],
            'preferred_format': preferred_format,
            'fallback_summary': fallback_handler.get_recovery_summary()
        }
        
        error_success, error_buffer, error_message = fallback_handler.create_error_report(
            Exception("All export methods failed"), error_context
        )
        
        if error_success:
            return True, error_buffer, 'application/json', error_message
        
        # Complete failure
        return False, None, '', "فشل في جميع طرق التصدير والاسترداد"
    
    @staticmethod
    def handle_memory_constraint_recovery(data: pd.DataFrame, username: str, operation_type: str) -> Tuple[bool, Optional[pd.DataFrame], str]:
        """
        Handle recovery when memory constraints are hit.
        
        Args:
            data: Original DataFrame
            username: Username for logging
            operation_type: Type of operation
            
        Returns:
            (success, reduced_data, message)
        """
        try:
            logger.info(f"Handling memory constraint recovery for {username}")
            
            # Strategy 1: Reduce data size by sampling
            if len(data) > 1000:
                sample_size = min(1000, len(data) // 2)
                reduced_data = data.sample(n=sample_size, random_state=42)
                message = f"تم تقليل البيانات من {len(data)} إلى {sample_size} سجل بسبب قيود الذاكرة"
                logger.info(f"Memory recovery: reduced data from {len(data)} to {sample_size} rows")
                return True, reduced_data, message
            
            # Strategy 2: Remove non-essential columns
            essential_cols = []
            for col in data.columns:
                if any(keyword in col.lower() for keyword in ['code', 'name', 'date', 'value', 'amount', 'qty']):
                    essential_cols.append(col)
            
            if len(essential_cols) < len(data.columns) and len(essential_cols) > 0:
                reduced_data = data[essential_cols].copy()
                message = f"تم تقليل الأعمدة من {len(data.columns)} إلى {len(essential_cols)} عمود بسبب قيود الذاكرة"
                logger.info(f"Memory recovery: reduced columns from {len(data.columns)} to {len(essential_cols)}")
                return True, reduced_data, message
            
            # Strategy 3: Use only first 500 rows
            if len(data) > 500:
                reduced_data = data.head(500).copy()
                message = f"تم تصدير أول 500 سجل فقط من أصل {len(data)} بسبب قيود الذاكرة"
                logger.info(f"Memory recovery: using first 500 rows of {len(data)}")
                return True, reduced_data, message
            
            # If data is already small, return as-is
            return True, data, "البيانات صغيرة بما فيه الكفاية"
            
        except Exception as e:
            logger.error(f"Memory constraint recovery failed for {username}: {e}", exc_info=True)
            return False, None, f"فشل في استرداد البيانات من قيود الذاكرة: {str(e)}"
    
    @staticmethod
    def handle_timeout_recovery(username: str, operation_type: str, elapsed_time: float) -> Dict[str, Any]:
        """
        Handle recovery when operation times out.
        
        Args:
            username: Username for logging
            operation_type: Type of operation
            elapsed_time: Time elapsed before timeout
            
        Returns:
            Recovery information dictionary
        """
        logger.warning(f"Handling timeout recovery for {username} after {elapsed_time:.2f}s")
        
        recovery_info = {
            'timeout_occurred': True,
            'elapsed_time': elapsed_time,
            'recovery_suggestions': [],
            'user_message': '',
            'technical_details': {
                'username': username,
                'operation_type': operation_type,
                'timeout_threshold': 300,  # 5 minutes
                'recovery_timestamp': datetime.now().isoformat()
            }
        }
        
        if elapsed_time > 240:  # 4 minutes
            recovery_info['user_message'] = 'انتهت مهلة التصدير. البيانات كبيرة جداً للمعالجة في الوقت المحدد'
            recovery_info['recovery_suggestions'] = [
                'تطبيق فلاتر زمنية لتقليل حجم البيانات',
                'تصدير البيانات على دفعات صغيرة',
                'استخدام تصدير CSV بدلاً من Excel',
                'المحاولة خلال ساعات أقل ازدحاماً'
            ]
        elif elapsed_time > 120:  # 2 minutes
            recovery_info['user_message'] = 'المعالجة تستغرق وقتاً أطول من المتوقع'
            recovery_info['recovery_suggestions'] = [
                'تطبيق فلاتر لتقليل البيانات',
                'المحاولة مرة أخرى بعد قليل',
                'استخدام تصدير مبسط'
            ]
        else:
            recovery_info['user_message'] = 'انتهت مهلة المعالجة'
            recovery_info['recovery_suggestions'] = [
                'المحاولة مرة أخرى',
                'التحقق من اتصال الإنترنت',
                'تحديث الصفحة والمحاولة مجدداً'
            ]
        
        return recovery_info

def create_fallback_export_response(username: str, operation_type: str, error: Exception, 
                                  context: Dict[str, Any]) -> Tuple[str, str]:
    """
    Create a user-friendly response when all export methods fail.
    
    Args:
        username: Username for logging
        operation_type: Type of operation that failed
        error: Original error
        context: Additional context
        
    Returns:
        (user_message, technical_message)
    """
    logger.error(f"Creating fallback response for {username} - {operation_type}: {error}")
    
    # Determine user-friendly message based on error type
    error_str = str(error).lower()
    
    if 'memory' in error_str or 'ram' in error_str:
        user_message = 'البيانات كبيرة جداً للتصدير. يرجى تطبيق فلاتر لتقليل حجم البيانات'
    elif 'timeout' in error_str or 'time' in error_str:
        user_message = 'انتهت مهلة التصدير. يرجى المحاولة مرة أخرى أو تقليل حجم البيانات'
    elif 'permission' in error_str or 'access' in error_str:
        user_message = 'مشكلة في صلاحيات النظام. يرجى المحاولة مرة أخرى'
    elif 'disk' in error_str or 'space' in error_str:
        user_message = 'مساحة القرص الصلب غير كافية. يرجى المحاولة لاحقاً'
    else:
        user_message = 'حدث خطأ تقني في التصدير. يرجى المحاولة مرة أخرى أو الاتصال بالدعم الفني'
    
    technical_message = f"Export failure for {username} - {operation_type}: {error}"
    
    return user_message, technical_message