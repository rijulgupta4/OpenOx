"""Canonical repository paths for OpenOx tooling."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
ANALYSIS_SCRIPTS_DIR = SCRIPTS_DIR / "analysis"
BUILD_SCRIPTS_DIR = SCRIPTS_DIR / "build"
QA_SCRIPTS_DIR = SCRIPTS_DIR / "qa"
DOCS_DIR = PROJECT_ROOT / "docs"
