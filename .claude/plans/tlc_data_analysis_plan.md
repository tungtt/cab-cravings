# Plan: TLC Trip Data Exploratory Analysis

## Context

Before building synthetic identity profiles (Stage 1) and taxi mobility features (Stage 2), we need to understand the raw data deeply. Five parquet files are available covering January–February 2025 across four fleet types. This EDA notebook will drive decisions about: which fleet types to include, what quality filters to apply, which spatial/temporal features are feasible, and how to harmonize schemas across fleet types.

---

## Fleet Grouping Model

The four fleets form two operationally distinct groups. Analysis must respect this — cross-group field comparisons are only valid after explicit normalization.

| Dimension | Metered group (Yellow + Green) | Dispatched group (FHV + FHVHV) |
|---|---|---|
| Pricing | Taximeter (metered fare) | Dynamic / algorithmic |
| Fare field | `fare_amount` → `total_amount` | `base_passenger_fare` (fhvhv only; fhv has no fare) |
| Distance | `trip_distance` (taximeter-reported, miles) | `trip_miles` (GPS, fhvhv only; absent in fhv) |
| Passenger count | `passenger_count` (both) | Absent in both |
| Operator ID | `VendorID` (meter vendor) | `hvfhs_license_num` / `dispatching_base_num` |
| Shared-ride | Not applicable | `SR_Flag` (fhv), `shared_request/match_flag` (fhvhv) |

The only fields that are directly comparable **across groups** are TLC zone IDs and timestamps — both use the same 263-zone system and the same UTC timezone.

---

## Cross-Fleet Feature Extraction Approach

No user ID exists in any fleet. Stage 1 (identity resolution) will fingerprint pseudo-users by **zone × time behavioral clusters**. For cross-fleet user linking to work:

1. Zone IDs must be a consistent foreign key across all four fleets and the shapefile → Task 16
2. Both groups must have meaningful geographic overlap (shared zones) → Task 14
3. Fare signals must be normalizable across groups if used in a unified feature → Task 15

A pseudo-user may have trips in both the metered and dispatched groups. Features from each group are computed separately and combined at the user level. Zones served only by one group (e.g., outer-borough zones exclusive to fhvhv) will produce group-specific features only.

---

## Data Snapshot

| File | Rows | Cols | Group |
|------|------|------|-------|
| yellow_tripdata_2025-01.parquet | 3,475,226 | 20 | Metered |
| green_tripdata_2025-01.parquet | 48,326 | 21 | Metered |
| fhv_tripdata_2025-01.parquet | 1,898,108 | 7 | Dispatched |
| fhvhv_tripdata_2025-01.parquet | 20,405,666 | 25 | Dispatched |

---

## Output

`notebooks/01_tlc_eda.ipynb` — one section per task, each ending with a **Key Finding** markdown cell.

---

## Decisions

- Exclude FHV. Clear, supported, no counter-argument.
- Include FHVHV, but treat it as a separate feature branch. The cold-start hypothesis specifically requires outer-borough dispatched-trip data — excluding fhvhv degrades that hypothesis from "rideshare-only users vs popularity baseline" to "Manhattan-taxi-only users vs popularity baseline," which is a much less compelling test. The schema complexity is real but manageable in Stage 2. Run Tasks 14 and 15 first — their results will determine whether the feature engineering needs one pipeline with normalization or two independent pipelines that merge at the user level.

---

## Analysis Tasks

### 1. Schema Harmonization Assessment
**What:** Three-part analysis:
1. **Metered group** — Yellow vs Green side-by-side. Identify shared fields vs fleet-specific ones (`Airport_fee` yellow-only, `ehail_fee` + `trip_type` green-only). Verdict: can they be pooled into one metered DataFrame?
2. **Dispatched group** — FHV vs FHVHV side-by-side. Document which fhv fields are recoverable vs structurally absent. Confirm FHVHV is the operative dispatched-group source.
3. **Cross-group common core** — Map only the genuinely comparable fields (zone IDs, timestamps). Label `fare_amount` ↔ `base_passenger_fare` as "analogous, not equivalent" and `trip_distance` ↔ `trip_miles` as "same unit (miles), different measurement method."

