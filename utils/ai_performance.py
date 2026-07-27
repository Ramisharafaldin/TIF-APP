"""
AI Performance Optimization and Monitoring
Provides performance tracking, large dataset handling, and optimization utilities.
"""
import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable, Iterator
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for AI operations."""
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: float = 0.0
    memory_usage_mb: float = 0.0
    data_size: int = 0
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchProcessingResult:
    """Result of batch processing operation."""
    total_items: int
    processed_items: int
    failed_items: int
    processing_time: float
    results: List[Any]
    errors: List[str]
    success_rate: float


class PerformanceMonitor:
    """
    Monitors and tracks AI operation performance.
    
    Provides metrics collection, performance analysis, and optimization
    recommendations for AI-powered features.
    """
    
    def __init__(self):
        """Initialize the performance monitor."""
        self.metrics: List[PerformanceMetrics] = []
        self.active_operations: Dict[str, PerformanceMetrics] = {}
        self._lock = threading.Lock()
        
        # Performance thresholds
        self.thresholds = {
            'response_time_warning': 5.0,  # seconds
            'response_time_critical': 10.0,  # seconds
            'memory_usage_warning': 100.0,  # MB
            'memory_usage_critical': 500.0,  # MB
            'batch_size_optimal': 50,  # items per batch
            'max_concurrent_operations': 3
        }
    
    def start_operation(self, operation_name: str, data_size: int = 0, 
                       metadata: Dict[str, Any] = None) -> str:
        """
        Start tracking a new AI operation.
        
        Args:
            operation_name: Name of the operation being tracked
            data_size: Size of data being processed
            metadata: Additional metadata about the operation
            
        Returns:
            Operation ID for tracking
        """
        operation_id = f"{operation_name}_{int(time.time() * 1000)}"
        
        metric = PerformanceMetrics(
            operation_name=operation_name,
            start_time=datetime.now(),
            data_size=data_size,
            metadata=metadata or {}
        )
        
        with self._lock:
            self.active_operations[operation_id] = metric
        
        logger.debug(f"Started tracking operation: {operation_id}")
        return operation_id
    
    def end_operation(self, operation_id: str, success: bool = True, 
                     error_message: Optional[str] = None) -> PerformanceMetrics:
        """
        End tracking of an AI operation.
        
        Args:
            operation_id: ID of the operation to end
            success: Whether the operation was successful
            error_message: Error message if operation failed
            
        Returns:
            Complete performance metrics for the operation
        """
        with self._lock:
            if operation_id not in self.active_operations:
                logger.warning(f"Operation ID not found: {operation_id}")
                return None
            
            metric = self.active_operations.pop(operation_id)
        
        # Complete the metrics
        metric.end_time = datetime.now()
        metric.duration = (metric.end_time - metric.start_time).total_seconds()
        metric.success = success
        metric.error_message = error_message
        metric.memory_usage_mb = self._get_memory_usage()
        
        # Store completed metric
        with self._lock:
            self.metrics.append(metric)
        
        # Log performance warnings
        self._check_performance_thresholds(metric)
        
        logger.debug(f"Completed tracking operation: {operation_id} ({metric.duration:.2f}s)")
        return metric
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get performance summary for the specified time period.
        
        Args:
            hours: Number of hours to include in summary
            
        Returns:
            Performance summary dictionary
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            recent_metrics = [m for m in self.metrics if m.start_time >= cutoff_time]
        
        if not recent_metrics:
            return {
                'total_operations': 0,
                'average_duration': 0.0,
                'success_rate': 0.0,
                'operations_by_type': {},
                'performance_warnings': []
            }
        
        # Calculate summary statistics
        total_operations = len(recent_metrics)
        successful_operations = sum(1 for m in recent_metrics if m.success)
        success_rate = (successful_operations / total_operations) * 100
        average_duration = sum(m.duration for m in recent_metrics) / total_operations
        
        # Group by operation type
        operations_by_type = {}
        for metric in recent_metrics:
            op_type = metric.operation_name
            if op_type not in operations_by_type:
                operations_by_type[op_type] = {
                    'count': 0,
                    'average_duration': 0.0,
                    'success_rate': 0.0,
                    'total_data_size': 0
                }
            
            type_metrics = operations_by_type[op_type]
            type_metrics['count'] += 1
            type_metrics['total_data_size'] += metric.data_size
        
        # Calculate averages for each operation type
        for op_type, stats in operations_by_type.items():
            type_metrics = [m for m in recent_metrics if m.operation_name == op_type]
            stats['average_duration'] = sum(m.duration for m in type_metrics) / len(type_metrics)
            stats['success_rate'] = (sum(1 for m in type_metrics if m.success) / len(type_metrics)) * 100
        
        # Identify performance warnings
        warnings = []
        slow_operations = [m for m in recent_metrics if m.duration > self.thresholds['response_time_warning']]
        if slow_operations:
            warnings.append(f"{len(slow_operations)} operations exceeded response time warning threshold")
        
        high_memory_operations = [m for m in recent_metrics if m.memory_usage_mb > self.thresholds['memory_usage_warning']]
        if high_memory_operations:
            warnings.append(f"{len(high_memory_operations)} operations exceeded memory usage warning threshold")
        
        return {
            'total_operations': total_operations,
            'average_duration': average_duration,
            'success_rate': success_rate,
            'operations_by_type': operations_by_type,
            'performance_warnings': warnings,
            'time_period_hours': hours,
            'generated_at': datetime.now().isoformat()
        }
    
    def _check_performance_thresholds(self, metric: PerformanceMetrics):
        """Check if operation exceeded performance thresholds."""
        if metric.duration > self.thresholds['response_time_critical']:
            logger.warning(f"Operation {metric.operation_name} exceeded critical response time: {metric.duration:.2f}s")
        elif metric.duration > self.thresholds['response_time_warning']:
            logger.info(f"Operation {metric.operation_name} exceeded warning response time: {metric.duration:.2f}s")
        
        if metric.memory_usage_mb > self.thresholds['memory_usage_critical']:
            logger.warning(f"Operation {metric.operation_name} exceeded critical memory usage: {metric.memory_usage_mb:.1f}MB")
        elif metric.memory_usage_mb > self.thresholds['memory_usage_warning']:
            logger.info(f"Operation {metric.operation_name} exceeded warning memory usage: {metric.memory_usage_mb:.1f}MB")
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # psutil not available, return 0
            return 0.0
        except Exception as e:
            logger.warning(f"Failed to get memory usage: {e}")
            return 0.0


class DatasetChunker:
    """
    Handles chunking of large datasets for efficient AI processing.
    
    Provides intelligent chunking strategies based on data size,
    memory constraints, and processing requirements.
    """
    
    def __init__(self, max_chunk_size: int = 1000, max_memory_mb: float = 100.0):
        """
        Initialize the dataset chunker.
        
        Args:
            max_chunk_size: Maximum number of items per chunk
            max_memory_mb: Maximum memory usage per chunk in MB
        """
        self.max_chunk_size = max_chunk_size
        self.max_memory_mb = max_memory_mb
    
    def chunk_dataframe(self, df: pd.DataFrame, chunk_size: Optional[int] = None) -> Iterator[pd.DataFrame]:
        """
        Chunk a pandas DataFrame into smaller pieces.
        
        Args:
            df: DataFrame to chunk
            chunk_size: Override default chunk size
            
        Yields:
            DataFrame chunks
        """
        if df.empty:
            return
        
        effective_chunk_size = chunk_size or self._calculate_optimal_chunk_size(df)
        
        for i in range(0, len(df), effective_chunk_size):
            chunk = df.iloc[i:i + effective_chunk_size]
            yield chunk
    
    def chunk_list(self, items: List[Any], chunk_size: Optional[int] = None) -> Iterator[List[Any]]:
        """
        Chunk a list into smaller pieces.
        
        Args:
            items: List to chunk
            chunk_size: Override default chunk size
            
        Yields:
            List chunks
        """
        if not items:
            return
        
        effective_chunk_size = chunk_size or min(self.max_chunk_size, len(items))
        
        for i in range(0, len(items), effective_chunk_size):
            chunk = items[i:i + effective_chunk_size]
            yield chunk
    
    def _calculate_optimal_chunk_size(self, df: pd.DataFrame) -> int:
        """Calculate optimal chunk size based on DataFrame characteristics."""
        try:
            # Estimate memory usage per row
            memory_per_row = df.memory_usage(deep=True).sum() / len(df) / 1024 / 1024  # MB per row
            
            # Calculate chunk size based on memory constraint
            memory_based_size = int(self.max_memory_mb / memory_per_row) if memory_per_row > 0 else self.max_chunk_size
            
            # Use the smaller of memory-based size and max chunk size
            optimal_size = min(memory_based_size, self.max_chunk_size)
            
            # Ensure minimum chunk size of 1
            return max(1, optimal_size)
            
        except Exception as e:
            logger.warning(f"Failed to calculate optimal chunk size: {e}")
            return min(self.max_chunk_size, len(df))


class BatchProcessor:
    """
    Processes large datasets in batches with parallel processing support.
    
    Provides efficient batch processing with error handling, progress tracking,
    and result aggregation for AI operations.
    """
    
    def __init__(self, max_workers: int = 3, chunk_size: int = 50):
        """
        Initialize the batch processor.
        
        Args:
            max_workers: Maximum number of concurrent workers
            chunk_size: Size of each processing batch
        """
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.chunker = DatasetChunker(max_chunk_size=chunk_size)
    
    def process_dataframe_batches(self, df: pd.DataFrame, 
                                 processing_func: Callable[[pd.DataFrame], Any],
                                 progress_callback: Optional[Callable[[int, int], None]] = None) -> BatchProcessingResult:
        """
        Process DataFrame in batches with parallel execution.
        
        Args:
            df: DataFrame to process
            processing_func: Function to apply to each batch
            progress_callback: Optional callback for progress updates
            
        Returns:
            BatchProcessingResult with aggregated results
        """
        start_time = time.time()
        results = []
        errors = []
        processed_items = 0
        total_items = len(df)
        
        try:
            # Create chunks
            chunks = list(self.chunker.chunk_dataframe(df, self.chunk_size))
            
            if not chunks:
                return BatchProcessingResult(
                    total_items=0,
                    processed_items=0,
                    failed_items=0,
                    processing_time=0.0,
                    results=[],
                    errors=[],
                    success_rate=0.0
                )
            
            # Process chunks in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all chunks for processing
                future_to_chunk = {
                    executor.submit(processing_func, chunk): i 
                    for i, chunk in enumerate(chunks)
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_chunk):
                    chunk_index = future_to_chunk[future]
                    chunk = chunks[chunk_index]
                    
                    try:
                        result = future.result()
                        results.append(result)
                        processed_items += len(chunk)
                        
                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(processed_items, total_items)
                            
                    except Exception as e:
                        error_msg = f"Chunk {chunk_index} failed: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
            
            processing_time = time.time() - start_time
            failed_items = total_items - processed_items
            success_rate = (processed_items / total_items * 100) if total_items > 0 else 0.0
            
            return BatchProcessingResult(
                total_items=total_items,
                processed_items=processed_items,
                failed_items=failed_items,
                processing_time=processing_time,
                results=results,
                errors=errors,
                success_rate=success_rate
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Batch processing failed: {str(e)}"
            logger.error(error_msg)
            
            return BatchProcessingResult(
                total_items=total_items,
                processed_items=processed_items,
                failed_items=total_items - processed_items,
                processing_time=processing_time,
                results=results,
                errors=errors + [error_msg],
                success_rate=0.0
            )
    
    def process_list_batches(self, items: List[Any],
                           processing_func: Callable[[List[Any]], Any],
                           progress_callback: Optional[Callable[[int, int], None]] = None) -> BatchProcessingResult:
        """
        Process list items in batches with parallel execution.
        
        Args:
            items: List of items to process
            processing_func: Function to apply to each batch
            progress_callback: Optional callback for progress updates
            
        Returns:
            BatchProcessingResult with aggregated results
        """
        start_time = time.time()
        results = []
        errors = []
        processed_items = 0
        total_items = len(items)
        
        try:
            # Create chunks
            chunks = list(self.chunker.chunk_list(items, self.chunk_size))
            
            if not chunks:
                return BatchProcessingResult(
                    total_items=0,
                    processed_items=0,
                    failed_items=0,
                    processing_time=0.0,
                    results=[],
                    errors=[],
                    success_rate=0.0
                )
            
            # Process chunks in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all chunks for processing
                future_to_chunk = {
                    executor.submit(processing_func, chunk): i 
                    for i, chunk in enumerate(chunks)
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_chunk):
                    chunk_index = future_to_chunk[future]
                    chunk = chunks[chunk_index]
                    
                    try:
                        result = future.result()
                        results.append(result)
                        processed_items += len(chunk)
                        
                        # Call progress callback if provided
                        if progress_callback:
                            progress_callback(processed_items, total_items)
                            
                    except Exception as e:
                        error_msg = f"Chunk {chunk_index} failed: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
            
            processing_time = time.time() - start_time
            failed_items = total_items - processed_items
            success_rate = (processed_items / total_items * 100) if total_items > 0 else 0.0
            
            return BatchProcessingResult(
                total_items=total_items,
                processed_items=processed_items,
                failed_items=failed_items,
                processing_time=processing_time,
                results=results,
                errors=errors,
                success_rate=success_rate
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Batch processing failed: {str(e)}"
            logger.error(error_msg)
            
            return BatchProcessingResult(
                total_items=total_items,
                processed_items=processed_items,
                failed_items=total_items - processed_items,
                processing_time=processing_time,
                results=results,
                errors=errors + [error_msg],
                success_rate=0.0
            )


class LoadingIndicatorManager:
    """
    Manages loading indicators for long-running AI operations.
    
    Provides progress tracking and user feedback for AI operations
    that may take significant time to complete.
    """
    
    def __init__(self):
        """Initialize the loading indicator manager."""
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def start_loading(self, operation_id: str, operation_name: str, 
                     estimated_duration: Optional[float] = None) -> Dict[str, Any]:
        """
        Start a loading indicator for an operation.
        
        Args:
            operation_id: Unique identifier for the operation
            operation_name: Human-readable name of the operation
            estimated_duration: Estimated duration in seconds
            
        Returns:
            Loading indicator data for UI
        """
        loading_data = {
            'operation_id': operation_id,
            'operation_name': operation_name,
            'start_time': datetime.now().isoformat(),
            'estimated_duration': estimated_duration,
            'progress_percentage': 0,
            'status_message': f'بدء {operation_name}...',
            'is_active': True
        }
        
        with self._lock:
            self.active_operations[operation_id] = loading_data
        
        return loading_data
    
    def update_progress(self, operation_id: str, progress_percentage: int, 
                       status_message: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Update progress for an active operation.
        
        Args:
            operation_id: ID of the operation to update
            progress_percentage: Progress percentage (0-100)
            status_message: Optional status message
            
        Returns:
            Updated loading indicator data or None if operation not found
        """
        with self._lock:
            if operation_id not in self.active_operations:
                return None
            
            loading_data = self.active_operations[operation_id]
            loading_data['progress_percentage'] = max(0, min(100, progress_percentage))
            
            if status_message:
                loading_data['status_message'] = status_message
            
            return loading_data.copy()
    
    def finish_loading(self, operation_id: str, success: bool = True, 
                      final_message: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Finish a loading operation.
        
        Args:
            operation_id: ID of the operation to finish
            success: Whether the operation was successful
            final_message: Optional final status message
            
        Returns:
            Final loading indicator data or None if operation not found
        """
        with self._lock:
            if operation_id not in self.active_operations:
                return None
            
            loading_data = self.active_operations.pop(operation_id)
            loading_data['is_active'] = False
            loading_data['progress_percentage'] = 100
            loading_data['success'] = success
            loading_data['end_time'] = datetime.now().isoformat()
            
            if final_message:
                loading_data['status_message'] = final_message
            elif success:
                loading_data['status_message'] = f'تم إكمال {loading_data["operation_name"]} بنجاح'
            else:
                loading_data['status_message'] = f'فشل في {loading_data["operation_name"]}'
            
            return loading_data
    
    def get_active_operations(self) -> List[Dict[str, Any]]:
        """Get all currently active loading operations."""
        with self._lock:
            return [data.copy() for data in self.active_operations.values()]
    
    def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific operation."""
        with self._lock:
            if operation_id in self.active_operations:
                return self.active_operations[operation_id].copy()
            return None


# Global instances for easy access
performance_monitor = PerformanceMonitor()
batch_processor = BatchProcessor()
loading_indicator_manager = LoadingIndicatorManager()


def performance_tracked(operation_name: str):
    """
    Decorator to automatically track performance of AI operations.
    
    Args:
        operation_name: Name of the operation being tracked
        
    Returns:
        Decorated function with performance tracking
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Start performance tracking
            operation_id = performance_monitor.start_operation(
                operation_name=operation_name,
                metadata={'function': func.__name__}
            )
            
            try:
                # Execute the function
                result = func(*args, **kwargs)
                
                # End tracking with success
                performance_monitor.end_operation(operation_id, success=True)
                
                return result
                
            except Exception as e:
                # End tracking with error
                performance_monitor.end_operation(
                    operation_id, 
                    success=False, 
                    error_message=str(e)
                )
                raise e
        
        return wrapper
    return decorator


def chunked_processing(chunk_size: int = 50, max_workers: int = 3):
    """
    Decorator to automatically process large datasets in chunks.
    
    Args:
        chunk_size: Size of each processing chunk
        max_workers: Maximum number of concurrent workers
        
    Returns:
        Decorated function with chunked processing
    """
    def decorator(func):
        def wrapper(data, *args, **kwargs):
            # If data is small, process normally
            if hasattr(data, '__len__') and len(data) <= chunk_size:
                return func(data, *args, **kwargs)
            
            # Use batch processor for large datasets
            processor = BatchProcessor(max_workers=max_workers, chunk_size=chunk_size)
            
            def process_chunk(chunk):
                return func(chunk, *args, **kwargs)
            
            if isinstance(data, pd.DataFrame):
                result = processor.process_dataframe_batches(data, process_chunk)
            elif isinstance(data, list):
                result = processor.process_list_batches(data, process_chunk)
            else:
                # Fallback to normal processing
                return func(data, *args, **kwargs)
            
            return result
        
        return wrapper
    return decorator