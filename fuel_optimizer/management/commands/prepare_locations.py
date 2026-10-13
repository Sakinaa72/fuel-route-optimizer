import csv
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fuel_optimizer.models import CityCoordinate
from fuel_optimizer.services.geographic_data import PLACES_URL, STATES_URL, archive_bytes, parse_states
from fuel_optimizer.services.locations import STATE_CODES, normalize_place_city


def parse_places(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        filename = next(name for name in archive.namelist() if name.endswith(".txt"))
        text = archive.read(filename).decode("utf-8-sig")
    # Census 2025 changed from tab-delimited files to pipe-delimited files.
    delimiter = "|" if "|" in text.splitlines()[0] else "\t"
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("Missing Gazetteer columns")
    reader.fieldnames = [field.strip() for field in reader.fieldnames]
    if not {"USPS", "GEOID", "NAME", "INTPTLAT", "INTPTLONG"}.issubset(reader.fieldnames):
        raise ValueError("Missing Gazetteer columns")
    places = []
    for row in reader:
        if row["USPS"].strip() not in STATE_CODES:
            continue
        latitude, longitude = float(row["INTPTLAT"]), float(row["INTPTLONG"])
        if not (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            raise ValueError("Invalid Gazetteer coordinate")
        city = row["NAME"].strip()
        places.append(
            CityCoordinate(
                geoid=row["GEOID"].strip(),
                city=city,
                normalized_city=normalize_place_city(city),
                state=row["USPS"].strip(),
                latitude=latitude,
                longitude=longitude,
            )
        )
    if not places:
        raise ValueError("No US places")
    return places


class Command(BaseCommand):
    help = "Download Census places and US boundaries once; no fuel station geocoding."

    def add_arguments(self, parser):
        parser.add_argument("--places-zip", type=Path)
        parser.add_argument("--states-zip", type=Path)
        parser.add_argument("--refresh", action="store_true")

    def handle(self, *args, **options):
        directory = settings.GEOGRAPHIC_DIR
        raw_directory = directory / "raw"
        try:
            places_raw = (
                options["places_zip"].read_bytes()
                if options["places_zip"]
                else archive_bytes(
                    raw_directory / "2025_Gaz_place_national.zip", PLACES_URL, options["refresh"]
                )
            )
            states_raw = (
                options["states_zip"].read_bytes()
                if options["states_zip"]
                else archive_bytes(
                    raw_directory / "cb_2025_us_state_500k.zip", STATES_URL, options["refresh"]
                )
            )
            places, states = parse_places(places_raw), parse_states(states_raw)
        except (OSError, ValueError, KeyError, StopIteration, zipfile.BadZipFile) as exc:
            raise CommandError(
                "Geographic data could not be parsed; existing place records were preserved."
            ) from exc
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / "us-states.geojson.tmp"
        temporary.write_text(json.dumps(states, separators=(",", ":")), encoding="utf-8")
        with transaction.atomic():
            CityCoordinate.objects.all().delete()
            CityCoordinate.objects.bulk_create(places, batch_size=1000)
            temporary.replace(directory / "us-states.geojson")
        manifest = {
            "version": "Census 2025",
            "places_url": PLACES_URL,
            "states_url": STATES_URL,
            "places_sha256": hashlib.sha256(places_raw).hexdigest(),
            "states_sha256": hashlib.sha256(states_raw).hexdigest(),
            "places_loaded": len(places),
            "states_loaded": len(states["features"]),
        }
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(json.dumps(manifest))
