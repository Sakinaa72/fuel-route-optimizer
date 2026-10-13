# Postman demonstration

1. Start the app, preprocess Census data and strictly import the supplied price CSV.
2. Run `python scripts/find_demo_routes.py`. It tries a bounded set of city pairs using
   **real local prices and the live routing provider**, checks that the long example has
   at least two stops, and only then writes a verified environment. It can fail honestly
   when coverage or routing is insufficient. It never seeds prices or invents successes.
3. Import `fuel-route-optimizer.postman_collection.json` and the generated
   `var/postman-verified.postman_environment.json`. Select the environment.
4. Set `base_url` if the server is elsewhere. Run health, short route, long route,
   missing-input and unsupported-location requests. Show `fuel_summary.legs`: the sum
   includes departure inventory and the last leg. Route coordinates are GeoJSON lon/lat.
5. The timeout request requires `DJANGO_DEBUG=true` and `ENABLE_FAILURE_DEMO=true`, then
   a server restart. It sends `X-Demo-Upstream-Failure: timeout` and returns a clearly
   labeled simulated 503 without external calls. It is disabled by default and outside
   DEBUG. Run it individually, or opt in before using the collection runner.

Default Austin/Dallas and Miami/Ellensburg variables were verified with the original
CSV and live OSRM. The short example has 3 modeled stops and costs $54.55; the long
example has 15 stops and costs $978.35. Regenerate the environment when data/providers
change. Houston/Chicago lacks a usable departure price within the current radius and
was deliberately replaced as the default long demonstration. No canned success responses are included.
The missing-input example runs even when the dataset is missing; the other input and
successful-route examples require initialized data.

Postman tests check HTTP/JSON, real LineString geometry, feasible leg distances, cost
reconciliation and multiple stops. The API permits 30 requests/minute per client in each
process; use a 2-second runner delay for larger repeated runs.
