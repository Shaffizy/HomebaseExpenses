import pytest
from django.core.exceptions import ImproperlyConfigured
from .database import database_settings


def environment(values):
    def get(name, default=None, cast=None):
        value = values.get(name, default)
        if cast is bool:
            return str(value).lower() in {"1", "true", "yes"}
        return cast(value) if cast else value
    return get


def test_postgresql_rollback_defaults():
    settings = database_settings(environment({}))
    assert settings["ENGINE"] == "django.db.backends.postgresql"
    assert settings["PORT"] == "5433"
    assert "OPTIONS" not in settings


def test_sqlserver_windows_auth_and_certificate_validation():
    settings = database_settings(environment({"DB_ENGINE": "mssql"}))
    assert settings["USER"] == settings["PASSWORD"] == settings["PORT"] == ""
    assert settings["OPTIONS"]["python_driver"] == "mssql_python"
    assert "Encrypt=yes;TrustServerCertificate=no" == settings["OPTIONS"]["extra_params"]


def test_local_sqlserver_certificate_exception_is_explicit():
    settings = database_settings(environment({"DB_ENGINE": "mssql", "DB_TRUST_SERVER_CERTIFICATE": "True"}))
    assert "TrustServerCertificate=yes" in settings["OPTIONS"]["extra_params"]


def test_unexpected_database_engine_is_rejected():
    with pytest.raises(ImproperlyConfigured):
        database_settings(environment({"DB_ENGINE": "arbitrary.module"}))
