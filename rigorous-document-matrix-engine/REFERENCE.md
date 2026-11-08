# Reference

## Contents

- CONFIG.yaml schema
- Discovery and pings
- Exit codes
- Shared context files
- Build v1 formats
- Verdict grammar
- File formats
- Scout card
- Brief templates
- Orchestrator files and sign-off

## CONFIG.yaml schema

```yaml
title: "Groundwater contamination at Site X"   # example only; replace before use
purpose: "Expert report on causation and quantum"
audience: court            # court | regulator | board | journal
standard: "CPR Part 35 and PD 35"
locale: en-GB
voice: first_person        # first_person | institutional
style_bans: [em_dash, emoji, numeric_likelihood_percentages, unhedged_absolutes]   # check_draft.py fails only on em_dash; the rest are agent checks
epistemic_labels: [Fact, Analysis, Author evaluation, Legal/compliance risk]
citation: "[Doc ID, p. X]"
citation_offset: ""        # set only from this bundle's register; "0" when PDF and document pages match
paths: {work: /abs/scratch/, out: /abs/deliverables/, bundle: /abs/bundle/}   # absolute paths only
external_models: denied    # denied | allowed; allowed needs user confirmation per matter
web_search: denied         # denied | allowed; a missing key means denied. Denied: grok runs with --disable-web-search, codex and claude get no web tools, dispatch.py refuses any chain with gemini (exit 4)
secrets_source: "<store name>"   # key names only; never write a key into this file, a prompt file or RUN_LOG.jsonl
exclude_models: []        # full IDs the user has banned; discovery skips them
concurrency: 4             # orchestrator cap; dispatch.py has no semaphore
document_slug: "<slug>"    # orchestrator note; names scratch/vN/<slug>/
parts_per_matrix: 20       # orchestrator note; the third argument of make_matrix.py is a target, not a guarantee
max_kb: 16                 # part size in KB, the fourth argument of make_matrix.py: about half of (output tokens x 4 / 1024), so 16 suits an 8K-token output cap
reference_doc: ""          # orchestrator note; absolute path of the house .docx, or empty; empty means pandoc runs without --reference-doc
convergence_change_rate: 0.05   # orchestrator note; change_rate counts FIX, ADD, CUT, STYLE, RISK, LABEL, UNVERIFIED, ATTACK, PREEMPT, CONCEDE, SCOUT and INTEGRATE, and ignores OK, GAP and n/a
figures: false             # orchestrator note
chains:                    # engine:model, first engine to return valid output wins; full model IDs from ENV_CAPABILITIES.json, never aliases
  drafter:     "claude:<full-id-A>,claude:<full-id-B>"
  checker:     "claude:<full-id-B>,claude:<full-id-C>"
  red_team:    "claude:<full-id-C>,claude:<full-id-A>"
  scout:       "claude:<full-id-C>,claude:<full-id-B>"
  apply:       "claude:<full-id-B>,claude:<full-id-A>"
approved_at: null          # set only when the user's whole message is proceed; dispatch.py exits 4 while null
approved_message: ""       # the exact approving message, stored beside approved_at
```

Use absolute paths only, and refuse this file when any path is relative or the title is still the Site X example. Every chain entry is `engine:full-id`. dispatch.py refuses empty IDs, placeholders and Claude aliases such as `claude:sonnet`. Record on the sign-off that drafter, checker and red team use three different models from one vendor.

The chains above are the `denied` defaults. With `allowed`, propose external engines at the head of the checker, red-team and scout chains, using model IDs from `ENV_CAPABILITIES.json`. Dispatch to an external engine only after the user approves that chain and `approved_at` is set again. Example with `external_models: allowed` and `web_search: denied`: checker `codex:<id>,claude:<id-B>,claude:<id-C>`, red team `grok:<id>,codex:<id>,claude:<id-C>,claude:<id-A>`. Gemini joins a chain only with `web_search: allowed`, which scouts also need.

