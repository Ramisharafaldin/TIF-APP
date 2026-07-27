"""
RBAC (Role-Based Access Control) Module
Implements 5-tier role system with permission management
"""

import logging
from functools import wraps
from flask import session, redirect, url_for, flash, abort
from typing import List, Set, Optional, Callable

logger = logging.getLogger(__name__)

# ============================================================================
# ROLE DEFINITIONS
# ============================================================================

class Role:
    """Role constants and hierarchy"""
    VIEWER = "viewer"
    ANALYST = "analyst"
    EDITOR = "editor"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"
    
    # Role hierarchy (lower number = higher privilege)
    HIERARCHY = {
        SUPERADMIN: 5,
        ADMIN: 4,
        EDITOR: 3,
        ANALYST: 2,
        VIEWER: 1
    }
    
    # Role display names (bilingual)
    DISPLAY_NAMES = {
        VIEWER: {"en": "Viewer", "ar": "مشاهد"},
        ANALYST: {"en": "Analyst", "ar": "محلل"},
        EDITOR: {"en": "Editor", "ar": "محرر"},
        ADMIN: {"en": "Admin", "ar": "مسؤول"},
        SUPERADMIN: {"en": "SuperAdmin", "ar": "مسؤول رئيسي"}
    }
    
    # Role descriptions
    DESCRIPTIONS = {
        VIEWER: "Can view data and reports (read-only)",
        ANALYST: "Can view data, use AI insights, and create forecasts",
        EDITOR: "Can upload files, modify data, and manage inventory",
        ADMIN: "Can manage users and system settings",
        SUPERADMIN: "Full system access with all privileges"
    }
    
    # Role badges (emoji)
    BADGES = {
        VIEWER: "👁️",
        ANALYST: "📊",
        EDITOR: "✏️",
        ADMIN: "👨‍💼",
        SUPERADMIN: "👑"
    }
    
    # Role colors (for UI)
    COLORS = {
        VIEWER: "secondary",  # Gray
        ANALYST: "info",      # Blue
        EDITOR: "success",    # Green
        ADMIN: "warning",     # Orange
        SUPERADMIN: "danger"  # Red
    }
    
    @classmethod
    def all_roles(cls) -> List[str]:
        """Get list of all roles"""
        return [cls.VIEWER, cls.ANALYST, cls.EDITOR, cls.ADMIN, cls.SUPERADMIN]
    
    @classmethod
    def get_level(cls, role: str) -> int:
        """Get role level (higher = more privileges)"""
        return cls.HIERARCHY.get(role, 0)
    
    @classmethod
    def is_valid_role(cls, role: str) -> bool:
        """Check if role is valid"""
        return role in cls.HIERARCHY
    
    @classmethod
    def has_higher_privilege(cls, role1: str, role2: str) -> bool:
        """Check if role1 has higher privilege than role2"""
        return cls.get_level(role1) > cls.get_level(role2)
    
    @classmethod
    def get_display_name(cls, role: str, lang: str = "en") -> str:
        """Get role display name"""
        return cls.DISPLAY_NAMES.get(role, {}).get(lang, role)
    
    @classmethod
    def get_badge(cls, role: str) -> str:
        """Get role badge emoji"""
        return cls.BADGES.get(role, "")
    
    @classmethod
    def get_color(cls, role: str) -> str:
        """Get role color for UI"""
        return cls.COLORS.get(role, "secondary")


# ============================================================================
# PERMISSION DEFINITIONS
# ============================================================================

class Permission:
    """Permission constants"""
    
    # Data permissions
    VIEW_DATA = "view_data"
    EXPORT_DATA = "export_data"
    EDIT_DATA = "edit_data"
    DELETE_DATA = "delete_data"
    UPLOAD_DATA = "upload_data"
    
    # Analytics permissions
    VIEW_ANALYTICS = "view_analytics"
    ADVANCED_ANALYTICS = "advanced_analytics"
    USE_AI = "use_ai"
    CREATE_FORECASTS = "create_forecasts"
    
    # User management permissions
    VIEW_USERS = "view_users"
    CREATE_USERS = "create_users"
    EDIT_USERS = "edit_users"
    DELETE_USERS = "delete_users"
    ASSIGN_ROLES = "assign_roles"
    
    # System permissions
    VIEW_SETTINGS = "view_settings"
    EDIT_SETTINGS = "edit_settings"
    VIEW_LOGS = "view_logs"
    MANAGE_DATABASE = "manage_database"
    
    # Permission descriptions
    DESCRIPTIONS = {
        VIEW_DATA: "View inventory data and dashboard",
        EXPORT_DATA: "Export reports and data",
        EDIT_DATA: "Modify inventory data",
        DELETE_DATA: "Delete inventory records",
        UPLOAD_DATA: "Upload inventory files",
        VIEW_ANALYTICS: "View basic analytics",
        ADVANCED_ANALYTICS: "Use advanced analytics features",
        USE_AI: "Access AI insights and recommendations",
        CREATE_FORECASTS: "Generate forecasts",
        VIEW_USERS: "View user list",
        CREATE_USERS: "Create new users",
        EDIT_USERS: "Modify user details",
        DELETE_USERS: "Delete users",
        ASSIGN_ROLES: "Change user roles",
        VIEW_SETTINGS: "View system settings",
        EDIT_SETTINGS: "Modify system settings",
        VIEW_LOGS: "View audit logs",
        MANAGE_DATABASE: "Perform database operations"
    }


