# TikTok Video Pipeline v2 — Instructions for Claude (any model size)

James makes mystical-cinematic philosophical TikToks. This zip is a tested pipeline that turns
an idea into a finished MP4. You only make TWO decisions: write the script, and check the result.
Everything else is one command run in a loop.

## Workflow

1. Unzip to sandbox: `unzip tiktok_pipeline.zip -d pipeline` and `mkdir -p build/<slug>`
   (slug = short-dashed-title, e.g. `dimmer-switch`).

2. WRITE THE SCRIPT (you are the scriptwriter; no API involved). Read style_profile.md first.
   Save as `build/<slug>/script.json` in exactly this shape:

   { "title": "Three Or Four Words",
     "slug": "<slug>",
     "scenes": [
       { "text": "One sentence or beat (max ~25 words).",
         "keywords": ["2-4 load-bearing words from that sentence, highlighted yellow"],
         "query": "pexels search - COPY OR ADAPT FROM THE QUERY BANK BELOW" }
     ] }

   Rules (build.py enforces most of them and tells you what to fix):
   - 18-26 scenes, 300-400 words total, ~2:00-2:30 spoken
   - Second-person, poetic-direct, grounded-metaphysical. Hook opener. Quiet realization ending.
   - keywords must be words that literally appear in the scene text
   - Show James the script text for approval before building, unless he says skip.

3. QUERY BANK — visuals are surreal/mystical/liminal, never literal or bright-stocky.
   Safe bets (mix, adapt nouns, keep the mood words):
     surreal fog silhouette | nebula space stars | underwater sun rays dark |
     silhouette tunnel light end | fog city aerial dark | smoke swirl black background |
     light rays forest fog | ink drop water black | stars time lapse night sky |
     eclipse moon dark clouds | person walking fog field | abstract particles dark |
     candle flame dark | ocean night moonlight | desert lone figure dusk |
     light through door dark room | clouds time lapse storm dark | mirror reflection surreal |
     glowing orb dark | shadow figure hallway | aurora night sky | deep space travel |
     rain window night bokeh | city lights bokeh night blur
   Don't worry about picking perfectly: footage.py auto-scores every candidate clip's
   thumbnail for mood (dark, muted) and picks the best. Bad queries fall back to this bank.

4. BUILD — run this ONE command, then run it again every time it says RUN AGAIN:

       python3 pipeline/build.py build/<slug>

   It loads keys from pipeline/.env itself (no exports needed), downloads fonts on first run,
   validates your script (with fix hints), generates voiceover, downloads footage, renders,
   and finishes with:  DONE -> build/<slug>/final.mp4
   Rules of thumb:
   - Every step is resumable. Rerunning never breaks anything.
   - If a bash call times out, just run the same command again.
   - On `ERROR: ... | FIX: ...` do exactly what FIX says, then rerun.

5. VERIFY (only judgment step besides the script): extract 3 frames and look at them:
       ffmpeg -y -ss 3 -i build/<slug>/final.mp4 -frames:v 1 f1.png   (repeat at mid + end)
   Check: 9:16 portrait, letterboxed footage band, captions below the band with yellow keywords,
   big rounded title on scene 0, footage moody/mystical. Check duration (~2:00-2:40).
   If one scene's footage looks wrong: delete its clip_XX.mp4 AND seg_XX.mp4, improve that
   scene's "query" in script.json, remove its "pexels_id", and rerun build.py.

6. DELIVER: present final.mp4 to James with present_files. Done.

