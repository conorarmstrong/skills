#!/usr/bin/env python3
"""Rebuild the next document version from apply-agent output.

Usage: apply_updates.py MATRIX_DIR OUT.md

Reads  MATRIX_DIR/rows.jsonl            canonical current text
       MATRIX_DIR/updated_part_XX.md    | Row | Location | New text | Change note |
Writes OUT.md                           rows joined by blank lines
       MATRIX_DIR/CROSS_NOTES.md        every change note containing CROSS:
       MATRIX_DIR/apply_report.json     counts and problems

New text conventions:
  =          keep the row unchanged (also the default for rows not listed)
  DELETE     drop the row
  anything else replaces the row (<br> for line breaks, \\| for a literal pipe)

Exit 1, writing nothing, on: a missing updated_part file, an unknown or duplicate row id,
or a row without exactly 4 cells. ADD is applied by the apply agent appending the INS
text to the row's New text; this script never inserts rows.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matrix_common import read_rows, table_lines, unescape_cell  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    d, out = Path(sys.argv[1]), Path(sys.argv[2])
    rows = read_rows(d)
    ids = {r["id"] for r in rows}
    updates, notes, problems = {}, [], []
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    for n in range(1, meta["parts"] + 1):
        if not (d / f"updated_part_{n:02d}.md").exists():
            problems.append(f"missing updated_part_{n:02d}.md")

    for p in sorted(d.glob("updated_part_*.md")):
        for cells in table_lines(p):
            rid = cells[0].strip()
            if rid not in ids:
                problems.append(f"{p.name}: unknown row {rid}")
                continue
            if rid in updates:
                problems.append(f"{p.name}: duplicate row {rid}")
            if len(cells) != 4:
                problems.append(f"{p.name}: {rid} has {len(cells)} cells, expected 4; an unescaped pipe?")
                continue
            new, note = cells[2], cells[3]
            updates[rid] = new
            if "CROSS:" in note:
                notes.append(f"- {rid} ({cells[1]}): {note}")

    if problems:
        # nothing is written, so a failed apply cannot be copied forward as the next version
        print(json.dumps({"problems": problems}, indent=2))
        sys.exit(1)

    kept = replaced = deleted = 0
    body = []
    for r in rows:
        new = updates.get(r["id"], "=").strip()
        if new in ("", "="):
            body.append(r["text"])
            kept += 1
        elif new.upper() == "DELETE":
            deleted += 1
        else:
            text = unescape_cell(new)
            body.append(text)
            replaced += text != r["text"]
            kept += text == r["text"]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(body) + "\n", encoding="utf-8")
    (d / "CROSS_NOTES.md").write_text("# CROSS notes\n\n" + "\n".join(notes) + "\n", encoding="utf-8")
    report = {"rows": len(rows), "kept": kept, "replaced": replaced, "deleted": deleted,
              "cross_notes": len(notes), "problems": problems}
    (d / "apply_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
