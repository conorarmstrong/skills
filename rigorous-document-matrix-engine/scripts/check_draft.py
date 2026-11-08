#!/usr/bin/env python3
"""Sanity checks on a compiled draft. Run after every rebuild.

Usage: check_draft.py DOCUMENT.md [--prev PREVIOUS.md] [--banned WORDS.txt] [--numbered] [--final]

Reports word count (and delta against --prev), em and en dashes, open markers,
paragraph numbering gaps and duplicates, unnumbered prose, leaked process text, and
banned words (one per line in WORDS.txt; a default list of absolutes is used otherwise).

Exit 1 on: an empty file, em dashes, numbering gaps or duplicates, and leaked process text
(finding not applied, change note, CROSS:, REPL:, INS:, ATTACK:, PREEMPT:, <<<).
--numbered   also exit 1 on prose paragraphs that carry no N.N number. Use it for numbered
             documents. Headings, tables, lists, code blocks and the front matter before the
             first numbered paragraph are exempt.
--final      also exit 1 while any [VERIFY], [CONFIRM], [FIGURE or [LEGAL/RISK] marker remains.
Banned words never set the exit code: a checker or the red team decides each hit.
Paragraphs are recognised as `N.N` at the line start, optionally after `**` or a leading
`[Label]`, so a label placed before the number is still counted.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

DEFAULT_BANNED = ["completely", "impossible", "undisputed", "undeniably", "certainly",
                  "clearly", "obviously", "always", "never", "proves", "conclusively"]
MARKERS = ["[VERIFY]", "[CONFIRM]", "[FIGURE", "[LEGAL/RISK]"]
LEAKS = ["finding not applied", "change note", "CROSS:", "REPL:", "INS:", "ATTACK:", "PREEMPT:", "<<<"]
NUM = re.compile(r"^(?:\[[^\]\n]{1,40}\]\s*)?\**(\d+)\.(\d+)\s", re.M)
SKIP = re.compile(r"^\s*(#|\||[-*+]\s|\d+[.)]\s|>|<!--|---|\[FIGURE)")


def strip_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


def unnumbered(text: str, first_numbered: int | None) -> list[str]:
    out = []
    for block in re.split(r"\n\s*\n", text):
        line = block.strip().splitlines()[0] if block.strip() else ""
        if not line or SKIP.match(line) or NUM.match(line):
            continue
        pos = text.find(block)
        if first_numbered is not None and pos < first_numbered:
            continue
        out.append(line[:80])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("--prev")
    ap.add_argument("--banned")
    ap.add_argument("--numbered", action="store_true")
    ap.add_argument("--final", action="store_true")
    a = ap.parse_args()
    text = strip_code(Path(a.doc).read_text(encoding="utf-8"))
    words = len(text.split())
    errors = []

    banned = (Path(a.banned).read_text(encoding="utf-8").split() if a.banned else DEFAULT_BANNED)
    banned_hits = {w: len(re.findall(rf"\b{re.escape(w)}\b", text, re.I)) for w in banned}

    nums = NUM.findall(text)
    dupes_raw = [k for k, c in Counter(nums).items() if c > 1]
    dupes = [f"{s}.{p}" for s, p in dupes_raw]
    gaps, last = [], {}
    for s, p in nums:
        s, p = int(s), int(p)
        expected = last.get(s, 0) + 1
        if p != expected and (str(s), str(p)) not in dupes_raw:
            gaps.append(f"{s}.{last.get(s, 0)} -> {s}.{p}" if s in last else f"section {s} starts at {s}.{p}")
        last[s] = max(p, last.get(s, 0))
    if dupes:
        errors.append("duplicate paragraph numbers")
    if gaps:
        errors.append("paragraph numbering gaps")

    first = NUM.search(text)
    loose = unnumbered(text, first.start() if first else None)
    if a.numbered and loose:
        errors.append("unnumbered prose paragraphs")

    leaks = {l: text.count(l) for l in LEAKS if l in text}
    if leaks:
        errors.append("leaked process text")

    markers = {m: text.count(m) for m in MARKERS}
    if a.final and any(markers.values()):
        errors.append("open markers remain")

    if words == 0:
        errors.append("empty document")
    em = text.count("—")
    if em:
        errors.append("em dashes present")

    report = {
        "words": words,
        "word_delta": words - len(strip_code(Path(a.prev).read_text(encoding="utf-8")).split()) if a.prev else None,
        "em_dashes": em,
        "en_dashes": text.count("–"),
        "markers": markers,
        "numbered_paragraphs": len(nums),
        "duplicate_numbers": dupes,
        "numbering_gaps": gaps,
        "unnumbered_prose": loose[:10],
        "leaks": leaks,
        "banned_words": {w: c for w, c in banned_hits.items() if c},
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
