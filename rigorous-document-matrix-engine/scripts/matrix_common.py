"""Shared helpers for the matrix scripts. Standard library only."""
import json
import re
from pathlib import Path

VERDICTS = {
    # fact-check
    "OK", "FIX", "ADD", "CUT", "UNVERIFIED", "STYLE", "RISK", "LABEL", "N/A",
    # red team
    "ATTACK", "PREEMPT", "GAP", "CONCEDE",
    # integration of accepted scout cards or external edit lists
    "SCOUT", "INTEGRATE",
}

PARA_RE = re.compile(r"^(\d+(?:\.\d+)+)\s")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)")


def escape_cell(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def unescape_cell(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in "\\|":
            out.append(text[i + 1])
            i += 2
        else:
            out.append(text[i])
            i += 1
    return re.sub(r"<br\s*/?>", "\n", "".join(out), flags=re.I)


def split_row(line: str) -> list[str]:
    """Split a markdown table line on unescaped pipes. Strips outer pipes."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        slashes = len(line[:-1]) - len(line[:-1].rstrip("\\"))
        if slashes % 2 == 0:  # even backslashes: the pipe is a real delimiter
            line = line[:-1]
    cells, cur, i = [], [], 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line):
            cur.append(line[i:i + 2])
            i += 2
            continue
        if c == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def read_rows(matrix_dir: Path) -> list[dict]:
    with open(matrix_dir / "rows.jsonl", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def table_lines(path: Path):
    """Yield cell lists for every data row (first cell like R0001)."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if re.match(r"^\|\s*R\d{4,}\s*\|", line):
            yield split_row(line)


def verdict_codes(finding: str) -> list[str]:
    """Findings are `CODE: detail // CODE: detail`. Returns the leading code of each segment.
    A segment that does not start with an upper-case token returns '?' so it is flagged."""
    codes = []
    for part in re.split(r"\s//\s", finding):
        if not part.strip():
            continue
        m = re.match(r"\s*(n/a|N/A|[A-Z]+)(?=[\s:]|$)", part)
        codes.append(m.group(1).upper() if m else "?")
    return codes
