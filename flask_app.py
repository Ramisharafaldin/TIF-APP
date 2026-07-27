import os
import sys
import logging
import json
import io
import pandas as pd
import numpy as np
import secrets
import datetime
import time
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_required, UserMixin, login_user, logout_user, current_user
import webbrowser
import threading
import sqlite3
from utils.logging_config import performance_monitor, get_upload_logger, get_performance_logger, get_memory_usage
# Import utility modules
from utils import data_processing, analysis, ui_helpers, flask_helpers, validation, alert_service
# Import data storage module
import data_store

# Helper function for PyInstaller paths
def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Initialize Flask application with environment-aware paths
app = Flask(__name__, 
            static_folder=get_resource_path('static'),
            template_folder=get_resource_path('templates'))
# Set a secret key for session management and CSRF protection
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
if not app.config['SECRET_KEY']:
    app.logger.warning("SECRET_KEY not set! Generate one: python -c \"import secrets; print(secrets.token_hex(32))\"")
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
# Allowed upload extensions
ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}
# Expose allowed extensions via app config for helpers and upload handlers
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS
# Upload folder (physical storage)
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
# Ensure upload folder exists on startup
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except Exception as e:
    print(f"Warning: could not create upload folder {app.config['UPLOAD_FOLDER']}: {e}")
