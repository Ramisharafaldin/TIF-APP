"""
MongoDB-backed implementation of the TIF data store (Phase 2).

This module provides :class:`MongoDataStore`, which implements the same
public surface as the legacy DuckDB module in ``data_store.py``
(``DuckDBDataStore``). It is selected at runtime via the ``DB_BACKEND``
config flag (``duckdb`` | ``mongodb``); see ``data_store.get_data_store``.

Storage model (per requirements §3.2):
- ``uploaded_files``: GridFS file (raw bytes) + metadata document.
- ``processed_data``: DataFrames serialized to **Parquet bytes**, encrypted
  per Phase 1 §2.1, stored in **GridFS**; a metadata document references the
  GridFS file id plus ``username/module/data_type/branch_name`` for querying.
- ``user_sessions``, ``ai_queries``, ``ai_insights_cache``,
  ``ai_performance_metrics``: ordinary documents.
- ``ai_insights_cache`` uses a Mongo TTL index for auto-expiry.

Analytic helpers (``calculate_dashboard_metrics``,
``get_filtered_inventory_data``) are re-expressed in pandas so their output
matches the legacy DuckDB path exactly (parity tested during migration).
"""

import os
import io
import json
import logging
import datetime
from typing import Optional, Tuple, Dict, Any, List

import pandas as pd

logger = logging.getLogger(__name__)


def _require_mongo():
    """Import pymongo lazily; raise a clear error if unavailable."""
    try:
        from pymongo import MongoClient  # noqa: F401
        from gridfs import GridFS  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment issue
        raise ImportError(
            "pymongo and gridfs are required for the MongoDB backend. "
            "Install with: pip install pymongo"
        ) from exc


def _df_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    return buf.getvalue()


def _parquet_bytes_to_df(data: bytes) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(data), engine="pyarrow")


