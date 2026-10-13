import io
import zipfile

import pytest

from fuel_optimizer.management.commands.prepare_locations import parse_places


@pytest.mark.parametrize("delimiter", ["|", "\t"])
def test_census_delimiters_and_header_whitespace(delimiter):
    data = delimiter.join(["USPS", "GEOID", "NAME", "INTPTLAT", "INTPTLONG   "]) + "\n"
    data += delimiter.join(["TX", "4805000", "Austin city", "30.2672", "-97.7431"]) + "\n"
    data += delimiter.join(["PR", "7200000", "Excluded place", "18.1", "-66.1"]) + "\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("places.txt", data)
    places = parse_places(buffer.getvalue())
    assert len(places) == 1 and places[0].normalized_city == "austin"
