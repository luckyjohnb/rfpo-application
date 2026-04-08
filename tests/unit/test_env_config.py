"""
Unit Tests — env_config module.

Covers get_env, get_database_url, get_secret_key, ConfigError.
"""

import os
import pytest
from unittest.mock import patch

from env_config import get_env, get_database_url, get_secret_key, ConfigError

pytestmark = pytest.mark.unit


class TestGetEnv:
    def test_returns_default(self):
        val = get_env("NONEXISTENT_VAR_12345", default="fallback")
        assert val == "fallback"

    def test_required_raises(self):
        with pytest.raises(ConfigError, match="Required"):
            get_env("NONEXISTENT_VAR_12345", required=True)

    def test_reads_env(self):
        with patch.dict(os.environ, {"TEST_VAR_XYZ": "hello"}):
            assert get_env("TEST_VAR_XYZ") == "hello"


class TestGetDatabaseUrl:
    def test_valid_postgresql(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pw@host:5432/db"}):
            url = get_database_url()
            assert url.startswith("postgresql://")

    def test_valid_sqlite(self):
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///test.db"}):
            url = get_database_url()
            assert url.startswith("sqlite://")

    def test_invalid_format(self):
        with patch.dict(os.environ, {"DATABASE_URL": "mysql://bad"}):
            with pytest.raises(ConfigError, match="Invalid"):
                get_database_url()


class TestGetSecretKey:
    def test_valid_key(self):
        long_key = "a" * 32
        with patch.dict(os.environ, {"FLASK_SECRET_KEY": long_key}):
            assert get_secret_key("FLASK_SECRET_KEY") == long_key

    def test_too_short(self):
        with patch.dict(os.environ, {"FLASK_SECRET_KEY": "short"}):
            with pytest.raises(ConfigError, match="too short"):
                get_secret_key("FLASK_SECRET_KEY")

    def test_default_value_rejected(self):
        with patch.dict(os.environ, {"FLASK_SECRET_KEY": "CHANGE-ME-to-something-secure-and-long-enough"}):
            with pytest.raises(ConfigError, match="default"):
                get_secret_key("FLASK_SECRET_KEY")
