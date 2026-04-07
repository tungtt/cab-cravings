# Google Local EDA Plan

## Context

Google Local Data (2021), a McAuley Lab dataset covering 666M reviews and 4.9M US businesses up to September 2021. The New York state 10-core subset (`review-New_York_10.json.gz`) contains 18,661,975 reviews, pre-filtered so every user and business has at least 10 interactions. Files are stored at `data/raw/googlelocal/`. The existing `notebooks/02_yelp_eda.ipynb` becomes `notebooks/02_google_eda.ipynb`.

## Schema Reference

### Review file: `data/raw/googlelocal/review-New_York_10.json.gz`

| Field | Type | Notes |
|---|---|---|
| `user_id` | str | reviewer ID |
| `name` | str | reviewer display name |
| `time` | int | unix timestamp in milliseconds |
| `rating` | int | 1-5 star rating |
| `text` | str | review text, may be null |
| `pics` | list | photo URL dicts, may be null |
| `resp` | dict | business response with `time` and `text` keys, may be null |
| `gmap_id` | str | business ID, join key to metadata |

No `review_id` field. Use `(user_id, gmap_id, time)` as a composite key for deduplication.

### Metadata file: `data/raw/googlelocal/meta-New_York.json.gz`

| Field | Type | Notes |
|---|---|---|
| `name` | str | business name |
| `address` | str | full address string |
| `gmap_id` | str | primary key |
| `description` | str | free-text description, often null |
| `latitude` | float | geographic coordinate |
| `longitude` | float | geographic coordinate |
| `category` | list[str] | category tags as a list |
| `avg_rating` | float | pre-aggregated average rating |
| `num_of_reviews` | int | pre-aggregated review count |
| `price` | str | "$", "$$", "$$$", or "$$$$", may be null |
| `hours` | list | nested day/time pairs, may be null |
| `MISC` | dict | arbitrary service attribute key-value pairs, may be null |
| `state` | str | BUSINESS STATUS string (e.g. "Closes soon"), NOT a US state abbreviation |
| `relative_results` | list | related business gmap_ids |
| `url` | str | Google Maps URL |

The `state` field is not a US state code. Geographic filtering must use `latitude`/`longitude`.

## File Loading Strategy

Both files are gzipped NDJSON. Use `pd.read_json(path, lines=True, chunksize=500_000, compression="gzip")` for streaming. The metadata file (272,189 businesses, all of New York state) is small enough to load in full and filter once in memory. The review file (18,661,975 rows) must be streamed in chunks. The NYC restaurant `gmap_id` set materialised in Task 1 gates all downstream review reads.

## Phase 1: Foundation

### Task 1 - NYC Restaurant Corpus Definition

**Objective:** Filter `meta-New_York.json.gz` to businesses physically in NYC with at least one restaurant/food category tag.

**Inputs:** `data/raw/googlelocal/meta-New_York.json.gz`

**Geographic filter:** Bounding box - latitude in [40.45, 40.92], longitude in [-74.26, -73.70]. Covers all five boroughs.

**Category filter:** The `category` field is a list. Flag businesses whose list contains at least one tag from a food seed set (e.g., "Restaurant", "Food", "Cafe", "Bar", "Pizza"). Report top-30 category tags across bbox-filtered businesses first to calibrate the seed set before finalising it.

**Analysis steps:**
- Load full metadata; apply bounding box filter; report pre/post counts at each step
- Among bbox-filtered businesses, count category tag frequencies; identify food-related tags
- Apply category filter; report final corpus size
- Approximate borough from coordinates (Manhattan: lat > 40.7 and lon > -74.02; Bronx: lat > 40.8 and lon < -73.83; etc.)
- Report `avg_rating` and `num_of_reviews` summary statistics (pre-aggregated in metadata)
- Report `price` field null rate and value distribution

**Output:** `data/processed/nyc_restaurant_gmap_ids.pkl` (set of gmap_ids). Summary table: total count, borough proxy breakdown, price tier coverage.

**Decision gate:** If NYC restaurant count < 5,000, widen the category seed set or expand the bounding box.

### Task 2 - Data Quality Audit

**Objective:** Measure null rates and structural issues across both files.

**Inputs:** `meta-New_York.json.gz` (full NYC restaurant subset); `review-New_York_10.json.gz` filtered to NYC restaurant `gmap_id`s.

**Analysis steps:**
- Null rates per field for both files (heatmap mirroring TLC EDA Task 2)
- `MISC` key frequency among NYC restaurants (analogous to Yelp `attributes`)
- `price` coverage: fraction of NYC restaurants with a price tier populated
- Review integrity: count duplicate `(user_id, gmap_id, time)` triples; written deduplication decision
- `resp` null rate: fraction of reviews with a business response
- `text` null rate: fraction of rating-only reviews with no text
- `time` range validation: confirm all timestamps parse cleanly to dates within 2000-2021

**Output:** Null-rate heatmap (two files). MISC key frequency table. Duplicate count. Deduplication decision.

### Task 3 - Temporal Coverage and TLC Alignment

**Objective:** Determine the review date range, document the temporal gap with TLC trip data, and establish the TLC download window and train/val/test split.

