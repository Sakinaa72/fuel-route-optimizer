# Assessment price data

Place the **original supplied CSV**, unchanged, at `data/fuel-prices-for-be-assessment.csv`.
The original file is now present and imported. It was copied byte-for-byte from the
assessment file in Downloads; no source rows were edited or replacement prices seeded.
SHA-256: `c704371f141ded9c54df6c32d488a0ba2ceb589f88c936c967daa5330e0cd241`.

Expected headers: `OPIS Truckstop ID`, `Truckstop Name`, `Address`, `City`, `State`,
`Rack ID`, `Retail Price`. CSV uses UTF-8 (a BOM is accepted). Prices must be positive
USD/US-gallon decimals for US planning, at most eight decimal places and no greater than
$100. The supplied file contains valid eight-decimal prices, preserved in storage and API output.

Final import: 8,151 source rows → 8,125 records, 26 exact duplicates, 0 rejected,
0 updated and 0 unchanged on first load. An identical reimport loads/updates 0 and
skips 8,125 unchanged records. Geographic coverage: 7,033 approximate coordinates;
1,092 unresolved (620 Canadian provinces, 428 unmatched US places, 44 ambiguous US places).
US coverage is 7,033 / 7,505 distinct US records (93.71%).

```bash
python manage.py migrate
python manage.py prepare_locations
python manage.py load_fuel_prices --csv data/fuel-prices-for-be-assessment.csv
```

The source's redistribution terms are unknown, so `.gitignore` and `.dockerignore`
exclude it. An evaluator must provide it separately unless the assignment owner
explicitly permits redistribution. Never replace it with the synthetic test fixtures.

An import validates the entire file before touching stations. A successful strict import
is an authoritative snapshot: absent records are removed **inside the same transaction**.
An invalid row aborts the import and preserves previous records. `--skip-invalid` is an
explicit non-destructive merge option: valid rows are merged, invalid rows reported, and
absent existing records kept. Such a merge can retain older prices; strict snapshots are
recommended for demonstrations.

Exact duplicates are rows with equal trimmed source ID, name, address, city, normalized
state/province, rack ID and numerically equal price. Their SHA-256 record keys are unique.
Different IDs, addresses, names or prices remain distinct. Source IDs are **not** unique.
Reimporting identical data does not duplicate records; updated place coordinates update
existing records. Names/addresses preserve case. The command prints JSON counts and
writes unresolved/ambiguous matches to `var/unresolved-stations.csv` by default.
Known Canadian province codes in the supplied dataset are valid source records, retained
with unresolved coordinates and `unsupported_region` in the report. They are never
silently matched to a US place or used to price a US route.
