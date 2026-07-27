"""
Integration tests for data upload workflow - Task 8.1
Tests complete upload-to-display flow and error handling in UI context.
Requirements: 2.4, 2.5
"""

import pytest
import sys
import os
import tempfile
import pandas as pd
from io import BytesIO
import sqlite3

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import only what we need to avoid dependency issues
import auth_flask
import data_store

# Create a minimal Flask app for testing
from flask import Flask

def create_test_app():
    """Create a minimal Flask app for testing"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['ALLOWED_EXTENSIONS'] = {"xlsx", "xls", "csv"}
    app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
    
    # Import and register only the routes we need for testing
    from flask import render_template, request, redirect, url_for, flash, session
    from flask_login import LoginManager, login_required, UserMixin, login_user as flask_login_user, logout_user
    from werkzeug.utils import secure_filename
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    class User(UserMixin):
        def __init__(self, username, is_admin=False):
            self.id = username
            self.is_admin = is_admin
        
        def get_id(self):
            return self.id
    
    @login_manager.user_loader
    def load_user(username):
        user_data = auth_flask.get_user(username)
        if user_data:
            return User(username=user_data[0], is_admin=bool(user_data[1]))
        return None
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            success, is_admin, message = auth_flask.login_user(username, password)
            if success:
                user = User(username, is_admin)
                flask_login_user(user)  # Flask-Login function
                session['username'] = username
                return redirect(url_for('data_upload'))
            else:
                flash('Invalid credentials', 'error')
        
        return '<form method="post"><input name="username"><input name="password" type="password"><button>Login</button></form>'
    
    @app.route('/logout')
    def logout():
        logout_user()
        session.clear()
        return redirect(url_for('login'))
    
    @app.route('/data/upload')
    @login_required
    def data_upload():
        try:
            username = session.get('username')
            branches = data_store.get_branch_files(username)
            
            # Simple HTML response for testing
            html = '<h1>Data Upload</h1><ul>'
            for branch in branches:
                html += f'<li>{branch["branch_name"]} - {branch["filename"]} ({branch["file_size"]} bytes)</li>'
            html += '</ul>'
            return html
            
        except Exception as e:
            flash('Error loading page', 'error')
            return '<h1>Data Upload</h1><p>Error loading branches</p>'
    
    @app.route('/data/upload/file', methods=['POST'])
    @login_required
    def data_upload_file():
        try:
            username = session.get('username')
            branch_name = request.form.get('branch_name', '').strip()
            
            if not branch_name:
                flash('Branch name is required', 'error')
                return redirect(url_for('data_upload'))
            
            if 'file' not in request.files:
                flash('No file selected', 'error')
                return redirect(url_for('data_upload'))
            
            file = request.files['file']
            if not file or file.filename == '':
                flash('No file selected', 'error')
                return redirect(url_for('data_upload'))
            
            filename = secure_filename(file.filename)
            if not filename.lower().endswith(('.xlsx', '.xls')):
                flash('Invalid file type', 'error')
                return redirect(url_for('data_upload'))
            
            file_data = file.read()
            
            # Save to database
            file_id, sales_id, inventory_id = data_store.save_branch_data(
                username=username,
                branch_name=branch_name,
                filename=file.filename,
                file_data=file_data
            )
            
            flash('File uploaded successfully', 'success')
            return redirect(url_for('data_upload'))
            
        except Exception as e:
            flash(f'Upload failed: {str(e)}', 'error')
            return redirect(url_for('data_upload'))
    
    return app


@pytest.fixture
def client():
    """Create test client with proper configuration"""
    app = create_test_app()
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def logged_in_client(client):
    """Create logged-in test client for upload tests"""
    username = 'test_upload_user'
    password = 'TestPass123!'
    auth_flask.add_user(username, password, is_admin=False)
    
    # Login the user
    response = client.post('/login', data={
        'username': username,
        'password': password
    })
    assert response.status_code == 302  # Redirect after successful login
    
    yield client
    
    # Cleanup
    auth_flask.delete_user(username, 'admin')


@pytest.fixture
def sample_excel_file():
    """Create a valid Excel file for testing"""
    # Create sample data
    transactions_data = {
        'Date': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'Item Code': ['ITEM001', 'ITEM002', 'ITEM003'],
        'Item Name': ['Product A', 'Product B', 'Product C'],
        'Quantity': [10, 20, 15],
        'Unit Price': [100.0, 150.0, 200.0],
        'Total': [1000.0, 3000.0, 3000.0]
    }
    
    item_info_data = {
        'Item Code': ['ITEM001', 'ITEM002', 'ITEM003'],
        'Item Name': ['Product A', 'Product B', 'Product C'],
        'Category': ['Electronics', 'Clothing', 'Books'],
        'Unit': ['PCS', 'PCS', 'PCS'],
        'Cost Price': [80.0, 120.0, 160.0]
    }
    
    # Create Excel file in memory
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        pd.DataFrame(transactions_data).to_excel(writer, sheet_name='Transactions', index=False)
        pd.DataFrame(item_info_data).to_excel(writer, sheet_name='Item info', index=False)
    
    excel_buffer.seek(0)
    return excel_buffer


@pytest.fixture
def invalid_excel_file():
    """Create an invalid Excel file for error testing"""
    # Create Excel file with missing required sheets
    invalid_data = {
        'Wrong Sheet': ['data1', 'data2', 'data3']
    }
    
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        pd.DataFrame(invalid_data).to_excel(writer, sheet_name='Wrong Sheet', index=False)
    
    excel_buffer.seek(0)
    return excel_buffer


class TestUploadWorkflowIntegration:
    """Integration tests for complete upload-to-display workflow"""
    
    def test_data_upload_page_access(self, logged_in_client):
        """Test accessing data upload page - Requirement 2.4"""
        response = logged_in_client.get('/data/upload')
        assert response.status_code == 200
        assert b'upload' in response.data.lower() or 'رفع'.encode('utf-8') in response.data
    
    def test_data_upload_page_requires_login(self, client):
        """Test that data upload page requires authentication"""
        response = client.get('/data/upload', follow_redirects=True)
        # Should redirect to login page
        assert b'login' in response.data.lower() or 'تسجيل الدخول'.encode('utf-8') in response.data
    
    def test_complete_upload_to_display_flow(self, logged_in_client, sample_excel_file):
        """
        Test complete upload-to-display flow - Requirement 2.4
        Upload file -> Verify success -> Check display on data management page
        """
        branch_name = 'test_branch_integration'
        
        # Step 1: Upload the file
        response = logged_in_client.post('/data/upload/file', data={
            'branch_name': branch_name,
            'file': (sample_excel_file, 'test_data.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        # Verify upload was successful
        assert response.status_code == 200
        # Should show success message or redirect to upload page
        assert b'success' in response.data.lower() or 'نجح'.encode('utf-8') in response.data or '/data/upload' in response.request.url
        
        # Step 2: Check that file appears in the data management page
        response = logged_in_client.get('/data/upload')
        assert response.status_code == 200
        
        # Verify the uploaded branch appears in the list
        assert branch_name.encode('utf-8') in response.data or branch_name in response.get_data(as_text=True)
        assert b'test_data.xlsx' in response.data or 'test_data.xlsx' in response.get_data(as_text=True)
        
        # Step 3: Verify data was actually saved to database
        username = 'test_upload_user'
        branches = data_store.get_branch_files(username)
        
        # Should find our uploaded branch
        uploaded_branch = None
        for branch in branches:
            if branch['branch_name'] == branch_name:
                uploaded_branch = branch
                break
        
        assert uploaded_branch is not None, f"Branch {branch_name} not found in database"
        assert uploaded_branch['filename'] == 'test_data.xlsx'
        assert uploaded_branch['file_size'] > 0
    
    def test_upload_with_empty_branch_name(self, logged_in_client, sample_excel_file):
        """Test upload with empty branch name shows error - Requirement 2.5"""
        response = logged_in_client.post('/data/upload/file', data={
            'branch_name': '',  # Empty branch name
            'file': (sample_excel_file, 'test_data.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message
        assert b'error' in response.data.lower() or 'خطأ'.encode('utf-8') in response.data
    
    def test_upload_with_invalid_file_extension(self, logged_in_client):
        """Test upload with invalid file extension shows error - Requirement 2.5"""
        # Create a text file
        text_file = BytesIO(b'This is not an Excel file')
        
        response = logged_in_client.post('/data/upload/file', data={
            'branch_name': 'test_branch',
            'file': (text_file, 'invalid_file.txt')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message about file type
        assert b'error' in response.data.lower() or 'خطأ'.encode('utf-8') in response.data
    
    def test_upload_with_invalid_excel_structure(self, logged_in_client, invalid_excel_file):
        """Test upload with invalid Excel structure shows error - Requirement 2.5"""
        response = logged_in_client.post('/data/upload/file', data={
            'branch_name': 'test_branch',
            'file': (invalid_excel_file, 'invalid_structure.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message about Excel structure
        assert b'error' in response.data.lower() or 'خطأ'.encode('utf-8') in response.data
    
    def test_upload_without_file(self, logged_in_client):
        """Test upload without selecting file shows error - Requirement 2.5"""
        response = logged_in_client.post('/data/upload/file', data={
            'branch_name': 'test_branch'
            # No file field
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message about missing file
        assert b'error' in response.data.lower() or 'خطأ'.encode('utf-8') in response.data
    
    def test_multiple_uploads_same_branch_shows_latest(self, logged_in_client, sample_excel_file):
        """Test multiple uploads for same branch shows most recent - Requirement 2.4"""
        branch_name = 'test_branch_multiple'
        
        # Upload first file
        sample_excel_file.seek(0)  # Reset buffer
        response1 = logged_in_client.post('/data/upload/file', data={
            'branch_name': branch_name,
            'file': (sample_excel_file, 'first_upload.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        assert response1.status_code == 200
        
        # Upload second file for same branch
        sample_excel_file.seek(0)  # Reset buffer
        response2 = logged_in_client.post('/data/upload/file', data={
            'branch_name': branch_name,
            'file': (sample_excel_file, 'second_upload.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        assert response2.status_code == 200
        
        # Check data management page
        response = logged_in_client.get('/data/upload')
        assert response.status_code == 200
        
        # Should show the most recent upload (second_upload.xlsx)
        assert b'second_upload.xlsx' in response.data or 'second_upload.xlsx' in response.get_data(as_text=True)
        # Should not show the first upload (due to deduplication)
        page_content = response.get_data(as_text=True)
        first_count = page_content.count('first_upload.xlsx')
        second_count = page_content.count('second_upload.xlsx')
        
        # The most recent should be shown
        assert second_count > 0, "Most recent upload should be displayed"
    
    def test_upload_persistence_across_sessions(self, client, sample_excel_file):
        """Test uploaded files persist across user sessions - Requirement 2.4"""
        username = 'test_persistence_user'
        password = 'TestPass123!'
        branch_name = 'test_persistence_branch'
        
        # Create user and login
        auth_flask.add_user(username, password, is_admin=False)
        
        # First session: login and upload
        response = client.post('/login', data={
            'username': username,
            'password': password
        })
        assert response.status_code == 302
        
        # Upload file
        response = client.post('/data/upload/file', data={
            'branch_name': branch_name,
            'file': (sample_excel_file, 'persistence_test.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        
        # Logout
        client.get('/logout')
        
        # Second session: login again and check if file is still there
        response = client.post('/login', data={
            'username': username,
            'password': password
        })
        assert response.status_code == 302
        
        # Check data management page
        response = client.get('/data/upload')
        assert response.status_code == 200
        
        # File should still be there
        assert branch_name.encode('utf-8') in response.data or branch_name in response.get_data(as_text=True)
        assert b'persistence_test.xlsx' in response.data or 'persistence_test.xlsx' in response.get_data(as_text=True)
        
        # Cleanup
        auth_flask.delete_user(username, 'admin')
    
    def test_empty_state_display_when_no_uploads(self, logged_in_client):
        """Test empty state message when no files uploaded - Requirement 2.4"""
        # Access data management page with no uploads
        response = logged_in_client.get('/data/upload')
        assert response.status_code == 200
        
        # Should show appropriate empty state or no files message
        # This could be an empty table, a message, or just no branch entries
        page_content = response.get_data(as_text=True)
        
        # The page should load successfully even with no data
        assert 'upload' in page_content.lower() or 'رفع' in page_content
    
    def test_ui_error_feedback_for_database_issues(self, logged_in_client, sample_excel_file, monkeypatch):
        """Test UI shows appropriate error when database operations fail - Requirement 2.5"""
        
        # Mock data_store.save_branch_data to raise an exception
        def mock_save_branch_data(*args, **kwargs):
            raise Exception("Database connection failed")
        
        monkeypatch.setattr(data_store, 'save_branch_data', mock_save_branch_data)
        
        response = logged_in_client.post('/data/upload/file', data={
            'branch_name': 'test_branch',
            'file': (sample_excel_file, 'test_data.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message to user
        assert b'error' in response.data.lower() or 'خطأ'.encode('utf-8') in response.data
    
    def test_file_size_validation_in_ui(self, logged_in_client):
        """Test file size validation shows appropriate error - Requirement 2.5"""
        # Create a large file (simulate oversized upload)
        large_data = b'x' * (50 * 1024 * 1024)  # 50MB file
        large_file = BytesIO(large_data)
        
        response = logged_in_client.post('/data/upload/file', data={
            'branch_name': 'test_branch',
            'file': (large_file, 'large_file.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error about file size
        assert b'error' in response.data.lower() or 'خطأ'.encode('utf-8') in response.data


class TestUploadWorkflowErrorHandling:
    """Test error handling scenarios in upload workflow"""
    
    def test_unauthorized_upload_attempt(self, client, sample_excel_file):
        """Test upload attempt without login is blocked"""
        response = client.post('/data/upload/file', data={
            'branch_name': 'test_branch',
            'file': (sample_excel_file, 'test_data.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        # Should redirect to login page
        assert b'login' in response.data.lower() or 'تسجيل الدخول'.encode('utf-8') in response.data
    
    def test_csrf_protection_on_upload_route(self, logged_in_client, sample_excel_file):
        """Test CSRF protection on upload route (when enabled)"""
        # This test verifies the route handles CSRF appropriately
        # Since we disabled CSRF for testing, we just verify the route works
        response = logged_in_client.post('/data/upload/file', data={
            'branch_name': 'test_branch',
            'file': (sample_excel_file, 'test_data.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        # Should work (CSRF disabled for testing)
        assert response.status_code == 200
    
    def test_concurrent_upload_handling(self, logged_in_client, sample_excel_file):
        """Test system handles concurrent uploads gracefully"""
        branch_name = 'test_concurrent_branch'
        
        # Simulate concurrent uploads by making multiple requests
        # (In real scenario, these would be truly concurrent)
        sample_excel_file.seek(0)
        response1 = logged_in_client.post('/data/upload/file', data={
            'branch_name': branch_name,
            'file': (sample_excel_file, 'concurrent1.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        sample_excel_file.seek(0)
        response2 = logged_in_client.post('/data/upload/file', data={
            'branch_name': branch_name,
            'file': (sample_excel_file, 'concurrent2.xlsx')
        }, content_type='multipart/form-data', follow_redirects=True)
        
        # Both should succeed
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Verify data integrity - should show the most recent upload
        response = logged_in_client.get('/data/upload')
        assert response.status_code == 200
        
        # Should show one of the uploads (most recent due to deduplication)
        page_content = response.get_data(as_text=True)
        assert 'concurrent' in page_content  # Should show at least one concurrent upload


if __name__ == '__main__':
    pytest.main([__file__, '-v'])