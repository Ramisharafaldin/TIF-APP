"""tif-ai cross-platform CLI (Phase 4, §5).

Entry point: ``tif_ai.cli:main`` (wired via pyproject.toml console script).

The CLI is pure Python (click + colorama), matching the app's Python
end-to-end stack (§5.1). It never provisions MongoDB — it only validates a
supplied MONGODB_URI and writes config to the OS-specific config directory
(§5.3). Backup/restore map to mongodump/mongorestore (§5.1, §5.5).
"""

__version__ = "1.0.0"
