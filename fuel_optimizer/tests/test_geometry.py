import pytest

from fuel_optimizer.errors import PlanningError
from fuel_optimizer.services.route_geometry import GEOD, RouteGeometry, distance_miles


def test_wgs84_cumulative_distances_and_coordinate_order():
    coordinates = [[-100, 35], [-99, 35], [-98, 35]]
    total = sum(distance_miles(a, b) for a, b in zip(coordinates, coordinates[1:]))
    route = RouteGeometry(coordinates, total)
    assert route.cumulative_miles[-1] == pytest.approx(total, rel=1e-8)
    assert total == pytest.approx(113.45, abs=0.2)
    projected = route.project(-99, 35, 20)
    assert projected.route_offset_miles == pytest.approx(total / 2, abs=0.001)
    assert projected.distance_from_route_miles < 0.0001
    assert route.project(35, -99, 20) is None


def test_perpendicular_and_corridor_filter():
    route = RouteGeometry([[-100, 35], [-98, 35]], distance_miles((-100, 35), (-98, 35)))
    station_lon, station_lat, _ = GEOD.fwd(-99, 35.0041, 0, 10 * 1609.344)
    projected = route.project(station_lon, station_lat, 20)
    assert projected.distance_from_route_miles == pytest.approx(10, abs=0.1)
    assert route.project(station_lon, station_lat, 9.5) is None


def test_segment_boundary_and_repeated_vertices():
    route = RouteGeometry([[-100, 35], [-99, 35], [-99, 35], [-99, 36]], 130)
    projection = route.project(-99, 35, 20)
    assert projection.distance_from_route_miles < 1e-5
    assert 0 < projection.route_offset_miles < 130


def test_offsets_scaled_to_provider_road_distance():
    route = RouteGeometry([[-100, 35], [-98, 35]], 120)
    assert route.project(-98, 35, 1).route_offset_miles == pytest.approx(120)


def test_alaska_dateline_index():
    coordinates = [[179, 52], [-179, 52]]
    route = RouteGeometry(coordinates, distance_miles(*coordinates))
    assert route.project(-179.5, 52, 10) is not None
    assert any(bounds[0] <= -179.5 <= bounds[2] for bounds in route.database_boxes(10))


def test_invalid_geometry_distance():
    with pytest.raises(PlanningError):
        RouteGeometry([[-100, 35], [-100, 35]], 50)
    with pytest.raises(PlanningError):
        RouteGeometry([[-100, 35], [-99, 35]], 5000)


@pytest.mark.django_db
def test_matching_filters_outside_corridor_and_keeps_distinct_ids(station_factory):
    from fuel_optimizer.services.station_matching import find_candidates

    station_factory(1, latitude=35, longitude=-99)
    station_factory(2, price="3.1", latitude=35, longitude=-99)
    station_factory(3, latitude=40, longitude=-99)
    route = RouteGeometry([[-100, 35], [-98, 35]], 120)
    candidates = find_candidates(route, 20, {"longitude": -100, "latitude": 35})
    assert len(candidates) == 2 and candidates[0].price < candidates[1].price
