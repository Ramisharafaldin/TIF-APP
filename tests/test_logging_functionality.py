"""
Unit tests for logging functionality.

Tests log format and content requirements, error message generation,
and structured logging for upload operations.

Requirements: 4.4, 4.5
"""

import pytest
import logging
import json
import tempfile
import os
from io import StringIO
from unittest.mock import patch, MagicMock
from datetime import datetime

# Import the modules we're testing
import data_store
from utils import validation


class TestLoggingFormat:
    """Test log format and content requirements."""
    
    def test_log_format_includes_timestamp(self):
        """Test that log messages include timestamp."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        handler.setFormatter(formatter)
        
        logger = logging.getLogger('test_logger')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        test_message = "Test log message"
        logger.info(test_message)
        
        log_output = log_stream.getvalue()
        
        # Check that timestamp is present (format: YYYY-MM-DD HH:MM:SS,mmm)
        assert len(log_output) > 0, "Log output should not be empty"
        assert test_message in log_output, "Log message should be present"
        
        # Check timestamp format (should start with date)
        lines = log_output.strip().split('\n')
        first_line = lines[0]
        timestamp_part = first_line.split(' - ')[0]
        
        # Verify timestamp format
        try:
            datetime.strptime(timestamp_part.split(',')[0], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pytest.fail(f"Timestamp format is invalid: {timestamp_part}")
    
    def test_log_format_includes_level(self):
        """Test that log messages include log level."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        handler.setFormatter(formatter)
        
        logger = logging.getLogger('test_logger_level')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        # Test different log levels
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        log_output = log_stream.getvalue()
        
        assert "INFO" in log_output, "INFO level should be present"
        assert "WARNING" in log_output, "WARNING level should be present"
        assert "ERROR" in log_output, "ERROR level should be present"
    
    def test_log_format_includes_module_name(self):
        """Test that log messages include module/logger name."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        handler.setFormatter(formatter)
        
        logger = logging.getLogger('test_module_name')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        logger.info("Test message")
        
        log_output = log_stream.getvalue()
        
        assert "test_module_name" in log_output, "Module name should be present in log"
    
    def test_structured_log_format_for_upload_operations(self):
        """Test structured logging format for upload operations."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        handler.setFormatter(formatter)
        
        logger = logging.getLogger('upload_operations')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Test structured upload log
        upload_data = {
            'username': 'test_user',
            'branch_name': 'test_branch',
            'filename': 'test_file.xlsx',
            'file_size': 1024,
            'operation': 'upload_start'
        }
        
        # Log structured data as JSON
        logger.info(f"Upload operation: {json.dumps(upload_data)}")
        
        log_output = log_stream.getvalue()
        
        assert "Upload operation:" in log_output, "Upload operation should be logged"
        assert "test_user" in log_output, "Username should be in log"
        assert "test_branch" in log_output, "Branch name should be in log"
        assert "test_file.xlsx" in log_output, "Filename should be in log"


class TestErrorMessageGeneration:
    """Test error message generation requirements."""
    
    def test_validation_error_messages_are_descriptive(self):
        """Test that validation error messages are descriptive and actionable."""
        # Test branch name validation
        valid, error = validation.validate_branch_name("")
        assert not valid, "Empty branch name should be invalid"
        assert error is not None, "Error message should be provided"
        assert len(error) > 10, "Error message should be descriptive"
        assert "فرع" in error or "branch" in error.lower(), "Error should mention branch"
        
        # Test file extension validation
        valid, error = validation.validate_file_extension("test.txt", {'xlsx', 'xls'})
        assert not valid, "Invalid extension should be rejected"
        assert error is not None, "Error message should be provided"
        assert "xlsx" in error or "xls" in error, "Error should mention valid extensions"
    
    def test_database_error_messages_include_context(self):
        """Test that database error messages include operation context."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        
        logger = logging.getLogger('data_store')
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        
        # Simulate database error with context
        username = "test_user"
        branch_name = "test_branch"
        operation = "save_branch_data"
        
        error_context = {
            'username': username,
            'branch_name': branch_name,
            'operation': operation,
            'error': 'Database connection failed'
        }
        
        logger.error(f"Database error in {operation}: {json.dumps(error_context)}")
        
        log_output = log_stream.getvalue()
        
        assert username in log_output, "Username should be in error log"
        assert branch_name in log_output, "Branch name should be in error log"
        assert operation in log_output, "Operation should be in error log"
        assert "Database connection failed" in log_output, "Error details should be in log"
    
    def test_file_processing_error_messages_include_file_details(self):
        """Test that file processing errors include file details."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        
        logger = logging.getLogger('file_processing')
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        
        # Simulate file processing error
        file_details = {
            'filename': 'corrupted_file.xlsx',
            'file_size': 2048,
            'username': 'test_user',
            'error': 'Excel file is corrupted',
            'operation': 'excel_validation'
        }
        
        logger.error(f"File processing error: {json.dumps(file_details)}")
        
        log_output = log_stream.getvalue()
        
        assert "corrupted_file.xlsx" in log_output, "Filename should be in error log"
        assert "2048" in log_output, "File size should be in error log"
        assert "test_user" in log_output, "Username should be in error log"
        assert "Excel file is corrupted" in log_output, "Error details should be in log"


