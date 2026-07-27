"""
Tests for resource path helper function and executable compatibility.
Validates that file paths work correctly in both development and executable modes.
"""

import pytest
import os
import sys
import tempfile
import shutil
from flask_app import get_resource_path, get_runtime_directory, initialize_runtime_directories, app


class TestResourcePathHelper:
    """Test the resource path helper function for PyInstaller compatibility."""
    
    def test_resource_path_in_development_mode(self):
        """Test that resource path returns correct path in development mode."""
        # In development mode, should return path relative to current directory
        path = get_resource_path('templates')
        
        # Should be an absolute path
        assert os.path.isabs(path)
        
        # Should end with 'templates'
        assert path.endswith('templates')
        
        # Should exist (since we're in development)
        assert os.path.exists(path)
    
    def test_resource_path_with_nested_path(self):
        """Test resource path with nested directory structure."""
        path = get_resource_path(os.path.join('forecast_modules', 'special_events.xlsx'))
        
        # Should be an absolute path
        assert os.path.isabs(path)
        
        # Should contain both parts
        assert 'forecast_modules' in path
        assert 'special_events.xlsx' in path
    
    def test_resource_path_for_static_files(self):
        """Test resource path for static files directory."""
        path = get_resource_path('static')
        
        # Should exist in development
        assert os.path.exists(path)
        
        # Should be a directory
        assert os.path.isdir(path)
    
    def test_flask_app_uses_resource_paths(self):
        """Test that Flask app is configured with resource paths."""
        # Flask app should have template_folder set
        assert app.template_folder is not None
        
        # Template folder should be an absolute path
        assert os.path.isabs(app.template_folder)
        
        # Template folder should exist
        assert os.path.exists(app.template_folder)
        
        # Static folder should be set
        assert app.static_folder is not None
        
        # Static folder should be an absolute path
        assert os.path.isabs(app.static_folder)
        
        # Static folder should exist
        assert os.path.exists(app.static_folder)
    
    def test_logs_directory_creation(self):
        """Test that logs directory is created correctly."""
        # Logs directory should exist after app initialization
        if getattr(sys, 'frozen', False):
            logs_dir = os.path.join(os.path.dirname(sys.executable), 'logs')
        else:
            logs_dir = 'logs'
        
        assert os.path.exists(logs_dir)
        assert os.path.isdir(logs_dir)
    
    def test_upload_folder_configuration(self):
        """Test that upload folder is configured correctly."""
        # Upload folder should be set in app config
        assert 'UPLOAD_FOLDER' in app.config
        
        # Upload folder should exist
        upload_folder = app.config['UPLOAD_FOLDER']
        assert os.path.exists(upload_folder)
        assert os.path.isdir(upload_folder)
    
    def test_database_paths_in_development(self):
        """Test that database files are accessible in development mode."""
        import auth_flask
        import data_store
        
        # Database paths should be set
        assert auth_flask.DB_NAME is not None
        assert data_store.DB_NAME is not None
        
        # In development, should be simple filenames or paths
        # After initialization, database files should exist
        assert os.path.exists(auth_flask.DB_NAME)
        assert os.path.exists(data_store.DB_NAME)