Keep a Claude model at the tail, leave drafter and apply on Claude, and keep privileged exhibits off external chains. Set `web_search: denied` unless the user allows queries.

The consistency auditor runs as an in-session sub-agent, not through `dispatch.py`. This role is manual: no script or brief exists. It edits the raw draft within its scope in SKILL.md and logs each change in CONSISTENCY_LOG.md, the only file it may add. The orchestrator diffs the raw draft against the apply output and fact-checks every changed row before the copy.

## Discovery and pings

Check `gemini`, `grok`, `codex` and `claude` on PATH. Ping each from a cwd outside the bundle. The prompt holds no path and no matter text. Check the reply text, because gemini exits 0 when it refuses an untrusted folder.

```
gemini -p "Reply pong. Do not use tools." --approval-mode plan --skip-trust -m <id>
grok -p "Reply pong. Do not use tools." --permission-mode plan --disable-web-search --cwd <dir outside bundle> -m <id>
codex exec --skip-git-repo-check --ephemeral -s read-only -C <dir outside bundle> -m <id> "Reply pong. Do not use tools."
claude -p "Reply pong." --model <id> --tools ""
```

Codex has no file-read tool. It reads files only through read-only shell commands, which its `-s read-only` sandbox permits and the output contract allows. Codex accounts support different IDs, and `codex debug models` lists the CLI's catalogue. The docs list IDs that an older CLI rejects, and the CLI updates itself, so ping each ID before use. A rejected ID exits 1 with `model_not_found`.

A CLI's own model list can be months stale. `gemini --list-models` omitted models the CLI accepts. Search the web for each vendor's latest models, with queries that name only the vendor and the words model id. Confirm each ID on the vendor's own docs page. Ping each candidate. Propose the newest that answers and is not on `exclude_models`.

`scratch/ENV_CAPABILITIES.json`, one entry per ID:
```
{"codex:<full-id>": {"source": "<docs URL>", "checked": "<date>", "ping": "ok", "output_tokens": <n>}}
```

## Exit codes

| Script | Code | Meaning |
|---|---|---|
| dispatch.py | 0 | output validated and written |
| dispatch.py | 3 | chain exhausted |
| dispatch.py | 4 | gate refused: `approved_at` null, external engine while denied, gemini while `web_search` denied, or a placeholder in the chain |
| dispatch.py | 2 | usage error or an input file not found: fix the command |
| merge_matrix.py | 1 | a row has no finding, a part is missing or a verdict code is unknown. It removes any earlier master_matrix.md, NOTES.md and merged parts, and counts.json lists the row ids |
| apply_updates.py | 1 | missing or invalid updated part; nothing written |
| check_draft.py | 1 | em dash, numbering gap, duplicate number, empty file or leaked process text such as `CROSS:` or `finding not applied`; with `--numbered` also unnumbered prose; with `--final` also open markers |

dispatch.py retries a transient failure once after 30 seconds, with `--timeout 900` and `--retries 1` by default. It retries bad output once. Each failed engine try counts once toward the circuit, and 3 consecutive failures skip the engine for 15 minutes. Circuit state is in `scratch/ENGINE_HEALTH.json`.

## Shared context files

Contents, before the templates below:
- CONTEXT.md: absolute paths, tools and versions, engines available, do-not-scan paths, the citation convention, the Doc p. formula, where bundle text lives. Add a page-image path only after that file exists. Refresh it when anything changes.
- BUNDLE_REGISTER.md: doc ID, title, page count, text path, OCR status, known quality problems. Write it after ingest.
- LEDGER.md: verified facts with source and loop, rejected findings with reasons, unreachable sources with date and error, cached sources under `scratch/sources/`.

