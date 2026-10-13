# Submission checklist

- GitHub URL: **[fill in after successful publication]**
- Loom URL: **[fill in after uploading the recording]**

- [x] Locate/copy the original CSV unchanged; validate all 8,151 source rows.
- [ ] Obtain redistribution permission before including the original CSV in a publication.
- [x] Run migrations, Census preprocessing and strict import locally and in a fresh container DB.
- [x] Record counts: 8,125 imported, 26 exact duplicates, 0 rejected; 7,033 approximate / 1,092 unresolved.
- [x] Verify idempotent reimport: 0 new, 0 updated, 8,125 unchanged.
- [x] Run the full suite and checks: 100 tests passed, no skips; Ruff and Django checks passed locally/in Docker.
- [x] Run discovery and independent live audit; verify Austin–Dallas and Miami–Ellensburg with real prices.
- [x] Validate the collection and execute all six request bodies against actual HTTP endpoints.
- [ ] Import the collection/environment in your Postman GUI before recording.
- [x] Verify both Leaflet routes, ordered markers, source prices, attribution and approximation notices.
- [x] Build/start Docker and verify import, actual HTTP API, health and test commands.
- [x] Review Git staging/ignore boundaries; no staged secrets, local DB or original dataset.
- [ ] Create a GitHub repository, commit the reviewed project and push the configured remote.
- [ ] Fill in the actual GitHub URL; never submit an invented link.
- [ ] Rehearse the script within five minutes, record and upload Loom, then fill in its actual URL.
- [ ] Include dataset limitations, departure price convention, public provider limitations and test results.

The currently running demo uses Docker at `http://127.0.0.1:8000/demo/`.
Stop Docker before starting the local Python server on the same port.
The timeout example was verified using a temporary opt-in container; the main service
retains its disabled-by-default setting. See `docs/verification.md` for all actual results.