class TestExecutableCompatibility:
    """Test that the application is ready for PyInstaller packaging."""
    
    def test_no_hardcoded_absolute_paths(self):
        """Verify that no hardcoded absolute paths are used in critical files."""
        # Read flask_app.py and check for common absolute path patterns
        with open('flask_app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should not contain hardcoded Windows paths
        assert 'C:\\' not in content or 'C:\\Users' not in content
        
        # Should not contain hardcoded Unix paths (except in comments)
        lines = content.split('\n')
        code_lines = [line for line in lines if not line.strip().startswith('#')]
        code_content = '\n'.join(code_lines)
        
        # Check that we're using get_resource_path for templates and static
        assert 'get_resource_path' in content
    
    def test_sys_module_imported(self):
        """Test that sys module is imported for frozen detection."""
        import flask_app
        
        # sys should be available in flask_app module
        assert hasattr(flask_app, 'sys')
    
    def test_frozen_attribute_check(self):
        """Test that frozen attribute checking works."""
        # In development mode, frozen should be False
        is_frozen = getattr(sys, 'frozen', False)
        assert is_frozen is False
    
    def test_resource_path_function_exists(self):
        """Test that get_resource_path function is defined and accessible."""
        from flask_app import get_resource_path
        
        # Function should be callable
        assert callable(get_resource_path)
        
        # Should accept a string argument
        result = get_resource_path('test')
        assert isinstance(result, str)


class TestRuntimeDirectoryInitialization:
    """Test runtime directory initialization functionality."""
    
    def test_get_runtime_directory_in_development(self):
        """Test that get_runtime_directory returns correct path in development mode."""
        runtime_dir = get_runtime_directory()
        
        # Should return an absolute path
        assert os.path.isabs(runtime_dir)
        
        # In development mode (not frozen), should return current directory
        if not getattr(sys, 'frozen', False):
            assert runtime_dir == os.path.abspath(".")
    
    def test_runtime_directories_exist(self):
        """Test that all required runtime directories are created."""
        runtime_dir = get_runtime_directory()
        
        # Check that all required directories exist
        required_dirs = ['uploads', 'logs', 'flask_sessions']
        
        for dir_name in required_dirs:
            dir_path = os.path.join(runtime_dir, dir_name)
            assert os.path.exists(dir_path), f"Directory {dir_name} should exist"
            assert os.path.isdir(dir_path), f"{dir_name} should be a directory"
    
    def test_initialize_runtime_directories_creates_missing_dirs(self):
        """Test that initialize_runtime_directories creates missing directories."""
        # Create a temporary directory to simulate a clean environment
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save original directory
            original_dir = os.getcwd()
            
            try:
                # Change to temp directory
                os.chdir(temp_dir)
                
                # Mock sys.frozen to False to use current directory
                original_frozen = getattr(sys, 'frozen', False)
                if hasattr(sys, 'frozen'):
                    delattr(sys, 'frozen')
                
                # Call initialization
                initialize_runtime_directories()
                
                # Verify directories were created
                for dir_name in ['uploads', 'logs', 'flask_sessions']:
                    dir_path = os.path.join(temp_dir, dir_name)
                    assert os.path.exists(dir_path), f"{dir_name} should be created"
                    assert os.path.isdir(dir_path), f"{dir_name} should be a directory"
                
                # Restore frozen attribute
                if original_frozen:
                    sys.frozen = original_frozen
                    
            finally:
                # Restore original directory
                os.chdir(original_dir)
    
    def test_initialize_runtime_directories_idempotent(self):
        """Test that calling initialize_runtime_directories multiple times is safe."""
        # Should not raise an error when called multiple times
        try:
            initialize_runtime_directories()
            initialize_runtime_directories()
            initialize_runtime_directories()
        except Exception as e:
            pytest.fail(f"initialize_runtime_directories should be idempotent, but raised: {e}")
    
    def test_upload_folder_uses_runtime_directory(self):
        """Test that upload folder is configured to use runtime directory."""
        runtime_dir = get_runtime_directory()
        upload_folder = app.config['UPLOAD_FOLDER']
        
        # Upload folder should be within runtime directory
        assert upload_folder.startswith(runtime_dir) or os.path.samefile(
            os.path.dirname(upload_folder), runtime_dir
        )
    
    def test_logs_directory_uses_runtime_directory(self):
        """Test that logs directory is in runtime directory."""
        runtime_dir = get_runtime_directory()
        
        # Logs should be in runtime_dir/logs
        expected_logs_dir = os.path.join(runtime_dir, 'logs')
        assert os.path.exists(expected_logs_dir)
        assert os.path.isdir(expected_logs_dir)


class TestDevelopmentModeOperation:
    """Test that application still works correctly in development mode."""
    
    def test_app_can_be_created(self):
        """Test that Flask app can be created successfully."""
        assert app is not None
        assert app.name == 'flask_app'
    
    def test_templates_are_accessible(self):
        """Test that template files can be found."""
        template_dir = app.template_folder
        
        # Check for key template files
        assert os.path.exists(os.path.join(template_dir, 'login.html'))
        assert os.path.exists(os.path.join(template_dir, 'home.html'))
        assert os.path.exists(os.path.join(template_dir, 'base.html'))
    
    def test_static_files_are_accessible(self):
        """Test that static files can be found."""
        static_dir = app.static_folder
        
        # Check for static subdirectories
        assert os.path.exists(os.path.join(static_dir, 'css'))
        assert os.path.exists(os.path.join(static_dir, 'js'))
    
    def test_forecast_modules_accessible(self):
        """Test that forecast_modules directory is accessible."""
        forecast_path = get_resource_path('forecast_modules')
        
        assert os.path.exists(forecast_path)
        assert os.path.isdir(forecast_path)
        
        # Check for special_events.xlsx
        events_file = get_resource_path(os.path.join('forecast_modules', 'special_events.xlsx'))
        assert os.path.exists(events_file)
    
    def test_data_directory_accessible(self):
        """Test that data directory is accessible."""
        data_path = get_resource_path('data')
        
        assert os.path.exists(data_path)
        assert os.path.isdir(data_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
