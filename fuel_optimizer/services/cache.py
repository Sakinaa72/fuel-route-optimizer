import hashlib
import json
from contextlib import contextmanager

from django.conf import settings
from filelock import FileLock, Timeout

from fuel_optimizer.errors import PlanningError


def cache_key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@contextmanager
def request_lock(name):
    directory = settings.VAR_DIR / "locks"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(directory / f"{name}.lock"), timeout=30):
            yield
    except Timeout as exc:
        raise PlanningError(
            "provider_busy", "Another provider request is in progress. Try again shortly.", 503
        ) from exc
