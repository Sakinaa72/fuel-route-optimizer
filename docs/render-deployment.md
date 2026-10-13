# Render deployment and private-data setup

The existing Django API runs as a Docker web service with a separate managed
PostgreSQL database. `render.yaml` specifies **free** plans only and the same Virginia
region for both resources. Local Compose continues to use persistent SQLite.

## Initialization and persistence

The image contains only code, collected static files and public US Census archives /
state boundaries. It never includes the assessment CSV, its row-level previews, local
databases or environment secrets. The entrypoint runs migrations before Gunicorn;
PostgreSQL advisory locking serializes overlapping initializers. Gunicorn binds to
`0.0.0.0:$PORT` (8000 locally) and gracefully handles SIGTERM.

With `AUTO_INITIALIZE_DATA=true`, empty Census tables are initialized from image-local
public archives. An empty fuel table is imported only if its private runtime CSV exists.
A populated fuel table is preserved on ordinary restarts, even when the CSV is missing.
For an intentional updated snapshot, set `REFRESH_FUEL_PRICES=true` for one deployment,
then restore it to false. Invalid CSV input rolls back the import; no fabricated prices
are supplied. Successful route/geocoding caches persist in PostgreSQL.

## Dashboard configuration checklist

| Variable / setting | Value |
|---|---|
| Runtime | Docker; root `Dockerfile` |
| Service plan / database plan | **Free / Free**, never upgrade automatically |
| Region | Virginia for both |
| `DATABASE_URL` | The managed database's **internal** connection URL; keep secret |
| `DJANGO_SECRET_KEY` | Generate at least 64 random characters securely; keep secret |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1`; platform hostname is added automatically |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Optional custom HTTPS origins; platform HTTPS origin is added automatically |
| `DJANGO_TRUST_PROXY_SSL_HEADER` | `true` on Render's trusted HTTPS proxy |
| `DJANGO_SECURE_SSL_REDIRECT` | `true`; local health path remains probe-accessible |
| `DJANGO_SECURE_HSTS_SECONDS` | `31536000` for the HTTPS service |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` / `DJANGO_SECURE_HSTS_PRELOAD` | `true` for this service's HTTPS host |
| `WEB_CONCURRENCY` | `1` for the free service; two threads |
| `AUTO_INITIALIZE_DATA` | `true` |
| `REFRESH_FUEL_PRICES` | `false` |
| `FUEL_CSV_PATH` | `/etc/secrets/fuel-prices-for-be-assessment.csv` |
| `GEOCODING_ENABLED` | `false` unless deliberately configured with an identifying User-Agent |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` or a compatible hosted provider |
| Health-check path | `/api/v1/health/` |
| Port | Read platform `PORT`; do not override it with 8000 |

## Private assessment CSV

The source CSV is **not authorized for redistribution**. Do not commit it, put rows in
source/configuration/logs, or bake it into an image.

In the correct Render workspace and service:

1. Open **Environment → Secret Files → Add Secret File**.
2. Set filename to `fuel-prices-for-be-assessment.csv`.
3. Paste the original file into **Contents** using the secure Dashboard form. Do not
   send passwords, connection URLs, signing keys or the file contents in chat.
4. Save/redeploy. The configured path is `/etc/secrets/fuel-prices-for-be-assessment.csv`.
5. Verify health: 8,125 records, 7,033 approximate coordinates, 1,092 unresolved,
   `ready_to_plan=true`. The original 8,151 rows contain 26 exact duplicates.

The file is 577,081 bytes, below Render's combined 1 MB secret-file limit. Secret files
are available to a running Docker service under `/etc/secrets/`; the build script never
reads them. If no file has been uploaded, the application starts with an accurate
`fuel_dataset_loaded=false` / `ready_to_plan=false` status and route planning returns
`fuel_data_missing` (503). A live HTML or health response is not proof of ready fuel data.

Free services do not provide SSH/one-off jobs, so this initialization occurs safely in
the startup process, rather than relying on a shell that the plan does not offer.

## Validate / test / publish

```bash
source .venv/bin/activate
python manage.py check
ruff check .
ruff format --check .
python -m pytest -q
docker compose config --quiet
docker compose up --build -d
docker compose exec web python -m pytest -q
```

The Blueprint was validated against `https://render.com/schema/render.yaml.json`.
On a host with the official Render CLI available, also run `render blueprints validate`.
Private dataset tests legitimately skip in CI if the evaluator has not supplied that
file. Public source publication does not include private CSV or generated price previews.

For a reproducible PostgreSQL compatibility check:

```bash
python scripts/create_postgres_check_env.py
docker compose --env-file var/postgres-check.env -f docker-compose.postgres.yml -p fuel-optimizer-pgcheck up --build -d
docker compose --env-file var/postgres-check.env -f docker-compose.postgres.yml -p fuel-optimizer-pgcheck exec web python -m pytest -q
```

This creates separate test volumes and serves on 127.0.0.1:8003. The generated credentials
are owner-only and ignored. It does not replace/delete the existing local SQLite volume.

After publication, connect the actual repository in Render or use the Blueprint link
constructed from that verified repository URL. Set the secret variables, health path
and private file; wait for the deploy to report **live**. Then verify HTTPS health,
demo, Swagger/static files, real route prices/geometry/ordered legs/costs, validation
errors and cache reuse. Record the actual URLs in the submission checklist only after
verification. Do not claim a price-backed public route before the private import succeeds.

## Plan limits and troubleshooting

- Free web services sleep after 15 idle minutes; wake-up can take about a minute.
- Free Postgres expires 30 days after creation; one free database per workspace, 1 GB
  storage and no managed backups. No paid fallback is authorized here.
- Data missing: verify the private secret filename/path and redeploy; do not insert fake prices.
- Database unavailable: check internal URL, same region and database lifetime; do not log credentials.
- Static docs missing: check `collectstatic` build output and WhiteNoise middleware.
- Incorrect redirect/host: check the actual Render hostname and trusted HTTPS proxy settings.
- Existing data disappearing on restart indicates an incorrect database URL or missing local
  named volume; the Render configuration rejects ephemeral SQLite.

Sources: [free-plan limits](https://render.com/docs/free),
[environment variables and secret files](https://render.com/docs/configure-environment-variables),
[Blueprint specification](https://render.com/docs/blueprint-spec).
