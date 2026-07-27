"""
MongoDB-backed data store (Phase 2 §3.3, Phase 4 §5 — cutover complete).

This module replaces the legacy DuckDB ``data_store.py`` (removed).  The same public API is preserved so
all callers (``flask_app.py``, ``utils/alert_service.py``, etc.) continue
to ``import data_store`` and call module-level functions without changes.

Under the hood every function delegates to a single cached
:class:`data_store_mongo.MongoDataStore` instance.
"""

import logging
from typing import Dict, Optional, Tuple, Any, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy singleton — defer the pymongo import so the module can be imported
# even when MongoDB is unreachable (callers catch errors at call time).
# ---------------------------------------------------------------------------
_store = None  # type: Optional[MongoDataStore]


def _get_store():
    global _store
    if _store is None:
        from data_store_mongo import MongoDataStore
        _store = MongoDataStore()
        logger.info("MongoDataStore singleton initialised.")
    return _store


# ---------------------------------------------------------------------------
# Migrated public API — every function mirrors the old DuckDB module.
# ---------------------------------------------------------------------------

def get_data_store():
    """Return the active data-store singleton (compatibility function)."""
    return _get_store()


def init_data_db() -> bool:
    """MongoDB needs no schema init; returns True for compat."""
    return _get_store().init_data_db()


def save_uploaded_file(username, module, filename, file_data, branch_name=None) -> int:
    return _get_store().save_uploaded_file(username, module, filename, file_data, branch_name)


def get_uploaded_file(file_id):
    return _get_store().get_uploaded_file(file_id)


def get_user_files(username, module, limit=10):
    return _get_store().get_user_files(username, module, limit)


def get_branch_files(username):
    return _get_store().get_branch_files(username)


def save_dataframe(username, module, data_type, df, metadata=None, branch_name=None) -> int:
    return _get_store().save_dataframe(username, module, data_type, df, metadata, branch_name)


def get_dataframe(data_id) -> Optional[Any]:
    return _get_store().get_dataframe(data_id)


def save_user_session(username, module, file_id, data_ids, params=None):
    return _get_store().save_user_session(username, module, file_id, data_ids, params)


def get_user_session(username, module) -> Optional[Dict[str, Any]]:
    return _get_store().get_user_session(username, module)


def clear_user_session(username, module) -> bool:
    return _get_store().clear_user_session(username, module)


def save_branch_data(username, branch_name, sales_df, inventory_df):
    return _get_store().save_branch_data(username, branch_name, sales_df, inventory_df)


def get_all_branches(username) -> List[str]:
    return _get_store().get_all_branches(username)


def get_branch_data(username, branch_name=None) -> Tuple[Optional[Any], Optional[Any]]:
    return _get_store().get_branch_data(username, branch_name)


def delete_branch_data(username, branch_name) -> Tuple[bool, str]:
    return _get_store().delete_branch_data(username, branch_name)


def clear_all_data():
    return _get_store().clear_all_data()


def clear_user_data(username):
    return _get_store().clear_user_data(username)


def calculate_dashboard_metrics(sales_df, inventory_df) -> Dict[str, Any]:
    return _get_store().calculate_dashboard_metrics(sales_df, inventory_df)


def get_filtered_inventory_data(results_df, filters) -> Any:
    return _get_store().get_filtered_inventory_data(results_df, filters)


def validate_data_ownership(username: str, data_ids: dict) -> Tuple[bool, str]:
    return _get_store().validate_data_ownership(username, data_ids)


def get_database_health() -> Dict[str, Any]:
    return _get_store().get_database_health()


def repair_database() -> Tuple[bool, str]:
    return _get_store().repair_database()


# ---------------------------------------------------------------------------
# AI-specific helpers
# ---------------------------------------------------------------------------

def save_ai_query(username, query, response, model):
    return _get_store().save_ai_query(username, query, response, model)


def get_ai_query_history(username, limit=10):
    return _get_store().get_ai_query_history(username, limit)


def save_ai_cache(key, data, ttl=3600):
    return _get_store().save_ai_cache(key, data, ttl)


def get_ai_cache(key):
    return _get_store().get_ai_cache(key)


def save_ai_performance_metric(metric_name, value, tags=None):
    return _get_store().save_ai_performance_metric(metric_name, value, tags)


def get_ai_performance_metrics(hours=24):
    return _get_store().get_ai_performance_metrics(hours)


def cleanup_ai_data(retention_days=30):
    return _get_store().cleanup_ai_data(retention_days)


def get_ai_database_stats():
    return _get_store().get_ai_database_stats()


def test_ai_database_functionality():
    return _get_store().test_ai_database_functionality()


def get_user_session_collection():
    return _get_store().get_user_session_collection()


# ---------------------------------------------------------------------------
# DB_NAME — used by some legacy callers (session_validator, debug scripts).
# Exposed here for back‑compat; these callers will eventually be refactored to
# use the MongoDataStore directly.
# ---------------------------------------------------------------------------

try:
    DB_NAME = _get_store().DB_NAME
except Exception:
    DB_NAME = "tif"
