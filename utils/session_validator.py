"""
Session data validation utility for export routes.
Provides comprehensive validation of user sessions, data integrity, and ownership verification.
"""

import logging
import sqlite3
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
import pandas as pd
from flask import request, current_app, g
from flask_wtf.csrf import validate_csrf
from werkzeug.exceptions import BadRequest

# Import data store for database operations
import data_store
# Import database retry utilities
from utils.database_retry import (
    get_user_session_with_retry, 
    get_dataframe_with_retry, 
    validate_data_ownership_with_retry,
    DatabaseRetryError
)


class SessionValidationError(Exception):
    """Custom exception for session validation errors."""
    pass


class DataIntegrityError(Exception):
    """Custom exception for data integrity errors."""
    pass


class UserOwnershipError(Exception):
    """Custom exception for user ownership validation errors."""
    pass


class CSRFValidationError(Exception):
    """Custom exception for CSRF validation errors."""
    pass


def validate_csrf_token_for_export(username: str) -> Tuple[bool, str]:
    """
    Validate CSRF token for export requests with comprehensive error handling.
    
    Args:
        username: Username for logging purposes
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if CSRF token is valid
        - error_message: Arabic error message if validation fails
        
    **Validates: Requirements 6.4**
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Step 1: Check if CSRF protection is enabled
        if not current_app.config.get('WTF_CSRF_ENABLED', True):
            logger.debug(f"CSRF protection is disabled for user {username}")
            return True, ''
        
        # Step 2: Skip CSRF validation for GET requests (export routes are GET)
        if request.method == 'GET':
            logger.debug(f"Skipping CSRF validation for GET request from user {username}")
            return True, ''
        
        # Step 3: Check if CSRF has already been validated in this request
        if g.get('csrf_valid', False):
            logger.debug(f"CSRF already validated for user {username}")
            return True, ''
        
        # Step 4: Get CSRF token from various sources
        csrf_token = None
        
        # Try to get token from form data
        csrf_token = request.form.get('csrf_token')
        
        # Try to get token from headers if not in form
        if not csrf_token:
            csrf_headers = current_app.config.get('WTF_CSRF_HEADERS', ['X-CSRFToken', 'X-CSRF-Token'])
            for header in csrf_headers:
                csrf_token = request.headers.get(header)
                if csrf_token:
                    break
        
        # Try to get token from query parameters (for GET requests with CSRF)
        if not csrf_token:
            csrf_token = request.args.get('csrf_token')
        
        # Step 5: Validate token presence
        if not csrf_token:
            logger.warning(f"Missing CSRF token for export request from user {username}")
            return False, 'رمز الحماية مفقود. يرجى تحديث الصفحة والمحاولة مرة أخرى'
        
        # Step 6: Validate token using Flask-WTF
        try:
            validate_csrf(csrf_token)
            logger.debug(f"CSRF token validation successful for user {username}")
            
            # Mark CSRF as valid for this request
            g.csrf_valid = True
            
            return True, ''
            
        except Exception as csrf_error:
            logger.warning(f"CSRF token validation failed for user {username}: {csrf_error}")
            return False, 'رمز الحماية غير صالح. يرجى تحديث الصفحة والمحاولة مرة أخرى'
        
    except Exception as e:
        logger.error(f"Unexpected error during CSRF validation for user {username}: {e}", exc_info=True)
        return False, 'خطأ في التحقق من رمز الحماية. يرجى تحديث الصفحة والمحاولة مرة أخرى'


def validate_user_authentication(username: str) -> Tuple[bool, str]:
    """
    Validate user authentication and session validity with comprehensive checks.
    
    Args:
        username: Username to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if user is properly authenticated
        - error_message: Arabic error message if validation fails
        
    **Validates: Requirements 6.1, 6.2**
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Step 1: Validate username presence
        if not username or not username.strip():
            logger.warning("Authentication validation attempted with empty username")
            return False, 'اسم المستخدم غير صالح'
        
        # Step 2: Check Flask-Login authentication status
        try:
            from flask_login import current_user
            
            # Verify user is authenticated via Flask-Login
            if not current_user.is_authenticated:
                logger.warning(f"User {username} is not authenticated via Flask-Login")
                return False, 'جلسة المستخدم منتهية الصلاحية. يرجى تسجيل الدخول مرة أخرى'
            
            # Verify the authenticated user matches the requested username
            if current_user.get_id() != username:
                logger.error(f"Authentication mismatch: current_user.id={current_user.get_id()}, requested_username={username}")
                return False, 'خطأ في التحقق من هوية المستخدم. يرجى تسجيل الدخول مرة أخرى'
                
        except Exception as flask_login_error:
            logger.error(f"Flask-Login authentication check failed for user {username}: {flask_login_error}", exc_info=True)
            return False, 'خطأ في التحقق من حالة تسجيل الدخول. يرجى تسجيل الدخول مرة أخرى'
        
        # Step 3: Check Flask session validity
        try:
            from flask import session
            
            # Verify session contains required authentication data
            if not session.get('logged_in'):
                logger.warning(f"User {username} session does not have logged_in flag")
                return False, 'جلسة المستخدم غير صالحة. يرجى تسجيل الدخول مرة أخرى'
            
            # Verify session username matches
            session_username = session.get('username')
            if session_username != username:
                logger.error(f"Session username mismatch: session_username={session_username}, requested_username={username}")
                return False, 'خطأ في بيانات الجلسة. يرجى تسجيل الدخول مرة أخرى'
                
        except Exception as session_error:
            logger.error(f"Flask session validation failed for user {username}: {session_error}", exc_info=True)
            return False, 'خطأ في التحقق من بيانات الجلسة. يرجى تسجيل الدخول مرة أخرى'
        
        # Step 4: Validate user exists in database
        try:
            import auth_flask
            user_data = auth_flask.get_user(username)
            
            if not user_data:
                logger.error(f"User {username} not found in database during authentication validation")
                return False, 'المستخدم غير موجود. يرجى الاتصال بالمسؤول'
                
        except Exception as db_error:
            logger.error(f"Database user validation failed for user {username}: {db_error}", exc_info=True)
            return False, 'خطأ في التحقق من بيانات المستخدم. يرجى المحاولة مرة أخرى'
        
        # Step 5: Log successful authentication validation
        logger.debug(f"User authentication validation successful for user {username}")
        return True, ''
        
    except Exception as e:
        logger.error(f"Unexpected error during user authentication validation for user {username}: {e}", exc_info=True)
        return False, 'خطأ غير متوقع في التحقق من المصادقة. يرجى المحاولة مرة أخرى'