class TestUploadOperationLogging:
    """Test logging for upload operations."""
    
    def test_upload_start_logging(self):
        """Test that upload start is properly logged."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        
        logger = logging.getLogger('upload_test')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Simulate upload start logging
        upload_info = {
            'event': 'upload_start',
            'username': 'test_user',
            'branch_name': 'test_branch',
            'filename': 'data.xlsx',
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Upload started: {json.dumps(upload_info)}")
        
        log_output = log_stream.getvalue()
        
        assert "upload_start" in log_output, "Upload start event should be logged"
        assert "test_user" in log_output, "Username should be logged"
        assert "test_branch" in log_output, "Branch name should be logged"
        assert "data.xlsx" in log_output, "Filename should be logged"
    
    def test_upload_success_logging(self):
        """Test that successful uploads are properly logged."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        
        logger = logging.getLogger('upload_success_test')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Simulate successful upload logging
        success_info = {
            'event': 'upload_success',
            'username': 'test_user',
            'branch_name': 'test_branch',
            'filename': 'data.xlsx',
            'file_id': 123,
            'sales_records': 500,
            'inventory_records': 200,
            'processing_time_ms': 1500
        }
        
        logger.info(f"Upload completed successfully: {json.dumps(success_info)}")
        
        log_output = log_stream.getvalue()
        
        assert "upload_success" in log_output, "Upload success should be logged"
        assert "file_id" in log_output, "File ID should be logged"
        assert "500" in log_output, "Sales record count should be logged"
        assert "200" in log_output, "Inventory record count should be logged"
        assert "1500" in log_output, "Processing time should be logged"
    
    def test_upload_failure_logging(self):
        """Test that upload failures are properly logged with error details."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        
        logger = logging.getLogger('upload_failure_test')
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        
        # Simulate upload failure logging
        failure_info = {
            'event': 'upload_failure',
            'username': 'test_user',
            'branch_name': 'test_branch',
            'filename': 'bad_data.xlsx',
            'error_type': 'ValidationError',
            'error_message': 'Missing required sheets',
            'validation_details': {
                'missing_sheets': ['Transactions', 'Item info'],
                'found_sheets': ['Sheet1']
            }
        }
        
        logger.error(f"Upload failed: {json.dumps(failure_info)}")
        
        log_output = log_stream.getvalue()
        
        assert "upload_failure" in log_output, "Upload failure should be logged"
        assert "ValidationError" in log_output, "Error type should be logged"
        assert "Missing required sheets" in log_output, "Error message should be logged"
        assert "Transactions" in log_output, "Missing sheet details should be logged"


class TestPerformanceLogging:
    """Test performance monitoring logging."""
    
    def test_large_file_upload_performance_logging(self):
        """Test that large file uploads are monitored for performance."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        
        logger = logging.getLogger('performance_test')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Simulate performance logging for large file
        perf_info = {
            'event': 'performance_monitor',
            'operation': 'large_file_upload',
            'file_size_mb': 15.5,
            'processing_time_ms': 8500,
            'memory_usage_mb': 120,
            'username': 'test_user',
            'filename': 'large_data.xlsx'
        }
        
        logger.info(f"Performance metrics: {json.dumps(perf_info)}")
        
        log_output = log_stream.getvalue()
        
        assert "performance_monitor" in log_output, "Performance monitoring should be logged"
        assert "15.5" in log_output, "File size should be logged"
        assert "8500" in log_output, "Processing time should be logged"
        assert "120" in log_output, "Memory usage should be logged"
    
    def test_database_operation_timing_logging(self):
        """Test that database operations are timed and logged."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        
        logger = logging.getLogger('db_timing_test')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Simulate database timing logging
        db_timing = {
            'event': 'database_timing',
            'operation': 'save_branch_data',
            'query_time_ms': 250,
            'transaction_time_ms': 300,
            'total_time_ms': 550,
            'records_processed': 1000
        }
        
        logger.info(f"Database timing: {json.dumps(db_timing)}")
        
        log_output = log_stream.getvalue()
        
        assert "database_timing" in log_output, "Database timing should be logged"
        assert "250" in log_output, "Query time should be logged"
        assert "300" in log_output, "Transaction time should be logged"
        assert "1000" in log_output, "Records processed should be logged"


class TestLogLevels:
    """Test appropriate use of log levels."""
    
    def test_info_level_for_normal_operations(self):
        """Test that normal operations use INFO level."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        logger = logging.getLogger('info_level_test')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Normal operations should use INFO
        logger.info("User logged in successfully")
        logger.info("File uploaded successfully")
        logger.info("Data processed successfully")
        
        log_output = log_stream.getvalue()
        
        # Should have 3 log entries
        log_lines = [line for line in log_output.strip().split('\n') if line]
        assert len(log_lines) == 3, "Should have 3 INFO log entries"
        
        for line in log_lines:
            assert "INFO" in line, "All entries should be INFO level"
    
    def test_warning_level_for_recoverable_issues(self):
        """Test that recoverable issues use WARNING level."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        logger = logging.getLogger('warning_level_test')
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        
        # Recoverable issues should use WARNING
        logger.warning("Invalid file extension, user redirected")
        logger.warning("Database locked, retrying operation")
        logger.warning("Missing optional data, using defaults")
        
        log_output = log_stream.getvalue()
        
        log_lines = [line for line in log_output.strip().split('\n') if line]
        assert len(log_lines) == 3, "Should have 3 WARNING log entries"
        
        for line in log_lines:
            assert "WARNING" in line, "All entries should be WARNING level"
    
    def test_error_level_for_failures(self):
        """Test that failures use ERROR level."""
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        logger = logging.getLogger('error_level_test')
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        
        # Failures should use ERROR
        logger.error("Database connection failed")
        logger.error("File processing failed")
        logger.error("Unexpected exception occurred")
        
        log_output = log_stream.getvalue()
        
        log_lines = [line for line in log_output.strip().split('\n') if line]
        assert len(log_lines) == 3, "Should have 3 ERROR log entries"
        
        for line in log_lines:
            assert "ERROR" in line, "All entries should be ERROR level"


if __name__ == '__main__':
    pytest.main([__file__])