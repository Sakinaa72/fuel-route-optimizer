"""Exact DAG shortest path for the documented outgoing-segment price model."""

import math
from bisect import bisect_left
from dataclasses import dataclass

from fuel_optimizer.errors import PlanningError

from .station_matching import Candidate


@dataclass(frozen=True)
class Leg:
    start_offset: float
    end_offset: float
    source: Candidate

    @property
    def distance(self):
        return self.end_offset - self.start_offset


@dataclass(frozen=True)
class Plan:
    legs: list[Leg]
    departure_source: Candidate
    candidates_evaluated: int


def optimize(distance, candidates, max_range=500, mpg=10, departure_radius=20):
    if not (math.isfinite(distance) and distance > 0 and max_range > 0 and mpg > 0):
        raise ValueError("Distance, range and MPG must be positive")
    sources = [
        c for c in candidates if c.distance_from_origin <= departure_radius and c.offset <= departure_radius
    ]
    if not sources:
        raise PlanningError(
            "departure_price_unavailable",
            "No imported, located price is available near departure; trip fuel cost cannot be estimated.",
            422,
        )
    departure = min(sources, key=lambda c: (c.price, c.distance_from_origin, c.station_id))
    # Only exact offset ties are collapsed; retain all distinct records in the DB.
    # A more expensive price at precisely the same modeled position is dominated.
    by_offset = {}
    for candidate in candidates:
        if 1e-8 < candidate.offset < distance - 1e-8:
            current = by_offset.get(candidate.offset)
            if current is None or (candidate.price, candidate.station_id) < (
                current.price,
                current.station_id,
            ):
                by_offset[candidate.offset] = candidate
    stations = sorted(by_offset.values(), key=lambda c: (c.offset, c.station_id))
    offsets = [0.0] + [c.offset for c in stations] + [distance]
    prices = [float(departure.price)] + [float(c.price) for c in stations]
    count = len(offsets)
    costs, hops, previous = [math.inf] * count, [count] * count, [-1] * count
    costs[0], hops[0] = 0.0, 0
    for end in range(1, count):
        first = bisect_left(offsets, offsets[end] - max_range - 1e-8, 0, end)
        for start in range(first, end):
            if math.isinf(costs[start]):
                continue
            value = costs[start] + (offsets[end] - offsets[start]) / mpg * prices[start]
            new_hops = hops[start] + 1
            if value < costs[end] - 1e-9 or (abs(value - costs[end]) <= 1e-9 and new_hops < hops[end]):
                costs[end], hops[end], previous[end] = value, new_hops, start
    if previous[-1] == -1:
        raise PlanningError(
            "no_feasible_refueling_plan",
            "The located stations in this route corridor leave a gap longer than the vehicle range.",
            422,
            {"max_range_miles": max_range, "candidates_evaluated": len(candidates)},
        )
    edges = []
    end = count - 1
    while end:
        start = previous[end]
        source = departure if start == 0 else stations[start - 1]
        edges.append(Leg(offsets[start], offsets[end], source))
        end = start
    return Plan(list(reversed(edges)), departure, len(candidates))