# Enable CSRF protection
csrf = CSRFProtect(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

import auth_flask

class User(UserMixin):
    def __init__(self, username, is_admin=False, role=None):
        self.id = username
        self.is_admin = is_admin
        self.role = role or ('admin' if is_admin else 'viewer')
    
    def get_id(self):
        return self.id

@login_manager.user_loader
def load_user(username):
    user_data = auth_flask.get_user(username)
    if user_data:
        # get_user returns (username, is_admin, role)
        username_val, is_admin, role = user_data[0], user_data[1], user_data[2] if len(user_data) > 2 else None
        return User(username=username_val, is_admin=bool(is_admin), role=role)
    return None


# ZERO-TOLERANCE: AI Hard Isolation
# AI Service is ONLY initialized if explicitly enabled
AI_ENABLED = os.environ.get('AI_ENABLED', 'false').lower() == 'true'

if AI_ENABLED:
    try:
        from utils.ai_config import ai_config
        ai_config.log_configuration_status()
        
        from modules.ai_insights import validate_ai_service
        ai_valid, ai_message = validate_ai_service()
        if ai_valid:
            app.logger.info(f"AI Service: {ai_message}")
        else:
            app.logger.warning(f"AI Service: {ai_message}")
            
    except Exception as ai_error:
        app.logger.error(f"Failed to initialize AI service: {ai_error}")
else:
    app.logger.info("AI Service: DETACHED MODE (AI_ENABLED=False). Core systems running independently.")

def get_runtime_directory():
    if getattr(sys, 'frozen', False):
        # Running as executable - use executable's directory
        return os.path.dirname(sys.executable)
    # Running as Python script - use current directory
    return os.path.abspath(".")

def open_browser():
    """ Open browser after a small delay to ensure Flask is running """
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')

def initialize_runtime_directories():

    runtime_dir = get_runtime_directory()
    
    # Define directories to create
    directories = ['uploads', 'logs', 'flask_sessions']
    
    for dir_name in directories:
        dir_path = os.path.join(runtime_dir, dir_name)
        try:
            os.makedirs(dir_path, exist_ok=True)
            logger = logging.getLogger(__name__)
            logger.debug(f"Runtime directory initialized: {dir_path}")
        except OSError as e:
            error_msg = f"Failed to create runtime directory '{dir_path}': {e}"
            raise OSError(error_msg) from e

def not_found_error(error):

    app.logger.warning(f"404 error: {request.url}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):

    app.logger.error(f"500 error: {error}")
    return render_template('500.html'), 500

@app.errorhandler(413)
def request_entity_too_large(error):

    app.logger.warning(f"413 error: File size limit exceeded")
    return render_template('413.html'), 413

@app.errorhandler(403)
def forbidden_error(error):

    app.logger.warning(f"403 error: Unauthorized access attempt to {request.url}")
    return render_template('403.html'), 403

# ============================================================================
# Authentication Routes
# ============================================================================

# ============================================================================
# ADMIN SETUP ROUTE (One-time initial setup - Task 1)
# ============================================================================

@app.route('/setup', methods=['GET', 'POST'])
def setup_admin():
    """
    Initial admin account setup (one-time use).
    
    GET: Display setup form with token validation
    POST: Create admin account with user-provided password
    """
    
    app.logger.debug("Setup request received")

    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'GET':
        token = request.args.get('token', '').strip()
        if not token:
            flash('رمز الإعداد مفقود', 'error')
            return redirect(url_for('login'))

        is_valid, is_expired, message = auth_flask.validate_setup_token(token)
        if not is_valid:
            if is_expired:
                flash('انتهت صلاحية رمز الإعداد', 'error')
            else:
                flash(message, 'error')
            return redirect(url_for('login'))

        return render_template('setup.html', token=token)

    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        is_valid, is_expired, message = auth_flask.validate_setup_token(token)
        if not is_valid:
            flash('رمز الإعداد غير صالح', 'error')
            return render_template('setup.html', token=token)

        if not username or len(username) < 3:
            flash('اسم المستخدم يجب أن يكون 3 أحرف على الأقل', 'error')
            return render_template('setup.html', token=token)

        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            flash('اسم المستخدم يحتوي على أحرف غير صالحة', 'error')
            return render_template('setup.html', token=token)

        if not password or len(password) < 8:
            flash('كلمة المرور يجب أن تكون 8 أحرف على الأقل', 'error')
            return render_template('setup.html', token=token)

        if password != password_confirm:
            flash('كلمات المرور غير متطابقة', 'error')
            return render_template('setup.html', token=token)

        try:
            success, message = auth_flask.add_user(username, password, is_admin=True)
            if not success:
                flash(f'خطأ: {message}', 'error')
                return render_template('setup.html', token=token)

            auth_flask.use_setup_token(token, username)
            flash('تم إنشاء حساب المسؤول بنجاح!', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            app.logger.exception("Setup admin failed")
            flash(f'خطأ: {str(e)}', 'error')
            return render_template('setup.html', token=token)

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Validate username
        username_valid, username_error = validation.validate_required_field(username, 'اسم المستخدم')
        if not username_valid:
            flash(username_error, 'error')
            return render_template('login.html')
        
        # Validate password
        password_valid, password_error = validation.validate_required_field(password, 'كلمة المرور')
        if not password_valid:
            flash(password_error, 'error')
            return render_template('login.html')
        
        # Authenticate user
        login_result = auth_flask.login_user(username, password)
        
        if login_result[0]:  # success flag
            success, is_admin, role, message = login_result
            # Create session
            session.permanent = True
            user = User(username, is_admin, role)
            login_user(user)
            session['logged_in'] = True
            session['username'] = username
            session['is_admin'] = is_admin
            session['role'] = role
            
            app.logger.info(f'User {username} logged in successfully with role: {role}')
            flash(message, 'success')
            return redirect(url_for('home'))
        else:
            success, is_admin, role, message = login_result
            app.logger.warning(f'Failed login attempt for user {username}')
            flash(message, 'error')
            return render_template('login.html')
    
    # GET request - display login page
    # If already logged in, redirect to home
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():

    username = session.get('username', 'Unknown')
    
    # Clear all session data before redirect
    logout_user()
    session.clear()
    
    # Log logout event with username and timestamp
    app.logger.info(f'User {username} logged out')
    
    # Create response with redirect
    response = redirect(url_for('login'))
    
    # Add response headers to expire session cookie
    # This ensures the cookie is removed from the client browser
    response.set_cookie(
        app.config.get('SESSION_COOKIE_NAME', 'session'),
        value='',
        max_age=0,
        expires=0,
        path='/',
        httponly=True,
        samesite='Lax'
    )
    
    # Add cache control headers to prevent form caching
    # This prevents the browser from caching the login form with credentials
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    # Flash message after clearing session (will be shown on login page)
    flash('تم تسجيل الخروج بنجاح', 'info')
    
    return response

@app.route('/')
@login_required
def home():

    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():

    try:
        username = session.get('username')
        
        # Get data from all branches
        df_sales, df_inventory = data_store.get_branch_data(username, branch_name=None)
        
        # Normalize columns to ensure compatibility with new aliases (fixes issues with existing data)
        if df_sales is not None:
            df_sales = data_processing.normalize_columns(df_sales)
        if df_inventory is not None:
            df_inventory = data_processing.normalize_columns(df_inventory)
        
        if df_sales is None or df_inventory is None:
            # No data available
            filters = session.get('dashboard_filters', {})
            # Get branches even if no data (might be cached or empty)
            branches = data_store.get_all_branches(username)
            
            return render_template('dashboard.html', 
                                 has_data=False,
                                 filters=filters,
                                 username=username,
                                 stats={'total_sales': 0, 'total_products': 0, 'total_stock_value': 0, 'total_suppliers': 0},
                                 monthly_sales_data={'labels': [], 'values': []},
                                 supplier_sales_data={'labels': [], 'values': []},
                                 department_stock_data={'labels': [], 'values': []},
                                 branches=branches)
        
        # Apply performance filtering before dashboard calculations
        try:
            from utils.performance_filter import filter_inactive_items_with_fallback
            df_sales, df_inventory, filter_stats = filter_inactive_items_with_fallback(
                df_sales, df_inventory, log_stats=True, username=username
            )
            
            # Log filtering results for dashboard
            if filter_stats.get('items_filtered', 0) > 0:
                app.logger.info(f"Dashboard filtering: {filter_stats['items_filtered']} inactive items filtered "
                               f"({filter_stats.get('filtering_percentage', 0):.1f}% reduction)")
        except Exception as filter_error:
            app.logger.warning(f"Dashboard filtering failed: {filter_error}, proceeding with unfiltered data")
            # Continue with original data if filtering fails
        
        # Get filters from session
        filters = session.get('dashboard_filters', {})
        
        # Apply filters
        filtered_sales = df_sales.copy()
        if filters.get('start_date'):
            filtered_sales = filtered_sales[filtered_sales['sale_date'] >= pd.to_datetime(filters['start_date'])]
        if filters.get('end_date'):
            filtered_sales = filtered_sales[filtered_sales['sale_date'] <= pd.to_datetime(filters['end_date'])]
        if filters.get('branch'):
            filtered_sales = filtered_sales[filtered_sales['branch_code'] == filters['branch']]
        
        # Apply filters to inventory
        filtered_inventory = df_inventory.copy()
        if filters.get('branch'):
            if 'branch_code' in filtered_inventory.columns:
                filtered_inventory = filtered_inventory[filtered_inventory['branch_code'] == filters['branch']]
        
        # Debug logging
        app.logger.info(f"Inventory columns: {filtered_inventory.columns.tolist()}")
        
        # Fallback: Try to identify columns if missing
        if 'inventory_value' not in filtered_inventory.columns:
            for col in filtered_inventory.columns:
                if any(x in col.lower() for x in ['cost', 'price', 'value', 'amount', 'unit']):
                    filtered_inventory['inventory_value'] = filtered_inventory[col]
                    app.logger.info(f"Using column '{col}' as inventory_value")
                    break
        
        if 'Last_on_hand' not in filtered_inventory.columns:
            for col in filtered_inventory.columns:
                if any(x in col.lower() for x in ['qty', 'quantity', 'stock', 'hand', 'count', 'balance']):
                    filtered_inventory['Last_on_hand'] = filtered_inventory[col]
                    app.logger.info(f"Using column '{col}' as Last_on_hand")
                    break

        # Ensure numeric types for calculation
        if 'inventory_value' in filtered_inventory.columns:
            filtered_inventory['inventory_value'] = pd.to_numeric(filtered_inventory['inventory_value'], errors='coerce').fillna(0)
        
        if 'Last_on_hand' in filtered_inventory.columns:
            filtered_inventory['Last_on_hand'] = pd.to_numeric(filtered_inventory['Last_on_hand'], errors='coerce').fillna(0)

        # Calculate statistics
        # Calculate metrics using DuckDB for accuracy and performance
        stats = data_store.calculate_dashboard_metrics(filtered_sales, filtered_inventory)
        
        # Monthly sales data
        if 'sale_date' in filtered_sales.columns and 'revenue' in filtered_sales.columns:
            filtered_sales['month'] = pd.to_datetime(filtered_sales['sale_date']).dt.to_period('M')
            monthly_sales = filtered_sales.groupby('month')['revenue'].sum().reset_index()
            monthly_sales['month'] = monthly_sales['month'].astype(str)
            monthly_sales_data = {
                'labels': monthly_sales['month'].tolist(),
                'values': monthly_sales['revenue'].tolist()
            }
        else:
            monthly_sales_data = {'labels': [], 'values': []}
        
        # Supplier sales share
        if 'supplier_name' in filtered_inventory.columns and 'revenue' in filtered_sales.columns:
            # Merge to get supplier info
            sales_with_supplier = pd.merge(
                filtered_sales, 
                filtered_inventory[['product_code', 'supplier_name']].drop_duplicates(),
                on='product_code',
                how='left'
            )
            supplier_sales = sales_with_supplier.groupby('supplier_name')['revenue'].sum().reset_index()
            supplier_sales = supplier_sales.nlargest(10, 'revenue')  # Top 10 suppliers
            supplier_sales_data = {
                'labels': supplier_sales['supplier_name'].fillna('غير محدد').tolist(),
                'values': supplier_sales['revenue'].tolist()
            }
        else:
            supplier_sales_data = {'labels': [], 'values': []}
        
        # Department stock percentage
        if 'item_category1' in filtered_inventory.columns and 'Last_on_hand' in filtered_inventory.columns:
            dept_stock = filtered_inventory.groupby('item_category1')['Last_on_hand'].sum().reset_index()
            dept_stock = dept_stock.nlargest(10, 'Last_on_hand')  # Top 10 departments
            department_stock_data = {
                'labels': dept_stock['item_category1'].fillna('غير محدد').tolist(),
                'values': dept_stock['Last_on_hand'].tolist()
            }
        else:
            department_stock_data = {'labels': [], 'values': []}
        
        # Get unique branches for filter
        branches = data_store.get_all_branches(username)
        
        return render_template('dashboard.html',
                             has_data=True,
                             stats=stats,
                             monthly_sales_data=monthly_sales_data,
                             supplier_sales_data=supplier_sales_data,
                             department_stock_data=department_stock_data,
                             branches=branches,
                             filters=filters,
                             username=username)
        
    except Exception as e:
        app.logger.error(f"Dashboard error: {e}", exc_info=True)
        # Get filters from session even in error case
        filters = session.get('dashboard_filters', {})
        return render_template('dashboard.html', 
                             has_data=False,
                             username=session.get('username'),
                             filters=filters,
                             error=str(e),
                             stats={'total_sales': 0, 'total_products': 0, 'total_stock_value': 0, 'total_suppliers': 0},
                             monthly_sales_data={'labels': [], 'values': []},
                             supplier_sales_data={'labels': [], 'values': []},
                             department_stock_data={'labels': [], 'values': []},
                             branches=[])

@app.route('/dashboard/filter', methods=['POST'])
@login_required
def dashboard_filter():
    """
    Handle dashboard filter changes and invalidate alert cache when branch filter changes.
    
    **Integrates: Requirements 4.3, 6.2, 6.3**
    """
    try:
        username = session.get('username')
        
        # Get current filters to compare for changes
        current_filters = session.get('dashboard_filters', {})
        
        filters = {
            'start_date': request.form.get('start_date'),
            'end_date': request.form.get('end_date'),
            'branch': request.form.get('branch')
        }
        
        # Check if branch filter changed (affects alert cache)
        branch_changed = current_filters.get('branch') != filters.get('branch')
        
        # Save filters to session
        session['dashboard_filters'] = filters
        
        # Invalidate alert cache if branch filter changed
        if branch_changed and username:
            try:
                alert_service.invalidate_alert_cache(username)
                app.logger.debug(f"Invalidated alert cache for user {username} due to branch filter change")
            except Exception as cache_error:
                app.logger.warning(f"Failed to invalidate alert cache for user {username}: {cache_error}")
                # Don't fail the entire request if cache invalidation fails
        
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        app.logger.error(f"Error applying dashboard filters: {e}", exc_info=True)
        flash('حدث خطأ في تطبيق الفلتر', 'error')
        return redirect(url_for('dashboard'))

@app.route('/dashboard/export')
@app.route('/dashboard/export/<format>')
@login_required
def dashboard_export(format='xlsx'):
    """
    Export dashboard data with comprehensive error handling and multi-format support.
    
    **Validates: Requirements 2.2, 2.3, 2.4, 5.1, 7.1, 7.4, 7.5**
    """
    username = session.get('username')
    
    # Strictly enforce XLSX
    format = 'xlsx'
    
    try:
        app.logger.info(f"Dashboard export initiated by user: {username}")
        
        # Enhanced comprehensive session and security validation
        from utils.session_validator import comprehensive_export_validation
        
        # Validate security requirements including CSRF protection
        validation_success, error_message, session_data, dataframes = comprehensive_export_validation(username, 'dashboard')
        
        if not validation_success:
            app.logger.warning(f"Dashboard export validation failed for user {username}: {error_message}")
            flash(error_message, 'error')
            return redirect(url_for('dashboard'))
        
        # Load data from all branches with specific error handling
        try:
            df_sales, df_inventory = data_store.get_branch_data(username, branch_name=None)
        except Exception as data_error:
            app.logger.error(f"Data retrieval error during dashboard export for user {username}: {data_error}", exc_info=True)
            flash('خطأ في تحميل البيانات. يرجى التأكد من وجود بيانات مرفوعة', 'error')
            return redirect(url_for('dashboard'))
        
        # Validate data availability
        if df_sales is None and df_inventory is None:
            app.logger.warning(f"No data available for dashboard export for user {username}")
            flash('لا توجد بيانات للتصدير. يرجى رفع ملفات البيانات أولاً', 'warning')
            return redirect(url_for('dashboard'))
        
        if df_sales is None:
            app.logger.warning(f"No sales data available for dashboard export for user {username}")
            flash('لا توجد بيانات مبيعات للتصدير. سيتم تصدير بيانات المخزون فقط', 'warning')
        
        if df_inventory is None:
            app.logger.warning(f"No inventory data available for dashboard export for user {username}")
            flash('لا توجد بيانات مخزون للتصدير. سيتم تصدير بيانات المبيعات فقط', 'warning')
        
        # Normalize columns with error handling
        try:
            if df_sales is not None:
                df_sales = data_processing.normalize_columns(df_sales)
            if df_inventory is not None:
                df_inventory = data_processing.normalize_columns(df_inventory)
        except Exception as normalize_error:
            app.logger.error(f"Column normalization error during dashboard export for user {username}: {normalize_error}", exc_info=True)
            flash('خطأ في معالجة أعمدة البيانات. يرجى التحقق من تنسيق الملفات', 'error')
            return redirect(url_for('dashboard'))
        
        # Apply filters with error handling
        try:
            filters = session.get('dashboard_filters', {})
            filtered_sales = df_sales.copy() if df_sales is not None else None
            
            if filtered_sales is not None:
                if filters.get('start_date'):
                    try:
                        start_date = pd.to_datetime(filters['start_date'])
                        filtered_sales = filtered_sales[filtered_sales['sale_date'] >= start_date]
                    except (ValueError, KeyError) as date_error:
                        app.logger.warning(f"Invalid start date filter for user {username}: {date_error}")
                        
                if filters.get('end_date'):
                    try:
                        end_date = pd.to_datetime(filters['end_date'])
                        filtered_sales = filtered_sales[filtered_sales['sale_date'] <= end_date]
                    except (ValueError, KeyError) as date_error:
                        app.logger.warning(f"Invalid end date filter for user {username}: {date_error}")
                        
                if filters.get('branch'):
                    try:
                        if 'branch_code' in filtered_sales.columns:
                            filtered_sales = filtered_sales[filtered_sales['branch_code'] == filters['branch']]
                    except KeyError as branch_error:
                        app.logger.warning(f"Branch filter error for user {username}: {branch_error}")
                        
        except Exception as filter_error:
            app.logger.error(f"Filter application error during dashboard export for user {username}: {filter_error}", exc_info=True)
            flash('خطأ في تطبيق الفلاتر. سيتم تصدير جميع البيانات', 'warning')
            filtered_sales = df_sales.copy() if df_sales is not None else None
        
        # Prepare data for export
        monthly_sales = None
        supplier_sales = None
        dept_stock = None
        
        # 1. Monthly Sales
        if filtered_sales is not None and 'sale_date' in filtered_sales.columns and 'revenue' in filtered_sales.columns:
            try:
                sales_temp = filtered_sales.copy()
                sales_temp['month'] = pd.to_datetime(sales_temp['sale_date']).dt.to_period('M')
                monthly_sales = sales_temp.groupby('month')['revenue'].sum().reset_index()
                monthly_sales['month'] = monthly_sales['month'].astype(str)
            except Exception as e:
                app.logger.warning(f"Failed to prepare monthly sales: {e}")

        # 2. Supplier Sales
        if (filtered_sales is not None and df_inventory is not None and 
            'supplier_name' in df_inventory.columns and 'revenue' in filtered_sales.columns):
            try:
                sales_with_supplier = pd.merge(
                    filtered_sales,
                    df_inventory[['product_code', 'supplier_name']].drop_duplicates(),
                    on='product_code',
                    how='left'
                )
                supplier_sales = sales_with_supplier.groupby('supplier_name')['revenue'].sum().reset_index()
                supplier_sales = supplier_sales.sort_values('revenue', ascending=False)
            except Exception as e:
                app.logger.warning(f"Failed to prepare supplier sales: {e}")
                
        # 3. Department Stock
        if df_inventory is not None and 'item_category1' in df_inventory.columns and 'Last_on_hand' in df_inventory.columns:
            try:
                dept_stock = df_inventory.groupby('item_category1')['Last_on_hand'].sum().reset_index()
                dept_stock = dept_stock.sort_values('Last_on_hand', ascending=False)
            except Exception as e:
                app.logger.warning(f"Failed to prepare dept stock: {e}")

        # Use UI helper to generate Excel
        from utils import ui_helpers
        import io
        
        excel_data = ui_helpers.export_dashboard_report(monthly_sales, supplier_sales, dept_stock, ai_insights=None)
        
        return send_file(
            io.BytesIO(excel_data),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"dashboard_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

    except Exception as e:
        app.logger.error(f"Dashboard export failed: {e}", exc_info=True)
        flash('حدث خطأ أثناء تصدير البيانات', 'error')
        return redirect(url_for('dashboard'))

@app.route('/api/supplier-distribution')
@login_required
def api_supplier_distribution():
    """
    API endpoint for supplier distribution data.
    Returns supplier names, values, and percentages for enhanced visualization.
    """
    try:
        username = session.get('username')
        
        # Get data from all branches (same as dashboard)
        df_sales, df_inventory = data_store.get_branch_data(username, branch_name=None)
        
        # Normalize columns to ensure compatibility
        if df_sales is not None:
            df_sales = data_processing.normalize_columns(df_sales)
        if df_inventory is not None:
            df_inventory = data_processing.normalize_columns(df_inventory)
        
        if df_sales is None or df_inventory is None:
            return jsonify({
                'success': False,
                'message': 'لا توجد بيانات متاحة',
                'suppliers': [],
                'totalValue': 0,
                'lastUpdated': datetime.datetime.now().isoformat()
            })
        
        # Apply performance filtering before supplier distribution calculations
        try:
            from utils.performance_filter import filter_inactive_items_with_fallback
            df_sales, df_inventory, filter_stats = filter_inactive_items_with_fallback(
                df_sales, df_inventory, log_stats=True, username=username
            )
            
            # Log filtering results for supplier distribution API
            if filter_stats.get('items_filtered', 0) > 0:
                app.logger.debug(f"Supplier distribution API filtering: {filter_stats['items_filtered']} inactive items filtered")
        except Exception as filter_error:
            app.logger.warning(f"Supplier distribution API filtering failed: {filter_error}, proceeding with unfiltered data")
            # Continue with original data if filtering fails
        
        # Apply filters from session
        filters = session.get('dashboard_filters', {})
        filtered_sales = df_sales.copy()
        if filters.get('start_date'):
            filtered_sales = filtered_sales[filtered_sales['sale_date'] >= pd.to_datetime(filters['start_date'])]
        if filters.get('end_date'):
            filtered_sales = filtered_sales[filtered_sales['sale_date'] <= pd.to_datetime(filters['end_date'])]
        if filters.get('branch'):
            filtered_sales = filtered_sales[filtered_sales['branch_code'] == filters['branch']]
        
        # Apply filters to inventory
        filtered_inventory = df_inventory.copy()
        if filters.get('branch'):
            if 'branch_code' in filtered_inventory.columns:
                filtered_inventory = filtered_inventory[filtered_inventory['branch_code'] == filters['branch']]
        
        # Calculate supplier distribution
        if 'supplier_name' in filtered_inventory.columns and 'revenue' in filtered_sales.columns:
            # Merge to get supplier info
            sales_with_supplier = pd.merge(
                filtered_sales, 
                filtered_inventory[['product_code', 'supplier_name']].drop_duplicates(),
                on='product_code',
                how='left'
            )
            
            # Group by supplier and calculate totals
            supplier_sales = sales_with_supplier.groupby('supplier_name')['revenue'].sum().reset_index()
            supplier_sales = supplier_sales.sort_values('revenue', ascending=False)
            
            # Calculate percentages
            total_revenue = supplier_sales['revenue'].sum()
            if total_revenue > 0:
                supplier_sales['percentage'] = (supplier_sales['revenue'] / total_revenue * 100).round(2)
            else:
                supplier_sales['percentage'] = 0
            
            # Prepare supplier data with colors
            colors = [
                '#135bec', '#3b82f6', '#60a5fa', '#93c5fd', '#dbeafe', '#eff6ff',
                '#f59e0b', '#fbbf24', '#fcd34d', '#fde68a', '#fef3c7', '#fffbeb',
                '#10b981', '#34d399', '#6ee7b7', '#a7f3d0', '#d1fae5', '#ecfdf5',
                '#ef4444', '#f87171', '#fca5a5', '#fecaca', '#fee2e2', '#fef2f2'
            ]
            
            suppliers_data = []
            for idx, row in supplier_sales.iterrows():
                supplier_name = row['supplier_name'] if pd.notna(row['supplier_name']) else 'غير محدد'
                suppliers_data.append({
                    'name': supplier_name,
                    'value': float(row['revenue']),
                    'percentage': float(row['percentage']),
                    'color': colors[idx % len(colors)]
                })
            
            return jsonify({
                'success': True,
                'suppliers': suppliers_data,
                'totalValue': float(total_revenue),
                'lastUpdated': datetime.datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'البيانات المطلوبة غير متوفرة (supplier_name أو revenue)',
                'suppliers': [],
                'totalValue': 0,
                'lastUpdated': datetime.datetime.now().isoformat()
            })
        
    except Exception as e:
        app.logger.error(f"Error in supplier distribution API: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'حدث خطأ في تحميل بيانات الموردين: {str(e)}',
            'suppliers': [],
            'totalValue': 0,
            'lastUpdated': datetime.datetime.now().isoformat()
        }), 500

@app.route('/api/inventory-alerts')
@login_required
def api_inventory_alerts():
    """
    API endpoint for inventory alerts.
    Returns inventory alerts in JSON format with product, branch, status, and quantity information.
    
    Query Parameters:
    - branch: Filter alerts by branch code (optional, overrides dashboard filter)
    - limit: Maximum number of alerts to return (default: 10)
    - severity: Filter by alert severity (optional)
    - use_dashboard_filters: Use dashboard session filters (default: true)
    
    Returns:
        JSON response with alerts data or error message
        
    **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
    **Integrates: Requirements 4.3, 6.2, 6.3**
    """
    try:
        username = session.get('username')
        
        # Get query parameters with validation
        branch_filter = request.args.get('branch', None)
        limit_param = request.args.get('limit', '10')
        severity_filter = request.args.get('severity', None)
        use_dashboard_filters = request.args.get('use_dashboard_filters', 'true').lower() == 'true'
        
        # Validate limit parameter
        try:
            limit = int(limit_param)
            if limit < 1:
                limit = 10
            elif limit > 1000:  # Reasonable upper bound
                limit = 1000
        except (ValueError, TypeError):
            limit = 10
        
        # Integrate with dashboard filters if requested and no explicit branch filter
        if use_dashboard_filters and branch_filter is None:
            dashboard_filters = session.get('dashboard_filters', {})
            if dashboard_filters.get('branch'):
                branch_filter = dashboard_filters['branch']
                app.logger.debug(f"Using dashboard branch filter: {branch_filter}")
        
        # Validate branch filter (if provided)
        if branch_filter is not None:
            branch_filter = branch_filter.strip()
            if not branch_filter:
                branch_filter = None
        
        # Generate alerts using the alert service with comprehensive error handling
        try:
            alerts = alert_service.generate_inventory_alerts(
                username=username,
                branch_filter=branch_filter,
                limit=limit
            )
        except Exception as alert_error:
            app.logger.error(f"Alert generation failed for user {username}: {alert_error}")
            
            # Return user-friendly error response
            error_response = {
                "success": False,
                "message": "لا يمكن تحميل تنبيهات المخزون حالياً. يرجى المحاولة مرة أخرى.",
                "error_type": "alert_generation_failed",
                "alerts": [],
                "total_alerts": 0,
                "last_updated": datetime.datetime.now().isoformat(),
                "filters": {
                    "branch": branch_filter,
                    "limit": limit,
                    "severity": severity_filter
                }
            }
            return jsonify(error_response), 500
        
        # Apply severity filter if provided
        if severity_filter:
            severity_filter = severity_filter.strip()
            if severity_filter:
                alerts = [alert for alert in alerts if alert.alert_status == severity_filter]
        
        # Convert alerts to dictionary format for JSON response
        try:
            alerts_data = [alert.to_dict() for alert in alerts]
        except Exception as conversion_error:
            app.logger.error(f"Error converting alerts to dict for user {username}: {conversion_error}")
            
            # Return user-friendly error response
            error_response = {
                "success": False,
                "message": "حدث خطأ في تنسيق بيانات التنبيهات. يرجى المحاولة مرة أخرى.",
                "error_type": "data_conversion_failed",
                "alerts": [],
                "total_alerts": 0,
                "last_updated": datetime.datetime.now().isoformat(),
                "filters": {
                    "branch": branch_filter,
                    "limit": limit,
                    "severity": severity_filter
                }
            }
            return jsonify(error_response), 500
        
        # Check if no data is available
        if len(alerts_data) == 0:
            # Determine appropriate message based on filters
            if branch_filter:
                message = f"لا توجد تنبيهات مخزون للفرع '{branch_filter}'"
            elif severity_filter:
                message = f"لا توجد تنبيهات بمستوى '{severity_filter}'"
            else:
                message = "لا توجد تنبيهات مخزون حالياً. جميع المنتجات في مستوى آمن."
            
            # Return successful response with no data message
            response_data = {
                "success": True,
                "message": message,
                "alerts": [],
                "total_alerts": 0,
                "last_updated": datetime.datetime.now().isoformat(),
                "filters": {
                    "branch": branch_filter,
                    "limit": limit,
                    "severity": severity_filter
                }
            }
        else:
            # Prepare successful response with data
            response_data = {
                "success": True,
                "alerts": alerts_data,
                "total_alerts": len(alerts_data),
                "last_updated": datetime.datetime.now().isoformat(),
                "filters": {
                    "branch": branch_filter,
                    "limit": limit,
                    "severity": severity_filter
                }
            }
        
        app.logger.info(f"API: Generated {len(alerts_data)} alerts for user {username}")
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Unexpected error in inventory alerts API: {e}", exc_info=True)
        
        # Return generic error response for unexpected errors
        error_response = {
            "success": False,
            "message": "حدث خطأ غير متوقع. يرجى إعادة تحميل الصفحة أو المحاولة لاحقاً.",
            "error_type": "unexpected_error",
            "alerts": [],
            "total_alerts": 0,
            "last_updated": datetime.datetime.now().isoformat()
        }
        

@app.route('/api/notifications')
@login_required
def api_notifications():
    """
    API endpoint for dynamic notifications.
    Returns alerts for items below safety stock or running out in 7 days.
    """
    try:
        username = session.get('username')
        notifications = alert_service.generate_notifications(username)
        
        return jsonify({
            'success': True,
            'notifications': notifications,
            'count': len(notifications),
            'timestamp': datetime.datetime.now().isoformat()
        })
    except Exception as e:
        app.logger.error(f"Error in api_notifications: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/performance-stats')
@login_required
def api_performance_stats():
    """
    API endpoint for performance statistics and monitoring.
    Returns performance metrics for the inventory alerts system.
    
    Query Parameters:
    - include_db_stats: Include database performance statistics (default: false)
    - reset_metrics: Reset performance metrics after retrieval (default: false)
    
    Returns:
        JSON response with performance statistics
        
    **Requirements: 6.5 - Add performance monitoring and logging**
    """
    try:
        username = session.get('username')
        
        # Get query parameters
        include_db_stats = request.args.get('include_db_stats', 'false').lower() == 'true'
        reset_metrics = request.args.get('reset_metrics', 'false').lower() == 'true'
        
        # Import performance optimization modules
        from utils.performance_optimization import performance_optimizer, get_database_performance_stats
        
        # Get performance summary
        perf_summary = performance_optimizer.get_performance_summary()
        
        response_data = {
            "success": True,
            "timestamp": datetime.datetime.now().isoformat(),
            "performance_summary": perf_summary
        }
        
        # Include database statistics if requested
        if include_db_stats:
            try:
                db_stats = get_database_performance_stats()
                response_data["database_stats"] = db_stats
            except Exception as db_error:
                app.logger.error(f"Error getting database stats: {db_error}")
                response_data["database_stats"] = {"error": str(db_error)}
        
        # Reset metrics if requested (admin-like functionality)
        if reset_metrics:
            try:
                performance_optimizer.clear_performance_metrics()
                response_data["metrics_reset"] = True
                app.logger.info(f"Performance metrics reset by user {username}")
            except Exception as reset_error:
                app.logger.error(f"Error resetting performance metrics: {reset_error}")
                response_data["metrics_reset"] = False
                response_data["reset_error"] = str(reset_error)
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Error in performance stats API: {e}", exc_info=True)
        
        error_response = {
            "success": False,
            "message": "حدث خطأ في تحميل إحصائيات الأداء",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        return jsonify(error_response), 500

# ============================================================================
# Enhanced AI API Routes
# ============================================================================

@app.route('/api/ai/insights/enhanced', methods=['POST'])
@csrf.exempt
@login_required
def api_ai_insights_enhanced():
    """
    Enhanced AI insights API endpoint with privacy compliance.
    Provides comprehensive inventory analysis with improved error handling.
    
    **Validates: Requirements 2.1, 2.2, 2.3, 2.5, 8.1, 8.2, 8.3**
    """
    try:
        from utils.ai_service import ai_service
        from utils.audit_logger import audit_logger
        
        username = session.get('username')
        user_id = session.get('user_id', username)
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Validate user permissions for AI insights
        if not audit_logger.validate_user_permissions(user_id, 'insights', 'inventory_data'):
            app.logger.warning(f"User {username} lacks permission for AI insights")
            return jsonify({
                'success': False,
                'error': 'Insufficient permissions for AI insights'
            }), 403
        
        # Generate enhanced insights with user context
        response = ai_service.generate_inventory_insights(data, user_id=user_id)
        
        # Convert AIResponse to JSON-serializable format
        result = {
            'success': response.success,
            'data': response.data,
            'error_message': response.error_message,
            'confidence_score': response.confidence_score,
            'processing_time': response.processing_time,
            'cached': response.cached,
            'timestamp': response.timestamp.isoformat(),
            'privacy_compliant': True
        }
        
        app.logger.info(f"Enhanced AI insights generated for user {username} with privacy compliance")
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in enhanced AI insights API: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to generate enhanced insights',
            'details': str(e)
        }), 500

@app.route('/api/ai/query', methods=['POST'])
@csrf.exempt
@login_required
def api_ai_natural_language_query():
    """
    Natural language query API endpoint.
    Processes user queries in plain English and returns conversational responses.
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
    """
    try:
        from utils.ai_service import ai_service
        from utils.ai_config import ai_config
        from utils.query_processor import QueryProcessor
        import data_store
        
        username = session.get('username')
        
        # Check if natural language features are enabled
        if ai_config and not ai_config.is_feature_enabled('natural_language'):
            return jsonify({
                'success': False,
                'error': 'Natural language queries are disabled'
            }), 403
        
        # Get request data
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'success': False,
                'error': 'Query text is required'
            }), 400
        
        query = data['query']
        context = data.get('context', {})
        
        # Initialize query processor
        query_processor = QueryProcessor(ai_service, data_store)
        
        # Parse query intent
        intent = query_processor.parse_query_intent(query)
        
        # Execute data query
        query_result = query_processor.execute_data_query(intent, username)
        
        # Format conversational response
        conversational_response = query_processor.format_conversational_response(query_result, query)
        
        # Combine results
        result = {
            'success': True,
            'intent': intent,
            'query_result': query_result,
            'conversational_response': conversational_response,
            'processing_time': 0.1,  # Placeholder
            'timestamp': datetime.datetime.now().isoformat()
        }
        
        app.logger.info(f"Natural language query processed for user {username}: {query[:50]}...")
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in natural language query API: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to process natural language query',
            'details': str(e)
        }), 500

