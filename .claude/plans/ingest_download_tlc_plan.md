# Plan: TLC Trip Data Download Script

## Context
The project needs raw TLC trip data in `data/raw/tlc_trips/` to feed Stage 1 (identity resolution) and Stage 2 (taxi feature engineering). No ingestion utilities exist yet. NYC TLC hosts parquet files at a CloudFront CDN with a predictable URL pattern.

## Approach

Create `src/ingest/download_tlc.py` as a standalone runnable module:
- `python -m src.ingest.download_tlc --from-year 2022 --to-year 2023`
- Downloads yellow and green taxi parquet files by default
- Skips files that already exist (idempotent)
- Silently skips months that return HTTP 404 (TLC data availability varies)
- Cleans up partial downloads on failure

## URL Pattern

```
https://d37ci6vzurychx.cloudfront.net/trip-data/{color}_tripdata_{YYYY}-{MM}.parquet
```
Colors: `yellow`, `green`

## Files to Create

### `src/ingest/__init__.py`
Empty, makes `src/ingest` a package.

### `src/ingest/download_tlc.py`

**CLI arguments:**
| Argument | Type | Required | Default | Description |
|---|---|---|---|---|
| `--from-year` | int | yes | — | First year to download |
| `--to-year` | int | yes | — | Last year to download (inclusive) |
| `--from-month` | int | no | `1` | Start month in `from-year` |
| `--to-month` | int | no | `12` | End month in `to-year` |
| `--types` | str (multi) | no | `yellow green` | Taxi types to download |
| `--output-dir` | path | no | `data/raw/tlc_trips` | Override output directory |

**Logic:**
```
for year in [from_year .. to_year]:
    month_range = [from_month..12] if year==from_year else [1..12]
                  clamped to [1..to_month] if year==to_year
    for month in month_range:
        for color in types:
            dest = output_dir / f"{color}_tripdata_{year}-{month:02d}.parquet"
            if dest.exists(): skip
            download url -> dest (urllib.request, no extra deps)
            on 404: skip silently with note
            on other error: print warning, remove partial file, continue
```

**Output directory** resolved relative to the project root (two `parent` steps up from `__file__`) so the script works regardless of working directory.

**Dependencies:** stdlib only (`urllib.request`, `argparse`, `pathlib`) — no new deps needed.

## Critical Files

- `src/ingest/__init__.py` — new, empty
- `src/ingest/download_tlc.py` — new, main script
- `data/raw/tlc_trips/` — output directory (created at runtime)

## Verification

```bash
# Dry run: download one month of yellow only
python -m src.ingest.download_tlc --from-year 2023 --to-year 2023 --from-month 1 --to-month 1 --types yellow

# Verify file landed
ls data/raw/tlc_trips/
# Expected: yellow_tripdata_2023-01.parquet

# Verify parquet is valid
python -c "import pandas as pd; df = pd.read_parquet('data/raw/tlc_trips/yellow_tripdata_2023-01.parquet'); print(df.shape)"

# Re-run to confirm idempotency (should print "Skip (exists): ...")
python -m src.ingest.download_tlc --from-year 2023 --to-year 2023 --from-month 1 --to-month 1 --types yellow
```
