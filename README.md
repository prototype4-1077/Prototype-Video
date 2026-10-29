# June Oxley cartoon prototype — current zero-cash work

The active cartoon renderer is a local, experimental 2.5D animation pipeline.
It does not require the paid-service credentials in the legacy instructions
below. It is **not yet a production-ready full-cartoon system**.

Start with [current cartoon capabilities, review files, and safe commands](docs/JUNE_CARTOON_CURRENT_STATE.md).
James has accepted the blink/audio and provisionally passed the mouth/hand
repairs for prototype progress. The next path is the source-built complete
scene: [run the working model](docs/JUNE_WORKING_MODEL.md), or double-click
**Run June Prototype.cmd** on the configured Windows computer. Its actual
clean-source full-build verification is being completed; this is not a
production-quality or general episode-generation claim.

---

# TikTok Video Render Farm — legacy pipeline

Cloud renderer for James's mystical-philosophical TikToks. The Cowork/Claude session
writes the script; GitHub Actions does all the heavy lifting (TTS/alignment, CLIP-vetted
footage, word-synced captions, adaptive music, -14 LUFS master) with no time limits.

## One-time setup
1. Create a PRIVATE repo and push this folder's contents.
2. Copy the `tiktok_pipeline` folder into it as `pipeline/` (keep `pipeline/memory.json`!).
3. Repo Settings > Secrets and variables > Actions > add:
   `ELEVENLABS_API_KEY`, `PEXELS_API_KEY`, optionally `ELEVENLABS_VOICE_ID`.

## Per video
1. Commit `build/<slug>/script.json` (see pipeline/HANDOFF.md for the format).
   Own voiceover? Commit it as `build/<slug>/vo.mp3` too (remove vo.mp3 from .gitignore or `git add -f`).
2. Actions tab > "Render video" > Run workflow > enter the slug.
3. ~10-25 min later: download `final.mp4` from the run's Artifacts.
   The run commits updated `memory.json` back - the pipeline keeps learning.

Claude can do steps 1-3 via a GitHub connector or gh CLI if you give it repo access.