**Rationale:** Metered and dispatched groups have different economic models. A naive cross-group schema merge would silently misrepresent both groups' data to Stage 2. Knowing the within-group compatibility now prevents rework at feature engineering time.

---

### 2. Null / Missing Value Audit
**What:** Per-column null counts and null rates for every file. Heatmap rows grouped by fleet group (metered together, dispatched together). Flag columns ≥ 20% nulls.

**Rationale:** Visual grouping distinguishes data quality issues (unexpected nulls in mostly-complete columns) from structural absences (fhv having no fare or distance fields at all). fhv's extreme location sparsity is a structural absence, not a data quality problem — the grouping makes this clear at a glance.

---

### 3. FHV Location Sparsity Decision Gate
**What:** Compute exact % non-null for `PUlocationID` and `DOlocationID` in fhv. Visualize which `dispatching_base_num` values have location data vs not. Apply threshold: if PU non-null < 30%, exclude fhv from zone-based features.

**Rationale:** FHV has 1.9M rows but task 3 result (17% PU non-null) confirms it cannot contribute to zone-based mobility features. The per-base breakdown identifies whether any sub-operator within fhv is recoverable.

---

### 4. Fleet Mix & Volume Overview
**What:** Three-level breakdown:
1. Group totals: metered (yellow + green) vs dispatched (fhv + fhvhv) — shows the 4:1 dispatched dominance
2. Within-group: yellow vs green (green = 1.4% of metered); fhvhv vs fhv
3. FHVHV platform: Uber (HV0003) vs Lyft (HV0005) vs Via (HV0004) vs Juno (HV0002)

**Rationale:** Presenting green (48K) and fhvhv (20.4M) as visual peers on the same axis makes green invisible and implies false comparability. Group-first hierarchy shows the scale within each group and the relative dominance between groups.

---

### 5. Temporal Distributions (Hour-of-Day & Day-of-Week)
**What:**
- **Plot A — Metered group:** Yellow and green overlaid (normalised %). Directly tests poolability. Annotate meal-time windows: lunch (11–14h), dinner (17–21h), late-night (22–02h).
- **Plot B — Dispatched group:** fhvhv hour-of-day with same meal-time annotations. fhv kept separate.
- **Plot C — Cross-group:** Metered aggregate vs fhvhv aggregate overlaid. Timestamps are directly comparable across groups — this tests whether the two populations use different services at different times.
- Day-of-week: group overlays (metered vs fhvhv) rather than per-fleet bars.

**Rationale:** The old 4-subplot layout implied all four fleets are equally independent. Overlaying yellow/green tests the pooling hypothesis. The cross-group temporal overlay is valid (timestamps are comparable across groups even when fares are not) and reveals whether metered and dispatched riders are the same population with different preferences or distinct populations.

---

