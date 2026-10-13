# Final end-to-end verification report

Final verification: **14 October 2026**, continuing the existing application. Working
features were retained. The real assessment CSV, live API, independent cost audit,
Docker container and browser demo were exercised. The reviewed source was subsequently pushed to GitHub during deployment preparation;
no Loom recording was created.

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

## Public deployment and actual quality checks

Source: https://github.com/Sakinaa72/fuel-route-optimizer

Public URLs verified on **14 October 2026**:

- Demo: https://fuel-route-optimizer-edcq.onrender.com/demo/
- Swagger: https://fuel-route-optimizer-edcq.onrender.com/docs/
- Health: https://fuel-route-optimizer-edcq.onrender.com/api/v1/health/
- POST: https://fuel-route-optimizer-edcq.onrender.com/api/v1/route/plan/

The user selected Sakina's authenticated Render workspace after initially selecting
Shyan's connector workspace. A Blueprint created a **free Docker web service and free
PostgreSQL 16 database** in Sakina's workspace. Database traffic uses the internal
connection reference; external database access is blocked. The signing key and CSV
were entered privately through Render's Dashboard. No private contents entered source,
image layers or application logs. The unused earlier free database in Shyan's workspace
was left untouched. No paid infrastructure was requested or created.

Before upload, public health reported zero records and `ready_to_plan=false`; route
planning returned 503 `fuel_data_missing`. After private secret-file upload, actual
Render logs recorded:

```json
{"source_rows":8151,"loaded":8125,"updated":0,"skipped":0,"duplicate":26,"invalid":0,"removed":0,"unresolved":1092,"located":7033}
```

Render reported **Deploy succeeded | Live**, Gunicorn listened on platform port **10000**,
and HTTPS health reported `ready_to_plan=true` with the same counts. Both examples in
the table above also passed the **public HTTP audit**: identities and exact prices match
the original CSV; coordinates match the local Census import; geometry/order/range,
first/final legs and rounded cost totals reconcile. Repeated requests and changed-MPG
requests reported cached geometry. The HTTP audit permits only the four-decimal display
uncertainty when recomputing per-leg cost; the separate Decimal audit uses unrounded
values and proves the modeled optimum. Exact adapter call counts are measured by the
local live audit, not inferred from HTTP timing or billed Render metrics.

The first public cache check overlapped the rolling secret-file redeployment and saw
a repeat cache miss; it was not marked successful. After the provider reported Live,
three short repeats and the complete two-route audit all verified cache reuse.

Public `/demo/`, `/docs/`, `/openapi.json` and collected Swagger initialization JS
returned 200. Swagger rendered its operations and current-host server. The public
Leaflet maps rendered real origin/destination and all 3/15 ordered stop markers; a popup
showed the returned price, leg cost and approximation notice. Attribution was visible.
Captured browser warning/error logs were empty for the demo and Swagger pages.
Missing input returned structured 400; an unknown path returned a non-debug 404.
The long route, including all 15 stops, was independently checked through the HTTP API.

A genuine free-plan Blueprint defect was found: Render rejected
`maxShutdownDelaySeconds`, even though its general JSON schema accepted the field.
The unsupported field was removed and a regression test added. Gunicorn retains a
25-second graceful timeout within Render's default 30-second window. Production support
also includes DATABASE_URL/driver validation, startup advisory locking, WhiteNoise,
exact hostname/HTTPS origin, proxy handling, production error redaction, and honest
missing-data/database-unavailable states; each behavior has regression coverage.

Actual final checks:

- Local full suite: **112 passed, zero skipped**, 2.11 s.
- SQLite Docker full suite: **112 passed, zero skipped**, 1.85 s.
- PostgreSQL 16 Docker full suite: **112 passed, zero skipped**, 2.48 s.
- Ruff check and format check passed; Django check reported zero issues.
- Production-profile PostgreSQL `manage.py check --deploy` reported zero issues.
- Migrations ran; `makemigrations --check --dry-run` reported no changes.
- Docker image rebuilt; Compose configuration validated; Gunicorn health is healthy.
- SQLite and PostgreSQL rows survived container restart/recreation: **8,125** retained.
- Live network integration / independent Decimal optimum / exact provider counters passed.
- Public HTTP audit passed for both routes, prices, coordinates, costs and cache reuse.
- GitHub CI succeeded. CI lacks the private CSV, so its supplied-CSV test legitimately skips.
- `.gitignore`, `.dockerignore`, staged source and committed file boundaries were reviewed.
  No CSV, environment secrets, databases, runtime evidence or exact-price screenshots
  were published. Source publication and pushes use the authorized Sakinaa72 repository.

Versions: host Python **3.13.4**; Docker Python **3.13.14**; Django **6.1.2**;
DRF **3.18.3**; HTTPX **0.28.1**; Shapely **2.2.0**; pyproj **3.8.0**;
pytest **9.1.1**; pytest-django **4.14.0**; Gunicorn **26.2.0**.
All **35** direct/transitive dependencies are hash-locked. Docker Engine **29.8.2**,
Docker Desktop **4.95.0** and Compose **5.6.0** were used.

## Run and submit

The local container remains at http://127.0.0.1:8000/demo/.

```bash
docker compose up --build -d
docker compose exec web python manage.py check
docker compose exec web python -m pytest -q
curl -sS https://fuel-route-optimizer-edcq.onrender.com/api/v1/health/
curl -sS -X POST https://fuel-route-optimizer-edcq.onrender.com/api/v1/route/plan/ \
  -H 'Content-Type: application/json' \
  -d '{"start":"Austin, TX","finish":"Dallas, TX"}'
```

After local CSV/Census import, reproduce the two independent audits:

```bash
source .venv/bin/activate
python scripts/find_demo_routes.py
python scripts/verify_live_api.py
python scripts/verify_http_api.py --base-url https://fuel-route-optimizer-edcq.onrender.com
```

The generated `var/` evidence/environment and previews remain private/ignored. Import
`postman/fuel-route-optimizer.postman_collection.json`, select its verified routes and
set `base_url` to the public host. The simulated timeout request runs only in an opt-in
local DEBUG instance. The public service keeps DEBUG and that simulation disabled.
The five-minute Loom script and submission checklist contain the verified links;
**no Loom recording exists yet**. Record/upload it, then add the genuine recording URL.

## Remaining limitations

All 7,033 located records use **approximate city coordinates**, with **zero verified
pump coordinates**. 1,092 remain unresolved. Road detours are excluded; costs value
consumed departure inventory and outgoing segments rather than purchases/tank mixing.
The independent optimum applies to this documented estimate. Prices are a static
assessment snapshot. Public OSRM has no production SLA; full-address geocoding remains
opt-in and was not contacted in these city-route audits.

Houston–Chicago honestly fails `departure_price_unavailable`: no usable Houston, TX
source record; the nearest located price reference is about **40.0023 miles** away,
beyond the 20-mile departure proxy radius. Houston, MS was not substituted.

Free Render web instances sleep after 15 idle minutes and may take about a minute to
wake. The actual PostgreSQL dashboard reports expiry **13 November 2026**; no paid
upgrade is authorized. Preserve the original local CSV for later private reinitialization.
Dataset redistribution remains explicitly unauthorized. Loom recording and Postman GUI
rehearsal remain user delivery steps; the collection's HTTP bodies and assertions are
verified separately. See the Render runbook for maintenance and private data setup.
