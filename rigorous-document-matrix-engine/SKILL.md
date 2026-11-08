---
name: rigorous-document-matrix-engine
description: Drafts and hardens long, fully referenced documents from a source bundle, such as expert reports, regulatory filings, white papers and valuation reports. Uses bundled scripts for the matrix split, merge and rebuild. Use when asked to draft from evidence or correspondence, or to fact-check, stress-test or matrix review an existing draft through versioned loops, six by default.
---

# Rigorous document production: approval gate, fact-check matrix, red team, scouts

The orchestrator holds state and runs scripts. Dispatched engines are read-only. They print the result between markers and dispatch.py writes the file [dispatch.py: CONTRACT]. Trust nothing because an earlier loop touched it.

After a crash, reload CONFIG.yaml, LEDGER.md, RUN_LOG.jsonl and ENGINE_HEALTH.json first.

Read [REFERENCE.md](REFERENCE.md) by its absolute path before writing briefs. It holds the schema, grammar, formats, exit codes, templates and the detail named below. Read [FIGURES.md](FIGURES.md) by its absolute path when `figures` is true or the draft contains `[FIGURE:]`. Never open either by a relative link.

## 0. Setup and approval gate

Dispatch nothing until step 5 returns proceed. Proceed means the user's whole message is exactly proceed. A plan-mode approval is not this gate. dispatch.py refuses to run while `approved_at` is null and exits 4 [dispatch.py: gate]. make_matrix.py and apply_updates.py do not check it, so call neither before the gate opens.

1. **Draft `scratch/CONFIG.yaml`** from REFERENCE.md. Mark guesses `# proposed`. Write absolute paths. Never copy sample titles, offsets or page maps.
2. **Confidentiality.** External CLIs get bundle text only with `external_models: allowed`. Client, privileged and personal material defaults to `denied`. When denied, every chain is Claude only and dispatch.py refuses gemini, grok and codex [dispatch.py: gate]. Claude still receives the text, so name it as a vendor.
3. **Discovery.** Run setup in a session that can execute commands. When denied, do not require or ping gemini, grok or codex. Otherwise follow the Discovery steps in REFERENCE.md. A CLI's own model list can be months stale or ahead of your account, so confirm each ID on the vendor's docs page and by a read-only ping. Never guess an ID. Skip `exclude_models`. Set `max_kb` to about half of (output tokens x 4 / 1024) for the smallest output limit in any chain [make_matrix.py: usage]. Write `scratch/ENV_CAPABILITIES.json` with source and date for each ID.
4. **Secrets.** Never read, pass, print or log API keys. The CLIs use their own login. If one is not logged in, stop and tell the user.
5. **Approval gate.** Show one table of every CONFIG.yaml setting, the resolved chains, the spend cap and every vendor that receives text, Claude included. dispatch.py does not enforce the spend cap. Repeat until the user says proceed. State again that text leaves the machine before changing `external_models` to allowed. Record `approved_at` only from a message whose whole text is proceed, and store that message in `approved_message`.

Ask again mid-run when a chain is exhausted, a new engine or model is needed outside the approved chain, the convergence rule adds a loop, or L5 changes a key figure. A key figure is any number, date, sum, name, quotation, citation, causation finding or legal characterisation. A move to the next model in an approved chain needs no approval. dispatch.py logs it in `scratch/RUN_LOG.jsonl`.

Before L3, read RUN_LOG.jsonl. If the red-team engine was skipped or shares the drafter's model family, stop and ask. Do not start L3. When a chain exits 3, start no further dispatch. Wait for in-flight calls, then ask.

## 1. Roles and fallback chains

Drafter, checker, red team, scout and apply agent have ordered chains, approved at the gate. Chains use `engine:model` with full model IDs from ENV_CAPABILITIES.json. dispatch.py refuses aliases, empty IDs and placeholders [dispatch.py: gate]. End every external chain with two pinned Claude IDs. Defaults when external models are allowed:

| Role | Config key | Default chain | Output |
|---|---|---|---|
| Drafter | drafter | claude:`<id-A>`, claude:`<id-B>` | `scratch/sections/NN.md` |
| Checker | checker | codex:`<id>`, claude:`<id-B>`, claude:`<id-C>` | `findings_part_XX.md` |
| Red team | red_team | grok:`<id>`, codex:`<id>`, claude:`<id-C>`, claude:`<id-A>` | `findings_part_XX.md`, dossier |
| Scout | scout | gemini:`<id>`, claude:`<id-C>`, claude:`<id-B>` | `scratch/vN/scout_NN.md` |
| Apply agent | apply | claude:`<id-B>`, claude:`<id-A>` | `updated_part_XX.md` |
| Consistency auditor | none | in-session Claude | edited raw draft, `CONSISTENCY_LOG.md` |
| Lookups | none | one pinned Claude ID | `scratch/BUNDLE_REGISTER.md`, via dispatch.py |

- `web_search` defaults to denied. Gemini has no flag to disable web tools, so dispatch.py refuses any chain with gemini unless `web_search` is allowed at the gate. Codex and Claude get web tools only on a scout dispatch with `--web`.
- The first model of the drafter, checker and red-team chains must differ. Fallbacks may overlap. Nothing in the scripts compares them, so check the table before approval. If the engine that returns a finding is the drafter's model, discard the part and pause. When denied, use three different Claude models.
- The auditor changes numbering and cross-references only. Any other edit is a new matrix row that must pass apply.
- Run matrix tasks through `scripts/fanout.py` and single tasks through `scripts/dispatch.py` with `--config`. dispatch.py prepends only the `--context` files named on its command. Claude gets Read, Grep and Glob only [dispatch.py: build_cmd].
- fanout.py enforces `concurrency` from the approved CONFIG.yaml, 4 if the key is missing. Single dispatches such as drafters and scouts are yours to pace; each takes one slot.
- Read-only modes do not keep client text on the machine. Gemini and Grok run in plan mode and Codex in its read-only sandbox, and all three read files through the engine's own tools. dispatch.py passes `--disable-web-search` to grok unless `web_search` is allowed [dispatch.py: build_cmd].

**Fallback during the run.** dispatch.py retries transient failures once on the same engine, then moves on. It moves on at once after auth errors, unknown models, an untrusted folder or a missing CLI. It retries bad output once: missing markers, or rows missing, unclosed or unfilled. Each failed engine try counts once toward the circuit. After 3 consecutive failures the engine is skipped for 15 minutes [dispatch.py: classify, CIRCUIT_LIMIT]. Exit codes are in REFERENCE.md. On exit 3:
1. Leave completed parts alone. Re-dispatch the parts that own the row ids merge_matrix.py lists. Run apply_updates.py only after merge exits 0.
2. Pause and ask the user: wait and retry, add an engine, or stop. Never swap engines silently. A skipped engine is a swap. To reset a circuit, delete `scratch/ENGINE_HEALTH.json`.
3. Every engine switch goes in RUN_LOG.jsonl.

## 1a. Shared context: do the work once

Create `scratch/CONTEXT.md`, `scratch/BUNDLE_REGISTER.md` and `scratch/LEDGER.md` at setup, even if empty. Pass all three absolute paths on every dispatch. If one is missing, stop. REFERENCE.md lists their contents.

- A ledger entry tells a checker where the source is. It does not excuse the check. The checker still opens the cited page. Mark a finding UNVERIFIED when it names no bundle path and page.
- Never raise a rejected finding again without new evidence. Drop a finding that matches a rejected ledger line and cites no new path.
- Never retry an unreachable source in the same loop. L4 retries a GAP source once. L5 retries each remaining source once.
- After merge, add only rejected findings and unreachable sources. Add a verified fact only after apply has kept it. Key entries by loop, paragraph number and a quoted phrase, never by row id, because row ids restart at R0001 each loop.
- Keep each file under about 2,000 words. Count before each dispatch. Keep privileged strategy out of LEDGER.md.

## 2. Build v1