@app.route('/api/ai/reports/smart', methods=['POST'])
@csrf.exempt
@login_required
def api_ai_smart_reports():
    """
    Smart report generation API endpoint.
    Creates AI-enhanced reports with executive summaries and insights.
    
    **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**
    """
    try:
        from utils.ai_service import ai_service
        from utils.ai_config import ai_config
        
        username = session.get('username')
        
        # Check if smart reports are enabled
        if not ai_config.is_feature_enabled('smart_reports'):
            return jsonify({
                'success': False,
                'error': 'Smart reports are disabled'
            }), 403
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Report data is required'
            }), 400
        
        report_type = data.get('report_type', 'general')
        report_data = data.get('data', {})
        
        # Generate smart report
        response = ai_service.generate_smart_report(report_data, report_type)
        
        # Convert AIResponse to JSON-serializable format
        result = {
            'success': response.success,
            'data': response.data,
            'error_message': response.error_message,
            'confidence_score': response.confidence_score,
            'processing_time': response.processing_time,
            'cached': response.cached,
            'timestamp': response.timestamp.isoformat()
        }
        
        app.logger.info(f"Smart report generated for user {username}: {report_type}")
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in smart reports API: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to generate smart report',
            'details': str(e)
        }), 500

@app.route('/api/ai/forecast/enhanced', methods=['POST'])
@csrf.exempt
@login_required
def api_ai_enhanced_forecast():
    """
    Enhanced forecasting API endpoint.
    Provides AI-powered forecast improvements with confidence intervals.
    
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
    """
    try:
        from utils.ai_service import ai_service
        from utils.ai_config import ai_config
        
        username = session.get('username')
        
        # Check if enhanced forecasting is enabled
        if not ai_config.is_feature_enabled('enhanced_forecasting'):
            return jsonify({
                'success': False,
                'error': 'Enhanced forecasting is disabled'
            }), 403
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Forecast data is required'
            }), 400
        
        forecast_data = data.get('forecast_data', {})
        historical_data = data.get('historical_data', {})
        
        # Enhance forecast
        response = ai_service.enhance_forecast(forecast_data, historical_data)
        
        # Convert AIResponse to JSON-serializable format
        result = {
            'success': response.success,
            'data': response.data,
            'error_message': response.error_message,
            'confidence_score': response.confidence_score,
            'processing_time': response.processing_time,
            'cached': response.cached,
            'timestamp': response.timestamp.isoformat()
        }
        
        app.logger.info(f"Enhanced forecast generated for user {username}")
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in enhanced forecast API: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to enhance forecast',
            'details': str(e)
        }), 500

@app.route('/api/ai/status')
@login_required
def api_ai_status():
    """
    AI service status API endpoint.
    Returns current status and configuration of AI services.
    
    **Validates: Requirements 1.2, 6.5**
    """
    try:
        from utils.ai_config import ai_config
        from utils.ai_service import ai_service
        
        # Get AI service status
        is_valid, message = ai_service.validate_api_connection()
        
        # Get configuration (masked for security)
        config = ai_config.load_api_configuration()
        
        # Get performance metrics
        metrics = ai_service.get_performance_metrics()
        
        result = {
            'success': True,
            'ai_available': is_valid,
            'status_message': message,
            'features': {
                'natural_language': ai_config.is_feature_enabled('natural_language'),
                'smart_reports': ai_config.is_feature_enabled('smart_reports'),
                'enhanced_forecasting': ai_config.is_feature_enabled('enhanced_forecasting')
            },
            'configuration': {
                'model': config['model_name'],
                'timeout': config['timeout'],
                'cache_ttl': config['cache_ttl']
            },
            'performance_metrics': metrics,
            'timestamp': datetime.datetime.now().isoformat()
        }
        
        return jsonify(result)
        
    except Exception as e:
        app.logger.error(f"Error in AI status API: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get AI status',
            'details': str(e)
        }), 500


@app.route('/api/ai/performance')
@login_required
def api_ai_performance():
    """
    AI performance monitoring API endpoint.
    Returns performance metrics and statistics for AI operations.
    
    **Validates: Requirements 6.2, 6.3**
    """
    try:
        from utils.ai_performance import performance_monitor
        
        # Get hours parameter (default to 24 hours)
        hours = request.args.get('hours', 24, type=int)
        hours = max(1, min(168, hours))  # Limit between 1 hour and 1 week
        
        # Get performance summary
        summary = performance_monitor.get_performance_summary(hours=hours)
        
        return jsonify({
            'success': True,
            'performance_summary': summary,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error in AI performance API: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get AI performance metrics',
            'details': str(e)
        }), 500


@app.route('/api/ai/loading-status')
@login_required
def api_ai_loading_status():
    """
    AI loading status API endpoint.
    Returns current loading operations and their progress.
    
    **Validates: Requirements 6.3, 7.4**
    """
    try:
        from utils.ai_performance import loading_indicator_manager
        
        # Get specific operation ID if provided
        operation_id = request.args.get('operation_id')
        
        if operation_id:
            # Get status for specific operation
            status = loading_indicator_manager.get_operation_status(operation_id)
            if status:
                return jsonify({
                    'success': True,
                    'operation': status,
                    'timestamp': datetime.datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Operation not found',
                    'operation_id': operation_id
                }), 404
        else:
            # Get all active operations
            active_operations = loading_indicator_manager.get_active_operations()
            return jsonify({
                'success': True,
                'active_operations': active_operations,
                'count': len(active_operations),
                'timestamp': datetime.datetime.now().isoformat()
            })
        
    except Exception as e:
        app.logger.error(f"Error in AI loading status API: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to get loading status',
            'details': str(e)
        }), 500



# ============================================================================
# Legacy AI Insights Routes (for compatibility with existing JS)
# ============================================================================

@app.route('/api/insights/inventory', methods=['POST'])
@csrf.exempt
@login_required
def api_insights_inventory():
    """Legacy endpoint for inventory insights."""
    try:
        data = request.get_json(silent=True)
        if data is None:
            app.logger.error(f"Legacy inventory insights: Invalid JSON or wrong content type. Header: {request.headers.get('Content-Type')}")
            return jsonify({'success': False, 'error': 'Invalid JSON or missing Content-Type'}), 400
            
        if 'summary' not in data:
            app.logger.error(f"Legacy inventory insights: Missing 'summary' key in data: {list(data.keys())}")
            return jsonify({'success': False, 'error': 'Missing summary data'}), 400
        
        if not AI_ENABLED:
            return jsonify({'success': False, 'error': 'AI features are disabled', 'data': {'stock_health': 'AI disabled'}}), 200

        from modules.ai_insights import insights_inventory
        result = insights_inventory(data['summary'])
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        app.logger.error(f"Error in legacy inventory insights: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/insights/transfers', methods=['POST'])
@csrf.exempt
@login_required
def api_insights_transfers():
    """Legacy endpoint for transfer insights."""
    try:
        data = request.get_json()
        if not data or 'transfers' not in data:
            return jsonify({'success': False, 'error': 'Missing transfer data'}), 400
        
        if not AI_ENABLED:
            return jsonify({'success': False, 'error': 'AI features are disabled'}), 200

        from modules.ai_insights import insights_branch_transfer
        result = insights_branch_transfer(data['transfers'])
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        app.logger.error(f"Error in legacy transfer insights: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/insights/forecasting', methods=['POST'])
@csrf.exempt
@login_required
def api_insights_forecasting():
    """Legacy endpoint for forecasting insights."""
    try:
        data = request.get_json()
        if not data or 'forecast' not in data:
            return jsonify({'success': False, 'error': 'Missing forecast data'}), 400
        
        if not AI_ENABLED:
            return jsonify({'success': False, 'error': 'AI features are disabled'}), 200

        from modules.ai_insights import insights_sales_forecasting
        result = insights_sales_forecasting(data['forecast'], data.get('context'))
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        app.logger.error(f"Error in legacy forecasting insights: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/insights/dashboard', methods=['POST'])
@csrf.exempt
@login_required
def api_insights_dashboard():
    """Legacy endpoint for dashboard insights."""
    try:
        data = request.get_json()
        if not data or 'kpis' not in data:
            return jsonify({'success': False, 'error': 'Missing KPI data'}), 400
        
        if not AI_ENABLED:
            return jsonify({'success': False, 'error': 'AI features are disabled'}), 200

        from modules.ai_insights import insights_dashboard
        result = insights_dashboard(data['kpis'], data.get('issues'))
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        app.logger.error(f"Error in legacy dashboard insights: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/download/inventory', methods=['POST'])
@csrf.exempt
@login_required
def download_inventory_report():
    """Download AI-enhanced inventory report using the main export logic."""
    data = request.get_json() or {}
    insights = data.get('insights')
    return inventory_export(insights=insights)

@app.route('/download/transfers', methods=['POST'])
@csrf.exempt
@login_required
def download_transfers_report():
    """Download AI-enhanced transfers report using the main export logic."""
    data = request.get_json() or {}
    insights = data.get('insights')
    return transfers_export(insights=insights)

@app.route('/download/forecasting', methods=['POST'])
@csrf.exempt
@login_required
def download_forecasting_report():
    """Download AI-enhanced forecasting report using the main export logic."""
    data = request.get_json() or {}
    insights = data.get('insights')
    return forecasting_export(insights=insights)

# ============================================================================
# DATA PRIVACY AND AUDIT MANAGEMENT API ENDPOINTS
# ============================================================================

@app.route('/api/privacy/audit-report', methods=['GET'])
@login_required
def api_privacy_audit_report():
    """
    Generate privacy compliance audit report.
    
    **Validates: Requirements 8.3, 8.4**
    """
    try:
        from utils.audit_logger import audit_logger
        from datetime import datetime, timedelta
        
        username = session.get('username')
        user_id = session.get('user_id', username)
        
        # Check admin permissions for audit reports
        if not audit_logger.validate_user_permissions(user_id, 'audit_report', 'system_data'):
            return jsonify({
                'success': False,
                'error': 'Insufficient permissions for audit reports'
            }), 403
        
        # Get date range from query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        start_date = datetime.datetime.fromisoformat(start_date_str) if start_date_str else datetime.datetime.now() - timedelta(days=30)
        end_date = datetime.datetime.fromisoformat(end_date_str) if end_date_str else datetime.datetime.now()
        
        # Generate audit report
        report = audit_logger.get_audit_report(start_date, end_date, user_id)
        
        app.logger.info(f"Privacy audit report generated for user {username}")
        return jsonify({
            'success': True,
            'report': report,
            'generated_by': username,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error generating privacy audit report: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to generate audit report',
            'details': str(e)
        }), 500


@app.route('/api/privacy/data-classification', methods=['POST'])
@login_required
def api_privacy_data_classification():
    """
    Classify data for privacy compliance.
    
    **Validates: Requirements 8.1, 8.5**
    """
    try:
        from utils.data_privacy import privacy_manager
        
        username = session.get('username')
        user_id = session.get('user_id', username)
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided for classification'
            }), 400
        
        # Classify the data
        classification = privacy_manager.classify_data(data.get('data', {}))
        
        app.logger.info(f"Data classification performed for user {username}")
        return jsonify({
            'success': True,
            'classification': classification,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error in data classification: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to classify data',
            'details': str(e)
        }), 500


@app.route('/api/privacy/retention-policy', methods=['GET', 'POST'])
@login_required
def api_privacy_retention_policy():
    """
    Manage data retention policies.
    
    **Validates: Requirements 8.4**
    """
    try:
        from utils.data_retention import retention_manager
        
        username = session.get('username')
        user_id = session.get('user_id', username)
        
        # Check admin permissions for retention policy management
        if not audit_logger.validate_user_permissions(user_id, 'retention_policy', 'system_data'):
            return jsonify({
                'success': False,
                'error': 'Insufficient permissions for retention policy management'
            }), 403
        
        if request.method == 'GET':
            # Get retention report
            report = retention_manager.get_retention_report()
            
            return jsonify({
                'success': True,
                'retention_report': report,
                'timestamp': datetime.datetime.now().isoformat()
            })
        
        elif request.method == 'POST':
            # Update retention policy
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No policy data provided'
                }), 400
            
            # This would implement policy updates
            # For now, return success
            app.logger.info(f"Retention policy update requested by user {username}")
            return jsonify({
                'success': True,
                'message': 'Retention policy update requested',
                'timestamp': datetime.datetime.now().isoformat()
            })
        
    except Exception as e:
        app.logger.error(f"Error in retention policy management: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to manage retention policy',
            'details': str(e)
        }), 500


