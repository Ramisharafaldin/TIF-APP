"""
Audit Logging System
Detailed logging for security, compliance, and debugging.
Works completely independently of AI services.
"""
import logging
import json
from datetime import datetime
from typing import Dict, Optional, List, Any
import os

logger = logging.getLogger("audit_logger")

class AuditLogger:
    """
    Robust audit logger that handles system events, user actions, and security alerts.
    """
    def __init__(self):
        self.enabled = True
        
    def log_event(self, event_type: str, user_id: str, details: Dict[str, Any], level: str = "INFO"):
        """
        Log a generic audit event.
        
        Args:
            event_type: Category of event (e.g., 'login', 'export', 'ai_request')
            user_id: ID of the user performing the action
            details: Dictionary of event details
            level: Log level (INFO, WARNING, ERROR)
        """
        if not self.enabled:
            return

        try:
            timestamp = datetime.now().isoformat()
            
            # Structure the log entry
            log_entry = {
                "timestamp": timestamp,
                "event_type": event_type,
                "user_id": user_id,
                "level": level,
                "details": details
            }
            
            # Serialize for structured logging
            log_message = json.dumps(log_entry)
            
            # Dispatch to standard python logger
            if level.upper() == "ERROR":
                logger.error(log_message)
            elif level.upper() == "WARNING":
                logger.warning(log_message)
            else:
                logger.info(log_message)
                
        except Exception as e:
            # Fallback logging to ensure we never crash on logging failure
            print(f"CRITICAL AUDIT FAILURE: {e}")

    def log_security_event(self, security_event_type: str, details: Dict[str, Any], level: str = "WARNING"):
        """
        Specific logger for security events.
        
        Args:
            security_event_type: Type of security event
            details: Event details
            level: Log level (default WARNING)
        """
        user_id = details.get('user_id', 'unknown')
        self.log_event(
            event_type="security_event",
            user_id=user_id,
            details={
                "security_type": security_event_type,
                **details
            },
            level=level
        )

    def log_ai_operation(self, operation_type: str, user_id: str, data_accessed: List[str], success: bool):
        """
        Specific logger for AI operations.
        Works even if AI is disabled (logs the attempt).
        """
        level = "INFO" if success else "WARNING"
        self.log_event(
            event_type="ai_operation",
            user_id=user_id,
            details={
                "operation": operation_type,
                "data_accessed": data_accessed,
                "success": success
            },
            level=level
        )

    def validate_user_permissions(self, user_id: str, action: str, resource: str) -> bool:
        """
        Real permission check backed by the RBAC module.

        Delegates to `rbac.validate_user_permissions`, which maps the
        (action, resource) intent to the corresponding RBAC permission and
        verifies the user's role holds it. Returns False (deny by default)
        when the role cannot be resolved or the permission is missing.
        """
        try:
            from rbac import validate_user_permissions as _rbac_check
            allowed = _rbac_check(user_id, action, resource)
        except Exception as exc:
            self.log_event(
                event_type="permission_check",
                user_id=user_id,
                details={"action": action, "resource": resource, "result": "error", "error": str(exc)},
                level="ERROR"
            )
            return False

        self.log_event(
            event_type="permission_check",
            user_id=user_id,
            details={"action": action, "resource": resource, "result": "allowed" if allowed else "denied"},
            level="INFO" if allowed else "WARNING"
        )
        return allowed

# Singleton instance
audit_logger = AuditLogger()
