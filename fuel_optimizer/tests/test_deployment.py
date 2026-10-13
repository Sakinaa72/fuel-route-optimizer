import io
import json
import logging
import runpy
from pathlib import Path
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.db import OperationalError

from config.database import database_config
from fuel_optimizer.logging import JsonFormatter
from fuel_optimizer.models import FuelStation


def test_postgres_database_url_and_timeouts(tmp_path):
    database = database_config(
        tmp_path, {"DATABASE_URL": "postgresql://tester:synthetic%40password@db:5432/fuel?sslmode=require"}
    )
    assert database["ENGINE"] == "django.db.backends.postgresql"
    assert database["NAME"] == "fuel" and database["PASSWORD"] == "synthetic@password"
    assert database["OPTIONS"]["sslmode"] == "require"
    assert database["OPTIONS"]["connect_timeout"] == 10
    assert database["CONN_HEALTH_CHECKS"]


def test_local_sqlite_preserved_and_render_requires_postgres(tmp_path):
    database = database_config(tmp_path, {})
    assert database["ENGINE"] == "django.db.backends.sqlite3"
    assert database["NAME"] == tmp_path / "var/db.sqlite3"
    with pytest.raises(RuntimeError, match="required on Render"):
        database_config(tmp_path, {"RENDER": "true"})


@pytest.mark.parametrize("url", ["mysql://private:synthetic-secret@host/db", "not-a-valid-url"])
def test_invalid_database_configuration_is_sanitized(tmp_path, url):
    with pytest.raises(RuntimeError) as error:
        database_config(tmp_path, {"DATABASE_URL": url})
    assert url not in str(error.value) and "synthetic-secret" not in str(error.value)


def test_gunicorn_uses_platform_port_and_graceful_shutdown(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    config = runpy.run_path("config/gunicorn.py")
    assert config["bind"] == "0.0.0.0:10000"
    assert config["graceful_timeout"] < 30


def test_production_logs_omit_exception_values_and_tracebacks(settings):
    settings.DEBUG = False
    try:
        raise RuntimeError("private-token-and-filesystem-path")
    except RuntimeError:
        import sys

        record = logging.LogRecord("test", logging.ERROR, __file__, 1, "planning_failed", (), sys.exc_info())
    output = JsonFormatter().format(record)
    assert json.loads(output)["exception_type"] == "RuntimeError"
    assert "private-token" not in output and "Traceback" not in output


@pytest.mark.django_db
def test_initializer_preserves_populated_database_without_csv(places, station_factory, settings):
    old = station_factory()
    settings.FUEL_PRICES_CSV = Path("/missing/private.csv")
    output = io.StringIO()
    call_command("initialize_deployment", stdout=output)
    assert FuelStation.objects.get().pk == old.pk
    assert "fuel_data_preserved" in output.getvalue()


@pytest.mark.django_db
def test_initializer_missing_csv_is_actionable_and_not_fabricated(places, settings):
    settings.FUEL_PRICES_CSV = Path("/missing/private.csv")
    output = io.StringIO()
    call_command("initialize_deployment", stdout=output)
    assert not FuelStation.objects.exists()
    assert "runtime secret file" in output.getvalue()


@pytest.mark.django_db
def test_initializer_imports_empty_database_once(places, settings, tmp_path):
    from fuel_optimizer.tests.test_import import write_csv

    path = write_csv(
        tmp_path,
        [["7", "Synthetic initialization fixture", "Fixture road", "Austin", "TX", "", "3.12345678"]],
    )
    settings.FUEL_PRICES_CSV = path
    call_command("initialize_deployment", stdout=io.StringIO())
    old = FuelStation.objects.get()
    call_command("initialize_deployment", stdout=io.StringIO())
    assert FuelStation.objects.count() == 1 and FuelStation.objects.get().pk == old.pk


@pytest.mark.django_db
def test_health_reports_database_failure_without_leaking_details(api_client, monkeypatch):
    monkeypatch.setattr(
        FuelStation.objects, "count", Mock(side_effect=OperationalError("private-host-password"))
    )
    response = api_client.get("/api/v1/health/")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "private-host-password" not in response.content.decode()


@pytest.mark.django_db
def test_swagger_uses_current_host_and_initialization_asset(api_client):
    schema = api_client.get("/openapi.json").json()
    assert schema["servers"][0]["url"] == "/"
    page = api_client.get("/docs/")
    assert b'id="swagger-ui"' in page.content and b"swagger-init.js" in page.content
