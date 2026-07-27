"""
Alert Service Module for Dynamic Inventory Alerts

This module provides functionality to generate, classify, and cache inventory alerts
based on current stock levels and configurable thresholds.

Feature: dynamic-inventory-alerts
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import pandas as pd

# Import data store for accessing inventory data
import data_store

# Import performance optimization
from utils.performance_optimization import monitor_alert_generation_performance, performance_optimizer

# Configure logging
logger = logging.getLogger(__name__)

# Alert thresholds configuration
ALERT_THRESHOLDS = {
    'out_of_stock': {
        'min': 0, 'max': 0, 
        'status': 'نفد المخزون', 
        'class': 'bg-red-600/10 text-red-600 border-red-600/20', 
        'priority': 1
    },
    'very_low': {
        'min': 1, 'max': 5, 
        'status': 'منخفض جداً', 
        'class': 'bg-red-500/10 text-red-500 border-red-500/20', 
        'priority': 2
    },
    'low': {
        'min': 6, 'max': 15, 
        'status': 'منخفض', 
        'class': 'bg-orange-500/10 text-orange-500 border-orange-500/20', 
        'priority': 3
    },
    'reorder': {
        'min': 16, 'max': 25, 
        'status': 'إعادة طلب', 
        'class': 'bg-blue-500/10 text-blue-500 border-blue-500/20', 
        'priority': 4
    }
}

# Cache configuration
CACHE_DURATION_MINUTES = 5
_alert_cache = {}


@dataclass
class InventoryAlert:
    """Data class representing an inventory alert"""
    product_code: str
    product_name: str
    branch_code: str
    current_stock: int
    alert_status: str
    status_class: str
    priority: int
    last_updated: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for JSON serialization"""
        return {
            'product_code': self.product_code,
            'product_name': self.product_name,
            'branch_code': self.branch_code,
            'current_stock': self.current_stock,
            'alert_status': self.alert_status,
            'status_class': self.status_class,
            'priority': self.priority,
            'last_updated': self.last_updated.isoformat()
        }


@dataclass
class AlertThreshold:
    """Data class for alert threshold configuration"""
    level_name: str
    min_stock: int
    max_stock: int
    status_text: str
    css_class: str
    priority: int


def get_alert_thresholds() -> Dict[str, AlertThreshold]:
    """
    Get configurable alert thresholds.
    
    Returns:
        Dictionary of threshold configurations
    """
    thresholds = {}
    for level_name, config in ALERT_THRESHOLDS.items():
        thresholds[level_name] = AlertThreshold(
            level_name=level_name,
            min_stock=config['min'],
            max_stock=config['max'],
            status_text=config['status'],
            css_class=config['class'],
            priority=config['priority']
        )
    return thresholds


def classify_alert_status(stock_level: int) -> Tuple[str, str, int]:
    """
    Classify alert severity based on stock quantity.
    
    Args:
        stock_level: Current stock quantity
        
    Returns:
        Tuple of (status_text, css_class, priority)
    """
    # Handle invalid or None stock levels
    if stock_level is None:
        stock_level = 0
    
    # Handle non-numeric types
    if not isinstance(stock_level, (int, float)):
        try:
            stock_level = float(stock_level)
        except (ValueError, TypeError):
            logger.warning(f"Invalid stock level '{stock_level}', defaulting to 0")
            stock_level = 0
    
    # Convert to int and ensure non-negative
    stock_level = int(stock_level)
    if stock_level < 0:
        logger.warning(f"Negative stock level {stock_level}, converting to 0")
        stock_level = 0
    
    for threshold_config in ALERT_THRESHOLDS.values():
        if threshold_config['min'] <= stock_level <= threshold_config['max']:
            return (
                threshold_config['status'],
                threshold_config['class'],
                threshold_config['priority']
            )
    
    # If stock level doesn't match any threshold, it's above reorder level
    # Return None to indicate no alert needed
    return None, None, None


