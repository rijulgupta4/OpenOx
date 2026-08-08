"""Central paths and local configuration for OpenOx."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCE_DIR = DATA_DIR / "reference"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
FIGURE_DIR = OUTPUT_DIR / "figures"
TABLE_DIR = OUTPUT_DIR / "tables"


def get_source_data_dir() -> Path:
    """Return the configured OpenOximetry source directory."""

    configured_path = os.getenv("OPENOX_DATA_DIR")
    if not configured_path:
        raise RuntimeError(
            "OPENOX_DATA_DIR is not configured. Copy .env.example to .env "
            "and set it to the OpenOximetry repository directory."
        )

    source_dir = Path(configured_path).expanduser().resolve()
    required_files = {
        "patient.csv",
        "encounter.csv",
        "bloodgas.csv",
        "pulseoximeter.csv",
    }
    missing_files = sorted(
        filename for filename in required_files if not (source_dir / filename).is_file()
    )
    if missing_files:
        missing_list = ", ".join(missing_files)
        raise RuntimeError(
            f"OPENOX_DATA_DIR does not contain the expected source files: {missing_list}"
        )

    return source_dir


def ensure_output_dirs() -> None:
    """Create project-owned directories used for generated artifacts."""

    for directory in (
        RAW_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        REFERENCE_DIR,
        FIGURE_DIR,
        TABLE_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
