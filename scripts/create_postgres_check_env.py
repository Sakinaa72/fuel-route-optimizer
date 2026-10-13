"""Generate local PostgreSQL test credentials in an ignored, owner-only file."""

import secrets
from pathlib import Path

path = Path("var/postgres-check.env")
path.parent.mkdir(exist_ok=True)
if not path.exists():
    password = secrets.token_urlsafe(32)
    key = secrets.token_urlsafe(64)
    with path.open("x") as stream:
        stream.write(f"POSTGRES_PASSWORD={password}\nDJANGO_SECRET_KEY={key}\n")
        stream.write(f"DATABASE_URL=postgresql://fuel_optimizer:{password}@postgres:5432/fuel_optimizer\n")
    path.chmod(0o600)
print("PostgreSQL check credentials are ready in ignored var/postgres-check.env; values were not displayed.")