def _truncate_product_name(product_name: str, max_length: int = 30) -> str:
    """
    Truncate product name if longer than max_length characters.
    
    Args:
        product_name: Original product name
        max_length: Maximum allowed length
        
    Returns:
        Truncated product name with ellipsis if needed
    """
    if not product_name:
        return "غير محدد"
    
    if len(product_name) <= max_length:
        return product_name
    
    return product_name[:max_length-3] + "..."


def _get_cache_key(username: str, branch_filter: Optional[str]) -> str:
    """Generate cache key for alert data"""
    return f"alerts_{username}_{branch_filter or 'all'}"


def _is_cache_valid(cache_entry: Dict) -> bool:
    """Check if cache entry is still valid"""
    if not cache_entry:
        return False
    
    cache_time = cache_entry.get('timestamp')
    if not cache_time:
        return False
    
    # Check if cache is within valid duration
    cache_age = datetime.now() - cache_time
    return cache_age.total_seconds() < (CACHE_DURATION_MINUTES * 60)


def cache_alerts(username: str, alerts: List[InventoryAlert], branch_filter: Optional[str] = None):
    """
    Cache generated alerts for performance optimization.
    
    Args:
        username: Username for cache key
        alerts: List of alerts to cache
        branch_filter: Branch filter used (for cache key)
    """
    cache_key = _get_cache_key(username, branch_filter)
    _alert_cache[cache_key] = {
        'alerts': alerts,
        'timestamp': datetime.now()
    }
    
    logger.debug(f"Cached {len(alerts)} alerts for user {username}, branch_filter: {branch_filter}")


def _get_cached_alerts(username: str, branch_filter: Optional[str] = None) -> Optional[List[InventoryAlert]]:
    """
    Get cached alerts if available and valid.
    
    Args:
        username: Username for cache key
        branch_filter: Branch filter used (for cache key)
        
    Returns:
        Cached alerts or None if not available/expired
    """
    cache_key = _get_cache_key(username, branch_filter)
    cache_entry = _alert_cache.get(cache_key)
    
    if _is_cache_valid(cache_entry):
        logger.debug(f"Using cached alerts for user {username}, branch_filter: {branch_filter}")
        return cache_entry['alerts']
    
    # Remove expired cache entry
    if cache_key in _alert_cache:
        del _alert_cache[cache_key]
    
    return None


def invalidate_alert_cache(username: str):
    """
    Invalidate alert cache for a user (called when new data is uploaded).
    
    Args:
        username: Username whose cache to invalidate
    """
    keys_to_remove = [key for key in _alert_cache.keys() if key.startswith(f"alerts_{username}_")]
    
    for key in keys_to_remove:
        del _alert_cache[key]
    
    logger.debug(f"Invalidated alert cache for user {username}")