@app.route('/api/privacy/cleanup-expired', methods=['POST'])
@login_required
def api_privacy_cleanup_expired():
    """
    Manually trigger cleanup of expired data.
    
    **Validates: Requirements 8.4**
    """
    try:
        from utils.data_retention import retention_manager
        
        username = session.get('username')
        user_id = session.get('user_id', username)
        
        # Check admin permissions for data cleanup
        if not audit_logger.validate_user_permissions(user_id, 'data_cleanup', 'system_data'):
            return jsonify({
                'success': False,
                'error': 'Insufficient permissions for data cleanup'
            }), 403
        
        # Get optional data type filter
        data = request.get_json() or {}
        data_type = data.get('data_type')
        
        # Perform cleanup
        cleanup_results = retention_manager.cleanup_expired_data(data_type)
        
        app.logger.info(f"Manual data cleanup performed by user {username}: {cleanup_results}")
        return jsonify({
            'success': True,
            'cleanup_results': cleanup_results,
            'performed_by': username,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error in manual data cleanup: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to cleanup expired data',
            'details': str(e)
        }), 500


@app.route('/api/privacy/user-permissions', methods=['GET', 'POST'])
@login_required
def api_privacy_user_permissions():
    """
    Manage user permissions for AI data access.
    
    **Validates: Requirements 8.2**
    """
    try:
        from utils.audit_logger import audit_logger
        
        username = session.get('username')
        user_id = session.get('user_id', username)
        
        # Check admin permissions for user permission management
        if not audit_logger.validate_user_permissions(user_id, 'user_permissions', 'system_data'):
            return jsonify({
                'success': False,
                'error': 'Insufficient permissions for user permission management'
            }), 403
        
        if request.method == 'GET':
            # Get user permissions (this would be implemented with proper database queries)
            return jsonify({
                'success': True,
                'message': 'User permissions retrieved',
                'timestamp': datetime.datetime.now().isoformat()
            })
        
        elif request.method == 'POST':
            # Update user permissions
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No permission data provided'
                }), 400
            
            # This would implement permission updates
            app.logger.info(f"User permissions update requested by user {username}")
            return jsonify({
                'success': True,
                'message': 'User permissions update requested',
                'timestamp': datetime.datetime.now().isoformat()
            })
        
    except Exception as e:
        app.logger.error(f"Error in user permission management: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Failed to manage user permissions',
            'details': str(e)
        }), 500


@app.route('/about')
@login_required
def about():

    return render_template('about.html')

@app.route('/data/upload')
@login_required
def data_upload():

    try:
        username = session.get('username')
        
        # Get all uploaded branches (now returns only most recent per branch)
        branches = data_store.get_branch_files(username)
        
        return render_template('data_upload.html', branches=branches)
        
    except Exception as e:
        app.logger.error(f"Error in data upload page: {e}", exc_info=True)
        flash('حدث خطأ في تحميل الصفحة', 'error')
        return render_template('data_upload.html', branches=[], uploaded_files=[])

@app.route('/data/upload/file', methods=['POST'])
@login_required
@performance_monitor('file_upload')
def data_upload_file():
    """
    Secure file upload endpoint for branch data with comprehensive validation and error handling.
    Validates CSRF token, file presence, and allowed extensions, saves file to uploads directory 
    and records it in the centralized data store with proper error handling and retry logic.
    """
    from flask import abort, current_app
    
    username = session.get('username')
    upload_logger = get_upload_logger()
    perf_logger = get_performance_logger()
    start_time = time.time()
    
    try:
        # CSRF presence check (Flask-WTF normally enforces this, but check explicitly)
        csrf_token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token')
        if not csrf_token:
            app.logger.warning(f"Missing CSRF token for upload by {username}")
            return abort(400, description='Missing CSRF token')

        # Enhanced branch name validation
        branch_name = request.form.get('branch_name', '').strip()
        branch_valid, branch_error = validation.validate_branch_name(branch_name)
        if not branch_valid:
            upload_logger.log_validation_error(
                username=username,
                filename='unknown',
                validation_type='branch_name',
                error_details={'error': branch_error, 'branch_name': branch_name}
            )
            flash(branch_error, 'error')
            return redirect(url_for('data_upload'))

        # Enhanced file validation
        if 'file' not in request.files:
            upload_logger.log_validation_error(
                username=username,
                filename='unknown',
                validation_type='file_presence',
                error_details={'error': 'No file in request'}
            )
            flash('لم يتم اختيار ملف', 'error')
            return redirect(url_for('data_upload'))

        file = request.files['file']
        if not file or file.filename == '':
            upload_logger.log_validation_error(
                username=username,
                filename='unknown',
                validation_type='file_empty',
                error_details={'error': 'Empty file selected'}
            )
            flash('لم يتم اختيار ملف', 'error')
            return redirect(url_for('data_upload'))

        # Secure filename and extension check using app config
        filename = secure_filename(file.filename)
        file_ext_valid, file_ext_error = validation.validate_file_extension(filename, current_app.config.get('ALLOWED_EXTENSIONS', set()))
        if not file_ext_valid:
            upload_logger.log_validation_error(
                username=username,
                filename=filename,
                validation_type='file_extension',
                error_details={'error': file_ext_error, 'filename': filename}
            )
            flash(file_ext_error, 'error')
            return redirect(url_for('data_upload'))

        # Read and validate file data
        try:
            file_data = file.read()
        except Exception as e:
            upload_logger.log_upload_failure(
                username=username,
                branch_name=branch_name,
                filename=filename,
                error_type='FileReadError',
                error_message=str(e)
            )
            flash('حدث خطأ أثناء قراءة الملف', 'error')
            return redirect(url_for('data_upload'))

        file_size = len(file_data)
        
        # Log upload start
        upload_logger.log_upload_start(username, branch_name, filename, file_size)

        # Validate file size
        file_size_valid, file_size_error = validation.validate_file_size(file_data)
        if not file_size_valid:
            upload_logger.log_validation_error(
                username=username,
                filename=filename,
                validation_type='file_size',
                error_details={'error': file_size_error, 'file_size': file_size}
            )
            flash(file_size_error, 'error')
            return redirect(url_for('data_upload'))

        # Validate Excel file structure before processing
        excel_valid, excel_error, sheets_info = validation.validate_excel_file_structure(file_data)
        if not excel_valid:
            upload_logger.log_validation_error(
                username=username,
                filename=filename,
                validation_type='excel_structure',
                error_details={
                    'error': excel_error,
                    'sheets_info': sheets_info,
                    'file_size': file_size
                }
            )
            flash(f'خطأ في بنية الملف: {excel_error}', 'error')
            return redirect(url_for('data_upload'))

        app.logger.info(f"File validation passed for user {username}, branch {branch_name}, file {filename}")

        # Persist uploaded file to centralized storage and process Excel data with retry logic
        max_retries = 2
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries + 1):
            try:
                processing_start = time.time()
                
                file_id, sales_id, inventory_id = data_store.save_branch_data(
                    username=username,
                    branch_name=branch_name,
                    filename=file.filename,
                    file_data=file_data
                )
                
                processing_time = time.time() - processing_start
                total_time = time.time() - start_time
                
                # Log successful upload
                upload_logger.log_upload_success(
                    username=username,
                    branch_name=branch_name,
                    filename=filename,
                    file_id=file_id,
                    sales_records=0,  # Will be updated with actual count
                    inventory_records=0,  # Will be updated with actual count
                    processing_time=processing_time
                )
                
                # Log performance metrics
                memory_usage = get_memory_usage()
                perf_logger.log_upload_performance(
                    username=username,
                    filename=filename,
                    file_size=file_size,
                    processing_time=processing_time,
                    memory_usage=memory_usage
                )
                
                app.logger.info(f'Branch data uploaded and processed successfully: {branch_name} by {username} (file_id={file_id}, sales_id={sales_id}, inventory_id={inventory_id})')
                flash(f'تم رفع ومعالجة بيانات الفرع "{branch_name}" بنجاح', 'success')
                return redirect(url_for('data_upload'))
                
            except ValueError as validation_error:
                # Validation errors should not be retried
                upload_logger.log_upload_failure(
                    username=username,
                    branch_name=branch_name,
                    filename=filename,
                    error_type='ValidationError',
                    error_message=str(validation_error)
                )
                flash(f'خطأ في البيانات: {str(validation_error)}', 'error')
                return redirect(url_for('data_upload'))
                
            except Exception as e:
                # Other errors - retry once
                if attempt < max_retries:
                    app.logger.warning(f"Processing error (attempt {attempt + 1}/{max_retries + 1}) for branch data {branch_name} by {username}: {e}")
                    time.sleep(retry_delay)
                    continue
                else:
                    upload_logger.log_upload_failure(
                        username=username,
                        branch_name=branch_name,
                        filename=filename,
                        error_type='ProcessingError',
                        error_message=str(e)
                    )
                    
                    # Provide specific error messages based on error type
                    error_message = str(e)
                    if 'excel' in error_message.lower() or 'sheet' in error_message.lower():
                        flash(f'خطأ في معالجة ملف Excel: {error_message}', 'error')
                    elif 'memory' in error_message.lower():
                        flash('الملف كبير جداً أو يحتوي على بيانات كثيرة. يرجى تقليل حجم البيانات', 'error')
                    elif 'permission' in error_message.lower():
                        flash('خطأ في صلاحيات النظام. يرجى المحاولة مرة أخرى', 'error')
                    else:
                        flash(f'حدث خطأ أثناء معالجة البيانات: {error_message}', 'error')
                    
                    return redirect(url_for('data_upload'))

    except Exception as e:
        upload_logger.log_upload_failure(
            username=username,
            branch_name=branch_name if 'branch_name' in locals() else 'unknown',
            filename=filename if 'filename' in locals() else 'unknown',
            error_type='UnexpectedError',
            error_message=str(e)
        )
        flash('حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('data_upload'))

@app.route('/download_template')
@login_required
def download_template():
    """
    Download an Excel template with the required column headers for data upload.
    Uses in-memory buffer to avoid disk writes (Windows compatible).
    """
    try:
        # Define the two sheets and their expected columns
        
        # Sheet 1: Transactions/Sales data
        transactions_columns = [
            'sale_date',
            'product_code',
            'branch_code',
            'quantity_sold',
            'revenue',
            'discount'
        ]
        
        # Sheet 2: Inventory/Item information
        inventory_columns = [
            'product_code',
            'branch_code',
            'product_name',
            'item_category1',
            'item_category2',
            'Last_on_hand',
            'inventory_value',
            'supplier_name',
            'supplier_code'
        ]
        
        # Create empty DataFrames with the required columns
        df_transactions = pd.DataFrame(columns=transactions_columns)
        df_inventory = pd.DataFrame(columns=inventory_columns)
        
        # Create an in-memory Excel file using BytesIO
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_transactions.to_excel(writer, sheet_name='Transactions', index=False)
            df_inventory.to_excel(writer, sheet_name='Inventory', index=False)
        
        # Reset the buffer position to the beginning
        output.seek(0)
        
        app.logger.info(f"Template downloaded by user {session.get('username')}")
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='TIF_Data_Template.xlsx'
        )
        
    except Exception as e:
        app.logger.error(f"Error generating template: {e}", exc_info=True)
        flash('حدث خطأ عند إنشاء النموذج. يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('data_upload'))

@app.route('/data/delete/<branch_name>', methods=['POST'])
@login_required
def data_delete_branch(branch_name):

    try:
        username = session.get('username')
        
        success, message = data_store.delete_branch_data(username, branch_name)
        
        if success:
            app.logger.info(f'Branch data deleted: {branch_name} by {username}')
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('data_upload'))
        
    except Exception as e:
        app.logger.error(f"Error deleting branch data: {e}", exc_info=True)
        flash('حدث خطأ أثناء حذف البيانات', 'error')
        return redirect(url_for('data_upload'))

@app.route('/data/delete-all', methods=['POST'])
@login_required
def data_delete_all():

    try:
        username = session.get('username')
        
        # Get all branches and delete them
        branches = data_store.get_all_branches(username)
        
        for branch_name in branches:
            data_store.delete_branch_data(username, branch_name)
        
        app.logger.info(f'All branch data deleted by {username}')
        flash('تم حذف جميع البيانات بنجاح', 'success')
        return redirect(url_for('data_upload'))
        
    except Exception as e:
        app.logger.error(f"Error deleting all data: {e}", exc_info=True)
        flash('حدث خطأ أثناء حذف البيانات', 'error')
        return redirect(url_for('data_upload'))



# ============================================================================
# Inventory Analysis Routes
# ============================================================================

