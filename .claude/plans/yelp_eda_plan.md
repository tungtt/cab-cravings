# Yelp EDA Plan

## Overall Objectives

The Yelp EDA has three roles in this project:

1. **Validate data feasibility.** Confirm the dataset contains enough NYC restaurant data, sufficiently dense user-restaurant interactions, and temporal coverage to support the two PRD hypotheses. Identify blockers early.

2. **Inform feature engineering (Epic 2).** Understand the distributions and structure of every feature we intend to compute - cuisine, price tier, geography, ratings, dining patterns - before writing the pipelines.

3. **Shape model design (Epic 3).** Quantify interaction matrix sparsity, cold-start extent, and geographic alignment with TLC taxi zones, so model choices are grounded in observed data rather than assumptions.

Tasks are grouped into three phases: **Foundation** (prerequisites for everything else), **Interaction Matrix** (core recommender concerns), and **Feature Distributions** (Epic 2 inputs). Tasks within each phase are independent and can run in parallel.

## Data Note: File Loading Strategy

The five NDJSON files total ~9 GB uncompressed. All tasks below should use `pandas.read_json(..., lines=True, chunksize=...)` or direct `pd.read_json` only after filtering to NYC restaurants. The NYC restaurant `business_id` set (from Task 1) should be materialized first and used to filter downstream files (reviews, checkins, tips) without loading them fully.

## Phase 1: Foundation

These three tasks must complete before any later task.

### Task 1 - NYC Restaurant Corpus Definition

**Objective:** Define the working corpus: all businesses in `business.json` that are in New York City and have "Restaurants" in their `categories` field.

**Rationale:** All downstream tasks - interaction matrix, feature distributions, geographic mapping - operate on this filtered subset. Without a clean corpus definition, we risk including non-restaurants, non-NYC businesses, or duplicate records. This is also the first gate: if the NYC restaurant count is too low, the POC scope narrows.

**Inputs:** `data/raw/yelp/yelp_academic_dataset_business.json`

**Analysis steps:**
- Filter by `state = "NY"` and `city` in common NYC spellings ("New York", "Brooklyn", "Queens", "Bronx", "Staten Island") - report counts per city variant to calibrate the filter
- Secondary filter: `categories` string contains "Restaurants"
- Count total businesses before and after each filter step
- Report borough distribution, `is_open` breakdown (open vs. permanently closed)
- Flag records with null `latitude`/`longitude` (needed for Task 7)

**Output:** A set of NYC restaurant `business_id`s (serialized) used by all downstream tasks. A summary table: total count, borough breakdown, open/closed split, null coordinate rate.

**Decision gate:** If NYC restaurant count < 5,000, revisit city filter and consider including New Jersey border areas.

### Task 2 - Data Quality Audit

**Objective:** Identify null rates, schema variability, and ID integrity issues across all five files before any feature computation.

**Rationale:** Downstream pipelines (Epic 2) will fail silently or produce biased features if we don't know in advance where the data is clean. For example, `attributes` in `business.json` is a sparse, heterogeneous dict — knowing which attribute keys appear on NYC restaurants determines whether price-tier (`RestaurantsPriceRange2`) is usable.

**Inputs:** All five NDJSON files. For review, user, checkin, tip: only records linked to the NYC restaurant corpus (Task 1 IDs).

**Analysis steps:**
- Null rates per field for each file (heatmap, mirroring Task 2 in the TLC notebook)
- For `business.attributes`: frequency of each attribute key among NYC restaurants; confirm presence of `RestaurantsPriceRange2`
- For `review`: duplicate `review_id` check; duplicate `(user_id, business_id)` pairs (a user reviewing the same place twice — decide on deduplication strategy)
- For `user`: `review_count` vs. actual review record count alignment (spot-check a sample)
- For `checkin.date`: confirm all values are comma-separated timestamp strings; measure parse failure rate

**Output:** Null-rate heatmap per file. Attribute key frequency table. Duplicate counts. Written decision on deduplication.

### Task 3 - Temporal Coverage & TLC Alignment

**Objective:** Determine the date range of reviews and checkins, and assess the temporal gap with the TLC trip data (Jan 2025 - Feb 2026).