**Inputs:** `review-New_York_10.json.gz` filtered to NYC restaurant `gmap_id`s.

**Analysis steps:**
- Convert `time` (unix ms) to datetime: `pd.to_datetime(df["time"], unit="ms")`
- Plot review volume by year and by month-year (last 5 years)
- Report: earliest review, latest review, peak year, share of reviews by year
- Compute 2018+ share; use as anchor for TLC download window decision
- Count unique users with at least one NYC restaurant review after 2018
- Document the gap: Google data cuts off Sep 2021; TLC window starts Jan 2025 (roughly 3.5 years). Must appear in the final report. The synthetic identity layer absorbs this gap by construction.
- Document train/val/test temporal boundaries (see Output)

**Output:** Review timeline chart. Year-over-year table. Written temporal gap assessment.

**TLC download decision:** Download yellow + green + FHVHV trips, Jan 2019 - Sep 2021. 72.6% of all reviews fall in 2018-2020 (peak 2019: 32.0%); taxi mobility signals from the same era as ground-truth reviews are more predictive than trips 4 years later. The existing 2025-2026 TLC data is valid for cold-start inference only.

**Train/val/test split:**

| Split | Reviews | TLC trips | Share of reviews |
|---|---|---|---|
| Train | 2019 Jan - 2020 Dec | 2019 Jan - 2020 Dec | 45.7% |
| Validation | 2021 Jan - Jun | 2021 Jan - Jun | ~2-3% |
| Test | 2021 Jul - Sep | 2021 Jul - Sep | ~2% |

Pre-2019 reviews feed the interaction matrix as static prior history but are not training examples for the ranking model. Users with fewer than 5 total reviews are excluded from NDCG evaluation.

**COVID note:** 2020 shows a 57.2% review drop vs 2019 (real signal, not artifact). Flag a 2018-2019 train-only ablation in Epic 3 to test whether excluding the COVID year improves validation NDCG.

**Decision gate:** If fewer than 50% of reviews are from 2018 or later, flag data recency risk.

## Phase 2: Interaction Matrix

### Task 4 - Interaction Matrix Characterization

**Objective:** Measure sparsity, user/item counts, and review distribution shapes for the NYC restaurant subset.

**Inputs:** `review-New_York_10.json.gz` filtered to NYC restaurant `gmap_id`s.

**Note:** The 10-core guarantee applies to the full New York state dataset. After filtering to NYC restaurants only, some users may fall below 10 reviews.

**Note:** Total reviews (4,986,344), unique users (405,662), and unique restaurants (27,539) are already produced by the Task 2-3 streaming pass. Reuse those variables; do not trigger a second streaming pass.

**Analysis steps:**
- Reuse streaming-pass counts: total reviews, unique users, unique restaurants
- Compute matrix sparsity: `1 - (n_reviews / (n_users x n_restaurants))`
- Plot reviews-per-user and reviews-per-restaurant distributions (log scale)
- Report: fraction of users with >=5, >=10, >=20 NYC reviews post-corpus-filter
- Report: fraction of restaurants with >=10, >=20, >=50 reviews

**Output:** Sparsity figure. Two log-scale histograms. Threshold sensitivity table.

### Task 5 - Reviewer Population Sizing

**Objective:** Size the NYC restaurant reviewer population and segment by review density.

**Inputs:** Review data from the Task 4 streaming pass.

**Note:** Google Local has no separate user.json. User metadata is limited to `user_id` and `name` within review records. Use earliest review `time` per user as an "active since" proxy.

**Analysis steps:**
- Count total unique users with at least 1 NYC restaurant review
- Compute per-user: review count, earliest timestamp, latest timestamp, active years span
- Segment users: 1-4, 5-9, 10-24, >=25 NYC reviews
- Report segment sizes and cumulative review share

**Output:** Reviewer population table by segment. Active-since proxy distribution. Written population sizing note for Epic 1 synthetic population.

## Phase 3: Feature Distributions

### Task 6 - Category and Price Distributions

**Objective:** Validate cuisine and price tier features for Epic 2.

**Inputs:** NYC restaurant metadata subset (Task 1).

**Note:** Task 1 already produces `cat_series` (3,269 distinct tags, ranked by count). Reuse it directly; do not re-explode the category list.

**Analysis steps:**
- Reuse `cat_series` from Task 1; propose cuisine bucketing scheme (15-20 buckets)
- Report `price` distribution: "$", "$$", "$$$", "$$$$" value counts and null rate
- Cross-tabulate price tier vs. top cuisine buckets

**Output:** Top-30 category bar chart. Cuisine bucket proposal. Price tier bar chart. Price x cuisine heatmap. Written usability assessment.

### Task 7 - Geographic Distribution and TLC Zone Alignment

**Objective:** Assign NYC restaurants to TLC taxi zones and measure zone coverage to validate geographic fusion.

**Inputs:** NYC restaurant lat/lon from metadata (Task 1). TLC zone shapefile at `data/raw/tlc_trip_taxi_zones/taxi_zones.dbf` (zone reference) and `taxi_zones.shp` (geometry for spatial join).

