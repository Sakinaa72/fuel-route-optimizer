# Separate geographic reference data

`python manage.py prepare_locations` downloads two official, fixed-vintage US Census
Bureau archives, independently of the assessment price CSV:

- [2025 National Places Gazetteer](https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_place_national.zip)
- [2025 US states, cartographic boundaries at 1:500,000](https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_state_500k.zip)

The command loads place internal-point coordinates into SQLite, writes
`us-states.geojson`, caches downloaded archives in `raw/`, and records source URLs,
SHA-256 digests and counts in `manifest.json`. Generated files are excluded from Git;
fresh checkouts reproduce them using the command. Existing raw archives are reused;
`--refresh` explicitly redownloads them. No network calls occur while importing station
prices or looking up stations during API requests.

Offline setup is supported using independently downloaded archives:

```bash
python manage.py prepare_locations \
  --places-zip /path/to/2025_Gaz_place_national.zip \
  --states-zip /path/to/cb_2025_us_state_500k.zip
```

The 2025 Gazetteer uses `|` delimiters; older tab-delimited files are also accepted.
We strip legal suffixes such as `city`/`CDP` from Census place names only, preserving
actual city names such as Kansas City and Oklahoma City. We normalize whitespace, punctuation, diacritics and
`St.`/`Ft.`/`Mt.`. Matching requires a unique normalized city/state pair. Ambiguous
names are unresolved rather than silently assigned to the wrong place. No fuzzy
matching or bulk online geocoding is used. Unincorporated locations absent from the
Places Gazetteer remain unresolved. Reimport prices after refreshing place data.

Gazetteer `INTPTLAT`/`INTPTLONG` are representative internal points, commonly referred
to here as city centroids, not mathematically exact centroids or truck stop pump
coordinates. The API exposes `city_centroid_approximation` and a Census GEOID reference.
All 50 states and DC are supported; territories are excluded. Direct coordinate country
checks use Census cartographic polygons, not a broad rectangular bounding box. The
generalized coastline/border can reject valid points extremely near a boundary; use a
supported local city or a higher-resolution boundary dataset if needed.

These are public US government geographic reference data, separate from any restricted
Census microdata. See the [Census public access policy](https://www2.census.gov/foia/ds_policies/ds027.pdf)
and [citation guidance](https://www.census.gov/about/policies/citation.html).
Preserve source attribution; do not imply Census endorsement. Assessment prices have separate terms.
