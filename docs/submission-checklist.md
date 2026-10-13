# Submission checklist

- GitHub URL: **https://github.com/Sakinaa72/fuel-route-optimizer**
- Public demo URL: **https://fuel-route-optimizer-edcq.onrender.com/demo/**
- Swagger URL: **https://fuel-route-optimizer-edcq.onrender.com/docs/**
- API health URL: **https://fuel-route-optimizer-edcq.onrender.com/api/v1/health/**
- Loom URL: **[fill in after uploading the recording]**

- [x] Locate/copy the original CSV unchanged; validate all 8,151 source rows.
- [x] Keep the assessment CSV, exact-price previews, credentials and databases private; redistribution is not authorized.
- [x] Run migrations, Census preprocessing and strict import locally and in a fresh container DB.
- [x] Record counts: 8,125 imported, 26 exact duplicates, 0 rejected; 7,033 approximate / 1,092 unresolved.
- [x] Verify idempotent reimport: 0 new, 0 updated, 8,125 unchanged.
- [x] Run the full suite and checks: 112 tests passed, no skips locally and on SQLite/PostgreSQL Docker; Ruff and Django checks passed.
- [x] Verify the production settings profile with `check --deploy`: zero issues.
- [x] Run discovery and independent live audit; verify Austin–Dallas and Miami–Ellensburg with real prices.
- [x] Validate the collection and execute all six request bodies against actual HTTP endpoints.
- [ ] Import the collection/environment in your Postman GUI before recording.
- [x] Verify both Leaflet routes, ordered markers, source prices, attribution and approximation notices.
- [x] Build/start Docker and verify import, actual HTTP API, health and test commands.
- [x] Review Git staging/ignore boundaries; no staged secrets, local DB or original dataset.
- [x] Create the selected GitHub repository, commit the reviewed source and push main; private files excluded.
- [x] Fill in the actual verified GitHub URL; CI succeeded.
- [ ] Rehearse the script within five minutes, record and upload Loom, then fill in its actual URL.
- [x] Include dataset limitations, departure price convention, public provider limitations and test results.
- [x] Deploy the actual reviewed source to free Render web/PostgreSQL services in the approved Sakina workspace.
- [x] Upload the original CSV privately; verify actual hosted import logs and health counts.
- [x] Audit both real public routes, source prices, Census coordinates, geometry/order/range/cost and cache reuse.
- [x] Verify hosted Leaflet markers/popup/attribution and rendered Swagger operations/static files.

The currently running demo uses Docker at `http://127.0.0.1:8000/demo/`.
Stop Docker before starting the local Python server on the same port.
The timeout example was verified using a temporary opt-in container; the main service
retains its disabled-by-default setting. See `docs/verification.md` for all actual results.

Render is live at the URLs above. Its PostgreSQL database expires **13 November 2026**;
free web instances sleep after 15 idle minutes. Wake and verify the service shortly
before assessment review. No paid upgrade is authorized. The unused earlier free
database in Shyan's workspace was left untouched after the user switched to Sakina's
Dashboard account. Loom recording/upload and Postman GUI rehearsal remain unfinished.
