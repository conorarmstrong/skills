#!/usr/bin/env python3
"""Validate CONFIG.yaml and print shell exports for the loop block.

Usage: eval "$(python3 -I loop_env.py /abs/scratch/CONFIG.yaml)"

Exports R (run root, the parent of paths.work), D (paths.out), SLUG, PARTS, MAX_KB, REF.
Exit 1 with the reasons on stderr, and print nothing, when:
  approved_at is not set, any path is relative, the title is still the Site X example,
  or document_slug is empty or a placeholder.
citation_offset may be "0" when PDF and document pages match.
"""
import shlex
import sys
from pathlib import Path

import yaml


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    cfg_path = Path(sys.argv[1])
    c = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    errs = []
    if not c.get("approved_at"):
        errs.append("approved_at is not set")
    if "Site X" in str(c.get("title", "")) or not c.get("title"):
        errs.append("title is empty or still the Site X example")
    paths = c.get("paths") or {}
    for k in ("work", "out", "bundle"):
        v = str(paths.get(k, ""))
        if not v.startswith("/"):
            errs.append(f"paths.{k} is not absolute: {v!r}")
    ref = str(c.get("reference_doc") or "")
    if ref and not ref.startswith("/"):
        errs.append(f"reference_doc is not absolute: {ref!r}")
    slug = str(c.get("document_slug") or "")
    if not slug or "<" in slug:
        errs.append("document_slug is empty or a placeholder")
    if errs:
        print("\n".join("CONFIG error: " + e for e in errs), file=sys.stderr)
        sys.exit(1)
    work = Path(paths["work"])
    out = {
        "R": str(work.parent),
        "D": str(paths["out"]).rstrip("/"),
        "SLUG": slug,
        "PARTS": str(c.get("parts_per_matrix", 20)),
        "MAX_KB": str(c.get("max_kb", 16)),
        "REF": ref,
    }
    for k, v in out.items():
        print(f"export {k}={shlex.quote(v)}")


if __name__ == "__main__":
    main()