1. Extract instructions and constraints from correspondence locally into `scratch/instructions.txt`. Never send correspondence to an external engine.
2. Build page-tagged text per bundle document with `pdftotext -layout`, tagging `=== PDF p.N | Doc p.M ===`. Compute M from `citation_offset` in CONFIG.yaml and write the formula into CONTEXT.md. If a page has no text, record OCR missing in the register and put `[VERIFY]` on every value from that page. For any table value, certificate or figure that matters, view the page image. Write BUNDLE_REGISTER.md.
3. Write `scratch/AGENT_BRIEF.md` from the template in REFERENCE.md. Mark anything uncertain as unverified. Orchestrator briefs carry errors too.
4. Fan out drafters, one dispatch per section. Set `--brief` to the AGENT_BRIEF.md path and `--out` to `scratch/sections/NN.md`. Set `--task` to two labelled absolute paths, SECTION and CONFIG. Paragraph and annex formats are in REFERENCE.md. Split each file on `---ANNEX---` and keep the annex out of the report.
5. Assemble `scratch/Document_v1.md` and run check_draft.py on it. It checks no citations. If it exits 1 or is missing, do not build the docx. Build as in section 4. After exit 0, copy v1 to `deliverables/` as the L1 input.

## 3. Loop schedule

Every loop starts from a fresh matrix of the latest reviewed version, in `scratch/vN/<document-slug>/`. make_matrix.py refuses a directory that already holds a matrix. If merge exited 0, do not rebuild. If it exited 1, keep the directory and re-dispatch the failed parts. Never delete a matrix that holds findings. Never skip a scheduled loop unless the user says stop. Matrix `deliverables/Document_vN.md` only after the copy from the reviewed raw file. If the user orders a loop skipped, renumber the later inputs and append `{"status": "loop_skipped", "loop": "L2", "user_order": "<message>"}` to RUN_LOG.jsonl.

| Loop | Input | Mode | Output |
|---|---|---|---|
| L1 | v1 | fact-check | v2 |
| L2 | v2 | fact-check | v3 |
| L3 | v3 | red team; apply ATTACK, PREEMPT and CONCEDE only; list GAP ids in `GAPS.md` | v4 |
| L4 | v4 | scouts on GAP ids, accepted cards only, plus fact-check of every row | v5 |
| L5 | v5 | full fact-check, apply, re-check replaced ids, then lock | v6 |

Lock means a copy in `deliverables/frozen/` with its sha256 in `deliverables/audit/LOCK.json`. The orchestrator writes both. No script does.

**Convergence rule.** `change_rate` in counts.json is the share of rows, excluding rows marked only n/a, that carry a text-changing verdict. After L2, take the higher of `change_rate` and the share of rows that apply_report.json shows as replaced. If it exceeds 0.05, run one extra fact-check loop in `scratch/v2b/` before L3 and keep the version numbers. The threshold is a default. If L5 changes a key figure, do not lock. Report the list and ask.

## 4. One loop, step by step

```
set -euo pipefail
S=<absolute skill dir>/scripts; CFG=<absolute run root>/scratch/CONFIG.yaml
eval "$(python3 -I $S/loop_env.py $CFG)"          # exports R D SLUG PARTS MAX_KB REF; exit 1 on a bad or unapproved config
V=<input version>; W=$((V+1)); M=$R/scratch/v$V/$SLUG
python3 -I $S/make_matrix.py $D/Document_v$V.md $M $PARTS $MAX_KB
python3 -I $S/fanout.py --config $CFG --matrix-dir $M --mode check     # L3: --mode redteam. Exit 1 lists failed parts: rerun with --only
python3 -I $S/merge_matrix.py $M          # exit 1: fix the parts counts.json names, never rerun make_matrix.py
python3 -I $S/fanout.py --config $CFG --matrix-dir $M --mode apply
python3 -I $S/apply_updates.py $M $R/scratch/v$V/Document_v${W}_raw.md   # exit 1 writes nothing
# update LEDGER.md; the auditor edits the raw file from $M/CROSS_NOTES.md and the merge problems list; fact-check that diff; then:
cp $R/scratch/v$V/Document_v${W}_raw.md $D/Document_v$W.md
mkdir -p $D/audit && cp $M/master_matrix.md $D/audit/v${V}_master_matrix.md && cp $M/counts.json $D/audit/v${V}_counts.json
for f in apply_report.json CROSS_NOTES.md NOTES.md; do cp $M/$f $D/audit/v${V}_$f; done
# L3 only: cp $M/NOTES.md $D/audit/RED_TEAM_DOSSIER.md
cp $R/scratch/RUN_LOG.jsonl $R/scratch/CONFIG.yaml $D/audit/
python3 -I $S/check_draft.py $D/Document_v$W.md --prev $D/Document_v$V.md --numbered
pandoc $D/Document_v$W.md ${REF:+--reference-doc "$REF"} -o $D/Document_v$W.docx
```

