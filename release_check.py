"""Fail closed when a public OpenOx release contains restricted artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DENIED_SUFFIXES = {
    ".csv.gz", ".dat", ".docx", ".feather", ".gz", ".hea", ".joblib",
    ".jpg", ".parquet", ".pdf", ".pickle", ".pkl", ".png",
}
ALLOWED_CSV = {"PUBLIC_RELEASE_MANIFEST.csv"}
PERSONAL_PATH = re.compile(r"C:\\Users\\rijul|C:\\\\Users\\\\rijul", re.I)
SECRET = re.compile(
    r"github_pat_|ghp_|BEGIN [A-Z ]*PRIVATE KEY|aws_access_key_id|"
    r"(?:api[_-]?key|password)\s*[=:]\s*[^\s\"']+|"
    r"bearer\s+[A-Za-z0-9._-]+",
    re.I,
)


def main() -> None:
    problems: list[str] = []
    files = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        lower = path.name.lower()
        denied = next((suffix for suffix in DENIED_SUFFIXES if lower.endswith(suffix)), None)
        if denied:
            problems.append(f"denied artifact type: {rel}")
        if path.suffix.lower() == ".csv" and path.name not in ALLOWED_CSV:
            problems.append(f"unreviewed CSV: {rel}")
        if re.search(r"(^|_)(24|v2)(_|\.|$)|waveform", lower):
            problems.append(f"post-D035/V2 file: {rel}")

        if path.name != "release_check.py" and path.suffix.lower() in {".py", ".ipynb", ".md", ".yml", ".yaml", ".json", ".example"}:
            text = path.read_text(encoding="utf-8")
            if PERSONAL_PATH.search(text):
                problems.append(f"personal absolute path: {rel}")
            if SECRET.search(text):
                problems.append(f"possible secret: {rel}")

        if path.suffix.lower() == ".ipynb":
            notebook = json.loads(path.read_text(encoding="utf-8"))
            for number, cell in enumerate(notebook.get("cells", []), start=1):
                if cell.get("cell_type") != "code":
                    continue
                if cell.get("outputs"):
                    problems.append(f"notebook output: {rel} cell {number}")
                if cell.get("execution_count") is not None:
                    problems.append(f"execution count: {rel} cell {number}")

    if problems:
        raise SystemExit("Public release check failed:\n- " + "\n- ".join(sorted(set(problems))))
    print(f"Public release check passed: {len(files)} files reviewed")


if __name__ == "__main__":
    main()
