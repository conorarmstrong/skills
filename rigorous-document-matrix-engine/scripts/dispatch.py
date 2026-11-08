#!/usr/bin/env python3
"""Run one sub-agent task on the first healthy engine in an approved fallback chain.

Usage:
  dispatch.py --config scratch/CONFIG.yaml \
              --chain gemini:<id>,codex:<id>,claude:claude-<id> \
              --context scratch/CONTEXT.md [--context scratch/LEDGER.md ...] \
              --brief scratch/FACTCHECK_BRIEF.md --task "Input: <abs path>." \
              --out scratch/v2/SKILL/findings_part_03.md \
              [--expect-rows scratch/v2/SKILL/matrix_part_03.md] [--codes OK,FIX,ADD,CUT,UNVERIFIED,STYLE,RISK,LABEL,N/A] \
              [--web] \
              [--workdir <abs dir>] [--timeout 900] [--retries 1] [--log scratch/RUN_LOG.jsonl]

Gate: refuses to run unless CONFIG.yaml has approved_at set. Refuses gemini, grok and codex
unless external_models is "allowed". web_search defaults to denied: grok then runs with
--disable-web-search, codex and claude run without web tools, and gemini is refused because
no gemini flag disables its web tools. --web (scouts) adds codex --search and claude
WebSearch and WebFetch, and only when web_search is allowed. Every chain entry needs a
pinned model ID. Empty entries, placeholders such as <id> and claude aliases such as
claude:sonnet are refused. Claude IDs must start with claude-.

The prompt is: every --context file under its file name, then the brief, the task and
the output contract. Engines run read-only. The agent prints its result between
<<<BEGIN OUTPUT>>> and <<<END OUTPUT>>>, then a summary after <<<SUMMARY>>>.
This script writes the result to --out and prints engine, status and summary.

Success is judged by output, never exit code: markers present, body non-empty, and with
--expect-rows every row id present, every row line closed with a pipe, and no row left
identical to its input line. With --codes, col 4 of every row must start with an allowed
verdict code, so invented codes fail at dispatch and not at merge.

Failure handling:
  transient (timeout, rate limit, 5xx): retry the same engine with backoff
  permanent (auth, unknown model, untrusted folder): next engine at once
  bad output: retry once, then next engine
One failed engine try counts once toward the circuit. After 3 consecutive failed tries
the engine is skipped for 15 minutes, then tried again.
Exit 0 on success, 2 when an input file is missing or the command is malformed, 3 when the
chain is exhausted (the last reason and the path of the last rejected output are printed),
4 when the gate refuses. A rejected answer is kept in prompts/<name>.rejected.txt.
"""
import argparse
import fcntl
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matrix_common import split_row, verdict_codes  # noqa: E402

BEGIN, END, SUMMARY = "<<<BEGIN OUTPUT>>>", "<<<END OUTPUT>>>", "<<<SUMMARY>>>"
CONTRACT = f"""
OUTPUT CONTRACT
- You are read-only. Never write, move or delete a file. Read files with your file tools. If your only way to read is a read-only shell command such as cat, grep or ls, you may use it. Use absolute paths.
- Print your full result between a line {BEGIN} and a line {END}.
- Keep each table row on one physical line. Use <br> for line breaks inside a cell.
- Then print {SUMMARY} and a summary under 150 words.
"""
TRANSIENT = re.compile(r"rate.?limit|\b429\b|quota exceeded|overloaded|\b50[0234]\b|timed? ?out|temporarily|ECONNRESET", re.I)
PERMANENT = re.compile(r"unauthori[sz]ed|\b40[13]\b|api key|not logged in|unknown model|invalid model|"
                       r"not running in a trusted|login required|command not found|unrecognized_model|model_not_found|"
                       r"not supported when using", re.I)
CIRCUIT_LIMIT, CIRCUIT_COOLDOWN = 3, 900
EXTERNAL = {"gemini", "grok", "codex"}
CLAUDE_ID = re.compile(r"^claude-[a-z0-9][a-z0-9.\-]*$")
ROW = re.compile(r"^\|\s*(R\d{4,})\s*\|.*$", re.M)