## Look spec (what "correct" looks like)
- 1080x1920 (9:16 phone), 30fps. Footage is a 16:9 band (1080x608) vertically centered on black.
- Captions: Questrial 44px, white, in the bottom black band, subtle dark boxes,
  2-4 keywords per sentence in pale yellow (#e6e87e).
- Title: Baloo2 ExtraBold ALL-CAPS white with shadow, centered over the footage band, scene 0.
- Audio: ElevenLabs VO (voice id in .env; James's current pick is Liam) over a low ambient bed.

## Config
- .env: ELEVENLABS_API_KEY, PEXELS_API_KEY, ELEVENLABS_VOICE_ID (Liam TX3LPaxmHKxFdv7VOQHJ;
  Daniel onwK4e9ZLuTAKqWW03F9 is the old calm-deep option). Ask James once per video if unsure.
- Optional full-frame portrait crop (no letterbox): add "layout": "fullbleed" in script.json.
- Custom music: put a file in the build dir and set "music": "<filename>" in script.json.

## Files
build.py   — THE orchestrator; the only command you need after writing the script
style_profile.md — James's writing voice + reference fragments (read before scripting)
tts.py, footage.py, prep.py, captions.py, music.py, assemble.py — internals (don't edit)
.env       — API keys

## v3: the pipeline is ALIVE (it learns between videos)
- memory.json (in this zip) persists across videos. NEVER delete it; always include it when re-zipping.
- Before writing any script: `python3 pipeline/learn.py show` — read James's notes and what worked.
- footage.py automatically: never reuses a clip from past videos, never picks banned clips,
  favors bank queries with the best track record. You don't manage this; it just happens.
- After James APPROVES a final video: `python3 pipeline/learn.py record build/<slug>`
- If James dislikes one scene's footage: `python3 pipeline/learn.py swap build/<slug> <scene_i>`
  (bans that clip forever + penalizes the query), optionally improve that scene's "query",
  then rerun build.py. Repeat until he's happy, THEN record.
- If James gives any feedback in chat worth remembering: `python3 pipeline/learn.py note "..."`
- When you deliver the final video, ALSO re-zip the pipeline folder (with the updated memory.json)
  and present it to James so the memory survives to his next session. This is what makes the
  videos living: each session inherits everything every past session learned.

## v3: James can supply his own voiceover
Drop his mp3 in the build dir as vo.mp3 BEFORE the first build.py run (and add "user_vo": true
in script.json). build.py then skips TTS, force-aligns his script text to his audio for exact
scene timing (align.py), and relaxes the word/scene-count limits (his script is authoritative —
split it into scenes VERBATIM, never rewrite his words).

## v3: the music listens
music.py reads the voiceover's energy: it recedes under speech, swells in the pauses,
sprinkles soft chimes at long-pause onsets, and builds ~30% toward the closing line.
Nothing to configure. For custom music set "music" in script.json as before.

## v5 upgrades (all automatic; nothing new to operate)
- WORD-SYNCED CAPTIONS: if `faster-whisper` is installed (pip install faster-whisper),
  build.py transcribes the VO locally and yellow keywords ignite at the exact moment they
  are spoken. Without it, captions fall back to static yellow. Env WHISPER_MODEL can point
  to a local model dir (default "base", auto-downloads).
- SEMANTIC FOOTAGE MATCHING: with open_clip_torch+torch installed AND env SEMANTIC_CLIP=1
  (auto-on in GitHub Actions), every candidate clip is also scored by CLIP for how well it
  matches the scene's query meaning, blended with the mood score. Leave off in 45s-limited
  sandboxes (model load is ~30s). Env CLIP_CACHE = model dir (default /tmp/clipcache).
- LOUDNESS MASTER: the final mix is automatically mastered to ~-14 LUFS / -1 dBTP
  (TikTok reference). Nothing to configure.
- GITHUB RENDER FARM: if this pipeline lives in a GitHub repo (see github_repo/README.md),
  trigger the "Render video" workflow with a slug instead of running build.py locally:
  no time limits, CLIP on, memory.json auto-committed back. Prefer it for full renders
  when available; use local build.py for quick tests and single-scene fixes.

## v7 upgrades
- CINEMATIC COHESION (automatic): unified color grade + film grain + vignette, camera
  motion alternates per scene (push-in / pull-out / drift), dip-to-black scene cuts,
  title fades in/out. Nothing to configure.
- 60s SHORT CUT (automatic for scripts >=16 scenes): build.py also writes final_short.mp4
  from the strongest beats (hook + questions + ending). Deliver BOTH files to James.
  Manual: python3 pipeline/shortcut.py build/<slug> [target_secs]
- MYTHOLOGY: memory.json now holds "motifs" (one signature line per video). When
  scriptwriting, echo exactly ONE earlier motif mid-video as a natural callback phrase.
  After each approved video: python3 pipeline/learn.py motif <slug> "<name>" "<line>"
- RETENTION LEARNING: when James shares TikTok retention drop-off timestamps:
  python3 pipeline/learn.py retention build/<slug> "43,87,110"
  It maps them to scenes and records the lesson; future scripts obey.
- ISSUE STUDIO (GitHub): open an issue labeled "video" whose title/body is the idea.
  CI writes the script (needs ANTHROPIC_API_KEY in repo secrets), renders, comments
  the artifact link on the issue. Closing the issue = approval.
