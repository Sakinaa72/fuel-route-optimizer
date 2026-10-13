from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q

from fuel_optimizer.models import FuelStation

from .route_geometry import distance_miles


@dataclass(frozen=True)
class Candidate:
    station_id: int
    offset: float
    price: Decimal
    distance_from_route: float = 0
    distance_from_origin: float = 0
    station: dict | None = None


def find_candidates(geometry, corridor_miles, origin):
    filters = Q(pk__in=[])
    for min_lon, min_lat, max_lon, max_lat in geometry.database_boxes(corridor_miles):
        filters |= Q(
            latitude__gte=min_lat, latitude__lte=max_lat, longitude__gte=min_lon, longitude__lte=max_lon
        )
    rows = FuelStation.objects.filter(
        filters, retail_price__gt=0, latitude__isnull=False, longitude__isnull=False
    ).values(
        "id",
        "source_truckstop_id",
        "name",
        "address",
        "city",
        "state",
        "latitude",
        "longitude",
        "coordinate_source",
        "coordinate_reference",
        "retail_price",
    )
    candidates = []
    for row in rows.iterator(chunk_size=1000):
        projection = geometry.project(row["longitude"], row["latitude"], corridor_miles)
        if projection:
            candidates.append(
                Candidate(
                    row["id"],
                    projection.route_offset_miles,
                    row["retail_price"],
                    projection.distance_from_route_miles,
                    distance_miles(
                        (origin["longitude"], origin["latitude"]), (row["longitude"], row["latitude"])
                    ),
                    row,
                )
            )
    return sorted(candidates, key=lambda c: (c.offset, c.price, c.station_id))
