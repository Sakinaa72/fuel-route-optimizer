# Five-minute demonstration (target 4:45; hard stop 5:00)

Preflight: import the actual supplied CSV, run `python scripts/find_demo_routes.py`,
import the resulting Postman environment, run the collection and tests, and open `/demo/`.
Run `python scripts/verify_live_api.py` to reproduce the source-price, range, independent
Decimal-cost and request-count checks. Close unrelated tabs
and avoid showing `.env`. For the timeout example, enable `ENABLE_FAILURE_DEMO=true`
with `DJANGO_DEBUG=true`, restart, then disable it afterward.

| Time | Screen and narration |
|---|---|
| 0:00–0:30 | Repository and diagram. “This Django API plans US driving trips using imported retail fuel prices, a 500-mile range and 10 mpg. It returns geometry, feasible stops and a complete estimated fuel cost.” |
| 0:30–1:15 | API docs and services. “Local Census places resolve cities. Full addresses can use cached, rate-limited geocoding. One OSRM call returns the complete route. All station filtering and optimization happen locally.” |
| 1:15–2:45 | Postman health, successful short route, then verified long route. Show distance/duration, `[longitude, latitude]` geometry, prices, ordered stops, `fuel_summary.legs` and `all_legs_within_max_range`. Switch to `/demo/` and display the same long route. “These are imported prices; station markers are approximate city locations.” |
| 2:45–3:30 | `optimization.py` and legs. “A DAG links later opportunities only when the route gap is within 500 miles. Dynamic programming minimizes outgoing-segment fuel cost. Departure inventory is valued using a nearby imported price, so the first leg is included. The final leg is included too. This estimates consumption cost rather than simulating purchases or leftover fuel.” |
| 3:30–4:15 | Import report and cache tests. “Prices are imported transactionally and duplicate source IDs remain safe. Places are matched once locally; unresolved records are reported. A repeated route uses persistent geometry and geocoding caches. There is no station-by-station routing or live station geocoding.” |
| 4:15–4:45 | Postman missing input and test summary. Show actual passing count. Mention provider failures, geometry, hand-calculated costs, exhaustive-path oracle and 8,151-record synthetic performance test. |
| 4:45–5:00 | Repository structure and links. “The repository includes setup instructions, migrations, tests, Postman and Docker configuration. Public OSRM has no production SLA. City locations and road-detour estimates need refinement for real dispatch.” |

Use the collection's selected routes, not unverified defaults. Rehearse with a stopwatch;
the narration is intentionally brief to reserve time for real requests. If network latency
would exceed the slot, warm the route cache beforehand and identify the cache hit on screen.
An actual recording has not been created by this repository.

Verified rehearsal data: health has **8,125 records / 7,033 located / 1,092 unresolved**.
Use **Austin, TX → Dallas, TX** (195.9715 miles; 3 stops; 19.5971 gallons; $54.55),
then **Miami, FL → Ellensburg, WA** (3,196.5477 miles; 15 stops; 319.6548 gallons;
$978.35). The longest modeled long-route leg is 475.5369 miles. Show **100 passing
tests with no skips**. Explain the 26 exact duplicates and preserved eight-decimal
prices briefly; omit detailed code scrolling to stay within the five-minute window.
The initial inventory value is included ($17.63 on the long route), and the final
Post Falls–destination leg contributes $66.36. No purchase receipts are implied.
