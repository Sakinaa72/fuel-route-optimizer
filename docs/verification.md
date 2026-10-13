# Final end-to-end verification report

Final verification: **14 October 2026**, continuing the existing application. Working
features were retained. The real assessment CSV, live API, independent cost audit,
Docker container and browser demo were exercised. No GitHub push or Loom recording
was performed.

## Actual data and import results

The file was located in Downloads and copied **byte-for-byte** to the required path.
Its schema contains all seven expected columns and **8,151 source rows**.
SHA-256: `c704371f141ded9c54df6c32d488a0ba2ceb589f88c936c967daa5330e0cd241`.
The source and copied file remain unchanged.

| Count | First successful strict import | Identical reimport |
|---|---:|---:|
| Source rows | 8,151 | 8,151 |
| Imported new records | **8,125** | **0** |
| Updated | **0** | **0** |
| Unchanged/skipped | **0** | **8,125** |
| Exact duplicate source rows | **26** | **26** |
| Rejected/invalid | **0** | **0** |
| Removed stale records | **0** | **0** |

Coordinate coverage: **7,033 approximate Census place coordinates**, **1,092 unresolved**.
Unresolved reasons: **620 Canadian records**, **428 unmatched US places**, and **44
ambiguous US place matches**. Coverage of the 7,505 distinct US records is **93.71%**.
All Canadian records are retained with null coordinates and excluded from US planning.
The local geographic reference has **32,058 places** and **51 state/DC polygons**.

The CSV redistribution terms were not supplied. Its presence is not permission to
publish it. `.gitignore` and `.dockerignore` continue to exclude the original CSV;
obtaining redistribution permission remains a publication checklist item.

## Defects found and corrected

1. The importer rejected valid source prices with more than four decimal places.
   Storage and validation now preserve **eight decimal places**, matching the actual
   dataset. Migration `0002_alter_fuelstation_retail_price.py` applies this change.
   Regression tests check exact eight-decimal storage, idempotency and a hand-calculated
   departure/final-leg cost example. The source CSV was not rounded or edited.
2. The actual CSV includes Canadian province codes. These valid source records are now
   preserved as unresolved `unsupported_region` records instead of aborting US import.
   A regression test verifies they cannot be matched to a US place.
3. Docker mounts the CSV under `/app/input`, whereas the original default/test lookup
   expected `/app/data`. `FUEL_PRICES_CSV` configures the default and the real-data test
   reads the mounted source/archive. A regression test verifies the configured default.
4. Container pytest/Ruff caches needed a writable location. Both use the persistent
   `var/` directory; the final container suite has no cache warnings.
5. The HTTP audit detected a stale development process answering port 8000 with the
   previous four-decimal model. It was stopped. The actual endpoint now identifies as
   **Gunicorn** and returns source-exact eight-decimal prices. This was a running-process
   issue; source-price checks prevented it from being mistaken for a verified success.

The map displays up to eight price decimals. The discovery script and Postman default
long example now use the genuinely successful Miami–Ellensburg pair.

## Verified actual API examples

| Example | Distance (mi) | Fuel (US gal) | Estimated cost (USD) | Stops | Candidates | Geometry points | Longest modeled leg (mi) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Austin, TX → Dallas, TX | **195.9715** | **19.5971** | **54.55** | **3** | **89** | **2,786** | **129.6933** |
| Miami, FL → Ellensburg, WA | **3,196.5477** | **319.6548** | **978.35** | **15** | **561** | **33,322** | **475.5369** |

The source-exact selected station names, coordinates and full-precision prices were
verified locally against the private original CSV. The row-level audit is retained only
in ignored local evidence files, not in the publication source or Docker image.
Departure and final-leg costs reconcile with the aggregate trip totals above.

These are measured route responses, not canned successes. Complete actual JSON is
saved locally in ignored `var/demo-examples.json` and `var/docker-short-response.json` /
`var/docker-long-response.json`. Reproduce the examples after import rather than assuming
prices or provider routing will never change.

## Independent mathematics and external-call audit

