"""
Configuration classes for Flask application.
Supports Development and Production environments with AI integration.
"""
import os
from datetime import timedelta
from utils.ai_config import AIConfigManager


class Config:
    """
    Base configuration class with common settings.
    
    This class defines default configuration values that are shared
    across all environments. Environment-specific classes inherit from
    this base class and override settings as needed.
    
    Attributes:
        SECRET_KEY: Secret key for session encryption and CSRF tokens
        UPLOAD_FOLDER: Directory for temporary file uploads
        MAX_CONTENT_LENGTH: Maximum allowed file upload size in bytes
        ALLOWED_EXTENSIONS: Set of allowed file extensions
        SESSION_TYPE: Session storage backend type
        SESSION_PERMANENT: Whether sessions persist across browser restarts
        PERMANENT_SESSION_LIFETIME: Duration before session expires
        SESSION_COOKIE_SECURE: Whether to require HTTPS for session cookies
        SESSION_COOKIE_HTTPONLY: Whether to prevent JavaScript access to cookies
        SESSION_COOKIE_SAMESITE: CSRF protection level for cookies
        AI_CONFIG: AI configuration manager instance
    """
    
    # Secret key for session management and CSRF protection.
    # IMPORTANT: Override this in production with a strong random key.
    # The base class intentionally has NO silent fallback (item 1.8):
    # a missing key must surface as None so ProductionConfig.init_app
    # hard-fails. Only DevelopmentConfig is permitted a dev fallback.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # File upload configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH_MB', '50')) * 1024 * 1024
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = 'flask_sessions'  # Will be resolved to runtime directory
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.environ.get('SESSION_COOKIE_HTTPONLY', 'true').lower() == 'true'
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    
    # Phase 3 + 4 — MongoDB backend (external, already-running service).
    # DB_BACKEND is kept as a deprecated attribute for backward compat;
    # the app always uses MongoDB (DuckDB fully removed per Decision D).
    DB_BACKEND = 'mongodb'
    MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017')
    MONGODB_DB_NAME = os.environ.get('MONGODB_DB_NAME', 'tif')
    
    # AI Configuration
    # ZERO-TOLERANCE: AI is disabled by default. Must be explicitly enabled via AI_ENABLED env var.
    AI_ENABLED = os.environ.get('AI_ENABLED', 'false').lower() == 'true'
    AI_CONFIG = AIConfigManager()
    
    @classmethod
    def init_app(cls, app):
        """
        Initialize base configuration.
        
        Args:
            app: Flask application instance
        """
        # Validate AI configuration on startup
        ai_config = cls.AI_CONFIG
        is_valid, errors = ai_config.validate_configuration()
        
        if not is_valid:
            app.logger.warning("AI Configuration Issues:")
            for error in errors:
                app.logger.warning(f"  - {error}")
        
        # Log configuration status
        ai_config.log_configuration_status()


class DevelopmentConfig(Config):
    """
    Development environment configuration.
    
    Optimized for local development with debug mode enabled
    and relaxed security settings. Should never be used in production.
    
    Key differences from base Config:
    - Debug mode enabled for detailed error pages
    - Less strict cookie security (no HTTPS required)
    - Exception propagation enabled for better debugging
    - Relaxed AI settings for testing
    """
    
    DEBUG = True
    TESTING = False

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Development-specific settings
    SESSION_COOKIE_SECURE = False
    
    # Enable detailed error pages
    PROPAGATE_EXCEPTIONS = True
    
    @classmethod
    def init_app(cls, app):
        """
        Initialize development configuration.
        
        Args:
            app: Flask application instance
        """
        super().init_app(app)
        
        # Development-specific AI settings
        app.logger.info("Development mode: AI debug features enabled")
        
        # Warn about development settings
        if cls.SECRET_KEY == 'dev-secret-key-change-in-production':
            app.logger.warning("Using default SECRET_KEY - change for production!")


class ProductionConfig(Config):
    """
    Production environment configuration.
    
    Optimized for production deployment with strict security settings.
    Requires HTTPS and enforces secure session management.
    
    Key differences from base Config:
    - Debug mode disabled
    - Secure cookies required (HTTPS only)
    - Strict CSRF protection
    - SECRET_KEY must be set via environment variable
    - AI production readiness validation
    
    Warning:
        Will raise ValueError if SECRET_KEY is not set in environment
        or if AI configuration is not production-ready.
    """
    
    DEBUG = False
    TESTING = False
    
    # Production-specific settings
    SESSION_COOKIE_SECURE = True  # Requires HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # Override secret key to require environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    @classmethod
    def init_app(cls, app):
        """
        Initialize production configuration and validate settings.
        
        Args:
            app: Flask application instance
            
        Raises:
            ValueError: If SECRET_KEY is not set in environment or
                       if AI configuration is not production-ready
            
        Note:
            This method is called automatically when using ProductionConfig.
            It ensures all required production settings are properly configured.
        """
        super().init_app(app)
        
        # Validate SECRET_KEY
        if not cls.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable must be set in production")
        
        if cls.SECRET_KEY == 'dev-secret-key-change-in-production':
            raise ValueError("SECRET_KEY is using default development value in production")
        
        if len(cls.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY should be at least 32 characters long for production")
        
        # Validate AI production readiness
        ai_config = cls.AI_CONFIG
        is_ready, issues = ai_config.validate_production_readiness()
        
        if not is_ready:
            app.logger.error("AI Configuration is not production-ready:")
            for issue in issues:
                app.logger.error(f"  - {issue}")
            raise ValueError("AI configuration is not production-ready. See logs for details.")
        
        # Log production readiness
        app.logger.info("Production configuration validated successfully")
        app.logger.info("AI services are production-ready")


class TestingConfig(Config):
    """
    Testing environment configuration.
    
    Optimized for automated testing with minimal external dependencies
    and fast execution times.
    """
    
    DEBUG = False
    TESTING = True
    
    # Testing-specific settings
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing
    SESSION_COOKIE_SECURE = False
    
    # Disable AI features for testing (unless specifically needed)
    AI_FEATURES_ENABLED = False
    
    @classmethod
    def init_app(cls, app):
        """
        Initialize testing configuration.
        
        Args:
            app: Flask application instance
        """
        # Skip AI validation for testing
        app.logger.info("Testing mode: AI features disabled by default")


# Configuration dictionary for easy access by environment name
# Maps environment names to their corresponding configuration classes
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig  # Used when FLASK_ENV is not set
}


def get_config(env=None):
    """
    Get configuration class based on environment.
    
    Args:
        env: Environment name ('development', 'production', 'testing', or None)
        
    Returns:
        Configuration class
    """
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    
    return config.get(env, config['default'])


def validate_config(env=None):
    """
    Validate configuration for the specified environment.
    
    Args:
        env: Environment name to validate
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    from utils.config_validator import ConfigValidator
    
    validator = ConfigValidator(env)
    return validator.validate_all()
