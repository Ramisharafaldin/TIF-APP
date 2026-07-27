"""
Input validation utilities for Flask application.
Provides validation functions for form inputs, file uploads, and date ranges.
"""

from datetime import datetime
import pandas as pd


def validate_file_extension(filename, allowed_extensions):
    """
    Validate file extension.
    
    Args:
        filename: Name of the file to validate
        allowed_extensions: Set of allowed extensions (e.g., {'xlsx', 'xls'})
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not filename:
        return False, 'لم يتم اختيار ملف'
    
    if '.' not in filename:
        return False, 'اسم الملف غير صالح'
    
    extension = filename.rsplit('.', 1)[1].lower()
    if extension not in allowed_extensions:
        allowed_str = ', '.join(allowed_extensions)
        return False, f'نوع الملف غير مسموح. الأنواع المسموحة: {allowed_str}'
    
    return True, None


def validate_required_field(value, field_name):
    """
    Validate that a required field is not empty.
    
    Args:
        value: Value to validate
        field_name: Name of the field for error message
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return False, f'يرجى إدخال {field_name}'
    
    return True, None


def validate_numeric_parameter(value, param_name, min_value=None, max_value=None):
    """
    Validate numeric parameter.
    
    Args:
        value: Value to validate
        param_name: Name of the parameter for error message
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)
    
    Returns:
        tuple: (is_valid, error_message, parsed_value)
    """
    try:
        parsed_value = int(value)
    except (ValueError, TypeError):
        return False, f'{param_name} يجب أن يكون رقماً صحيحاً', None
    
    if min_value is not None and parsed_value < min_value:
        return False, f'{param_name} يجب أن يكون {min_value} على الأقل', None
    
    if max_value is not None and parsed_value > max_value:
        return False, f'{param_name} يجب أن يكون {max_value} على الأكثر', None
    
    return True, None, parsed_value


def validate_date_range(start_date_str, end_date_str):
    """
    Validate date range.
    
    Args:
        start_date_str: Start date string (YYYY-MM-DD format)
        end_date_str: End date string (YYYY-MM-DD format)
    
    Returns:
        tuple: (is_valid, error_message, start_date, end_date)
    """
    # Check if dates are provided
    if not start_date_str:
        return False, 'يرجى تحديد تاريخ البداية', None, None
    
    if not end_date_str:
        return False, 'يرجى تحديد تاريخ النهاية', None, None
    
    # Parse dates
    try:
        start_date = pd.to_datetime(start_date_str)
    except Exception:
        return False, 'تاريخ البداية غير صالح', None, None
    
    try:
        end_date = pd.to_datetime(end_date_str)
    except Exception:
        return False, 'تاريخ النهاية غير صالح', None, None
    
    # Validate that start is before end
    if start_date > end_date:
        return False, 'تاريخ البداية يجب أن يكون قبل تاريخ النهاية', None, None
    
    return True, None, start_date, end_date


def validate_min_max_parameters(min_value, max_value, param_name):
    """
    Validate that min parameter is less than max parameter.
    
    Args:
        min_value: Minimum value
        max_value: Maximum value
        param_name: Name of the parameter for error message
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if min_value >= max_value:
        return False, f'الحد الأدنى لـ{param_name} يجب أن يكون أقل من الحد الأقصى'
    
    return True, None


def validate_password(password, min_length=6):
    """
    Validate password strength.
    
    Args:
        password: Password to validate
        min_length: Minimum password length
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not password:
        return False, 'يرجى إدخال كلمة المرور'
    
    if len(password) < min_length:
        return False, f'كلمة المرور يجب أن تكون {min_length} أحرف على الأقل'
    
    return True, None


