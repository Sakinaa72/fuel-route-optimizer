import csv
import io
import json
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from fuel_optimizer.management.commands.load_fuel_prices import COLUMNS
from fuel_optimizer.models import CityCoordinate, FuelStation
from fuel_optimizer.services.locations import normalize_city, normalize_place_city, normalize_state

pytestmark = pytest.mark.django_db


def write_csv(tmp_path, rows, columns=COLUMNS):
    path = tmp_path / "prices.csv"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)
    return path


def load(path, tmp_path, **kwargs):
    output = io.StringIO()
    call_command(
        "load_fuel_prices",
        csv=str(path),
        unresolved_report=str(tmp_path / "unresolved.csv"),
        stdout=output,
        **kwargs,
    )
    return json.loads(output.getvalue())


def test_duplicate_source_ids_preserve_distinct_prices_and_records(places, tmp_path):
    rows = [
        ["42", "Test One", "1 First", "Austin", "TX", "9", "3.25"],
        ["42", "Test Two", "2 Second", "Dallas", "TX", "9", "3.50"],
        ["42", "Test One", "1 First", "Austin", "TX", "9", "3.2500"],
        ["42", "Test One", "1 First", "Austin", "TX", "9", "3.35"],
    ]
    path = write_csv(tmp_path, rows)
    result = load(path, tmp_path)
    assert (result["loaded"], result["duplicate"], result["located"]) == (3, 1, 3)
    assert FuelStation.objects.count() == 3
    again = load(path, tmp_path)
    assert again["loaded"] == 0 and again["skipped"] == 3
    assert FuelStation.objects.get(name="Test Two").latitude == 32.7767


@pytest.mark.parametrize("price", ["NaN", "Infinity", "-1", "0", "abc", "100.001", "3.123456789"])
def test_invalid_price_rolls_back(places, station_factory, tmp_path, price):
    old = station_factory()
    path = write_csv(tmp_path, [["5", "Bad", "1 Road", "Austin", "TX", "", price]])
    with pytest.raises(CommandError, match="aborted"):
        load(path, tmp_path)
    assert FuelStation.objects.get(pk=old.pk).name == old.name


def test_column_validation_preserves_existing(places, station_factory, tmp_path):
    station_factory()
    path = write_csv(tmp_path, [], columns=["City", "price"])
    with pytest.raises(CommandError, match="columns"):
        load(path, tmp_path)
    assert FuelStation.objects.count() == 1


def test_unresolved_and_ambiguous_places_are_reported(places, tmp_path):
    CityCoordinate.objects.create(
        geoid="duplicate", city="Austin CDP", normalized_city="austin", state="TX", latitude=30, longitude=-97
    )
    path = write_csv(
        tmp_path,
        [
            ["1", "Test", "1 Road", "Unknownville", "TX", "", "3.5"],
            ["2", "Test", "2 Road", "Austin", "TX", "", "3.5"],
        ],
    )
    result = load(path, tmp_path)
    assert result["unresolved"] == 2
    assert all(s.latitude is None for s in FuelStation.objects.all())
    report = (tmp_path / "unresolved.csv").read_text()
    assert "ambiguous_place" in report and "no_place_match" in report


def test_successful_snapshot_removes_only_stale_rows(places, station_factory, tmp_path):
    station_factory()
    path = write_csv(tmp_path, [["2", "Test", "2 Road", "Austin", "Texas", "", "$3.5"]])
    result = load(path, tmp_path)
    assert result["removed"] == 1 and FuelStation.objects.count() == 1


def test_skip_invalid_is_non_destructive_merge(places, station_factory, tmp_path):
    station_factory()
    path = write_csv(
        tmp_path,
        [
            ["2", "Test", "2 Road", "Austin", "TX", "", "3.5"],
            ["3", "Bad", "3 Road", "Austin", "TX", "", "bad"],
        ],
    )
    result = load(path, tmp_path, skip_invalid=True)
    assert result["invalid"] == 1 and FuelStation.objects.count() == 2


def test_reimport_updates_coordinates(places, tmp_path):
    path = write_csv(tmp_path, [["2", "Test", "2 Road", "Austin", "TX", "", "3.5"]])
    load(path, tmp_path)
    CityCoordinate.objects.filter(normalized_city="austin").update(latitude=30.3)
    assert load(path, tmp_path)["updated"] == 1
    assert FuelStation.objects.get().latitude == 30.3