**CONTEXT.md**
```
Run: <title>. Today: <date>. Loop: <LN>, input v<N>.
Absolute paths: work <...>/scratch, bundle text <...>/scratch/bundle_text, images <...>/bundle
Tools: pandoc <ver>, pdftotext <ver>, python3 <ver>. OCR already done for: <doc IDs>.
Engines: <engine:model list>.
Do not scan: <mounts or folders>. Never search from /.
Every path in the task is absolute. For a table, a certificate or a figure, open the page image under the images path.
Citation: [Doc ID, p. X]; Doc p. = PDF p. - <offset from this bundle's register>.
Style: <inline the style bans and epistemic labels>. Full config: <abs path>/CONFIG.yaml.
Markers: [VERIFY] [CONFIRM] [FIGURE: id] [LEGAL/RISK].
```

**LEDGER.md**
```
EXAMPLE ONLY: delete these sample rows before the run
## Verified facts
- F-012 | benzene 14.2 ug/l, BH3, 2019 | Doc 12, p. 40 | L1
## Rejected findings: do not re-raise without new evidence
- L1 para 14 "benzene 14.2 ug/l" | checker said p. 41 | p. 40 is correct, table header on p. 40 | Doc 12, p. 40
## Unreachable sources
- EA report 2011 | 2026-11-08 | 404 at <url> | open, retry once in L5
## Cached sources
- /abs/scratch/sources/ISO-5667-11.pdf | fetched L1
```

Key a rejection by loop, paragraph number and a quoted phrase, never by row ID, because row IDs restart at R0001 each loop. A ledger line is a pointer: the checker still opens the page. Mark an unreachable source retried-failed after its one retry.

## Build v1 formats

Page tag: `=== PDF p.N | Doc p.M ===`. Extract with `pdftotext -layout`.

Paragraph: `N.N **Lead-in.** [Label] Text [Doc ID, p. X].` The number comes first and `[Label]` is one epistemic label from CONFIG. Unknowns get markers: `[VERIFY]`, `[CONFIRM]`, `[FIGURE: id]`, `[LEGAL/RISK]`. Each drafter file ends with `---ANNEX---` and the author list. The orchestrator splits each file on that line, puts the text above it in the report, puts the author list into the sign-off checklist, and accepts a file only with at least one `N.N` paragraph and one annex line.

Drafter `--task`: `SECTION: <absolute path of the section outline>. CONFIG: <absolute path of CONFIG.yaml>.`

## Verdict grammar

A finding is one physical line. Segments are separated by ` // `, with spaces, and nowhere else in the detail. Each segment starts with a code in capitals, then `: detail`. Use `<br>` for a break. The merge cannot detect a line cut at a newline.

```
OK: checked against Doc 12, p. 40
FIX: REPL: <exact replacement text for the whole row, on one line>
ADD: INS: <text to append to this row>
CUT: unsupported by Doc 7; no other source found
UNVERIFIED: Doc 22 not in bundle; soften or add [VERIFY]
STYLE: passive lead-in; em dash
RISK: states a legal conclusion; flag for counsel
LABEL: presented as Fact but is Analysis
n/a: heading
ATTACK: <vulnerability> // PREEMPT: <defence text>
GAP: <missing evidence>
CONCEDE: <narrower scope to adopt>
SCOUT: card S-03 accepted; <text to integrate>
INTEGRATE: <edit from an external review list>
```

Several verdicts on one row always go in separate ` // ` segments. A segment that does not start with a known capital code, other than `n/a`, is listed under `unknown_codes` in `counts.json`, and the merge exits 1. Re-brief the agent and merge again. `REPL:` and `INS:` are for the apply agent to read. The scripts do not parse them.

Apply rules by code:
- FIX, ADD, CUT, STYLE: apply after the spot check.
- UNVERIFIED: soften the claim or add `[VERIFY]`.
- RISK: hedge and add `[LEGAL/RISK]`.
- LABEL: relabel or rewrite to match the label.
- ATTACK + PREEMPT: add the defence, rewritten in the document's voice after a source check. ATTACK alone: narrow the claim.
- CONCEDE: adopt the narrower scope.
- GAP: no text change in L3. It goes to a scout in L4.
- SCOUT: integrate accepted card text.
- INTEGRATE: apply listed edit after spot check.
Two codes on one row that clash: keep the original and note finding not applied.

