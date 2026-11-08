#!/usr/bin/env python3
"""Split a markdown document into a row matrix for one review loop.

Usage: make_matrix.py DOCUMENT.md OUT_DIR [PARTS=20] [MAX_KB=16]

PARTS is a target. A part is split further when its text exceeds MAX_KB, so the agent's
returned table fits the model's output limit. The agent echoes the part and adds findings, so
use about half of (output tokens x 4 / 1024) KB: 16 KB suits an 8K-token output cap. Row ids restart at R0001 in every loop: key the ledger on
paragraph number and a quoted phrase, never on row id.

Writes:
  OUT_DIR/rows.jsonl            canonical rows {id, location, text}; the rebuild reads this,
                                never the agent-edited part files, for the current text
  OUT_DIR/matrix_part_XX.md     | Row | Location | Current text | Findings |  (col 4 blank)
  OUT_DIR/meta.json             source path, sha256, row and part counts

A row is one block: a paragraph, heading, list run, table, or fenced code block.
Part boundaries snap forward to the next heading when one is within 25% of a part.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matrix_common import HEAD_RE, PARA_RE, escape_cell  # noqa: E402


def blocks(text: str) -> list[str]:
    out, cur, fence = [], [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            cur.append(line)
            continue
        if not fence and not line.strip():
            if cur:
                out.append("\n".join(cur))
                cur = []
            continue
        if not fence and HEAD_RE.match(line) and cur:
            out.append("\n".join(cur))
            cur = []
        cur.append(line)
        if not fence and HEAD_RE.match(line):
            out.append("\n".join(cur))
            cur = []
    if cur:
        out.append("\n".join(cur))
    return out


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    parts = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    max_bytes = int(sys.argv[4]) * 1024 if len(sys.argv) > 4 else 16 * 1024
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob("matrix_part_*.md")):
        sys.exit(f"{out} already holds a matrix. Use a fresh directory per loop.")

    raw = src.read_text(encoding="utf-8")
    rows, heading = [], "front"
    for i, b in enumerate(blocks(raw), 1):
        first = b.splitlines()[0]
        h, p = HEAD_RE.match(first), PARA_RE.match(first.lstrip("*"))
        if h:
            heading = h.group(2).strip()[:60]
            loc = f"H{len(h.group(1))}: {heading}"
        elif p:
            loc = f"para {p.group(1)}"
        else:
            loc = f"in {heading}"
        rows.append({"id": f"R{i:04d}", "location": loc, "text": b, "is_heading": bool(h)})

    with open(out / "rows.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({k: r[k] for k in ("id", "location", "text")}, ensure_ascii=False) + "\n")

    size = max(1, -(-len(rows) // parts))
    chunks, start = [], 0
    while start < len(rows):
        end = min(start + size, len(rows))
        for j in range(end, min(end + size // 4, len(rows))):
            if rows[j]["is_heading"]:
                end = j
                break
        # cap part size so the agent's echoed table fits its output limit
        while end - start > 1 and sum(len(escape_cell(r["text"])) + 40 for r in rows[start:end]) > max_bytes:
            end -= 1
        chunks.append(rows[start:end])
        start = end

    for n, chunk in enumerate(chunks, 1):
        lines = ["| Row | Location | Current text | Findings |", "|---|---|---|---|"]
        lines += [f"| {r['id']} | {escape_cell(r['location'])} | {escape_cell(r['text'])} |  |" for r in chunk]
        (out / f"matrix_part_{n:02d}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    meta = {"source": str(src.resolve()), "sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "rows": len(rows), "parts": len(chunks)}
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"{len(rows)} rows in {len(chunks)} parts -> {out}")


if __name__ == "__main__":
    main()
