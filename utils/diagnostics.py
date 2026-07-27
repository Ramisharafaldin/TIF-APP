"""
Diagnostic endpoints and utilities for troubleshooting upload operations.

Provides health checks, log analysis, and system monitoring capabilities.

Requirements: 4.1, 4.2, 4.3, 4.4
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
import data_store
from utils.logging_config import get_loggers


class DiagnosticCollector:
    """
    Collects diagnostic information for troubleshooting.
    """
    
    def __init__(self):
        self.loggers = get_loggers()
        self.logger = logging.getLogger('diagnostics')
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health information.
        
        Returns:
            Dictionary with system health status
        """
        health_info = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'components': {},
            'warnings': [],
            'errors': []
        }
        
        try:
            # Check database health
            db_health = data_store.get_database_health()
            health_info['components']['database'] = db_health
            
            if db_health['status'] != 'healthy':
                health_info['status'] = 'warning'
                health_info['warnings'].append(f"Database: {db_health['message']}")
            
            # Check log files
            log_health = self._check_log_files()
            health_info['components']['logging'] = log_health
            
            if not log_health['accessible']:
                health_info['status'] = 'warning'
                health_info['warnings'].append("Some log files are not accessible")
            
            # Check disk space
            disk_health = self._check_disk_space()
            health_info['components']['disk_space'] = disk_health
            
            if disk_health['warning']:
                health_info['status'] = 'warning'
                health_info['warnings'].append(f"Low disk space: {disk_health['message']}")
            
            # Check upload directory
            upload_health = self._check_upload_directory()
            health_info['components']['upload_directory'] = upload_health
            
            if not upload_health['accessible']:
                health_info['status'] = 'error'
                health_info['errors'].append("Upload directory not accessible")
            
        except Exception as e:
            self.logger.error(f"Error collecting system health: {e}", exc_info=True)
            health_info['status'] = 'error'
            health_info['errors'].append(f"Health check failed: {str(e)}")
        
        return health_info
    
    def get_upload_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get upload statistics for the specified time period.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with upload statistics
        """
        stats = {
            'period_hours': hours,
            'timestamp': datetime.now().isoformat(),
            'total_uploads': 0,
            'successful_uploads': 0,
            'failed_uploads': 0,
            'success_rate': 0.0,
            'average_file_size_mb': 0.0,
            'average_processing_time_ms': 0.0,
            'uploads_by_user': {},
            'uploads_by_branch': {},
            'error_types': {},
            'performance_warnings': 0
        }
        
        try:
            # Analyze upload logs
            upload_logs = self._read_upload_logs(hours)
            
            if not upload_logs:
                return stats
            
            # Process upload events
            upload_events = defaultdict(dict)
            
            for log_entry in upload_logs:
                try:
                    data = json.loads(log_entry)
                    event_data = data.get('extra_data', {})
                    event_type = event_data.get('event')
                    
                    if event_type in ['upload_start', 'upload_success', 'upload_failure']:
                        username = event_data.get('username')
                        filename = event_data.get('filename')
                        key = f"{username}:{filename}"
                        
                        upload_events[key][event_type] = event_data
                        
                except (json.JSONDecodeError, KeyError):
                    continue
            
            # Calculate statistics
            for upload_key, events in upload_events.items():
                stats['total_uploads'] += 1
                
                if 'upload_success' in events:
                    stats['successful_uploads'] += 1
                    
                    # File size statistics
                    file_size_mb = events['upload_success'].get('file_size_mb', 0)
                    if file_size_mb > 0:
                        stats['average_file_size_mb'] += file_size_mb
                    
                    # Processing time statistics
                    proc_time = events['upload_success'].get('processing_time_ms', 0)
                    if proc_time > 0:
                        stats['average_processing_time_ms'] += proc_time
                    
                    # User statistics
                    username = events['upload_success'].get('username', 'unknown')
                    stats['uploads_by_user'][username] = stats['uploads_by_user'].get(username, 0) + 1
                    
                    # Branch statistics
                    branch = events['upload_success'].get('branch_name', 'unknown')
                    stats['uploads_by_branch'][branch] = stats['uploads_by_branch'].get(branch, 0) + 1
                
                elif 'upload_failure' in events:
                    stats['failed_uploads'] += 1
                    
                    # Error type statistics
                    error_type = events['upload_failure'].get('error_type', 'unknown')
                    stats['error_types'][error_type] = stats['error_types'].get(error_type, 0) + 1
            
            # Calculate averages
            if stats['successful_uploads'] > 0:
                stats['average_file_size_mb'] /= stats['successful_uploads']
                stats['average_processing_time_ms'] /= stats['successful_uploads']
            
            # Calculate success rate
            if stats['total_uploads'] > 0:
                stats['success_rate'] = (stats['successful_uploads'] / stats['total_uploads']) * 100
            
            # Check for performance warnings
            perf_logs = self._read_performance_logs(hours)
            for log_entry in perf_logs:
                try:
                    data = json.loads(log_entry)
                    if data.get('level') == 'WARNING':
                        stats['performance_warnings'] += 1
                except (json.JSONDecodeError, KeyError):
                    continue
            
        except Exception as e:
            self.logger.error(f"Error collecting upload statistics: {e}", exc_info=True)
        
        return stats
    
    def get_recent_errors(self, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent error logs.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of errors to return
            
        Returns:
            List of recent error entries
        """
        errors = []
        
        try:
            error_log_path = os.path.join('logs', 'errors.log')
            
            if not os.path.exists(error_log_path):
                return errors
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with open(error_log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Process recent lines (reverse order to get most recent first)
            for line in reversed(lines[-1000:]):  # Look at last 1000 lines
                if len(errors) >= limit:
                    break
                
                try:
                    # Parse timestamp from log line
                    if ' - ' in line:
                        timestamp_str = line.split(' - ')[0]
                        log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                        
                        if log_time >= cutoff_time:
                            errors.append({
                                'timestamp': log_time.isoformat(),
                                'message': line.strip(),
                                'severity': 'ERROR' if 'ERROR' in line else 'WARNING'
                            })
                except (ValueError, IndexError):
                    continue
            
        except Exception as e:
            self.logger.error(f"Error reading error logs: {e}", exc_info=True)
        
        return errors
    
    def analyze_performance_trends(self, hours: int = 168) -> Dict[str, Any]:  # Default 1 week
        """
        Analyze performance trends over time.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Dictionary with performance trend analysis
        """
        trends = {
            'period_hours': hours,
            'timestamp': datetime.now().isoformat(),
            'upload_performance': {
                'average_processing_time_ms': 0.0,
                'max_processing_time_ms': 0.0,
                'min_processing_time_ms': float('inf'),
                'slow_uploads_count': 0,
                'total_uploads': 0
            },
            'database_performance': {
                'average_query_time_ms': 0.0,
                'slow_queries_count': 0,
                'total_operations': 0
            },
            'file_size_trends': {
                'average_file_size_mb': 0.0,
                'large_files_count': 0,  # > 10MB
                'total_files': 0
            },
            'hourly_distribution': defaultdict(int),
            'recommendations': []
        }
        
        try:
            # Analyze performance logs
            perf_logs = self._read_performance_logs(hours)
            
            processing_times = []
            query_times = []
            file_sizes = []
            
            for log_entry in perf_logs:
                try:
                    data = json.loads(log_entry)
                    event_data = data.get('extra_data', {})
                    event_type = event_data.get('event')
                    
                    # Parse timestamp for hourly distribution
                    timestamp = datetime.fromisoformat(data.get('timestamp', ''))
                    hour = timestamp.hour
                    trends['hourly_distribution'][hour] += 1
                    
                    if event_type == 'upload_performance':
                        proc_time = event_data.get('processing_time_ms', 0)
                        file_size_mb = event_data.get('file_size_mb', 0)
                        
                        if proc_time > 0:
                            processing_times.append(proc_time)
                            if proc_time > 10000:  # > 10 seconds
                                trends['upload_performance']['slow_uploads_count'] += 1
                        
                        if file_size_mb > 0:
                            file_sizes.append(file_size_mb)
                            if file_size_mb > 10:  # > 10MB
                                trends['file_size_trends']['large_files_count'] += 1
                    
                    elif event_type == 'database_performance':
                        query_time = event_data.get('query_time_ms', 0)
                        if query_time > 0:
                            query_times.append(query_time)
                            if query_time > 1000:  # > 1 second
                                trends['database_performance']['slow_queries_count'] += 1
                
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
            
            # Calculate upload performance statistics
            if processing_times:
                trends['upload_performance']['total_uploads'] = len(processing_times)
                trends['upload_performance']['average_processing_time_ms'] = sum(processing_times) / len(processing_times)
                trends['upload_performance']['max_processing_time_ms'] = max(processing_times)
                trends['upload_performance']['min_processing_time_ms'] = min(processing_times)
            
            # Calculate database performance statistics
            if query_times:
                trends['database_performance']['total_operations'] = len(query_times)
                trends['database_performance']['average_query_time_ms'] = sum(query_times) / len(query_times)
            
            # Calculate file size statistics
            if file_sizes:
                trends['file_size_trends']['total_files'] = len(file_sizes)
                trends['file_size_trends']['average_file_size_mb'] = sum(file_sizes) / len(file_sizes)
            
            # Generate recommendations
            self._generate_performance_recommendations(trends)
            
        except Exception as e:
            self.logger.error(f"Error analyzing performance trends: {e}", exc_info=True)
        
        return trends
    
    def _check_log_files(self) -> Dict[str, Any]:
        """Check accessibility and status of log files."""
        log_files = [
            'logs/flask_app.log',
            'logs/upload_operations.jsonl',
            'logs/performance.jsonl',
            'logs/errors.log'
        ]
        
        status = {
            'accessible': True,
            'files': {},
            'total_size_mb': 0.0
        }
        
        for log_file in log_files:
            file_status = {
                'exists': os.path.exists(log_file),
                'readable': False,
                'size_mb': 0.0,
                'last_modified': None
            }
            
            if file_status['exists']:
                try:
                    file_status['readable'] = os.access(log_file, os.R_OK)
                    stat_info = os.stat(log_file)
                    file_status['size_mb'] = stat_info.st_size / (1024 * 1024)
                    file_status['last_modified'] = datetime.fromtimestamp(stat_info.st_mtime).isoformat()
                    status['total_size_mb'] += file_status['size_mb']
                except OSError:
                    status['accessible'] = False
            else:
                status['accessible'] = False
            
            status['files'][log_file] = file_status
        
        return status
    
    def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space."""
        try:
            import shutil
            total, used, free = shutil.disk_usage('.')
            
            free_gb = free / (1024 ** 3)
            total_gb = total / (1024 ** 3)
            used_percent = (used / total) * 100
            
            return {
                'free_gb': round(free_gb, 2),
                'total_gb': round(total_gb, 2),
                'used_percent': round(used_percent, 1),
                'warning': free_gb < 1.0,  # Warn if less than 1GB free
                'message': f"{free_gb:.1f}GB free of {total_gb:.1f}GB total"
            }
        except Exception:
            return {
                'free_gb': 0,
                'total_gb': 0,
                'used_percent': 0,
                'warning': True,
                'message': "Unable to check disk space"
            }
    
    def _check_upload_directory(self) -> Dict[str, Any]:
        """Check upload directory accessibility."""
        upload_dir = 'uploads'
        
        return {
            'path': upload_dir,
            'exists': os.path.exists(upload_dir),
            'accessible': os.path.exists(upload_dir) and os.access(upload_dir, os.W_OK),
            'writable': os.access(upload_dir, os.W_OK) if os.path.exists(upload_dir) else False
        }
    
    def _read_upload_logs(self, hours: int) -> List[str]:
        """Read upload operation logs from the specified time period."""
        log_file = os.path.join('logs', 'upload_operations.jsonl')
        
        if not os.path.exists(log_file):
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_logs = []
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        log_time = datetime.fromisoformat(data.get('timestamp', ''))
                        
                        if log_time >= cutoff_time:
                            recent_logs.append(line.strip())
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception as e:
            self.logger.error(f"Error reading upload logs: {e}")
        
        return recent_logs
    
    def _read_performance_logs(self, hours: int) -> List[str]:
        """Read performance logs from the specified time period."""
        log_file = os.path.join('logs', 'performance.jsonl')
        
        if not os.path.exists(log_file):
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_logs = []
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        log_time = datetime.fromisoformat(data.get('timestamp', ''))
                        
                        if log_time >= cutoff_time:
                            recent_logs.append(line.strip())
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception as e:
            self.logger.error(f"Error reading performance logs: {e}")
        
        return recent_logs
    
    def _generate_performance_recommendations(self, trends: Dict[str, Any]):
        """Generate performance recommendations based on trends."""
        recommendations = []
        
        # Check upload performance
        avg_proc_time = trends['upload_performance']['average_processing_time_ms']
        slow_uploads = trends['upload_performance']['slow_uploads_count']
        total_uploads = trends['upload_performance']['total_uploads']
        
        if avg_proc_time > 5000:  # > 5 seconds average
            recommendations.append({
                'type': 'performance',
                'severity': 'warning',
                'message': f'Average upload processing time is high ({avg_proc_time:.0f}ms). Consider optimizing Excel processing.',
                'action': 'Investigate Excel processing bottlenecks'
            })
        
        if total_uploads > 0 and (slow_uploads / total_uploads) > 0.2:  # > 20% slow uploads
            recommendations.append({
                'type': 'performance',
                'severity': 'warning',
                'message': f'{slow_uploads} out of {total_uploads} uploads were slow (>10s). Check for large files or system load.',
                'action': 'Monitor system resources during peak usage'
            })
        
        # Check database performance
        avg_query_time = trends['database_performance']['average_query_time_ms']
        slow_queries = trends['database_performance']['slow_queries_count']
        
        if avg_query_time > 500:  # > 500ms average
            recommendations.append({
                'type': 'database',
                'severity': 'warning',
                'message': f'Average database query time is high ({avg_query_time:.0f}ms). Consider database optimization.',
                'action': 'Review database indexes and query optimization'
            })
        
        # Check file size trends
        avg_file_size = trends['file_size_trends']['average_file_size_mb']
        large_files = trends['file_size_trends']['large_files_count']
        
        if avg_file_size > 15:  # > 15MB average
            recommendations.append({
                'type': 'storage',
                'severity': 'info',
                'message': f'Average file size is large ({avg_file_size:.1f}MB). Monitor storage usage.',
                'action': 'Consider implementing file size limits or compression'
            })
        
        trends['recommendations'] = recommendations


def get_diagnostic_collector():
    """Get a diagnostic collector instance."""
    return DiagnosticCollector()