# Think Tank → Render: submission contract

**Read this file first (`getFile` on `THINK_TANK_CONTRACT.md`) before submitting a video.**

You have one reliable path to this repo: the **Prototype4-1077 Pipeline Action**
(`getFile`, `putFile`, `listRenderRuns`, `getRun`, `getRelease`).
Do **not** use the GitHub connector or the `gh` CLI — neither is available.

---

## Easiest path: send plain JSON (no Base64)

If encoding a file body is unreliable for you, skip files entirely. POST the
submission as plain JSON:

    POST /repos/prototype4-1077/Prototype-Video/dispatches
    {
      "event_type": "submission",
      "client_payload": {
        "slug": "tomorrow-uses-old-footage",
        "submission": {
          "title": "Tomorrow Uses Old Footage",
          "voice": "liam",
          "series_label": null,
          "scenes": [
            { "text": "...", "visual": "..." }
          ]
        }
      }
    }

Nothing is Base64-encoded. The workflow writes the file, expands it, runs
preflight, and dispatches the render. Confirm with `listRenderRuns`.

## Alternative: commit the file yourself

Commit **one small file**: `build/<slug>/submission.json`

```json
{
  "title": "Beliefs Are Software Updates",
  "voice": "liam",
  "series_label": null,
  "visual_style": "literal_motion_graphics",
  "scenes": [
    { "text": "Most people think reality is stubborn.", "visual": "a settings panel locks every option except OLD BELIEF", "keywords": ["REALITY", "OLD BELIEF"], "visual_function": "mechanism" },
    { "text": "Your phone does something similar.", "visual": "a real phone camera locking focus", "visual_mode": "stock" },
    { "text": "Then the whole system opens.", "visual": "a luminous interface unfolding into deep space", "visual_mode": "hero" }
  ]
}
```

That is the **entire** submission. A workflow automatically:

1. expands it into the full `script.json` (narration preserved **exactly**),
2. assigns varied symbol families so the visual classifier passes,
3. splits any line over 220 characters on a sentence boundary,
4. writes `source-script.txt`, runs preflight,
5. drops `render.request` — **the render starts on its own**.

You do **not** need to write `script.json`, `source-script.txt`, or `render.request` yourself.

**Long-form only (Shorts paused).** Each render produces the landscape master
and publishing posts it with a generated thumbnail. Vertical Shorts are paused;
a submission can still opt in with `"render_outputs": ["youtube", "portrait"]`.

### Fields
| field | required | notes |
|---|---|---|
| `title` | yes | Video title. |
| `scenes[].text` | yes | Narration for that beat, verbatim. Never rewritten. |
| `scenes[].visual` | recommended | Plain description of what's on screen. Physical objects/places beat abstractions. |
| `scenes[].hero` | no | `true` = generated hero art instead of stock. Keep ≤ 5 per video. |
| `visual_style` | no | Set `literal_motion_graphics` for the approved *Reality Was Never Hidden* grammar. Non-hero scenes become animated literal storyboards unless overridden. |
| `scenes[].visual_mode` | no | `storyboard`, `stock`, `auto`, or `hero`. Use `stock` for exact documentary footage inside a graphics-first video. `auto` lets the literal-mechanism classifier decide. |
| `scenes[].semantic_anchor` | no | A concise description of the idea the visual must prove. Defaults to `visual`. |
| `scenes[].visual_function` | no | Prefer `literal_anchor`, `mechanism`, `contrast`, `recursion`, `boundary`, `choice`, `perspective_shift`, or `transformation`. |
| `scenes[].keywords` | no | Up to four short labels or concepts used by literal motion graphics. |
| `voice` | no | `liam` (default) or `june`. |
| `series_label` | no | Omit/`null` for standalone (no yellow eyebrow). Set only for a real series (DMT, Oxley, Reality Machine). |
| `invitation`, `end_card_question`, `evidence_boundary` | no | Sensible defaults are filled in. |

### Aim for
- **18–26 scenes**, one beat each; **300–400 words** total.
- Each `text` under 220 characters (longer is auto-split, but write it clean).
- **Vary the `visual` descriptions.** If every scene says "a room with a window,"
  the classifier collapses them into one family and preflight blocks. Mix
  objects, light, landscapes, paths, textures, time.
- Avoid "no text / no words" phrasing in `visual` — it makes the classifier
  think the scene is *about* language.

### Reproducing the Reality motion-graphics look

Set `"visual_style": "literal_motion_graphics"`. Write each `visual` as an
on-screen mechanism: a filter hiding evidence, counters changing value, a route
redrawing itself, a scale tipping, or a focus box selecting one object. Add
`visual_mode: "stock"` only where real footage represents the line exactly, and
use a small number of `visual_mode: "hero"` scenes for cinematic visual peaks.

This profile sends authored storyboard beats directly to `storyboard.py` before
the effects-still fallback. Ordinary submissions remain stock-first.

---

## Checking your work

- `listRenderRuns` → recent renders and their status/conclusion.
- `getRun` with a run id → status + conclusion for one run.
- `getRelease` with tag `video-<slug>` → the finished MP4 asset once it exists.

`render.request` is **deleted by the workflow after it fires** — that's normal,
not a failure. Confirm via `listRenderRuns`, not by looking for that file.

---

## Notes

- Narration is **never** rewritten or "optimized." What you submit is what is spoken.
- If preflight blocks, `build/<slug>/expand-blocked.txt` and
  `build/<slug>/preflight-report.json` explain why.
- Writing a full `script.json` by hand still works, but it's ~15 KB and often
  fails to write through the Action. Prefer `submission.json`.