**Rationale:** This is the most consequential feasibility gate. If Yelp reviews extend only to 2022 and TLC trips start in 2025, there is no contemporaneous overlap. While the synthetic identity layer does not require temporal alignment (it's constructed, not discovered), it limits the realism of the POC and any claim about real-world applicability. The result must be explicitly documented in the final report.

**Inputs:** `data/raw/yelp/yelp_academic_dataset_review.json` (filtered to NYC restaurants)

**Analysis steps:**
- Parse `date` field; plot review volume by year and by month-year
- Report: earliest review date, latest review date, year with peak volume
- Compute % of reviews from each year (2004–present)
- Report total unique users who have reviewed any NYC restaurant after 2020 (the most recent Yelp snapshot years)
- Note for the final report: the temporal gap between Yelp data and TLC trip period

**Output:** Review volume timeline chart. Summary table of year-over-year counts. Written assessment of temporal coverage.

**Decision gate:** If fewer than 50% of NYC restaurant reviews are from 2018 or later, flag a data recency risk in the report. (No change to scope - the synthetic identity layer absorbs this, but it must be documented.)

## Phase 2: Interaction Matrix

These tasks characterize the user-restaurant interaction structure - the core input to all recommendation models.

### Task 4 - User-Restaurant Interaction Matrix Characterization

**Objective:** Measure the sparsity, density, and shape of the NYC restaurant review matrix to determine which recommendation algorithms are viable and set modeling thresholds.

**Rationale:** Sparsity is the single most important number for a recommender POC. A matrix with 0.01% density supports matrix factorization; one with 0.001% forces fallback to content-based methods. The review threshold (e.g., users with >=5 reviews) controls how many users enter the primary hypothesis path vs. the cold-start path - this directly maps to the user-segment matrix in the PRD.

**Inputs:** `data/raw/yelp/yelp_academic_dataset_review.json` filtered to NYC restaurant corpus (Task 1 IDs).

**Analysis steps:**
- Count: total reviews, unique users, unique restaurants
- Compute matrix sparsity: `1 - (n_reviews / (n_users × n_restaurants))`
- Plot distribution of reviews per user (log scale; mark 1, 5, 10, 20 review thresholds)
- Plot distribution of reviews per restaurant (log scale)
- Report: % of users with >=1, >=3, >=5, >=10 NYC restaurant reviews
- Report: % of restaurants with >=5, >=10, >=20 reviews
- Identify the "long-tail" threshold for users and restaurants (Lorenz curve or 80/20 breakdown)

**Output:** Sparsity figure. Two log-scale histograms (reviews/user, reviews/restaurant). Threshold sensitivity table. Written recommendation for minimum review cutoffs to use in Epic 3.

### Task 5 - NYC Reviewer Population Sizing

**Objective:** Determine the total size of the NYC restaurant reviewer population and the split between data-rich users (>=N reviews, candidate for the primary hypothesis path) and data-sparse users (cold-start path).

**Rationale:** Epic 1 constructs a synthetic identity layer with a 30% controlled overlap between TLC riders and Yelp reviewers. To make that overlap realistic, we need to know the total size of the Yelp NYC reviewer population. This task also quantifies the cold-start problem: users with zero Yelp history but taxi data are the cold-start test case (US-3.2.2).

**Inputs:** `data/raw/yelp/yelp_academic_dataset_review.json` + `data/raw/yelp/yelp_academic_dataset_user.json`, both filtered to NYC restaurant reviewers.

**Analysis steps:**
- Count total unique users who have reviewed >=1 NYC restaurant
- Cross-join with `user.json`: report `yelping_since` distribution, total `review_count` (global, not just NYC), `average_stars` distribution
- Segment users by NYC restaurant review count: 1, 2–4, 5–9, 10–24, >=25 reviews - report user counts per segment
- Compute the fraction of users whose entire Yelp activity is concentrated in NYC restaurants (vs. reviewers who also review non-NYC or non-restaurant businesses) — this signals how "local" the reviewer population is

**Output:** Reviewer population table by review-count segment. `yelping_since` distribution chart. Written sizing recommendation for Epic 1 synthetic population.

## Phase 3: Feature Distributions

These tasks validate that the features planned in Epic 2 are computable from the data as-is.

### Task 6 — Cuisine & Price Tier Distributions

**Objective:** Understand the category (cuisine type) and price tier distributions among NYC restaurants to validate Epic 2 dining preference features (US-2.1.1).

**Rationale:** US-2.1.1 requires computing a cuisine distribution per user. If the category taxonomy is too fragmented (thousands of leaf categories) or too coarse (only 5 buckets), the feature engineering strategy changes. Price tier (`RestaurantsPriceRange2` attribute) is used as a user preference feature — this task confirms it's populated for enough restaurants to be useful.

**Inputs:** NYC restaurant subset of `yelp_academic_dataset_business.json` (Task 1 IDs).

**Analysis steps:**
- Explode the `categories` comma-separated string; count frequency of each category tag
- Report top 30 category tags among NYC restaurants; identify the dominant cuisine labels
- Propose a cuisine bucketing scheme (e.g., 15–20 buckets) based on the distribution
- Extract `RestaurantsPriceRange2` from `attributes`; report the null rate and distribution of values 1–4
- Cross-tabulate price tier vs. top cuisine buckets (are price tiers evenly distributed across cuisines?)

**Output:** Top-30 category bar chart. Proposed cuisine bucket mapping. Price tier bar chart. Price × cuisine heatmap. Written assessment: are both features usable as-is or does cleaning/bucketing need to be specified?

### Task 7 - Geographic Distribution & TLC Zone Alignment

**Objective:** Map NYC restaurant locations to TLC taxi zones and measure zone coverage, to validate the geographic fusion hypothesis (US-3.2.3) and the dining-radius feature (US-2.1.2).

**Rationale:** The primary mechanism connecting taxi mobility to restaurant recommendations is geographic: users are predicted to prefer restaurants in zones they frequently visit. If restaurant locations are poorly distributed across TLC zones (e.g., concentrated in just a few zones), the geographic feature loses discriminative power. This task tests that assumption directly.

**Inputs:** NYC restaurant lat/lon from `business.json` (Task 1). TLC taxi zone shapefile at `data/raw/tlc_trip_taxi_zones/`.

**Analysis steps:**
- Scatter plot of restaurant lat/lon (colored by borough)
- Spatial join restaurants to TLC zone shapefile (`LocationID`); report: total TLC zones (263), zones with ≥1 restaurant, zones with ≥10 restaurants
- Plot: choropleth of restaurant density per TLC zone
- Report top-20 zones by restaurant count and identify expected high-density zones (Midtown, Lower Manhattan, Williamsburg)
- Cross-reference with Task 8 in the TLC EDA notebook ("Dining-Neighborhood Dropoff Concentration" — top-30 zones by dinner-hour dropoff): do the zones with the most restaurant dropoffs also have the most restaurants?

**Output:** Restaurant scatter map. TLC zone choropleth (restaurant density). Zone coverage table. Overlap table vs. TLC top dinner-dropoff zones.

**Decision gate:** If fewer than 100 of 263 TLC zones contain ≥5 restaurants, the geographic fusion feature (US-3.2.3) will be weak and should be flagged as a risk.

### Task 8 - Rating Distributions & User Bias

**Objective:** Understand star rating distributions at the restaurant and review level to inform label construction for the ranking models in Epic 3.

**Rationale:** NDCG@10 (the primary evaluation metric) requires a relevance label. The most natural label is "has reviewed with >=N stars." If ratings are heavily skewed toward 4–5 stars (common in Yelp data), a threshold of 4+ will produce very high positive rates, making the ranking problem trivial. Knowing the distribution allows us to set a defensible threshold and consider implicit feedback alternatives.

**Inputs:** `data/raw/yelp/yelp_academic_dataset_review.json` filtered to NYC restaurants.

**Analysis steps:**
- Plot restaurant-level rating distribution (`business.stars` for NYC restaurants) — bar chart
- Plot review-level star distribution (1–5) for all NYC restaurant reviews — bar chart
- Compute per-user average rating and its distribution — are users systematically lenient or harsh?
- Report: % of reviews that are >=4 stars, >=3 stars; this informs where to set the "positive" label threshold
- Flag the user rating bias: how many users give 4–5 stars to ≥80% of their reviews (generous raters)?

**Output:** Two rating distribution bar charts. User average-rating distribution. Written label threshold recommendation for Epic 3 models.

### Task 9 - Temporal Dining Patterns

**Objective:** Characterize review timing (hour-of-day, day-of-week, month-of-year) to determine whether dining temporal patterns can be extracted from review timestamps and aligned with taxi trip temporal features.

**Rationale:** US-2.2.1 computes taxi zone affinity features split by weekday vs. weekend and time-of-day. For these to correlate with dining behavior, restaurant visits should also show temporal structure. Reviews are a proxy for visits (review date ~ visit date). If reviews show no temporal signal (flat across hours/days), the taxi temporal features have nothing to correlate with, weakening US-3.2.1.

**Inputs:** `data/raw/yelp/yelp_academic_dataset_review.json` filtered to NYC restaurants.

**Analysis steps:**
- Parse review `date`; extract hour, day-of-week, month
- Plot: review count by hour-of-day (expect peaks at lunch 12–14h and dinner 18–21h)
- Plot: review count by day-of-week (expect weekend elevation)
- Plot: review count by month (seasonality)
- Overlay the TLC "dining-hour" dropoff window (17–21h from the TLC EDA) with the Yelp review hour distribution - do they peak at the same times?

**Output:** Three temporal distribution charts. Correlation note: do review peak hours match TLC dinner-dropoff peak hours?

### Task 10 - Per-User Dining Geography (Dining Radius)

**Objective:** Measure how geographically concentrated or dispersed each user's dining reviews are across TLC zones, to validate the dining radius feature planned in US-2.1.2.

**Rationale:** The core hypothesis assumes users have identifiable "home zones" or "activity zones" that predict where they eat. If users review restaurants uniformly across all 263 TLC zones, geographic personalization adds no signal. If users concentrate their reviews in 2–5 zones, zone-based features are highly discriminative. This task measures that concentration directly.

**Inputs:** `data/raw/yelp/yelp_academic_dataset_review.json` filtered to NYC restaurants. TLC zone assignment from Task 7 (restaurant → zone mapping).

**Analysis steps:**
- For each user with >=5 NYC restaurant reviews: count distinct TLC zones in their review history
- Plot distribution of distinct zones per user (histogram)
- Compute a zone concentration index per user (e.g., fraction of reviews in the user's top-1, top-3, top-5 zones)
- Report median and 75th percentile of distinct zones per user
- Identify the "dining radius" feature range: what % of users concentrate ≥50% of reviews in ≤3 zones?

**Output:** Distinct-zones-per-user histogram. Concentration index distribution. Written assessment: is user dining geography concentrated enough to be a useful feature?

### Task 11 - Checkin Signal Assessment

**Objective:** Assess whether `checkin.json` adds independent signal beyond `review.json` for either user-level or business-level features.

**Rationale:** Unlike reviews, checkin records in `yelp_academic_dataset_checkin.json` are aggregate and **business-level only** - they record timestamps of all check-ins at a business, but not which user checked in. This means they cannot be used for user-level features. This task confirms that limitation and decides whether checkin data contributes any usable business-level signal (e.g., peak hour popularity) for Epic 2.

**Inputs:** `data/raw/yelp/yelp_academic_dataset_checkin.json` filtered to NYC restaurant `business_id`s (Task 1).

**Analysis steps:**
- Confirm schema: verify that checkin records have no `user_id` field (business-level only)
- Count total check-in events per NYC restaurant; compare distribution to review count per restaurant
- Parse checkin timestamps; plot aggregate checkin volume by hour-of-day and day-of-week
- Compute Spearman correlation between restaurant review count and restaurant checkin count — does checkin volume proxy for review volume (redundant) or add independent signal?

**Output:** Checkin vs. review count scatter + correlation. Checkin temporal distribution chart.

**Decision gate:** If checkin volume is near-perfectly correlated with review count (p > 0.9), checkin data is redundant and can be excluded from Epic 2. Otherwise, include as a business popularity feature.

## Task Summary

| # | Task | Phase | PRD Stories | Priority |
|---|---|---|---|---|
| 1 | NYC Restaurant Corpus Definition | Foundation | US-1.1.3 | P0 |
| 2 | Data Quality Audit | Foundation | All Epic 2 | P0 |
| 3 | Temporal Coverage & TLC Alignment | Foundation | US-1.1.2, US-1.1.3 | P0 |
| 4 | Interaction Matrix Characterization | Interaction Matrix | US-3.1.2, US-3.2.1 | P0 |
| 5 | NYC Reviewer Population Sizing | Interaction Matrix | US-1.1.1, US-3.2.2 | P0 |
| 6 | Cuisine & Price Tier Distributions | Feature Distributions | US-2.1.1 | P0 |
| 7 | Geographic Distribution & Zone Alignment | Feature Distributions | US-2.1.2, US-3.2.3 | P0 |
| 8 | Rating Distributions & User Bias | Feature Distributions | US-3.1.2, US-3.2.1 | P0 |
| 9 | Temporal Dining Patterns | Feature Distributions | US-2.2.1 | P1 |
| 10 | Per-User Dining Geography | Feature Distributions | US-2.1.2 | P1 |
| 11 | Checkin Signal Assessment | Feature Distributions | US-2.1.1 (decision gate) | P1 |

**Intentionally excluded:**
- Review text / NLP analysis - the POC uses structured features only; text is not in the Epic 2 feature plan
- Friend graph analysis - not referenced in any epic
- Tip text / content analysis - tips not in the feature plan; only aggregate tip count is a candidate business signal
- User compliment / elite status - not in the feature plan