**Note:** Latitude/longitude are available directly in metadata. No geocoding needed.

**Analysis steps:**
- Scatter plot of restaurant lat/lon colored by borough proxy
- Spatial join to TLC zones via shapefile; report: zones covered, zones with >=1 restaurant, zones with >=10 restaurants
- Choropleth of restaurant density per TLC zone
- Top-20 zones by restaurant count
- Cross-reference against TLC EDA Task 7 top-30 dinner-dropoff zones; compute overlap

**Output:** Restaurant scatter map. TLC zone choropleth. Zone coverage table. Overlap table vs. TLC dinner-dropoff zones.

**Decision gate:** If fewer than 100 of 263 TLC zones contain >=5 restaurants, flag geographic feature risk.

### Task 8 - Rating Distributions and User Bias

**Objective:** Characterise rating distributions to set the positive-label threshold for ranking models.

**Inputs:** Reviews filtered to NYC restaurants. `avg_rating` from metadata.

**Analysis steps:**
- Plot business-level `avg_rating` distribution from metadata (bar chart)
- Plot review-level `rating` distribution (1-5) from review records (bar chart)
- Compute per-user mean rating; plot distribution
- Report: fraction of reviews at >=4 stars, >=3 stars
- Flag users who give >=4 stars to >=80% of their reviews

**Output:** Two rating distribution bar charts. User average-rating distribution. Written label threshold recommendation for Epic 3.

### Task 9 - Temporal Dining Patterns

**Objective:** Characterise review timing to assess alignment with TLC temporal features.

**Inputs:** Reviews filtered to NYC restaurants.

**Note:** Monthly volume is already plotted in Task 3 (last 5 years). Task 9 focuses on sub-day and day-of-week patterns only.

**Analysis steps:**
- Convert `time` (unix ms) to America/New_York local time
- Plot review count by hour-of-day and day-of-week
- Overlay TLC dinner-dropoff window (17-21h) on the hour-of-day chart

**Output:** Two temporal distribution charts. Alignment note vs. TLC dinner-dropoff peak.

### Task 10 - Per-User Dining Geography

**Objective:** Measure how geographically concentrated each user's dining reviews are across TLC zones.

**Inputs:** Reviews filtered to NYC restaurants. TLC zone assignment from Task 7.

**Analysis steps:**
- For users with >=5 NYC reviews: count distinct TLC zones in review history
- Plot distribution of distinct zones per user (histogram)
- Compute zone concentration index: fraction of reviews in top-1, top-3, top-5 zones per user
- Report median and 75th percentile of distinct zones per user
- Report: fraction of users with >=50% of reviews concentrated in <=3 zones

**Output:** Distinct-zones histogram. Concentration index distribution. Written assessment of geographic feature viability.

## Task Summary

| # | Task | Phase | Priority |
|---|---|---|---|
| 1 | NYC Restaurant Corpus Definition | Foundation | P0 |
| 2 | Data Quality Audit | Foundation | P0 |
| 3 | Temporal Coverage and TLC Alignment | Foundation | P0 |
| 4 | Interaction Matrix Characterization | Interaction Matrix | P0 |
| 5 | Reviewer Population Sizing | Interaction Matrix | P0 |
| 6 | Category and Price Distributions | Feature Distributions | P0 |
| 7 | Geographic Distribution and Zone Alignment | Feature Distributions | P0 |
| 8 | Rating Distributions and User Bias | Feature Distributions | P0 |
| 9 | Temporal Dining Patterns | Feature Distributions | P1 |
| 10 | Per-User Dining Geography | Feature Distributions | P1 |

**Intentionally excluded:**
- Checkin and tip signal assessment: Google Local has no checkin or tip files
- User friend graph: not available in Google Local
- Review text / NLP: the POC uses structured features only

## Critical Files

| File | Role |
|---|---|
| `data/raw/googlelocal/review-New_York_10.json.gz` | Primary review source, 18,661,975 rows |
| `data/raw/googlelocal/meta-New_York.json.gz` | Business metadata, 272,189 businesses |
| `data/raw/tlc_trip_taxi_zones/taxi_zones.dbf` | Zone reference for spatial join (Tasks 7, 10) |
| `data/raw/tlc_trip_taxi_zones/taxi_zones.shp` | Zone geometry for spatial join (Tasks 7, 10) |
| `data/processed/nyc_restaurant_gmap_ids.pkl` | Task 1 output; gates all downstream reads |
| `notebooks/02_google_eda.ipynb` | Rename from `02_yelp_eda.ipynb` |

## Verification

1. Run Task 1: confirm `nyc_restaurant_gmap_ids.pkl` is written and count >= 5,000
2. Run Tasks 2-3: confirm heatmap renders and temporal gap documented
3. Run Tasks 4-5: confirm sparsity and population sizing numbers are plausible given the 10-core density guarantee
4. Run Tasks 6-8: confirm category chart, price tier chart, and rating charts render without errors
5. Run Tasks 9-10: confirm temporal charts align with TLC dinner-dropoff window; confirm zone concentration histogram is non-degenerate
