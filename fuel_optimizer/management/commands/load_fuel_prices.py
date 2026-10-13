import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from fuel_optimizer.models import CityCoordinate, FuelStation
from fuel_optimizer.services.locations import normalize_city, normalize_state

COLUMNS = ["OPIS Truckstop ID", "Truckstop Name", "Address", "City", "State", "Rack ID", "Retail Price"]
CANADIAN_PROVINCES = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}


class Command(BaseCommand):
    help = "Import an authoritative CSV snapshot transactionally; no station geocoding."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(settings.FUEL_PRICES_CSV))
        parser.add_argument(
            "--skip-invalid", action="store_true", help="Merge valid rows without removing existing rows."
        )
        parser.add_argument("--unresolved-report", default="var/unresolved-stations.csv")

    def handle(self, *args, **options):
        path = Path(options["csv"])
        if not path.exists():
            raise CommandError(
                "Fuel CSV is missing. Place the supplied file at data/fuel-prices-for-be-assessment.csv."
            )
        locations, ambiguous = {}, set()
        for place in CityCoordinate.objects.values(
            "geoid", "normalized_city", "state", "latitude", "longitude", "source"
        ):
            key = (place["normalized_city"], place["state"])
            if key in locations:
                ambiguous.add(key)
            locations[key] = place
        if not locations:
            raise CommandError("No local places loaded. Run python manage.py prepare_locations first.")
        records, invalid, duplicates, row_count, unresolved = {}, [], 0, 0, []
        try:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames or not set(COLUMNS).issubset(reader.fieldnames):
                    raise CommandError("CSV must contain columns: " + ", ".join(COLUMNS))
                for line, row in enumerate(reader, 2):
                    row_count += 1
                    try:
                        if None in row or any(row.get(column) is None for column in COLUMNS):
                            raise ValueError("Malformed CSV row")
                        values = [row[column].strip() for column in COLUMNS]
                        source_id, name, address, city, state, rack_id, raw_price = values
                        state = normalize_state(state) or (
                            state.upper() if state.upper() in CANADIAN_PROVINCES else None
                        )
                        if not source_id or not name or not address or not city or not state:
                            raise ValueError("Missing required field or unsupported state/province code")
                        if any(
                            len(value) > bound
                            for value, bound in zip(values[:-1], [64, 240, 300, 160, 40, 64], strict=True)
                        ):
                            raise ValueError("Field too long")
                        price = Decimal(raw_price.removeprefix("$"))
                        if (
                            not price.is_finite()
                            or not 0 < price <= 100
                            or price != price.quantize(Decimal("0.00000001"))
                        ):
                            raise ValueError("Price must be positive, <=100 and have <=8 decimal places")
                        normalized = normalize_city(city)
                        content = [source_id, name, address, city, state, rack_id, str(price.normalize())]
                        record_key = hashlib.sha256(json.dumps(content).encode()).hexdigest()
                        if record_key in records:
                            duplicates += 1
                            continue
                        key = (normalized, state)
                        place = locations.get(key) if key not in ambiguous else None
                        fields = {
                            "source_truckstop_id": source_id,
                            "name": name,
                            "address": address,
                            "city": city,
                            "normalized_city": normalized,
                            "state": state,
                            "rack_id": rack_id,
                            "retail_price": price,
                            "latitude": place["latitude"] if place else None,
                            "longitude": place["longitude"] if place else None,
                            "coordinate_source": "city_centroid_approximation" if place else "unresolved",
                            "coordinate_reference": f"{place['source']}:{place['geoid']}" if place else "",
                        }
                        records[record_key] = fields
                        if not place:
                            unresolved.append(
                                [
                                    source_id,
                                    name,
                                    city,
                                    state,
                                    "unsupported_region"
                                    if state in CANADIAN_PROVINCES
                                    else "ambiguous_place"
                                    if key in ambiguous
                                    else "no_place_match",
                                ]
                            )
                    except (ValueError, InvalidOperation) as exc:
                        invalid.append((line, str(exc)))
        except (OSError, UnicodeError, csv.Error) as exc:
            raise CommandError("CSV could not be read. Existing station data was preserved.") from exc
        if invalid:
            self.stderr.write(f"Invalid rows: {len(invalid)}. First errors: {invalid[:10]}")
            if not options["skip_invalid"]:
                raise CommandError(
                    "Import aborted; existing data preserved. Fix rows or explicitly use --skip-invalid for a non-destructive merge."
                )
        if not records:
            raise CommandError("No valid records; existing data preserved.")
        report = Path(options["unresolved_report"])
        if report.resolve() == path.resolve():
            raise CommandError("The unresolved report cannot overwrite the original source CSV.")
        temporary_report = report.with_name(report.name + ".tmp")
        try:
            report.parent.mkdir(parents=True, exist_ok=True)
            with temporary_report.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["source_id", "name", "city", "state", "reason"])
                writer.writerows(unresolved)
        except OSError as exc:
            raise CommandError("Unresolved report could not be written; existing data preserved.") from exc
        loaded, updated, skipped, removed = 0, 0, 0, 0
        with transaction.atomic():
            existing = {row.record_key: row for row in FuelStation.objects.all()}
            additions, changes = [], []
            for record_key, fields in records.items():
                old = existing.get(record_key)
                if old is None:
                    additions.append(FuelStation(record_key=record_key, **fields))
                elif any(getattr(old, field) != value for field, value in fields.items()):
                    for field, value in fields.items():
                        setattr(old, field, value)
                    old.imported_at = timezone.now()
                    changes.append(old)
                else:
                    skipped += 1
            FuelStation.objects.bulk_create(additions, batch_size=500)
            if changes:
                FuelStation.objects.bulk_update(
                    changes, [*next(iter(records.values())), "imported_at"], batch_size=500
                )
            loaded, updated = len(additions), len(changes)
            if not options["skip_invalid"]:
                stale = [old.pk for key, old in existing.items() if key not in records]
                removed = len(stale)
                FuelStation.objects.filter(pk__in=stale).delete()
            # Replacement failure also rolls back the database snapshot.
            try:
                temporary_report.replace(report)
            except OSError as exc:
                raise CommandError(
                    "Unresolved report could not be finalized; existing data preserved."
                ) from exc
        self.stdout.write(
            json.dumps(
                {
                    "source_rows": row_count,
                    "loaded": loaded,
                    "updated": updated,
                    "skipped": skipped,
                    "duplicate": duplicates,
                    "invalid": len(invalid),
                    "removed": removed,
                    "unresolved": len(unresolved),
                    "located": len(records) - len(unresolved),
                }
            )
        )