def validate_data_access_permissions(username: str, module: str, data_ids: Dict[str, int]) -> Tuple[bool, str]:
    """
    Validate that user has permission to access the requested data and ensure data isolation.
    
    Args:
        username: Username requesting access
        module: Module name (for logging and context)
        data_ids: Dictionary of data IDs to validate access for
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if user has access to all requested data
        - error_message: Arabic error message if validation fails
        
    **Validates: Requirements 6.2**
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Step 1: Validate input parameters
        if not username or not username.strip():
            logger.warning("Data access validation attempted with empty username")
            return False, 'اسم المستخدم غير صالح'
        
        if not isinstance(data_ids, dict):
            logger.warning(f"Data access validation attempted with invalid data_ids type for user {username}")
            return False, 'معرفات البيانات غير صالحة'
        
        # Step 2: If no data IDs to validate, return success
        if not data_ids:
            logger.debug(f"No data IDs to validate for user {username}, module {module}")
            return True, ''
        
        # Step 3: Validate ownership for each data ID
        try:
            ownership_valid, ownership_error = validate_user_ownership(username, data_ids)
            if not ownership_valid:
                logger.error(f"Data ownership validation failed for user {username}, module {module}: {ownership_error}")
                return False, ownership_error
                
        except Exception as ownership_error:
            logger.error(f"Error during data ownership validation for user {username}, module {module}: {ownership_error}", exc_info=True)
            return False, 'خطأ في التحقق من صلاحيات الوصول للبيانات'
        
        # Step 4: Additional access control checks can be added here
        # For example: time-based access, IP-based restrictions, etc.
        
        logger.debug(f"Data access permissions validation successful for user {username}, module {module}")
        return True, ''
        
    except Exception as e:
        logger.error(f"Unexpected error during data access permissions validation for user {username}, module {module}: {e}", exc_info=True)
        return False, 'خطأ غير متوقع في التحقق من صلاحيات الوصول'


def log_export_access_attempt(username: str, module: str, success: bool, error_message: str = '') -> None:
    """
    Log export access attempts for security auditing and monitoring.
    
    Args:
        username: Username attempting export
        module: Module name being exported
        success: Whether the export attempt was successful
        error_message: Error message if export failed
        
    **Validates: Requirements 6.1, 6.2**
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Import audit logger for security logging
        from utils.audit_logger import audit_logger
        
        # Prepare audit log data
        audit_data = {
            'username': username,
            'module': module,
            'action': 'export_attempt',
            'success': success,
            'timestamp': datetime.now().isoformat(),
            'user_agent': None,
            'ip_address': None
        }
        
        # Add error information if export failed
        if not success and error_message:
            audit_data['error_message'] = error_message
        
        # Try to get additional request information
        try:
            from flask import request
            audit_data['user_agent'] = request.headers.get('User-Agent', 'Unknown')
            audit_data['ip_address'] = request.remote_addr or 'Unknown'
        except Exception:
            # Request context might not be available in all cases
            pass
        
        # Log the security event
        audit_logger.log_security_event('export_access', audit_data)
        
        # Also log to application logger
        if success:
            logger.info(f"Export access granted: user={username}, module={module}")
        else:
            logger.warning(f"Export access denied: user={username}, module={module}, error={error_message}")
            
    except Exception as e:
        # Don't fail the main operation if audit logging fails
        logger.error(f"Failed to log export access attempt for user {username}, module {module}: {e}", exc_info=True)