def test_missing_csv_or_places(tmp_path):
    with pytest.raises(CommandError, match="missing"):
        load(tmp_path / "absent.csv", tmp_path)
    path = write_csv(tmp_path, [["2", "Test", "2 Road", "Austin", "TX", "", "3.5"]])
    with pytest.raises(CommandError, match="places"):
        load(path, tmp_path)


def test_report_cannot_overwrite_original_csv(places, station_factory, tmp_path):
    station_factory()
    path = write_csv(tmp_path, [["2", "Test", "2 Road", "Austin", "TX", "", "3.5"]])
    original = path.read_bytes()
    with pytest.raises(CommandError, match="overwrite"):
        call_command("load_fuel_prices", csv=str(path), unresolved_report=str(path))
    assert path.read_bytes() == original and FuelStation.objects.count() == 1


def test_report_failure_rolls_back_snapshot(places, station_factory, tmp_path):
    old = station_factory()
    path = write_csv(tmp_path, [["2", "Test", "2 Road", "Austin", "TX", "", "3.5"]])
    report = tmp_path / "directory-instead-of-file"
    report.mkdir()
    with pytest.raises(CommandError, match="finalized"):
        call_command("load_fuel_prices", csv=str(path), unresolved_report=str(report))
    assert FuelStation.objects.get().pk == old.pk


def test_city_normalization():
    assert normalize_place_city("St. Louis city") == normalize_city("Saint Louis")
    assert normalize_city("Ft. Worth") == "fort worth"
    assert normalize_place_city("New York city") == "new york"
    assert normalize_place_city("Kansas City city") == normalize_city("Kansas City")
    assert normalize_place_city("Oklahoma City city") == normalize_city("Oklahoma City")
    assert normalize_state("New York") == "NY"
    assert normalize_state("Ontario") is None


def test_supplied_csv_when_available(settings, tmp_path):
    path = settings.FUEL_PRICES_CSV
    if not path.exists():
        pytest.skip("The assessment CSV was not supplied; no fuel prices have been fabricated.")
    # Restore the real preprocessed geographic lookup in the test DB without network access.
    raw = settings.BASE_DIR / "data" / "geographic" / "raw" / "2025_Gaz_place_national.zip"
    if not raw.exists():
        raw = path.parent / "geographic" / "raw" / "2025_Gaz_place_national.zip"
    if not raw.exists():
        pytest.skip("Run prepare_locations once to cache the Census places archive.")
    from fuel_optimizer.management.commands.prepare_locations import parse_places

    CityCoordinate.objects.bulk_create(parse_places(raw.read_bytes()), batch_size=1000)
    result = load(path, tmp_path)
    assert result["source_rows"] > 0
    assert result["loaded"] == FuelStation.objects.count()
    assert result["located"] > 0


def test_eight_decimal_source_prices_are_preserved(places, tmp_path):
    path = write_csv(tmp_path, [["7", "Test", "1 Road", "Austin", "TX", "", "3.12345678"]])
    result = load(path, tmp_path)
    assert result["loaded"] == 1 and result["invalid"] == 0
    assert FuelStation.objects.get().retail_price == Decimal("3.12345678")
    assert load(path, tmp_path)["skipped"] == 1


def test_canadian_source_records_retained_and_excluded_from_us_location_matching(places, tmp_path):
    path = write_csv(tmp_path, [["8", "Test", "1 Road", "Toronto", "ON", "", "4.23456789"]])
    result = load(path, tmp_path)
    station = FuelStation.objects.get()
    assert result["loaded"] == 1 and result["invalid"] == 0 and result["unresolved"] == 1
    assert station.state == "ON" and station.latitude is None and station.coordinate_source == "unresolved"
    assert "unsupported_region" in (tmp_path / "unresolved.csv").read_text()


def test_configured_csv_default_supports_docker_mount(places, settings, tmp_path):
    path = write_csv(tmp_path, [["7", "Test", "1 Road", "Austin", "TX", "", "3.12345678"]])
    settings.FUEL_PRICES_CSV = path
    call_command("load_fuel_prices", unresolved_report=str(tmp_path / "unresolved.csv"))
    assert FuelStation.objects.get().retail_price == Decimal("3.12345678")