`python scripts/verify_live_api.py` invokes the real Django request pipeline with live
OSRM and the imported database. It checks each selected record against the **original
CSV**, each coordinate against its Census GEOID, ordering, corridor bounds, every range
constraint, fuel consumption and cent-rounded leg-cost reconciliation. A separate
**forward Decimal path relaxation** agrees with the optimizer's unrounded minimum cost
for both real candidate sets. It also checks changed-MPG requests recalculate fuel while
reusing geometry. All modeled legs are below the default 500-mile range.

| Measured case, for each verified city pair | OSRM requests | Geocoding requests |
|---|---:|---:|
| Deliberately expired example cache / first live plan | **1** | **0** |
| Repeated identical request | **0** | **0** |
| Same endpoints with changed MPG | **0** | **0** |

The counters wrap the real provider adapters without replacing their responses. The
normal automated suite forbids live HTTP. Full-address call-limit/cache tests separately
verify <=2 endpoint geocodes and one route call on a miss. No request loop geocodes fuel
stations or routes once per station. Station import itself uses only local Census data.
The audit expires only the selected example route entries, not the entire cache.

Actual TCP requests to the Docker/Gunicorn server were also checked with full responses,
source-price/coordinate validation and the independent oracle. Repeats reported cache
hits. Health, `/demo/`, `/docs/` and `/openapi.json` returned HTTP 200 with expected
content types and `ready_to_plan=true`. All six Postman **request bodies** returned the
expected status: health/short/long 200, missing finish/non-US input 400, opt-in simulated
upstream timeout 503. The last was exercised on a temporary local container with
`ENABLE_FAILURE_DEMO=true`; that container was removed and the main service keeps the
failure switch disabled. The Postman GUI itself was not automated.

## Actual checks and runtime versions

- Local `python -m pytest -q`: **100 passed, zero skipped**, 1.83 s.
- Container `python -m pytest -q`: **100 passed, zero skipped, zero warnings**, 1.77 s.
- Migrations applied in both databases; `makemigrations --check --dry-run`: no changes.
- Django system checks: zero issues. Ruff check and format check: passed locally and in Docker.
- Docker image built, Compose configuration validated, non-root Gunicorn started,
  original CSV imported in a fresh persistent container DB and health check became healthy.
- Docker source CSV mount is read-only; source data are not baked into the image.
- Browser short/long routes rendered with origin/destination and all 3/15 numbered stop
  markers. Popups displayed source-exact prices, outgoing-leg cost and approximation
  notices. Mapping attribution was visible; captured console warnings/errors were empty.
- Dataset fingerprint and source equality checked; ignored secrets/DB/data boundaries
  and staged files reviewed. No remote and no staged files were present.

Versions: host Python **3.13.4**; container Python **3.13.14**; Django **6.1.2**;
DRF **3.18.3**; HTTPX **0.28.1**; Shapely **2.2.0**; pyproj **3.8.0**;
pytest **9.1.1**; pytest-django **4.14.0**; Gunicorn **26.2.0**.
All 25 direct/transitive dependencies remain hash-locked. Docker Engine **29.8.2**,
Docker Desktop **4.95.0** and Compose **5.6.0** were actually available and used.

## Run and submit

The verified container is left running at `http://127.0.0.1:8000/demo/`.

```bash
docker compose up -d
docker compose exec web python manage.py check
docker compose exec web python -m pytest -q
```

Local Python alternative (stop Docker first to release port 8000):

```bash
docker compose stop
source .venv/bin/activate
python manage.py migrate
python manage.py load_fuel_prices --csv data/fuel-prices-for-be-assessment.csv
python -m pytest -q
python scripts/find_demo_routes.py
python scripts/verify_live_api.py
python manage.py runserver 127.0.0.1:8000
```

Fresh setup instructions, geographic preprocessing and offline archive options are in
README. Import `postman/fuel-route-optimizer.postman_collection.json` and generated
`var/postman-verified.postman_environment.json`; the default verified request is:

```json
{"start": "Austin, TX", "finish": "Dallas, TX"}
```

