"""
Custom Exception Classes for RFPO Application

This module defines a hierarchy of custom exceptions for better error handling
and logging throughout the application.
"""


class RFPOException(Exception):
    """
    Base exception class for all RFPO application errors.

    All custom exceptions should inherit from this class to allow
    for unified exception handling.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code (default: 500)
        payload: Additional error context (dict)
    """

    def __init__(self, message: str, status_code: int = 500, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}

    def to_dict(self):
        """Convert exception to dictionary for JSON serialization"""
        rv = dict(self.payload or {})
        rv["message"] = self.message
        rv["error_type"] = self.__class__.__name__
        return rv


class DatabaseException(RFPOException):
    """
    Database-related errors (connection failures, query errors, etc.)

    Examples:
        - Connection timeout
        - Query execution failure
        - Schema mismatch
        - Data integrity violations
    """

    def __init__(self, message: str, status_code: int = 500, payload=None):
        super().__init__(message, status_code, payload)


class AuthenticationException(RFPOException):
    """
    Authentication failures (invalid credentials, expired tokens, etc.)

    Examples:
        - Invalid username/password
        - Expired JWT token
        - Missing authentication headers
        - Invalid token signature
    """

    def __init__(self, message: str, status_code: int = 401, payload=None):
        super().__init__(message, status_code, payload)


class AuthorizationException(RFPOException):
    """
    Authorization failures (insufficient permissions, access denied, etc.)

    Examples:
        - User lacks required permission
        - Attempting to access another user's data
        - Team membership required
        - Admin privileges required
    """

    def __init__(self, message: str, status_code: int = 403, payload=None):
        super().__init__(message, status_code, payload)


class ValidationException(RFPOException):
    """
    Data validation errors (invalid input, missing required fields, etc.)

    Examples:
        - Missing required field
        - Invalid email format
        - Password too weak
        - Invalid date range
    """

    def __init__(self, message: str, status_code: int = 400, payload=None):
        super().__init__(message, status_code, payload)


class ResourceNotFoundException(RFPOException):
    """
    Resource not found errors (RFPO, user, team not found, etc.)

    Examples:
        - RFPO ID doesn't exist
        - User not found
        - Team not found
        - Consortium not found
    """

    def __init__(self, message: str, status_code: int = 404, payload=None):
        super().__init__(message, status_code, payload)


class ConfigurationException(RFPOException):
    """
    Configuration errors (missing env vars, invalid config values, etc.)

    Examples:
        - Missing DATABASE_URL
        - Invalid secret key
        - Missing required configuration
        - Invalid configuration format
    """

    def __init__(self, message: str, status_code: int = 500, payload=None):
        super().__init__(message, status_code, payload)


class FileProcessingException(RFPOException):
    """
    File upload/processing errors (invalid format, size exceeded, etc.)

    Examples:
        - File too large
        - Invalid file format
        - Corrupted file
        - Upload failed
    """

    def __init__(self, message: str, status_code: int = 400, payload=None):
        super().__init__(message, status_code, payload)


class ExternalServiceException(RFPOException):
    """
    External service failures (email service, API calls, etc.)

    Examples:
        - Email send failure
        - Third-party API timeout
        - External service unavailable
    """

    def __init__(self, message: str, status_code: int = 503, payload=None):
        super().__init__(message, status_code, payload)


class BusinessLogicException(RFPOException):
    """
    Business rule violations (approval workflow, budget exceeded, etc.)

    Examples:
        - Budget limit exceeded
        - Approval already submitted
        - Duplicate RFPO number
        - Invalid workflow transition
    """

    def __init__(self, message: str, status_code: int = 422, payload=None):
        super().__init__(message, status_code, payload)
