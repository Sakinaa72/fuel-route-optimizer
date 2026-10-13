"""Bake only public Census archives/boundaries into the image; never read a fuel CSV."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fuel_optimizer.services.geographic_data import (  # noqa: E402
    PLACES_URL,
    STATES_URL,
    archive_bytes,
    parse_states,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory", type=Path, default=Path(__file__).resolve().parents[1] / "data/geographic"
    )
    directory = parser.parse_args().directory
    archive_bytes(directory / "raw/2025_Gaz_place_national.zip", PLACES_URL)
    states = archive_bytes(directory / "raw/cb_2025_us_state_500k.zip", STATES_URL)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "us-states.geojson").write_text(json.dumps(parse_states(states), separators=(",", ":")))
    print(json.dumps({"event": "public_geographic_files_prepared", "states": 51}))


if __name__ == "__main__":
    main()