@monitor_alert_generation_performance
def generate_inventory_alerts(
    username: str, 
    branch_filter: Optional[str] = None, 
    limit: int = 10
) -> List[InventoryAlert]:
    """
    Generate inventory alerts based on current stock levels.
    
    Args:
        username: Username to get inventory data for
        branch_filter: Optional branch filter (None for all branches)
        limit: Maximum number of alerts to return
        
    Returns:
        List of InventoryAlert objects sorted by priority and stock level
        
    Raises:
        Exception: If alert generation fails critically
    """
    start_time = time.time()
    
    try:
        # Check cache first
        cached_alerts = _get_cached_alerts(username, branch_filter)
        if cached_alerts is not None:
            # Apply limit to cached results
            return cached_alerts[:limit]
        
        logger.info(f"Generating alerts for user {username}, branch_filter: {branch_filter}")
        
        # Get inventory data from data store with error handling
        try:
            sales_df, inventory_df = data_store.get_branch_data(username, branch_filter)
        except Exception as data_error:
            logger.error(f"Failed to retrieve inventory data for user {username}: {data_error}")
            # Return empty list instead of crashing
            return []
        
        if inventory_df is None or inventory_df.empty:
            logger.warning(f"No inventory data available for user {username}")
            return []
        
        # Apply performance filter before alert generation
        try:
            from utils.performance_filter import filter_inactive_items
            sales_df, inventory_df, filter_stats = filter_inactive_items(
                sales_df, inventory_df, log_stats=True, username=username
            )
            
            logger.info(f"Performance filter applied: filtered {filter_stats['items_filtered']} inactive items "
                       f"({filter_stats['filtering_percentage']:.1f}% reduction)")
            
        except Exception as filter_error:
            logger.warning(f"Performance filtering failed, proceeding with unfiltered data: {filter_error}")
            # Continue with original data if filtering fails
        
        # Ensure required columns exist
        required_columns = ['product_code', 'Last_on_hand', 'branch_code']
        missing_columns = [col for col in required_columns if col not in inventory_df.columns]
        
        if missing_columns:
            logger.error(f"Missing required columns in inventory data: {missing_columns}")
            # Return empty list instead of raising exception
            return []
        
        alerts = []
        current_time = datetime.now()
        processed_items = 0
        skipped_items = 0
        
        # Process each inventory item with individual error handling
        for _, row in inventory_df.iterrows():
            try:
                # Extract data with safe defaults
                product_code = str(row.get('product_code', 'Unknown'))
                product_name = str(row.get('product_name', product_code))
                branch_code = str(row.get('branch_code', 'Unknown'))
                current_stock = row.get('Last_on_hand', 0)
                
                # Skip items with invalid product codes
                if not product_code or product_code == 'Unknown' or pd.isna(product_code):
                    skipped_items += 1
                    continue
                
                # Ensure stock is numeric with improved error handling
                try:
                    if pd.isna(current_stock):
                        current_stock = 0
                    else:
                        current_stock = int(float(current_stock))
                except (ValueError, TypeError, OverflowError):
                    logger.warning(f"Invalid stock value for product {product_code}: {current_stock}, defaulting to 0")
                    current_stock = 0
                
                # Ensure non-negative stock
                if current_stock < 0:
                    logger.warning(f"Negative stock for product {product_code}: {current_stock}, converting to 0")
                    current_stock = 0
                
                # Classify alert status
                status_text, css_class, priority = classify_alert_status(current_stock)
                
                # Only create alert if item needs attention (has a status)
                if status_text is not None:
                    # Truncate product name if too long
                    truncated_name = _truncate_product_name(product_name)
                    
                    alert = InventoryAlert(
                        product_code=product_code,
                        product_name=truncated_name,
                        branch_code=branch_code,
                        current_stock=current_stock,
                        alert_status=status_text,
                        status_class=css_class,
                        priority=priority,
                        last_updated=current_time
                    )
                    
                    alerts.append(alert)
                
                processed_items += 1
                    
            except Exception as item_error:
                logger.warning(f"Error processing inventory item: {item_error}")
                skipped_items += 1
                # Skip this item and continue processing others
                continue
        
        # Log processing statistics
        logger.info(f"Processed {processed_items} items, skipped {skipped_items} items, generated {len(alerts)} alerts")
        
        # Sort alerts by priority (lower number = higher priority), then by stock level (ascending)
        alerts.sort(key=lambda x: (x.priority, x.current_stock))
        
        # Cache the results
        cache_alerts(username, alerts, branch_filter)
        
        processing_time = time.time() - start_time
        logger.info(f"Generated {len(alerts)} alerts in {processing_time:.2f} seconds")
        
        # Apply limit and return
        return alerts[:limit]
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Error generating alerts for user {username}: {e}", exc_info=True)
        logger.error(f"Alert generation failed after {processing_time:.2f} seconds")
        
        # Try to return cached data as fallback
        try:
            cached_alerts = _get_cached_alerts(username, branch_filter)
            if cached_alerts is not None:
                logger.info(f"Returning cached alerts as fallback for user {username}")
                return cached_alerts[:limit]
        except Exception as cache_error:
            logger.error(f"Failed to retrieve cached alerts as fallback: {cache_error}")
        
        # If all else fails, return empty list instead of crashing
        logger.warning(f"Returning empty alert list for user {username} due to errors")
        return []


