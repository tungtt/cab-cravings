"""
Download NYC TLC trip record parquet files from the TLC CloudFront CDN.

Usage:
    python3 src/ingest/download_tlc.py --from-year 2022 --to-year 2023 --types yellow green
"""

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
# DEFAULT_TYPES = ["yellow", "green", "fhv", "fhvhv"]
DEFAULT_TYPES = ["yellow", "green", "fhvhv"]  # fhv is excluded due to sparse data (low drop-off)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "tlc_trips"


def _progress_hook(filename: str):
    """
    Return a urllib reporthook that prints a single progress line.
    """
    reported = [False]

    def hook(block_count, block_size, total_size):
        if total_size <= 0:
            return
        downloaded = min(block_count * block_size, total_size)
        pct = downloaded / total_size * 100
        mb = downloaded / 1_048_576
        total_mb = total_size / 1_048_576
        print(f"\r  {filename}: {mb:.1f}/{total_mb:.1f} MB ({pct:.0f}%)", end="", flush=True)
        if downloaded >= total_size and not reported[0]:
            print()
            reported[0] = True

    return hook


def _month_range(year: int, from_year: int, to_year: int, from_month: int, to_month: int):
    start = from_month if year == from_year else 1
    end = to_month if year == to_year else 12
    return range(start, end + 1)


def download_tlc_trips(
    from_year: int,
    to_year: int,
    from_month: int = 1,
    to_month: int = 12,
    types: list[str] = DEFAULT_TYPES,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    skipped = downloaded = failed = 0

    for year in range(from_year, to_year + 1):
        for month in _month_range(year, from_year, to_year, from_month, to_month):
            for color in types:
                filename = f"{color}_tripdata_{year}-{month:02d}.parquet"
                dest = output_dir / filename

                if dest.exists():
                    print(f"Skip (exists): {filename}")
                    skipped += 1
                    continue

                url = f"{BASE_URL}/{filename}"
                print(f"Downloading {url}")
                try:
                    urllib.request.urlretrieve(url, dest, reporthook=_progress_hook(filename))
                    downloaded += 1
                except urllib.error.HTTPError as exc:
                    if exc.code == 404:
                        print(f"  Not found (404): {filename} — skipping")
                    else:
                        print(f"  HTTP {exc.code} for {filename} — skipping", file=sys.stderr)
                        failed += 1
                    if dest.exists():
                        dest.unlink()
                except Exception as exc:
                    print(f"  Error downloading {filename}: {exc}", file=sys.stderr)
                    failed += 1
                    if dest.exists():
                        dest.unlink()

    print(f"\nDone. downloaded={downloaded}  skipped={skipped}  failed={failed}")
    print(f"Output: {output_dir}")


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Download NYC TLC trip record parquet files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--from-year", type=int, required=True, help="First year to download")
    parser.add_argument("--to-year", type=int, required=True, help="Last year to download (inclusive)")
    parser.add_argument(
        "--from-month",
        type=int,
        default=1,
        choices=range(1, 13),
        metavar="{1..12}",
        help="Start month within from-year",
    )
    parser.add_argument(
        "--to-month",
        type=int,
        default=12,
        choices=range(1, 13),
        metavar="{1..12}",
        help="End month within to-year",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=DEFAULT_TYPES,
        choices=["yellow", "green", "fhv", "fhvhv"],
        metavar="TYPE",
        help="Taxi types to download (yellow, green, fhv, fhvhv)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to save parquet files",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)

    if args.from_year > args.to_year:
        print("Error: --from-year must be <= --to-year", file=sys.stderr)
        sys.exit(1)
    if args.from_year == args.to_year and args.from_month > args.to_month:
        print("Error: --from-month must be <= --to-month when years are equal", file=sys.stderr)
        sys.exit(1)

    download_tlc_trips(
        from_year=args.from_year,
        to_year=args.to_year,
        from_month=args.from_month,
        to_month=args.to_month,
        types=args.types,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