def validate_export_request_security(username: str) -> Tuple[bool, str]:
    """
    Validate security requirements for export requests including CSRF and authentication.
    
    Args:
        username: Username to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if all security validations pass
        - error_message: Arabic error message if validation fails
        
    **Validates: Requirements 6.1, 6.4**
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Step 1: Validate user authentication
        auth_valid, auth_error = validate_user_authentication(username)
        if not auth_valid:
            logger.warning(f"Authentication validation failed for export request from user {username}: {auth_error}")
            return False, auth_error
        
        # Step 2: Validate CSRF token (for applicable requests)
        csrf_valid, csrf_error = validate_csrf_token_for_export(username)
        if not csrf_valid:
            logger.warning(f"CSRF validation failed for export request from user {username}: {csrf_error}")
            return False, csrf_error
        
        # Step 3: Additional security checks can be added here
        # For example: rate limiting, IP validation, etc.
        
        logger.debug(f"Export request security validation successful for user {username}")
        return True, ''
        
    except Exception as e:
        logger.error(f"Unexpected error during export request security validation for user {username}: {e}", exc_info=True)
        return False, 'خطأ في التحقق من أمان الطلب. يرجى المحاولة مرة أخرى'


def validate_user_session(username: str, module: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Validate user session and return session data with comprehensive error handling.
    
    Args:
        username: Username to validate
        module: Module name (dashboard, inventory, transfers, forecasting)
        
    Returns:
        Tuple of (is_valid, error_message, session_data)
        - is_valid: True if session is valid
        - error_message: Arabic error message if validation fails
        - session_data: Session data dictionary if valid, None otherwise
        
    **Validates: Requirements 2.1, 6.2, 6.3**
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Step 1: Validate input parameters
        if not username or not username.strip():
            logger.warning("Session validation attempted with empty username")
            return False, 'اسم المستخدم غير صالح', None
            
        if not module or not module.strip():
            logger.warning(f"Session validation attempted with empty module for user {username}")
            return False, 'اسم الوحدة غير صالح', None
            
        if module not in ['dashboard', 'inventory', 'transfers', 'forecasting']:
            logger.warning(f"Session validation attempted with invalid module '{module}' for user {username}")
            return False, f'وحدة غير مدعومة: {module}', None
        
        # Step 2: Special handling for dashboard module (doesn't require session data)
        if module == 'dashboard':
            logger.info(f"Dashboard session validation successful for user {username} (no session data required)")
            return True, '', {'data_ids': {}, 'params': {}}
        
        # Step 3: Retrieve session data with database error handling and retry logic for other modules
        try:
            user_session = get_user_session_with_retry(username, module, data_store.DB_NAME)
        except DatabaseRetryError as retry_error:
            logger.error(f"Database retry error during session validation for user {username}, module {module}: {retry_error}", exc_info=True)
            return False, 'خطأ في الاتصال بقاعدة البيانات بعد عدة محاولات. يرجى المحاولة مرة أخرى لاحقاً', None
        except sqlite3.Error as db_error:
            logger.error(f"Database error during session validation for user {username}, module {module}: {db_error}", exc_info=True)
            return False, 'خطأ في الاتصال بقاعدة البيانات. يرجى المحاولة مرة أخرى', None
        except Exception as session_error:
            logger.error(f"Session retrieval error for user {username}, module {module}: {session_error}", exc_info=True)
            return False, 'خطأ في تحميل بيانات الجلسة. يرجى إعادة تسجيل الدخول', None
        
        # Step 4: Validate session existence
        if not user_session:
            logger.warning(f"No user session found for user {username}, module {module}")
            return False, 'لا توجد جلسة نشطة. يرجى إجراء التحليل أولاً', None
        
        # Step 5: Validate session structure
        if not isinstance(user_session, dict):
            logger.error(f"Invalid session data type for user {username}, module {module}: {type(user_session)}")
            return False, 'بيانات الجلسة تالفة. يرجى إعادة إجراء التحليل', None
        
        # Step 6: Validate required session fields
        required_fields = ['data_ids', 'params']
        for field in required_fields:
            if field not in user_session:
                logger.warning(f"Missing required field '{field}' in session for user {username}, module {module}")
                return False, f'بيانات الجلسة غير مكتملة. يرجى إعادة إجراء التحليل', None
        
        # Step 7: Validate data_ids structure
        data_ids = user_session.get('data_ids', {})
        if not isinstance(data_ids, dict):
            logger.error(f"Invalid data_ids type for user {username}, module {module}: {type(data_ids)}")
            return False, 'معرفات البيانات تالفة. يرجى إعادة إجراء التحليل', None
        
        # Step 8: Validate module-specific data requirements
        module_requirements = {
            'dashboard': [],  # Dashboard doesn't require specific data IDs
            'inventory': ['results'],
            'transfers': ['transfer_results'],
            'forecasting': ['forecast_results']
        }
        
        # Special handling for forecasting - accept either forecast_results OR summary_df
        if module == 'forecasting':
            if not (data_ids.get('forecast_results') or data_ids.get('summary_df')):
                logger.warning(f"Missing required data ID for user {username}, module {module}")
                return False, f'لا توجد نتائج للتصدير. يرجى إجراء التحليل أولاً', None
        else:
            required_data_ids = module_requirements.get(module, [])
            for required_id in required_data_ids:
                if not data_ids.get(required_id):
                    logger.warning(f"Missing required data ID '{required_id}' for user {username}, module {module}")
                    return False, f'لا توجد نتائج للتصدير. يرجى إجراء التحليل أولاً', None
        
        # Step 9: Validate session age (optional - prevent very old sessions)
        if 'last_updated' in user_session:
            try:
                # This would require adding last_updated to session data
                # For now, we'll skip this validation
                pass
            except Exception as age_error:
                logger.warning(f"Could not validate session age for user {username}, module {module}: {age_error}")
        
        logger.info(f"Session validation successful for user {username}, module {module}")
        return True, '', user_session
        
    except Exception as e:
        logger.error(f"Unexpected error during session validation for user {username}, module {module}: {e}", exc_info=True)
        return False, 'خطأ غير متوقع في التحقق من الجلسة. يرجى المحاولة مرة أخرى', None


def validate_data_integrity(data_ids: Dict[str, int], username: str, module: str) -> Tuple[bool, str, Dict[str, pd.DataFrame]]:
    """
    Validate data integrity and load DataFrames with comprehensive error handling.
    
    Args:
        data_ids: Dictionary mapping data types to data IDs
        username: Username for logging and validation
        module: Module name for logging
        
    Returns:
        Tuple of (is_valid, error_message, dataframes_dict)
        - is_valid: True if all data is valid
        - error_message: Arabic error message if validation fails
        - dataframes_dict: Dictionary of loaded DataFrames if valid
        
    **Validates: Requirements 2.1, 6.3**
    """
    logger = logging.getLogger(__name__)
    dataframes = {}
    
    try:
        # Step 1: Validate input parameters
        if not isinstance(data_ids, dict):
            logger.error(f"Invalid data_ids type for user {username}, module {module}: {type(data_ids)}")
            return False, 'معرفات البيانات غير صالحة', {}
        
        if not data_ids:
            logger.warning(f"Empty data_ids for user {username}, module {module}")
            return False, 'لا توجد بيانات للتحقق منها', {}
        
        # Step 2: Load and validate each DataFrame
        for data_type, data_id in data_ids.items():
            try:
                # Validate data ID
                if not isinstance(data_id, int) or data_id <= 0:
                    logger.error(f"Invalid data ID for {data_type}: {data_id} for user {username}, module {module}")
                    return False, f'معرف البيانات غير صالح لـ {data_type}', {}
                
                # Load DataFrame with database error handling and retry logic
                try:
                    df = get_dataframe_with_retry(data_id, data_store.DB_NAME)
                except DatabaseRetryError as retry_error:
                    logger.error(f"Database retry error loading {data_type} (ID: {data_id}) for user {username}, module {module}: {retry_error}", exc_info=True)
                    return False, f'خطأ في قاعدة البيانات عند تحميل {data_type} بعد عدة محاولات', {}
                except sqlite3.Error as db_error:
                    logger.error(f"Database error loading {data_type} (ID: {data_id}) for user {username}, module {module}: {db_error}", exc_info=True)
                    return False, f'خطأ في قاعدة البيانات عند تحميل {data_type}', {}
                except Exception as load_error:
                    logger.error(f"Error loading {data_type} (ID: {data_id}) for user {username}, module {module}: {load_error}", exc_info=True)
                    return False, f'خطأ في تحميل بيانات {data_type}', {}
                
                # Validate DataFrame existence
                if df is None:
                    logger.error(f"DataFrame is None for {data_type} (ID: {data_id}) for user {username}, module {module}")
                    return False, f'البيانات المحفوظة لـ {data_type} تالفة. يرجى إعادة إجراء التحليل', {}
                
                # Validate DataFrame type
                if not isinstance(df, pd.DataFrame):
                    logger.error(f"Invalid DataFrame type for {data_type} (ID: {data_id}) for user {username}, module {module}: {type(df)}")
                    return False, f'نوع البيانات غير صالح لـ {data_type}', {}
                
                # Validate DataFrame is not empty (with exception for some cases)
                if df.empty:
                    # Some modules might have empty results (e.g., no transfers recommended)
                    if module == 'transfers' and data_type == 'transfer_results':
                        logger.info(f"Empty transfer results for user {username} - this is acceptable")
                    else:
                        logger.warning(f"Empty DataFrame for {data_type} (ID: {data_id}) for user {username}, module {module}")
                        return False, f'لا توجد بيانات في {data_type}. يرجى التحقق من البيانات المرفوعة', {}
                
                # Validate DataFrame structure (basic checks)
                if len(df.columns) == 0:
                    logger.error(f"DataFrame has no columns for {data_type} (ID: {data_id}) for user {username}, module {module}")
                    return False, f'بنية البيانات غير صالحة لـ {data_type}', {}
                
                # Store validated DataFrame
                dataframes[data_type] = df
                logger.debug(f"Successfully validated {data_type} with {len(df)} rows and {len(df.columns)} columns for user {username}, module {module}")
                
            except Exception as df_error:
                logger.error(f"Unexpected error validating {data_type} for user {username}, module {module}: {df_error}", exc_info=True)
                return False, f'خطأ غير متوقع في التحقق من بيانات {data_type}', {}
        
        logger.info(f"Data integrity validation successful for user {username}, module {module}: {len(dataframes)} DataFrames validated")
        return True, '', dataframes
        
    except Exception as e:
        logger.error(f"Unexpected error during data integrity validation for user {username}, module {module}: {e}", exc_info=True)
        return False, 'خطأ غير متوقع في التحقق من سلامة البيانات', {}


def validate_user_ownership(username: str, data_ids: Dict[str, int]) -> Tuple[bool, str]:
    """
    Validate that the user owns the data they're trying to export.
    
    Args:
        username: Username to validate ownership for
        data_ids: Dictionary mapping data types to data IDs
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if user owns all the data
        - error_message: Arabic error message if validation fails
        
    **Validates: Requirements 6.2**
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Step 1: Validate input parameters
        if not username or not username.strip():
            logger.warning("User ownership validation attempted with empty username")
            return False, 'اسم المستخدم غير صالح'
        
        if not isinstance(data_ids, dict) or not data_ids:
            logger.warning(f"User ownership validation attempted with invalid data_ids for user {username}")
            return False, 'معرفات البيانات غير صالحة'
        
        # Step 2: Check ownership for each data ID with retry logic
        try:
            is_valid, error_message = validate_data_ownership_with_retry(username, data_ids, data_store.DB_NAME)
            return is_valid, error_message
            
        except DatabaseRetryError as retry_error:
            logger.error(f"Database retry error during ownership validation for user {username}: {retry_error}", exc_info=True)
            return False, 'خطأ في قاعدة البيانات أثناء التحقق من الصلاحيات بعد عدة محاولات'
        except Exception as db_error:
            logger.error(f"Database connection error during ownership validation for user {username}: {db_error}", exc_info=True)
            return False, 'خطأ في الاتصال بقاعدة البيانات'
        
        logger.info(f"User ownership validation successful for user {username}: {len(data_ids)} data items validated")
        return True, ''
        
    except Exception as e:
        logger.error(f"Unexpected error during user ownership validation for user {username}: {e}", exc_info=True)
        return False, 'خطأ غير متوقع في التحقق من صلاحيات المستخدم'


