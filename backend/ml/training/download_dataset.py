"""
download_dataset.py
-------------------
Downloads the NSL-KDD dataset from the Canadian Institute for Cybersecurity.
Files:
  - KDDTrain+.csv  : 125,973 training samples
  - KDDTest+.csv   : 22,544  test samples

Run:
    python ml/training/download_dataset.py
"""

import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from loguru import logger

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parents[2]          # backend/
RAW_DIR    = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ─── Dataset URLs ─────────────────────────────────────────────────────────────
DATASET_FILES = {
    "KDDTrain+.csv": (
        "https://raw.githubusercontent.com/defcom17/"
        "NSL_KDD/master/KDDTrain%2B.csv"
    ),
    "KDDTest+.csv": (
        "https://raw.githubusercontent.com/defcom17/"
        "NSL_KDD/master/KDDTest%2B.csv"
    ),
}

# NSL-KDD has no header row — we define columns ourselves
COLUMNS = [
    "duration", "protocol_type", "service", "flag",
    "src_bytes", "dst_bytes", "land", "wrong_fragment", "urgent",
    "hot", "num_failed_logins", "logged_in", "num_compromised",
    "root_shell", "su_attempted", "num_root", "num_file_creations",
    "num_shells", "num_access_files", "num_outbound_cmds",
    "is_host_login", "is_guest_login", "count", "srv_count",
    "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
    "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate",
    "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate",
    "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
    "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate", "label", "difficulty_level",
]


def download_file(url: str, dest: Path) -> None:
    """Download a single file with progress reporting."""
    if dest.exists():
        logger.info(f"Already exists, skipping: {dest.name}")
        return

    logger.info(f"Downloading: {dest.name}")
    logger.info(f"  URL: {url}")

    try:
        def progress_hook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                pct = min(100, downloaded * 100 // total_size)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                print(f"\r  [{bar}] {pct}% ({downloaded:,} / {total_size:,} bytes)",
                      end="", flush=True)

        urllib.request.urlretrieve(url, dest, reporthook=progress_hook)
        print()  # newline after progress bar
        logger.success(f"  Saved to: {dest}")

    except urllib.error.URLError as e:
        logger.error(f"  Download failed: {e}")
        logger.error("  Check your internet connection or try again later.")
        sys.exit(1)


def verify_dataset(file_path: Path) -> None:
    """Verify the downloaded CSV has expected number of columns."""
    import csv
    with open(file_path, "r") as f:
        reader = csv.reader(f)
        first_row = next(reader)

    col_count = len(first_row)
    expected  = len(COLUMNS)

    if col_count == expected:
        logger.success(f"  Verified: {file_path.name} has {col_count} columns ✓")
    elif col_count == expected - 1:
        # Some versions omit difficulty_level
        logger.warning(
            f"  {file_path.name} has {col_count} cols (no difficulty_level) — OK"
        )
    else:
        logger.error(
            f"  Unexpected column count: {col_count} (expected ~{expected})"
        )
        sys.exit(1)


def main() -> None:
    logger.add(
        BASE_DIR / "logs" / "download.log",
        rotation="10 MB",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )

    logger.info("=" * 60)
    logger.info("NSL-KDD Dataset Downloader")
    logger.info("=" * 60)
    logger.info(f"Destination: {RAW_DIR}")

    for filename, url in DATASET_FILES.items():
        dest = RAW_DIR / filename
        download_file(url, dest)
        verify_dataset(dest)
        logger.info("")

    logger.success("All dataset files downloaded and verified!")
    logger.info("")
    logger.info("Next step: Run preprocessing")
    logger.info("  python ml/training/preprocess.py")


if __name__ == "__main__":
    main()
