"""
Resource Management Utilities for Export Operations

This module provides context managers and utilities for proper resource cleanup
during export operations, including file operations, memory management, and
temporary file cleanup.

**Validates: Requirements 6.5**
"""

import os
import tempfile
import logging
import gc
from contextlib import contextmanager
from io import BytesIO
from typing import Optional, Generator, Any
import threading
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Try to import psutil, but handle gracefully if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

logger = logging.getLogger(__name__)

class ResourceMonitor:
    """Monitor system resources during export operations."""
    
    def __init__(self, memory_threshold_mb: int = 500, memory_critical_mb: int = 1000):
        self.memory_threshold_mb = memory_threshold_mb
        self.memory_critical_mb = memory_critical_mb  # Critical threshold for immediate action
        self.initial_memory = None
        self.peak_memory = 0
        self.memory_samples = []  # Track memory usage over time
        self.start_time = None
        
    def start_monitoring(self):
        """Start monitoring system resources."""
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil not available, memory monitoring disabled")
            self.initial_memory = 0
            self.start_time = datetime.now()
            return
            
        try:
            process = psutil.Process()
            self.initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            self.peak_memory = self.initial_memory
            self.start_time = datetime.now()
            self.memory_samples = [(self.start_time, self.initial_memory)]
            logger.debug(f"Resource monitoring started. Initial memory: {self.initial_memory:.2f} MB")
        except Exception as e:
            logger.warning(f"Failed to start resource monitoring: {e}")
            self.initial_memory = 0
            self.start_time = datetime.now()
    
    def check_memory_usage(self) -> tuple[bool, dict]:
        """
        Check if memory usage is within acceptable limits.
        
        Returns:
            (is_within_limits, memory_info)
        """
        if not PSUTIL_AVAILABLE:
            return True, {'status': 'monitoring_unavailable'}
            
        try:
            process = psutil.Process()
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            self.peak_memory = max(self.peak_memory, current_memory)
            
            # Track memory samples for trend analysis
            current_time = datetime.now()
            self.memory_samples.append((current_time, current_memory))
            
            # Keep only last 10 samples for trend analysis
            if len(self.memory_samples) > 10:
                self.memory_samples = self.memory_samples[-10:]
            
            # Calculate memory growth rate
            memory_growth_rate = 0
            if len(self.memory_samples) >= 2:
                time_diff = (self.memory_samples[-1][0] - self.memory_samples[0][0]).total_seconds()
                if time_diff > 0:
                    memory_diff = self.memory_samples[-1][1] - self.memory_samples[0][1]
                    memory_growth_rate = memory_diff / time_diff  # MB per second
            
            memory_info = {
                'current_memory_mb': current_memory,
                'peak_memory_mb': self.peak_memory,
                'initial_memory_mb': self.initial_memory or 0,
                'memory_increase_mb': current_memory - (self.initial_memory or 0),
                'memory_growth_rate_mb_per_sec': memory_growth_rate,
                'threshold_mb': self.memory_threshold_mb,
                'critical_threshold_mb': self.memory_critical_mb
            }
            
            # Check critical threshold first
            if current_memory > self.memory_critical_mb:
                logger.error(f"Critical memory usage exceeded: {current_memory:.2f} MB > {self.memory_critical_mb} MB")
                memory_info['status'] = 'critical'
                return False, memory_info
            
            # Check warning threshold
            if current_memory > self.memory_threshold_mb:
                logger.warning(f"Memory usage exceeded threshold: {current_memory:.2f} MB > {self.memory_threshold_mb} MB")
                memory_info['status'] = 'warning'
                return False, memory_info
            
            # Check rapid memory growth
            if memory_growth_rate > 10:  # More than 10 MB/sec growth
                logger.warning(f"Rapid memory growth detected: {memory_growth_rate:.2f} MB/sec")
                memory_info['status'] = 'rapid_growth'
                return False, memory_info
            
            memory_info['status'] = 'ok'
            return True, memory_info
            
        except Exception as e:
            logger.warning(f"Failed to check memory usage: {e}")
            return True, {'status': 'check_failed', 'error': str(e)}
    
    def get_system_memory_info(self) -> dict:
        """Get system-wide memory information."""
        if not PSUTIL_AVAILABLE:
            return {'available': False}
            
        try:
            system_memory = psutil.virtual_memory()
            return {
                'available': True,
                'total_gb': system_memory.total / 1024 / 1024 / 1024,
                'available_gb': system_memory.available / 1024 / 1024 / 1024,
                'used_percent': system_memory.percent,
                'free_gb': system_memory.free / 1024 / 1024 / 1024
            }
        except Exception as e:
            logger.warning(f"Failed to get system memory info: {e}")
            return {'available': False, 'error': str(e)}
    
    def estimate_processing_time(self, data_size_mb: float) -> float:
        """
        Estimate processing time based on current performance.
        
        Args:
            data_size_mb: Size of data to process in MB
            
        Returns:
            Estimated time in seconds
        """
        if not self.start_time or len(self.memory_samples) < 2:
            # Default estimate: 1 second per MB
            return data_size_mb
        
        # Calculate processing rate based on memory growth
        elapsed_time = (datetime.now() - self.start_time).total_seconds()
        memory_processed = self.peak_memory - (self.initial_memory or 0)
        
        if elapsed_time > 0 and memory_processed > 0:
            processing_rate = memory_processed / elapsed_time  # MB per second
            if processing_rate > 0:
                return data_size_mb / processing_rate
        
        # Fallback estimate
        return data_size_mb
    
    def get_memory_stats(self) -> dict:
        """Get memory usage statistics."""
        if not PSUTIL_AVAILABLE:
            return {
                'initial_memory_mb': 0,
                'current_memory_mb': 0,
                'peak_memory_mb': 0,
                'memory_increase_mb': 0
            }
            
        try:
            process = psutil.Process()
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            return {
                'initial_memory_mb': self.initial_memory or 0,
                'current_memory_mb': current_memory,
                'peak_memory_mb': self.peak_memory,
                'memory_increase_mb': current_memory - (self.initial_memory or 0)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory stats: {e}")
            return {
                'initial_memory_mb': 0,
                'current_memory_mb': 0,
                'peak_memory_mb': 0,
                'memory_increase_mb': 0
            }

@contextmanager
def managed_bytesio(initial_data: Optional[bytes] = None) -> Generator[BytesIO, None, None]:
    """
    Context manager for BytesIO objects with automatic cleanup.
    
    Args:
        initial_data: Optional initial data to write to the BytesIO object
        
    Yields:
        BytesIO object
        
    **Validates: Requirements 6.5**
    """
    output = None
    try:
        output = BytesIO(initial_data) if initial_data else BytesIO()
        logger.debug("BytesIO object created")
        yield output
    except Exception as e:
        logger.error(f"Error in managed BytesIO: {e}")
        raise
    finally:
        if output:
            try:
                output.close()
                logger.debug("BytesIO object closed")
            except Exception as e:
                logger.warning(f"Error closing BytesIO: {e}")
        # Force garbage collection to free memory
        gc.collect()

@contextmanager
def managed_temp_file(suffix: str = '.tmp', prefix: str = 'export_') -> Generator[str, None, None]:
    """
    Context manager for temporary files with automatic cleanup.
    
    Args:
        suffix: File suffix (e.g., '.xlsx', '.pdf')
        prefix: File prefix
        
    Yields:
        Path to temporary file
        
    **Validates: Requirements 6.5**
    """
    temp_file = None
    try:
        # Create temporary file
        fd, temp_file = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)  # Close file descriptor, keep the file
        logger.debug(f"Temporary file created: {temp_file}")
        yield temp_file
    except Exception as e:
        logger.error(f"Error in managed temp file: {e}")
        raise
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                logger.debug(f"Temporary file cleaned up: {temp_file}")
            except Exception as e:
                logger.warning(f"Error cleaning up temp file {temp_file}: {e}")