check_draft.py exits 1 on em dashes, duplicate or gapped `N.N` numbers, an empty file, leaked process text such as `CROSS:` and `finding not applied`, and with `--numbered` any unnumbered prose outside headings, tables, bullets, quotes and numbered lists, so keep report prose out of those. Run it with `--final` before lock: open markers then fail too. Banned words never set the exit code, so have a checker or the red team decide each hit. Never alter a quotation to clear the dash check. Set it in a fenced block, which the check skips.

- **Checkers** verify every number, date, quote, citation, cross-reference, derivation and epistemic label, in the source order in FACTCHECK_BRIEF.md. A table or list run is one row, so the finding must cover every figure in it. From L2 on they re-verify earlier fixes, so pass the prior master_matrix.md in `--task`. An authority absent from the bundle and `scratch/sources/` is UNVERIFIED.
- **Red team** attacks unearned inferences, ignored adverse evidence, absolutes and weak assumptions. Merge collects every part's dossier into NOTES.md. Copy it to `RED_TEAM_DOSSIER.md`.
- **Scouts** get one GAP each, write to their own `--out`, and carry no bundle text in their query. Every card is a proposal. The orchestrator alone sets accepted or rejected in `SCOUT_FINDINGS.md`. Accept only after reading the source in full, and add it to the documents-relied-on appendix in the same pass. Apply only accepted cards. Scouts need `web_search: allowed` and run with `--web`.
- **Apply agents** spot-check the primary source before changing any number, date, page, quote or attribution. The change note names the file and page opened. If a finding is wrong, they keep the original and write `finding not applied: <reason>`. They never add numbered paragraphs. Cross-section effects go in the change note as `CROSS: <note>`. The script only copies these to CROSS_NOTES.md. Edit every CROSS location and fact-check those rows again.
- **Consistency auditor** settles agent conflicts by reading the source, never by averaging. It works only on ids in CROSS_NOTES.md and the merge problems list. It logs every change in `CONSISTENCY_LOG.md`. Check each `para N.N` target by hand, because no script does.
- **Orchestrator** confirms every copied output on disk with `ls` and check_draft.py.

## 5. Known failure modes

- Column drift. merge_matrix.py repairs it only when col 4 is empty and col 3 starts with a verdict code. It lists each repair in `problems`. Read `problems` after every merge.
- Fix passes add errors, such as a page off by one, and checkers "fix" correct values. Fact-check the diff after every apply, L5 included.
- Agent change counts do not add up. Trust apply_report.json, not the summary, and only when `problems` is empty.
- A part that echoes OK with no file citation is bad output. Reject it at review. dispatch.py judges success by output, not exit code, and rejects invented verdict codes when `--codes` is set.
- Cross-section drift. List repeated dates and figures at ingest and grep them after apply.
- Scratch holds the evidence, including `prompts/` folders beside every output. Treat it as confidential and delete it at sign-off. Delete generated chart rasters only. Keep page images until sign-off.

## 6. Deliverables and sign-off

The document is a draft until the author clears `AUTHOR_SIGN_OFF_CHECKLIST.md`. check_draft.py exits 0 with open markers, so the checklist is the only gate. Mark the docx cover DRAFT until every required line is signed. REFERENCE.md lists the deliverables, the checklist order and the final message format. The final message is short.
