"""Environment-driven database settings with a PostgreSQL rollback path."""
from django.core.exceptions import ImproperlyConfigured


def database_settings(config):
    engine = config("DB_ENGINE", default="django.db.backends.postgresql")
    if engine not in {"mssql", "django.db.backends.postgresql"}:
        raise ImproperlyConfigured("DB_ENGINE must be mssql or django.db.backends.postgresql")
    sqlserver = engine == "mssql"
    database = {
        "ENGINE": engine,
        "NAME": config("DB_NAME", default="homebase_expenses_mssql" if sqlserver else "homebase_expenses"),
        "USER": config("DB_USER", default="" if sqlserver else "homebase_expenses_app"),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default="localhost" if sqlserver else "127.0.0.1"),
        "PORT": config("DB_PORT", default="" if sqlserver else "5433"),
    }
    if sqlserver:
        trust = config("DB_TRUST_SERVER_CERTIFICATE", default=False, cast=bool)
        database["OPTIONS"] = {
            "python_driver": "mssql_python",
            "extra_params": "Encrypt=yes;TrustServerCertificate=" + ("yes" if trust else "no"),
            "connection_timeout": 10,
            "connection_retries": 0,
        }
    return database
