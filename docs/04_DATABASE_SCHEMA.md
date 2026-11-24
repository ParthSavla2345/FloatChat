# Database Schema

## Primary table: `argo_profiles`

The DuckDB table stores individual profile observations, one row per measurement depth sample.

| Column | Type | Purpose |
| --- | --- | --- |
| `file_name` | VARCHAR | Source NetCDF filename |
| `float_id` | VARCHAR | Processed float identifier for the recovered pipeline |
| `profile_number` | BIGINT | Sequence number within the file |
| `cycle_number` | BIGINT | Argo cycle number |
| `datetime` | TIMESTAMP WITH TIME ZONE | UTC-normalized observation time |
| `latitude` | DOUBLE | Observation latitude |
| `longitude` | DOUBLE | Observation longitude |
| `depth` | DOUBLE | Pressure/depth in metres or decibars |
| `temperature` | DOUBLE | Temperature measurement |
| `salinity` | DOUBLE | Salinity measurement |

## Important identifier distinction

The project must not assume that `file_name` or `float_id` are the same as the true ARGO float identifier.

- `file_name`: source file name; useful for provenance only.
- `float_id`: processed identifier created in the extraction pipeline.
- `PLATFORM_NUMBER`: actual source variable from the NetCDF, which is the authoritative WMO-like float identifier when available.

## Metadata table

`float_metadata` aggregates the observed range for each processed float, capturing:

- `float_id`
- `total_profiles`
- `observation_start`
- `observation_end`
- `latitude_min` and `latitude_max`
- `longitude_min` and `longitude_max`
- `depth_min` and `depth_max`
- `variables_available`
- `total_observations`

## Query guidance

- Spatial queries should filter on `latitude` and `longitude`.
- Temporal queries should filter on `datetime` in UTC.
- Nearest-float queries should group by `float_id`, not by every row or every `profile_number`.
- Region filters should rely on coordinate bounds and Haversine calculation rather than filename assumptions.

## Execution notes

The database is used as a read-only layer. write operations are rejected by `backend/services/duckdb_service.py` and all retrieval logic should use parameterized SQL queries.