## File formats

`matrix_part_XX.md` and `findings_part_XX.md`:
```
| Row | Location | Current text | Findings |
|---|---|---|---|
| R0042 | para 3.4 | 3.4 **Levels.** ... | OK: Doc 12, p. 40 |
```
In cells, `<br>` is a line break and `\|` is a literal pipe. Checkers copy the part file and fill col 4 only. Agents still drift, so `merge_matrix.py` repairs it and writes the repaired `merged_part_XX.md` only on success. Extra cells and a moved col 3 are listed under `problems` in `counts.json`; re-dispatch that part before apply.

`updated_part_XX.md`:
```
| Row | Location | New text | Change note |
|---|---|---|---|
| R0042 | para 3.4 | = | OK, no change |
| R0043 | para 3.5 | 3.5 **Trend.** ... | FIX applied // CROSS: para 7.2 repeats the old figure |
| R0044 | para 3.6 | DELETE | CUT applied |
```
`=` alone in New text keeps the row, as does a blank cell and any unlisted row. `DELETE` alone removes it. Any other value replaces the whole row, so keep notes out of New text and keep it on one physical line. Exit 1 writes nothing.

## Scout card

```
### S-03  answers GAP in R0187, file scratch/vN/scout_NN.md
Source: <full citation, URL or DOI>
Read in full: yes | abstract only
Cache: scratch/sources/<file>
Page and quote: <page>; <short quote>
Claim supported: <one sentence>
Limits: <sample, jurisdiction, date, conflicts>
Engine: <engine and model, or none>
Status: proposed | accepted, only if Read in full is yes | rejected: <reason>
```

The scout writes the card as proposed. The orchestrator alone sets the status in `SCOUT_FINDINGS.md`, then adds an accepted source to the documents-relied-on appendix in the same pass. A scout query names the missing evidence only and carries no bundle text.

## Brief templates

Keep each brief under 200 words. fanout.py passes `--codes` for fact-check (`OK,FIX,ADD,CUT,UNVERIFIED,STYLE,RISK,LABEL,N/A`) and red team (`OK,ATTACK,PREEMPT,GAP,CONCEDE,N/A`), and reads chains and concurrency from CONFIG.yaml. To retry parts with extra guidance, run `fanout.py --only 02 --retry-note "<what to fix>"`. A single dispatch uses `--task "... RETRY: <what to fix>"` and the same `--out`. Scout dispatches add `--web`. A rejected answer is kept in `prompts/<name>.rejected.txt` beside the output, and the exhausted message names the last reason. With `--context`, `dispatch.py` puts each context file under its file name before the brief, then the task, then the output contract: print the result between markers, then a summary under 150 words. Briefs do not repeat the context or the contract. Put one absolute path in `--task`. Drafters get two labelled paths. On matrix dispatches pass the same file to `--expect-rows`, because the script never opens `--task`.

**AGENT_BRIEF.md** for drafters
```
Draft only the section at the SECTION path in the task. Read voice, style_bans and epistemic_labels only from the CONFIG path in the task.
Format: N.N **Lead-in.** [Label] Text [Doc ID, p. X]. Start every paragraph with its number. Label is one epistemic label from CONFIG.
Never invent a source. Keep [LEGAL/RISK] as a marker.
End with a line ---ANNEX--- and the author list.
```

Split the annex off as described above. No script does it.

