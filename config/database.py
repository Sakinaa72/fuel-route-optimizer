"""SQLite locally; an explicitly configured PostgreSQL URL for hosted deployments."""

from pathlib import Path

import dj_database_url


def database_config(base_dir, environment):
    url = environment.get("DATABASE_URL", "").strip()
    if url:
        try:
            database = dj_database_url.parse(url, conn_max_age=60, conn_health_checks=True)
            if database["ENGINE"] != "django.db.backends.postgresql":
                raise ValueError("Unsupported database URL")
            database.setdefault("OPTIONS", {}).setdefault("connect_timeout", 10)
            database["OPTIONS"].setdefault("options", "-c statement_timeout=60000")
            return database
        except (ValueError, KeyError) as exc:
            raise RuntimeError("DATABASE_URL must be a valid PostgreSQL connection URL.") from exc
    if environment.get("RENDER", "").lower() == "true":
        raise RuntimeError("DATABASE_URL is required on Render; ephemeral SQLite is not permitted.")
    path = Path(environment.get("DATABASE_PATH", "var/db.sqlite3"))
    if not path.is_absolute():
        path = base_dir / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return {"ENGINE": "django.db.backends.sqlite3", "NAME": path, "OPTIONS": {"timeout": 20}}
