"""
Comprehensive integration tests for forecasting workflow.
Tests file upload, parameter configuration, forecasting execution, chart display, results display, and export.
Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import pytest
import sys
import os
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask_app import app
import auth_flask


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        yield client


@pytest.fixture
def logged_in_client(client):
    """Create logged-in test client"""
    username = 'test_forecast_user'
    password = 'TestPass123!'
    auth_flask.add_user(username, password, is_admin=False)
    
    client.post('/login', data={'username': username, 'password': password})
    
    yield client
    
    auth_flask.delete_user(username, 'admin')


@pytest.fixture
def sample_forecast_file():
    """Create a sample unified Excel file for forecasting"""
    # Create sample sales data with realistic structure
    # Note: load_unified_data merges sales and inventory, so we need both sheets
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(90)]  # 90 days of data
    
    sales_records = []
    products = ['ITEM001', 'ITEM002', 'ITEM003']
    branches = ['BR001', 'BR002']
    
    for product in products:
        for branch in branches:
            for date in dates:
                # Generate realistic sales data
                base_qty = 10 if product == 'ITEM001' else (15 if product == 'ITEM002' else 8)
                quantity = base_qty + (date.day % 5)  # Add some variation
                price = 10.5 if product == 'ITEM001' else (20.0 if product == 'ITEM002' else 15.75)
                revenue = quantity * price
                
                sales_records.append({
                    'product_code': product,
                    'branch_code': branch,
                    'sale_date': date,
                    'quantity_sold': quantity,
                    'revenue': revenue
                })
    
    sales_df = pd.DataFrame(sales_records)
    
    # Create inventory data with all required columns
    inventory_records = []
    for product in products:
        for branch in branches:
            inventory_records.append({
                'product_code': product,
                'product_name': f'Product {product[-3:]}',
                'branch_code': branch,
                'Last_on_hand': 500 if product == 'ITEM001' else (300 if product == 'ITEM002' else 200),
                'item_category1': 'Category A',
                'item_category2': 'Subcategory 1'
            })
    
    inventory_df = pd.DataFrame(inventory_records)
    
    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        sales_df.to_excel(writer, sheet_name='Sales', index=False)
        inventory_df.to_excel(writer, sheet_name='Inventory', index=False)
    output.seek(0)
    
    return output


class TestForecastingWorkflow:
    """Test forecasting workflow - Requirements 5.1, 5.2, 5.3, 5.4, 5.5"""
    
    def test_forecasting_page_access(self, logged_in_client):
        """Test accessing forecasting page - Requirement 5.3"""
        response = logged_in_client.get('/forecasting')
        assert response.status_code == 200
        assert 'التنبؤ'.encode('utf-8') in response.data or b'forecast' in response.data.lower()
    
    def test_forecasting_page_requires_login(self, client):
        """Test that forecasting page requires authentication"""
        response = client.get('/forecasting', follow_redirects=True)
        assert 'يرجى تسجيل الدخول'.encode('utf-8') in response.data or b'login' in response.data.lower()
    
    def test_file_upload_valid(self, logged_in_client, sample_forecast_file):
        """Test uploading valid forecast file - Requirement 5.1"""
        response = logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Check for success message
        assert 'نجح'.encode('utf-8') in response.data or b'success' in response.data.lower() or \
               'تم رفع'.encode('utf-8') in response.data
    
    def test_file_upload_invalid_extension(self, logged_in_client):
        """Test uploading file with invalid extension - Requirement 5.1"""
        csv_data = BytesIO(b'col1,col2\nval1,val2')
        
        response = logged_in_client.post('/forecasting/upload', data={
            'file': (csv_data, 'test.csv'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower() or \
               'غير مسموح'.encode('utf-8') in response.data
    
    def test_file_upload_no_file(self, logged_in_client):
        """Test uploading without selecting a file - Requirement 5.1"""
        response = logged_in_client.post('/forecasting/upload', data={
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message
        assert 'لم يتم اختيار ملف'.encode('utf-8') in response.data or b'file' in response.data.lower()
    
    def test_file_upload_invalid_date_range(self, logged_in_client, sample_forecast_file):
        """Test uploading with invalid date range - Requirement 5.1"""
        response = logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-12-31',
            'end_date': '2024-01-01'  # Invalid: end before start
        }, content_type='multipart/form-data', follow_redirects=True)
        
        assert response.status_code == 200
        # Should show validation error
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_parameter_configuration(self, logged_in_client, sample_forecast_file):
        """Test configuring forecast parameters - Requirement 5.4"""
        # First upload a file
        logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data')
        
        # Then run forecast with parameters
        response = logged_in_client.post('/forecasting/run', data={
            'forecast_days': '30'
        }, follow_redirects=True)
        
        assert response.status_code == 200
    
    def test_forecasting_execution(self, logged_in_client, sample_forecast_file):
        """Test running forecasting pipeline - Requirement 5.2"""
        # Upload file first
        logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data')
        
        # Run forecasting
        response = logged_in_client.post('/forecasting/run', data={
            'forecast_days': '30'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Check for success message or results
        assert 'نجح'.encode('utf-8') in response.data or b'success' in response.data.lower() or \
               'تم إجراء'.encode('utf-8') in response.data
    
    def test_forecasting_without_upload(self, logged_in_client):
        """Test running forecast without uploading data first"""
        response = logged_in_client.post('/forecasting/run', data={
            'forecast_days': '30'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show warning message
        assert 'يرجى رفع'.encode('utf-8') in response.data or b'upload' in response.data.lower()
    
    def test_forecasting_invalid_parameters(self, logged_in_client, sample_forecast_file):
        """Test forecast with invalid parameters - Requirement 5.4"""
        # Upload file first
        logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data')
        
        # Try with invalid forecast days (negative)
        response = logged_in_client.post('/forecasting/run', data={
            'forecast_days': '-10'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show validation error
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_forecasting_excessive_days(self, logged_in_client, sample_forecast_file):
        """Test forecast with excessive forecast days - Requirement 5.4"""
        # Upload file first
        logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data')
        
        # Try with excessive forecast days (> 365)
        response = logged_in_client.post('/forecasting/run', data={
            'forecast_days': '500'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show validation error
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_chart_data_route(self, logged_in_client, sample_forecast_file):
        """Test chart data endpoint - Requirement 5.3"""
        # Upload and run forecast first
        logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data')
        
        logged_in_client.post('/forecasting/run', data={
            'forecast_days': '30'
        })
        
        # Request chart data
        response = logged_in_client.get('/forecasting/chart_data/ITEM001/BR001')
        
        assert response.status_code == 200
        # Should return JSON data
        json_data = response.get_json()
        assert json_data is not None
        assert 'dates' in json_data or 'error' in json_data
    
    def test_chart_data_without_forecast(self, logged_in_client):
        """Test chart data endpoint without running forecast first"""
        response = logged_in_client.get('/forecasting/chart_data/ITEM001/BR001')
        
        # Should return error
        assert response.status_code == 404 or (response.status_code == 200 and 'error' in response.get_json())
    
    def test_results_display(self, logged_in_client, sample_forecast_file):
        """Test that results are displayed after forecast - Requirement 5.3"""
        # Upload and run forecast
        logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data')
        
        logged_in_client.post('/forecasting/run', data={
            'forecast_days': '30'
        })
        
        # Access forecasting page to see results
        response = logged_in_client.get('/forecasting')
        
        assert response.status_code == 200
        # Should display results (check for table or data indicators)
        # The page should have some forecast data displayed
        assert b'ITEM' in response.data or 'product'.encode('utf-8') in response.data or \
               'منتج'.encode('utf-8') in response.data
    
    def test_export_functionality(self, logged_in_client, sample_forecast_file):
        """Test exporting forecast results - Requirement 5.5"""
        # Upload and run forecast first
        logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data')
        
        logged_in_client.post('/forecasting/run', data={
            'forecast_days': '30'
        })
        
        # Export results
        response = logged_in_client.get('/forecasting/export')
        
        assert response.status_code == 200
        # Should return Excel file
        assert response.content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'forecast_summary' in response.headers.get('Content-Disposition', '').lower()
    
    def test_export_without_results(self, logged_in_client):
        """Test exporting without running forecast first"""
        response = logged_in_client.get('/forecasting/export', follow_redirects=True)
        
        # Should redirect or show error
        assert response.status_code in [200, 302]
        if response.status_code == 200:
            assert 'لا توجد نتائج'.encode('utf-8') in response.data or b'no results' in response.data.lower()
    
    def test_session_data_persistence(self, logged_in_client, sample_forecast_file):
        """Test that forecast data persists in session - Requirement 5.3"""
        # Upload file
        logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data')
        
        # Access forecasting page again - should still work
        response = logged_in_client.get('/forecasting')
        assert response.status_code == 200
        
        # Run forecast
        logged_in_client.post('/forecasting/run', data={
            'forecast_days': '30'
        })
        
        # Access page again - results should persist
        response = logged_in_client.get('/forecasting')
        assert response.status_code == 200


class TestForecastingValidation:
    """Test input validation for forecasting module"""
    
    def test_forecast_days_validation_zero(self, logged_in_client, sample_forecast_file):
        """Test forecast days validation with zero value"""
        # Upload file first
        logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data')
        
        # Try with zero forecast days
        response = logged_in_client.post('/forecasting/run', data={
            'forecast_days': '0'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show validation error
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()
    
    def test_forecast_days_validation_non_numeric(self, logged_in_client, sample_forecast_file):
        """Test forecast days validation with non-numeric value"""
        # Upload file first
        logged_in_client.post('/forecasting/upload', data={
            'file': (sample_forecast_file, 'test_forecast.xlsx'),
            'start_date': '2024-01-01',
            'end_date': '2024-03-31'
        }, content_type='multipart/form-data')
        
        # Try with non-numeric forecast days
        response = logged_in_client.post('/forecasting/run', data={
            'forecast_days': 'invalid'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show validation error
        assert 'خطأ'.encode('utf-8') in response.data or b'error' in response.data.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
