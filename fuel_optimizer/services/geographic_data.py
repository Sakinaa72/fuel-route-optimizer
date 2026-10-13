import io
import zipfile

import httpx
import shapefile
from django.core.management.base import CommandError
from shapely.geometry import mapping, shape

from .states import STATE_CODES

PLACES_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_place_national.zip"
)
STATES_URL = "https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_state_500k.zip"


def archive_bytes(path, url, refresh=False):
    if path.exists() and not refresh:
        return path.read_bytes()
    try:
        with httpx.Client(timeout=httpx.Timeout(60, connect=10), follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "FuelRouteOptimizer/1.0 Census preprocessing"})
            response.raise_for_status()
        if len(response.content) > 30_000_000:
            raise CommandError("Geographic archive exceeds the permitted size.")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            if archive.testzip() is not None:
                raise zipfile.BadZipFile("Archive checksum mismatch")
    except (httpx.HTTPError, zipfile.BadZipFile) as exc:
        raise CommandError(
            "Could not download Census data. Supply downloaded archives using --places-zip and --states-zip."
        ) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(response.content)
    temporary.replace(path)
    return response.content


def parse_states(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        streams = {
            extension: io.BytesIO(archive.read(next(name for name in names if name.endswith(extension))))
            for extension in (".shp", ".shx", ".dbf")
        }
        with shapefile.Reader(shp=streams[".shp"], shx=streams[".shx"], dbf=streams[".dbf"]) as reader:
            features = []
            for row in reader.iterShapeRecords():
                record = row.record.as_dict()
                state = record["STUSPS"]
                if state in STATE_CODES:
                    polygon = shape(row.shape.__geo_interface__)
                    if not polygon.is_valid:
                        polygon = polygon.buffer(0)
                    features.append(
                        {"type": "Feature", "properties": {"state": state}, "geometry": mapping(polygon)}
                    )
    if len(features) != 51:
        raise ValueError("Expected 50 states and DC")
    return {"type": "FeatureCollection", "features": features}