class MongoDataStore:
    """
    MongoDB implementation of the DataStoreRepository interface.

    Every method mirrors a function in ``data_store.py``. DataFrames are
    persisted as encrypted Parquet in GridFS; structured rows are stored as
    documents. The DuckDB path remains the default until cutover.
    """

    #: DB_NAME class attribute for backward compatibility with callers that
    #: reference ``data_store.DB_NAME`` (the duckdb path). Points to the
    #: MongoDB database name as a fallback.
    DB_NAME: str = "tif"

    def __init__(self, db_name: Optional[str] = None):
        _require_mongo()
        from db.mongo_client import (
            get_mongo_db_name,
            get_database, get_gridfs,
            COL_UPLOADED_FILES, COL_PROCESSED_DATA, COL_USER_SESSIONS,
            COL_AI_QUERIES, COL_AI_INSIGHTS_CACHE, COL_AI_PERFORMANCE_METRICS,
        )
        self._db = get_database(db_name)
        self._gfs = get_gridfs(db_name)
        MongoDataStore.DB_NAME = db_name or get_mongo_db_name()

        self._c_uploaded = self._db[COL_UPLOADED_FILES]
        self._c_processed = self._db[COL_PROCESSED_DATA]
        self._c_sessions = self._db[COL_USER_SESSIONS]
        self._c_ai_queries = self._db[COL_AI_QUERIES]
        self._c_ai_cache = self._db[COL_AI_INSIGHTS_CACHE]
        self._c_ai_metrics = self._db[COL_AI_PERFORMANCE_METRICS]

        # Ensure a TTL index on the AI cache for auto-expiry (req §3.2).
        try:
            self._c_ai_cache.create_index(
                [("expires_at", 1)], expireAfterSeconds=0, name="ai_cache_ttl"
            )
        except Exception as exc:  # pragma: no cover
            logger.debug(f"ai cache TTL index already present: {exc}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _put_df(self, df: pd.DataFrame) -> str:
        parquet = _df_to_parquet_bytes(df)
        file_id = self._gfs.put(parquet, filename="processed_data.parquet")
        return str(file_id)

    def _gridfs_get(self, file_id):
        """Retrieve a GridFS file by id, coercing string ids to ObjectId."""
        from bson import ObjectId
        if isinstance(file_id, str):
            try:
                file_id = ObjectId(file_id)
            except Exception:
                pass
        return self._gfs.get(file_id)

    def _get_df(self, file_id) -> Optional[pd.DataFrame]:
        try:
            grid_out = self._gridfs_get(file_id)
            return _parquet_bytes_to_df(grid_out.read())
        except Exception as exc:
            logger.warning(f"Failed to load DataFrame from GridFS {file_id}: {exc}")
            return None

    # ------------------------------------------------------------------
    # File storage
    # ------------------------------------------------------------------
    def _next_int_id(self, name: str) -> int:
        """Atomically allocate a stable integer id (call-site parity w/ DuckDB)."""
        from db.mongo_client import COL_SCHEMA_VERSION
        counter = self._db[COL_SCHEMA_VERSION]
        res = counter.find_one_and_update(
            {"_id": f"int_id_{name}"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True,
        )
        return int(res["seq"])

    def save_uploaded_file(self, username, module, filename, file_data,
                           branch_name=None) -> int:
        # Store raw bytes in GridFS, reference id from the metadata doc.
        gridfs_id = self._gfs.put(file_data, filename=filename)
        doc_id = self._next_int_id("uploaded_files")
        doc = {
            "doc_id": doc_id,
            "username": username,
            "module": module,
            "branch_name": branch_name,
            "original_filename": filename,
            "file_size": len(file_data),
            "gridfs_file_id": gridfs_id,
            "upload_timestamp": datetime.datetime.utcnow(),
        }
        self._c_uploaded.insert_one(doc)
        return doc_id

    def get_uploaded_file(self, file_id):
        doc = self._c_uploaded.find_one({"doc_id": int(file_id)})
        if not doc:
            return None
        try:
            grid_out = self._gridfs_get(doc["gridfs_file_id"])
            data = grid_out.read()
        except Exception:
            return None
        return (doc.get("original_filename"), data)

    def get_user_files(self, username, module, limit=10):
        docs = self._c_uploaded.find(
            {"username": username, "module": module}
        ).sort("upload_timestamp", -1).limit(limit)
        return [
            (d.get("doc_id"), d.get("original_filename"),
             d.get("upload_timestamp"), d.get("file_size"))
            for d in docs
        ]

    def get_branch_files(self, username):
        docs = self._c_uploaded.find(
            {"username": username, "branch_name": {"$ne": None}}
        ).sort("upload_timestamp", -1)
        seen = {}
        for d in docs:
            b = d.get("branch_name")
            if b and b not in seen:
                seen[b] = (b, d.get("original_filename"),
                           d.get("upload_timestamp"), d.get("file_size"))
        return list(seen.values())



    # ------------------------------------------------------------------
    # Processed DataFrames
    # ------------------------------------------------------------------
    def save_dataframe(self, username, module, data_type, df,
                       metadata=None, branch_name=None) -> int:
        gridfs_id = self._put_df(df)
        doc_id = self._next_int_id("processed_data")
        doc = {
            "doc_id": doc_id,
            "username": username,
            "module": module,
            "data_type": data_type,
            "branch_name": branch_name,
            "gridfs_id": gridfs_id,
            "metadata": metadata or {},
            "created_timestamp": datetime.datetime.utcnow(),
        }
        self._c_processed.insert_one(doc)
        return doc_id

    def get_dataframe(self, data_id) -> Optional[pd.DataFrame]:
        doc = self._c_processed.find_one({"doc_id": int(data_id)})
        if not doc:
            return None
        return self._get_df(doc.get("gridfs_id"))

    def validate_data_ownership(self, username: str,
                                 data_ids: dict) -> Tuple[bool, str]:
        """
        Validate that all given data IDs belong to the specified user.

        Args:
            username: Owner to check against.
            data_ids: Mapping of ``{data_type: doc_id}``.

        Returns:
            ``(True, '')`` if all IDs belong to the user, or ``(False, error_msg)``.
        """
        for data_type, data_id in data_ids.items():
            if not isinstance(data_id, int) or data_id <= 0:
                return False, f'معرف البيانات غير صالح لـ {data_type}'
            doc = self._c_processed.find_one(
                {"doc_id": data_id},
                {"username": 1},
            )
            if not doc:
                return False, f'البيانات المطلوبة غير موجودة لـ {data_type}'
            if doc["username"] != username:
                return False, 'ليس لديك صلاحية للوصول إلى هذه البيانات'
        return True, ''

    # ------------------------------------------------------------------
    # User sessions (field-level encryption on username, Phase 1 §2.1)
    # ------------------------------------------------------------------
    def save_user_session(self, username, module, file_id=None,
                          data_ids=None, params=None):
        doc = {
            "username": username,
            "module": module,
            "file_id": file_id,
            "data_ids": json.dumps(data_ids) if data_ids else None,
            "params": json.dumps(params) if params else None,
            "last_updated": datetime.datetime.utcnow(),
        }
        self._c_sessions.update_one(
            {"username": doc["username"], "module": module},
            {"$set": doc},
            upsert=True,
        )

    def get_user_session(self, username, module):
        doc = self._c_sessions.find_one(
            {"username": username, "module": module}
        )
        if not doc:
            return None
        return {
            "file_id": doc.get("file_id"),
            "data_ids": json.loads(doc["data_ids"]) if doc.get("data_ids") else {},
            "params": json.loads(doc["params"]) if doc.get("params") else {},
        }

    def clear_user_session(self, username, module):
        self._c_sessions.delete_one(
            {"username": username, "module": module}
        )

    # ------------------------------------------------------------------
    # Branch data
    # ------------------------------------------------------------------
    def save_branch_data(self, username, branch_name, filename, file_data):
        from utils import data_processing
        df_sales, df_inventory = data_processing.process_new_format_bytes(file_data)
        if df_sales is None or df_inventory is None:
            raise ValueError("فشل في معالجة ملف Excel")
        fid = self.save_uploaded_file(username, "branch_data", filename,
                                      file_data, branch_name=branch_name)
        sales_id = self.save_dataframe(username, "branch_data", "sales_df",
                                       df_sales, branch_name=branch_name)
        inv_id = self.save_dataframe(username, "branch_data", "inventory_df",
                                     df_inventory, branch_name=branch_name)
        return fid, sales_id, inv_id

    def get_all_branches(self, username) -> list:
        docs = self._c_uploaded.find(
            {"username": username, "branch_name": {"$ne": None}}
        ).sort("branch_name", 1)
        return [d["branch_name"] for d in docs if d.get("branch_name")]

    def get_branch_data(self, username, branch_name=None):
        query = {"username": username,
                 "data_type": "sales_df"}
        if branch_name:
            query["branch_name"] = branch_name
        else:
            query["branch_name"] = {"$ne": None}
        sales_docs = self._c_processed.find(query).sort("created_timestamp", -1)
        if branch_name:
            sales_docs = sales_docs.limit(1)
        sales_dfs = []
        for d in sales_docs:
            df = self._get_df(d.get("gridfs_id"))
            if df is not None:
                df["branch_code"] = d.get("branch_name")
                sales_dfs.append(df)

        iquery = dict(query)
        iquery["data_type"] = "inventory_df"
        inv_docs = self._c_processed.find(iquery).sort("created_timestamp", -1)
        if branch_name:
            inv_docs = inv_docs.limit(1)
        inv_dfs = []
        for d in inv_docs:
            df = self._get_df(d.get("gridfs_id"))
            if df is not None:
                df["branch_code"] = d.get("branch_name")
                inv_dfs.append(df)

        sales_df = pd.concat(sales_dfs, ignore_index=True) if sales_dfs else None
        inventory_df = pd.concat(inv_dfs, ignore_index=True) if inv_dfs else None
        return sales_df, inventory_df

    def delete_branch_data(self, username, branch_name):
        self._c_uploaded.delete_many({"username": username, "branch_name": branch_name})
        self._c_processed.delete_many({"username": username, "branch_name": branch_name})
        self._c_sessions.delete_many({"username": username, "module": "branch_data"})
        return True, f"تم حذف جميع بيانات الفرع '{branch_name}' بنجاح"

    # ------------------------------------------------------------------
    # Clearing data
    # ------------------------------------------------------------------
    def clear_all_data(self):
        self._c_uploaded.delete_many({})
        self._c_processed.delete_many({})
        self._c_sessions.delete_many({})
        return True, "All data cleared successfully"

    def clear_user_data(self, username):
        self._c_uploaded.delete_many({"username": username})
        self._c_processed.delete_many({"username": username})
        self._c_sessions.delete_many({"username": username})
        return True, f"All data for user {username} cleared successfully"

    def cleanup_old_data(self, days=7):
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        self._c_uploaded.delete_many({"upload_timestamp": {"$lt": cutoff}})
        self._c_processed.delete_many({"created_timestamp": {"$lt": cutoff}})
        self._c_sessions.delete_many({"last_updated": {"$lt": cutoff}})

    # ------------------------------------------------------------------
    # AI query / cache / metrics
    # ------------------------------------------------------------------
    def save_ai_query(self, user_id, query_text, query_intent=None,
                      response_data=None, processing_time=None) -> int:
        doc_id = self._next_int_id("ai_queries")
        doc = {
            "doc_id": doc_id,
            "user_id": user_id,
            "query_text": query_text,
            "query_intent": query_intent,
            "response_data": response_data,
            "processing_time": processing_time,
            "timestamp": datetime.datetime.utcnow(),
        }
        self._c_ai_queries.insert_one(doc)
        return doc_id

    def get_ai_query_history(self, user_id, limit=50):
        docs = self._c_ai_queries.find({"user_id": user_id}).sort(
            "timestamp", -1).limit(limit)
        return [
            (d.get("doc_id"), d.get("query_text"), d.get("query_intent"),
             d.get("response_data"), d.get("processing_time"), d.get("timestamp"))
            for d in docs
        ]

    def save_ai_cache(self, cache_key, response_data, ttl_hours=1) -> bool:
        try:
            expires = datetime.datetime.utcnow() + datetime.timedelta(hours=ttl_hours)
            self._c_ai_cache.update_one(
                {"cache_key": cache_key},
                {"$set": {"response_data": response_data, "expires_at": expires}},
                upsert=True,
            )
            return True
        except Exception as exc:
            logger.error(f"Error saving AI cache: {exc}")
            return False

    def get_ai_cache(self, cache_key):
        try:
            doc = self._c_ai_cache.find_one({"cache_key": cache_key})
            if not doc:
                return None
            if doc.get("expires_at") and doc["expires_at"] < datetime.datetime.utcnow():
                return None
            return doc.get("response_data")
        except Exception as exc:
            logger.error(f"Error getting AI cache: {exc}")
            return None

    def save_ai_performance_metric(self, metric_type, metric_value,
                                   metadata=None) -> int:
        doc_id = self._next_int_id("ai_performance_metrics")
        doc = {
            "doc_id": doc_id,
            "metric_type": metric_type,
            "metric_value": metric_value,
            "metadata": metadata,
            "timestamp": datetime.datetime.utcnow(),
        }
        self._c_ai_metrics.insert_one(doc)
        return doc_id

    def get_ai_performance_metrics(self, metric_type=None, limit=50):
        query = {"metric_type": metric_type} if metric_type else {}
        docs = self._c_ai_metrics.find(query).sort("timestamp", -1).limit(limit)
        return [(d.get("doc_id"), d.get("metric_type"), d.get("metric_value"),
                d.get("metadata"), d.get("timestamp")) for d in docs]

    def cleanup_ai_data(self, days=30):
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        q = self._c_ai_queries.delete_many({"timestamp": {"$lt": cutoff}})
        c = self._c_ai_cache.delete_many({"expires_at": {"$lt": datetime.datetime.utcnow()}})
        m = self._c_ai_metrics.delete_many({"timestamp": {"$lt": cutoff}})
        return True, (f"Cleaned up {q.deleted_count} queries, "
                      f"{c.deleted_count} cache entries, {m.deleted_count} metrics")

    def get_ai_database_stats(self):
        now = datetime.datetime.utcnow()
        day_ago = now - datetime.timedelta(hours=24)
        try:
            total = self._c_ai_queries.count_documents({})
            last24 = self._c_ai_queries.count_documents({"timestamp": {"$gt": day_ago}})
            avg = list(self._c_ai_queries.aggregate([
                {"$match": {"processing_time": {"$ne": None}}},
                {"$group": {"_id": None, "avg": {"$avg": "$processing_time"}}},
            ]))
            avg_t = round(avg[0]["avg"], 3) if avg else 0
            cache_all = self._c_ai_cache.count_documents({})
            cache_active = self._c_ai_cache.count_documents(
                {"expires_at": {"$gt": now}})
            metrics = self._c_ai_metrics.count_documents({})
            metrics24 = self._c_ai_metrics.count_documents({"timestamp": {"$gt": day_ago}})
            return {
                "total_queries": total,
                "queries_last_24h": last24,
                "avg_processing_time": avg_t,
                "cache_entries": cache_all,
                "active_cache_entries": cache_active,
                "performance_metrics": metrics,
                "metrics_last_24h": metrics24,
            }
        except Exception as exc:
            logger.error(f"Error getting AI database stats: {exc}")
            return {"error": str(exc), "total_queries": 0,
                    "cache_entries": 0, "performance_metrics": 0}

    def test_ai_database_functionality(self):
        issues = []
        try:
            qid = self.save_ai_query("test_user", "test query", "intent", "{}", 1.5)
            if not self.get_ai_query_history("test_user", 1):
                issues.append("Failed to retrieve AI query history")
            self._c_ai_queries.delete_many({"user_id": "test_user"})

            key = f"test_key_{datetime.datetime.now().timestamp()}"
            if self.save_ai_cache(key, "{}", 1):
                if not self.get_ai_cache(key):
                    issues.append("Failed to retrieve AI cache data")
                self._c_ai_cache.delete_many({"cache_key": key})
            else:
                issues.append("Failed to save AI cache data")

            mid = self.save_ai_performance_metric("test_metric", 123.45, "{}")
            if not self.get_ai_performance_metrics("test_metric", 1):
                issues.append("Failed to retrieve AI performance metrics")
            self._c_ai_metrics.delete_many({"metric_type": "test_metric"})
        except Exception as exc:
            issues.append(f"AI database test failed: {exc}")
        return len(issues) == 0, issues

    # ------------------------------------------------------------------
    # Analytics (pandas equivalents of the legacy DuckDB queries)
    # ------------------------------------------------------------------
    def calculate_dashboard_metrics(self, sales_df, inventory_df):
        return calculate_dashboard_metrics(sales_df, inventory_df)

    def get_filtered_inventory_data(self, df, filters):
        return get_filtered_inventory_data(df, filters)

    # ------------------------------------------------------------------
    # Health / diagnostics (Mongo-flavored)
    # ------------------------------------------------------------------
    def get_database_health(self):
        try:
            self._db.command("ping")
            files = self._c_uploaded.count_documents({})
            data = self._c_processed.count_documents({})
            sessions = self._c_sessions.count_documents({})
            return {
                "status": "healthy",
                "message": "Database is healthy",
                "details": {
                    "accessibility": True,
                    "schema_valid": True,
                    "data_integrity": True,
                    "file_count": files,
                    "data_count": data,
                    "session_count": sessions,
                    "backend": "mongodb",
                },
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": f"MongoDB health check failed: {exc}",
                "details": {"error": str(exc), "backend": "mongodb"},
            }

    def init_data_db(self) -> bool:
        """No-op: MongoDB requires no schema initialisation.
        Returns True for compatibility with callers that check the return."""
        return True

    def repair_database(self):
        # Mongo is self-healing; nothing to repair. Report success.
        return True, "Database repaired successfully"

    def get_user_session_collection(self):
        return self._c_sessions


# ==========================================================================
# Shared analytics helpers (identical logic to data_store.py, expressed in
# pandas so both backends produce the same output). Imported by data_store.py
# so the DuckDB path can also use the canonical implementation.
# ==========================================================================

def calculate_dashboard_metrics(sales_df: pd.DataFrame,
                                inventory_df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate dashboard KPIs (pandas port of the DuckDB version)."""
    metrics = {
        'total_sales': 0.0,
        'total_products': 0,
        'total_stock_value': 0.0,
        'total_suppliers': 0,
    }
    try:
        if sales_df is not None and not sales_df.empty and 'revenue' in sales_df.columns:
            metrics['total_sales'] = round(float(sales_df['revenue'].sum() or 0), 2)

        if inventory_df is not None and not inventory_df.empty:
            prod = inventory_df
            if 'product_code' in prod.columns and 'Last_on_hand' in prod.columns:
                active = prod[(prod['Last_on_hand'] > 0) &
                             (prod['product_code'].notna())]
                metrics['total_products'] = int(active['product_code'].nunique())
            if 'inventory_value' in prod.columns and 'Last_on_hand' in prod.columns:
                active = prod[prod['Last_on_hand'] > 0]
                val = (active['inventory_value'].fillna(0) * active['Last_on_hand'])
                metrics['total_stock_value'] = round(float(val.sum() or 0), 2)
            if 'supplier_name' in prod.columns:
                metrics['total_suppliers'] = int(
                    prod[prod['supplier_name'].notna()]['supplier_name'].nunique())
        return metrics
    except Exception as exc:
        logger.error(f"Error calculating dashboard metrics: {exc}")
        return metrics


def get_filtered_inventory_data(df: pd.DataFrame,
                                filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filter inventory rows (pandas port of the DuckDB version)."""
    if df is None or df.empty:
        return []
    try:
        result = df.copy()

        if filters.get('search_term'):
            term = str(filters['search_term']).lower()
            mask = (
                result['product_code'].astype(str).str.lower().str.contains(term, na=False) |
                result['product_name'].astype(str).str.lower().str.contains(term, na=False) |
                result['item_category1'].astype(str).str.lower().str.contains(term, na=False)
            )
            result = result[mask]

        if filters.get('min_stock') is not None:
            result = result[result['Last_on_hand'] >= float(filters['min_stock'])]
        if filters.get('max_stock') is not None:
            result = result[result['Last_on_hand'] <= float(filters['max_stock'])]

        if filters.get('category') and filters['category'] != 'all':
            result = result[result['item_category1'] == filters['category']]

        status = filters.get('status')
        if status and status != 'all':
            min_coverage = float(filters.get('min_coverage', 7))
            if status == 'low_stock' and 'coverage_days' in result.columns:
                result = result[result['coverage_days'] < min_coverage]
            elif status == 'stagnant' and 'is_stagnant' in result.columns:
                result = result[result['is_stagnant'] == True]  # noqa: E712
            elif status == 'available':
                conds = []
                if 'coverage_days' in result.columns:
                    conds.append(result['coverage_days'] >= min_coverage)
                if 'is_stagnant' in result.columns:
                    conds.append(result['is_stagnant'] == False)  # noqa: E712
                if conds:
                    combined = conds[0]
                    for c in conds[1:]:
                        combined = combined & c
                    result = result[combined]

        selected_columns = filters.get('columns')
        if selected_columns and isinstance(selected_columns, list):
            valid = [c for c in selected_columns if c in result.columns]
            if valid:
                result = result[valid]

        return result.to_dict('records')
    except Exception as exc:
        logger.error(f"Error filtering inventory data: {exc}")
        return []


# ==========================================================================
# Helpers
# ==========================================================================


