import json
import logging
import time

from django.conf import settings
from django.db import DatabaseError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response

from .errors import PlanningError
from .models import CityCoordinate, FuelStation
from .serializers import PlanRequestSerializer
from .services.planning import plan_route

logger = logging.getLogger(__name__)


@api_view(["GET"])
@throttle_classes([])
def health(request):
    try:
        total = FuelStation.objects.count()
        located = FuelStation.objects.filter(latitude__isnull=False, longitude__isnull=False).count()
        geographic_ready = (
            settings.GEOGRAPHIC_DIR / "us-states.geojson"
        ).exists() and CityCoordinate.objects.exists()
    except DatabaseError:
        return Response(
            {
                "status": "unavailable",
                "ready_to_plan": False,
                "error": {
                    "code": "database_unavailable",
                    "message": "Database is unavailable.",
                    "details": {},
                    "request_id": request.request_id,
                },
            },
            status=503,
        )
    return Response(
        {
            "status": "ok",
            "fuel_dataset_loaded": total > 0,
            "stations_total": total,
            "stations_located": located,
            "stations_unresolved": total - located,
            "geographic_data_ready": geographic_ready,
            "ready_to_plan": located > 0 and geographic_ready,
            "required_action": None
            if located > 0 and geographic_ready
            else "Prepare Census locations and import the private fuel CSV; hosted startup initializes it after secret-file upload.",
        }
    )


@api_view(["POST"])
def route_plan(request):
    serializer = PlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    if settings.ENABLE_FAILURE_DEMO and request.headers.get("X-Demo-Upstream-Failure") == "timeout":
        raise PlanningError("osrm_timeout", "Simulated OSRM timeout for the local demonstration.", 503)
    started = time.perf_counter()
    try:
        result = plan_route(serializer.validated_data)
    except PlanningError:
        raise
    except Exception:
        logger.exception("planning_failed", extra={"request_id": request.request_id})
        return Response(
            {
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "details": {},
                    "request_id": request.request_id,
                }
            },
            status=500,
        )
    logger.info(
        "route_planned",
        extra={
            "request_id": request.request_id,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "candidate_count": result["optimization"]["candidates_evaluated"],
            "stop_count": len(result["fuel_stops"]),
        },
    )
    return Response(result)


@ensure_csrf_cookie
def demo(request):
    return render(request, "fuel_optimizer/demo.html", {"map_tile_url": settings.MAP_TILE_URL})


def docs(request):
    return render(request, "fuel_optimizer/docs.html")


def openapi(request):
    with open(settings.BASE_DIR / "docs" / "openapi.json", encoding="utf-8") as stream:
        return JsonResponse(json.load(stream))
