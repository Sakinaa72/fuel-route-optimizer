"""Read plain CSVs or private gzip/base64 runtime files without writing decoded rows."""

import base64
import gzip
import io
from contextlib import contextmanager

MAX_SECRET_BYTES = 500 * 1024
MAX_DECODED_BYTES = 20_000_000


def encode_runtime_csv(raw):
    encoded = base64.b64encode(gzip.compress(raw, mtime=0))
    if len(encoded) > MAX_SECRET_BYTES:
        raise ValueError("Encoded private CSV exceeds the Docker secret-file limit.")
    return encoded


@contextmanager
def open_price_csv(path):
    if not path.name.endswith(".gz.b64"):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            yield stream
        return
    encoded = path.read_bytes().strip()
    if len(encoded) > MAX_SECRET_BYTES:
        raise ValueError("Encoded private CSV exceeds the Docker secret-file limit.")
    compressed = base64.b64decode(encoded, validate=True)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as archive:
        raw = archive.read(MAX_DECODED_BYTES + 1)
    if len(raw) > MAX_DECODED_BYTES:
        raise ValueError("Decoded private CSV exceeds the import size limit.")
    with io.StringIO(raw.decode("utf-8-sig"), newline="") as stream:
        yield stream
