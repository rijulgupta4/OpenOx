"""Public-safe repository checks that do not require PhysioNet data."""

from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_release_checker_passes_outside_repository() -> None:
    """The release check must anchor itself to the repository, not the shell CWD."""

    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "release_check.py")],
        cwd=ROOT / "tests",
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_notebooks_are_output_cleared() -> None:
    for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
        notebook = json.loads(path.read_text(encoding="utf-8"))
        for cell in notebook.get("cells", []):
            if cell.get("cell_type") == "code":
                assert cell.get("outputs", []) == [], path
                assert cell.get("execution_count") is None, path
            assert not cell.get("attachments"), path


def test_local_markdown_links_resolve() -> None:
    missing: list[str] = []
    for path in sorted(ROOT.rglob("*.md")):
        for match in LOCAL_LINK.finditer(path.read_text(encoding="utf-8")):
            target = match.group(1).split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (path.parent / target).resolve().exists():
                missing.append(f"{path.relative_to(ROOT)} -> {target}")
    assert not missing, "Missing local links:\n" + "\n".join(missing)


def test_public_python_sources_parse() -> None:
    for directory in (ROOT / "src", ROOT / "scripts"):
        for path in sorted(directory.rglob("*.py")):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_analysis_and_qa_paths_do_not_depend_on_cwd() -> None:
    offenders: list[str] = []
    for directory in (ROOT / "scripts" / "analysis", ROOT / "scripts" / "qa"):
        for path in sorted(directory.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "Path.cwd()" in text or 'Path(r".")' in text:
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, "CWD-dependent path constants: " + ", ".join(offenders)


def test_required_governance_files_are_present() -> None:
    required = {
        "README.md",
        "LICENSE",
        "DATA_USE.md",
        "SECURITY.md",
        "CITATION.cff",
        "PUBLIC_RELEASE_MANIFEST.csv",
    }
    assert required.issubset({path.name for path in ROOT.iterdir() if path.is_file()})


def test_manifest_order_is_platform_independent() -> None:
    with (ROOT / "PUBLIC_RELEASE_MANIFEST.csv").open(encoding="utf-8", newline="") as stream:
        paths = [row["path"] for row in csv.DictReader(stream)]
    assert paths == sorted(paths, key=str.casefold)