Send it to `POST http://127.0.0.1:8000/api/v1/route/plan/`.
For the multiple-stop example use `Miami, FL` and `Ellensburg, WA`.
Review and commit the source files, create/configure the authorized GitHub repository,
then push yourself. Use `docs/loom-demo-script.md` to record/upload a <=5-minute demo.
Fill actual URLs in `docs/submission-checklist.md` after each succeeds.

## Remaining limitations

Coordinates are approximate Census place points, not verified truck stop pumps. Fuel
consumption/range use OSRM-scaled route offsets; **road detours are excluded**. Costs
value consumed departure inventory and outgoing segments at actual source prices;
actual purchases, leftover fuel and tank mixing are not simulated. Independent optimality
therefore applies to the documented segment-price model, not real-world transactions.
The public OSRM service has no production SLA. Public Nominatim was not contacted;
full-address geocoding remains deliberate opt-in. HTTPS production deployment is outside
this local verification.

Houston–Chicago failed honestly with `departure_price_unavailable`. The source has no usable Houston, TX departure record; the nearest located price
reference is approximately **40.0023 miles** away, beyond the
20-mile departure proxy radius. The source has a Houston, MS record, which is a different
place and was not substituted. Coverage/ambiguous/unmatched coordinates remain reported
rather than guessed. The original CSV redistribution permission remains unresolved.

Successful map previews are retained locally and excluded from Git and Docker images
because they show private source-price rows. No GitHub URL, Loom URL or completed recording has been invented.

## Publication-ready file inventory

The existing application was retained. New/changed verification work includes the
price migration, source-data importer/configuration, regression tests, writable container
caches, live audit script, real-route defaults, previews and delivery documentation.
All currently untracked source artifacts are:

```text
.dockerignore
.env.example
.github/workflows/tests.yml
.gitignore
Dockerfile
README.md
config/__init__.py
config/asgi.py
config/settings.py
config/urls.py
config/wsgi.py
conftest.py
data/README.md
data/geographic/README.md
docker-compose.yml
docs/loom-demo-script.md
docs/openapi.json
docs/submission-checklist.md
docs/verification.md
fuel_optimizer/__init__.py
fuel_optimizer/apps.py
fuel_optimizer/errors.py
fuel_optimizer/logging.py
fuel_optimizer/management/__init__.py
fuel_optimizer/management/commands/__init__.py
fuel_optimizer/management/commands/load_fuel_prices.py
fuel_optimizer/management/commands/prepare_locations.py
fuel_optimizer/middleware.py
fuel_optimizer/migrations/0001_initial.py
fuel_optimizer/migrations/0002_alter_fuelstation_retail_price.py
fuel_optimizer/migrations/__init__.py
fuel_optimizer/models.py
fuel_optimizer/serializers.py
fuel_optimizer/services/__init__.py
fuel_optimizer/services/cache.py
fuel_optimizer/services/cost_calculation.py
fuel_optimizer/services/geocoding.py
fuel_optimizer/services/http.py
fuel_optimizer/services/locations.py
fuel_optimizer/services/optimization.py
fuel_optimizer/services/planning.py
fuel_optimizer/services/route_geometry.py
fuel_optimizer/services/routing.py
fuel_optimizer/services/station_matching.py
fuel_optimizer/templates/fuel_optimizer/demo.html
fuel_optimizer/templates/fuel_optimizer/docs.html
fuel_optimizer/tests/__init__.py
fuel_optimizer/tests/test_api.py
fuel_optimizer/tests/test_geocoding.py
fuel_optimizer/tests/test_geometry.py
fuel_optimizer/tests/test_import.py
fuel_optimizer/tests/test_optimization.py
fuel_optimizer/tests/test_preprocessing.py
fuel_optimizer/urls.py
fuel_optimizer/views.py
manage.py
postman/README.md
postman/fuel-route-optimizer.postman_collection.json
pyproject.toml
pytest.ini
requirements.in
requirements.txt
scripts/docker-entrypoint.sh
scripts/find_demo_routes.py
scripts/prepare_station_locations.py
scripts/verify_live_api.py
tests/__init__.py
tests/test_delivery_artifacts.py
tests/test_performance.py
```
