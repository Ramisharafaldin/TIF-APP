"""
Export Operation Monitoring and Alerting

This module provides monitoring and alerting capabilities for export operations,
including resource usage tracking, performance metrics, and system health monitoring.

**Validates: Requirements 5.5**
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import psutil
import json
import os

logger = logging.getLogger(__name__)

@dataclass
class ExportMetrics:
    """Metrics for a single export operation."""
    username: str
    operation_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    memory_peak_mb: float = 0
    memory_start_mb: float = 0
    file_size_bytes: int = 0
    format: str = 'xlsx'
    success: bool = True
    error_message: Optional[str] = None

class ExportMonitor:
    """
    Monitor export operations and system resources.
    
    **Validates: Requirements 5.5**
    """
    
    def __init__(self, alert_threshold_memory_mb: int = 1000, 
                 alert_threshold_concurrent: int = 5,
                 metrics_retention_hours: int = 24):
        self.alert_threshold_memory_mb = alert_threshold_memory_mb
        self.alert_threshold_concurrent = alert_threshold_concurrent
        self.metrics_retention_hours = metrics_retention_hours
        
        self.active_operations: Dict[str, ExportMetrics] = {}
        self.completed_operations: List[ExportMetrics] = []
        self.system_alerts: List[Dict] = []
        
        self.lock = threading.Lock()
        self._monitoring_active = False
        self._monitor_thread = None
        
    def start_monitoring(self):
        """Start background monitoring thread."""
        if self._monitoring_active:
            return
            
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Export monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring thread."""
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Export monitoring stopped")
    
    def start_operation(self, username: str, operation_type: str) -> str:
        """
        Start tracking an export operation.
        
        Returns:
            Operation ID for tracking
        """
        operation_id = f"{username}_{operation_type}_{int(time.time())}"
        
        try:
            process = psutil.Process()
            memory_start = process.memory_info().rss / 1024 / 1024  # MB
        except Exception:
            memory_start = 0
        
        metrics = ExportMetrics(
            username=username,
            operation_type=operation_type,
            start_time=datetime.now(),
            memory_start_mb=memory_start
        )
        
        with self.lock:
            self.active_operations[operation_id] = metrics
            
            # Check for concurrent operations alert
            concurrent_count = len(self.active_operations)
            if concurrent_count >= self.alert_threshold_concurrent:
                self._add_alert(
                    'high_concurrent_operations',
                    f'High concurrent export operations: {concurrent_count}',
                    {'concurrent_count': concurrent_count, 'threshold': self.alert_threshold_concurrent}
                )
        
        logger.info(f"Started monitoring export operation: {operation_id}")
        return operation_id
    
    def update_operation_memory(self, operation_id: str, memory_mb: float):
        """Update memory usage for an operation."""
        with self.lock:
            if operation_id in self.active_operations:
                metrics = self.active_operations[operation_id]
                metrics.memory_peak_mb = max(metrics.memory_peak_mb, memory_mb)
                
                # Check memory threshold
                if memory_mb > self.alert_threshold_memory_mb:
                    self._add_alert(
                        'high_memory_usage',
                        f'High memory usage in export operation: {memory_mb:.2f} MB',
                        {
                            'operation_id': operation_id,
                            'username': metrics.username,
                            'operation_type': metrics.operation_type,
                            'memory_mb': memory_mb,
                            'threshold': self.alert_threshold_memory_mb
                        }
                    )
    
    def finish_operation(self, operation_id: str, success: bool = True, 
                        error_message: Optional[str] = None, 
                        file_size_bytes: int = 0, format: str = 'xlsx'):
        """Finish tracking an export operation."""
        with self.lock:
            if operation_id not in self.active_operations:
                logger.warning(f"Attempted to finish unknown operation: {operation_id}")
                return
            
            metrics = self.active_operations.pop(operation_id)
            metrics.end_time = datetime.now()
            metrics.duration_seconds = (metrics.end_time - metrics.start_time).total_seconds()
            metrics.success = success
            metrics.error_message = error_message
            metrics.file_size_bytes = file_size_bytes
            metrics.format = format
            
            # Update final memory usage
            try:
                process = psutil.Process()
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                metrics.memory_peak_mb = max(metrics.memory_peak_mb, current_memory)
            except Exception:
                pass
            
            self.completed_operations.append(metrics)
            
            # Clean up old metrics
            self._cleanup_old_metrics()
        
        logger.info(f"Finished monitoring export operation: {operation_id}, "
                   f"success: {success}, duration: {metrics.duration_seconds:.2f}s")
    
    def get_system_status(self) -> Dict:
        """Get current system status and metrics."""
        with self.lock:
            # System resource usage
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
            except Exception as e:
                logger.warning(f"Failed to get system metrics: {e}")
                cpu_percent = 0
                memory = None
                disk = None
            
            # Active operations
            active_count = len(self.active_operations)
            active_by_type = {}
            for metrics in self.active_operations.values():
                active_by_type[metrics.operation_type] = active_by_type.get(metrics.operation_type, 0) + 1
            
            # Recent completed operations (last hour)
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_completed = [
                m for m in self.completed_operations 
                if m.end_time and m.end_time > one_hour_ago
            ]
            
            # Success rate
            if recent_completed:
                success_count = sum(1 for m in recent_completed if m.success)
                success_rate = success_count / len(recent_completed)
            else:
                success_rate = 1.0
            
            # Average duration
            successful_operations = [m for m in recent_completed if m.success and m.duration_seconds]
            if successful_operations:
                avg_duration = sum(m.duration_seconds for m in successful_operations) / len(successful_operations)
            else:
                avg_duration = 0
            
            return {
                'timestamp': datetime.now().isoformat(),
                'system': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent if memory else 0,
                    'memory_available_gb': memory.available / 1024 / 1024 / 1024 if memory else 0,
                    'disk_percent': disk.percent if disk else 0,
                    'disk_free_gb': disk.free / 1024 / 1024 / 1024 if disk else 0
                },
                'exports': {
                    'active_count': active_count,
                    'active_by_type': active_by_type,
                    'recent_completed_count': len(recent_completed),
                    'success_rate': success_rate,
                    'average_duration_seconds': avg_duration
                },
                'alerts': {
                    'active_count': len(self.system_alerts),
                    'recent_alerts': self.system_alerts[-5:]  # Last 5 alerts
                }
            }
    
    def get_user_statistics(self, username: str, hours: int = 24) -> Dict:
        """Get export statistics for a specific user."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self.lock:
            # Active operations for user
            user_active = [
                m for m in self.active_operations.values() 
                if m.username == username
            ]
            
            # Completed operations for user
            user_completed = [
                m for m in self.completed_operations 
                if m.username == username and m.end_time and m.end_time > cutoff_time
            ]
            
            # Statistics
            total_operations = len(user_completed)
            successful_operations = [m for m in user_completed if m.success]
            failed_operations = [m for m in user_completed if not m.success]
            
            if successful_operations:
                avg_duration = sum(m.duration_seconds for m in successful_operations) / len(successful_operations)
                avg_memory = sum(m.memory_peak_mb for m in successful_operations) / len(successful_operations)
                total_file_size = sum(m.file_size_bytes for m in successful_operations)
            else:
                avg_duration = 0
                avg_memory = 0
                total_file_size = 0
            
            # Format breakdown
            format_counts = {}
            for m in user_completed:
                format_counts[m.format] = format_counts.get(m.format, 0) + 1
            
            return {
                'username': username,
                'period_hours': hours,
                'active_operations': len(user_active),
                'total_operations': total_operations,
                'successful_operations': len(successful_operations),
                'failed_operations': len(failed_operations),
                'success_rate': len(successful_operations) / total_operations if total_operations > 0 else 1.0,
                'average_duration_seconds': avg_duration,
                'average_memory_mb': avg_memory,
                'total_file_size_bytes': total_file_size,
                'format_breakdown': format_counts,
                'recent_errors': [m.error_message for m in failed_operations if m.error_message][-5:]
            }
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self._monitoring_active:
            try:
                # Check system resources
                self._check_system_resources()
                
                # Check for stuck operations
                self._check_stuck_operations()
                
                # Clean up old data
                self._cleanup_old_metrics()
                self._cleanup_old_alerts()
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            time.sleep(30)  # Check every 30 seconds
    
    def _check_system_resources(self):
        """Check system resource usage and generate alerts."""
        try:
            # Memory check
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                self._add_alert(
                    'high_system_memory',
                    f'High system memory usage: {memory.percent:.1f}%',
                    {'memory_percent': memory.percent, 'available_gb': memory.available / 1024 / 1024 / 1024}
                )
            
            # CPU check
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                self._add_alert(
                    'high_system_cpu',
                    f'High system CPU usage: {cpu_percent:.1f}%',
                    {'cpu_percent': cpu_percent}
                )
            
            # Disk check
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                self._add_alert(
                    'high_disk_usage',
                    f'High disk usage: {disk.percent:.1f}%',
                    {'disk_percent': disk.percent, 'free_gb': disk.free / 1024 / 1024 / 1024}
                )
                
        except Exception as e:
            logger.warning(f"Failed to check system resources: {e}")
    
    def _check_stuck_operations(self):
        """Check for operations that have been running too long."""
        current_time = datetime.now()
        stuck_threshold = timedelta(minutes=10)  # 10 minutes
        
        with self.lock:
            for operation_id, metrics in self.active_operations.items():
                if current_time - metrics.start_time > stuck_threshold:
                    self._add_alert(
                        'stuck_operation',
                        f'Export operation running for too long: {operation_id}',
                        {
                            'operation_id': operation_id,
                            'username': metrics.username,
                            'operation_type': metrics.operation_type,
                            'duration_minutes': (current_time - metrics.start_time).total_seconds() / 60
                        }
                    )
    
    def _add_alert(self, alert_type: str, message: str, details: Dict):
        """Add a system alert."""
        alert = {
            'type': alert_type,
            'message': message,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        
        # Avoid duplicate alerts (same type within 5 minutes)
        five_minutes_ago = datetime.now() - timedelta(minutes=5)
        recent_similar = [
            a for a in self.system_alerts 
            if (a['type'] == alert_type and 
                datetime.fromisoformat(a['timestamp']) > five_minutes_ago)
        ]
        
        if not recent_similar:
            self.system_alerts.append(alert)
            logger.warning(f"Export system alert: {message}")
    
    def _cleanup_old_metrics(self):
        """Remove old completed operations."""
        cutoff_time = datetime.now() - timedelta(hours=self.metrics_retention_hours)
        self.completed_operations = [
            m for m in self.completed_operations 
            if m.end_time and m.end_time > cutoff_time
        ]
    
    def _cleanup_old_alerts(self):
        """Remove old alerts."""
        cutoff_time = datetime.now() - timedelta(hours=24)  # Keep alerts for 24 hours
        self.system_alerts = [
            a for a in self.system_alerts 
            if datetime.fromisoformat(a['timestamp']) > cutoff_time
        ]

# Global monitor instance
export_monitor = ExportMonitor()

def start_export_monitoring():
    """Start the global export monitor."""
    export_monitor.start_monitoring()

def stop_export_monitoring():
    """Stop the global export monitor."""
    export_monitor.stop_monitoring()

def get_export_system_status() -> Dict:
    """Get current export system status."""
    return export_monitor.get_system_status()

def get_user_export_stats(username: str, hours: int = 24) -> Dict:
    """Get export statistics for a user."""
    return export_monitor.get_user_statistics(username, hours)