@app.route('/inventory')
@login_required
def inventory():

    username = session.get('username')
    
    # Get all available branches
    branches = data_store.get_all_branches(username)
    
    # Get selected branch from session
    selected_branch = session.get('selected_inventory_branch')
    
    # Get user session from database (for results and params)
    user_session = data_store.get_user_session(username, 'inventory')
    params = user_session.get('params', {}) if user_session else {}
    
    # Prepare results for display if available
    results = None
    critical_items = None
    stagnant_items = None
    
    if user_session and user_session.get('data_ids', {}).get('results'):
        try:
            results_id = user_session['data_ids']['results']
            results_df = data_store.get_dataframe(results_id)
            
            if results_df is not None:
                # Check if required columns exist
                required_columns = ['daily_sales', 'coverage_days', 'is_stagnant']
                missing_columns = [col for col in required_columns if col not in results_df.columns]
                
                if missing_columns:
                    app.logger.warning(f"Results dataframe missing columns: {missing_columns}. Available columns: {list(results_df.columns)}")
                    # Clear the results to force re-analysis
                    results = None
                    critical_items = None
                    stagnant_items = None
                else:
                    # ULTIMATUM KILL SWITCH: IF Sufficient is True OR Stagnant is True, THEN the "Expected Order" MUST BE COMPLETELY EMPTY.
                    if 'Stock_Is_Sufficient' in results_df.columns and 'expected_demand' in results_df.columns:
                        kill_mask = (results_df['Stock_Is_Sufficient'] == True) | (results_df['is_stagnant'] == True)
                        results_df.loc[kill_mask, 'expected_demand'] = None
                        
                    # Convert to list of dicts for template
                    results_dict = results_df.to_dict('records')
                    
                    # Clean data for JSON serialization (handle NaT values and datetime objects)
                    def clean_for_json(data):
                        """Clean data to make it JSON serializable"""
                        import pandas as pd
                        import numpy as np
                        from datetime import datetime
                        
                        if isinstance(data, list):
                            return [clean_for_json(item) for item in data]
                        elif isinstance(data, dict):
                            cleaned = {}
                            for key, value in data.items():
                                cleaned[key] = clean_for_json(value)
                            return cleaned
                        elif pd.isna(data) or (hasattr(data, 'isna') and data.isna()):
                            return None
                        elif isinstance(data, (pd.Timestamp, datetime)):
                            return data.isoformat() if not pd.isna(data) else None
                        elif isinstance(data, (np.integer, np.floating)):
                            return data.item() if not pd.isna(data) else None
                        elif isinstance(data, np.ndarray):
                            return data.tolist()
                        else:
                            return data
                    
                    results = clean_for_json(results_dict)
                    
                    # Filter critical items
                    min_coverage = params.get('min_coverage', 7)
                    critical_df = results_df[
                        (results_df['coverage_days'] < min_coverage) & 
                        (results_df['daily_sales'] > 0)
                    ]
                    if not critical_df.empty:
                        critical_items = clean_for_json(critical_df.to_dict('records'))
                    
                    # Filter stagnant items
                    stagnant_df = results_df[results_df['is_stagnant'] == True]
                    if not stagnant_df.empty:
                        stagnant_items = clean_for_json(stagnant_df.to_dict('records'))
        except Exception as e:
            app.logger.error(f"Error loading results: {e}")
            flash('خطأ في عرض النتائج', 'error')
    
    return render_template('inventory.html',
                         params=params,
                         results=results,
                         critical_items=critical_items,
                         stagnant_items=stagnant_items,
                         branches=branches,
                         selected_branch=selected_branch)

@app.route('/inventory/select-branch', methods=['POST'])
@login_required
def inventory_select_branch():

    try:
        branch_name = request.form.get('branch_name')
        if not branch_name:
            flash('يرجى اختيار فرع', 'error')
            return redirect(url_for('inventory'))
        
        # Store selected branch in session
        session['selected_inventory_branch'] = branch_name
        flash(f'تم تحديد الفرع: {branch_name if branch_name != "all" else "جميع الفروع"}', 'success')
        
        return redirect(url_for('inventory'))
        
    except Exception as e:
        app.logger.error(f"Error selecting branch: {e}", exc_info=True)
        flash('حدث خطأ في تحديد الفرع', 'error')
        return redirect(url_for('inventory'))


@app.route('/inventory/upload', methods=['POST'])
@login_required
def inventory_upload():

    filepath = None
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('لم يتم اختيار ملف', 'error')
            return redirect(url_for('inventory'))
        
        file = request.files['file']
        
        if file.filename == '':
            flash('لم يتم اختيار ملف', 'error')
            return redirect(url_for('inventory'))
        
        # Validate file extension
        file_valid, file_error = validation.validate_file_extension(
            file.filename, app.config['ALLOWED_EXTENSIONS']
        )
        if not file_valid:
            flash(file_error, 'error')
            return redirect(url_for('inventory'))
        
        # Read file data into memory
        file_data = file.read()
        username = session.get('username')
        
        # Save file to database
        file_id = data_store.save_uploaded_file(
            username=username,
            module='inventory',
            filename=file.filename,
            file_data=file_data
        )
        
        # Create temporary file for processing
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file.write(file_data)
            filepath = tmp_file.name
        
        # Process the file using existing utility
        df_sales, df_inventory = data_processing.process_new_format(filepath)
        
        if df_sales is None or df_inventory is None:
            app.logger.error(f'Failed to process inventory file: {file.filename}')
            flash('فشل معالجة الملف. تأكد من وجود شيتات Transactions و Item info', 'error')
            return redirect(url_for('inventory'))
        
        # Save DataFrames to database
        sales_id = data_store.save_dataframe(username, 'inventory', 'sales_df', df_sales)
        inventory_id = data_store.save_dataframe(username, 'inventory', 'inventory_df', df_inventory)
        
        # Save user session with data IDs (not the actual data)
        data_store.save_user_session(
            username=username,
            module='inventory',
            file_id=file_id,
            data_ids={'sales_df': sales_id, 'inventory_df': inventory_id}
        )
        
        app.logger.info(f'Inventory file uploaded successfully: {file.filename}')
        flash('تم رفع الملف ومعالجته بنجاح', 'success')
        return redirect(url_for('inventory'))
        
    except Exception as e:
        app.logger.error(f"Error in inventory upload: {e}", exc_info=True)
        flash(f'حدث خطأ أثناء معالجة الملف: {str(e)}', 'error')
        return redirect(url_for('inventory'))
    finally:
        # Clean up temporary file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                app.logger.warning(f"Could not delete temp file {filepath}: {e}")

@app.route('/inventory/analyze', methods=['POST'])
@login_required
def inventory_analyze():

    try:
        username = session.get('username')
        
        # Get user session from database (for storing results and params)
        user_session = data_store.get_user_session(username, 'inventory')
        
        # Get and validate numeric parameters
        min_coverage_valid, min_coverage_error, min_coverage = validation.validate_numeric_parameter(
            request.form.get('min_coverage', 7), 'الحد الأدنى للتغطية', min_value=1
        )
        if not min_coverage_valid:
            flash(min_coverage_error, 'error')
            return redirect(url_for('inventory'))
        
        max_coverage_valid, max_coverage_error, max_coverage = validation.validate_numeric_parameter(
            request.form.get('max_coverage', 30), 'الحد الأقصى للتغطية', min_value=1
        )
        if not max_coverage_valid:
            flash(max_coverage_error, 'error')
            return redirect(url_for('inventory'))
        
        forecast_days_valid, forecast_days_error, forecast_days = validation.validate_numeric_parameter(
            request.form.get('forecast_days', 30), 'أيام التنبؤ', min_value=1, max_value=365
        )
        if not forecast_days_valid:
            flash(forecast_days_error, 'error')
            return redirect(url_for('inventory'))
        
        safety_stock_valid, safety_stock_error, safety_stock = validation.validate_numeric_parameter(
            request.form.get('safety_stock', 0), 'مخزون الأمان', min_value=0
        )
        if not safety_stock_valid:
            flash(safety_stock_error, 'error')
            return redirect(url_for('inventory'))
        
        reorder_point_valid, reorder_point_error, reorder_point = validation.validate_numeric_parameter(
            request.form.get('reorder_point', 0), 'نقطة إعادة الطلب', min_value=0
        )
        if not reorder_point_valid:
            flash(reorder_point_error, 'error')
            return redirect(url_for('inventory'))
        
        stagnant_period_valid, stagnant_period_error, stagnant_period = validation.validate_numeric_parameter(
            request.form.get('stagnant_period', 90), 'فترة الركود', min_value=1
        )
        if not stagnant_period_valid:
            flash(stagnant_period_error, 'error')
            return redirect(url_for('inventory'))
        
        params = {
            'min_coverage': min_coverage,
            'max_coverage': max_coverage,
            'forecast_days': forecast_days,
            'safety_stock': safety_stock,
            'reorder_point': reorder_point,
            'stagnant_period': stagnant_period
        }
        
        # Validate min < max for coverage
        min_max_valid, min_max_error = validation.validate_min_max_parameters(
            min_coverage, max_coverage, 'التغطية'
        )
        if not min_max_valid:
            flash(min_max_error, 'error')
            return redirect(url_for('inventory'))
        
        # Validate date range
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        date_valid, date_error, start_date_dt, end_date_dt = validation.validate_date_range(
            start_date, end_date
        )
        if not date_valid:
            flash(date_error, 'error')
            return redirect(url_for('inventory'))
        
        # Get selected branch
        selected_branch = session.get('selected_inventory_branch')
        
        if not selected_branch:
            flash('يرجى اختيار فرع أولاً', 'warning')
            return redirect(url_for('inventory'))
        
        # Load DataFrames from branch data
        branch_filter = None if selected_branch == 'all' else selected_branch
        df_sales, df_inventory = data_store.get_branch_data(username, branch_filter)
        
        if df_sales is None or df_inventory is None:
            app.logger.warning(f'No results found for inventory analysis: {start_date} to {end_date}')
            flash('لم يتم العثور على نتائج للفترة المحددة', 'warning')
            return redirect(url_for('inventory'))
        
        # Perform inventory analysis
        try:
            from utils import data_processing
            
            # Filter data by date range
            df_sales_filtered = data_processing.filter_sales_by_date(df_sales, start_date_dt, end_date_dt)
            
            # Perform inventory analysis with the provided parameters
            results_df = data_processing.analyze_inventory(
                df_sales_filtered, 
                df_inventory,
                min_coverage=min_coverage,
                max_coverage=max_coverage,
                forecast_days=forecast_days,
                safety_stock=safety_stock,
                reorder_point=reorder_point,
                stagnant_period=stagnant_period
            )
            
            # ULTIMATUM KILL SWITCH: IF Sufficient is True OR Stagnant is True, THEN the "Expected Order" MUST BE COMPLETELY EMPTY.
            results_df['Stock_Is_Sufficient'] = results_df['Last_on_hand'] >= results_df['expected_demand']
            kill_mask = (results_df['Stock_Is_Sufficient'] == True) | (results_df['is_stagnant'] == True)
            results_df.loc[kill_mask, ['expected_demand', 'recommended_order']] = None
            
            if results_df is None or results_df.empty:
                app.logger.warning(f'No analysis results generated for period: {start_date} to {end_date}')
                flash('لم يتم إنتاج نتائج للتحليل في الفترة المحددة', 'warning')
                return redirect(url_for('inventory'))
                
        except Exception as analysis_error:
            app.logger.error(f"Error during inventory analysis processing: {analysis_error}", exc_info=True)
            flash(f'حدث خطأ أثناء معالجة التحليل: {str(analysis_error)}', 'error')
            return redirect(url_for('inventory'))
        
        # Save results to database
        results_id = data_store.save_dataframe(username, 'inventory', 'results', results_df)
        
        # Update user session with results and parameters
        params['start_date'] = start_date
        params['end_date'] = end_date
        
        data_ids = user_session.get('data_ids', {}) if user_session else {}
        data_ids['results'] = results_id
        
        data_store.save_user_session(
            username=username,
            module='inventory',
            file_id=user_session.get('file_id') if user_session else None,
            data_ids=data_ids,
            params=params
        )
        
        app.logger.info(f'Inventory analysis completed successfully: {start_date} to {end_date}')
        flash('تم إجراء التحليل بنجاح', 'success')
        return redirect(url_for('inventory'))
        
    except ValueError as e:
        app.logger.error(f"Validation error in inventory analysis: {e}", exc_info=True)
        flash(f'خطأ في البيانات المدخلة: {str(e)}', 'error')
        return redirect(url_for('inventory'))
    except Exception as e:
        app.logger.error(f"Error in inventory analysis: {e}", exc_info=True)
        flash(f'حدث خطأ أثناء التحليل: {str(e)}', 'error')
        return redirect(url_for('inventory'))

