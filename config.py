"""
Configuration management for Flask application
Handles environment-specific settings and security configurations
"""

import os
import secrets
from typing import Dict, Any


class Config:
    """Base configuration class"""

    # Flask Settings
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY") or secrets.token_urlsafe(32)

    # Security Settings
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or secrets.token_urlsafe(32)
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get("TOKEN_EXPIRY_HOURS", 24)) * 3600

    # Upload Settings
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
    ALLOWED_EXTENSIONS = set(
        os.environ.get("ALLOWED_EXTENSIONS", "csv,xlsx,xls").split(",")
    )

    # User Management
    PASSWORD_MIN_LENGTH = int(os.environ.get("PASSWORD_MIN_LENGTH", 12))
    PASSWORD_MAX_LENGTH = int(os.environ.get("PASSWORD_MAX_LENGTH", 128))
    LOGIN_ATTEMPT_LIMIT = int(os.environ.get("LOGIN_ATTEMPT_LIMIT", 5))
    ACCOUNT_LOCKOUT_MINUTES = int(os.environ.get("ACCOUNT_LOCKOUT_MINUTES", 30))

    # Database (for future migration)
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///app.db")

    # Email Configuration
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@localhost")

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", 10 * 1024 * 1024))
    LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", 3))

    # Security Headers
    FORCE_HTTPS = os.environ.get("FORCE_HTTPS", "False").lower() == "true"
    SESSION_COOKIE_SECURE = (
        os.environ.get("SESSION_COOKIE_SECURE", "False").lower() == "true"
    )
    SESSION_COOKIE_HTTPONLY = (
        os.environ.get("SESSION_COOKIE_HTTPONLY", "True").lower() == "true"
    )
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")


class DevelopmentConfig(Config):
    """Development configuration"""

    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration"""

    DEBUG = False
    TESTING = False

    # Ensure secure settings in production
    SESSION_COOKIE_SECURE = True
    FORCE_HTTPS = True


class TestingConfig(Config):
    """Testing configuration"""

    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False
    DATABASE_URL = "sqlite:///:memory:"


# Configuration dictionary
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config(config_name: str = None) -> Config:
    """Get configuration class based on environment"""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    return config.get(config_name, config["default"])


def load_env_file(env_file: str = ".env") -> Dict[str, str]:
    """Load environment variables from file"""
    env_vars = {}

    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key] = value
                    # Set environment variable if not already set
                    if key not in os.environ:
                        os.environ[key] = value

    return env_vars
