# June Oxley: reusable studio development

This opt-in branch applies the animation research to a real Blender asset and
performance pipeline. The studio contains an editable character, a complete
porch set, reusable actions, and audio-driven facial deformations. It remains a
development asset: June's approved turnaround and golden-scene art are still the
likeness and finish targets. Passing a mechanical check does not approve the art.

## What is implemented

| Change | What it makes easier | Current boundary |
| --- | --- | --- |
| Packed Blender studio library | Load the character, set, cameras, and actions without rebuilding them for every shot | Built with Blender 4.2.0; edited assets need a new reviewed version and checksum receipt |
| Eight reusable body actions | Reuse walking, standing, listening, explaining, pointing, reaching, skepticism, and chuckling | These are authored starting performances; no automatic prop contact or award-level acting claim |
| Fifteen facial assets | Reuse nine speech shapes plus blinks, smile, eye warmth, brow raise, and concern | Actual head deformation with driven beard/brow/teeth meshes; extreme expressions still need art review |
| Rhubarb 1.14.0 | Derive speech timing from the final voice recording | Timing is an animator's starting pass, not a replacement for phoneme and acting review |
| Poly Haven materials and lighting | Reuse a weathered wood surface and daylight environment, packed inside the scene | Two pinned CC0 assets; no recurring live asset search is required |
| Local Mixamo-style FBX intake | Preserve a licensed source motion as a separate Blender action library | No Adobe login, download, or automatic retargeting to June; contact cleanup remains necessary |
| Per-shot frame cache | A camera or performance change invalidates the affected cache; unchanged completed shots can be reused | Incomplete or corrupt frame sequences are never accepted as completed shots |
| Real progress and failure reports | See actual rendered frames and the failing shot/log | A stage without a completed frame is not reported as a successful render |

No new subscription is required for these tools. The benchmark uses the existing
ElevenLabs connection for **Granpa Spuds Oxley** (`NOpBlnGInO9m6vDvFkFC`). That
service's existing account/credit terms still apply. The take is preserved and
reused; animation rerenders do not generate another voice. Piper Norman and Liam
are not interchangeable with June's approved casting.

## Reproduce the studio

Run commands from the repository root. Use the pinned Blender 4.2.0 executable
as `blender`, Python 3.11+, and FFmpeg/FFprobe. Bootstrap downloads are Linux x64;
the studio itself is a normal portable `.blend` file with packed textures.

```bash
python3 -m pipeline.june_studio bootstrap build/june-studio-tools

blender -b -t 4 --python-exit-code 1 \
  --python pipeline/blender/june_studio_assets.py -- \
  --tools build/june-studio-tools \
  --output build/june-studio-assets/june-studio.blend --review
```

The second command is a **one-time asset build**, not a per-episode operation.
It writes the asset, a checksum/provenance receipt, and three camera review
frames. The `.blend` contains 8 body clips, 15 facial pose assets, three cameras,
and the packed wood/HDRI files. Collections can be appended through Blender's
Asset Browser. Body clips belong to the armature; facial poses belong to the
head's shape-key datablock.

The new facial target data is CC0, pinned to MPFB source commit
`437dd513888a92399d1d3200d2e80859fae55abc`. Each original target URL and hash is in
`concept/characters/assets/june_expression_cc0_provenance.json`. The new archive
does not modify the v9 anatomical source archive or legacy phase evidence.

## Preserve and align the voice once

The short benchmark line is the first sentence of the existing Phase33 script:
“Funny thing: the account got lighter before the debt did.” It is a performance
test, not a researched claim about a specific current event.

