"""
MongoDB-backed authentication store (Phase 2, §3.3 step 3).

Mirrors the public surface of ``auth_flask`` (users / setup_tokens) using
MongoDB collections instead of ``users.duckdb``. The bcrypt hashing logic
stays identical (bcrypt is DB-agnostic), so password hashes round-trip
unchanged. ``setup_tokens`` uses a Mongo TTL index for auto-expiry.

Selected at runtime via the ``DB_BACKEND`` flag; the legacy DuckDB
implementation in ``auth_flask`` remains the default until cutover.
"""

import os
import sys
import secrets
import logging
from datetime import datetime, timedelta

import bcrypt

logger = logging.getLogger(__name__)


def _auth_flask_helpers():
    """Lazily import auth_flask helpers to avoid a circular import at load."""
    from auth_flask import (
        SETUP_TOKEN_TTL_HOURS, _setup_token_log_path, hash_password, verify_password,
    )
    return SETUP_TOKEN_TTL_HOURS, _setup_token_log_path, hash_password, verify_password


# Local imports (avoid circular import at module load).
from db.mongo_client import (
    get_database, COL_USERS, COL_SETUP_TOKENS,
)


def _require_mongo():
    try:
        from pymongo import MongoClient  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "pymongo is required for the MongoDB auth backend. "
            "Install with: pip install pymongo"
        ) from exc


def _db():
    _require_mongo()
    return get_database()


def _users():
    return _db()[COL_USERS]


def _tokens():
    coll = _db()[COL_SETUP_TOKENS]
    # Auto-expiry via TTL index (req §3.2). expires_at is a Date field.
    try:
        coll.create_index([("expires_at", 1)], expireAfterSeconds=0,
                          name="setup_token_ttl")
    except Exception:
        pass
    return coll


def init_db():
    """Ensure collections/indexes exist and bootstrap a setup token if no admin."""
    try:
        SETUP_TOKEN_TTL_HOURS, _setup_token_log_path, _hp, _vp = _auth_flask_helpers()
        users = _users()
        users.create_index([("username", 1)], unique=True, name="username_uniq")
        tokens = _tokens()

        admin_count = users.count_documents({"is_admin": True})
        if admin_count == 0:
            existing = tokens.find_one({
                "is_used": False,
                "expires_at": {"$gt": datetime.now()},
            })
            if existing:
                token = existing["token_id"]
                logger.info(f"Using existing setup token: {token[:10]}...")
            else:
                token = secrets.token_urlsafe(32)
                expires_at = datetime.now() + timedelta(hours=SETUP_TOKEN_TTL_HOURS)
                tokens.insert_one({
                    "token_id": token,
                    "is_used": False,
                    "created_at": datetime.now(),
                    "expires_at": expires_at,
                    "used_at": None,
                    "used_by_username": None,
                })
                logger.info(f"Generated new setup token: {token[:10]}...")

            setup_message = (
                "INITIAL ADMIN SETUP REQUIRED — a setup token has been "
                f"generated and written to {_setup_token_log_path()}. "
                f"It expires in {SETUP_TOKEN_TTL_HOURS:g} hour(s). "
                "Use the /setup page with that token to create the admin account."
            )
            logger.warning(setup_message)

            try:
                token_log = _setup_token_log_path()
                fd = os.open(token_log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, 'a') as f:
                    f.write(f"\n{datetime.now().isoformat()} | Token: {token}\n")
                    f.write(f"Expires: {(datetime.now() + timedelta(hours=SETUP_TOKEN_TTL_HOURS)).isoformat()}\n")
                    f.write(f"Access: http://localhost:5000/setup?token={token}\n")
                try:
                    os.chmod(token_log, 0o600)
                except (NotImplementedError, OSError):
                    pass
            except Exception as e:
                logger.warning(f"Could not write setup token to log: {e}")
    except Exception as e:
        logger.error(f"Error during Mongo auth init_db: {e}", exc_info=True)


def login_user(username, password):
    """Authenticate a user. Returns (success, is_admin, role, message)."""
    try:
        _ttl, _log, hash_password, verify_password = _auth_flask_helpers()
        from modules.rbac import Role
        doc = _users().find_one({"username": username})
        if not doc:
            logger.warning(f"Login attempt for non-existent user: {username}")
            return False, False, None, "اسم المستخدم أو كلمة المرور غير صحيحة"

        is_active = doc.get("is_active", True)
        if not is_active:
            logger.warning(f"Login attempt for inactive user: {username}")
            return False, False, None, "هذا الحساب معطل"

        if not verify_password(doc["password_hash"], password):
            logger.warning(f"Failed login attempt for user: {username}")
            return False, False, None, "اسم المستخدم أو كلمة المرور غير صحيحة"

        is_admin = bool(doc.get("is_admin", False))
        role = doc.get("role") or (Role.ADMIN if is_admin else Role.VIEWER)
        try:
            _users().update_one(
                {"username": username},
                {"$set": {"last_login": datetime.now()}},
            )
        except Exception as e:
            logger.warning(f"Could not update last login for {username}: {e}")

        logger.info(f"Successful login: {username} (role: {role})")
        return True, is_admin, role, f"مرحبا {username}"
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return False, False, None, f"خطأ في المصادقة: {str(e)}"


