# AGENT.md — Instructions for any AI operating this repo

You are making a mystical-philosophical TikTok video for James using this repo's
cloud render farm. You need NO video tools — GitHub Actions renders everything.
You only need: (1) the connected GitHub app, (2) this file.

REPO: jameswatson1077/tiktok-videos (private)
ACCESS: Use the workspace's connected GitHub app. This connection is persistent across
ChatGPT/Codex instances. Never ask James to paste a personal access token and never put a
credential in a file, command, commit, or response. If the GitHub app is unavailable, report
that connection as the blocker instead of requesting a secret.
API BASE: https://api.github.com/repos/jameswatson1077/tiktok-videos

## Step 0 — Read context (GET file contents via API or git clone)
- pipeline/HANDOFF.md      — full pipeline docs
- pipeline/style_profile.md — James's writing voice + visual spec
- pipeline/memory.json      — READ "notes" (his standing feedback) and respect it.
  Current standing rules: slides must be LIT-but-moody (window light, god rays,
  lamplight, golden hour; only a few near-dark slides), footage must match the
  spoken words (especially endings), and every build creates both a 1080x1920 9:16
  portrait social export and a native 1920x1080 16:9 regular-YouTube export. Never
  stretch or pillarbox the portrait render to make the YouTube version. The portrait
  remains letterboxed with yellow keyword captions. Titles must wrap and shrink
  automatically when needed so they remain fully inside the portrait safe area.
  No more than 35% of finished runtime may come from still images. Animated stills,
  depth moves, keyframes, and pan/zoom all count toward that 35%; at least 65% must
  be genuine footage where people or objects actually move. Check
  motion_report.json before delivery.
  Acquire genuine stock scenes before creating any still. Every still must begin
  from the saved public frame of the closest related selected stock scene, receive
  the complete reference/exposure/detail/depth/background/internal-motion/light/
  grade/grain path, and pass still_reference_report.json. Never use raw stills or
  pan/zoom-only slides; if reference-conditioned generation fails, use stock video.
  Match the MECHANISM of each spoken line, not merely its mood. A person is one
  symbol among many and must have a role (observer, chooser, explorer, scale,
  collective, creator, guardian, performer, relationship). New normal videos use
  at least six symbol families, no more than three consecutive beats from one
  family, and roughly half or less human presence. Avoid generic thoughtful-person
  footage. Check visual_symbol_report.json before delivery.
  Every render must create at least three genuinely distinct background-music choices.
  Keep every choice in artifacts/Releases, but default delivery shows only the two
  files named in music_variants.json `delivery`: Deep Current in portrait and native
  16:9 YouTube. Do not show links for the other music choices unless James explicitly
  asks for them. For an older manifest without `delivery`, find the variant labeled
  Deep Current and use its matching portrait/YouTube filenames. final.mp4 remains an
  alias of choice 1 for compatibility.

## Step 1 — Write the script file
Create build/<slug>/script.json  (slug = short-dashed-title):
{ "title": "Three Or Four Words", "slug": "<slug>",
  "visual_policy": "diverse_symbols",
  "scenes": [ { "text": "One sentence/beat (max ~25 words).",
                "keywords": ["2-4 words that appear IN that text"],
                "semantic_anchor": "load-bearing idea",
                "visual_function": "what the image explains",
                "symbol_family": "one family from visual_symbols.py",
                "human_role": "only if a person appears",
                "query": "physical searchable action: lit-but-moody, literal to the line" } ] }
Rules: 18-26 scenes and 300-400 words if YOU write the script (second person,
poetic-direct, quiet powerful ending — see style_profile.md).
If James supplies script text: split it into scenes VERBATIM (never rewrite), any length.
If James supplies a voiceover mp3: also commit it as build/<slug>/vo.mp3 and put
"user_vo": true at the top level. (vo.mp3 is gitignored — force-add it: git add -f,
or use the contents API which ignores .gitignore.)
If James explicitly says **June Oxley**, add top-level `"profile": "june_oxley"`.
Never infer this profile for another video. It automatically changes only that video's
footage search/ranking, warm rural grade, hero-shot styling, music, sound design, and
separate taste learning. See the June Oxley section in `pipeline/style_profile.md`.
Show James the script for approval before rendering unless he says skip.