def build_cmd(engine, model, prompt_file, workdir, web_denied, web):
    """Returns (argv, stdin text). Flags verified against each CLI's --help."""
    prompt = prompt_file.read_text(encoding="utf-8")
    if engine == "gemini":
        cmd = ["gemini", "-p", "Follow the instructions on stdin.", "--approval-mode", "plan", "--skip-trust"]
        return cmd + (["-m", model] if model else []), prompt
    if engine == "grok":
        cmd = ["grok", "--prompt-file", str(prompt_file), "--cwd", str(workdir),
               "--permission-mode", "plan", "--output-format", "plain"]
        cmd += ["--disable-web-search"] if web_denied else []
        return cmd + (["-m", model] if model else []), None
    if engine == "codex":
        cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "-C", str(workdir)]
        cmd += ["--search"] if web and not web_denied else []
        return cmd + ["-m", model, "-"], prompt
    if engine == "claude":
        tools = "Read,Grep,Glob" + (",WebSearch,WebFetch" if web and not web_denied else "")
        cmd = ["claude", "-p", "--tools", tools, "--permission-prompts", "none"]
        return cmd + (["--model", model] if model else []), prompt
    raise SystemExit(f"unknown engine {engine}")


def locked_json(path: Path, fn):
    path.touch(exist_ok=True)
    with open(path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        raw = f.read()
        data = json.loads(raw) if raw.strip() else {}
        out = fn(data)
        f.seek(0), f.truncate(), f.write(json.dumps(data, indent=2))
        return out


def circuit_open(health: Path, key: str) -> bool:
    def fn(d):
        e = d.get(key, {})
        if e.get("consecutive_failures", 0) < CIRCUIT_LIMIT:
            return False
        return time.time() - e.get("last_failure_ts", 0) < CIRCUIT_COOLDOWN
    return locked_json(health, fn)


def record(health: Path, key: str, ok: bool, reason: str = "") -> None:
    def fn(d):
        e = d.setdefault(key, {"consecutive_failures": 0})
        e["consecutive_failures"] = 0 if ok else e["consecutive_failures"] + 1
        if not ok:
            e["last_failure_ts"] = time.time()
        e["last"] = {"ok": ok, "reason": reason, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    locked_json(health, fn)


def classify(rc, stderr: str, stdout: str) -> str:
    """Reads stderr, and stdout only when no output markers came back, so document text
    quoted in a valid answer cannot steer the fallback."""
    if rc is None:
        return "transient"
    probe = stderr + ("" if BEGIN in stdout else stdout[-1500:])
    if PERMANENT.search(probe):
        return "permanent"
    if TRANSIENT.search(probe):
        return "transient"
    return "bad_output"


def validate(text: str, expect_rows: Path | None, codes: set[str] | None = None):
    """Returns (output or None, summary, failure reason)."""
    if BEGIN not in text or END not in text:
        return None, "", "markers missing"
    body = text.split(BEGIN, 1)[1].split(END, 1)[0].strip("\n")
    summary = text.split(SUMMARY, 1)[1].strip() if SUMMARY in text else ""
    summary = re.sub(r"<<<.*?>>>", "", summary).strip()
    if not body.strip():
        return None, summary, "empty output"
    if expect_rows:
        given = {m.group(1): " ".join(m.group(0).split()) for m in ROW.finditer(expect_rows.read_text(encoding="utf-8"))}
        got = {m.group(1): m.group(0) for m in ROW.finditer(body)}
        missing = sorted(set(given) - set(got))
        if missing:
            return None, summary, f"{len(missing)} rows missing, e.g. {missing[:3]}"
        open_rows = [r for r, line in got.items() if not line.rstrip().endswith("|")]
        if open_rows:
            return None, summary, f"rows not closed on one line, e.g. {open_rows[:3]}"
        unfilled = [r for r in given if " ".join(got[r].split()) == given[r]]
        if unfilled:
            return None, summary, f"{len(unfilled)} rows returned unfilled, e.g. {unfilled[:3]}"
        if codes:
            bad, seen = [], set()
            for r, line in got.items():
                cells = split_row(line)
                cs = verdict_codes(cells[3]) if len(cells) == 4 else ["?"]
                if not cs or any(c not in codes for c in cs):
                    bad.append(r)
                    seen.update(c for c in cs if c not in codes)
            if bad:
                return None, summary, (f"{len(bad)} rows with a missing or disallowed verdict code "
                                       f"{sorted(seen) or ['(none given)']}, e.g. {bad[:3]}")
    return body + "\n", summary, ""


def gate(config: Path, chain: list[tuple[str, str]]) -> tuple[bool, str]:
    c = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    if not c.get("approved_at"):
        return False, "CONFIG.yaml approved_at is not set: the user has not approved this run"
    external_ok = str(c.get("external_models", "denied")).lower() == "allowed"
    web_denied = str(c.get("web_search", "denied")).lower() != "allowed"
    for engine, model in chain:
        if not model or "<" in model or ">" in model:
            return False, f"empty or placeholder model in chain entry {engine}:{model}"
        if engine == "claude" and not CLAUDE_ID.match(model):
            return False, f"claude:{model} is not a pinned ID (claude-...); aliases are refused"
        if engine in EXTERNAL and not external_ok:
            return False, f"{engine} in chain but external_models is not allowed"
        if engine == "gemini" and web_denied:
            return False, "gemini cannot run unless web_search is allowed: no flag disables its web tools"
    return True, "web_denied" if web_denied else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--chain", required=True)
    ap.add_argument("--context", action="append", default=[])
    ap.add_argument("--brief", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-rows")
    ap.add_argument("--codes", help="comma list of verdict codes allowed in col 4, e.g. OK,FIX,N/A")
    ap.add_argument("--web", action="store_true", help="this task needs web search (scouts); needs web_search allowed")
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--log", default="scratch/RUN_LOG.jsonl")
    a = ap.parse_args()

    inputs = [("--config", a.config), ("--brief", a.brief)] + [("--context", c) for c in a.context]
    inputs += [("--expect-rows", a.expect_rows)] if a.expect_rows else []
    missing_in = [f"{k} {v}" for k, v in inputs if not Path(v).is_file()]
    if missing_in:
        print(json.dumps({"status": "usage", "reason": "input file not found: " + "; ".join(missing_in)}))
        sys.exit(2)

    out, log = Path(a.out).resolve(), Path(a.log).resolve()
    workdir = Path(a.workdir).resolve()
    log.parent.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    health = log.parent / "ENGINE_HEALTH.json"
    expect = Path(a.expect_rows) if a.expect_rows else None
    codes = {c.strip().upper() for c in a.codes.split(",")} if a.codes else None

    def logline(**kw):
        with open(log, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "out": str(out)} | kw) + "\n")

    chain = [tuple(l.strip().partition(":")[::2]) for l in a.chain.split(",") if l.strip()]
    ok, note = gate(Path(a.config), chain)
    if not ok:
        logline(status="refused", reason=note)
        print(json.dumps({"status": "refused", "reason": note}))
        sys.exit(4)
    web_denied = note == "web_denied"

    parts = [f"## FILE: {Path(c).name}\n\n" + Path(c).read_text(encoding="utf-8") for c in a.context]
    parts += [Path(a.brief).read_text(encoding="utf-8"), "TASK\n" + a.task, CONTRACT]
    prompt_file = out.parent / "prompts" / (out.stem + ".prompt.txt")
    prompt_file.parent.mkdir(exist_ok=True)
    prompt_file.write_text("\n\n---\n\n".join(parts), encoding="utf-8")

    final_reason = ""
    for engine, model in chain:
        key = f"{engine}:{model}"
        if not shutil.which(engine):
            logline(engine=key, status="skip", reason="CLI not on PATH")
            continue
        if circuit_open(health, key):
            logline(engine=key, status="skip", reason="circuit open")
            continue
        bad_output_seen, last_reason = False, ""
        for attempt in range(a.retries + 1):
            cmd, stdin = build_cmd(engine, model, prompt_file, workdir, web_denied, a.web)
            t0 = time.time()
            try:
                p = subprocess.run(cmd, input=stdin, capture_output=True, text=True,
                                   timeout=a.timeout, cwd=workdir)
                rc, stdout, stderr = p.returncode, p.stdout, p.stderr
            except subprocess.TimeoutExpired:
                rc, stdout, stderr = None, "", "timeout"
            body, summary, why = validate(stdout, expect, codes) if rc is not None else (None, "", "timeout")
            secs = round(time.time() - t0)
            if body is not None:
                out.write_text(body, encoding="utf-8")
                record(health, key, True)
                logline(engine=key, status="ok", attempt=attempt, secs=secs)
                print(json.dumps({"status": "ok", "engine": key, "out": str(out),
                                  "summary": " ".join(summary.split()[:150])}))
                return
            kind = classify(rc, stderr, stdout)
            last_reason = f"{why}; exit {rc}"
            final_reason = f"{key}: {last_reason}"
            if rc is not None and stdout.strip():
                (prompt_file.parent / (out.stem + ".rejected.txt")).write_text(stdout, encoding="utf-8")
            logline(engine=key, status="fail", attempt=attempt, kind=kind, reason=last_reason,
                    secs=secs, stderr_tail=stderr[-300:])
            if kind == "permanent":
                break
            if kind == "bad_output":
                if bad_output_seen:
                    break
                bad_output_seen = True
            if attempt < a.retries:
                time.sleep(30 * (attempt + 1))
        record(health, key, False, last_reason)
    print(json.dumps({"status": "exhausted", "chain": a.chain, "out": str(out), "see": str(log),
                      "last_reason": final_reason or "no engine ran",
                      "rejected_output": str(prompt_file.parent / (out.stem + ".rejected.txt"))}))
    sys.exit(3)


if __name__ == "__main__":
    main()
