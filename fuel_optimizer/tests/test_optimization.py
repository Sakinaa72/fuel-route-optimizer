import itertools
import random
from decimal import Decimal

import pytest

from fuel_optimizer.errors import PlanningError
from fuel_optimizer.services.cost_calculation import leg_cost, summarize
from fuel_optimizer.services.optimization import optimize
from fuel_optimizer.services.station_matching import Candidate


def candidate(index, offset, price, from_origin=None):
    row = {
        "source_truckstop_id": str(index),
        "name": f"Synthetic {index}",
        "address": "Fixture",
        "city": "Fixture",
        "state": "TX",
        "latitude": 35,
        "longitude": -100,
        "coordinate_source": "city_centroid_approximation",
        "coordinate_reference": "test",
    }
    return Candidate(
        index, offset, Decimal(str(price)), 0, offset if from_origin is None else from_origin, row
    )


def sources(plan):
    return [leg.source.station_id for leg in plan.legs]


def cost(plan, mpg=10):
    return sum(leg_cost(leg.distance, mpg, leg.source.price) for leg in plan.legs)


def test_short_route_no_stop_includes_departure_and_last_leg():
    plan = optimize(200, [candidate(1, 0, 3)])
    assert sources(plan) == [1]
    assert cost(plan) == Decimal("60.00")


def test_exact_one_stop():
    plan = optimize(800, [candidate(1, 0, 3), candidate(2, 400, 4)])
    assert sources(plan) == [1, 2]
    assert cost(plan) == Decimal("280.00")


def test_multiple_required_stops():
    plan = optimize(1300, [candidate(1, 0, 4), candidate(2, 400, 3), candidate(3, 800, 5)])
    assert sources(plan) == [1, 2, 3]
    assert all(leg.distance <= 500 for leg in plan.legs)
    assert cost(plan) == Decimal("530.00")


def test_cheaper_reachable_station_wins_even_on_short_trip():
    plan = optimize(400, [candidate(1, 0, 5), candidate(2, 100, 2)])
    assert sources(plan) == [1, 2]
    assert cost(plan) == Decimal("110.00")


def test_unreachable_cheapest_requires_expensive_bridge():
    plan = optimize(1100, [candidate(1, 0, 4), candidate(2, 400, 6), candidate(3, 700, 1)])
    assert sources(plan) == [1, 2, 3]
    assert cost(plan) == Decimal("380.00")


def test_global_cheapest_is_not_feasible_on_its_own():
    with pytest.raises(PlanningError, match="gap") as error:
        optimize(1000, [candidate(1, 0, 4), candidate(2, 600, 1)])
    assert error.value.error_code == "no_feasible_refueling_plan"


def test_lowest_cost_sequence_beats_fewer_expensive_stops():
    plan = optimize(
        900, [candidate(1, 0, 4), candidate(2, 300, 2), candidate(3, 450, 6), candidate(4, 700, 3)]
    )
    assert sources(plan) == [1, 2, 4]
    assert cost(plan) == Decimal("260.00")


def test_empty_candidates_and_missing_departure_price():
    for stations in ([], [candidate(1, 200, 3)]):
        with pytest.raises(PlanningError) as error:
            optimize(200, stations)
        assert error.value.error_code == "departure_price_unavailable"


def test_gap_in_middle():
    with pytest.raises(PlanningError):
        optimize(
            1700, [candidate(1, 0, 3), candidate(2, 400, 4), candidate(3, 1000, 2), candidate(4, 1400, 4)]
        )


def test_duplicate_positions_and_equal_prices_tie_break():
    plan = optimize(
        900, [candidate(1, 0, 4), candidate(2, 400, 5), candidate(3, 400, 3), candidate(4, 450, 3)]
    )
    assert sources(plan) == [1, 3]
    flat = optimize(400, [candidate(1, 0, 3), candidate(2, 100, 3), candidate(3, 200, 3)])
    assert len(flat.legs) == 1


def test_range_boundary_inclusive_and_just_outside():
    assert len(optimize(1000, [candidate(1, 0, 3), candidate(2, 500, 4)]).legs) == 2
    with pytest.raises(PlanningError):
        optimize(1000.01, [candidate(1, 0, 3), candidate(2, 500, 4)])


def test_summary_cost_is_sum_of_all_leg_costs():
    plan = optimize(800.33, [candidate(1, 0, "3.1234"), candidate(2, 400.12, "4.5678")])
    summary, stops = summarize(plan, 800.33, 10)
    assert Decimal(str(summary["estimated_total_fuel_cost_usd"])) == sum(
        Decimal(str(leg["cost_usd"])) for leg in summary["legs"]
    )
    assert stops[0]["estimated_leg_cost_usd"] == summary["legs"][1]["cost_usd"]
    assert summary["total_fuel_consumed_gallons"] == 80.033


def test_full_precision_imported_prices_include_departure_and_destination_costs():
    plan = optimize(620, [candidate(1, 0, "3.12345678"), candidate(2, 500, "4.23456789")])
    summary, stops = summarize(plan, 620, 10)
    # Hand calculation: 50 * 3.12345678 = 156.172839, rounded to 156.17;
    # 12 * 4.23456789 = 50.81481468, rounded to 50.81.
    assert summary["departure_fuel_value_usd"] == 156.17
    assert stops[0]["estimated_leg_cost_usd"] == 50.81
    assert summary["estimated_total_fuel_cost_usd"] == 206.98
    assert summary["total_fuel_consumed_gallons"] == 62


def test_random_small_graphs_match_exhaustive_path_oracle():
    rng = random.Random(100)
    for _ in range(60):
        offsets = sorted(rng.sample(range(30, 890), 6))
        stations = [candidate(1, 0, rng.randint(2, 6))] + [
            candidate(i + 2, x, rng.randint(1, 6)) for i, x in enumerate(offsets)
        ]
        best = float("inf")
        for selected in itertools.chain.from_iterable(
            itertools.combinations(stations[1:], n) for n in range(7)
        ):
            nodes = [stations[0], *selected]
            ends = [c.offset for c in nodes[1:]] + [900]
            if all(end - start.offset <= 500 for start, end in zip(nodes, ends)):
                best = min(
                    best,
                    sum((end - start.offset) / 10 * float(start.price) for start, end in zip(nodes, ends)),
                )
        if best == float("inf"):
            with pytest.raises(PlanningError):
                optimize(900, stations)
        else:
            plan = optimize(900, stations)
            unrounded = sum(leg.distance / 10 * float(leg.source.price) for leg in plan.legs)
            assert unrounded == pytest.approx(best, abs=1e-8)