def validate_username(username, min_length=3, max_length=50):
    """
    Validate username.
    
    Args:
        username: Username to validate
        min_length: Minimum username length
        max_length: Maximum username length
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not username or not username.strip():
        return False, 'يرجى إدخال اسم المستخدم'
    
    username = username.strip()
    
    if len(username) < min_length:
        return False, f'اسم المستخدم يجب أن يكون {min_length} أحرف على الأقل'
    
    if len(username) > max_length:
        return False, f'اسم المستخدم يجب أن يكون {max_length} حرف على الأكثر'
    
    # Check for valid characters (alphanumeric and underscore)
    if not username.replace('_', '').replace('-', '').isalnum():
        return False, 'اسم المستخدم يجب أن يحتوي على أحرف وأرقام فقط'
    
    return True, None


def validate_branch_name(branch_name):
    """
    Validate branch name for data uploads.
    
    Args:
        branch_name: Branch name to validate
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not branch_name:
        return False, 'يرجى إدخال اسم الفرع'
    
    branch_name = branch_name.strip()
    
    if not branch_name:
        return False, 'اسم الفرع لا يمكن أن يكون فارغاً أو مسافات فقط'
    
    if len(branch_name) < 2:
        return False, 'اسم الفرع يجب أن يكون حرفين على الأقل'
    
    if len(branch_name) > 100:
        return False, 'اسم الفرع يجب أن يكون 100 حرف على الأكثر'
    
    # Check for dangerous characters that could cause issues
    dangerous_chars = ['<', '>', '"', "'", '&', '\n', '\r', '\t']
    for char in dangerous_chars:
        if char in branch_name:
            return False, f'اسم الفرع يحتوي على حرف غير مسموح: {char}'
    
    return True, None


def validate_excel_file_structure(file_data):
    """
    Validate Excel file structure before processing.
    
    Args:
        file_data: Binary file data
    
    Returns:
        tuple: (is_valid, error_message, sheets_info)
    """
    import tempfile
    import pandas as pd
    from io import BytesIO
    
    try:
        # Try to read as Excel file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file.write(file_data)
            filepath = tmp_file.name
        
        try:
            # Check if file can be opened as Excel
            xls = pd.ExcelFile(filepath)
            sheet_names = xls.sheet_names
            xls.close()
            
            # Check for required sheets
            transactions_sheet = None
            item_info_sheet = None
            
            for sheet in sheet_names:
                sheet_lower = sheet.lower()
                if 'transaction' in sheet_lower or 'sale' in sheet_lower:
                    transactions_sheet = sheet
                elif 'item' in sheet_lower or 'inventory' in sheet_lower:
                    item_info_sheet = sheet
            
            if not transactions_sheet:
                return False, 'الملف يجب أن يحتوي على شيت "Transactions" أو "Sales"', None
            
            if not item_info_sheet:
                return False, 'الملف يجب أن يحتوي على شيت "Item info" أو "Inventory"', None
            
            # Try to read a few rows to validate structure
            try:
                df_trans = pd.read_excel(filepath, sheet_name=transactions_sheet, nrows=5)
                df_items = pd.read_excel(filepath, sheet_name=item_info_sheet, nrows=5)
                
                # Check if sheets have data
                if df_trans.empty:
                    return False, f'شيت "{transactions_sheet}" فارغ', None
                
                if df_items.empty:
                    return False, f'شيت "{item_info_sheet}" فارغ', None
                
                return True, None, {
                    'transactions_sheet': transactions_sheet,
                    'item_info_sheet': item_info_sheet,
                    'total_sheets': len(sheet_names)
                }
                
            except Exception as e:
                return False, f'خطأ في قراءة بيانات الشيتات: {str(e)}', None
            
        except Exception as e:
            return False, f'الملف تالف أو ليس ملف Excel صالح: {str(e)}', None
        
        finally:
            # Clean up temporary file
            try:
                import os
                if os.path.exists(filepath):
                    os.remove(filepath)
            except:
                pass
                
    except Exception as e:
        return False, f'خطأ في معالجة الملف: {str(e)}', None


def validate_file_size(file_data, max_size_mb=50):
    """
    Validate file size.
    
    Args:
        file_data: Binary file data
        max_size_mb: Maximum file size in MB
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not file_data:
        return False, 'الملف فارغ'
    
    file_size_mb = len(file_data) / (1024 * 1024)
    
    if file_size_mb > max_size_mb:
        return False, f'حجم الملف كبير جداً ({file_size_mb:.1f} MB). الحد الأقصى {max_size_mb} MB'
    
    if file_size_mb < 0.001:  # Less than 1KB
        return False, 'حجم الملف صغير جداً. يرجى التأكد من أن الملف يحتوي على بيانات'
    
    return True, None
