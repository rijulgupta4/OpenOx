"""Fail closed when a public OpenOx release contains restricted artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DENIED_SUFFIXES = {
    ".7z", ".arrow", ".bmp", ".csv.gz", ".dat", ".db", ".doc", ".docx",
    ".feather", ".gif", ".gz", ".h5", ".hdf5", ".hea", ".jpeg", ".joblib",
    ".jpg", ".jsonl", ".mp3", ".ndjson", ".npy", ".npz", ".parquet", ".pdf",
    ".ckpt", ".onnx", ".pickle", ".pkl", ".png", ".ppt", ".pptx", ".pt",
    ".pth", ".rds", ".safetensors", ".sav", ".sqlite", ".sqlite3", ".tar",
    ".tgz", ".tif", ".tiff", ".tsv", ".tsv.gz", ".wav", ".xls", ".xlsx",
    ".zip",
}
ALLOWED_CSV = {"PUBLIC_RELEASE_MANIFEST.csv"}
ALLOWED_SVG = {
    "docs/figures/model-transport.svg",
    "docs/figures/timing-study-flow.svg",
}
ALLOWED_POST_D035_DOCS = {"docs/WAVEFORM_STUDY.md"}
MANIFEST = ROOT / "PUBLIC_RELEASE_MANIFEST.csv"
SKIP_DIRS = {
    ".git", ".hypothesis", ".ipynb_checkpoints", ".mypy_cache", ".nox",
    ".pytest_cache", ".ruff_cache", ".tox", ".venv", "__pycache__", "dist",
    "htmlcov", "venv",
}
PERSONAL_PATH = re.compile(r"C:\\Users\\rijul|C:\\\\Users\\\\rijul", re.I)
SECRET = re.compile(
    r"github_pat_|ghp_|BEGIN [A-Z ]*PRIVATE KEY|aws_access_key_id|"
    r"(?:api[_-]?key|password)\s*[=:]\s*[^\s\"']+|"
    r"bearer\s+[A-Za-z0-9._-]+",
    re.I,
)


def canonical_bytes(path: Path) -> bytes:
    """Normalize UTF-8 line endings for a cross-platform manifest."""
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return text.replace("\r\n", "\n").encode("utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def is_unreviewed_post_d035_file(rel: str, filename: str) -> bool:
    """Allow the reviewed explanation without opening the waveform artifact gate."""
    return bool(re.search(r"(^|_)(24|v2)(_|\.|$)|waveform", filename.lower())) and (
        rel not in ALLOWED_POST_D035_DOCS
    )


def public_files() -> list[Path]:
    files = (
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
    )
    return sorted(
        files,
        key=lambda path: path.relative_to(ROOT).as_posix().casefold(),
    )


def manifest_rows(files: list[Path]) -> list[dict[str, str | int]]:
    return [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": len(canonical_bytes(path)),
            "sha256": sha256(path),
        }
        for path in files if path != MANIFEST
    ]


def write_manifest(files: list[Path]) -> None:
    with MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["path", "bytes", "sha256"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(manifest_rows(files))


def check_manifest(files: list[Path], problems: list[str]) -> None:
    if not MANIFEST.is_file():
        problems.append("missing PUBLIC_RELEASE_MANIFEST.csv")
        return
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        recorded = list(csv.DictReader(handle))
    expected = manifest_rows(files)
    normalized = [
        {"path": row["path"], "bytes": int(row["bytes"]), "sha256": row["sha256"]}
        for row in recorded
    ]
    if normalized != expected:
        problems.append(
            "PUBLIC_RELEASE_MANIFEST.csv is stale; run python scripts/release_check.py --write-manifest"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="regenerate the reviewed public-tree manifest",
    )
    args = parser.parse_args()
    problems: list[str] = []
    files = public_files()

    for required in ("notebooks", "scripts", "src", "docs"):
        if not (ROOT / required).is_dir():
            problems.append(f"missing required directory: {required}/")
    for path in ROOT.glob("*.ipynb"):
        problems.append(f"notebook must be under notebooks/: {path.name}")
    for path in ROOT.glob("*.py"):
        problems.append(f"Python file must be under scripts/ or src/: {path.name}")

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        lower = path.name.lower()
        if path.is_symlink():
            problems.append(f"symbolic link requires manual review: {rel}")
        denied = next(
            (suffix for suffix in DENIED_SUFFIXES if lower.endswith(suffix)), None
        )
        if denied:
            problems.append(f"denied artifact type: {rel}")
        if path.suffix.lower() == ".csv" and path.name not in ALLOWED_CSV:
            problems.append(f"unreviewed CSV: {rel}")
        if path.suffix.lower() == ".svg" and rel not in ALLOWED_SVG:
            problems.append(f"unreviewed SVG: {rel}")
        if is_unreviewed_post_d035_file(rel, lower):
            problems.append(f"post-D035/V2 file: {rel}")

        if path.name != "release_check.py" and path.stat().st_size <= 5_000_000:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                problems.append(f"unreviewed binary content: {rel}")
            else:
                if PERSONAL_PATH.search(text):
                    problems.append(f"personal absolute path: {rel}")
                if SECRET.search(text):
                    problems.append(f"possible secret: {rel}")
                if path.suffix.lower() == ".svg" and re.search(
                    r"<image\b|(?:href|src)\s*=|data:|url\(", text, re.I
                ):
                    problems.append(f"embedded or externally linked SVG content: {rel}")

        if path.suffix.lower() == ".ipynb":
            notebook = json.loads(path.read_text(encoding="utf-8"))
            for number, cell in enumerate(notebook.get("cells", []), start=1):
                if cell.get("cell_type") == "code":
                    if cell.get("outputs"):
                        problems.append(f"notebook output: {rel} cell {number}")
                    if cell.get("execution_count") is not None:
                        problems.append(f"execution count: {rel} cell {number}")
                if cell.get("attachments"):
                    problems.append(f"notebook attachment: {rel} cell {number}")

    if problems:
        raise SystemExit(
            "Public release check failed:\n- " + "\n- ".join(sorted(set(problems)))
        )

    if args.write_manifest:
        write_manifest(files)
        files = public_files()
    else:
        check_manifest(files, problems)
        if problems:
            raise SystemExit(
                "Public release check failed:\n- " + "\n- ".join(sorted(set(problems)))
            )

    print(f"Public release check passed: {len(files)} files reviewed")


if __name__ == "__main__":
    main()