# ============================================================================
# ROLE-PERMISSION MAPPING
# ============================================================================

ROLE_PERMISSIONS = {
    Role.VIEWER: {
        Permission.VIEW_DATA,
        Permission.EXPORT_DATA,
        Permission.VIEW_ANALYTICS,
    },
    
    Role.ANALYST: {
        # All Viewer permissions
        Permission.VIEW_DATA,
        Permission.EXPORT_DATA,
        Permission.VIEW_ANALYTICS,
        # Plus Analyst-specific
        Permission.ADVANCED_ANALYTICS,
        Permission.USE_AI,
        Permission.CREATE_FORECASTS,
    },
    
    Role.EDITOR: {
        # All Analyst permissions
        Permission.VIEW_DATA,
        Permission.EXPORT_DATA,
        Permission.VIEW_ANALYTICS,
        Permission.ADVANCED_ANALYTICS,
        Permission.USE_AI,
        Permission.CREATE_FORECASTS,
        # Plus Editor-specific
        Permission.EDIT_DATA,
        Permission.DELETE_DATA,
        Permission.UPLOAD_DATA,
    },
    
    Role.ADMIN: {
        # All Editor permissions
        Permission.VIEW_DATA,
        Permission.EXPORT_DATA,
        Permission.VIEW_ANALYTICS,
        Permission.ADVANCED_ANALYTICS,
        Permission.USE_AI,
        Permission.CREATE_FORECASTS,
        Permission.EDIT_DATA,
        Permission.DELETE_DATA,
        Permission.UPLOAD_DATA,
        # Plus Admin-specific
        Permission.VIEW_USERS,
        Permission.CREATE_USERS,
        Permission.EDIT_USERS,
        Permission.DELETE_USERS,
        Permission.ASSIGN_ROLES,
        Permission.VIEW_SETTINGS,
        Permission.EDIT_SETTINGS,
        Permission.VIEW_LOGS,
    },
    
    Role.SUPERADMIN: {
        # All permissions
        Permission.VIEW_DATA,
        Permission.EXPORT_DATA,
        Permission.VIEW_ANALYTICS,
        Permission.ADVANCED_ANALYTICS,
        Permission.USE_AI,
        Permission.CREATE_FORECASTS,
        Permission.EDIT_DATA,
        Permission.DELETE_DATA,
        Permission.UPLOAD_DATA,
        Permission.VIEW_USERS,
        Permission.CREATE_USERS,
        Permission.EDIT_USERS,
        Permission.DELETE_USERS,
        Permission.ASSIGN_ROLES,
        Permission.VIEW_SETTINGS,
        Permission.EDIT_SETTINGS,
        Permission.VIEW_LOGS,
        Permission.MANAGE_DATABASE,
    }
}


# ============================================================================
# PERMISSION CHECKING FUNCTIONS
# ============================================================================

def get_role_permissions(role: str) -> Set[str]:
    """
    Get all permissions for a role.
    
    Args:
        role: Role name
        
    Returns:
        Set of permission names
    """
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: str, permission: str) -> bool:
    """
    Check if a role has a specific permission.
    
    Args:
        role: Role name
        permission: Permission name
        
    Returns:
        True if role has permission, False otherwise
    """
    return permission in get_role_permissions(role)


def has_any_permission(role: str, permissions: List[str]) -> bool:
    """
    Check if a role has any of the specified permissions.
    
    Args:
        role: Role name
        permissions: List of permission names
        
    Returns:
        True if role has at least one permission, False otherwise
    """
    role_perms = get_role_permissions(role)
    return any(perm in role_perms for perm in permissions)


def has_all_permissions(role: str, permissions: List[str]) -> bool:
    """
    Check if a role has all of the specified permissions.
    
    Args:
        role: Role name
        permissions: List of permission names
        
    Returns:
        True if role has all permissions, False otherwise
    """
    role_perms = get_role_permissions(role)
    return all(perm in role_perms for perm in permissions)


def get_user_role() -> Optional[str]:
    """
    Get current user's role from session.
    
    Returns:
        Role name or None if not logged in
    """
    return session.get('role')


