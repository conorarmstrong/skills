#!/usr/bin/env python3
"""Merge agent findings into one master matrix, repairing column drift.

Usage: merge_matrix.py MATRIX_DIR

Reads  MATRIX_DIR/findings_part_XX.md  (agent copies of matrix_part_XX.md with col 4 filled)
On success (exit 0) writes:
       MATRIX_DIR/master_matrix.md     | Row | Location | Current text | Findings |
       MATRIX_DIR/merged_part_XX.md    repaired per-part matrices for the apply agents
       MATRIX_DIR/NOTES.md             '## ' sections agents put after the table: dossier, script issues
Always writes:
       MATRIX_DIR/counts.json          verdict counts, change rate, problems, and the row ids
                                       behind every missing row, unknown code and repair

Exit 1, writing only counts.json and removing any earlier master_matrix.md, merged_part_XX.md
and NOTES.md, when a row has no finding, a part file is missing, or an unknown verdict code
appears. A failed merge therefore leaves nothing an apply step could use.
Every run first deletes updated_part_XX.md, apply_report.json and CROSS_NOTES.md from earlier
rounds, because they belong to a merge that no longer stands.

Drift repair: the current text always comes from rows.jsonl. The finding is col 4 (extra
cells are joined into it). If col 4 is empty or absent and col 3 starts with a known verdict
code, col 3 is taken as the finding.

change_rate = rows with a text-changing verdict / rows not marked only n/a. The
text-changing codes are FIX, ADD, CUT, STYLE, RISK, LABEL, UNVERIFIED, ATTACK, PREEMPT,
CONCEDE, SCOUT and INTEGRATE. OK, GAP and n/a do not count.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matrix_common import VERDICTS, escape_cell, read_rows, table_lines, verdict_codes  # noqa: E402

CHANGE_CODES = {"FIX", "ADD", "CUT", "STYLE", "RISK", "LABEL", "UNVERIFIED",
                "ATTACK", "PREEMPT", "CONCEDE", "SCOUT", "INTEGRATE"}
HEADER = ["| Row | Location | Current text | Findings |", "|---|---|---|---|"]


def trailing_sections(path: Path) -> list[str]:
    """Keep '## ' sections after the table, such as a red-team Dossier or Script issues."""
    text = path.read_text(encoding="utf-8")
    i = text.find("\n## ")
    return [f"<!-- from {path.name} -->\n" + text[i + 1:].strip()] if i >= 0 else []


def starts_with_verdict(cell: str) -> bool:
    codes = verdict_codes(cell)
    return bool(codes) and codes[0] in VERDICTS


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    d = Path(sys.argv[1])
    # a new merge makes every apply output from an earlier merge stale
    for stale in [*d.glob("updated_part_*.md"), d / "apply_report.json", d / "CROSS_NOTES.md"]:
        stale.unlink(missing_ok=True)
    rows = read_rows(d)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    known = {r["id"] for r in rows}
    findings, problems, notes = {}, [], []
    repaired = []

    for n in range(1, meta["parts"] + 1):
        p = d / f"findings_part_{n:02d}.md"
        if not p.exists():
            problems.append(f"missing {p.name}")
            continue
        notes.extend(trailing_sections(p))
        for cells in table_lines(p):
            rid = cells[0].strip()
            f = ""
            if len(cells) > 4:
                f = " \\| ".join(c for c in cells[3:] if c)
                problems.append(f"{rid}: {len(cells)} cells, extra cells joined into findings")
                repaired.append(rid)
            elif len(cells) == 4:
                f = cells[3]
            if not f and len(cells) >= 3 and starts_with_verdict(cells[2]):
                f = cells[2]
                problems.append(f"{rid}: finding found in col 3, moved to col 4")
                repaired.append(rid)
            if rid not in known:
                problems.append(f"{p.name}: unknown row {rid}, ignored")
                continue
            if rid in findings and f:
                problems.append(f"{p.name}: duplicate row {rid}, later finding kept")
            if f:
                findings[rid] = f

    counts, unknown_rows = Counter(), defaultdict(list)
    missing, by_id, lines = [], {}, list(HEADER)
    for r in rows:
        f = findings.get(r["id"], "")
        if not f:
            missing.append(r["id"])
        for c in verdict_codes(f):
            if c in VERDICTS:
                counts[c] += 1
            else:
                unknown_rows[c].append(r["id"])
        by_id[r["id"]] = f"| {r['id']} | {escape_cell(r['location'])} | {escape_cell(r['text'])} | {f} |"
        lines.append(by_id[r["id"]])

    changed = sum(1 for r in rows if CHANGE_CODES & set(verdict_codes(findings.get(r["id"], ""))))
    scored = [r for r in rows if set(verdict_codes(findings.get(r["id"], ""))) != {"N/A"}]
    failed = bool(missing or unknown_rows or any(p.startswith("missing") for p in problems))

    summary = {
        "rows": len(rows),
        "rows_with_findings": len(rows) - len(missing),
        "rows_changed": changed,
        "change_rate": round(changed / max(1, len(scored)), 4),
        "verdicts": dict(counts.most_common()),
        "unknown_codes": {k: v for k, v in unknown_rows.items()},
        "missing_rows": missing,
        "repaired_rows": sorted(set(repaired)),
        "problems": problems,
        "ok": not failed,
    }
    (d / "counts.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if failed:
        for stale in [d / "master_matrix.md", d / "NOTES.md", *d.glob("merged_part_*.md")]:
            stale.unlink(missing_ok=True)
    else:
        (d / "master_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (d / "NOTES.md").write_text("\n\n".join(notes) + "\n", encoding="utf-8")
        for n in range(1, meta["parts"] + 1):
            part_ids = [c[0].strip() for c in table_lines(d / f"matrix_part_{n:02d}.md")]
            (d / f"merged_part_{n:02d}.md").write_text(
                "\n".join(HEADER + [by_id[i] for i in part_ids]) + "\n", encoding="utf-8")

    shown = {k: v for k, v in summary.items() if k != "missing_rows"}
    shown["missing_rows"] = len(missing)
    shown["missing_ids"] = missing[:20] + (["..."] if len(missing) > 20 else [])
    print(json.dumps(shown, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
