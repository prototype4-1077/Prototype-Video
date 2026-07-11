# AGENT.md — Instructions for any AI operating this repo

You are making a mystical-philosophical TikTok video for James using this repo's
cloud render farm. You need NO video tools — GitHub Actions renders everything.
You only need: (1) the ability to call HTTPS APIs or run git, (2) this file.

REPO: jameswatson1077/tiktok-videos (private)
AUTH: James gives you a token. Use header  Authorization: Bearer <TOKEN>
API BASE: https://api.github.com/repos/jameswatson1077/tiktok-videos

## Step 0 — Read context (GET file contents via API or git clone)
- pipeline/HANDOFF.md      — full pipeline docs
- pipeline/style_profile.md — James's writing voice + visual spec
- pipeline/memory.json      — READ "notes" (his standing feedback) and respect it.
  Current standing rules: slides must be LIT-but-moody (window light, god rays,
  lamplight, golden hour; only a few near-dark slides), footage must match the
  spoken words (especially endings), 9:16, letterboxed, yellow keyword captions.

## Step 1 — Write the script file
Create build/<slug>/script.json  (slug = short-dashed-title):
{ "title": "Three Or Four Words", "slug": "<slug>",
  "scenes": [ { "text": "One sentence/beat (max ~25 words).",
                "keywords": ["2-4 words that appear IN that text"],
                "query": "pexels search: lit-but-moody, literal to the line" } ] }
Rules: 18-26 scenes and 300-400 words if YOU write the script (second person,
poetic-direct, quiet powerful ending — see style_profile.md).
If James supplies script text: split it into scenes VERBATIM (never rewrite), any length.
If James supplies a voiceover mp3: also commit it as build/<slug>/vo.mp3 and put
"user_vo": true at the top level. (vo.mp3 is gitignored — force-add it: git add -f,
or use the contents API which ignores .gitignore.)
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
GET that url (same auth, follow redirects) -> zip containing final.mp4. Give it to James.
If conclusion is "failure": GET /actions/runs/<id>/logs, find the "ERROR: ... | FIX: ..."
line, apply the FIX (usually edit script.json), push, re-dispatch.

## Step 5 — The learning loop (IMPORTANT — this keeps the videos improving)
- James approves → in a checkout run: python3 pipeline/learn.py record build/<slug>
  then commit+push pipeline/memory.json. (No shell? Skip; tell James it's unrecorded.)
- James dislikes scene i's footage → python3 pipeline/learn.py swap build/<slug> <i>,
  improve that scene's "query", commit, re-dispatch.
- James gives style feedback → python3 pipeline/learn.py note "<his feedback>",
  commit memory.json. Never delete memory.json.

## Judgment checklist before delivering
Duration ≈ VO length; 1080x1920; captions with yellow keywords in bottom band;
bold rounded title on scene 0; majority of slides visibly lit; every clip matches
its spoken line. If a scene misses, use the swap flow before delivering.

## v7 additions
- Deliver BOTH final.mp4 and final_short.mp4 (60s cut) when present in artifacts.
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
