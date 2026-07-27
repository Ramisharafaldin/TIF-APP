"""
Configuration Validation Utilities
Provides comprehensive validation for application configuration.
"""
import os
import sys
import logging
from typing import Dict, List, Tuple, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ai_config import AIConfigManager
from config import get_config

logger = logging.getLogger(__name__)


class ConfigValidator:
    """
    Validates application configuration for different environments.
    
    Provides comprehensive validation of Flask app configuration,
    AI service settings, and environment-specific requirements.
    """
    
    def __init__(self, environment: str = None):
        """
        Initialize the configuration validator.
        
        Args:
            environment: Target environment ('development', 'production', or None for auto-detect)
        """
        self.environment = environment or os.getenv('FLASK_ENV', 'development')
        self.ai_config = AIConfigManager()
        self.flask_config = get_config(self.environment)
        
    def validate_all(self) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Validate all configuration aspects.
        
        Returns:
            Tuple of (is_valid, dict_of_validation_results)
        """
        results = {
            'flask': [],
            'ai': [],
            'security': [],
            'environment': [],
            'production_readiness': []
        }
        
        # Validate Flask configuration
        flask_valid, flask_errors = self.validate_flask_config()
        results['flask'] = flask_errors
        
        # Validate AI configuration
        ai_valid, ai_errors = self.ai_config.validate_configuration()
        results['ai'] = ai_errors
        
        # Validate security settings
        security_valid, security_errors = self.validate_security_config()
        results['security'] = security_errors
        
        # Validate environment-specific settings
        env_valid, env_errors = self.validate_environment_config()
        results['environment'] = env_errors
        
        # Validate production readiness if in production
        if self.environment == 'production':
            prod_valid, prod_errors = self.ai_config.validate_production_readiness()
            results['production_readiness'] = prod_errors
        
        # Overall validation status
        all_valid = all([
            flask_valid,
            ai_valid,
            security_valid,
            env_valid,
            (self.environment != 'production' or len(results['production_readiness']) == 0)
        ])
        
        return all_valid, results
    
    def validate_flask_config(self) -> Tuple[bool, List[str]]:
        """
        Validate Flask application configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check SECRET_KEY
        secret_key = os.getenv('SECRET_KEY')
        if not secret_key:
            errors.append("SECRET_KEY environment variable is not set")
        elif secret_key == 'dev-secret-key-change-in-production' and self.environment == 'production':
            errors.append("SECRET_KEY is using default development value in production")
        elif len(secret_key) < 32:
            errors.append("SECRET_KEY should be at least 32 characters long")
        
        # Check upload settings
        max_content_length = os.getenv('MAX_CONTENT_LENGTH_MB')
        if max_content_length:
            try:
                size_mb = int(max_content_length)
                if size_mb < 1 or size_mb > 500:
                    errors.append(f"MAX_CONTENT_LENGTH_MB ({size_mb}) should be between 1 and 500 MB")
            except ValueError:
                errors.append("MAX_CONTENT_LENGTH_MB must be a valid integer")
        
        # Check upload folder
        upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        if not os.path.exists(upload_folder):
            try:
                os.makedirs(upload_folder, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create upload folder '{upload_folder}': {e}")
        
        # Check database path
        db_path = os.getenv('DATABASE_PATH', 'users.db')
        db_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else '.'
        if not os.path.exists(db_dir):
            errors.append(f"Database directory '{db_dir}' does not exist")
        
        return len(errors) == 0, errors
    
    def validate_security_config(self) -> Tuple[bool, List[str]]:
        """
        Validate security-related configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check session security in production
        if self.environment == 'production':
            if not os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true':
                errors.append("SESSION_COOKIE_SECURE should be enabled in production")
            
            if not os.getenv('SESSION_COOKIE_HTTPONLY', 'true').lower() == 'true':
                errors.append("SESSION_COOKIE_HTTPONLY should be enabled in production")
        
        # Check AI security settings
        security_settings = self.ai_config.get_security_settings()
        
        if self.environment == 'production':
            if security_settings['debug_logging']:
                errors.append("AI debug logging should be disabled in production")
            
            if not security_settings['audit_enabled']:
                errors.append("AI audit logging should be enabled in production")
            
            if not security_settings['mask_sensitive_data']:
                errors.append("AI sensitive data masking should be enabled in production")
        
        # Check data retention settings
        if security_settings['data_retention_days'] < 1:
            errors.append("AI data retention period should be at least 1 day")
        elif security_settings['data_retention_days'] > 365:
            errors.append("AI data retention period should not exceed 365 days")
        
        return len(errors) == 0, errors
    
    def validate_environment_config(self) -> Tuple[bool, List[str]]:
        """
        Validate environment-specific configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check Flask environment
        flask_env = os.getenv('FLASK_ENV')
        if not flask_env:
            errors.append("FLASK_ENV environment variable is not set")
        elif flask_env not in ['development', 'production']:
            errors.append(f"Invalid FLASK_ENV value: {flask_env}. Must be 'development' or 'production'")
        
        # Check debug settings
        flask_debug = os.getenv('FLASK_DEBUG', 'false').lower()
        if self.environment == 'production' and flask_debug == 'true':
            errors.append("FLASK_DEBUG should be disabled in production")
        
        # Check host and port settings
        flask_host = os.getenv('FLASK_HOST', '127.0.0.1')
        flask_port = os.getenv('FLASK_PORT', '5000')
        
        try:
            port = int(flask_port)
            if port < 1 or port > 65535:
                errors.append(f"Invalid FLASK_PORT: {port}. Must be between 1 and 65535")
        except ValueError:
            errors.append("FLASK_PORT must be a valid integer")
        
        # Validate host format (basic check)
        if flask_host not in ['0.0.0.0', '127.0.0.1', 'localhost'] and not self._is_valid_ip(flask_host):
            errors.append(f"Invalid FLASK_HOST: {flask_host}")
        
        return len(errors) == 0, errors
    
    def _is_valid_ip(self, ip: str) -> bool:
        """
        Basic IP address validation.
        
        Args:
            ip: IP address string to validate
            
        Returns:
            True if IP appears valid
        """
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                if not 0 <= int(part) <= 255:
                    return False
            return True
        except (ValueError, AttributeError):
            return False
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive configuration summary.
        
        Returns:
            Dict containing configuration summary
        """
        ai_config = self.ai_config.load_api_configuration()
        security_settings = self.ai_config.get_security_settings()
        env_config = self.ai_config.get_environment_config()
        
        return {
            'environment': {
                'flask_env': self.environment,
                'debug_mode': os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
                'host': os.getenv('FLASK_HOST', '127.0.0.1'),
                'port': os.getenv('FLASK_PORT', '5000')
            },
            'ai_features': {
                'enabled': ai_config['features_enabled'],
                'natural_language': ai_config['natural_language_enabled'],
                'smart_reports': ai_config['smart_reports_enabled'],
                'enhanced_forecasting': ai_config['enhanced_forecasting_enabled'],
                'dashboard_insights': ai_config['dashboard_insights_enabled']
            },
            'security': {
                'api_key_present': bool(self.ai_config.get_api_key()),
                'audit_enabled': security_settings['audit_enabled'],
                'data_masking': security_settings['mask_sensitive_data'],
                'debug_logging': security_settings['debug_logging'],
                'data_retention_days': security_settings['data_retention_days']
            },
            'performance': {
                'cache_ttl': ai_config['cache_ttl'],
                'timeout': ai_config['timeout'],
                'max_retries': ai_config['max_retries'],
                'circuit_breaker': ai_config['circuit_breaker_enabled']
            }
        }
    
    def print_validation_report(self) -> None:
        """Print a comprehensive validation report."""
        print(f"\n{'='*60}")
        print(f"Configuration Validation Report - {self.environment.upper()}")
        print(f"{'='*60}")
        
        is_valid, results = self.validate_all()
        
        # Print overall status
        status = "✅ VALID" if is_valid else "❌ INVALID"
        print(f"\nOverall Status: {status}")
        
        # Print detailed results
        for category, errors in results.items():
            if errors:
                print(f"\n{category.upper()} Issues:")
                for error in errors:
                    print(f"  ❌ {error}")
            else:
                print(f"\n{category.upper()}: ✅ Valid")
        
        # Print configuration summary
        print(f"\n{'='*60}")
        print("Configuration Summary")
        print(f"{'='*60}")
        
        summary = self.get_configuration_summary()
        for section, settings in summary.items():
            print(f"\n{section.upper()}:")
            for key, value in settings.items():
                print(f"  {key}: {value}")
        
        # Print production readiness if applicable
        if self.environment == 'production':
            print(f"\n{'='*60}")
            print("Production Readiness Checklist")
            print(f"{'='*60}")
            
            checklist = self.ai_config.get_production_checklist()
            for item, status in checklist.items():
                status_icon = "✅" if status else "❌"
                print(f"  {status_icon} {item.replace('_', ' ').title()}")


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate application configuration')
    parser.add_argument('--env', choices=['development', 'production'], 
                       help='Environment to validate (default: auto-detect)')
    parser.add_argument('--quiet', action='store_true', 
                       help='Only show errors, no detailed report')
    
    args = parser.parse_args()
    
    validator = ConfigValidator(args.env)
    
    if args.quiet:
        is_valid, results = validator.validate_all()
        if not is_valid:
            for category, errors in results.items():
                for error in errors:
                    print(f"ERROR: {error}")
            sys.exit(1)
        else:
            print("Configuration is valid")
    else:
        validator.print_validation_report()
        
        # Exit with error code if validation failed
        is_valid, _ = validator.validate_all()
        if not is_valid:
            sys.exit(1)


if __name__ == '__main__':
    main()