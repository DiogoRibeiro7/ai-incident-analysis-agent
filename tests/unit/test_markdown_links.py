from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*]\(([^)\s]+(?:\s+\"[^\"]*\")?)\)")
LOCAL_ABSOLUTE_PATTERN = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]|file://|vscode://")
EXTERNAL_SCHEMES = ("http://", "https://", "mailto:")


def tracked_markdown_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return [REPO_ROOT / line for line in result.stdout.splitlines()]


def clean_markdown_target(raw_target: str) -> str:
    target = raw_target.strip()
    if " " in target:
        target = target.split(" ", 1)[0]
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split("#", 1)[0].split("?", 1)[0]
    return unquote(target)


def is_external_target(target: str) -> bool:
    return target.startswith(EXTERNAL_SCHEMES)


def existing_local_target(markdown_file: Path, target: str) -> Path | None:
    candidates = [
        (markdown_file.parent / target).resolve(strict=False),
        (REPO_ROOT / target).resolve(strict=False),
    ]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def test_markdown_files_do_not_use_machine_local_links() -> None:
    failures = [
        str(path.relative_to(REPO_ROOT))
        for path in tracked_markdown_files()
        if LOCAL_ABSOLUTE_PATTERN.search(path.read_text(encoding="utf-8"))
    ]

    assert failures == []


def test_markdown_local_links_resolve_to_tracked_files() -> None:
    failures: list[str] = []

    for markdown_file in tracked_markdown_files():
        text = markdown_file.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_PATTERN.finditer(text):
            target = clean_markdown_target(match.group(1))
            if not target or target.startswith("#") or is_external_target(target):
                continue
            if existing_local_target(markdown_file, target) is None:
                relative_path = markdown_file.relative_to(REPO_ROOT)
                failures.append(f"{relative_path}: unresolved Markdown link target {target!r}")

    assert failures == []
