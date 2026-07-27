"""
Performance filtering module for inventory analysis optimization.

This module provides functionality to filter out inactive inventory items
(items with zero stock AND zero sales) before heavy processing operations
to improve application performance and prevent freezing.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.3, 4.5, 5.5
"""

import pandas as pd
import time
import logging
import os
from datetime import datetime
from typing import Tuple, Dict, Set, Optional, Any
from utils.logging_config import get_performance_logger

# Configure logging
logger = logging.getLogger(__name__)

# Configuration for bypass capability
BYPASS_FILTERING_ENV_VAR = 'BYPASS_PERFORMANCE_FILTERING'
BYPASS_FILTERING_CONFIG_FILE = '.bypass_filtering'


def should_bypass_filtering() -> bool:
    """
    Check if filtering should be bypassed for debugging purposes.
    
    Checks multiple sources for bypass configuration:
    1. Environment variable BYPASS_PERFORMANCE_FILTERING
    2. Configuration file .bypass_filtering in current directory
    
    Returns:
        True if filtering should be bypassed, False otherwise
        
    Requirements: 5.5
    """
    try:
        # Check environment variable
        if os.environ.get(BYPASS_FILTERING_ENV_VAR, '').lower() in ('true', '1', 'yes', 'on'):
            logger.info("Performance filtering bypassed via environment variable")
            return True
        
        # Check configuration file
        if os.path.exists(BYPASS_FILTERING_CONFIG_FILE):
            try:
                with open(BYPASS_FILTERING_CONFIG_FILE, 'r') as f:
                    content = f.read().strip().lower()
                    if content in ('true', '1', 'yes', 'on'):
                        logger.info("Performance filtering bypassed via configuration file")
                        return True
            except Exception as e:
                logger.debug(f"Could not read bypass configuration file: {e}")
        
        return False
        
    except Exception as e:
        logger.debug(f"Error checking bypass configuration: {e}")
        return False