Download `vo.mp3`, `voiceover-manifest.json`, `script.json`, and `SHA256SUMS` from
the preserved [benchmark release](https://github.com/prototype4-1077/Prototype-Video/releases/tag/june-studio-voice-benchmark-v1)
into `build/june-studio-voice`, then run:

```bash
python3 -m pipeline.june_studio prepare-voice build/june-studio-voice \
  --rhubarb build/june-studio-tools/rhubarb/Rhubarb-Lip-Sync-1.14.0-Linux/rhubarb
```

This decodes the exact MP3, runs Rhubarb with the dialogue text, and binds the
MP3, WAV, script, and normalized cues in `cue-source.json`. The renderer rejects
a substituted voice, modified recording, or cues from a different take. It uses
the decoded audio duration, not the older script's estimated scene duration.
Changing narration requires realignment before rendering.

## Render and reuse shots

```bash
python3 -m pipeline.june_studio_render \
  --asset build/june-studio-assets/june-studio.blend \
  --voice-dir build/june-studio-voice \
  --output-dir build/june-studio-preview \
  --blender blender --width 640 --samples 4 --threads 4
```

This benchmark is a **15-second, 640×360, 30 fps development preview** with three
cuts: walk into the set, address the audience, and react. All 450 frames are
rendered from animated geometry. The preserved voice starts at 4 seconds and
is neither stretched nor pitch-shifted. No score, captions, or finishing upscale
are added to this test. Production episodes retain the existing native
1920×1080 delivery rules and Creekside Stomp score unless James requests otherwise.

The renderer checks all 450 evaluated rig frames for finite transforms, ankle
and wrist targeting, and sole contact before rendering. These checks do not
certify cloth collision, appeal, likeness, or lip-sync quality. Review those in
the actual movie. `status.json` reports actual frame progress; per-shot logs
and cache receipts retain the detailed evidence. Rerun the same command to
reuse checksum-verified completed shots. A failed partial shot must be rebuilt.

Cycles is the default and produced cleaner low-sample images in this CPU
environment. `--engine BLENDER_EEVEE_NEXT` is available for a machine with a
working graphics/EGL context. Software Eevee was grainier and slower here;
there is no blanket promise that Eevee is faster on every machine. Use camera
inspection (`--inspect`) before committing a whole sequence to higher quality.

## Bring in an external motion

Download only a motion you have rights to use, using your own Adobe account if
it comes from Mixamo. Then import it into an isolated library:

```bash
blender -b --python-exit-code 1 \
  --python pipeline/blender/import_june_motion.py -- \
  --input /absolute/path/motion.fbx \
  --output build/june-motion/source-motion.blend \
  --license-note "Source and applicable license recorded by the operator"
```

The importer checks for a humanoid bone naming set and actual animation curves,
preserves timing at the requested frame rate, marks source actions as assets,
and records the source checksum. It does **not** retarget the action, approve
it, or add it to June's show library automatically. Retarget body scale, pin
contacts, clean hands, and review acting before publishing a reusable June action.

## Next improvements, in order

1. Refine the saved master face against the approved turnaround: eye size and
   lids, cheek and nose planes, silhouette, smile, hairline, beard shape, and
   age. Reuse that corrected asset in every later shot. More prompts or render
   samples cannot substitute for this sculpting pass.
2. Refine wardrobe construction and deformation: believable collars and
   overall straps, elbows, pockets, seams, and restrained fabric texture. Use
   corrective shapes at the worst poses before adding expensive cloth simulation.
3. Animate a short speech phrase by hand over Rhubarb's timing: jaw rhythm,
   lip closure, gaze-before-head movement, thought pauses, and asymmetrical
   gestures. Save the successful acting pieces for later episodes.
4. Add two carefully dressed locations after the porch is accepted. Reuse
   props, materials, lighting rigs, and camera presets across them.
5. Establish a current-affairs episode brief with a dated source list, one
   clear audience question, factual setup, June's opinion, and a useful ending.
   Verify factual claims near publication time and keep satire distinguishable
   from the reported facts. Reusing a set should not mean recycling the argument.
6. Choose final render settings from a temporal sample on the actual production
   machine. Bake expensive static detail or lighting only where the camera and
   light changes permit it; retain the original geometry and textures.

## Research used

- [Blender Studio: stylized character workflow](https://studio.blender.org/training/stylized-character-workflow/)
  informed the separation of character construction, rigging, acting, and look review.
- [Blender pose library](https://docs.blender.org/manual/en/latest/animation/armatures/posing/editing/pose_library.html)
  and [animation editors](https://docs.blender.org/manual/en/latest/animation/animation_editors.html)
  support reusable poses, editable actions, and layered performance.
- [Rhubarb's official project](https://github.com/DanielSWolf/rhubarb-lip-sync)
  provides audio-derived timed mouth shapes and the pinned Linux release.
- [Adobe's Mixamo FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)
  documents account access, animation use, and humanoid requirements.
- [Poly Haven license](https://polyhaven.com/license) and
  [API terms](https://github.com/Poly-Haven/Public-API/blob/master/ToS.md)
  inform asset reuse and download attribution. Assets are pinned and packed locally.
- [MakeHuman/MPFB asset licensing](https://static.makehumancommunity.org/mpfb/faq/build_other_chargen.html)
  documents the CC0 core-asset basis for the compatible facial targets.
- [Cycles baking](https://docs.blender.org/manual/en/latest/render/cycles/baking.html)
  is a later optimization after the look and lighting are accepted, not an
  automatic conversion in this change.