## Step 2 — Commit
Via git push, or via API (works without git; handles base64 for the mp3):
PUT /contents/build/<slug>/script.json   {"message":"...","content":"<base64>"}
PUT /contents/build/<slug>/vo.mp3        {"message":"...","content":"<base64 of mp3>"}

## Step 3 — Render
POST /actions/workflows/render.yml/dispatches   {"ref":"main","inputs":{"slug":"<slug>"}}
Expect HTTP 204. Takes ~10-15 min.

## Step 4 — Poll + fetch result
GET /actions/runs?per_page=1        -> id, status ("completed"), conclusion ("success")
GET /actions/runs/<id>/artifacts    -> archive_download_url
GET that url (same auth, follow redirects) -> zip containing final.mp4 plus at least
three final_music_NN.mp4 choices and their YouTube counterparts. Read
music_variants.json and give James only the two `delivery` files by default. The other
choices remain available and should be linked only when he specifically asks for them.
For a legacy manifest, select the row labeled Deep Current and its matching YouTube file.
If conclusion is "failure": GET /actions/runs/<id>/logs, find the "ERROR: ... | FIX: ..."
line, apply the FIX (usually edit script.json), push, re-dispatch.

## Step 5 — The learning loop (IMPORTANT — this keeps the videos improving)
- James approves → in a checkout run: python3 pipeline/learn.py record build/<slug>
  then commit+push pipeline/memory.json and pipeline/taste.npz. Profiled taste is kept
  separate automatically. (No shell? Skip; tell James it's unrecorded.)
- James dislikes scene i's footage → python3 pipeline/learn.py swap build/<slug> <i>,
  improve that scene's "query", commit, re-dispatch.
- James gives style feedback → python3 pipeline/learn.py note "<his feedback>",
  commit memory.json. Never delete memory.json.

## Judgment checklist before delivering
Duration ≈ VO length; both 1080x1920 portrait and 1920x1080 landscape outputs;
captions with yellow keywords in each format's safe area; bold rounded title fully
fitted on scene 0; majority of slides visibly lit; every clip matches
its spoken line; at least six visual symbol families; no repeated generic-human run;
still-derived duration <=35% and genuine moving footage >=65%; every still passes
still_reference_report.json and visibly belongs beside its stock reference. If a scene
misses, use the swap flow before delivering. Confirm three music-choice MP4s exist and
have distinct audio before delivery, then surface only the manifest's Deep Current
portrait and YouTube delivery links.

## v7 additions
- By default, deliver only the Deep Current portrait and YouTube files selected in
  music_variants.json. Keep all other full-length choices and final_short.mp4 available
  for an explicit request, but do not show their download links automatically.
- Scripts must echo ONE motif from memory.json "motifs" as a brief mid-video callback.
- Retention feedback: python3 pipeline/learn.py retention build/<slug> "<t1,t2>" then push memory.
- Zero-effort mode: open a GitHub issue labeled "video" with the idea; CI does everything
  (requires ANTHROPIC_API_KEY secret). Comment on the issue = feedback; close = approve.

## Parallel operators
Multiple AIs may work simultaneously, each on its OWN slug. Rules:
- Never touch another slug's build dir. Pick a fresh slug; check build/ first.
- If your git push is rejected: git pull --rebase origin main, then push again (retry a few times).
- CI enforces one run per slug at a time; different slugs render in parallel.
- Record/note/swap (learn.py) immediately before pushing, then push promptly - memory
  is shared, last-writer-wins on notes is fine, but always pull-rebase first.
- Tricky prop shots can be PINNED: set the scene's "pexels_id" to a curated clip id; the build fetches that exact clip.
- DMT/visionary scripts: set "genre": "dmt" in script.json (see style_profile.md DMT
  section). Footage scoring flips to vivid/saturated automatically.
- HERO SHOTS: scenes may set "hero": true + "image_prompt" - CI generates free AI
  imagery (pollinations.ai) with a 2.5D parallax move instead of stock. Use for
  impossible metaphors, the scene-0 thumbnail, and the closing reframe (2-4 per video).
- ALTERNATES: after a render, build/<slug>/alts.json lists runner-up clips per scene and
  the run artifact alts_sheet.jpg shows them. Swap = learn.py pin build/<slug> <i> <id>,
  then re-dispatch. Prefer pinning an alternate over re-rolling queries.