@contextmanager
def resource_monitored_operation(memory_threshold_mb: int = 500, operation_name: str = "export"):
    """
    Context manager for monitoring resource usage during operations.
    
    Args:
        memory_threshold_mb: Memory threshold in MB
        operation_name: Name of the operation for logging
        
    **Validates: Requirements 6.5**
    """
    monitor = ResourceMonitor(memory_threshold_mb)
    start_time = datetime.now()
    
    try:
        monitor.start_monitoring()
        logger.info(f"Started {operation_name} operation with resource monitoring")
        yield monitor
    except MemoryError:
        logger.error(f"Memory error during {operation_name} operation")
        raise
    except Exception as e:
        logger.error(f"Error during {operation_name} operation: {e}")
        raise
    finally:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        memory_stats = monitor.get_memory_stats()
        
        logger.info(f"Completed {operation_name} operation in {duration:.2f}s. "
                   f"Memory stats: {memory_stats}")
        
        # Force garbage collection
        gc.collect()

class ExportResourceManager:
    """
    Comprehensive resource manager for export operations with timeout and fallback support.
    
    **Validates: Requirements 6.5, 5.3**
    """
    
    def __init__(self, username: str, operation_type: str, timeout_seconds: int = 300):
        self.username = username
        self.operation_type = operation_type
        self.timeout_seconds = timeout_seconds
        self.temp_files = []
        self.bytesio_objects = []
        self.monitor = ResourceMonitor()
        self.start_time = None
        self.operation_id = None
        self.fallback_mode = False
        self.processing_timeout = None
        
    def __enter__(self):
        self.start_time = datetime.now()
        self.processing_timeout = self.start_time + timedelta(seconds=self.timeout_seconds)
        self.monitor.start_monitoring()
        
        # Check system resources before starting
        system_memory = self.monitor.get_system_memory_info()
        if system_memory.get('available') and system_memory.get('used_percent', 0) > 90:
            logger.warning(f"System memory usage high ({system_memory['used_percent']:.1f}%) for {self.username}")
            self.fallback_mode = True
        
        # Start monitoring with the export monitor
        try:
            from utils.export_monitor import export_monitor
            self.operation_id = export_monitor.start_operation(self.username, self.operation_type)
        except Exception as e:
            logger.warning(f"Failed to start export monitoring: {e}")
            self.operation_id = None
        
        logger.info(f"Export resource manager started for {self.username} - {self.operation_type}, "
                   f"timeout: {self.timeout_seconds}s, fallback_mode: {self.fallback_mode}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Determine success status
        success = exc_type is None
        error_message = str(exc_val) if exc_val else None
        
        # Finish monitoring
        if self.operation_id:
            try:
                from utils.export_monitor import export_monitor
                export_monitor.finish_operation(
                    self.operation_id, 
                    success=success, 
                    error_message=error_message
                )
            except Exception as e:
                logger.warning(f"Failed to finish export monitoring: {e}")
        
        # Clean up all resources
        self.cleanup_all()
        
        # Log final statistics
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds() if self.start_time else 0
        memory_stats = self.monitor.get_memory_stats()
        
        logger.info(f"Export resource manager completed for {self.username} - {self.operation_type}. "
                   f"Duration: {duration:.2f}s, Memory stats: {memory_stats}")
        
        # Force garbage collection
        gc.collect()
    
    def create_bytesio(self, initial_data: Optional[bytes] = None) -> BytesIO:
        """Create a managed BytesIO object."""
        output = BytesIO(initial_data) if initial_data else BytesIO()
        self.bytesio_objects.append(output)
        logger.debug(f"Created BytesIO object for {self.username}")
        return output
    
    def create_temp_file(self, suffix: str = '.tmp', prefix: str = 'export_') -> str:
        """Create a managed temporary file."""
        fd, temp_file = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)
        self.temp_files.append(temp_file)
        logger.debug(f"Created temporary file for {self.username}: {temp_file}")
        return temp_file
    
    def check_memory_limits(self) -> bool:
        """
        Check if memory usage is within limits with enhanced monitoring.
        
        Returns:
            True if within limits, False if limits exceeded
        """
        memory_ok, memory_info = self.monitor.check_memory_usage()
        
        # Update monitoring system
        if self.operation_id:
            try:
                from utils.export_monitor import export_monitor
                current_memory = memory_info.get('current_memory_mb', 0)
                export_monitor.update_operation_memory(self.operation_id, current_memory)
            except Exception as e:
                logger.warning(f"Failed to update memory monitoring: {e}")
        
        # Log memory status for debugging
        if not memory_ok:
            status = memory_info.get('status', 'unknown')
            current_memory = memory_info.get('current_memory_mb', 0)
            logger.warning(f"Memory limit check failed for {self.username}: status={status}, "
                          f"current={current_memory:.2f}MB, threshold={self.monitor.memory_threshold_mb}MB")
            
            # Enable fallback mode if memory is getting tight
            if status in ['warning', 'rapid_growth']:
                self.fallback_mode = True
                logger.info(f"Enabled fallback mode for {self.username} due to memory constraints")
        
        return memory_ok
    
    def check_timeout(self) -> bool:
        """
        Check if operation has exceeded timeout.
        
        Returns:
            True if within timeout, False if timeout exceeded
        """
        if not self.processing_timeout:
            return True
            
        current_time = datetime.now()
        if current_time > self.processing_timeout:
            elapsed = (current_time - self.start_time).total_seconds()
            logger.warning(f"Operation timeout exceeded for {self.username}: {elapsed:.2f}s > {self.timeout_seconds}s")
            
            # Attempt timeout recovery
            try:
                from utils.export_fallback import ExportRecoveryManager
                recovery_info = ExportRecoveryManager.handle_timeout_recovery(
                    self.username, self.operation_type, elapsed
                )
                logger.info(f"Timeout recovery info generated for {self.username}: {recovery_info['user_message']}")
            except Exception as recovery_error:
                logger.error(f"Timeout recovery failed for {self.username}: {recovery_error}")
            
            return False
        
        return True
    
    def get_remaining_time(self) -> float:
        """Get remaining time before timeout in seconds."""
        if not self.processing_timeout:
            return float('inf')
            
        remaining = (self.processing_timeout - datetime.now()).total_seconds()
        return max(0, remaining)
    
    def should_use_fallback(self) -> bool:
        """Determine if fallback processing should be used."""
        return self.fallback_mode
    
    def estimate_data_processing_time(self, data_size_mb: float) -> float:
        """Estimate time needed to process given data size."""
        return self.monitor.estimate_processing_time(data_size_mb)
    
    def can_process_data_size(self, data_size_mb: float) -> tuple[bool, str]:
        """
        Check if we can process data of given size within constraints.
        
        Returns:
            (can_process, reason)
        """
        # Check timeout constraint
        estimated_time = self.estimate_data_processing_time(data_size_mb)
        remaining_time = self.get_remaining_time()
        
        if estimated_time > remaining_time:
            return False, f"Estimated processing time ({estimated_time:.1f}s) exceeds remaining timeout ({remaining_time:.1f}s)"
        
        # Check memory constraint
        system_memory = self.monitor.get_system_memory_info()
        if system_memory.get('available'):
            available_gb = system_memory.get('available_gb', 0)
            # Rough estimate: need 2x data size in memory for processing
            needed_gb = (data_size_mb * 2) / 1024
            
            if needed_gb > available_gb:
                return False, f"Insufficient memory: need {needed_gb:.2f}GB, available {available_gb:.2f}GB"
        
        return True, "OK"
    
    def cleanup_all(self):
        """Clean up all managed resources."""
        # Clean up BytesIO objects
        for output in self.bytesio_objects:
            try:
                output.close()
            except Exception as e:
                logger.warning(f"Error closing BytesIO for {self.username}: {e}")
        self.bytesio_objects.clear()
        
        # Clean up temporary files
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temp file for {self.username}: {temp_file}")
            except Exception as e:
                logger.warning(f"Error cleaning up temp file for {self.username} - {temp_file}: {e}")
        self.temp_files.clear()

