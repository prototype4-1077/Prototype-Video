# Canonical Editorial Timeline and Selective Scene Revision

This layer makes the rendered edit durable and revisions surgical.

## What is canonical

After every successful `Render video` workflow, `editorial-post-render.yml` creates:

- `editorial.otio` — OpenTimelineIO timeline containing the ordered scene masters,
  durations, external media references, voiceover/score tracks, and scene status metadata;
- `editorial_manifest.json` — compact JSON equivalent for tools that do not load OTIO;
- `editorial-verification.json` — scene-count, duration, and media-reference checks;
- `export-verification-*.json` — PySceneDetect comparison of planned versus detected cuts;
- `detected-scenes-*.csv` — detected scene ranges;
- `revision-cache-manifest.json` — hashes and sizes for the reusable scene-master cache;
- `revision-cache-run-id.txt` — the workflow run containing the current cache artifact.

OTIO references media; it does not embed media. The large scene masters remain in a
90-day GitHub Actions artifact named `<slug>-revision-cache`. Small editorial records
are also uploaded to the permanent video Release.

## Revision flow

1. James reviews the generated scene survey.
2. `apply-scene-feedback.yml` verifies that every scene is reviewed and that narration
   and approved scene metadata remain unchanged.
3. It dispatches `selective-revision.yml`.
4. The workflow downloads the current revision cache and verifies every cached hash.
5. `selective_revision.py prepare`:
   - hash-locks approved scene masters;
   - records the old hashes of rejected masters;
   - removes only rejected scene masters and their visual source files;
   - removes canonical finals/review outputs so they are rebuilt;
   - preserves voiceover, word timing, score, captions, titles, approved raw clips,
     and approved scene masters.
6. The normal Governor regenerates missing visuals and scene masters, then reassembles.
7. `selective_revision.py finalize` blocks delivery if:
   - narration text/timing changed;
   - any approved scene-master hash changed;
   - a rejected scene was not regenerated;
   - a replacement has the same hash as the rejected version;
   - no canonical final was produced.
8. OTIO and PySceneDetect verification run again, the Release is updated, and a new
   cache artifact becomes the baseline for the next review.

## Older videos

A video rendered before this system will not have `revision-cache-run-id.txt`.
Selective revision then dispatches the established full `render.yml` workflow. Its
successful completion automatically creates the first OTIO timeline and revision cache,
so subsequent feedback becomes surgical.

## Export verification policy

PySceneDetect is an independent measurement of the exported video, not the source of
editorial truth. The script/OTIO timeline defines planned boundaries. Detection reports:

- final duration versus planned duration;
- audio/video duration mismatch;
- detected scene ranges;
- planned boundaries matched within tolerance;
- unexpected cuts;
- micro-scenes or flashing edits;
- representative midpoint frames for every planned scene.

Low boundary-match ratios are warnings because continuous motion and gentle fades can be
valid. Duration mismatch, audio/video mismatch, micro-scenes, and excessive unexpected
cuts are delivery failures.

## Commands

```bash
python3 pipeline/editorial_timeline.py build build/<slug>
python3 pipeline/editorial_timeline.py verify build/<slug>
python3 pipeline/export_verify.py build/<slug> final_youtube.mp4 --frames
python3 pipeline/revision_cache.py build build/<slug> --run-id <run-id>
python3 pipeline/revision_cache.py validate build/<slug>
python3 pipeline/selective_revision.py prepare build/<slug>
python3 pipeline/selective_revision.py finalize build/<slug>
```

## Safety properties

- Approved narration is not regenerated during a selective revision.
- Approved scene masters are verified by SHA-256 before and after the revision.
- Rejected scenes must produce a different scene-master hash.
- Cache corruption causes a full-render fallback rather than partial delivery.
- No editorial workflow publishes or changes a script without the existing feedback
  and GitHub gates.
