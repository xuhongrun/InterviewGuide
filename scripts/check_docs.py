#!/usr/bin/env python3
"""Run dependency-free checks for public documentation."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SKIP_SCHEMES = {"http", "https", "mailto", "data", "javascript"}
ALLOWED_REFERENCE_SUFFIXES = {".md", ".txt", ".yml", ".yaml"}
SENSITIVE_CASE_TOKENS = {"VCCD", "DCD", "ADD"}
INLINE_CODE_RE = re.compile(r"(`+)(.*?)(?<!`)\1(?!`)")


def markdown_targets(line: str) -> list[str]:
    """Extract inline Markdown link targets, including escaped parentheses."""
    targets: list[str] = []
    cursor = 0
    while True:
        marker = line.find("](", cursor)
        if marker < 0:
            return targets
        start = marker + 2
        depth = 1
        escaped = False
        index = start
        while index < len(line):
            char = line[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    targets.append(line[start:index].strip())
                    cursor = index + 1
                    break
            index += 1
        else:
            return targets


def without_inline_code(line: str) -> str:
    """Mask inline code so Markdown-like examples are not treated as links."""
    return INLINE_CODE_RE.sub(lambda match: " " * len(match.group(0)), line)


def normalize_target(raw_target: str) -> str:
    target = raw_target
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    elif ' "' in target:
        target = target.split(' "', 1)[0]
    elif " '" in target:
        target = target.split(" '", 1)[0]
    return unquote(target.replace("\\(", "(").replace("\\)", ")"))


def check_markdown(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(ROOT)
    in_fence = False

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        for token in SENSITIVE_CASE_TOKENS:
            if relative.parts[:2] == ("summarize", "dds") and token in line:
                errors.append(f"{relative}:{line_number}: public case contains token {token}")

        for raw_target in markdown_targets(without_inline_code(line)):
            target = normalize_target(raw_target)
            if not target or target.startswith("#"):
                continue
            parsed = urlsplit(target)
            if parsed.scheme.lower() in SKIP_SCHEMES:
                continue
            if target.startswith("/"):
                errors.append(f"{relative}:{line_number}: absolute local link: {target}")
                continue

            local_part = target.split("#", 1)[0].split("?", 1)[0]
            if not local_part:
                continue
            destination = (path.parent / local_part).resolve()
            if ROOT not in destination.parents and destination != ROOT:
                errors.append(f"{relative}:{line_number}: link escapes repository: {target}")
            elif not destination.exists():
                errors.append(f"{relative}:{line_number}: broken relative link: {target}")
    return errors


def main() -> int:
    errors: list[str] = []
    markdown_files = sorted(ROOT.rglob("*.md"))
    for path in markdown_files:
        if ".git" not in path.parts:
            errors.extend(check_markdown(path))

    reference_dir = ROOT / "reference"
    if reference_dir.exists():
        for path in reference_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() not in ALLOWED_REFERENCE_SUFFIXES:
                errors.append(
                    f"{path.relative_to(ROOT)}: binary reference material requires explicit licensing review"
                )

    if errors:
        print("Documentation checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Documentation checks passed for {len(markdown_files)} Markdown files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
