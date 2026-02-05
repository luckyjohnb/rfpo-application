"""
Environment Configuration Loader
Centralized configuration management with validation
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


class ConfigError(Exception):
    """Configuration error exception"""

    pass


def get_env(key: str, default: Optional[str] = None, required: bool = False) -> str:
    """
    Get environment variable with validation

    Args:
        key: Environment variable name
        default: Default value if not set
        required: If True, raises error if not set

    Returns:
        Environment variable value

    Raises:
        ConfigError: If required variable is not set
    """
    value = os.environ.get(key, default)

    if required and not value:
        raise ConfigError(
            f"Required environment variable '{key}' is not set. "
            f"Please set it in your .env file or environment."
        )

    return value


def get_database_url() -> str:
    """
    Get database URL with validation

    Returns:
        Database URL string

    Raises:
        ConfigError: If DATABASE_URL is not set
    """
    db_url = get_env("DATABASE_URL", required=True)

    if not db_url.startswith(("postgresql://", "sqlite://")):
        raise ConfigError(
            f"Invalid DATABASE_URL format. "
            f"Must start with 'postgresql://' or 'sqlite://'"
        )

    return db_url


def get_secret_key(key_name: str = "FLASK_SECRET_KEY") -> str:
    """
    Get secret key with validation

    Args:
        key_name: Name of secret key env variable

    Returns:
        Secret key value

    Raises:
        ConfigError: If secret key is not set or is default value
    """
    secret = get_env(key_name, required=True)

    # Check if it's still the default value
    if "CHANGE-ME" in secret or "change-this" in secret.lower():
        raise ConfigError(
            f"{key_name} is still set to default value. "
            f"Please generate a secure secret key and update your .env file."
        )

    if len(secret) < 32:
        raise ConfigError(
            f"{key_name} is too short (minimum 32 characters). "
            f"Please generate a longer secret key."
        )

    return secret


def validate_configuration():
    """
    Validate all critical configuration values

    Raises:
        ConfigError: If any critical configuration is invalid
    """
    errors = []

    # Check database URL
    try:
        get_database_url()
    except ConfigError as e:
        errors.append(str(e))

    # Check secret keys
    for key in ["FLASK_SECRET_KEY", "JWT_SECRET_KEY"]:
        try:
            get_secret_key(key)
        except ConfigError as e:
            errors.append(str(e))

    if errors:
        error_msg = "\n".join([f"  - {err}" for err in errors])
        raise ConfigError(
            f"Configuration validation failed:\n{error_msg}\n\n"
            f"Please check your .env file and update the required values."
        )


# Configuration values with defaults
class Config:
    """Centralized configuration class"""

    # Database
    DATABASE_URL = get_env("DATABASE_URL")

    # Secret Keys (will validate on access)
    @property
    def FLASK_SECRET_KEY(self):
        return get_secret_key("FLASK_SECRET_KEY")

    @property
    def JWT_SECRET_KEY(self):
        return get_secret_key("JWT_SECRET_KEY")

    @property
    def USER_APP_SECRET_KEY(self):
        return get_env("USER_APP_SECRET_KEY", self.FLASK_SECRET_KEY)

    @property
    def API_SECRET_KEY(self):
        return get_env("API_SECRET_KEY", self.FLASK_SECRET_KEY)

    # Application
    FLASK_ENV = get_env("FLASK_ENV", "production")
    DEBUG = get_env("DEBUG", "False").lower() == "true"

    # API URLs
    API_BASE_URL = get_env("API_BASE_URL", "http://127.0.0.1:5002/api")
    ADMIN_API_URL = get_env("ADMIN_API_URL", "http://127.0.0.1:5111/api")

    # File Uploads
    UPLOAD_FOLDER = get_env("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(get_env("MAX_CONTENT_LENGTH", "16777216"))
    ALLOWED_EXTENSIONS = set(
        get_env("ALLOWED_EXTENSIONS", "csv,xlsx,xls,pdf").split(",")
    )

    # Security
    PASSWORD_MIN_LENGTH = int(get_env("PASSWORD_MIN_LENGTH", "12"))
    PASSWORD_MAX_LENGTH = int(get_env("PASSWORD_MAX_LENGTH", "128"))
    LOGIN_ATTEMPT_LIMIT = int(get_env("LOGIN_ATTEMPT_LIMIT", "5"))
    TOKEN_EXPIRY_HOURS = int(get_env("TOKEN_EXPIRY_HOURS", "24"))
    ACCOUNT_LOCKOUT_MINUTES = int(get_env("ACCOUNT_LOCKOUT_MINUTES", "30"))

    # Email
    MAIL_SERVER = get_env("MAIL_SERVER", "localhost")
    MAIL_PORT = int(get_env("MAIL_PORT", "587"))
    MAIL_USE_TLS = get_env("MAIL_USE_TLS", "True").lower() == "true"
    MAIL_USERNAME = get_env("MAIL_USERNAME")
    MAIL_PASSWORD = get_env("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = get_env("MAIL_DEFAULT_SENDER", "noreply@localhost")

    # Logging
    LOG_LEVEL = get_env("LOG_LEVEL", "INFO")
    LOG_MAX_BYTES = int(get_env("LOG_MAX_BYTES", "10485760"))
    LOG_BACKUP_COUNT = int(get_env("LOG_BACKUP_COUNT", "3"))

    # Session Security
    SESSION_COOKIE_SECURE = get_env("SESSION_COOKIE_SECURE", "False").lower() == "true"
    SESSION_COOKIE_HTTPONLY = (
        get_env("SESSION_COOKIE_HTTPONLY", "True").lower() == "true"
    )
    SESSION_COOKIE_SAMESITE = get_env("SESSION_COOKIE_SAMESITE", "Lax")
    FORCE_HTTPS = get_env("FORCE_HTTPS", "False").lower() == "true"

    # Azure (optional)
    AZURE_SUBSCRIPTION_ID = get_env("AZURE_SUBSCRIPTION_ID")
    AZURE_RESOURCE_GROUP = get_env("AZURE_RESOURCE_GROUP")
    AZURE_LOCATION = get_env("AZURE_LOCATION", "eastus")


# Create singleton instance
config = Config()