def handle_corrupted_session_data(username: str, module: str) -> Tuple[bool, str]:
    """
    Handle corrupted session data by clearing it and providing recovery guidance.
    
    Args:
        username: Username whose session to clear
        module: Module name to clear
        
    Returns:
        Tuple of (success, message)
        - success: True if session was cleared successfully
        - message: Arabic message with recovery guidance
        
    **Validates: Requirements 2.1, 6.3**
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Step 1: Validate input parameters
        if not username or not username.strip():
            logger.warning("Session cleanup attempted with empty username")
            return False, 'اسم المستخدم غير صالح'
        
        if not module or not module.strip():
            logger.warning(f"Session cleanup attempted with empty module for user {username}")
            return False, 'اسم الوحدة غير صالح'
        
        # Step 2: Clear corrupted session data
        try:
            data_store.clear_user_session(username, module)
            logger.info(f"Cleared corrupted session data for user {username}, module {module}")
        except Exception as clear_error:
            logger.error(f"Error clearing session data for user {username}, module {module}: {clear_error}", exc_info=True)
            return False, 'فشل في مسح البيانات التالفة. يرجى الاتصال بالدعم الفني'
        
        # Step 3: Provide recovery guidance based on module
        recovery_messages = {
            'dashboard': 'تم مسح البيانات التالفة. يرجى تحديث الصفحة لإعادة تحميل البيانات',
            'inventory': 'تم مسح البيانات التالفة. يرجى إعادة إجراء تحليل المخزون',
            'transfers': 'تم مسح البيانات التالفة. يرجى إعادة إجراء تحليل التوازن',
            'forecasting': 'تم مسح البيانات التالفة. يرجى إعادة إجراء التنبؤ بالمبيعات'
        }
        
        recovery_message = recovery_messages.get(module, 'تم مسح البيانات التالفة. يرجى إعادة إجراء التحليل')
        
        logger.info(f"Session cleanup completed for user {username}, module {module}")
        return True, recovery_message
        
    except Exception as e:
        logger.error(f"Unexpected error during session cleanup for user {username}, module {module}: {e}", exc_info=True)
        return False, 'خطأ غير متوقع في مسح البيانات التالفة'


def comprehensive_export_validation(username: str, module: str) -> Tuple[bool, str, Optional[Dict[str, Any]], Optional[Dict[str, pd.DataFrame]]]:
    """
    Perform comprehensive validation for export operations including security checks.
    
    This function combines all validation steps into a single call for convenience.
    
    Args:
        username: Username to validate
        module: Module name to validate
        
    Returns:
        Tuple of (is_valid, error_message, session_data, dataframes)
        - is_valid: True if all validations pass
        - error_message: Arabic error message if any validation fails
        - session_data: Session data dictionary if valid
        - dataframes: Dictionary of loaded DataFrames if valid
        
    **Validates: Requirements 2.1, 6.1, 6.2, 6.3, 6.4**
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Starting comprehensive export validation for user {username}, module {module}")
        
        # Step 1: Validate export request security (including CSRF and authentication)
        security_valid, security_error = validate_export_request_security(username)
        if not security_valid:
            logger.warning(f"Security validation failed for user {username}, module {module}: {security_error}")
            # Log failed access attempt
            log_export_access_attempt(username, module, False, security_error)
            return False, security_error, None, None
        
        # Step 2: Validate user session
        session_valid, session_error, session_data = validate_user_session(username, module)
        if not session_valid:
            logger.warning(f"Session validation failed for user {username}, module {module}: {session_error}")
            # Log failed access attempt
            log_export_access_attempt(username, module, False, session_error)
            return False, session_error, None, None
        
        # Step 3: Validate data access permissions
        data_ids = session_data.get('data_ids', {})
        if data_ids:  # Only validate permissions if there are data IDs
            access_valid, access_error = validate_data_access_permissions(username, module, data_ids)
            if not access_valid:
                logger.error(f"Data access permissions validation failed for user {username}, module {module}: {access_error}")
                # Log failed access attempt
                log_export_access_attempt(username, module, False, access_error)
                return False, access_error, None, None
        
        # Step 4: Validate user ownership (additional check)
        if data_ids:  # Only validate ownership if there are data IDs
            ownership_valid, ownership_error = validate_user_ownership(username, data_ids)
            if not ownership_valid:
                logger.error(f"Ownership validation failed for user {username}, module {module}: {ownership_error}")
                # Log failed access attempt
                log_export_access_attempt(username, module, False, ownership_error)
                return False, ownership_error, None, None
        
        # Step 5: Validate data integrity
        if data_ids:  # Only validate data if there are data IDs
            integrity_valid, integrity_error, dataframes = validate_data_integrity(data_ids, username, module)
            if not integrity_valid:
                logger.error(f"Data integrity validation failed for user {username}, module {module}: {integrity_error}")
                # Try to handle corrupted data
                cleanup_success, cleanup_message = handle_corrupted_session_data(username, module)
                # Log failed access attempt
                log_export_access_attempt(username, module, False, integrity_error)
                if cleanup_success:
                    return False, cleanup_message, None, None
                else:
                    return False, integrity_error, None, None
        else:
            # No data IDs to validate (e.g., dashboard export)
            dataframes = {}
        
        # Step 6: Log successful access attempt
        log_export_access_attempt(username, module, True)
        
        logger.info(f"Comprehensive export validation successful for user {username}, module {module}")
        return True, '', session_data, dataframes
        
    except Exception as e:
        logger.error(f"Unexpected error during comprehensive export validation for user {username}, module {module}: {e}", exc_info=True)
        # Log failed access attempt
        log_export_access_attempt(username, module, False, 'خطأ غير متوقع في التحقق من صحة البيانات للتصدير')
        return False, 'خطأ غير متوقع في التحقق من صحة البيانات للتصدير', None, None