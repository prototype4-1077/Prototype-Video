# Second authored June scene — Rest Your Hands

New words, cached local phonemes, new head/camera keys and blink placement;
207 frames /6.9s /1080p30, rather than the first scene's228 dialogue frames.
The existing June raster rig and source artwork produce the pixels.
The first passed three-shot film is untouched. No new renderer or paid API.

Play `scene.mp4`; `scene.mov` preserves exact source dialogue PCM, explicitly
duplicated from mono to stereo at unity gain. This is new **non-canonical
Piper scratch voice**, not a transfer of the first film's audio acceptance.
Run `Run June Dialogue Scene.cmd` at root; see `docs/JUNE_DIALOGUE_SCENES.md`.

The source-only snapshot render completed all207 picture frames but its
256k AAC preview scored38.27dB, below the unchanged40dB floor. It failed
honestly. Export-only recovery copied the identical picture/MOV, raised AAC
to512k and reran every media gate:40.47dB SNR, all207 frames decoded, exact
timestamps and source PCM. Six sampled picture checks exceed38.45dB PSNR.
Both failed outputs remain local; the picture was never rerendered/re-encoded.

Evidence limitation: the initial renderer wrote native inventory only after
the audio gate, so that in-memory inventory was lost at failure. This package
contains all decoded preview hashes and all six actual raw reference PNGs;
they are explicitly distinguished. Future builds now persist native inventory
before export. See `source-build-receipt.json` and `new-scene-report.json`.
Root inspected decoded stills, not the full normal-speed performance or sound.

This proves a new authored dialogue performance through the same engine,
not a new set, arbitrary camera angle, full-body action, episode production
or industry-competitive final acting. Resting hands are intentional; there
is no new hand deformation. New voice/acting remain human-unaccepted.
Main/release promotion is false. Keep `ATTRIBUTION.md` with derivatives.

Next: reuse the existing pose/contact mechanics to author one convincing
hand/prop action from the same scene recipe, with visible contact and timing
tests. Avoid another talk-only scene or renewed polish of the passed film.
