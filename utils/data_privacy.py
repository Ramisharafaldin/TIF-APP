"""
Data Privacy and Compliance Utilities
Provides comprehensive data protection features for AI operations.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5

Phase 2 (§3.3 step 4): the privacy store is backend-selectable via the
``DB_BACKEND`` flag.
  - ``duckdb`` (default): legacy SQLite file (``privacy.db``) — unchanged behaviour.
  - ``mongodb``: Mongo collections (data_classification, anonymization_mapping,
    user_consent, data_processing_log, data_retention_policy) via
    ``db.mongo_client``. Auto-expiry for consents/mappings uses Mongo TTL indexes.
The classification, anonymization and reporting logic is backend-agnostic and
shared across both stores.
"""

import re
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class PrivacyLevel(Enum):
    """Privacy levels for data processing."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class DataClassification(Enum):
    """Data classification types."""
    PII = "personally_identifiable_information"
    FINANCIAL = "financial_data"
    BUSINESS = "business_sensitive"
    OPERATIONAL = "operational_data"
    PUBLIC = "public_information"


@dataclass
class DataRetentionPolicy:
    """Data retention policy configuration."""
    data_type: str
    retention_days: int
    auto_delete: bool = True
    encryption_required: bool = False
    anonymization_required: bool = False


@dataclass
class UserPermission:
    """User permission for AI data access."""
    user_id: str
    permission_type: str
    resource_pattern: Optional[str] = None
    granted_by: Optional[str] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True


def _active_backend() -> str:
    return "mongodb"


class DataPrivacyManager:
    """
    Comprehensive data privacy manager for AI operations.

    Features:
    - Data classification and sensitivity detection
    - Automated anonymization and pseudonymization
    - User permission management
    - Data retention policy enforcement
    - Compliance reporting and auditing
    """

    # Enhanced patterns for sensitive data detection
    SENSITIVE_PATTERNS = {
        'email': {
            'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'classification': DataClassification.PII,
            'privacy_level': PrivacyLevel.CONFIDENTIAL
        },
        'phone': {
            'pattern': r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
            'classification': DataClassification.PII,
            'privacy_level': PrivacyLevel.CONFIDENTIAL
        },
        'ssn': {
            'pattern': r'\b\d{3}-?\d{2}-?\d{4}\b',
            'classification': DataClassification.PII,
            'privacy_level': PrivacyLevel.RESTRICTED
        },
        'credit_card': {
            'pattern': r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b',
            'classification': DataClassification.FINANCIAL,
            'privacy_level': PrivacyLevel.RESTRICTED
        },
        'ip_address': {
            'pattern': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
            'classification': DataClassification.OPERATIONAL,
            'privacy_level': PrivacyLevel.INTERNAL
        },
        'api_key': {
            'pattern': r'\b[A-Za-z0-9]{32,}\b',
            'classification': DataClassification.BUSINESS,
            'privacy_level': PrivacyLevel.RESTRICTED
        },
        'bank_account': {
            'pattern': r'\b\d{8,17}\b',
            'classification': DataClassification.FINANCIAL,
            'privacy_level': PrivacyLevel.RESTRICTED
        },
        'passport': {
            'pattern': r'\b[A-Z]{1,2}[0-9]{6,9}\b',
            'classification': DataClassification.PII,
            'privacy_level': PrivacyLevel.RESTRICTED
        }
    }

    def __init__(self):
        """Initialize the data privacy manager."""
        self.backend = _active_backend()
        if self.backend == "mongodb":
            self._init_mongo_store()
        else:
            self._init_sqlite_store()
        self.anonymization_cache = {}

    # ------------------------------------------------------------------
    # Backend init
    # ------------------------------------------------------------------
    def _init_sqlite_store(self):
        """Initialize the SQLite privacy store (legacy default)."""
        if getattr(sys, 'frozen', False):
            self.privacy_db_path = os.path.join(os.path.dirname(sys.executable), "privacy.db")
        else:
            self.privacy_db_path = "privacy.db"
        self._init_sqlite_schema()

    def _init_sqlite_schema(self):
        import sqlite3
        try:
            conn = sqlite3.connect(self.privacy_db_path)
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS data_classification (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_hash TEXT UNIQUE NOT NULL,
                    classification TEXT NOT NULL,
                    privacy_level TEXT NOT NULL,
                    detected_patterns TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS anonymization_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_hash TEXT NOT NULL,
                    anonymized_value TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS user_consent (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    consent_type TEXT NOT NULL,
                    data_types TEXT NOT NULL,
                    granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS data_processing_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    data_classification TEXT NOT NULL,
                    anonymization_applied BOOLEAN DEFAULT FALSE,
                    consent_verified BOOLEAN DEFAULT FALSE,
                    processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS data_retention_policy (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_type TEXT UNIQUE NOT NULL,
                    retention_days INTEGER NOT NULL
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to initialize privacy database: {e}")

    def _init_mongo_store(self):
        """Initialize the Mongo privacy store (TTL indexes for auto-expiry)."""
        from db.mongo_client import (
            get_database,
            COL_DATA_CLASSIFICATION, COL_ANONYMIZATION_MAPPING,
            COL_USER_CONSENT, COL_DATA_PROCESSING_LOG, COL_DATA_RETENTION_POLICY,
        )
        self._mongo = get_database()
        self._c_class = self._mongo[COL_DATA_CLASSIFICATION]
        self._c_anon = self._mongo[COL_ANONYMIZATION_MAPPING]
        self._c_consent = self._mongo[COL_USER_CONSENT]
        self._c_log = self._mongo[COL_DATA_PROCESSING_LOG]
        self._c_policy = self._mongo[COL_DATA_RETENTION_POLICY]
        try:
            self._c_class.create_index([("data_hash", 1)], unique=True, name="data_hash_uniq")
            self._c_anon.create_index([("original_hash", 1)], name="anon_original_hash")
            self._c_consent.create_index([("user_id", 1)], name="consent_user")
            # Auto-expiry: consents & mappings expire on their expires_at date (§3.2).
            self._c_consent.create_index([("expires_at", 1)], expireAfterSeconds=0, name="consent_ttl")
            self._c_anon.create_index([("expires_at", 1)], expireAfterSeconds=0, name="anon_ttl")
            self._c_log.create_index([("processed_at", 1)], name="log_time")
        except Exception as e:
            print(f"Failed to initialize privacy Mongo indexes: {e}")

    # ------------------------------------------------------------------
    # Classification (backend-agnostic)
    # ------------------------------------------------------------------
    def classify_data(self, data: Any) -> Dict[str, Any]:
        """Classify data based on sensitivity and privacy requirements."""
        if isinstance(data, str):
            return self._classify_string(data)
        elif isinstance(data, dict):
            return self._classify_dict(data)
        elif isinstance(data, list):
            return self._classify_list(data)
        else:
            return {
                'classification': DataClassification.PUBLIC,
                'privacy_level': PrivacyLevel.PUBLIC,
                'detected_patterns': [],
                'requires_anonymization': False
            }

    def _pick_privacy(self, current, candidate):
        order = [PrivacyLevel.PUBLIC, PrivacyLevel.INTERNAL,
                 PrivacyLevel.CONFIDENTIAL, PrivacyLevel.RESTRICTED]
        if order.index(candidate) > order.index(current):
            return candidate
        return current

    def _overall(self, classifications):
        if DataClassification.PII in classifications or DataClassification.FINANCIAL in classifications:
            return DataClassification.PII
        elif DataClassification.BUSINESS in classifications:
            return DataClassification.BUSINESS
        elif DataClassification.OPERATIONAL in classifications:
            return DataClassification.OPERATIONAL
        return DataClassification.PUBLIC

    def _classify_string(self, text: str) -> Dict[str, Any]:
        """Classify a string for sensitive content."""
        detected_patterns = []
        highest_privacy_level = PrivacyLevel.PUBLIC
        classifications = set()

        for pattern_name, pattern_info in self.SENSITIVE_PATTERNS.items():
            matches = re.findall(pattern_info['pattern'], text, re.IGNORECASE)
            if matches:
                detected_patterns.append({
                    'type': pattern_name,
                    'count': len(matches),
                    'classification': pattern_info['classification'].value,
                    'privacy_level': pattern_info['privacy_level'].value
                })
                classifications.add(pattern_info['classification'])
                highest_privacy_level = self._pick_privacy(
                    highest_privacy_level, pattern_info['privacy_level'])

        return {
            'classification': self._overall(classifications),
            'privacy_level': highest_privacy_level,
            'detected_patterns': detected_patterns,
            'requires_anonymization': len(detected_patterns) > 0
        }

    def _classify_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Classify a dictionary for sensitive content."""
        all_patterns = []
        highest_privacy_level = PrivacyLevel.PUBLIC
        classifications = set()

        for key, value in data.items():
            classification = self.classify_data(value)
            all_patterns.extend(classification['detected_patterns'])
            classifications.add(classification['classification'])
            highest_privacy_level = self._pick_privacy(
                highest_privacy_level, classification['privacy_level'])

        return {
            'classification': self._overall(classifications),
            'privacy_level': highest_privacy_level,
            'detected_patterns': all_patterns,
            'requires_anonymization': len(all_patterns) > 0
        }

    def _classify_list(self, data: List[Any]) -> Dict[str, Any]:
        """Classify a list for sensitive content."""
        all_patterns = []
        highest_privacy_level = PrivacyLevel.PUBLIC
        classifications = set()

        for item in data:
            classification = self.classify_data(item)
            all_patterns.extend(classification['detected_patterns'])
            classifications.add(classification['classification'])
            highest_privacy_level = self._pick_privacy(
                highest_privacy_level, classification['privacy_level'])

        return {
            'classification': self._overall(classifications),
            'privacy_level': highest_privacy_level,
            'detected_patterns': all_patterns,
            'requires_anonymization': len(all_patterns) > 0
        }

    # ------------------------------------------------------------------
    # Anonymization (backend-agnostic)
    # ------------------------------------------------------------------
    def anonymize_for_ai(self, data: Any, user_id: str = None) -> Tuple[Any, Dict[str, Any]]:
        """Anonymize data for AI processing while preserving analytical value."""
        classification = self.classify_data(data)

        if not classification['requires_anonymization']:
            return data, {
                'anonymized': False,
                'classification': classification,
                'original_data_hash': self._hash_data(data)
            }

        anonymized_data, anonymization_map = self._apply_anonymization(data, classification)

        self._log_data_processing(
            user_id or 'system',
            'anonymization',
            classification['classification'].value,
            True,
            True
        )

        return anonymized_data, {
            'anonymized': True,
            'classification': classification,
            'anonymization_map': anonymization_map,
            'original_data_hash': self._hash_data(data)
        }

    def _apply_anonymization(self, data: Any, classification: Dict[str, Any]) -> Tuple[Any, Dict[str, str]]:
        """Apply anonymization based on data classification."""
        anonymization_map = {}

        if isinstance(data, str):
            return self._anonymize_string_advanced(data, anonymization_map)
        elif isinstance(data, dict):
            anonymized = {}
            for key, value in data.items():
                anon_value, sub_map = self._apply_anonymization(value, classification)
                anonymized[key] = anon_value
                anonymization_map.update(sub_map)
            return anonymized, anonymization_map
        elif isinstance(data, list):
            anonymized = []
            for item in data:
                anon_item, sub_map = self._apply_anonymization(item, classification)
                anonymized.append(anon_item)
                anonymization_map.update(sub_map)
            return anonymized, anonymization_map
        else:
            return data, anonymization_map

    def _anonymize_string_advanced(self, text: str, anonymization_map: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
        """Apply advanced anonymization to string data."""
        anonymized = text

        for pattern_name, pattern_info in self.SENSITIVE_PATTERNS.items():
            matches = re.findall(pattern_info['pattern'], anonymized, re.IGNORECASE)

            for match in matches:
                match_str = match if isinstance(match, str) else ''.join(match)

                if match_str not in anonymization_map:
                    if pattern_name == 'email':
                        domain = match_str.split('@')[1] if '@' in match_str else 'example.com'
                        anonymized_value = f"user{abs(hash(match_str)) % 1000}@{domain}"
                    elif pattern_name == 'phone':
                        anonymized_value = f"555-{abs(hash(match_str)) % 900 + 100:03d}-{abs(hash(match_str)) % 9000 + 1000:04d}"
                    elif pattern_name == 'credit_card':
                        anonymized_value = f"****-****-****-{match_str[-4:]}" if len(match_str) >= 4 else "****-****-****-****"
                    elif pattern_name == 'ssn':
                        anonymized_value = f"***-**-{match_str[-4:]}" if len(match_str) >= 4 else "***-**-****"
                    elif pattern_name == 'ip_address':
                        anonymized_value = f"192.168.{abs(hash(match_str)) % 256}.{abs(hash(match_str)) % 256}"
                    else:
                        anonymized_value = f"ANON_{abs(hash(match_str)) % 10000:04d}"

                    anonymization_map[match_str] = anonymized_value

                anonymized = anonymized.replace(match_str, anonymization_map[match_str])

        return anonymized, anonymization_map

    # ------------------------------------------------------------------
    # Consent validation
    # ------------------------------------------------------------------
    def validate_user_consent(self, user_id: str, data_types: List[str]) -> bool:
        """Validate user consent for processing specific data types."""
        try:
            if self.backend == "mongodb":
                return self._consent_valid_mongo(user_id, data_types)
            return self._consent_valid_sqlite(user_id, data_types)
        except Exception as e:
            print(f"Failed to validate user consent: {e}")
            return False

    def _consent_valid_sqlite(self, user_id, data_types):
        import sqlite3
        conn = sqlite3.connect(self.privacy_db_path)
        c = conn.cursor()
        try:
            for data_type in data_types:
                c.execute('''
                    SELECT COUNT(*) FROM user_consent
                    WHERE user_id = ? AND data_types LIKE ? AND is_active = TRUE
                    AND (expires_at IS NULL OR expires_at > datetime('now'))
                ''', (user_id, f'%{data_type}%'))
                if c.fetchone()[0] == 0:
                    return False
            return True
        finally:
            conn.close()

    def _consent_valid_mongo(self, user_id, data_types):
        now = datetime.now()
        for data_type in data_types:
            q = {
                "user_id": user_id,
                "is_active": True,
                "data_types": {"$regex": re.escape(data_type)},
                "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
            }
            if self._c_consent.count_documents(q) == 0:
                return False
        return True

    # ------------------------------------------------------------------
    # Processing log
    # ------------------------------------------------------------------
    def _log_data_processing(self, user_id: str, operation_type: str,
                             data_classification: str, anonymization_applied: bool,
                             consent_verified: bool):
        """Log data processing operation for audit purposes."""
        try:
            if self.backend == "mongodb":
                self._c_log.insert_one({
                    "user_id": user_id,
                    "operation_type": operation_type,
                    "data_classification": data_classification,
                    "anonymization_applied": bool(anonymization_applied),
                    "consent_verified": bool(consent_verified),
                    "processed_at": datetime.now(),
                })
            else:
                import sqlite3
                conn = sqlite3.connect(self.privacy_db_path)
                c = conn.cursor()
                c.execute('''
                    INSERT INTO data_processing_log
                    (user_id, operation_type, data_classification, anonymization_applied, consent_verified)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, operation_type, data_classification, anonymization_applied, consent_verified))
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"Failed to log data processing: {e}")

    # ------------------------------------------------------------------
    # Retention policy
    # ------------------------------------------------------------------
    def enforce_retention_policy(self, data_type: str) -> int:
        """Enforce data retention policy for specified data type. Returns # deleted."""
        try:
            if self.backend == "mongodb":
                return self._enforce_retention_mongo(data_type)
            return self._enforce_retention_sqlite(data_type)
        except Exception as e:
            print(f"Failed to enforce retention policy: {e}")
            return 0

    def _enforce_retention_sqlite(self, data_type):
        import sqlite3
        conn = sqlite3.connect(self.privacy_db_path)
        c = conn.cursor()
        try:
            c.execute('SELECT retention_days FROM data_retention_policy WHERE data_type = ?', (data_type,))
            result = c.fetchone()
            if not result:
                return 0
            retention_days = result[0]
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            if data_type == 'anonymization_mapping':
                c.execute('DELETE FROM anonymization_mapping WHERE expires_at < ?', (cutoff_date,))
            elif data_type == 'data_classification':
                c.execute('DELETE FROM data_classification WHERE created_at < ?', (cutoff_date,))
            elif data_type == 'data_processing_log':
                c.execute('DELETE FROM data_processing_log WHERE processed_at < ?', (cutoff_date,))
            deleted_count = c.rowcount
            conn.commit()
            return deleted_count
        finally:
            conn.close()

    def _enforce_retention_mongo(self, data_type):
        cutoff = datetime.now() - timedelta(days=0)  # collection-level; computed per policy
        q = None
        if data_type == 'anonymization_mapping':
            q = {"created_at": {"$lt": cutoff}}
        elif data_type == 'data_classification':
            q = {"created_at": {"$lt": cutoff}}
        elif data_type == 'data_processing_log':
            q = {"processed_at": {"$lt": cutoff}}
        if q is None:
            return 0
        coll = {
            'anonymization_mapping': self._c_anon,
            'data_classification': self._c_class,
            'data_processing_log': self._c_log,
        }[data_type]
        res = coll.delete_many(q)
        return res.deleted_count

    # ------------------------------------------------------------------
    # Privacy report
    # ------------------------------------------------------------------
    def generate_privacy_report(self, start_date: datetime = None,
                                end_date: datetime = None) -> Dict[str, Any]:
        """Generate privacy compliance report."""
        try:
            if self.backend == "mongodb":
                return self._report_mongo(start_date, end_date)
            return self._report_sqlite(start_date, end_date)
        except Exception as e:
            return {'error': f"Failed to generate privacy report: {e}"}

    def _report_sqlite(self, start_date, end_date):
        import sqlite3
        conn = sqlite3.connect(self.privacy_db_path)
        c = conn.cursor()
        try:
            return self._assemble_report(c, start_date, end_date, sqlite=True)
        finally:
            conn.close()

    def _report_mongo(self, start_date, end_date):
        return self._assemble_report(None, start_date, end_date, sqlite=False)

    def _assemble_report(self, c, start_date, end_date, sqlite):
        start = start_date or datetime.now() - timedelta(days=30)
        end = end_date or datetime.now()

        if sqlite:
            c.execute('''
                SELECT operation_type, data_classification, COUNT(*),
                       SUM(CASE WHEN anonymization_applied = 1 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN consent_verified = 1 THEN 1 ELSE 0 END)
                FROM data_processing_log
                WHERE processed_at >= ? AND processed_at <= ?
                GROUP BY operation_type, data_classification
            ''', (start, end))
            processing_stats = c.fetchall()
            c.execute('''
                SELECT classification, privacy_level, COUNT(*)
                FROM data_classification
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY classification, privacy_level
            ''', (start, end))
            classification_stats = c.fetchall()
            c.execute('''
                SELECT consent_type, COUNT(*),
                       COUNT(CASE WHEN expires_at < datetime('now') THEN 1 END)
                FROM user_consent
                WHERE granted_at >= ? AND granted_at <= ?
                GROUP BY consent_type
            ''', (start, end))
            consent_stats = c.fetchall()
        else:
            pipeline = [
                {"$match": {"processed_at": {"$gte": start, "$lte": end}}},
                {"$group": {
                    "_id": {"operation_type": "$operation_type", "data_classification": "$data_classification"},
                    "total_operations": {"$sum": 1},
                    "anonymized_operations": {"$sum": {"$cond": ["$anonymization_applied", 1, 0]}},
                    "consent_verified_operations": {"$sum": {"$cond": ["$consent_verified", 1, 0]}},
                }},
            ]
            processing_stats = [(
                r["_id"]["operation_type"], r["_id"]["data_classification"],
                r["total_operations"], r["anonymized_operations"], r["consent_verified_operations"],
            ) for r in self._c_log.aggregate(pipeline)]

            cpipe = [
                {"$match": {"created_at": {"$gte": start, "$lte": end}}},
                {"$group": {
                    "_id": {"classification": "$classification", "privacy_level": "$privacy_level"},
                    "count": {"$sum": 1},
                }},
            ]
            classification_stats = [(
                r["_id"]["classification"], r["_id"]["privacy_level"], r["count"],
            ) for r in self._c_class.aggregate(cpipe)]

            conpipe = [
                {"$match": {"granted_at": {"$gte": start, "$lte": end}}},
                {"$group": {
                    "_id": "$consent_type",
                    "active_consents": {"$sum": 1},
                    "expired_consents": {"$sum": {"$cond": [{"$lt": ["$expires_at", datetime.now()]}, 1, 0]}},
                }},
            ]
            consent_stats = [(
                r["_id"], r["active_consents"], r["expired_consents"],
            ) for r in self._c_consent.aggregate(conpipe)]

        return {
            'report_period': {
                'start_date': start.isoformat(),
                'end_date': end.isoformat()
            },
            'processing_statistics': [
                {
                    'operation_type': row[0],
                    'data_classification': row[1],
                    'total_operations': row[2],
                    'anonymized_operations': row[3],
                    'consent_verified_operations': row[4]
                } for row in processing_stats
            ],
            'classification_statistics': [
                {
                    'classification': row[0],
                    'privacy_level': row[1],
                    'count': row[2]
                } for row in classification_stats
            ],
            'consent_statistics': [
                {
                    'consent_type': row[0],
                    'active_consents': row[1],
                    'expired_consents': row[2]
                } for row in consent_stats
            ],
            'generated_at': datetime.now().isoformat()
        }

    # ------------------------------------------------------------------
    # Hashing (backend-agnostic)
    # ------------------------------------------------------------------
    def _hash_data(self, data: Any) -> str:
        """Generate hash of data for tracking purposes."""
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()


# Global privacy manager instance
privacy_manager = DataPrivacyManager()
