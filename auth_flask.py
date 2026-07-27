"""
Flask-compatible authentication module (MongoDB-only backend).

Provides user authentication, password management, and user CRUD operations
using MongoDB (auth_mongo). DuckDB backend has been removed.
"""

import bcrypt
import os
import sys
import logging

logger = logging.getLogger(__name__)

# Setup token lifetime, configurable via SETUP_TOKEN_TTL_HOURS env var.
SETUP_TOKEN_TTL_HOURS = float(os.environ.get('SETUP_TOKEN_TTL_HOURS', '1'))

def _setup_token_log_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.getcwd()
    return os.path.join(base, 'setup_token.log')

def hash_password(password: str) -> str:
    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Error hashing password: {e}")
        raise

def verify_password(stored_hash: str, provided_password: str) -> bool:
    try:
        return bcrypt.checkpw(provided_password.encode('utf-8'), stored_hash.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

# All database-backed operations delegated to auth_mongo (MongoDB)
from auth_mongo import (
    init_db,
    login_user,
    get_all_users,
    add_user,
    delete_user,
    change_password,
    get_user,
    validate_setup_token,
    use_setup_token,
)

# Ensure MongoDB collections and indexes exist
init_db()

