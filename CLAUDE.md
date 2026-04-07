# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

POC testing whether NYC taxi mobility patterns improve restaurant recommendations beyond Google Local (2021) review history alone. Two hypotheses:

1. Primary: For users with both taxi and Google Local data, does adding mobility features to Google Local dining features improve NDCG@10 vs Google-Local-only?
2. Cold-start: For taxi-only users (no Google Local history), can mobility patterns beat a popularity baseline?

## Data Sources

- TLC trip data: yellow, green, and FHVHV trips Jan 2025 - Feb 2026. Parquet files at `data/raw/tlc_trips/`.
- Google Local Data (2021): New York state 10-core subset (18,661,975 reviews; every user and business has >=10 interactions). Stored at `data/raw/googlelocal/`. The Yelp Academic Dataset was rejected: it contains no New York state businesses (dataset is concentrated in PA, FL, TN).

## Commands

```bash
# Install
pip install -e ".[dev]"

# Lint
ruff check src/ tests/

# Run all tests
pytest

# Run a single test file
pytest tests/path/to/test_file.py

# Run a single test
pytest tests/path/to/test_file.py::test_name

# Run the pipeline (stage by stage)
python -m src.identity.run
python -m src.features.run
python -m src.models.run
```

## Architecture

The codebase mirrors the four PRD epics as pipeline stages:

```
Stage 1 (src/identity/)      → data/processed/    Identity resolution: synthetic profiles linking TLC riders to Google Local reviewers
Stage 2 (src/features/)      → data/features/     Feature engineering: Google Local dining features + taxi mobility features (parallel)
Stage 3 (src/models/)        → results/           Baselines, taxi-augmented models, tiered router
Stage 4 (src/evaluation/)    → reports/           Metric tables, significance tests, final report
```

**Data flow:** `data/raw/` (gitignored TLC + Google Local downloads) → `data/processed/` (Stage 1 outputs) → `data/features/` (Stage 2 outputs) → model artifacts and metrics.

**Identity layer is synthetic:** no real PII. The 30% controlled overlap between taxi and Google Local populations is assigned, not discovered.

**User-segment matrix** drives model selection in the router:
- Both sources → Tier 2 (taxi+Google fusion)
- Google Local only → Tier 1 (Google-only personalized)
- Taxi only → Cold-start model
- Neither → Tier 0 (popularity fallback)

Pipeline stages run directly via `python -m`. A Makefile encoding stage dependencies is the intended sequencing mechanism.

## Key Libraries

- `pandas` + `pyarrow`: data wrangling and parquet I/O
- `scikit-learn`: feature pipelines and baselines
- `lightgbm`: taxi-augmented ranking models
- `scipy`: statistical significance tests for evaluation

## Writing Styles (must)

Direct, concise, specific, no em dash, no ---, no redundant whitespaces
