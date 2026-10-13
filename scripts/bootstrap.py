"""Safe initialization before Gunicorn; no credentials or private CSV data in logs."""

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


@contextmanager
def deployment_lock(connection):
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(731946102)")
        try:
            yield
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(731946102)")
    else:
        yield


def main():
    try:
        import django

        django.setup()
        from django.conf import settings
        from django.core.management import call_command
        from django.db import connection

        with deployment_lock(connection):
            call_command("migrate", interactive=False, verbosity=0)
            if settings.AUTO_INITIALIZE_DATA:
                call_command("initialize_deployment")
        print(json.dumps({"event": "startup_ready"}))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "event": "startup_failed",
                    "exception_type": type(exc).__name__,
                    "message": "Initialization failed. Check database connectivity and runtime configuration.",
                }
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