def get_user_permissions() -> Set[str]:
    """
    Get current user's permissions from session.
    
    Returns:
        Set of permission names
    """
    role = get_user_role()
    if not role:
        return set()
    return get_role_permissions(role)


def user_has_permission(permission: str) -> bool:
    """
    Check if current user has a specific permission.
    
    Args:
        permission: Permission name
        
    Returns:
        True if user has permission, False otherwise
    """
    role = get_user_role()
    if not role:
        return False
    return has_permission(role, permission)


def user_has_role(role: str) -> bool:
    """
    Check if current user has a specific role.
    
    Args:
        role: Role name
        
    Returns:
        True if user has role, False otherwise
    """
    user_role = get_user_role()
    return user_role == role


def user_has_min_role(min_role: str) -> bool:
    """
    Check if current user has at least the specified role level.
    
    Args:
        min_role: Minimum required role
        
    Returns:
        True if user has sufficient role level, False otherwise
    """
    user_role = get_user_role()
    if not user_role:
        return False
    return Role.get_level(user_role) >= Role.get_level(min_role)


# ============================================================================
# ACTION/RESOURCE -> PERMISSION MAPPING
# ============================================================================

# Maps (action, resource) tuples to the RBAC permission required to perform them.
# Used by validate_user_permissions so callers can express intent semantically
# (e.g. validate_user_permissions(user, 'insights', 'inventory_data')) instead
# of referencing raw permission constants.
ACTION_RESOURCE_PERMISSIONS = {
    ('insights', 'inventory_data'): Permission.USE_AI,
    ('insights', 'ai'): Permission.USE_AI,
    ('view', 'data'): Permission.VIEW_DATA,
    ('view', 'analytics'): Permission.VIEW_ANALYTICS,
    ('export', 'data'): Permission.EXPORT_DATA,
    ('edit', 'data'): Permission.EDIT_DATA,
    ('delete', 'data'): Permission.DELETE_DATA,
    ('upload', 'data'): Permission.UPLOAD_DATA,
    ('forecast', 'data'): Permission.CREATE_FORECASTS,
    ('manage', 'users'): Permission.VIEW_USERS,
    ('manage', 'settings'): Permission.VIEW_SETTINGS,
    ('view', 'logs'): Permission.VIEW_LOGS,
    # Privacy/audit management endpoints (flask_app.py)
    ('audit_report', 'system_data'): Permission.VIEW_LOGS,
    ('retention_policy', 'system_data'): Permission.EDIT_SETTINGS,
    ('data_cleanup', 'system_data'): Permission.DELETE_DATA,
    ('user_permissions', 'system_data'): Permission.VIEW_USERS,
}


def resolve_user_role(user_id: Optional[str]) -> Optional[str]:
    """
    Resolve the role for a given user, preferring the active session and
    falling back to the persisted user record when no session is present
    (e.g. when called from a service context without a request).

    Args:
        user_id: Username / user identifier (optional)

    Returns:
        Role name or None if it cannot be determined
    """
    # Prefer the live session role when available.
    session_role = get_user_role()
    if session_role:
        return session_role

    if not user_id:
        return None

    # Fall back to the persisted role in the user store.
    try:
        from auth_flask import get_user
        user = get_user(user_id)
        if user:
            role = user.get('role') if isinstance(user, dict) else getattr(user, 'role', None)
            if role:
                return role
    except Exception:
        logger.debug(f"Could not resolve role for user {user_id} from store", exc_info=True)

    return None


def validate_user_permissions(user_id: Optional[str], action: str, resource: str) -> bool:
    """
    Real permission check: maps an (action, resource) intent to the
    corresponding RBAC permission and verifies the user's role holds it.

    Args:
        user_id: Username / user identifier (optional; session used if present)
        action: Semantic action (e.g. 'insights', 'view', 'edit', 'export')
        resource: Semantic resource (e.g. 'inventory_data', 'data', 'users')

    Returns:
        True if the resolved role has the required permission, False otherwise
    """
    required_permission = ACTION_RESOURCE_PERMISSIONS.get((action, resource))
    if required_permission is None:
        logger.warning(f"Unknown (action, resource) pair: ({action!r}, {resource!r})")
        return False

    role = resolve_user_role(user_id)
    if not role or not Role.is_valid_role(role):
        logger.warning(f"Permission denied: no valid role resolved for user {user_id}")
        return False

    granted = has_permission(role, required_permission)
    if not granted:
        logger.warning(
            f"Permission denied: user {user_id} (role={role}) lacks "
            f"{required_permission} for ({action}, {resource})"
        )
    return granted


# ============================================================================
# DECORATORS
# ============================================================================

