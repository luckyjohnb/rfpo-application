"""
Unit Tests — Exception hierarchy.

Verifies status codes, to_dict(), and payload handling.
"""

import pytest
from exceptions import (
    RFPOException,
    AuthenticationException,
    AuthorizationException,
    ValidationException,
    ResourceNotFoundException,
    DatabaseException,
    ConfigurationException,
    FileProcessingException,
    ExternalServiceException,
    BusinessLogicException,
)

pytestmark = pytest.mark.unit


class TestExceptions:
    @pytest.mark.parametrize("exc_cls,expected_code", [
        (RFPOException, 500),
        (DatabaseException, 500),
        (AuthenticationException, 401),
        (AuthorizationException, 403),
        (ValidationException, 400),
        (ResourceNotFoundException, 404),
        (ConfigurationException, 500),
        (FileProcessingException, 400),
        (ExternalServiceException, 503),
        (BusinessLogicException, 422),
    ])
    def test_status_codes(self, exc_cls, expected_code):
        e = exc_cls("test")
        assert e.status_code == expected_code

    def test_to_dict(self):
        e = ValidationException("bad input", payload={"field": "email"})
        d = e.to_dict()
        assert d["message"] == "bad input"
        assert d["field"] == "email"

    def test_to_dict_no_payload(self):
        e = AuthenticationException("denied")
        d = e.to_dict()
        assert d["message"] == "denied"

    def test_exception_str(self):
        e = ResourceNotFoundException("RFPO not found")
        assert str(e) == "RFPO not found"
