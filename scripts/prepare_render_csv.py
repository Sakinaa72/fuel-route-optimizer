"""Prepare a private runtime secret below Docker's per-file size limit; print no rows."""

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fuel_optimizer.services.price_files import encode_runtime_csv  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=Path("data/fuel-prices-for-be-assessment.csv"))
    parser.add_argument("--output", type=Path, default=Path("var/fuel-prices-for-be-assessment.csv.gz.b64"))
    args = parser.parse_args()
    if args.csv.resolve() == args.output.resolve():
        raise ValueError("Output must not overwrite the original CSV.")
    raw = args.csv.read_bytes()
    encoded = encode_runtime_csv(raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as stream:
        args.output.chmod(0o600)
        stream.write(encoded)
    print(
        f"Private runtime file prepared: {len(raw)} source bytes / {len(encoded)} encoded bytes; "
        f"source SHA256 {hashlib.sha256(raw).hexdigest()}"
    )


if __name__ == "__main__":
    main()