def require_permission(permission: str, redirect_url: str = 'dashboard'):
    """
    Decorator to require a specific permission for a route.
    
    Args:
        permission: Required permission name
        redirect_url: URL to redirect to if permission denied (default: dashboard)
        
    Usage:
        @app.route('/upload')
        @require_permission(Permission.UPLOAD_DATA)
        def upload():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('logged_in'):
                flash('يرجى تسجيل الدخول أولاً', 'warning')
                return redirect(url_for('login'))
            
            if not user_has_permission(permission):
                role = get_user_role()
                logger.warning(f"Permission denied: {session.get('username')} ({role}) tried to access {permission}")
                flash(f'ليس لديك صلاحية للوصول إلى هذه الصفحة (مطلوب: {permission})', 'danger')
                return redirect(url_for(redirect_url))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_role(role: str, redirect_url: str = 'dashboard'):
    """
    Decorator to require a specific role for a route.
    
    Args:
        role: Required role name
        redirect_url: URL to redirect to if role denied (default: dashboard)
        
    Usage:
        @app.route('/admin')
        @require_role(Role.ADMIN)
        def admin_panel():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('logged_in'):
                flash('يرجى تسجيل الدخول أولاً', 'warning')
                return redirect(url_for('login'))
            
            if not user_has_role(role):
                user_role = get_user_role()
                logger.warning(f"Role denied: {session.get('username')} ({user_role}) tried to access {role}-only route")
                flash(f'ليس لديك صلاحية للوصول إلى هذه الصفحة (مطلوب: {Role.get_display_name(role, "ar")})', 'danger')
                return redirect(url_for(redirect_url))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_min_role(min_role: str, redirect_url: str = 'dashboard'):
    """
    Decorator to require a minimum role level for a route.
    
    Args:
        min_role: Minimum required role
        redirect_url: URL to redirect to if role denied (default: dashboard)
        
    Usage:
        @app.route('/edit')
        @require_min_role(Role.EDITOR)
        def edit_data():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('logged_in'):
                flash('يرجى تسجيل الدخول أولاً', 'warning')
                return redirect(url_for('login'))
            
            if not user_has_min_role(min_role):
                user_role = get_user_role()
                logger.warning(f"Min role denied: {session.get('username')} ({user_role}) tried to access {min_role}+ route")
                flash(f'ليس لديك صلاحية للوصول إلى هذه الصفحة (مطلوب: {Role.get_display_name(min_role, "ar")} أو أعلى)', 'danger')
                return redirect(url_for(redirect_url))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def can_assign_role(assigner_role: str, target_role: str) -> bool:
    """
    Check if a user with assigner_role can assign target_role to another user.
    
    Rules:
    - SuperAdmin can assign any role
    - Admin can assign roles up to Editor (not Admin or SuperAdmin)
    - Others cannot assign roles
    
    Args:
        assigner_role: Role of user trying to assign
        target_role: Role being assigned
        
    Returns:
        True if assignment is allowed, False otherwise
    """
    if assigner_role == Role.SUPERADMIN:
        return True
    
    if assigner_role == Role.ADMIN:
        # Admin can assign Viewer, Analyst, Editor (not Admin or SuperAdmin)
        return target_role in [Role.VIEWER, Role.ANALYST, Role.EDITOR]
    
    return False


def can_manage_user(manager_role: str, target_role: str) -> bool:
    """
    Check if a user with manager_role can manage a user with target_role.
    
    Rules:
    - SuperAdmin can manage anyone
    - Admin can manage users with Editor role or lower
    - Others cannot manage users
    
    Args:
        manager_role: Role of user trying to manage
        target_role: Role of user being managed
        
    Returns:
        True if management is allowed, False otherwise
    """
    if manager_role == Role.SUPERADMIN:
        return True
    
    if manager_role == Role.ADMIN:
        # Admin can manage Viewer, Analyst, Editor (not Admin or SuperAdmin)
        return target_role in [Role.VIEWER, Role.ANALYST, Role.EDITOR]
    
    return False


def get_assignable_roles(assigner_role: str) -> List[str]:
    """
    Get list of roles that can be assigned by a user with assigner_role.
    
    Args:
        assigner_role: Role of user trying to assign
        
    Returns:
        List of assignable role names
    """
    if assigner_role == Role.SUPERADMIN:
        return Role.all_roles()
    
    if assigner_role == Role.ADMIN:
        return [Role.VIEWER, Role.ANALYST, Role.EDITOR]
    
    return []


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

def is_admin_role(role: str) -> bool:
    """
    Check if role is admin-level (for backward compatibility).
    
    Args:
        role: Role name
        
    Returns:
        True if role is Admin or SuperAdmin
    """
    return role in [Role.ADMIN, Role.SUPERADMIN]


def role_from_is_admin(is_admin: bool) -> str:
    """
    Convert is_admin flag to role (for migration).
    
    Args:
        is_admin: Boolean admin flag
        
    Returns:
        Role name (Admin if True, Viewer if False)
    """
    return Role.ADMIN if is_admin else Role.VIEWER