def get_all_users():
    try:
        docs = _users().find({"is_active": True}, {"username": 1, "is_admin": 1})
        return [(d["username"], d.get("is_admin", False)) for d in docs]
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        return []


def add_user(username, password, is_admin=False, role=None):
    try:
        _ttl, _log, hash_password, verify_password = _auth_flask_helpers()
        from modules.rbac import Role
        if role is None:
            role = Role.ADMIN if is_admin else Role.VIEWER
        hashed_pw = hash_password(password)
        _users().update_one(
            {"username": username},
            {"$set": {
                "username": username,
                "password_hash": hashed_pw,
                "is_admin": bool(is_admin),
                "password_changed": True,
                "is_active": True,
                "role": role,
                "created_at": datetime.now(),
            }},
            upsert=True,
        )
        logger.info(f"New user created: {username} (role={role})")
        return True, f"تمت إضافة المستخدم '{username}' بنجاح"
    except Exception as e:
        logger.error(f"Error adding user {username}: {e}")
        return False, f"خطأ: اسم المستخدم '{username}' موجود بالفعل أو حدث خطأ في النظام: {str(e)}"


def delete_user(username, current_user):
    if username == current_user:
        return False, "لا يمكنك حذف حسابك الحالي"
    try:
        res = _users().delete_one({"username": username})
        if res.deleted_count > 0:
            logger.info(f"User deleted: {username}")
            return True, f"تم حذف المستخدم '{username}' بنجاح"
        return False, f"لم يتم العثور على المستخدم '{username}'"
    except Exception as e:
        logger.error(f"Error deleting user {username}: {e}")
        return False, f"خطأ في حذف المستخدم: {str(e)}"


def change_password(username, new_password):
    try:
        _ttl, _log, hash_password, verify_password = _auth_flask_helpers()
        hashed_pw = hash_password(new_password)
        res = _users().update_one(
            {"username": username},
            {"$set": {"password_hash": hashed_pw}},
        )
        if res.matched_count > 0:
            logger.info(f"Password changed for user: {username}")
            return True, f"تم تغيير كلمة مرور المستخدم '{username}' بنجاح"
        return False, f"لم يتم العثور على المستخدم '{username}'"
    except Exception as e:
        logger.error(f"Error changing password for {username}: {e}")
        return False, f"حدث خطأ أثناء تغيير كلمة المرور: {str(e)}"


def get_user(username):
    """Return (username, is_admin, role) or None."""
    try:
        from modules.rbac import Role
        doc = _users().find_one(
            {"username": username, "is_active": True},
            {"username": 1, "is_admin": 1, "role": 1},
        )
        if not doc:
            return None
        is_admin = bool(doc.get("is_admin", False))
        role = doc.get("role") or (Role.ADMIN if is_admin else Role.VIEWER)
        return (doc["username"], is_admin, role)
    except Exception as e:
        logger.error(f"Error getting user {username}: {e}")
        return None


def validate_setup_token(token):
    try:
        doc = _tokens().find_one({"token_id": token})
        if not doc:
            return False, False, "رمز الإعداد غير صالح"

        if doc.get("is_used"):
            logger.warning("Attempt to reuse setup token")
            return False, False, "تم استخدام هذا الرمز بالفعل"

        expires_at = doc.get("expires_at")
        if expires_at is None:
            expires_dt = datetime.now() + timedelta(days=1)
        elif isinstance(expires_at, datetime):
            expires_dt = expires_at
        else:
            try:
                expires_dt = datetime.fromisoformat(str(expires_at))
            except (ValueError, TypeError):
                expires_dt = datetime.now() + timedelta(days=1)

        if expires_dt < datetime.now():
            logger.warning("Attempt to use expired setup token")
            return False, True, "انتهت صلاحية رمز الإعداد"

        return True, False, "رمز الإعداد صالح"
    except Exception as e:
        logger.error(f"Error validating setup token: {e}")
        return False, False, f"خطأ في التحقق: {str(e)}"


def use_setup_token(token, username):
    try:
        res = _tokens().update_one(
            {"token_id": token},
            {"$set": {
                "is_used": True,
                "used_at": datetime.now(),
                "used_by_username": username,
            }},
        )
        logger.info(f"Setup token marked as used by {username}")
        return res.matched_count > 0
    except Exception as e:
        logger.error(f"Error using setup token: {e}")
        return False