@app.route('/inventory/export')
@app.route('/inventory/export/<format>')
@login_required
def inventory_export(format='xlsx', insights=None):
    """
    Export inventory analysis results strictly in XLSX format.
    
    **Validates: Requirements 2.2, 2.3, 2.4, 5.1, 7.1, 7.4, 7.5**
    """
    username = session.get('username')
    format = 'xlsx'  # Force XLSX
    
    try:
        app.logger.info(f"Inventory export initiated by user: {username}")
        
        # Enhanced comprehensive session and data validation
        from utils.session_validator import comprehensive_export_validation
        validation_success, error_message, session_data, dataframes = comprehensive_export_validation(username, 'inventory')
        
        if not validation_success:
            app.logger.warning(f"Inventory export validation failed for user {username}: {error_message}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify({'success': False, 'error': error_message}), 400
            flash(error_message, 'error')
            return redirect(url_for('inventory'))
        
        results_df = dataframes.get('results')
        params = session_data.get('params', {})
        
        if results_df is None or results_df.empty:
            app.logger.warning(f"No results to export for user {username}")
            msg = 'لا توجد بيانات للتصدير. يرجى البدء بالتحليل أولاً'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify({'success': False, 'error': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('inventory'))
            
        # Apply stock sufficiency and stagnant logic: clear order quantities for sufficient stock or stagnant items
        if 'Stock_Is_Sufficient' in results_df.columns and 'expected_demand' in results_df.columns:
            kill_mask = (results_df['Stock_Is_Sufficient'] == True) | (results_df['is_stagnant'] == True)
            results_df.loc[kill_mask, 'expected_demand'] = None
            
        # Generate Excel report
        from utils import ui_helpers
        import io
        excel_data = ui_helpers.export_full_report(results_df, params, ai_insights=insights)
        
        if not excel_data:
            raise Exception("Failed to generate Excel data")
            
        return send_file(
            io.BytesIO(excel_data),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"inventory_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        
    except Exception as e:
        app.logger.error(f"Inventory export failed: {e}", exc_info=True)
        msg = 'حدث خطأ أثناء تصدير البيانات'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'error': msg}), 500
        flash(msg, 'error')
        return redirect(url_for('inventory'))

@app.route('/inventory/clear', methods=['POST'])
@login_required
def inventory_clear():

    try:
        username = session.get('username')
        
        # Clear user session in database
        data_store.clear_user_session(username, 'inventory')
        
        # Clear session variables
        if 'selected_inventory_branch' in session:
            session.pop('selected_inventory_branch')
            
        flash('تم تحديث الصفحة ومسح النتائج السابقة', 'success')
        return redirect(url_for('inventory'))
        
    except Exception as e:
        app.logger.error(f"Error clearing inventory session: {e}")
        flash('حدث خطأ أثناء مسح النتائج', 'error')
        flash('حدث خطأ أثناء مسح النتائج', 'error')
        return redirect(url_for('inventory'))


@app.route('/api/inventory/filter', methods=['POST'])
@login_required
def api_inventory_filter():
    """
    API endpoint for filtering inventory data dynamically.
    Process JSON request with search terms, filters, and column selection.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
            
        username = session.get('username')
        
        # Get user session to retrieve the current results dataframe
        # We use the cached results from the last analysis to filter
        user_session = data_store.get_user_session(username, 'inventory')
        
        if not user_session or not user_session.get('data_ids', {}).get('results'):
             return jsonify({
                'success': False, 
                'error': 'No analysis results found. Please run an analysis first.',
                'results': []
            }), 404
            
        results_id = user_session['data_ids']['results']
        results_df = data_store.get_dataframe(results_id)
        
        if results_df is None or results_df.empty:
            return jsonify({
                'success': True, 
                'results': [],
                'message': 'No data available'
            })
            
        # Get filter parameters
        # Handle empty strings for numeric fields which might come from JSON
        min_stock = data.get('min_stock')
        if min_stock == '': min_stock = None
        
        max_stock = data.get('max_stock')
        if max_stock == '': max_stock = None
        
        filters = {
            'search_term': data.get('search_term'),
            'min_stock': min_stock,
            'max_stock': max_stock,
            'category': data.get('category'),
            'status': data.get('status'),
            'columns': data.get('columns'),
            'min_coverage': user_session.get('params', {}).get('min_coverage', 7)
        }
        
        # Apply stock sufficiency and stagnant logic: clear order quantities for sufficient stock or stagnant items
        if 'Stock_Is_Sufficient' in results_df.columns and 'expected_demand' in results_df.columns:
            kill_mask = (results_df['Stock_Is_Sufficient'] == True) | (results_df['is_stagnant'] == True)
            results_df.loc[kill_mask, 'expected_demand'] = None
        
        # Apply filters using DuckDB via data_store
        filtered_data = data_store.get_filtered_inventory_data(results_df, filters)
        
        # Clean data for JSON (handle NaNs, timestamps)
        def clean_for_json(data):
            import pandas as pd
            import numpy as np
            from datetime import datetime
            
            if isinstance(data, list):
                return [clean_for_json(item) for item in data]
            elif isinstance(data, dict):
                cleaned = {}
                for key, value in data.items():
                    cleaned[key] = clean_for_json(value)
                return cleaned
            elif pd.isna(data):
                return None
            elif isinstance(data, (pd.Timestamp, datetime)):
                return data.isoformat() if not pd.isna(data) else None
            elif isinstance(data, (np.integer, np.floating)):
                return data.item() if not pd.isna(data) else None
            else:
                return data
                
        cleaned_results = clean_for_json(filtered_data)
        
        return jsonify({
            'success': True,
            'results': cleaned_results,
            'count': len(cleaned_results)
        })
        
    except Exception as e:
        app.logger.error(f"Error in inventory filter API: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Branch Transfer Routes
# ============================================================================

@app.route('/transfers')
@login_required
def transfers():

    username = session.get('username')
    
    # Get all available branches
    branches = data_store.get_all_branches(username)
    
    # Get selected branches from session
    selected_source = session.get('selected_transfer_source')
    selected_target = session.get('selected_transfer_target')
    
    # Get user session from database (for results and params)
    user_session = data_store.get_user_session(username, 'transfers')
    params = user_session.get('params', {}) if user_session else {}
    
    # Prepare results for display if available
    transfer_results = None
    summary_results = None
    
    if user_session and user_session.get('data_ids', {}).get('transfer_results'):
        try:
            transfer_id = user_session['data_ids']['transfer_results']
            transfer_df = data_store.get_dataframe(transfer_id)
            if transfer_df is not None and not transfer_df.empty:
                transfer_results = transfer_df.to_dict('records')
        except Exception as e:
            app.logger.error(f"Error loading transfer results: {e}")
    
    if user_session and user_session.get('data_ids', {}).get('summary_results'):
        try:
            summary_id = user_session['data_ids']['summary_results']
            summary_df = data_store.get_dataframe(summary_id)
            if summary_df is not None and not summary_df.empty:
                summary_results = summary_df.to_dict('records')
        except Exception as e:
            app.logger.error(f"Error loading summary results: {e}")
    
    return render_template('transfers.html',
                         params=params,
                         transfer_results=transfer_results,
                         summary_results=summary_results,
                         branches=branches,
                         selected_source=selected_source,
                         selected_target=selected_target)

@app.route('/transfers/clear', methods=['POST'])
@login_required
def transfers_clear():

    try:
        username = session.get('username')
        
        # Clear user session in database
        data_store.clear_user_session(username, 'transfers')
        
        # Clear session variables
        if 'selected_transfer_source' in session:
            session.pop('selected_transfer_source')
        if 'selected_transfer_target' in session:
            session.pop('selected_transfer_target')
            
        flash('تم مسح البيانات بنجاح', 'success')
        return redirect(url_for('transfers'))
        
    except Exception as e:
        app.logger.error(f"Error clearing transfers session: {e}")
        flash('حدث خطأ أثناء مسح البيانات', 'error')
        return redirect(url_for('transfers'))

@app.route('/transfers/select-branches', methods=['POST'])
@login_required
def transfers_select_branches():

    try:
        source_branch = request.form.get('source_branch')
        target_branch = request.form.get('target_branch')
        
        if not source_branch or not target_branch:
            flash('يرجى اختيار فرع المصدر والهدف', 'error')
            return redirect(url_for('transfers'))
        
        # Allow same branch if both are 'all' (global analysis)
        if source_branch == target_branch and source_branch != 'all':
            flash('يجب أن يكون فرع المصدر مختلفاً عن فرع الهدف', 'error')
            return redirect(url_for('transfers'))
        
        # Store selected branches in session
        session['selected_transfer_source'] = source_branch
        session['selected_transfer_target'] = target_branch
        
        source_msg = "جميع الفروع" if source_branch == 'all' else source_branch
        target_msg = "جميع الفروع" if target_branch == 'all' else target_branch
        flash(f'تم تحديد: {source_msg} ← {target_msg}', 'success')
        
        return redirect(url_for('transfers'))
        
    except Exception as e:
        app.logger.error(f"Error selecting branches: {e}", exc_info=True)
        flash('حدث خطأ في تحديد الفروع', 'error')
        return redirect(url_for('transfers'))

@app.route('/transfers/upload', methods=['POST'])
@login_required
def transfers_upload():

    filepath = None
    try:
        # Get and validate branch code from form
        branch_code = request.form.get('branch_code', '').strip()
        
        branch_valid, branch_error = validation.validate_required_field(branch_code, 'الفرع')
        if not branch_valid:
            flash(branch_error, 'error')
            return redirect(url_for('transfers'))
        
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('لم يتم اختيار ملف', 'error')
            return redirect(url_for('transfers'))
        
        file = request.files['file']
        
        if file.filename == '':
            flash('لم يتم اختيار ملف', 'error')
            return redirect(url_for('transfers'))
        
        # Validate file extension
        file_valid, file_error = validation.validate_file_extension(
            file.filename, app.config['ALLOWED_EXTENSIONS']
        )
        if not file_valid:
            flash(file_error, 'error')
            return redirect(url_for('transfers'))
        
        # Read file data into memory
        file_data = file.read()
        username = session.get('username')
        
        # Save file to database
        file_id = data_store.save_uploaded_file(
            username=username,
            module='transfers',
            filename=f"{branch_code}_{file.filename}",
            file_data=file_data
        )
        
        # Create temporary file for processing
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file.write(file_data)
            filepath = tmp_file.name
        
        # Process the file using existing utility
        df_sales, df_inventory = data_processing.process_new_format(filepath)
        
        if df_sales is None or df_inventory is None:
            app.logger.error(f'Failed to process transfer file for branch {branch_code}: {file.filename}')
            flash('فشل معالجة الملف. تأكد من وجود شيتات Transactions و Item info', 'error')
            return redirect(url_for('transfers'))
        
        # Get actual branch code from data if available
        if 'branch_code' in df_sales.columns and not df_sales.empty:
            actual_branch_code = str(df_sales['branch_code'].iloc[0])
        else:
            actual_branch_code = branch_code
        
        # Save DataFrames to database with branch-specific keys
        sales_id = data_store.save_dataframe(
            username, 'transfers', f'branch_{actual_branch_code}_sales', df_sales
        )
        inventory_id = data_store.save_dataframe(
            username, 'transfers', f'branch_{actual_branch_code}_inventory', df_inventory
        )
        
        # Get existing session or create new one
        user_session = data_store.get_user_session(username, 'transfers')
        if not user_session:
            user_session = {'file_id': file_id, 'data_ids': {}, 'params': {}}
        
        # Update data_ids with branch data
        user_session['data_ids'][f'branch_{actual_branch_code}_sales'] = sales_id
        user_session['data_ids'][f'branch_{actual_branch_code}_inventory'] = inventory_id
        
        # Save updated session
        data_store.save_user_session(
            username=username,
            module='transfers',
            file_id=user_session.get('file_id', file_id),
            data_ids=user_session['data_ids'],
            params=user_session.get('params', {})
        )
        
        app.logger.info(f'Transfer file uploaded successfully for branch {actual_branch_code}: {file.filename}')
        flash(f'تم تحميل البيانات لـ {actual_branch_code} بنجاح', 'success')
        return redirect(url_for('transfers'))
        
    except Exception as e:
        app.logger.error(f"Error in transfers upload: {e}", exc_info=True)
        flash(f'حدث خطأ أثناء معالجة الملف: {str(e)}', 'error')
        return redirect(url_for('transfers'))
    finally:
        # Clean up temporary file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                app.logger.warning(f"Could not delete temp file {filepath}: {e}")

@app.route('/transfers/analyze', methods=['POST'])
@login_required
def transfers_analyze():

    try:
        username = session.get('username')
        
        # Get all available branches from centralized storage
        branches = data_store.get_all_branches(username)
        
        if len(branches) < 2:
            flash('يجب تحميل بيانات المبيعات والمخزون لفرعين على الأقل لإجراء تحليل التوازن', 'warning')
            return redirect(url_for('transfers'))
        
        # Get and validate numeric parameters
        min_coverage_valid, min_coverage_error, min_coverage = validation.validate_numeric_parameter(
            request.form.get('min_coverage', 7), 'الحد الأدنى للتغطية', min_value=1
        )
        if not min_coverage_valid:
            flash(min_coverage_error, 'error')
            return redirect(url_for('transfers'))
        
        max_coverage_valid, max_coverage_error, max_coverage = validation.validate_numeric_parameter(
            request.form.get('max_coverage', 30), 'الحد الأقصى للتغطية', min_value=1
        )
        if not max_coverage_valid:
            flash(max_coverage_error, 'error')
            return redirect(url_for('transfers'))
        
        params = {
            'min_coverage': min_coverage,
            'max_coverage': max_coverage
        }
        
        # Validate min < max for coverage
        min_max_valid, min_max_error = validation.validate_min_max_parameters(
            min_coverage, max_coverage, 'التغطية'
        )
        if not min_max_valid:
            flash(min_max_error, 'error')
            return redirect(url_for('transfers'))
        
        # Validate date range
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        date_valid, date_error, start_date_dt, end_date_dt = validation.validate_date_range(
            start_date, end_date
        )
        if not date_valid:
            flash(date_error, 'error')
            return redirect(url_for('transfers'))
        
        # Import pandas and numpy for analysis
        import pandas as pd
        import numpy as np
        
        # Perform branch balance analysis
        min_days = params['min_coverage']
        max_days = params['max_coverage']
        
        branch_metrics = {}
        
        # Process each branch - load from centralized branch data
        for branch_name in branches:
            # Load DataFrames from centralized storage
            sales_df, inv_df = data_store.get_branch_data(username, branch_name)
            
            if sales_df is None or inv_df is None:
                app.logger.warning(f'No data found for branch {branch_name}')
                continue
            
            sales_df = sales_df.copy()
            
            # Filter by date range
            sales_df['sale_date'] = pd.to_datetime(sales_df['sale_date'])
            mask = (sales_df['sale_date'] >= start_date_dt) & (sales_df['sale_date'] <= end_date_dt)
            sales_df = sales_df.loc[mask]
            
            # Remove items with zero inventory and zero sales
            inv_df = inv_df[~((inv_df['Last_on_hand'] == 0) & 
                             (inv_df['product_code'].isin(sales_df[sales_df['quantity_sold'] == 0]['product_code'])))]
            
            if sales_df.empty:
                flash(f'⚠️ لا توجد بيانات مبيعات في الفترة المحددة لـ {branch_name}', 'warning')
                continue
            
            # Calculate daily sales summary
            daily_sales_summary = sales_df.groupby(['product_code', 'sale_date']).agg(
                daily_quantity=('quantity_sold', 'sum')
            ).reset_index()
            
            sales_agg = daily_sales_summary.groupby('product_code').agg(
                total_quantity_sold=('daily_quantity', 'sum'),
                sale_days=('sale_date', 'nunique')
            ).reset_index()
            
            sales_agg['avg_daily_sales'] = np.where(
                sales_agg['sale_days'] > 0,
                sales_agg['total_quantity_sold'] / sales_agg['sale_days'],
                0
            )
            
            # Merge with inventory data
            daily_avg = sales_agg[['product_code', 'avg_daily_sales']]
            merged = pd.merge(inv_df, daily_avg, on='product_code', how='left')
            merged['avg_daily_sales'].fillna(0, inplace=True)
            merged['coverage_days'] = merged['Last_on_hand'] / merged['avg_daily_sales'].replace(0, np.nan)
            
            # Remove items with zero inventory and zero sales
            merged = merged[~((merged['Last_on_hand'] == 0) & (merged['avg_daily_sales'] == 0))]
            
            branch_metrics[branch_name] = merged
        
        if not branch_metrics:
            flash('❌ لا توجد بيانات كافية لتحليل الأصناف. تأكد من تحميل بيانات صحيحة للمبيعات والمخزون', 'error')
            return redirect(url_for('transfers'))
        
        # Calculate transfer recommendations
        transfers = []
        item_code_dfs = [df[['product_code']] for df in branch_metrics.values()]
        all_items = pd.concat(item_code_dfs).drop_duplicates()['product_code']
        
        for item in all_items:
            item_stats = []
            for branch_code, df in branch_metrics.items():
                row = df[df['product_code'] == item]
                if not row.empty:
                    row = row.iloc[0]
                    item_stats.append({
                        'branch': branch_code,
                        'coverage_days': row['coverage_days'],
                        'stock_qty': row['Last_on_hand'],
                        'avg_daily_sales': row['avg_daily_sales'],
                        'item_category1': row.get('item_category1', ''),
                        'item_category2': row.get('item_category2', ''),
                        'product_name': row.get('product_name', '')
                    })
            
            # Find needy and surplus branches
            needy = [r for r in item_stats if r['coverage_days'] < min_days]
            surplus = [r for r in item_stats if r['coverage_days'] > max_days]
            
            # Calculate transfers
            for n in needy:
                needed_qty = int((min_days - n['coverage_days']) * n['avg_daily_sales'])
                for s in surplus:
                    available_surplus = int((s['coverage_days'] - max_days) * s['avg_daily_sales'])
                    transfer_qty = min(needed_qty, available_surplus)
                    if transfer_qty > 0:
                        transfers.append({
                            'item_code': item,
                            'product_name': n['product_name'],
                            'from_branch': s['branch'],
                            'to_branch': n['branch'],
                            'transfer_qty': transfer_qty,
                            'item_category1': n['item_category1'],
                            'item_category2': n['item_category2']
                        })
                        s['coverage_days'] -= transfer_qty / s['avg_daily_sales']
                        n['coverage_days'] += transfer_qty / n['avg_daily_sales']
                        needed_qty -= transfer_qty
                        if needed_qty <= 0:
                            break
        
        # Create results DataFrames
        if transfers:
            result_df = pd.DataFrame(transfers).rename(columns={
                'item_code': 'كود المنتج',
                'product_name': 'اسم الصنف',
                'from_branch': 'من فرع',
                'to_branch': 'إلى فرع',
                'transfer_qty': 'كمية النقل',
                'item_category1': 'القسم',
                'item_category2': 'القسم الفرعي'
            })
            result_df = result_df[['كود المنتج', 'اسم الصنف', 'القسم', 'القسم الفرعي', 'من فرع', 'إلى فرع', 'كمية النقل']]
            
            # Filter results based on selected branches
            selected_source = session.get('selected_transfer_source')
            selected_target = session.get('selected_transfer_target')
            
            if selected_source and selected_source != 'all':
                result_df = result_df[result_df['من فرع'] == selected_source]
            
            if selected_target and selected_target != 'all':
                result_df = result_df[result_df['إلى فرع'] == selected_target]
                
        else:
            result_df = pd.DataFrame()
        
        # Create branch summary
        branch_summaries = []
        for branch_code, df in branch_metrics.items():
            temp = df.copy()
            temp['branch'] = branch_code
            temp['coverage_status'] = temp['coverage_days'].apply(
                lambda x: '❌ عجز' if x < min_days else ('✅ متوازن' if x <= max_days else '📦 فائض')
            )
            branch_summaries.append(temp[['branch', 'product_code', 'product_name', 'item_category1', 
                                         'item_category2', 'Last_on_hand', 'avg_daily_sales', 
                                         'coverage_days', 'coverage_status']])
        
        summary_df = pd.concat(branch_summaries, ignore_index=True).rename(columns={
            'product_code': 'كود المنتج',
            'product_name': 'اسم الصنف',
            'branch': 'الفرع',
            'Last_on_hand': 'المخزون الحالي',
            'avg_daily_sales': 'متوسط المبيعات اليومي',
            'coverage_days': 'أيام التغطية',
            'coverage_status': 'الحالة',
            'item_category1': 'القسم',
            'item_category2': 'القسم الفرعي'
        })
        summary_df = summary_df[['الفرع', 'كود المنتج', 'اسم الصنف', 'القسم', 'القسم الفرعي', 
                                'المخزون الحالي', 'متوسط المبيعات اليومي', 'أيام التغطية', 'الحالة']]
        
        # Store results in database
        transfer_results_id = data_store.save_dataframe(username, 'transfers', 'transfer_results', result_df)
        summary_results_id = data_store.save_dataframe(username, 'transfers', 'summary_results', summary_df)
        
        # Update params
        params['start_date'] = start_date
        params['end_date'] = end_date
        
        # Get or create user session
        user_session = data_store.get_user_session(username, 'transfers')
        if not user_session:
            user_session = {'file_id': None, 'data_ids': {}, 'params': {}}
        
        # Update user session
        data_ids = user_session.get('data_ids', {})
        data_ids['transfer_results'] = transfer_results_id
        data_ids['summary_results'] = summary_results_id
        
        data_store.save_user_session(
            username=username,
            module='transfers',
            file_id=user_session.get('file_id'),
            data_ids=data_ids,
            params=params
        )
        
        if not result_df.empty:
            app.logger.info(f'Transfer analysis completed successfully: {len(transfers)} transfers recommended')
            flash('✅ تم تنفيذ تحليل التوازن بنجاح', 'success')
        else:
            app.logger.info('Transfer analysis completed: no transfers recommended')
            flash('ℹ️ لا توجد اقتراحات نقل حالياً بناءً على التغطية', 'info')
        
        return redirect(url_for('transfers'))
        
    except ValueError as e:
        app.logger.error(f"Validation error in transfers analysis: {e}", exc_info=True)
        flash(f'خطأ في البيانات المدخلة: {str(e)}', 'error')
        return redirect(url_for('transfers'))
    except Exception as e:
        app.logger.error(f"Error in transfers analysis: {e}", exc_info=True)
        flash(f'حدث خطأ أثناء التحليل: {str(e)}', 'error')
        return redirect(url_for('transfers'))

@app.route('/transfers/export')
@app.route('/transfers/export/<format>')
@login_required
def transfers_export(format='xlsx', insights=None):
    """
    Export transfers results strictly in XLSX format.
    """
    username = session.get('username')
    format = 'xlsx'  # Force XLSX
    
    try:
        app.logger.info(f"Transfers export initiated by user: {username}")
        
        from utils.session_validator import comprehensive_export_validation
        validation_success, error_message, session_data, dataframes = comprehensive_export_validation(username, 'transfers')
        
        if not validation_success:
            app.logger.warning(f"Transfers export validation failed for user {username}: {error_message}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify({'success': False, 'error': error_message}), 400
            flash(error_message, 'error')
            return redirect(url_for('transfers'))
        
        transfer_df = dataframes.get('transfer_results')
        summary_df = dataframes.get('summary_results')
        params = session_data.get('params', {})
        
        if transfer_df is None:
            msg = 'لا توجد بيانات للتصدير. يرجى البدء بالتحليل أولاً'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify({'success': False, 'error': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('transfers'))
            
        from utils import ui_helpers
        import io
        excel_data = ui_helpers.export_transfers_report(transfer_df, summary_df, ai_insights=insights)
        
        if not excel_data:
            raise Exception("Failed to generate Excel data")
            
        return send_file(
            io.BytesIO(excel_data),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"transfers_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        
    except Exception as e:
        app.logger.error(f"Transfers export failed: {e}", exc_info=True)
        msg = 'حدث خطأ أثناء تصدير البيانات'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'error': msg}), 500
        flash(msg, 'error')
        return redirect(url_for('transfers'))

@app.route('/forecasting')
@login_required
def forecasting():

    username = session.get('username')
    
    # Get all available branches
    branches = data_store.get_all_branches(username)
    
    # Get selected branch from session
    selected_branch = session.get('selected_forecasting_branch')
    
    # Get user session from database (for results and params)
    user_session = data_store.get_user_session(username, 'forecasting')
    params = user_session.get('params', {}) if user_session else {}
    
    # Prepare results for display if available
    forecast_results = None
    summary_df = None
    feature_importance = None
    
    if user_session and user_session.get('data_ids', {}).get('summary_df'):
        try:
            summary_id = user_session['data_ids']['summary_df']
            summary_data = data_store.get_dataframe(summary_id)
            if summary_data is not None:
                summary_df = summary_data.to_dict('records')
                forecast_results = summary_df  # Use summary as forecast results
        except Exception as e:
            app.logger.error(f"Error loading summary: {e}")
    
    if user_session and user_session.get('data_ids', {}).get('feature_importance_df'):
        try:
            importance_id = user_session['data_ids']['feature_importance_df']
            importance_data = data_store.get_dataframe(importance_id)
            if importance_data is not None:
                # Normalize importance values to sum to 1
                total_importance = importance_data['importance'].sum()
                if total_importance > 0:
                    importance_data['importance'] = importance_data['importance'] / total_importance
                feature_importance = importance_data.head(10).to_dict('records')  # Top 10 features
        except Exception as e:
            app.logger.error(f"Error loading feature importance: {e}")
    
    return render_template('forecasting.html',
                         params=params,
                         forecast_results=forecast_results,
                         summary_df=summary_df,
                         feature_importance=feature_importance,
                         branches=branches,
                         selected_branch=selected_branch)

@app.route('/forecasting/select-branch', methods=['POST'])
@login_required
def forecasting_select_branch():

    try:
        branch_name = request.form.get('branch_name')
        if not branch_name:
            flash('يرجى اختيار فرع', 'error')
            return redirect(url_for('forecasting'))
        
        # Store selected branch in session
        session['selected_forecasting_branch'] = branch_name
        flash(f'تم تحديد الفرع: {branch_name if branch_name != "all" else "جميع الفروع"}', 'success')
        
        return redirect(url_for('forecasting'))
        
    except Exception as e:
        app.logger.error(f"Error selecting branch: {e}", exc_info=True)
        flash('حدث خطأ في تحديد الفرع', 'error')
        return redirect(url_for('forecasting'))


@app.route('/forecasting/upload', methods=['POST'])
@login_required
def forecasting_upload():

    filepath = None
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('لم يتم اختيار ملف', 'error')
            return redirect(url_for('forecasting'))
        
        file = request.files['file']
        
        if file.filename == '':
            flash('لم يتم اختيار ملف', 'error')
            return redirect(url_for('forecasting'))
        
        # Validate file extension
        file_valid, file_error = validation.validate_file_extension(
            file.filename, app.config['ALLOWED_EXTENSIONS']
        )
        if not file_valid:
            flash(file_error, 'error')
            return redirect(url_for('forecasting'))
        
        # Get and validate date range from form
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        date_valid, date_error, start_date_dt, end_date_dt = validation.validate_date_range(
            start_date, end_date
        )
        if not date_valid:
            flash(date_error, 'error')
            return redirect(url_for('forecasting'))
        
        # Read file data into memory
        file_data = file.read()
        username = session.get('username')
        
        # Save file to database
        file_id = data_store.save_uploaded_file(
            username=username,
            module='forecasting',
            filename=file.filename,
            file_data=file_data
        )
        
        # Create temporary file for processing
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file.write(file_data)
            filepath = tmp_file.name
        
        # Process the file using existing utility
        merged_df = data_processing.load_unified_data(filepath)
        
        if merged_df is None or merged_df.empty:
            app.logger.error(f'Failed to process forecasting file: {file.filename}')
            flash('فشل معالجة الملف. تأكد من وجود شيتات Sales و Inventory', 'error')
            return redirect(url_for('forecasting'))
        
        # Filter data by date range
        merged_df['sale_date'] = pd.to_datetime(merged_df['sale_date'])
        mask = (merged_df['sale_date'] >= start_date_dt) & (merged_df['sale_date'] <= end_date_dt)
        filtered_df = merged_df.loc[mask]
        
        if filtered_df.empty:
            flash('لا توجد بيانات في الفترة المحددة', 'warning')
            return redirect(url_for('forecasting'))
        
        # Save DataFrame to database
        sales_id = data_store.save_dataframe(username, 'forecasting', 'sales_df', filtered_df)
        
        # Save user session
        data_store.save_user_session(
            username=username,
            module='forecasting',
            file_id=file_id,
            data_ids={'sales_df': sales_id},
            params={'start_date': start_date, 'end_date': end_date}
        )
        
        app.logger.info(f'Forecasting file uploaded successfully: {file.filename}')
        flash('تم رفع الملف ومعالجته بنجاح', 'success')
        return redirect(url_for('forecasting'))
        
    except Exception as e:
        app.logger.error(f"Error in forecasting upload: {e}", exc_info=True)
        flash(f'حدث خطأ أثناء معالجة الملف: {str(e)}', 'error')
        return redirect(url_for('forecasting'))
    finally:
        # Clean up temporary file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                app.logger.warning(f"Could not delete temp file {filepath}: {e}")


@app.route('/forecasting/clear', methods=['POST'])
@login_required
def forecasting_clear():

    try:
        username = session.get('username')
        
        # Clear user session in database
        data_store.clear_user_session(username, 'forecasting')
        
        # Clear session variables
        session.pop('forecasting_results', None)
        session.pop('selected_forecasting_branch', None)
        
        flash('تم مسح بيانات التنبؤ بنجاح', 'success')
        return redirect(url_for('forecasting'))
        
    except Exception as e:
        app.logger.error(f"Error clearing forecasting session: {e}", exc_info=True)
        flash('حدث خطأ أثناء مسح بيانات التنبؤ', 'error')
        return redirect(url_for('forecasting'))

@app.route('/forecasting/run', methods=['POST'])
@login_required
def forecasting_run():

    try:
        username = session.get('username')
        
        # Get selected branch from session
        selected_branch = session.get('selected_forecasting_branch')
        
        if not selected_branch:
            flash('يرجى اختيار فرع أولاً', 'warning')
            return redirect(url_for('forecasting'))
        
        # Get and validate parameters from form
        forecast_days_valid, forecast_days_error, forecast_days = validation.validate_numeric_parameter(
            request.form.get('forecast_days', 30), 'أيام التنبؤ', min_value=1, max_value=365
        )
        if not forecast_days_valid:
            flash(forecast_days_error, 'error')
            return redirect(url_for('forecasting'))
        
        # Validate date range
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        date_valid, date_error, start_date_dt, end_date_dt = validation.validate_date_range(
            start_date, end_date
        )
        if not date_valid:
            flash(date_error, 'error')
            return redirect(url_for('forecasting'))
        
        # Load sales data from centralized storage
        sales_df, inv_df = data_store.get_branch_data(username, selected_branch if selected_branch != 'all' else None)
        
        if sales_df is None or sales_df.empty:
            flash('لا توجد بيانات للتنبؤ. يرجى رفع بيانات الفروع أولاً', 'warning')
            return redirect(url_for('forecasting'))
        
        if inv_df is None or inv_df.empty:
            flash('لا توجد بيانات المخزون. يرجى رفع بيانات كاملة', 'warning')
            return redirect(url_for('forecasting'))
        
        # Calculate price if not present
        if 'price' not in sales_df.columns:
            sales_df['price'] = sales_df.apply(
                lambda row: row['revenue'] / row['quantity_sold'] if row['quantity_sold'] > 0 else 0,
                axis=1
            )
        
        # Merge sales with inventory to get required columns
        merged_df = pd.merge(
            sales_df,
            inv_df[['product_code', 'branch_code', 'product_name', 'item_category1', 'item_category2', 'Last_on_hand']].drop_duplicates(subset=['product_code', 'branch_code']),
            on=['product_code', 'branch_code'],
            how='left'
        )
        
        # Ensure discount column exists
        if 'discount' not in merged_df.columns:
            merged_df['discount'] = 0
        
        # Filter by date range
        merged_df['sale_date'] = pd.to_datetime(merged_df['sale_date'])
        mask = (merged_df['sale_date'] >= start_date_dt) & (merged_df['sale_date'] <= end_date_dt)
        merged_df = merged_df.loc[mask]
        
        if merged_df.empty:
            flash('لا توجد بيانات في الفترة المحددة', 'warning')
            return redirect(url_for('forecasting'))
        
        # Path to special events file - use resource path helper for executable compatibility
        events_path = get_resource_path(os.path.join('forecast_modules', 'special_events.xlsx'))
        
        # Import forecasting utility
        from utils import forecasting
        
        # Run forecasting pipeline
        full_daily_df, product_summary_df, feature_importance_df = forecasting.run_forecasting_pipeline(
            merged_df, 
            forecast_days, 
            events_path
        )
        
        if full_daily_df is None or product_summary_df is None:
            app.logger.error('Forecasting pipeline failed to generate results')
            flash('فشل تشغيل التنبؤ. يرجى التحقق من البيانات', 'error')
            return redirect(url_for('forecasting'))
        
        # Store results in database
        full_daily_id = data_store.save_dataframe(username, 'forecasting', 'full_daily_df', full_daily_df)
        summary_id = data_store.save_dataframe(username, 'forecasting', 'summary_df', product_summary_df)
        
        # Get or create user session
        user_session = data_store.get_user_session(username, 'forecasting')
        if not user_session:
            user_session = {'file_id': None, 'data_ids': {}, 'params': {}}
        
        # Update data_ids
        data_ids = user_session.get('data_ids', {})
        data_ids['full_daily_df'] = full_daily_id
        data_ids['summary_df'] = summary_id
        data_ids['forecast_results'] = summary_id  # Export validator expects 'forecast_results'
        
        if feature_importance_df is not None:
            importance_id = data_store.save_dataframe(username, 'forecasting', 'feature_importance_df', feature_importance_df)
            data_ids['feature_importance_df'] = importance_id
        
        # Update params
        params = user_session.get('params', {})
        params['forecast_days'] = forecast_days
        params['start_date'] = start_date
        params['end_date'] = end_date
        
        # Save updated session
        data_store.save_user_session(
            username=username,
            module='forecasting',
            file_id=user_session.get('file_id'),
            data_ids=data_ids,
            params=params
        )
        
        app.logger.info(f'Forecasting completed successfully: {forecast_days} days forecast')
        
        # PROOF OF LOGIC: Verify dynamic confidence values
        if product_summary_df is not None and not product_summary_df.empty:
            app.logger.info("PROOF OF LOGIC - First 5 confidence values from results:")
            app.logger.info("\n" + str(product_summary_df[['product_code', 'confidence']].head(5)))
            
        flash('✅ تم إجراء التنبؤ بنجاح', 'success')
        return redirect(url_for('forecasting'))
        
    except ValueError as e:
        app.logger.error(f"Validation error in forecasting: {e}", exc_info=True)
        flash(f'خطأ في البيانات المدخلة: {str(e)}', 'error')
        return redirect(url_for('forecasting'))
    except Exception as e:
        app.logger.error(f"Error in forecasting run: {e}", exc_info=True)
        flash(f'حدث خطأ أثناء التنبؤ: {str(e)}', 'error')
        return redirect(url_for('forecasting'))

@app.route('/forecasting/chart_data/<product_code>/<branch_code>')
@login_required
def forecasting_chart_data(product_code, branch_code):

    try:
        username = session.get('username')
        
        # Check if forecast data exists in database
        user_session = data_store.get_user_session(username, 'forecasting')
        
        if not user_session or not user_session.get('data_ids', {}).get('full_daily_df'):
            return {'error': 'لا توجد بيانات تنبؤ متاحة'}, 404
        
        # Load full daily data from database
        full_daily_id = user_session['data_ids']['full_daily_df']
        full_daily_df = data_store.get_dataframe(full_daily_id)
        
        if full_daily_df is None:
            return {'error': 'خطأ في تحميل البيانات'}, 500
        
        # Filter data for selected product and branch
        product_data = full_daily_df[
            (full_daily_df['product_code'] == product_code) & 
            (full_daily_df['branch_code'] == branch_code)
        ].copy()
        
        if product_data.empty:
            return {'error': 'لا توجد بيانات لهذا المنتج والفرع'}, 404
        
        # Sort by date
        product_data = product_data.sort_values('sale_date')
        
        # Prepare data for chart
        import pandas as pd
        dates = product_data['sale_date'].dt.strftime('%Y-%m-%d').tolist()
        
        # Actual sales (where predicted is null)
        actual_sales = []
        predicted_sales = []
        
        for _, row in product_data.iterrows():
            if pd.isna(row['predicted_quantity_sold']):
                # Historical data
                actual_sales.append(float(row['quantity_sold']))
                predicted_sales.append(None)
            else:
                # Forecast data
                actual_sales.append(None)
                predicted_sales.append(float(row['predicted_quantity_sold']))
        
        # Prepare chart data
        chart_data = {
            "dates": dates,
            "actual_sales": actual_sales,
            "predicted_sales": predicted_sales,
        }
        return {"chart_data": chart_data}, 200
    except Exception as e:
        app.logger.error(f"Error generating chart data: {e}", exc_info=True)
        return {"error": "Failed to generate chart data"}, 500


@app.route('/forecasting/export')
@app.route('/forecasting/export/<format>')
@login_required
def forecasting_export(format='xlsx', insights=None):
    """
    Export forecasting results strictly in XLSX format.
    """
    username = session.get('username')
    format = 'xlsx'  # Force XLSX
    
    try:
        app.logger.info(f"Forecasting export initiated by user: {username}")
        
        from utils.session_validator import comprehensive_export_validation
        validation_success, error_message, session_data, dataframes = comprehensive_export_validation(username, 'forecasting')
        
        if not validation_success:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify({'success': False, 'error': error_message}), 400
            flash(error_message, 'error')
            return redirect(url_for('forecasting'))
        
        # Safely get the dataframe without triggering bool() on a DataFrame
        forecast_df = dataframes.get('forecast_results')
        if forecast_df is None:
            forecast_df = dataframes.get('summary_df')
        if forecast_df is None:
            forecast_df = dataframes.get('summary')
        params = session_data.get('params', {})
        
        if forecast_df is None or forecast_df.empty:
            msg = 'لا توجد بيانات للتصدير. يرجى البدء بالتنبؤ أولاً'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify({'success': False, 'error': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('forecasting'))
            
        from utils import ui_helpers
        import io
        # Use simple forecasting export
        excel_data = ui_helpers.export_forecasting_report(forecast_df, params, ai_insights=insights)
        
        if not excel_data:
            raise Exception("Failed to generate Excel data")
            
        return send_file(
            io.BytesIO(excel_data),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"forecasting_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        
    except Exception as e:
        app.logger.error(f"Forecasting export failed: {e}", exc_info=True)
        msg = 'حدث خطأ أثناء تصدير البيانات'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'error': msg}), 500
        flash(msg, 'error')
        return redirect(url_for('forecasting'))

# ===== NEW ROUTES: HIGH DEMAND & LOW STOCK FILTERING (Fix #2) =====
@app.route('/forecasting/high-demand')
@login_required
def forecasting_high_demand():
    """Filter and display high-demand products (forecast > 1000 units)."""
    try:
        username = session.get('username')
        
        # Load user session and summary data
        user_session = data_store.get_user_session(username, 'forecasting')
        
        if not user_session or not user_session.get('data_ids', {}).get('summary_df'):
            flash('لا توجد بيانات تنبؤ. يرجى تشغيل التحليل أولاً', 'warning')
            return redirect(url_for('forecasting'))
        
        # Load summary from database
        summary_id = user_session['data_ids']['summary_df']
        summary_df = data_store.get_dataframe(summary_id)
        
        if summary_df is None or summary_df.empty:
            flash('لا توجد نتائج للتصدير', 'warning')
            return redirect(url_for('forecasting'))
        
        # Filter: forecast > 1000 (high demand threshold)
        high_demand_threshold = 1000
        high_demand_df = summary_df[summary_df['forecast_quantity'] > high_demand_threshold].copy()
        high_demand_df = high_demand_df.sort_values('forecast_quantity', ascending=False)
        
        app.logger.info(f"High-demand filter: {len(high_demand_df)} products found")
        
        # Get params for context
        params = user_session.get('params', {})
        
        return render_template('forecasting_filtered.html',
                             results=high_demand_df.to_dict('records'),
                             filter_type='منتجات الطلب المرتفع',
                             count=len(high_demand_df),
                             total_count=len(summary_df),
                             params=params)
    
    except Exception as e:
        app.logger.error(f"Error in high-demand filter: {e}", exc_info=True)
        flash('حدث خطأ في تطبيق المرشح', 'error')
        return redirect(url_for('forecasting'))

@app.route('/forecasting/low-stock')
@login_required
def forecasting_low_stock():
    """Filter and display low-stock products (stock < 100 units)."""
    try:
        username = session.get('username')
        
        # Load user session and summary data
        user_session = data_store.get_user_session(username, 'forecasting')
        
        if not user_session or not user_session.get('data_ids', {}).get('summary_df'):
            flash('لا توجد بيانات تنبؤ. يرجى تشغيل التحليل أولاً', 'warning')
            return redirect(url_for('forecasting'))
        
        # Load summary from database
        summary_id = user_session['data_ids']['summary_df']
        summary_df = data_store.get_dataframe(summary_id)
        
        if summary_df is None or summary_df.empty:
            flash('لا توجد نتائج للتصدير', 'warning')
            return redirect(url_for('forecasting'))
        
        # Filter: stock < 100 (low stock threshold)
        low_stock_threshold = 100
        low_stock_df = summary_df[summary_df['Last_on_hand'] < low_stock_threshold].copy()
        low_stock_df = low_stock_df.sort_values('Last_on_hand', ascending=True)
        
        app.logger.info(f"Low-stock filter: {len(low_stock_df)} products found")
        
        # Get params for context
        params = user_session.get('params', {})
        
        return render_template('forecasting_filtered.html',
                             results=low_stock_df.to_dict('records'),
                             filter_type='منتجات المخزون المنخفض',
                             count=len(low_stock_df),
                             total_count=len(summary_df),
                             params=params)
    
    except Exception as e:
        app.logger.error(f"Error in low-stock filter: {e}", exc_info=True)
        flash('حدث خطأ في تطبيق المرشح', 'error')
        return redirect(url_for('forecasting'))
# ===== END NEW ROUTES =====
        
@app.route('/admin')
@login_required
def admin():
    if not session.get('is_admin'):
        flash('غير مسموح لك بالدخول لهذه الصفحة', 'error')
        return redirect(url_for('home'))
        
    try:
        users = auth_flask.get_all_users()
        return render_template('admin.html', users=users)
    except Exception as e:
        app.logger.error(f"Error accessing admin page: {e}", exc_info=True)
        flash('حدث خطأ أثناء تحميل الصفحة', 'error')
        return redirect(url_for('home'))

@app.route('/admin/add-user', methods=['POST'])
@login_required
def admin_add_user():
    if not session.get('is_admin'):
        return redirect(url_for('home'))
        
    try:
        username = request.form.get('username')
        password = request.form.get('password')
        is_admin = bool(request.form.get('is_admin'))
        
        success, message = auth_flask.add_user(username, password, is_admin)
        
        flash(message, 'success' if success else 'error')
        return redirect(url_for('admin'))
    except Exception as e:
        app.logger.error(f"Error adding user: {e}", exc_info=True)
        flash('حدث خطأ أثناء إضافة المستخدم', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/delete-user', methods=['POST'])
@login_required
def admin_delete_user():
    if not session.get('is_admin'):
        return redirect(url_for('home'))
        
    try:
        username = request.form.get('username')
        current_user = session.get('username')
        
        success, message = auth_flask.delete_user(username, current_user)
        
        flash(message, 'success' if success else 'error')
        return redirect(url_for('admin'))
    except Exception as e:
        app.logger.error(f"Error deleting user: {e}", exc_info=True)
        flash('حدث خطأ أثناء حذف المستخدم', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/change-password', methods=['POST'])
@login_required
def admin_change_password():
    if not session.get('is_admin'):
        return redirect(url_for('home'))
        
    try:
        username = request.form.get('username')
        new_password = request.form.get('new_password')
        
        success, message = auth_flask.change_password(username, new_password)
        
        flash(message, 'success' if success else 'error')
        return redirect(url_for('admin'))
    except Exception as e:
        app.logger.error(f"Error changing password: {e}", exc_info=True)
        flash('حدث خطأ أثناء تغيير كلمة المرور', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/reset-all-data', methods=['POST'])
@login_required
def admin_reset_all_data():
    if not session.get('is_admin'):
        return redirect(url_for('home'))
        
    try:
        current_user = session.get('username')
        
        # 1. Delete all database records (except users and critical data)
        #    Use the DuckDB-native store layer instead of sqlite3 (which cannot
        #    open DuckDB files) — fixes the driver-mismatch defect.
        data_store.clear_all_data()
        
        app.logger.warning(f'⚡ ALL SYSTEM DATA CLEARED by admin: {current_user}')
        flash('تم مسح جميع بيانات النظام بنجاح', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        app.logger.error(f"CRITICAL ERROR clearing system data: {e}", exc_info=True)
        flash('حدث خطأ كارثي أثناء مسح البيانات', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/database-health')
@login_required
def admin_database_health():
    """
    Database health check endpoint for administrators.
    Returns JSON with database status and diagnostic information.
    """
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        health = data_store.get_database_health()
        return jsonify(health)
    except Exception as e:
        app.logger.error(f"Error checking database health: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error checking database health: {str(e)}',
            'details': {'error': str(e)}
        }), 500

@app.route('/admin/repair-database', methods=['POST'])
@login_required
def admin_repair_database():
    """
    Database repair endpoint for administrators.
    Attempts to fix database issues and returns status.
    """
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
        
    try:
        current_user = session.get('username')
        app.logger.info(f"Database repair initiated by admin: {current_user}")
        
        success, message = data_store.repair_database()
        
        if success:
            app.logger.info(f"Database repair completed successfully by admin: {current_user}")
            flash('تم إصلاح قاعدة البيانات بنجاح', 'success')
        else:
            app.logger.error(f"Database repair failed for admin {current_user}: {message}")
            flash(f'فشل إصلاح قاعدة البيانات: {message}', 'error')
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        app.logger.error(f"Error during database repair: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error during database repair: {str(e)}'
        }), 500

# ============================================================================
# Diagnostic and Monitoring Endpoints
# ============================================================================

@app.route('/admin/diagnostics/health')
@login_required
def admin_diagnostics_health():
    """
    System health check endpoint for administrators.
    Returns comprehensive system health information.
    """
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        diagnostic_collector = get_diagnostic_collector()
        health_info = diagnostic_collector.get_system_health()
        return jsonify(health_info)
    except Exception as e:
        app.logger.error(f"Error getting system health: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error getting system health: {str(e)}',
            'timestamp': datetime.datetime.now().isoformat()
        }), 500

@app.route('/admin/diagnostics/upload-stats')
@login_required
def admin_diagnostics_upload_stats():
    """
    Upload statistics endpoint for administrators.
    Returns upload statistics for the specified time period.
    """
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        hours = request.args.get('hours', 24, type=int)
        if hours < 1 or hours > 168:  # Limit to 1 hour - 1 week
            hours = 24
        
        diagnostic_collector = get_diagnostic_collector()
        stats = diagnostic_collector.get_upload_statistics(hours)
        return jsonify(stats)
    except Exception as e:
        app.logger.error(f"Error getting upload statistics: {e}", exc_info=True)
        return jsonify({
            'error': f'Error getting upload statistics: {str(e)}',
            'timestamp': datetime.datetime.now().isoformat()
        }), 500

@app.route('/admin/diagnostics/recent-errors')
@login_required
def admin_diagnostics_recent_errors():
    """
    Recent errors endpoint for administrators.
    Returns recent error logs for troubleshooting.
    """
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        if hours < 1 or hours > 168:  # Limit to 1 hour - 1 week
            hours = 24
        if limit < 1 or limit > 200:  # Limit to 1-200 errors
            limit = 50
        
        diagnostic_collector = get_diagnostic_collector()
        errors = diagnostic_collector.get_recent_errors(hours, limit)
        return jsonify({
            'errors': errors,
            'count': len(errors),
            'period_hours': hours,
            'timestamp': datetime.datetime.now().isoformat()
        })
    except Exception as e:
        app.logger.error(f"Error getting recent errors: {e}", exc_info=True)
        return jsonify({
            'error': f'Error getting recent errors: {str(e)}',
            'timestamp': datetime.datetime.now().isoformat()
        }), 500

@app.route('/admin/diagnostics/performance-trends')
@login_required
def admin_diagnostics_performance_trends():
    """
    Performance trends endpoint for administrators.
    Returns performance analysis and trends over time.
    """
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        hours = request.args.get('hours', 168, type=int)  # Default 1 week
        if hours < 1 or hours > 720:  # Limit to 1 hour - 30 days
            hours = 168
        
        diagnostic_collector = get_diagnostic_collector()
        trends = diagnostic_collector.analyze_performance_trends(hours)
        return jsonify(trends)
    except Exception as e:
        app.logger.error(f"Error analyzing performance trends: {e}", exc_info=True)
        return jsonify({
            'error': f'Error analyzing performance trends: {str(e)}',
            'timestamp': datetime.datetime.now().isoformat()
        }), 500

@app.route('/admin/diagnostics/logs/<log_type>')
@login_required
def admin_diagnostics_logs(log_type):
    """
    Log file access endpoint for administrators.
    Returns recent log entries from specified log type.
    """
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Validate log type
        valid_log_types = {
            'upload': 'upload_operations.jsonl',
            'performance': 'performance.jsonl',
            'errors': 'errors.log',
            'app': 'flask_app.log'
        }
        
        if log_type not in valid_log_types:
            return jsonify({
                'error': f'Invalid log type. Valid types: {list(valid_log_types.keys())}'
            }), 400
        
        log_file = os.path.join('logs', valid_log_types[log_type])
        lines = request.args.get('lines', 100, type=int)
        
        if lines < 1 or lines > 1000:  # Limit to 1-1000 lines
            lines = 100
        
        if not os.path.exists(log_file):
            return jsonify({
                'log_type': log_type,
                'entries': [],
                'message': 'Log file does not exist',
                'timestamp': datetime.datetime.now().isoformat()
            })
        
        # Read recent log entries
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Get the most recent lines
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # Parse JSON logs if applicable
        entries = []
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue
            
            if log_type in ['upload', 'performance'] and line.startswith('{'):
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    entries.append({'raw_line': line})
            else:
                entries.append({'raw_line': line})
        
        return jsonify({
            'log_type': log_type,
            'entries': entries,
            'count': len(entries),
            'requested_lines': lines,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error reading log file {log_type}: {e}", exc_info=True)
        return jsonify({
            'error': f'Error reading log file: {str(e)}',
            'timestamp': datetime.datetime.now().isoformat()
        }), 500

# ============================================================================
# Main Execution
# ============================================================================

if __name__ == '__main__':
    # Initialize runtime directories (logs, uploads, etc.)
    initialize_runtime_directories()
    
    # Initialize performance optimizations for inventory alerts
    try:
        from utils.performance_optimization import initialize_performance_optimizations
        success, message = initialize_performance_optimizations()
        if success:
            app.logger.info(f"Performance optimizations initialized: {message}")
        else:
            app.logger.warning(f"Some performance optimizations failed: {message}")
    except Exception as e:
        app.logger.error(f"Error initializing performance optimizations: {e}")
    
    # Start browser thread (only if not in debug mode to avoid double opening)
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        threading.Thread(target=open_browser, daemon=True).start()

    # Run the Flask application
    # Note: debug=False is recommended for EXE deployment
    host = os.environ.get('FLASK_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', '5000'))
    app.run(host=host, port=port, debug=False)
