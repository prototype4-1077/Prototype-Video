# Mouth-cue translation study — v1 — not human accepted

Watch `mouth-semantics-native-ab-v1.mp4`: existing mouth on the left, cue
translation on the right. Same 138 frames, 30 fps, 4.6 seconds, same speech
window (scene 3.3–7.9 s). Drawings, cue times and two-frame blend values are
unchanged. Native fixed-face crop, not a rebuilt scene or whole-performance
approval. No head/body/camera changes are demonstrated here.

The speech tool's cue letters and the internal artwork labels use different
meanings. For example, upstream A is closed P/B/M while our A opens; upstream
G is F/V contact while our G is rounded. This candidate translates labels at
the art boundary, reusing the existing source-textured deformation renderer.
Primary semantics: https://github.com/DanielSWolf/rhubarb-lip-sync#mouth-shapes

| Upstream cue | Internal art |
| --- | --- |
| A — closed P/B/M | X — closed/rest |
| B — clenched consonants / EE | C |
| C — open EH/AE | D |
| D — wide AA | B |
| E — slightly rounded | A |
| F — puckered OO/W | G |
| G — F/V contact | F |
| H — long L | H |
| X — rest | X |

This is not a claim that every reused drawing is a perfect phonetic match.
Rounded/puckered and long-L poses remain approximations. P/B/M borrows the
relaxed rest plate, not a newly drawn pressure pose. The cue recognizer and
two-frame interpolation are unchanged and can still be artistically wrong.
Listen for under-articulation, abrupt tooth changes, and whether closures
land with the words. Inspect the moustache/beard edge for a floating seam.

The MOV contains the same compressed picture and PCM24 excerpt; MP4 is the
browser-friendly AAC copy. Only the review excerpt has 30-ms entry/exit
fades. The accepted full-scene audio itself is untouched. Keep
`ATTRIBUTION.md` and `sources.json` with shared derivatives.

`mouth-semantics-keyframes-v1.png` and
`mouth-semantics-study-report-v1.json` provide native samples, per-frame cue
translation, support checks, hashes and limits. Their technical checks are
not human acceptance of lip-sync, performance or production quality.

The original integrated scene, all rejected evidence, accepted eyelids and
recorded audio, and main branch remain unchanged. No paid call or cloud job.
