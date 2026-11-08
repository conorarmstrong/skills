# skills

A collection of agent skills. Each folder is one skill, with a `SKILL.md` that the agent loads and any supporting files beside it.

## Skills

| Folder | What it does |
|---|---|
| [rigorous-document-matrix-engine](rigorous-document-matrix-engine) | Drafts long, fully referenced documents from a source bundle, then hardens them over versioned loops of row-by-row fact-checking, adversarial red teaming and gap-closing research. An approval gate, model fallback chains and bundled scripts keep each run controlled. |

## Install a skill

Copy its folder into your skills directory:

```
cp -r rigorous-document-matrix-engine ~/.claude/skills/
```

Some skills carry scripts with their own requirements. Each skill folder says what it needs. For `rigorous-document-matrix-engine`: Python 3 with `pip install -r requirements.txt`, and `pandoc` for the docx build. The `gemini`, `grok` and `codex` command line tools are optional and are used only when you approve external models at the start of a run.

## Add a skill

Add a folder named after the skill, put a `SKILL.md` with `name` and `description` frontmatter inside it, and add a row to the table above.

## Licence

MIT. See [LICENSE](LICENSE).
