# cab-cravings
POC testing whether taxi mobility patterns improve restaurant recommendations beyond review history alone.

## Setup

### Prerequisites

- Python 3.11 or higher
- `git`

Verify your Python version:

```bash
python3 --version
```

---

### 1. Clone the repository

```bash
git clone <repo-url>
cd cab-cravings
```

---

### 2. Create a virtual environment

**macOS / Linux**
```bash
python3 -m venv .cabvenv
```

**Windows**
```cmd
python -m venv .cabvenv
```

This creates a `.cabvenv/` directory in the project root. It is already listed in `.gitignore`.

---

### 3. Activate the virtual environment

**macOS / Linux**
```bash
source .cabvenv/bin/activate
```

**Windows (Command Prompt)**
```cmd
.cabvenv\Scripts\activate.bat
```

**Windows (PowerShell)**
```powershell
.cabvenv\Scripts\Activate.ps1
```

Your prompt will change to show `(.cabvenv)` when the environment is active.

To deactivate at any time:
```bash
deactivate
```

---

### 4. Install dependencies

**Runtime dependencies only:**
```bash
pip install -r requirements.txt
```

**Runtime + development tools** (pytest, ruff — recommended for contributors):
```bash
pip install -e ".[dev]"
```

The `-e` flag installs the project in editable mode so changes to `src/` are reflected immediately without reinstalling.

---

### 5. Verify the installation

```bash
python - <<'EOF'
import pandas, pyarrow, sklearn, lightgbm, scipy
print("pandas     ", pandas.__version__)
print("pyarrow    ", pyarrow.__version__)
print("scikit-learn", sklearn.__version__)
print("lightgbm   ", lightgbm.__version__)
print("scipy      ", scipy.__version__)
EOF
```

All five packages should print their version numbers without errors.

---

## Running the pipeline

Each stage is run as a Python module from the project root with the virtual environment active:

```bash
python -m src.identity.run    # Stage 1 — identity resolution
python -m src.features.run    # Stage 2 — feature engineering
python -m src.models.run      # Stage 3 — modeling & evaluation
```

## Downloading TLC trip data

```bash
python -m src.ingest.download_tlc --from-year 2022 --to-year 2023
```

Optional flags:

| Flag | Default | Description |
|---|---|---|
| `--from-month` | `1` | Start month within `from-year` |
| `--to-month` | `12` | End month within `to-year` |
| `--types` | `yellow green fhv fhvhv` | Taxi/FHV types to download |
| `--output-dir` | `data/raw/tlc_trips` | Override output directory |

Files are saved as parquet to `data/raw/tlc_trips/` and skipped if already downloaded.