### 6. Zone Coverage Audit (Metered Group)
**What:** For each metered fleet (yellow, green) and each role (pickup, dropoff): count distinct `PULocationID` / `DOLocationID` values and classify them as **known** (ID present in the 263-zone TLC reference), **unknown** (ID not in the reference), or **unused** (reference zones absent from this month's trips). Surface any unknown IDs explicitly.

**Rationale:** Zone IDs are the primary join key between trip records and `taxi_zones.shp`. Unknown IDs that slip into zone-based joins produce silent row loss or erroneous zone assignments in Stage 2. Scoped to the metered group here as a preliminary audit; Task 16 extends the same verification cross-fleet (metered + fhvhv) and confirms whether unknown IDs are systematic (e.g., TLC staging zones 264/265) or isolated data errors.

---

### 7. Dining-Neighborhood Dropoff Concentration
**What:** Top-30 most frequent `DOLocationID` zones during dinner hours (17–21h) on weekdays for yellow + fhvhv independently. Join with `taxi_zones.shp` for zone names. Compute dinner concentration score = dinner dropoffs / all-hour dropoffs per zone.

**Rationale:** The strongest mobility signal for restaurant recommendation is not total trip volume but whether a zone is disproportionately a dinner-hour destination. Running separately per group checks whether the two groups agree on which zones are restaurant-dense — agreement strengthens the signal, disagreement reveals group-specific dining populations.

---

### 8. Pickup/Dropoff Zone Coverage
**What:** Count distinct PU/DO zone IDs per fleet. Choropleth of trip density per zone (yellow and fhvhv separately). Identify zones in shapefile with zero trips in either group.

**Rationale:** Zone coverage asymmetry (yellow concentrates in Manhattan, fhvhv covers all 5 boroughs) determines where mobility features will be available and reliable. Zones with zero coverage are cold-start blind spots for Stage 3.

---

### 9. Trip Distance & Duration Distributions
**What:** Histograms of `trip_distance` (yellow/green) and `trip_miles` (fhvhv) separately — same unit but different measurement methods, so plot side-by-side not overlaid. Computed `trip_duration = dropoff - pickup` in minutes for all groups. Flag trips with duration < 1 min or > 180 min, distance = 0, or negative duration.

**Rationale:** Normalization bounds for distance and duration features must be set per group because the measurement methods differ (taximeter vs GPS). Trips with invalid distance/duration are data errors to filter before Stage 2.

---

### 10. Fare & Spend Distribution
**What:** Distribution of `fare_amount` / `total_amount` (yellow/green) and `base_passenger_fare` (fhvhv) separately. Flag negatives and extreme outliers (>$500). Median fare by borough within each group.

**Rationale:** Rider spend is a proxy for neighborhood price tier. Groups must be analyzed separately because their fare structures are not equivalent. Borough-level median fare within each group reveals whether the geographic coverage asymmetry also implies a spend-tier asymmetry.

---

### 11. Passenger Count & Shared Ride Analysis
**What:** `passenger_count` value_counts for yellow/green. `shared_request_flag` and `shared_match_flag` distributions for fhvhv.

**Rationale:** Group rides are ambiguous for individual preference modeling. The two groups measure this differently — metered uses passenger count, dispatched uses explicit shared-ride flags. Understanding the share of ambiguous trips in each group determines whether to exclude them or weight them down.

---

### 12. CBD Congestion Fee Characterization
**What:** Count trips with `cbd_congestion_fee > 0` across yellow, green, fhvhv. Map which zones generate congestion-fee trips. Show pre/post Jan 5, 2025 effect in yellow January data.

**Rationale:** CBD congestion pricing is present in all three groups that have the field (yellow, green, fhvhv — not fhv). It is a potential confound (inflates total_amount for Manhattan-bound trips) and a potential feature (CBD entry = high-density restaurant area). Characterizing its scope and spatial distribution informs both normalization strategy and feature engineering.

---

### 13. Metered Group Poolability (Yellow + Green)
**What:** Compare yellow and green on: (a) pickup zone distribution overlap — what fraction of green zones appear in yellow? (b) fare and distance distributions after normalization — are they compatible? Produce a binary verdict: pool or keep separate.

**Rationale:** Green has only 48K rows (1.4% of the metered group). If green's zone distribution is a subset of yellow's, pooling adds noise but no new signal and green can be merged in. If green covers distinct outer-borough zones not in yellow, keeping separate preserves geographic signal. The data dictionary confirms green has `trip_type` and `ehail_fee` that yellow lacks — the pooling decision must explicitly handle these columns (fill with NaN or drop).

---

### 14. Cross-Fleet Zone Overlap
**What:** For each of the 263 TLC zones: count trips from metered group (yellow + green) and from fhvhv. Classify each zone as: metered-only, fhvhv-only, or shared. Produce overlap table and bar chart by category.

**Rationale:** This is the direct feasibility test for the cross-fleet joining approach. Stage 1 can only link a pseudo-user across fleet groups at zones served by both groups. If outer-borough zones are exclusively fhvhv, then cross-fleet user linking is limited to Manhattan/airport zones. This scopes the identity model's reach before Stage 1 is built.

---

### 15. Fare-Per-Mile Normalization Feasibility
**What:** Compute `fare_per_mile = fare_amount / trip_distance` (yellow/green) and `fare_per_mile = base_passenger_fare / trip_miles` (fhvhv). Plot distributions side-by-side. Assess whether they converge enough to support a single cross-fleet spend-intensity feature or must remain group-specific.

**Rationale:** The data dictionary marks `fare_amount` and `base_passenger_fare` as "analogous but not equivalent." Per-mile rate normalization strips out distance and partially corrects for the metered-vs-dynamic pricing difference. If distributions converge after normalization, a unified spend feature is feasible for Stage 2. If they remain bimodal, Stage 2 must engineer group-specific fare features.

---

### 16. Zone System Consistency Verification
**What:** Collect all distinct `PULocationID` / `DOLocationID` values from each fleet. Compare against the 263 zone IDs in `taxi_zones.shp`. Report: (a) zone IDs in parquet but not in shapefile (e.g., zones 264/265 are airport staging areas not in the public shapefile), (b) shapefile zones absent from all fleet data (coverage blind spots). Flag fhv's float-typed location columns as a type-mismatch risk.

**Rationale:** The entire cross-fleet joining approach depends on zone IDs being a consistent foreign key. If phantom zone IDs exist (zones 264/265 are documented TLC staging areas that do appear in real data), zone-based joins will silently drop valid trips. This must be confirmed before any zone join is built in Stage 2.

---

## Critical Files

- `data/raw/tlc_trips/yellow_tripdata_2025-01.parquet`
- `data/raw/tlc_trips/yellow_tripdata_2025-02.parquet`
- `data/raw/tlc_trips/green_tripdata_2025-01.parquet`
- `data/raw/tlc_trips/fhv_tripdata_2025-01.parquet`
- `data/raw/tlc_trips/fhvhv_tripdata_2025-01.parquet`
- `data/raw/tlc_trip_taxi_zones/taxi_zones.shp`
- `docs/tlc_ref/tlc_data_dictionary_comp.md`

## Output Notebook

`notebooks/01_tlc_eda.ipynb`

One section per task. Each section ends with a **Key Finding** markdown cell summarizing the result and its implication for downstream stages.

## Verification

```bash
source .cabvenv/bin/activate
jupyter nbconvert --to notebook --execute --output 01_tlc_eda.ipynb notebooks/01_tlc_eda.ipynb
```

---

## Appendix 1 - Rationale for excluding FHV and including FHVHV

### FHV: Yes, exclusion is clear

The data leaves no ambiguity:

- PU location: 17% non-null — 83% of FHV trips have no pickup zone. Zone × time behavioral clustering (the entire identity model) is impossible without pickup zones.
- No fare, no distance — structurally absent, not nulls. FHV contributes nothing to spend or distance features.
- Dinner-hour share: 18.3% — weakest dining signal of all four fleets, consistent with black-car / pre-scheduled usage (airport runs, corporate accounts) rather than discretionary dining trips.
- Only 2 fields shared with fhvhv — it's not really in the same "dispatched group" in any meaningful operational sense. It's legacy black-car data with a minimal schema.

The ~320K trips with usable PU zones (~17% of 1.9M) could theoretically be kept, but the engineering cost of handling a partially-useful dataset that shares no fare/distance signals with anything else is not justified.

### FHVHV: Genuinely contested — here are the stakes

The case for including it

  ┌──────────────┬───────────────────────────────────────────────────────────────────────────────────────────────┐
  │    Factor    │                                            Detail                                             │
  ├──────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Volume       │ 20.4M trips — 79% of all trips in the dataset. Excluding it means the entire pipeline runs on │
  │              │  3.5M yellow + 48K green rows.                                                                │
  ├──────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
  │              │ The PRD's second hypothesis ("taxi-only users with no Yelp history") is almost exclusively an │
  │ Cold-start   │  fhvhv story. Outer-borough users who have never hailed a yellow cab are exactly the          │
  │ hypothesis   │ population fhvhv captures. Exclude fhvhv and the cold-start test becomes "can Manhattan       │
  │              │ yellow-taxi patterns beat a popularity baseline" — a weaker, less interesting test.           │
  ├──────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Geographic   │ Yellow concentrates in Manhattan and airports. fhvhv covers all 5 boroughs. Task 14 (not yet  │
  │ coverage     │ run) will quantify this, but the asymmetry is expected and large.                             │
  ├──────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Schema       │ request_datetime → pickup_datetime gap = wait time = implicit demand signal.                  │
  │ richness     │ shared_request_flag vs shared_match_flag = intent vs reality. trip_time is GPS-accurate       │
  │              │ duration. These are signals yellow doesn't have.                                              │
  ├──────────────┼───────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Dinner       │ 28.5% — only 4 points below metered's 32.9%. Strong enough to extract dining patterns from.   │
  │ signal       │                                                                                               │
  └──────────────┴───────────────────────────────────────────────────────────────────────────────────────────────┘

The case for excluding it

Factor: Schema incompatibility
Detail: fare_amount ≠ base_passenger_fare (metered rate vs dynamic surge pricing). trip_distance ≠ trip_miles (taximeter vs GPS). Cross-group feature engineering requires an explicit normalization layer in Stage 2 — this is non-trivial.

  ────────────────────────────────────────
  Factor: Population mismatch risk
  Detail: Uber/Lyft riders skew younger, outer-borough, and different income tier than yellow taxi riders. If the
  Yelp
    reviewer population overlaps more with metered taxi users, fhvhv may produce mobility features that don't link to

    any Yelp profiles — adding noise, not signal. The 30% controlled overlap in Stage 1 is synthetic, so this isn't
    about real linkage — but the feature distribution assumptions matter.
  ────────────────────────────────────────
  Factor: No passenger_count
  Detail: Can't distinguish solo trips (clear individual signal) from group trips (ambiguous). shared_match_flag is a

    partial substitute but different semantics.
  ────────────────────────────────────────
  Factor: Fare instability
  Detail: Dynamic pricing means base_passenger_fare varies with surge multipliers. The same zone × time pattern will
    have very different fare values on a Friday night vs Tuesday morning — making spend-tier inference noisier than
    metered's stable rate codes.
  ────────────────────────────────────────
  Factor: Stage 2 complexity
  Detail: Two schemas means two feature engineering branches that must be reconciled at the user level. A simpler
    pipeline (metered only) is easier to debug, faster to iterate, and produces cleaner results for a POC.

---

What the current EDA cannot yet answer

The strongest argument for including fhvhv hinges on Task 14 (cross-fleet zone overlap). If yellow and fhvhv serve largely the same zones, a pseudo-user could plausibly appear in both datasets and cross-fleet linking is feasible.

If the zone distributions are largely disjoint (expected: yellow = Manhattan, fhvhv = everywhere), then fhvhv and metered users are essentially separate populations — meaning the feature vectors from each group can't reinforce each other, and the fusion model must handle them as distinct signals from the start.

Task 15 (fare-per-mile normalization) is the other open question. If fare_amount / trip_distance and base_passenger_fare / trip_miles converge after normalization, a unified spend signal is feasible. If they remain bimodal, every fare feature must be duplicated per group.
