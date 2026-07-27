"""
Comprehensive logging configuration for the data upload system.

Provides structured logging for all upload operations, performance monitoring
for large file uploads, and diagnostic capabilities for troubleshooting.

Requirements: 4.1, 4.2, 4.3, 4.4
"""

import logging
import logging.handlers
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs for better parsing and analysis.
    """
    
    def format(self, record):
        # Create base log entry
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)
        
        return json.dumps(log_entry, ensure_ascii=False)


class PerformanceLogger:
    """
    Logger for performance monitoring of upload operations.
    """
    
    def __init__(self, logger_name: str = 'performance'):
        self.logger = logging.getLogger(logger_name)
    
    def log_upload_performance(self, username: str, filename: str, file_size: int, 
                             processing_time: float, memory_usage: Optional[float] = None):
        """
        Log performance metrics for file upload operations.
        
        Args:
            username: User performing the upload
            filename: Name of uploaded file
            file_size: Size of file in bytes
            processing_time: Time taken to process in seconds
            memory_usage: Memory usage in MB (optional)
        """
        perf_data = {
            'event': 'upload_performance',
            'username': username,
            'filename': filename,
            'file_size_bytes': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'processing_time_seconds': round(processing_time, 3),
            'processing_time_ms': round(processing_time * 1000, 1)
        }
        
        if memory_usage is not None:
            perf_data['memory_usage_mb'] = round(memory_usage, 2)
        
        # Determine log level based on performance
        if file_size > 10 * 1024 * 1024:  # Files > 10MB
            level = logging.WARNING if processing_time > 10 else logging.INFO
        else:
            level = logging.INFO
        
        self.logger.log(level, "Upload performance metrics", extra={'extra_data': perf_data})
    
    def log_database_performance(self, operation: str, query_time: float, 
                               transaction_time: float, records_processed: int):
        """
        Log database operation performance.
        
        Args:
            operation: Database operation name
            query_time: Time for queries in seconds
            transaction_time: Time for transaction in seconds
            records_processed: Number of records processed
        """
        db_perf = {
            'event': 'database_performance',
            'operation': operation,
            'query_time_ms': round(query_time * 1000, 1),
            'transaction_time_ms': round(transaction_time * 1000, 1),
            'total_time_ms': round((query_time + transaction_time) * 1000, 1),
            'records_processed': records_processed,
            'records_per_second': round(records_processed / (query_time + transaction_time), 1) if (query_time + transaction_time) > 0 else 0
        }
        
        # Log as warning if operation is slow
        level = logging.WARNING if (query_time + transaction_time) > 5 else logging.INFO
        
        self.logger.log(level, "Database performance metrics", extra={'extra_data': db_perf})


class UploadLogger:
    """
    Specialized logger for upload operations with structured logging.
    """
    
    def __init__(self, logger_name: str = 'upload_operations'):
        self.logger = logging.getLogger(logger_name)
    
    def log_upload_start(self, username: str, branch_name: str, filename: str, file_size: int):
        """Log the start of an upload operation."""
        upload_data = {
            'event': 'upload_start',
            'username': username,
            'branch_name': branch_name,
            'filename': filename,
            'file_size_bytes': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.info("Upload operation started", extra={'extra_data': upload_data})
    
    def log_upload_success(self, username: str, branch_name: str, filename: str, 
                          file_id: int, sales_records: int, inventory_records: int, 
                          processing_time: float):
        """Log successful upload completion."""
        success_data = {
            'event': 'upload_success',
            'username': username,
            'branch_name': branch_name,
            'filename': filename,
            'file_id': file_id,
            'sales_records': sales_records,
            'inventory_records': inventory_records,
            'processing_time_ms': round(processing_time * 1000, 1),
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.info("Upload completed successfully", extra={'extra_data': success_data})
    
    def log_upload_failure(self, username: str, branch_name: str, filename: str, 
                          error_type: str, error_message: str, validation_details: Optional[Dict] = None):
        """Log upload failure with detailed error information."""
        failure_data = {
            'event': 'upload_failure',
            'username': username,
            'branch_name': branch_name,
            'filename': filename,
            'error_type': error_type,
            'error_message': error_message,
            'timestamp': datetime.now().isoformat()
        }
        
        if validation_details:
            failure_data['validation_details'] = validation_details
        
        self.logger.error("Upload operation failed", extra={'extra_data': failure_data})
    
    def log_validation_error(self, username: str, filename: str, validation_type: str, 
                           error_details: Dict[str, Any]):
        """Log validation errors with detailed context."""
        validation_data = {
            'event': 'validation_error',
            'username': username,
            'filename': filename,
            'validation_type': validation_type,
            'error_details': error_details,
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.warning("Validation error occurred", extra={'extra_data': validation_data})


def setup_logging(log_level: str = 'INFO', log_dir: str = 'logs') -> Dict[str, logging.Logger]:
    """
    Set up comprehensive logging configuration for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files
    
    Returns:
        Dictionary of configured loggers
    """
    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler with human-readable format
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    
    # File handler for general application logs (human-readable)
    app_log_file = os.path.join(log_dir, 'flask_app.log')
    app_file_handler = logging.handlers.RotatingFileHandler(
        app_log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    app_file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    app_file_handler.setFormatter(app_file_formatter)
    app_file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(app_file_handler)
    
    # Structured JSON log handler for upload operations
    upload_log_file = os.path.join(log_dir, 'upload_operations.jsonl')
    upload_file_handler = logging.handlers.RotatingFileHandler(
        upload_log_file, maxBytes=50*1024*1024, backupCount=10, encoding='utf-8'
    )
    upload_file_handler.setFormatter(StructuredFormatter())
    upload_file_handler.setLevel(logging.DEBUG)
    
    # Performance monitoring log file
    perf_log_file = os.path.join(log_dir, 'performance.jsonl')
    perf_file_handler = logging.handlers.RotatingFileHandler(
        perf_log_file, maxBytes=20*1024*1024, backupCount=5, encoding='utf-8'
    )
    perf_file_handler.setFormatter(StructuredFormatter())
    perf_file_handler.setLevel(logging.INFO)
    
    # Error-only log file
    error_log_file = os.path.join(log_dir, 'errors.log')
    error_file_handler = logging.handlers.RotatingFileHandler(
        error_log_file, maxBytes=10*1024*1024, backupCount=10, encoding='utf-8'
    )
    error_file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s\n%(exc_text)s'
    )
    error_file_handler.setFormatter(error_file_formatter)
    error_file_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_file_handler)
    
    # Configure specialized loggers
    upload_logger = logging.getLogger('upload_operations')
    upload_logger.addHandler(upload_file_handler)
    upload_logger.setLevel(logging.DEBUG)
    upload_logger.propagate = True  # Also send to root logger
    
    perf_logger = logging.getLogger('performance')
    perf_logger.addHandler(perf_file_handler)
    perf_logger.setLevel(logging.INFO)
    perf_logger.propagate = True
    
    # Configure Flask app logger
    flask_logger = logging.getLogger('flask_app')
    flask_logger.setLevel(logging.INFO)
    
    # Configure data store logger
    data_store_logger = logging.getLogger('data_store')
    data_store_logger.setLevel(logging.DEBUG)
    
    return {
        'root': root_logger,
        'upload': upload_logger,
        'performance': perf_logger,
        'flask_app': flask_logger,
        'data_store': data_store_logger
    }


def performance_monitor(operation_name: str):
    """
    Decorator to monitor performance of functions.
    
    Args:
        operation_name: Name of the operation being monitored
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            perf_logger = PerformanceLogger()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                processing_time = end_time - start_time
                
                # Log performance metrics
                perf_data = {
                    'event': 'function_performance',
                    'operation': operation_name,
                    'function': func.__name__,
                    'processing_time_ms': round(processing_time * 1000, 1),
                    'success': True
                }
                
                perf_logger.logger.info("Function performance", extra={'extra_data': perf_data})
                return result
                
            except Exception as e:
                end_time = time.time()
                processing_time = end_time - start_time
                
                # Log performance metrics for failed operations
                perf_data = {
                    'event': 'function_performance',
                    'operation': operation_name,
                    'function': func.__name__,
                    'processing_time_ms': round(processing_time * 1000, 1),
                    'success': False,
                    'error': str(e)
                }
                
                perf_logger.logger.warning("Function performance (failed)", extra={'extra_data': perf_data})
                raise
        
        return wrapper
    return decorator


def get_memory_usage():
    """
    Get current memory usage in MB.
    
    Returns:
        Memory usage in MB or None if unavailable
    """
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return memory_info.rss / (1024 * 1024)  # Convert to MB
    except ImportError:
        return None
    except Exception:
        return None


# Initialize logging when module is imported
_loggers = None

def get_loggers():
    """Get configured loggers, initializing if necessary."""
    global _loggers
    if _loggers is None:
        _loggers = setup_logging()
    return _loggers


def get_upload_logger():
    """Get the upload operations logger."""
    return UploadLogger()


def get_performance_logger():
    """Get the performance monitoring logger."""
    return PerformanceLogger()