def get_alert_summary(username: str, branch_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Get summary statistics for inventory alerts.
    
    Args:
        username: Username to get data for
        branch_filter: Optional branch filter
        
    Returns:
        Dictionary with alert summary statistics
    """
    try:
        alerts = generate_inventory_alerts(username, branch_filter, limit=1000)  # Get all alerts for summary
        
        summary = {
            'total_alerts': len(alerts),
            'out_of_stock': 0,
            'very_low': 0,
            'low': 0,
            'reorder': 0,
            'last_updated': datetime.now().isoformat()
        }
        
        # Count alerts by status
        for alert in alerts:
            try:
                if alert.alert_status == 'نفد المخزون':
                    summary['out_of_stock'] += 1
                elif alert.alert_status == 'منخفض جداً':
                    summary['very_low'] += 1
                elif alert.alert_status == 'منخفض':
                    summary['low'] += 1
                elif alert.alert_status == 'إعادة طلب':
                    summary['reorder'] += 1
            except Exception as alert_error:
                logger.warning(f"Error processing alert in summary: {alert_error}")
                continue
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating alert summary: {e}")
        return {
            'total_alerts': 0,
            'out_of_stock': 0,
            'very_low': 0,
            'low': 0,
            'reorder': 0,
            'last_updated': datetime.now().isoformat(),
            'error': str(e)
        }


def generate_notifications(username: str) -> List[Dict[str, Any]]:
    """
    Generate dynamic notifications for items below safety stock or running out in 7 days.
    
    Args:
        username: Username to generate notifications for
        
    Returns:
        List of notification dictionaries
    """
    try:
        # Get inventory analysis results from user session
        user_session = data_store.get_user_session(username, 'inventory')
        if not user_session or 'data_ids' not in user_session or 'results' not in user_session['data_ids']:
            logger.info(f"No inventory analysis results found for user {username}")
            return []
            
        results_id = user_session['data_ids']['results']
        results_df = data_store.get_dataframe(results_id)
        
        if results_df is None or results_df.empty:
            logger.info(f"Inventory analysis results dataframe is empty for user {username}")
            return []
            
        # Get safety stock from params if available
        params = user_session.get('params', {})
        safety_stock_threshold = params.get('safety_stock', 0)
        
        notifications = []
        
        # We'll use the results_df which already contains coverage_days and Last_on_hand
        for _, row in results_df.iterrows():
            product_code = row.get('product_code', 'Unknown')
            product_name = row.get('product_name', product_code)
            current_stock = row.get('Last_on_hand', 0)
            coverage_days = row.get('coverage_days', 999)
            branch_code = row.get('branch_code', 'الكل')
            
            # Condition 1: Stock < Safety Stock (from params or explicit column if exists)
            # Check for a specific 'safety_stock' column first, then fallback to param
            item_safety_stock = row.get('safety_stock', safety_stock_threshold)
            
            is_below_safety = current_stock < item_safety_stock
            
            # Condition 2: Run out in 7 days (coverage_days < 7)
            is_running_out = coverage_days < 7
            
            if is_below_safety or is_running_out:
                msg = ""
                if current_stock == 0:
                    msg = f"نفد المخزون للمنتج {product_name} في فرع {branch_code}"
                elif is_running_out:
                    msg = f"المنتج {product_name} سينفد خلال {int(coverage_days)} أيام في فرع {branch_code}"
                else:
                    msg = f"المخزون ({int(current_stock)}) أقل من حد الأمان للمنتج {product_name} في فرع {branch_code}"
                
                notifications.append({
                    'id': f"notif_{product_code}_{branch_code}",
                    'title': 'تنبيه مخزون',
                    'message': msg,
                    'type': 'warning' if is_running_out else 'info',
                    'product_code': product_code,
                    'branch': branch_code,
                    'timestamp': datetime.now().isoformat()
                })
        
        # Sort notifications (running out first, then below safety)
        # For simplicity, just return them
        return notifications[:20]  # Limit to 20 notifications for the dropdown
        
    except Exception as e:
        logger.error(f"Error generating notifications: {e}", exc_info=True)
        return []