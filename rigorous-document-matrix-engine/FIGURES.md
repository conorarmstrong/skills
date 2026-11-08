# Figures

Run on the locked version, or any version that exists as `.docx`. The `.md` keeps its `[FIGURE: id]` placeholders. Figures live only in the docx and PDF, so re-run the pipeline on every new docx.

## Rules for every figure
- Values come only from verified document tables or bundle page images. No speculative points.
- Schematics say "not to scale".
- Where the source series is not tabulated, either draw the structure only or digitise the plot.
- Look at every rendered PNG yourself and recheck the plotted numbers against the text.

## Kinds

| Kind | Tool | Notes |
|---|---|---|
| Chart | Chart.js in headless Chromium, 2x screenshot | Data from verified tables only |
| Diagram | Excalidraw, Graphviz or Mermaid | Flows, timelines, decision trees, statutory routes |
| Overlay | Bundle page render plus registered overlay | At least 3 fixed reference points. Report residual error. Show error rings. If registration fails, say so and draw nothing. |
| Digitised plot | Calibrate axes from printed ticks | Save raw CSV with calibration notes. Check against values the text states. Label "Digitised, approximate". |
| Illustration | Image model | No text in image. Label "Illustration only, not to scale, not evidence". Never for data or site features. |

## Manifest

One `scratch/figures/manifests/<id>.json` per figure:
```json
{"id": "fig5-1", "label": "Figure 5.1", "match": "FIGURE: fig5-1",
 "kind": "chart", "spec": "charts/fig5-1.js", "caption": "...", "width_in": 6.3}
```
`match` is a unique substring of the placeholder paragraph. For a figure without a placeholder, add `"after": "<start of paragraph>"`.

## Injection
Replace each placeholder paragraph with a centred image and a caption: label bold, text italic. Placeholders with no manifest stay as text and are listed. The script must report any manifest with no match. Inserted count must equal manifest count.

## Gotchas
- Docx paragraphs may carry a tab, not a space, after the paragraph number. Normalise before matching.
- A CUT or reworded placeholder orphans its manifest. Re-point it with `after` or update `match`.
- Figure agents may spot statements in the text that look wrong. Pass those to the author.
