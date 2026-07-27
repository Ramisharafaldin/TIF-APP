"""
Database retry logic utility for export operations.

Phase 4 cleanup (§3.6): Rewritten to delegate to ``data_store`` module
functions instead of raw DuckDB connections. The ``ConnectionPool`` class
and DuckDB-specific retry logic are removed; the public function signatures
are preserved for backward compatibility with callers in ``session_validator``
and test modules.
"""

import logging
import time
from typing import Callable, Any, Optional, Tuple
from functools import wraps


class DatabaseRetryError(Exception):
    """Custom exception for database retry operations."""
    pass


def with_database_retry(max_retries: int = 3, base_delay: float = 0.1,
                        max_delay: float = 5.0, timeout: float = 300.0):
    """
    Decorator that retries a database operation with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        timeout: Maximum total time to spend retrying in seconds

    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            start_time = time.time()

            for attempt in range(max_retries + 1):
                try:
                    if time.time() - start_time > timeout:
                        raise DatabaseRetryError(
                            f"Database operation timeout exceeded: {timeout}s"
                        )
                    return func(*args, **kwargs)
                except DatabaseRetryError:
                    raise
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logging.getLogger(__name__).warning(
                            f"Retry {attempt + 1}/{max_retries} after error: {e}"
                        )
                        time.sleep(delay)

            raise DatabaseRetryError(
                f"Database operation failed after {max_retries} retries: "
                f"{str(last_exception)}"
            ) from last_exception
        return wrapper
    return decorator


@with_database_retry(max_retries=3, base_delay=0.1, max_delay=2.0)
def execute_with_retry(backend: str, operation: Callable[[], Any]) -> Any:
    """
    Execute an operation with retry logic.

    Args:
        backend: Unused — preserved for backward compatibility (was ``database_path``).
        operation: Zero-argument callable returning the result.

    Returns:
        Result from the operation.

    Raises:
        DatabaseRetryError: If operation fails after all retries.
    """
    return operation()


def get_user_session_with_retry(
    username: str, module: str, backend: str
) -> Optional[dict]:
    """
    Get user session with database retry logic.

    Args:
        username: Username.
        module: Module name.
        backend: Unused — preserved for backward compatibility.

    Returns:
        User session data or None.
    """
    import data_store
    return execute_with_retry(backend, lambda: data_store.get_user_session(username, module))


def get_dataframe_with_retry(data_id: int, backend: str):
    """
    Get DataFrame with database retry logic.

    Args:
        data_id: Data ID.
        backend: Unused — preserved for backward compatibility.

    Returns:
        DataFrame or None.
    """
    import data_store
    return execute_with_retry(backend, lambda: data_store.get_dataframe(data_id))


def validate_data_ownership_with_retry(
    username: str, data_ids: dict, backend: str
) -> Tuple[bool, str]:
    """
    Validate data ownership with database retry logic.

    Args:
        username: Username to validate.
        data_ids: Dictionary of data IDs to validate.
        backend: Unused — preserved for backward compatibility.

    Returns:
        Tuple of (is_valid, error_message).
    """
    import data_store
    return execute_with_retry(
        backend,
        lambda: data_store.validate_data_ownership(username, data_ids)
    )