def measure_processing_performance(
    df_sales: pd.DataFrame, 
    df_inventory: pd.DataFrame,
    processing_func,
    *args, **kwargs
) -> Dict[str, Any]:
    """
    Measure performance improvement from filtering by comparing processing times.
    
    Args:
        df_sales: Sales DataFrame
        df_inventory: Inventory DataFrame  
        processing_func: Function to measure (should accept df_sales, df_inventory as first args)
        *args, **kwargs: Additional arguments for processing_func
        
    Returns:
        Dictionary with performance comparison metrics
        
    Requirements: 4.1, 4.3, 4.5
    """
    try:
        # Measure unfiltered processing time
        start_time = time.time()
        memory_before = get_memory_usage_mb()
        
        try:
            unfiltered_result = processing_func(df_sales, df_inventory, *args, **kwargs)
            unfiltered_time = time.time() - start_time
            unfiltered_success = True
        except Exception as e:
            unfiltered_time = time.time() - start_time
            unfiltered_success = False
            unfiltered_result = None
            logger.debug(f"Unfiltered processing failed: {e}")
        
        memory_after_unfiltered = get_memory_usage_mb()
        
        # Apply filtering
        filter_start = time.time()
        filtered_sales, filtered_inventory, filter_stats = filter_inactive_items(
            df_sales, df_inventory, log_stats=False
        )
        filter_time = time.time() - filter_start
        
        # Measure filtered processing time
        start_time = time.time()
        memory_before_filtered = get_memory_usage_mb()
        
        try:
            filtered_result = processing_func(filtered_sales, filtered_inventory, *args, **kwargs)
            filtered_time = time.time() - start_time
            filtered_success = True
        except Exception as e:
            filtered_time = time.time() - start_time
            filtered_success = False
            filtered_result = None
            logger.debug(f"Filtered processing failed: {e}")
        
        memory_after_filtered = get_memory_usage_mb()
        
        # Calculate performance metrics
        total_filtered_time = filter_time + filtered_time
        time_savings = unfiltered_time - total_filtered_time if unfiltered_success and filtered_success else 0
        time_improvement_percent = (time_savings / unfiltered_time * 100) if unfiltered_time > 0 and unfiltered_success else 0
        
        # Calculate memory metrics
        memory_savings = 0
        if memory_before and memory_after_unfiltered and memory_before_filtered and memory_after_filtered:
            unfiltered_memory_usage = memory_after_unfiltered - memory_before
            filtered_memory_usage = memory_after_filtered - memory_before_filtered
            memory_savings = unfiltered_memory_usage - filtered_memory_usage
        
        performance_metrics = {
            'unfiltered_time_ms': round(unfiltered_time * 1000, 2),
            'filter_time_ms': round(filter_time * 1000, 2),
            'filtered_processing_time_ms': round(filtered_time * 1000, 2),
            'total_filtered_time_ms': round(total_filtered_time * 1000, 2),
            'time_savings_ms': round(time_savings * 1000, 2),
            'time_improvement_percent': round(time_improvement_percent, 2),
            'memory_savings_mb': round(memory_savings, 2),
            'items_filtered': filter_stats.get('items_filtered', 0),
            'filtering_percentage': filter_stats.get('filtering_percentage', 0),
            'unfiltered_success': unfiltered_success,
            'filtered_success': filtered_success,
            'performance_improved': time_savings > 0 and filtered_success,
            'timestamp': datetime.now().isoformat()
        }
        
        # Log performance comparison
        log_performance_comparison(performance_metrics)
        
        return performance_metrics
        
    except Exception as e:
        logger.error(f"Error measuring processing performance: {str(e)}", exc_info=True)
        return {
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def log_performance_comparison(metrics: Dict[str, Any]) -> None:
    """
    Log performance comparison metrics for monitoring.
    
    Args:
        metrics: Performance comparison metrics dictionary
        
    Requirements: 4.5
    """
    try:
        perf_logger = get_performance_logger()
        
        # Prepare performance comparison data
        perf_data = {
            'event': 'performance_comparison',
            **metrics
        }
        
        # Determine log level and message based on results
        if metrics.get('error'):
            level = logging.ERROR
            message = f"Performance measurement failed: {metrics['error']}"
        elif metrics.get('performance_improved', False):
            level = logging.INFO
            improvement = metrics.get('time_improvement_percent', 0)
            savings = metrics.get('time_savings_ms', 0)
            message = f"Performance improved by {improvement:.1f}% ({savings:.1f}ms savings) through filtering"
        elif metrics.get('filtered_success', False):
            level = logging.INFO
            message = f"Filtering applied but no significant performance improvement detected"
        else:
            level = logging.WARNING
            message = f"Performance measurement completed but filtering may not be beneficial"
        
        # Log to performance logger
        perf_logger.logger.log(level, message, extra={'extra_data': perf_data})
        
        # Also log summary to main logger
        if metrics.get('performance_improved', False):
            logger.info(f"Performance improvement: {metrics.get('time_improvement_percent', 0):.1f}% "
                       f"({metrics.get('time_savings_ms', 0):.1f}ms savings)")
        
    except Exception as e:
        logger.error(f"Error logging performance comparison: {str(e)}", exc_info=True)


def filter_inactive_items(
    df_sales: pd.DataFrame, 
    df_inventory: pd.DataFrame,
    log_stats: bool = True,
    username: Optional[str] = None,
    bypass_check: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Filter out inactive inventory items to improve processing performance.
    
    An inactive item is defined as having both:
    - Zero stock balance (Last_on_hand = 0)
    - No sales activity (quantity_sold = 0 or no sales records)
    
    Args:
        df_sales: Sales DataFrame
        df_inventory: Inventory DataFrame
        log_stats: Whether to log filtering statistics
        username: Username for logging context (optional)
        bypass_check: Whether to check for bypass configuration (default: True)
        
    Returns:
        Tuple of (filtered_sales_df, filtered_inventory_df, statistics_dict)
        
    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.5
    """
    start_time = time.time()
    
    # Check if filtering should be bypassed
    if bypass_check and should_bypass_filtering():
        logger.info("Performance filtering bypassed due to configuration")
        return df_sales, df_inventory, {
            'items_filtered': 0,
            'total_items_before': len(df_inventory) if df_inventory is not None else 0,
            'total_items_after': len(df_inventory) if df_inventory is not None else 0,
            'filtering_percentage': 0.0,
            'processing_time_ms': (time.time() - start_time) * 1000,
            'bypassed': True,
            'error': None
        }
    
    try:
        # Validate input DataFrames
        if df_sales is None or df_inventory is None:
            logger.warning("Received None DataFrame(s) for filtering")
            return df_sales, df_inventory, {
                'items_filtered': 0,
                'total_items_before': 0,
                'total_items_after': 0,
                'filtering_percentage': 0.0,
                'processing_time_ms': 0.0,
                'error': 'Invalid input DataFrames'
            }
        
        if df_sales.empty or df_inventory.empty:
            logger.info("Empty DataFrame(s) provided, no filtering needed")
            return df_sales, df_inventory, {
                'items_filtered': 0,
                'total_items_before': len(df_inventory),
                'total_items_after': len(df_inventory),
                'filtering_percentage': 0.0,
                'processing_time_ms': (time.time() - start_time) * 1000,
                'error': None
            }
        
        # Validate required columns
        required_sales_cols = ['product_code']
        required_inventory_cols = ['product_code', 'Last_on_hand']
        
        missing_sales_cols = [col for col in required_sales_cols if col not in df_sales.columns]
        missing_inventory_cols = [col for col in required_inventory_cols if col not in df_inventory.columns]
        
        if missing_sales_cols or missing_inventory_cols:
            error_msg = f"Missing required columns - Sales: {missing_sales_cols}, Inventory: {missing_inventory_cols}"
            logger.warning(f"Column validation failed: {error_msg}")
            return df_sales, df_inventory, {
                'items_filtered': 0,
                'total_items_before': len(df_inventory),
                'total_items_after': len(df_inventory),
                'filtering_percentage': 0.0,
                'processing_time_ms': (time.time() - start_time) * 1000,
                'error': error_msg
            }
        
        # Store original counts
        original_inventory_count = len(df_inventory)
        original_sales_count = len(df_sales)
        
        # Identify inactive items
        inactive_items = identify_inactive_items(df_sales, df_inventory)
        
        # Filter DataFrames to remove inactive items
        filtered_inventory = df_inventory[~df_inventory['product_code'].isin(inactive_items)].copy()
        filtered_sales = df_sales[~df_sales['product_code'].isin(inactive_items)].copy()
        
        # Calculate statistics
        items_filtered = len(inactive_items)
        items_after = len(filtered_inventory)
        filtering_percentage = (items_filtered / original_inventory_count * 100) if original_inventory_count > 0 else 0.0
        processing_time = time.time() - start_time
        
        # Validate filtering integrity
        integrity_valid = validate_filtering_integrity(df_inventory, filtered_inventory)
        
        # Validate referential integrity between sales and inventory data
        referential_integrity = validate_referential_integrity(
            df_sales, df_inventory, filtered_sales, filtered_inventory
        )
        
        # If referential integrity issues are found and repair is needed, attempt repair
        if referential_integrity['repair_needed']:
            logger.warning("Referential integrity issues detected, attempting repair")
            filtered_sales, filtered_inventory, repair_summary = repair_referential_integrity(
                filtered_sales, filtered_inventory, referential_integrity
            )
            
            # Re-validate after repair
            referential_integrity = validate_referential_integrity(
                df_sales, df_inventory, filtered_sales, filtered_inventory
            )
        
        stats = {
            'items_filtered': items_filtered,
            'total_items_before': original_inventory_count,
            'total_items_after': items_after,
            'sales_records_before': original_sales_count,
            'sales_records_after': len(filtered_sales),
            'filtering_percentage': round(filtering_percentage, 2),
            'processing_time_ms': round(processing_time * 1000, 2),
            'integrity_valid': integrity_valid,
            'referential_integrity': referential_integrity,
            'timestamp': datetime.now().isoformat(),
            'error': None
        }
        
        # Log statistics if requested
        if log_stats:
            log_filtering_stats(stats, username)
        
        logger.info(f"Filtering completed: {items_filtered} inactive items removed "
                   f"({filtering_percentage:.1f}% reduction)")
        
        return filtered_sales, filtered_inventory, stats
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Error during filtering: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Return original data on error with error statistics
        return df_sales, df_inventory, {
            'items_filtered': 0,
            'total_items_before': len(df_inventory) if df_inventory is not None else 0,
            'total_items_after': len(df_inventory) if df_inventory is not None else 0,
            'filtering_percentage': 0.0,
            'processing_time_ms': round(processing_time * 1000, 2),
            'error': error_msg
        }


def identify_inactive_items(df_sales: pd.DataFrame, df_inventory: pd.DataFrame) -> Set[str]:
    """
    Identify inactive items that have both zero stock AND zero sales.
    
    A product is considered inactive only if:
    - ALL instances of that product have zero stock (Last_on_hand = 0), AND
    - The product has no sales activity (quantity_sold = 0 or no sales records)
    
    Args:
        df_sales: Sales DataFrame
        df_inventory: Inventory DataFrame
        
    Returns:
        Set of product codes for inactive items
        
    Requirements: 1.1, 1.2, 1.3
    """
    try:
        # Ensure numeric columns are properly typed to prevent string comparison errors
        if 'Last_on_hand' in df_inventory.columns:
            df_inventory = df_inventory.copy()
            df_inventory['Last_on_hand'] = pd.to_numeric(df_inventory['Last_on_hand'], errors='coerce').fillna(0)
        
        if 'quantity_sold' in df_sales.columns:
            df_sales = df_sales.copy()
            df_sales['quantity_sold'] = pd.to_numeric(df_sales['quantity_sold'], errors='coerce').fillna(0)
        
        # Get items with sales activity (quantity_sold > 0)
        if 'quantity_sold' in df_sales.columns:
            # Use quantity_sold column to determine actual sales activity
            items_with_sales = set(
                df_sales[df_sales['quantity_sold'] > 0]['product_code']
            )
        else:
            # Fallback: any item that appears in sales data has sales activity
            # But only if the sales DataFrame is not empty and has meaningful data
            if not df_sales.empty and len(df_sales.columns) > 1:
                items_with_sales = set(df_sales['product_code'])
            else:
                items_with_sales = set()  # Empty sales data means no sales activity
        
        # Get products where ALL instances have zero stock
        # Group by product_code and check if max stock is 0
        stock_by_product = df_inventory.groupby('product_code')['Last_on_hand'].max()
        products_with_zero_stock = set(stock_by_product[stock_by_product == 0].index)
        
        # Inactive items = ALL instances have zero stock AND no sales activity
        inactive_items = products_with_zero_stock - items_with_sales
        
        logger.debug(f"Identified {len(inactive_items)} inactive items from "
                    f"{len(products_with_zero_stock)} zero-stock products and "
                    f"{len(items_with_sales)} products with sales")
        
        return inactive_items
        
    except Exception as e:
        logger.error(f"Error identifying inactive items: {str(e)}", exc_info=True)
        return set()  # Return empty set on error to avoid filtering


def log_filtering_stats(stats: Dict[str, Any], username: Optional[str] = None) -> None:
    """
    Log filtering statistics for performance monitoring.
    
    Args:
        stats: Statistics dictionary from filtering operation
        username: Username for logging context (optional)
        
    Requirements: 1.5, 4.5, 5.1, 5.2, 5.3
    """
    try:
        perf_logger = get_performance_logger()
        
        # Prepare performance data
        perf_data = {
            'event': 'performance_filtering',
            'username': username or 'unknown',
            'items_filtered': stats.get('items_filtered', 0),
            'total_items_before': stats.get('total_items_before', 0),
            'total_items_after': stats.get('total_items_after', 0),
            'filtering_percentage': stats.get('filtering_percentage', 0.0),
            'processing_time_ms': stats.get('processing_time_ms', 0.0),
            'sales_records_before': stats.get('sales_records_before', 0),
            'sales_records_after': stats.get('sales_records_after', 0),
            'integrity_valid': stats.get('integrity_valid', True),
            'referential_integrity_valid': stats.get('referential_integrity', {}).get('is_valid', True),
            'referential_integrity_violations': len(stats.get('referential_integrity', {}).get('integrity_violations', [])),
            'orphaned_references_found': len(stats.get('referential_integrity', {}).get('orphaned_sales_references', [])),
            'timestamp': stats.get('timestamp', datetime.now().isoformat()),
            'error': stats.get('error')
        }
        
        # Determine log level based on filtering results
        referential_integrity = stats.get('referential_integrity', {})
        has_referential_issues = not referential_integrity.get('is_valid', True)
        
        if stats.get('error'):
            level = logging.ERROR
            message = f"Performance filtering failed: {stats['error']}"
        elif has_referential_issues:
            level = logging.WARNING
            violations = len(referential_integrity.get('integrity_violations', []))
            message = f"Performance filtering completed with referential integrity issues: {violations} violations"
        elif stats.get('filtering_percentage', 0) > 20:
            level = logging.INFO
            message = f"Significant performance improvement: filtered {stats['items_filtered']} items ({stats['filtering_percentage']:.1f}%)"
        elif stats.get('items_filtered', 0) > 0:
            level = logging.INFO
            message = f"Performance filtering applied: {stats['items_filtered']} items filtered"
        else:
            level = logging.DEBUG
            message = "No items filtered - all items are active"
        
        # Log to performance logger
        perf_logger.logger.log(level, message, extra={'extra_data': perf_data})
        
        # Also log to main logger for visibility
        logger.info(f"Filtering stats - Items: {stats.get('items_filtered', 0)} filtered, "
                   f"Reduction: {stats.get('filtering_percentage', 0):.1f}%, "
                   f"Time: {stats.get('processing_time_ms', 0):.1f}ms")
        
    except Exception as e:
        logger.error(f"Error logging filtering statistics: {str(e)}", exc_info=True)


def validate_filtering_integrity(original_df: pd.DataFrame, filtered_df: pd.DataFrame) -> bool:
    """
    Validate that filtering preserved data integrity.
    
    Args:
        original_df: Original DataFrame before filtering
        filtered_df: Filtered DataFrame after filtering
        
    Returns:
        True if integrity is maintained, False otherwise
        
    Requirements: 1.4, 3.1, 3.2, 3.3, 3.4
    """
    try:
        # Basic integrity checks
        if filtered_df is None:
            logger.warning("Filtered DataFrame is None")
            return False
        
        if len(filtered_df) > len(original_df):
            logger.error("Filtered DataFrame has more records than original")
            return False
        
        # Check that all remaining items have either stock > 0 OR sales activity
        # Note: We can't check sales activity here since we only have inventory DataFrame
        # This check is performed in the property tests
        
        # Check for required columns preservation
        required_cols = ['product_code', 'Last_on_hand']
        for col in required_cols:
            if col in original_df.columns and col not in filtered_df.columns:
                logger.error(f"Required column {col} missing from filtered DataFrame")
                return False
        
        # Check that no items with stock > 0 were filtered out
        if 'Last_on_hand' in original_df.columns and 'Last_on_hand' in filtered_df.columns:
            # Ensure Last_on_hand is numeric to avoid string comparison errors
            original_df_temp = original_df.copy()
            filtered_df_temp = filtered_df.copy()
            original_df_temp['Last_on_hand'] = pd.to_numeric(original_df_temp['Last_on_hand'], errors='coerce').fillna(0)
            filtered_df_temp['Last_on_hand'] = pd.to_numeric(filtered_df_temp['Last_on_hand'], errors='coerce').fillna(0)
            
            original_with_stock = set(
                original_df_temp[original_df_temp['Last_on_hand'] > 0]['product_code']
            )
            filtered_with_stock = set(
                filtered_df_temp[filtered_df_temp['Last_on_hand'] > 0]['product_code']
            )
            
            missing_stock_items = original_with_stock - filtered_with_stock
            if missing_stock_items:
                logger.error(f"Items with stock were incorrectly filtered: {len(missing_stock_items)} items")
                return False
        
        logger.debug("Filtering integrity validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Error validating filtering integrity: {str(e)}", exc_info=True)
        return False


def validate_referential_integrity(
    original_sales_df: pd.DataFrame,
    original_inventory_df: pd.DataFrame,
    filtered_sales_df: pd.DataFrame,
    filtered_inventory_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Validate referential integrity between sales and inventory data after filtering.
    
    Ensures that sales-inventory relationships remain valid and identifies any
    orphaned references that may need repair.
    
    Args:
        original_sales_df: Original sales DataFrame before filtering
        original_inventory_df: Original inventory DataFrame before filtering
        filtered_sales_df: Filtered sales DataFrame after filtering
        filtered_inventory_df: Filtered inventory DataFrame after filtering
        
    Returns:
        Dictionary containing integrity validation results and repair information
        
    Requirements: 3.5
    """
    try:
        integrity_results = {
            'is_valid': True,
            'orphaned_sales_references': [],
            'orphaned_inventory_references': [],
            'missing_sales_products': [],
            'missing_inventory_products': [],
            'integrity_violations': [],
            'repair_needed': False,
            'validation_timestamp': datetime.now().isoformat(),
            'error': None
        }
        
        # Validate input DataFrames
        if any(df is None for df in [original_sales_df, original_inventory_df, filtered_sales_df, filtered_inventory_df]):
            integrity_results['error'] = 'One or more DataFrames is None'
            integrity_results['is_valid'] = False
            return integrity_results
        
        # Get product codes from each DataFrame
        original_sales_products = set(original_sales_df['product_code']) if not original_sales_df.empty else set()
        original_inventory_products = set(original_inventory_df['product_code']) if not original_inventory_df.empty else set()
        filtered_sales_products = set(filtered_sales_df['product_code']) if not filtered_sales_df.empty else set()
        filtered_inventory_products = set(filtered_inventory_df['product_code']) if not filtered_inventory_df.empty else set()
        
        # Check for orphaned sales references (sales records without corresponding inventory)
        orphaned_sales = filtered_sales_products - filtered_inventory_products
        if orphaned_sales:
            integrity_results['orphaned_sales_references'] = list(orphaned_sales)
            integrity_results['integrity_violations'].append(
                f"Found {len(orphaned_sales)} sales records without corresponding inventory records"
            )
            logger.warning(f"Orphaned sales references found: {orphaned_sales}")
        
        # Check for orphaned inventory references (inventory records without corresponding sales)
        # Note: This is not necessarily a violation since items can have inventory without sales
        orphaned_inventory = filtered_inventory_products - filtered_sales_products
        if orphaned_inventory:
            integrity_results['orphaned_inventory_references'] = list(orphaned_inventory)
            # This is informational, not a violation
            logger.debug(f"Inventory items without sales records: {len(orphaned_inventory)} items")
        
        # Check for products that were in original data but missing from filtered data
        missing_sales_products = original_sales_products - filtered_sales_products
        missing_inventory_products = original_inventory_products - filtered_inventory_products
        
        if missing_sales_products:
            integrity_results['missing_sales_products'] = list(missing_sales_products)
            logger.debug(f"Sales products filtered out: {len(missing_sales_products)} items")
        
        if missing_inventory_products:
            integrity_results['missing_inventory_products'] = list(missing_inventory_products)
            logger.debug(f"Inventory products filtered out: {len(missing_inventory_products)} items")
        
        # Validate that filtering was consistent between sales and inventory
        # Items that were filtered from inventory should also be filtered from sales (if they existed)
        inconsistent_filtering = []
        for product in missing_inventory_products:
            if product in filtered_sales_products:
                inconsistent_filtering.append(product)
                integrity_results['integrity_violations'].append(
                    f"Product {product} was filtered from inventory but not from sales"
                )
        
        if inconsistent_filtering:
            integrity_results['is_valid'] = False
            logger.error(f"Inconsistent filtering detected for products: {inconsistent_filtering}")
        
        # Check for data consistency within filtered datasets
        # Verify that product codes are consistent between related records
        if not filtered_sales_df.empty and not filtered_inventory_df.empty:
            # Check for duplicate product codes within each DataFrame
            sales_duplicates = filtered_sales_df['product_code'].duplicated().sum()
            inventory_duplicates = filtered_inventory_df['product_code'].duplicated().sum()
            
            if sales_duplicates > 0:
                logger.debug(f"Found {sales_duplicates} duplicate product codes in filtered sales data")
            
            if inventory_duplicates > 0:
                logger.debug(f"Found {inventory_duplicates} duplicate product codes in filtered inventory data")
        
        # Determine if repair is needed
        if integrity_results['orphaned_sales_references'] or inconsistent_filtering:
            integrity_results['repair_needed'] = True
            integrity_results['is_valid'] = False
        
        # Log validation results
        if integrity_results['is_valid']:
            logger.debug("Referential integrity validation passed")
        else:
            logger.warning(f"Referential integrity validation failed: {len(integrity_results['integrity_violations'])} violations")
        
        return integrity_results
        
    except Exception as e:
        error_msg = f"Error validating referential integrity: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'is_valid': False,
            'orphaned_sales_references': [],
            'orphaned_inventory_references': [],
            'missing_sales_products': [],
            'missing_inventory_products': [],
            'integrity_violations': [error_msg],
            'repair_needed': False,
            'validation_timestamp': datetime.now().isoformat(),
            'error': error_msg
        }


def repair_referential_integrity(
    sales_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    integrity_results: Dict[str, Any]
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Repair referential integrity violations between sales and inventory data.
    
    Removes orphaned references and ensures data consistency between datasets.
    
    Args:
        sales_df: Sales DataFrame with potential integrity issues
        inventory_df: Inventory DataFrame with potential integrity issues
        integrity_results: Results from validate_referential_integrity
        
    Returns:
        Tuple of (repaired_sales_df, repaired_inventory_df, repair_summary)
        
    Requirements: 3.5
    """
    try:
        repair_summary = {
            'repairs_applied': [],
            'orphaned_sales_removed': 0,
            'orphaned_inventory_removed': 0,
            'repair_successful': True,
            'repair_timestamp': datetime.now().isoformat(),
            'error': None
        }
        
        # Make copies to avoid modifying original DataFrames
        repaired_sales = sales_df.copy()
        repaired_inventory = inventory_df.copy()
        
        # Repair orphaned sales references (remove sales records without inventory)
        orphaned_sales = integrity_results.get('orphaned_sales_references', [])
        if orphaned_sales:
            original_sales_count = len(repaired_sales)
            repaired_sales = repaired_sales[~repaired_sales['product_code'].isin(orphaned_sales)]
            removed_sales = original_sales_count - len(repaired_sales)
            
            repair_summary['orphaned_sales_removed'] = removed_sales
            repair_summary['repairs_applied'].append(f"Removed {removed_sales} orphaned sales records")
            logger.info(f"Removed {removed_sales} orphaned sales records for products: {orphaned_sales}")
        
        # Note: We don't remove orphaned inventory references as items can legitimately have
        # inventory without sales (new items, items with no recent sales, etc.)
        
        # Validate that repair was successful
        if not repaired_sales.empty and not repaired_inventory.empty:
            sales_products = set(repaired_sales['product_code'])
            inventory_products = set(repaired_inventory['product_code'])
            
            # Check if there are still orphaned sales references
            remaining_orphaned_sales = sales_products - inventory_products
            if remaining_orphaned_sales:
                repair_summary['repair_successful'] = False
                repair_summary['error'] = f"Repair incomplete: {len(remaining_orphaned_sales)} orphaned sales references remain"
                logger.error(f"Repair incomplete: orphaned sales references remain: {remaining_orphaned_sales}")
        
        # Log repair summary
        if repair_summary['repair_successful']:
            logger.info(f"Referential integrity repair completed successfully: {len(repair_summary['repairs_applied'])} repairs applied")
        else:
            logger.error(f"Referential integrity repair failed: {repair_summary['error']}")
        
        return repaired_sales, repaired_inventory, repair_summary
        
    except Exception as e:
        error_msg = f"Error repairing referential integrity: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        repair_summary = {
            'repairs_applied': [],
            'orphaned_sales_removed': 0,
            'orphaned_inventory_removed': 0,
            'repair_successful': False,
            'repair_timestamp': datetime.now().isoformat(),
            'error': error_msg
        }
        
        return sales_df, inventory_df, repair_summary


def filter_inactive_items_with_fallback(
    df_sales: pd.DataFrame, 
    df_inventory: pd.DataFrame,
    log_stats: bool = True,
    username: Optional[str] = None,
    bypass_check: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Filter inactive items with graceful fallback on errors.
    
    This function provides error recovery by returning original data
    if filtering fails, ensuring the application continues to function.
    
    Args:
        df_sales: Sales DataFrame
        df_inventory: Inventory DataFrame
        log_stats: Whether to log filtering statistics
        username: Username for logging context (optional)
        bypass_check: Whether to check for bypass configuration (default: True)
        
    Returns:
        Tuple of (filtered_sales_df, filtered_inventory_df, statistics_dict)
        
    Requirements: 5.4, 5.5
    """
    try:
        return filter_inactive_items(df_sales, df_inventory, log_stats, username, bypass_check)
    except Exception as e:
        logger.warning(f"Filtering failed for user {username}: {e}, proceeding with unfiltered data")
        
        # Return original data with error statistics
        return df_sales, df_inventory, {
            'items_filtered': 0,
            'total_items_before': len(df_inventory) if df_inventory is not None else 0,
            'total_items_after': len(df_inventory) if df_inventory is not None else 0,
            'filtering_percentage': 0.0,
            'processing_time_ms': 0.0,
            'error': f'Filtering failed: {str(e)}',
            'fallback_used': True
        }


def get_memory_usage_mb() -> Optional[float]:
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


def calculate_memory_difference(original_df: pd.DataFrame, filtered_df: pd.DataFrame) -> float:
    """
    Calculate memory savings from filtering in MB.
    
    Args:
        original_df: Original DataFrame
        filtered_df: Filtered DataFrame
        
    Returns:
        Memory difference in MB (positive means savings)
    """
    try:
        original_memory = original_df.memory_usage(deep=True).sum() / (1024 * 1024)
        filtered_memory = filtered_df.memory_usage(deep=True).sum() / (1024 * 1024)
        return original_memory - filtered_memory
    except Exception as e:
        logger.debug(f"Could not calculate memory difference: {e}")
        return 0.0