# Rate limiting utilities
class ExportRateLimiter:
    """
    Rate limiter for export operations to prevent system overload.
    
    **Validates: Requirements 5.5**
    """
    
    def __init__(self, max_concurrent: int = 3, max_per_minute: int = 10):
        self.max_concurrent = max_concurrent
        self.max_per_minute = max_per_minute
        self.active_exports = {}  # username -> start_time
        self.export_history = []  # list of (username, timestamp) tuples
        self.lock = threading.Lock()
    
    def can_start_export(self, username: str) -> tuple[bool, str]:
        """
        Check if user can start a new export operation.
        
        Returns:
            (can_start, reason)
        """
        with self.lock:
            current_time = datetime.now()
            
            # Check if user already has an active export
            if username in self.active_exports:
                return False, "لديك عملية تصدير قيد التنفيذ بالفعل"
            
            # Check concurrent limit
            if len(self.active_exports) >= self.max_concurrent:
                return False, "النظام مشغول حالياً. يرجى المحاولة بعد قليل"
            
            # Check rate limit (exports per minute)
            one_minute_ago = current_time - timedelta(minutes=1)
            recent_exports = [
                (user, timestamp) for user, timestamp in self.export_history
                if timestamp > one_minute_ago and user == username
            ]
            
            if len(recent_exports) >= self.max_per_minute:
                return False, "تم تجاوز الحد المسموح للتصدير. يرجى الانتظار دقيقة واحدة"
            
            return True, ""
    
    def start_export(self, username: str) -> bool:
        """
        Start tracking an export operation.
        
        Returns:
            True if export can start, False otherwise
        """
        can_start, _ = self.can_start_export(username)
        if not can_start:
            return False
        
        with self.lock:
            current_time = datetime.now()
            self.active_exports[username] = current_time
            self.export_history.append((username, current_time))
            
            # Clean up old history (keep only last hour)
            one_hour_ago = current_time - timedelta(hours=1)
            self.export_history = [
                (user, timestamp) for user, timestamp in self.export_history
                if timestamp > one_hour_ago
            ]
            
            logger.info(f"Export started for {username}. Active exports: {len(self.active_exports)}")
            return True
    
    def finish_export(self, username: str):
        """Finish tracking an export operation."""
        with self.lock:
            if username in self.active_exports:
                start_time = self.active_exports.pop(username)
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"Export finished for {username} after {duration:.2f}s. "
                           f"Active exports: {len(self.active_exports)}")

