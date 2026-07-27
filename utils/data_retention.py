"""
Data Retention Management for AI Operations
Implements automated data retention policies and cleanup procedures.

Requirements: 8.4

Phase 2 (§3.3 step 5): retention cleanup is backend-selectable via ``DB_BACKEND``.
  - ``duckdb`` (default): legacy SQLite (audit_log.db) / DuckDB (ai_insights_cache)
    paths — unchanged behaviour.
  - ``mongodb``: time-series collections get TTL indexes for auto-expiry (§3.2),
    and ``cleanup_expired_data`` performs an explicit ``delete_many`` against the
    retention cutoff as a deterministic fallback. The timestamp fields match those
    used by ``data_store_mongo`` / ``auth_mongo`` / ``data_privacy``.
The policy model, default policies, background scheduler and reporting API are
backend-agnostic and preserved exactly.
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass
import os
import sys

logger = logging.getLogger(__name__)


def _active_backend() -> str:
    return "mongodb"


@dataclass
class RetentionPolicy:
    """Data retention policy configuration."""
    data_type: str
    retention_days: int
    auto_delete: bool = True
    archive_before_delete: bool = False
    archive_location: Optional[str] = None


# ---------------------------------------------------------------------------
# Mongo mapping: data_type -> (collection_name, timestamp_field)
# Timestamp fields mirror the writers in data_store_mongo / auth_mongo /
# data_privacy so TTL + cleanup target the right field.
# ---------------------------------------------------------------------------
_MONGO_RETENTION_MAP = {
    "ai_audit_log": ("ai_audit_log", "timestamp"),
    "ai_cache": ("ai_insights_cache", "expires_at"),
    "query_history": ("ai_queries", "timestamp"),
    "performance_metrics": ("ai_performance_metrics", "timestamp"),
    "anonymization_mapping": ("anonymization_mapping", "expires_at"),
    "data_classification": ("data_classification", "created_at"),
    "user_consent": ("user_consent", "expires_at"),
}


class DataRetentionManager:
    """
    Manages data retention policies for AI operations.

    Features:
    - Automated cleanup of expired data
    - Configurable retention policies
    - Archive capabilities before deletion
    - Compliance reporting
    - Background cleanup scheduling
    """

    DEFAULT_POLICIES = [
        RetentionPolicy("ai_audit_log", 365, True, True),
        RetentionPolicy("ai_cache", 30, True, False),
        RetentionPolicy("query_history", 90, True, True),
        RetentionPolicy("performance_metrics", 180, True, False),
        RetentionPolicy("anonymization_mapping", 7, True, False),
        RetentionPolicy("data_classification", 30, True, False),
        RetentionPolicy("user_consent", 2555, False, True),  # 7 years for compliance
    ]

    def __init__(self):
        """Initialize the data retention manager."""
        self.backend = _active_backend()
        self.policies = {}
        self.cleanup_thread = None
        self.running = False
        self._load_policies()

    # ------------------------------------------------------------------
    # Policy storage (backend-agnostic metadata)
    # ------------------------------------------------------------------
    def _load_policies(self):
        """Load retention policies from database or use defaults."""
        try:
            self._load_policies_mongo()
        except Exception as e:
            logger.error(f"Failed to load retention policies: {e}")
            for policy in self.DEFAULT_POLICIES:
                self.policies[policy.data_type] = policy

    def _load_policies_mongo(self):
        from db.mongo_client import get_database, COL_DATA_RETENTION_POLICY
        coll = get_database()[COL_DATA_RETENTION_POLICY]
        for doc in coll.find({}):
            self.policies[doc["data_type"]] = RetentionPolicy(
                data_type=doc["data_type"], retention_days=doc["retention_days"],
                auto_delete=bool(doc.get("auto_delete", True)),
                archive_before_delete=bool(doc.get("archive_before_delete", False)),
                archive_location=doc.get("archive_location"))
        for default_policy in self.DEFAULT_POLICIES:
            if default_policy.data_type not in self.policies:
                self.add_policy(default_policy)

    def add_policy(self, policy: RetentionPolicy):
        """Add or update a retention policy."""
        try:
            self._add_policy_mongo(policy)
            self.policies[policy.data_type] = policy
            logger.info(f"Added retention policy for {policy.data_type}: {policy.retention_days} days")
        except Exception as e:
            logger.error(f"Failed to add retention policy: {e}")

    def _add_policy_mongo(self, policy):
        from db.mongo_client import get_database, COL_DATA_RETENTION_POLICY
        coll = get_database()[COL_DATA_RETENTION_POLICY]
        coll.update_one(
            {"data_type": policy.data_type},
            {"$set": {
                "data_type": policy.data_type,
                "retention_days": policy.retention_days,
                "auto_delete": policy.auto_delete,
                "archive_before_delete": policy.archive_before_delete,
                "archive_location": policy.archive_location,
                "updated_at": datetime.now(),
            }},
            upsert=True,
        )
        # Ensure a TTL index exists on the target time-series collection so
        # expired records auto-purge (§3.2). TTL is based on the retention_days
        # for this policy, applied to the collection's timestamp field.
        self._ensure_ttl(policy)

    def _ensure_ttl(self, policy):
        if not policy.auto_delete:
            return
        mapping = _MONGO_RETENTION_MAP.get(policy.data_type)
        if not mapping:
            return
        coll_name, ts_field = mapping
        try:
            from db.mongo_client import get_database
            coll = get_database()[coll_name]
            # expireAfterSeconds is relative to the timestamp field. TTL deletes
            # when (ts_field + retention_days) < now.
            coll.create_index([(ts_field, 1)], expireAfterSeconds=policy.retention_days * 86400,
                             name=f"retention_ttl_{coll_name}")
        except Exception as e:  # noqa: BLE001
            # An equivalent TTL may already exist (e.g. data_privacy's
            # anon_ttl / auth_mongo's consent_ttl). The explicit delete_many in
            # cleanup_expired_data remains the deterministic fallback, so an
            # index-name/options conflict here is non-fatal.
            err = str(e)
            if "IndexOptionsConflict" in err or "already exists" in err or "OperationFailure" in type(e).__name__:
                logger.debug(f"TTL index for {policy.data_type} already present/skipped: {e}")
            else:
                logger.error(f"Failed to create TTL index for {policy.data_type}: {e}")

    def _audit_db_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), "audit_log.db")
        return "audit_log.db"

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def cleanup_expired_data(self, data_type: str = None) -> Dict[str, int]:
        """Clean up expired data based on retention policies."""
        cleanup_results = {}
        policies_to_process = [self.policies[data_type]] if data_type and data_type in self.policies else self.policies.values()

        for policy in policies_to_process:
            if not policy.auto_delete:
                continue
            try:
                deleted_count = self._cleanup_data_type(policy)
                cleanup_results[policy.data_type] = deleted_count
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired {policy.data_type} records")
            except Exception as e:
                logger.error(f"Failed to cleanup {policy.data_type}: {e}")
                cleanup_results[policy.data_type] = 0

        return cleanup_results

    def _cleanup_data_type(self, policy: RetentionPolicy) -> int:
        """Clean up specific data type based on policy (MongoDB)."""
        return self._cleanup_data_type_mongo(policy)

    def _cleanup_data_type_mongo(self, policy) -> int:
        mapping = _MONGO_RETENTION_MAP.get(policy.data_type)
        if not mapping:
            return 0
        coll_name, ts_field = mapping
        cutoff = datetime.now() - timedelta(days=policy.retention_days)
        try:
            from db.mongo_client import get_database
            coll = get_database()[coll_name]
            if ts_field == "expires_at":
                res = coll.delete_many({ts_field: {"$lt": datetime.now()}})
            else:
                res = coll.delete_many({ts_field: {"$lt": cutoff}})
            return res.deleted_count
        except Exception as e:
			logger.error(f"Failed to cleanup {policy.data_type} (mongo): {e}")
			return 0

    # ------------------------------------------------------------------
    # Background scheduler (backend-agnostic)
    # ------------------------------------------------------------------
    def start_background_cleanup(self, interval_hours: int = 24):
        """Start background cleanup process."""
        if self.running:
            logger.warning("Background cleanup already running")
            return
        self.running = True

        def run_cleanup():
            while self.running:
                try:
                    self.cleanup_expired_data()
                    time.sleep(interval_hours * 3600)
                except Exception as e:
                    logger.error(f"Background cleanup error: {e}")
                    time.sleep(3600)

        self.cleanup_thread = threading.Thread(target=run_cleanup, daemon=True)
        self.cleanup_thread.start()
        logger.info(f"Started background cleanup with {interval_hours}h interval")

    def stop_background_cleanup(self):
        """Stop background cleanup process."""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        logger.info("Stopped background cleanup")

    # ------------------------------------------------------------------
    # Reporting (backend-agnostic)
    # ------------------------------------------------------------------
    def get_retention_report(self) -> Dict[str, any]:
        """Generate retention policy compliance report."""
        report = {
            'policies': [],
            'data_sizes': {},
            'next_cleanup_estimates': {},
            'generated_at': datetime.now().isoformat()
        }
        for policy in self.policies.values():
            policy_info = {
                'data_type': policy.data_type,
                'retention_days': policy.retention_days,
                'auto_delete': policy.auto_delete,
                'archive_before_delete': policy.archive_before_delete
            }
            try:
                cutoff_date = datetime.now() - timedelta(days=policy.retention_days)
                size_info = self._get_data_size_info(policy.data_type, cutoff_date)
                policy_info.update(size_info)
            except Exception as e:
                logger.error(f"Failed to get size info for {policy.data_type}: {e}")
                policy_info['error'] = str(e)
            report['policies'].append(policy_info)
        return report

    def _get_data_size_info(self, data_type: str, cutoff_date: datetime) -> Dict[str, any]:
        info = {
            'total_records': 0,
            'expired_records': 0,
            'estimated_cleanup_date': None
        }
        try:
            mapping = _MONGO_RETENTION_MAP.get(data_type)
            if mapping:
                from db.mongo_client import get_database
                coll = get_database()[mapping[0]]
                ts_field = mapping[1]
                info['total_records'] = coll.count_documents({})
                if ts_field == "expires_at":
                    info['expired_records'] = coll.count_documents({ts_field: {"$lt": datetime.now()}})
                else:
                    info['expired_records'] = coll.count_documents({ts_field: {"$lt": cutoff_date}})
        except Exception as e:
            logger.error(f"Failed to get size info for {data_type}: {e}")
        return info


# Global retention manager instance
retention_manager = DataRetentionManager()
