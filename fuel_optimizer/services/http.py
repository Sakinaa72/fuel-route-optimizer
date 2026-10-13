import httpx
from django.conf import settings

from fuel_optimizer.errors import PlanningError


def get_json(url, *, provider, params=None, headers=None):
    timeout = httpx.Timeout(settings.HTTP_READ_TIMEOUT, connect=settings.HTTP_CONNECT_TIMEOUT)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException as exc:
        raise PlanningError(
            f"{provider}_timeout", f"{provider.upper()} timed out. Try again later.", 503
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise PlanningError(
            f"{provider}_http_error", f"{provider.upper()} returned an upstream error.", 502
        ) from exc
    except (httpx.RequestError, ValueError) as exc:
        raise PlanningError(
            f"{provider}_unavailable", f"{provider.upper()} is unavailable or returned invalid JSON.", 502
        ) from exc