**FACTCHECK_BRIEF.md**
```
The task names a matrix part. Output that table, same rows, col 4 filled.
Copy columns 1 to 3 unchanged. Use one physical line per row, a backslash before each literal pipe, and <br> for line breaks. Do not fence the table.
Check every number, date, quote, cite, cross-reference and derivation. Check the epistemic label and the cross-references inside the draft.
Source order: bundle text and images, correspondence, primary law and standards, literature. The bundle decides facts. Primary law decides propositions of law. Literature overrides neither. When two sources of different rank disagree, such as law against literature, add RISK and do not change the number.
Do not trust earlier fixes. Use the ledger to locate sources, then open them.
A draft value that differs from its source is FIX: REPL: <the whole corrected row>. Never answer it with RISK alone.
Write col 4 as CODE: detail, with segments divided by " // ". Codes: OK, FIX, ADD, CUT, UNVERIFIED, STYLE, RISK, LABEL, n/a (any case). Every OK cites a file and page.
Summary: name the three worst row ids. Do not count.
```

**APPLY_BRIEF.md**
```
The task names a merged_part file. Output | Row | Location | New text | Change note |.
Open the cited source before any replacement, including a STYLE rewrite or a pasted defence.
New text "=" keeps the row. "DELETE" removes it. Anything else replaces the whole row. Return one line for every row. Unchanged rows use "=".
Use one physical line per row. Copy the Row id unchanged. Write a line break as <br> and a literal pipe as a backslash followed by a pipe. A row with extra cells fails the whole apply.
For ADD, append the INS text after the row text with <br><br>. Give it no new number.
Apply every segment of a row to that same row. Put every CROSS: <note> in the change note.
Wrong finding: New text "=", note starts "finding not applied: <reason>".
``` 

Copy every "finding not applied" note into the ledger. No script does this. Read apply_report.json for kept, replaced and deleted.

**REDTEAM_BRIEF.md**
```
You are opposing counsel, a hostile regulator and a forensic auditor at once. Keep each attack in its own segment.
The task names a matrix part. The bundle is in the paths in CONTEXT.md.
Find: unearned inferences, ignored adverse evidence, absolutes, weak assumptions.
Output the table, same rows, col 4 filled. Write each code as its own segment, divided by " // ". An attacked row needs an ATTACK segment and a PREEMPT segment. Use CONCEDE for a point you cannot dispute. Use GAP only when a necessary document is absent, in one sentence. Mark unchallenged rows OK and headings n/a. Do not emit FIX, CUT, ADD or STYLE.
After the table, before the end marker, add "## Dossier" with at most three counter-narratives in 120 words. Do not soften attacks.
Summary: counts and the three most damaging attacks.
```

merge_matrix.py collects every part's Dossier into one NOTES.md. After L3 merges, copy that NOTES.md to deliverables/audit/RED_TEAM_DOSSIER.md.

## Orchestrator files and sign-off

`GAPS.md`, one line per GAP: `<loop> | para N.N | "<quoted phrase>" | <missing evidence> | scout_NN.md or none`.

`deliverables/audit/LOCK.json`: `{"file": "deliverables/frozen/Document_v6.md", "sha256": "<hash>", "locked_at": "<date>"}`.

Deliverables: `deliverables/Document_v1..v6.md` and `.docx`, plus the illustrated `.pdf` if figures were made, built only from the frozen docx. In `deliverables/audit/`: `vN_master_matrix.md`, `vN_counts.json`, `vN_apply_report.json`, `vN_CROSS_NOTES.md` and `vN_NOTES.md` per loop, then `RED_TEAM_DOSSIER.md`, `SCOUT_FINDINGS.md`, `RUN_LOG.jsonl`, the approved `CONFIG.yaml` and `LOCK.json`.

`AUTHOR_SIGN_OFF_CHECKLIST.md`, in priority order: AI-use disclosure, author credentials and independence, every `[CONFIRM]`, unresolved `[VERIFY]` with sources not reached, `[LEGAL/RISK]` items, judgement calls, figure inventory. Each line ends `Signed: <name>, <date>`. Mark the docx cover DRAFT until every required line is signed.

Final message, kept short: file locations, changes per loop as `replaced` and `deleted` from `apply_report.json`, verdict totals from `counts.json` on a separate line, engine fallbacks from `RUN_LOG.jsonl`, open items, anything skipped.
