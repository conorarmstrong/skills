#!/usr/bin/env python3
"""Dispatch one task per matrix part, in parallel, within the approved concurrency.

Usage: fanout.py --config /abs/scratch/CONFIG.yaml --matrix-dir /abs/scratch/vN/slug \
                 --mode check|redteam|apply [--only 01,03] [--retry-note "text"]

check     matrix_part_XX.md -> findings_part_XX.md   chain "checker",  FACTCHECK_BRIEF.md
redteam   matrix_part_XX.md -> findings_part_XX.md   chain "red_team", REDTEAM_BRIEF.md
apply     merged_part_XX.md -> updated_part_XX.md    chain "apply",    APPLY_BRIEF.md

Reads chains, concurrency (default 4) and paths from CONFIG.yaml. Briefs and the three
context files (CONTEXT.md, BUNDLE_REGISTER.md, LEDGER.md) live in paths.work. Each part runs
dispatch.py, so every gate, fallback and validation rule applies. --only re-dispatches the
named parts, for example the ones merge_matrix.py listed. --retry-note adds RETRY: <text> to
the task. Prints one line per part. Exit 1 if any part failed, with the failed parts listed.
"""
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

MODES = {
    "check":   ("checker",  "FACTCHECK_BRIEF.md", "matrix_part_",  "findings_part_", "OK,FIX,ADD,CUT,UNVERIFIED,STYLE,RISK,LABEL,N/A"),
    "redteam": ("red_team", "REDTEAM_BRIEF.md",   "matrix_part_",  "findings_part_", "OK,ATTACK,PREEMPT,GAP,CONCEDE,N/A"),
    "apply":   ("apply",    "APPLY_BRIEF.md",     "merged_part_",  "updated_part_",  None),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--matrix-dir", required=True)
    ap.add_argument("--mode", required=True, choices=MODES)
    ap.add_argument("--only")
    ap.add_argument("--retry-note", default="")
    a = ap.parse_args()

    cfg = yaml.safe_load(Path(a.config).read_text(encoding="utf-8")) or {}
    chain_key, brief_name, src_prefix, out_prefix, codes = MODES[a.mode]
    chain = (cfg.get("chains") or {}).get(chain_key)
    if not chain:
        sys.exit(f"CONFIG.yaml has no chains.{chain_key}")
    work = Path(cfg["paths"]["work"])
    m = Path(a.matrix_dir)
    here = Path(__file__).resolve().parent
    ctx = []
    for name in ("CONTEXT.md", "BUNDLE_REGISTER.md", "LEDGER.md"):
        if not (work / name).is_file():
            sys.exit(f"missing {work / name}: create it before any dispatch")
        ctx += ["--context", str(work / name)]

    parts = sorted(m.glob(f"{src_prefix}*.md"))
    if a.only:
        want = {x.strip() for x in a.only.split(",")}
        parts = [p for p in parts if p.stem.removeprefix(src_prefix) in want]
    if not parts:
        sys.exit(f"no {src_prefix}*.md parts found in {m}")

    def run(p: Path):
        x = p.stem.removeprefix(src_prefix)
        task = f"Input: {p}" + (f" RETRY: {a.retry_note}" if a.retry_note else "")
        cmd = ["python3", "-I", str(here / "dispatch.py"), "--config", a.config, "--chain", chain,
               *ctx, "--brief", str(work / brief_name), "--task", task,
               "--out", str(m / f"{out_prefix}{x}.md"), "--expect-rows", str(p),
               "--workdir", str(work.parent), "--log", str(work / "RUN_LOG.jsonl")]
        if codes:
            cmd += ["--codes", codes]
        r = subprocess.run(cmd, capture_output=True, text=True)
        try:
            d = json.loads(r.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            d = {"status": "crashed", "reason": (r.stderr or r.stdout)[-300:]}
        return x, r.returncode, d

    workers = int(cfg.get("concurrency", 4))
    failed = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for x, rc, d in ex.map(run, parts):
            note = d.get("engine") or d.get("last_reason") or d.get("reason", "")
            print(f"part {x}: {d.get('status')} exit {rc} {note}")
            if rc != 0:
                failed.append(x)
    if failed:
        print(f"FAILED parts: {','.join(failed)}  (re-run with --only {','.join(failed)})")
        sys.exit(1)


if __name__ == "__main__":
    main()
