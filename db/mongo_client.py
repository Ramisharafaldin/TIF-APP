"""
MongoDB connection layer for TIF (Phase 2 migration target).

Provides a single, process-wide MongoClient factory built on PyMongo's
built-in connection pool. The application only *connects* to an
already-running, externally-managed MongoDB instance (it does not install,
start, or bundle MongoDB) — see requirements §3 deployment note.

Connection string is read from MONGODB_URI (with MONGODB_DB_NAME selecting
the target database). All access goes through get_mongo_client() /
get_database() so there is exactly one client/pool per process.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Environment variable names
MONGO_URI_ENV = "MONGODB_URI"
MONGO_DB_ENV = "MONGODB_DB_NAME"

# Sensible defaults that assume a locally-running standalone service.
DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DB_NAME = "tif"

# Process-wide singleton client (PyMongo pooling handles concurrency).
_client = None
_client_uri = None


def get_mongo_uri() -> str:
    """Return the configured MongoDB connection string."""
    return os.environ.get(MONGO_URI_ENV, DEFAULT_MONGO_URI)


def get_mongo_db_name() -> str:
    """Return the configured target database name."""
    return os.environ.get(MONGO_DB_ENV, DEFAULT_DB_NAME)


def reset_client() -> None:
    """Drop the cached client (used by tests or config reloads)."""
    global _client, _client_uri
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None
    _client_uri = None


def get_mongo_client() -> "object":
    """
    Return a process-wide MongoClient, creating it on first use.

    Uses PyMongo's built-in connection pool (maxPoolSize default 100).
    Raises ConnectionError if the URI is unreachable at first use.
    """
    global _client, _client_uri
    uri = get_mongo_uri()
    if _client is not None and _client_uri == uri:
        return _client

    try:
        from pymongo import MongoClient
        from pymongo.errors import PyMongoError
    except ImportError as exc:  # pragma: no cover - environment issue
        raise ImportError(
            "pymongo is required for the MongoDB backend. "
            "Install with: pip install pymongo"
        ) from exc

    try:
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=int(os.environ.get("MONGODB_TIMEOUT_MS", "5000")),
            connectTimeoutMS=int(os.environ.get("MONGODB_CONNECT_TIMEOUT_MS", "10000")),
            socketTimeoutMS=int(os.environ.get("MONGODB_SOCKET_TIMEOUT_MS", "30000")),
            maxPoolSize=int(os.environ.get("MONGODB_MAX_POOL_SIZE", "100")),
            minPoolSize=int(os.environ.get("MONGODB_MIN_POOL_SIZE", "0")),
        )
        # Eagerly verify connectivity (PyMongo connects lazily otherwise).
        client.admin.command("ping")
    except Exception as exc:
        logger.error(f"Failed to connect to MongoDB at {uri}: {exc}")
        raise

    _client = client
    _client_uri = uri
    logger.info(f"MongoDB client initialized for {uri}")
    return _client


def get_database(db_name: Optional[str] = None) -> "object":
    """
    Return the active MongoDB database handle.

    Args:
        db_name: Optional override; defaults to MONGODB_DB_NAME env or 'tif'.
    """
    client = get_mongo_client()
    return client[db_name or get_mongo_db_name()]


def check_connectivity(uri: Optional[str] = None) -> bool:
    """
    Lightweight connectivity/auth check (used by tif-ai doctor, §5.5).

    Returns True if a ping succeeds against the configured (or supplied) URI.
    Never raises — returns False on any failure.
    """
    import os as _os
    target = uri or _os.environ.get(MONGO_URI_ENV, DEFAULT_MONGO_URI)
    try:
        from pymongo import MongoClient
        client = MongoClient(target, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        return True
    except Exception as exc:
        logger.debug(f"MongoDB connectivity check failed: {exc}")
        return False


# GridFS helpers ------------------------------------------------------------

def get_gridfs(db_name: Optional[str] = None) -> "object":
    """
    Return a GridFS handle bound to the active database. Used to store
    serialized DataFrame payloads (Parquet bytes) for processed_data.
    """
    from gridfs import GridFS
    return GridFS(get_database(db_name))


# Collection name constants (centralized to avoid typos across modules).
COL_USERS = "users"
COL_SETUP_TOKENS = "setup_tokens"
COL_UPLOADED_FILES = "uploaded_files"
COL_PROCESSED_DATA = "processed_data"
COL_USER_SESSIONS = "user_sessions"
COL_AI_QUERIES = "ai_queries"
COL_AI_INSIGHTS_CACHE = "ai_insights_cache"
COL_AI_PERFORMANCE_METRICS = "ai_performance_metrics"
COL_DATA_CLASSIFICATION = "data_classification"
COL_ANONYMIZATION_MAPPING = "anonymization_mapping"
COL_USER_CONSENT = "user_consent"
COL_DATA_PROCESSING_LOG = "data_processing_log"
COL_DATA_RETENTION_POLICY = "data_retention_policy"
COL_AI_AUDIT_LOG = "ai_audit_log"
COL_SCHEMA_VERSION = "schema_version"
