#!/usr/bin/env python3
"""Parses YAML frontmatter across docs/ and builds .index/graph.json for AI Agent RAG."""

import json
from pathlib import Path
import re
from typing import Any, Dict
import yaml


def extract_frontmatter(file_path: Path) -> Dict[str, Any]:
    content = file_path.read_text(encoding="utf-8-sig")
    match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except Exception as e:
        print(f"Error parsing YAML in {file_path}: {e}")
        return {}


def build_graph() -> None:
    docs_dir = Path("docs")
    index_dir = Path(".index")
    index_dir.mkdir(exist_ok=True)

    nodes: Dict[str, Dict[str, Any]] = {}
    edges = []

    for md_file in docs_dir.rglob("*.md"):
        meta = extract_frontmatter(md_file)
        doc_id = meta.get("id")
        if not doc_id:
            continue

        nodes[doc_id] = {
            "path": str(md_file),
            "title": meta.get("title"),
            "type": meta.get("type"),
            "status": meta.get("status"),
            "domain": meta.get("domain"),
            "layer": meta.get("layer"),
            "code_references": meta.get("code_references", []),
            "test_references": meta.get("test_references", []),
        }

        trace = meta.get("traceability", {})
        for brd in trace.get("implements_brd", []):
            edges.append({"source": doc_id, "target": brd, "relation": "implements"})
        for adr in trace.get("governed_by_adr", []):
            edges.append({"source": doc_id, "target": adr, "relation": "governed_by"})

    graph_data = {"nodes": nodes, "edges": edges}
    output_path = index_dir / "graph.json"
    output_path.write_text(json.dumps(graph_data, indent=2), encoding="utf-8")
    print(f"Successfully generated dependency graph ({len(nodes)} nodes) -> {output_path}")


if __name__ == "__main__":
    build_graph()
