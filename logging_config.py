"""
Structured Logging Configuration for RFPO Application

Provides centralized logging setup with proper formatting, rotation,
and level configuration.
"""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime
from env_config import Config


def setup_logging(app_name: str = "rfpo", log_to_file: bool = True):
    """
    Configure structured logging for the application

    Args:
        app_name: Name of the application (used in log file naming)
        log_to_file: Whether to write logs to file (default: True)

    Returns:
        Configured logger instance
    """
    config = Config()

    # Get log level from config (default: INFO)
    log_level_str = config.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Create logger
    logger = logging.getLogger(app_name)
    logger.setLevel(log_level)

    # Prevent duplicate handlers
    if logger.handlers:
        logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "[%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_formatter = logging.Formatter("%(levelname)s: %(message)s")

    # Console Handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File Handler with rotation (if enabled)
    if log_to_file:
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Log file path with timestamp
        log_file = log_dir / f"{app_name}.log"

        # Rotating file handler (10MB max, 5 backups)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=config.LOG_MAX_BYTES, backupCount=config.LOG_BACKUP_COUNT
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

    # Log startup message
    logger.info(f"Logging initialized for {app_name} at level {log_level_str}")

    return logger


def get_logger(name: str = None):
    """
    Get or create a logger instance

    Args:
        name: Logger name (default: 'rfpo')

    Returns:
        Logger instance
    """
    if name is None:
        name = "rfpo"

    logger = logging.getLogger(name)

    # If logger has no handlers, set it up
    if not logger.handlers:
        logger = setup_logging(name)

    return logger


def log_exception(logger, exc: Exception, context: dict = None):
    """
    Log exception with context information

    Args:
        logger: Logger instance
        exc: Exception to log
        context: Additional context (dict)
    """
    context = context or {}

    error_msg = f"{exc.__class__.__name__}: {str(exc)}"

    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        error_msg = f"{error_msg} | Context: {context_str}"

    logger.error(error_msg, exc_info=True)


def log_api_request(
    logger, method: str, endpoint: str, user_id: str = None, status_code: int = None
):
    """
    Log API request with standardized format

    Args:
        logger: Logger instance
        method: HTTP method (GET, POST, etc.)
        endpoint: API endpoint path
        user_id: User ID making request (optional)
        status_code: Response status code (optional)
    """
    user_part = f"User: {user_id}" if user_id else "User: Anonymous"
    status_part = f"Status: {status_code}" if status_code else ""

    logger.info(f"{method} {endpoint} | {user_part} | {status_part}".strip())


def log_database_operation(
    logger, operation: str, table: str, record_id: str = None, success: bool = True
):
    """
    Log database operation with standardized format

    Args:
        logger: Logger instance
        operation: Operation type (INSERT, UPDATE, DELETE, SELECT)
        table: Database table name
        record_id: Record identifier (optional)
        success: Whether operation succeeded
    """
    status = "SUCCESS" if success else "FAILED"
    record_part = f"ID: {record_id}" if record_id else ""

    msg = f"DB {operation} on {table} | {record_part} | {status}".strip()

    if success:
        logger.debug(msg)
    else:
        logger.error(msg)


def log_authentication(logger, email: str, success: bool, reason: str = None):
    """
    Log authentication attempt

    Args:
        logger: Logger instance
        email: User email
        success: Whether authentication succeeded
        reason: Failure reason (optional)
    """
    status = "SUCCESS" if success else "FAILED"
    reason_part = f"Reason: {reason}" if reason else ""

    msg = f"Authentication {status} for {email} | {reason_part}".strip()

    if success:
        logger.info(msg)
    else:
        logger.warning(msg)


def log_authorization(logger, user_id: str, resource: str, action: str, success: bool):
    """
    Log authorization check

    Args:
        logger: Logger instance
        user_id: User ID
        resource: Resource being accessed
        action: Action being performed
        success: Whether authorized
    """
    status = "AUTHORIZED" if success else "DENIED"
    msg = f"Authorization {status} | User: {user_id} | "
    msg += f"Resource: {resource} | Action: {action}"

    if success:
        logger.debug(msg)
    else:
        logger.warning(msg)
