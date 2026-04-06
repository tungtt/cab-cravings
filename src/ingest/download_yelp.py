"""
Download the Yelp Open Dataset from Kaggle.

Usage:
    python -m src.ingest.download_yelp
    python -m src.ingest.download_yelp --output-dir /path/to/yelp
    python -m src.ingest.download_yelp --force

Requires KAGGLE_USERNAME and KAGGLE_KEY environment variables, or
.kaggle/kaggle.json credentials file.  See README for setup instructions.
"""

import argparse
import sys
from pathlib import Path

KAGGLE_DATASET = "yelp-dataset/yelp-dataset"
EXPECTED_FILES = [
    "yelp_academic_dataset_business.json",
    "yelp_academic_dataset_review.json",
    "yelp_academic_dataset_user.json",
    "yelp_academic_dataset_checkin.json",
    "yelp_academic_dataset_tip.json",
]
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "yelp"


def download_yelp_dataset(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    force: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    existing = [f for f in EXPECTED_FILES if (output_dir / f).exists()]
    if not force and len(existing) == len(EXPECTED_FILES):
        print(f"All {len(EXPECTED_FILES)} files already present in {output_dir} — use --force to re-download.")
        for name in existing:
            size_mb = (output_dir / name).stat().st_size / 1_048_576
            print(f"  {name}: {size_mb:.1f} MB")
        return

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        print(
            "Error: kaggle package not installed. Run: pip install 'kaggle==2.0'",
            file=sys.stderr,
        )
        sys.exit(1)

    api = KaggleApi()
    try:
        api.authenticate()
    except Exception as exc:
        print(
            f"Kaggle authentication failed: {exc}\n"
            "Options:\n"
            "  1. Set KAGGLE_USERNAME and KAGGLE_KEY environment variables\n"
            "  2. Place kaggle.json in ~/.kaggle/ (default) or in the directory\n"
            "     pointed to by KAGGLE_CONFIG_DIR",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Downloading {KAGGLE_DATASET} → {output_dir}")
    print("This is a large dataset (~9 GB uncompressed). Progress is shown below:")
    api.dataset_download_files(KAGGLE_DATASET, path=output_dir, unzip=True, force=True)

    present = [f for f in EXPECTED_FILES if (output_dir / f).exists()]
    missing = [f for f in EXPECTED_FILES if f not in present]

    print(f"\nDone. {len(present)}/{len(EXPECTED_FILES)} files present in {output_dir}")
    for name in present:
        size_mb = (output_dir / name).stat().st_size / 1_048_576
        print(f"  {name}: {size_mb:.1f} MB")
    if missing:
        print("Missing files (unexpected):", file=sys.stderr)
        for name in missing:
            print(f"  {name}", file=sys.stderr)
        sys.exit(1)


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Download the Yelp Open Dataset from Kaggle.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to save the extracted JSON files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if all files already exist",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    download_yelp_dataset(output_dir=args.output_dir, force=args.force)


if __name__ == "__main__":
    main()