# Global rate limiter instance
export_rate_limiter = ExportRateLimiter()

@contextmanager
def rate_limited_export(username: str):
    """
    Context manager for rate-limited export operations.
    
    **Validates: Requirements 5.5**
    """
    if not export_rate_limiter.start_export(username):
        can_start, reason = export_rate_limiter.can_start_export(username)
        raise RuntimeError(reason)
    
    try:
        yield
    finally:
        export_rate_limiter.finish_export(username)

# Fallback strategies for large exports
class ExportFallbackStrategies:
    """
    Fallback strategies for handling large exports and resource constraints.
    
    **Validates: Requirements 5.3, 5.4**
    """
    
    @staticmethod
    def reduce_data_size(df, max_rows: int = 10000, strategy: str = 'sample') -> tuple:
        """
        Reduce DataFrame size using various strategies.
        
        Args:
            df: DataFrame to reduce
            max_rows: Maximum number of rows to keep
            strategy: 'sample', 'recent', 'top_values'
            
        Returns:
            (reduced_df, reduction_info)
        """
        if df is None or len(df) <= max_rows:
            return df, {'reduced': False, 'original_rows': len(df) if df is not None else 0}
        
        original_rows = len(df)
        
        try:
            if strategy == 'sample':
                # Random sampling
                reduced_df = df.sample(n=max_rows, random_state=42)
            elif strategy == 'recent':
                # Keep most recent records (assumes date column exists)
                date_cols = [col for col in df.columns if 'date' in col.lower()]
                if date_cols:
                    df_sorted = df.sort_values(date_cols[0], ascending=False)
                    reduced_df = df_sorted.head(max_rows)
                else:
                    # Fallback to last N rows
                    reduced_df = df.tail(max_rows)
            elif strategy == 'top_values':
                # Keep records with highest values (assumes numeric column exists)
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    # Sort by first numeric column
                    df_sorted = df.sort_values(numeric_cols[0], ascending=False)
                    reduced_df = df_sorted.head(max_rows)
                else:
                    # Fallback to first N rows
                    reduced_df = df.head(max_rows)
            else:
                # Default: first N rows
                reduced_df = df.head(max_rows)
            
            reduction_info = {
                'reduced': True,
                'original_rows': original_rows,
                'final_rows': len(reduced_df),
                'reduction_percent': ((original_rows - len(reduced_df)) / original_rows) * 100,
                'strategy_used': strategy
            }
            
            logger.info(f"Data reduced from {original_rows} to {len(reduced_df)} rows "
                       f"({reduction_info['reduction_percent']:.1f}% reduction) using {strategy} strategy")
            
            return reduced_df, reduction_info
            
        except Exception as e:
            logger.error(f"Failed to reduce data size: {e}")
            # Return original data if reduction fails
            return df, {'reduced': False, 'original_rows': original_rows, 'error': str(e)}
    
    @staticmethod
    def create_summary_export(df, operation_type: str) -> tuple:
        """
        Create a summary version of the export for large datasets.
        
        Args:
            df: DataFrame to summarize
            operation_type: Type of operation (dashboard, inventory, etc.)
            
        Returns:
            (summary_df, summary_info)
        """
        if df is None:
            return None, {'created': False, 'reason': 'no_data'}
        
        try:
            summary_info = {'created': True, 'original_rows': len(df)}
            
            if operation_type == 'dashboard':
                # Create dashboard summary
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                summary_data = []
                
                for col in numeric_cols:
                    summary_data.append({
                        'المتغير': col,
                        'المجموع': df[col].sum(),
                        'المتوسط': df[col].mean(),
                        'الحد الأدنى': df[col].min(),
                        'الحد الأقصى': df[col].max(),
                        'عدد القيم': df[col].count()
                    })
                
                summary_df = pd.DataFrame(summary_data)
                summary_info['summary_type'] = 'numeric_statistics'
                
            elif operation_type == 'inventory':
                # Create inventory summary by category
                if 'item_category1' in df.columns:
                    summary_df = df.groupby('item_category1').agg({
                        'product_code': 'count',
                        'Last_on_hand': 'sum' if 'Last_on_hand' in df.columns else 'count',
                        'inventory_value': 'sum' if 'inventory_value' in df.columns else 'count'
                    }).reset_index()
                    summary_df.columns = ['الفئة', 'عدد المنتجات', 'إجمالي المخزون', 'إجمالي القيمة']
                    summary_info['summary_type'] = 'category_summary'
                else:
                    # Fallback: basic statistics
                    summary_df = pd.DataFrame([{
                        'إجمالي المنتجات': len(df),
                        'الفئات': df['item_category1'].nunique() if 'item_category1' in df.columns else 'غير متاح',
                        'الموردين': df['supplier_name'].nunique() if 'supplier_name' in df.columns else 'غير متاح'
                    }])
                    summary_info['summary_type'] = 'basic_statistics'
            else:
                # Generic summary
                summary_df = pd.DataFrame([{
                    'إجمالي السجلات': len(df),
                    'الأعمدة': len(df.columns),
                    'تاريخ التصدير': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }])
                summary_info['summary_type'] = 'generic'
            
            summary_info['summary_rows'] = len(summary_df)
            logger.info(f"Created {summary_info['summary_type']} summary with {len(summary_df)} rows "
                       f"from {len(df)} original rows")
            
            return summary_df, summary_info
            
        except Exception as e:
            logger.error(f"Failed to create summary export: {e}")
            return None, {'created': False, 'error': str(e)}
    
    @staticmethod
    def handle_timeout_scenario(username: str, operation_type: str, elapsed_time: float) -> dict:
        """
        Handle timeout scenarios with appropriate user messaging.
        
        Returns:
            Dictionary with timeout handling information
        """
        timeout_info = {
            'timeout_occurred': True,
            'elapsed_time_seconds': elapsed_time,
            'user_message': '',
            'suggested_actions': []
        }
        
        if elapsed_time > 300:  # 5 minutes
            timeout_info['user_message'] = 'انتهت مهلة التصدير. البيانات كبيرة جداً للمعالجة'
            timeout_info['suggested_actions'] = [
                'تطبيق فلاتر لتقليل حجم البيانات',
                'تصدير البيانات على دفعات',
                'استخدام تصدير ملخص بدلاً من التفاصيل الكاملة'
            ]
        elif elapsed_time > 120:  # 2 minutes
            timeout_info['user_message'] = 'المعالجة تستغرق وقتاً أطول من المتوقع'
            timeout_info['suggested_actions'] = [
                'تطبيق فلاتر زمنية لتقليل البيانات',
                'المحاولة مرة أخرى لاحقاً'
            ]
        else:
            timeout_info['user_message'] = 'انتهت مهلة المعالجة'
            timeout_info['suggested_actions'] = [
                'المحاولة مرة أخرى',
                'التحقق من اتصال الإنترنت'
            ]
        
        logger.warning(f"Timeout scenario handled for {username} - {operation_type}: {elapsed_time:.2f}s")
        return timeout_info

# Timeout handling utilities
@contextmanager
def timeout_handler(timeout_seconds: int = 300, operation_name: str = "export"):
    """
    Context manager for handling operation timeouts.
    
    **Validates: Requirements 5.3**
    """
    start_time = datetime.now()
    timeout_time = start_time + timedelta(seconds=timeout_seconds)
    
    class TimeoutException(Exception):
        pass
    
    def check_timeout():
        if datetime.now() > timeout_time:
            elapsed = (datetime.now() - start_time).total_seconds()
            raise TimeoutException(f"{operation_name} operation timed out after {elapsed:.2f} seconds")
    
    try:
        # Provide timeout checker to the context
        yield check_timeout
    except TimeoutException:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"{operation_name} operation timed out after {elapsed:.2f} seconds")
        raise
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"{operation_name} operation failed after {elapsed:.2f} seconds: {e}")
        raise
    finally:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"{operation_name} operation completed in {elapsed:.2f} seconds")