#!/usr/bin/env python3
"""Validates YAML frontmatter across docs/ and checks code_references."""

import re
import sys
from pathlib import Path
from typing import Any

import yaml


def extract_frontmatter(file_path: Path) -> dict[str, Any]:
    content = file_path.read_text(encoding="utf-8-sig")
    match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except Exception as e:
        print(f"Error parsing YAML in {file_path}: {e}")
        return {}


def validate_docs() -> int:
    docs_dir = Path("docs")
    if not docs_dir.exists():
        print("docs/ directory not found.")
        return 1

    errors = 0
    required_fields = [
        "id",
        "title",
        "type",
        "status",
        "domain",
        "layer",
        "c4_level",
        "diataxis_type",
        "traceability",
        "code_references",
        "test_references",
    ]

    for md_file in docs_dir.rglob("*.md"):
        if md_file.name == "DOCUMENTATION.md":
            continue

        meta = extract_frontmatter(md_file)
        if not meta:
            print(f"Error: Missing or invalid YAML frontmatter in {md_file}")
            errors += 1
            continue

        for field in required_fields:
            if field not in meta:
                print(f"Error: Missing required field '{field}' in {md_file} frontmatter")
                errors += 1

        code_refs = meta.get("code_references", [])
        if isinstance(code_refs, list):
            for ref in code_refs:
                if not Path(ref).exists():
                    print(f"Error: code_reference '{ref}' in {md_file} does not exist.")
                    errors += 1

        test_refs = meta.get("test_references", [])
        if isinstance(test_refs, list):
            for ref in test_refs:
                if not Path(ref).exists():
                    print(f"Error: test_reference '{ref}' in {md_file} does not exist.")
                    errors += 1

    if errors > 0:
        print(f"Validation failed with {errors} errors.")
        return 1

    print("Documentation validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(validate_docs())
