# Pickup: Rest Your Hands is now a story beat

Previous goal turn was **progress** (710d289, complete mug exchange).
This turn is **progress**: new [face → mug → face] 7.433333-second review
with the cup landing just after “down” and fingers open before the
second line. Sources and all previously passed media remain immutable.
The synthetic Piper Norman voice is still scratch. No new James verdict,
fresh Claude review, automation change, main promotion or paid tool.

Source and command: `concept/scenes/june-rest-your-hands-story-v1.json`,
`python -m pipeline.cartoon_story_beat --output <fresh-dir>`. Review
package with PCM master, MP4, credit and decoded cut sheet:
`june_rest_your_hands_story_v1/`.

Zero-based output cuts F38 / F124. Insert uses v3 F35–120, touchdown
F98 → F101, release reaches open before cutting back to original face
F108 with voice offset by exactly 16 frames. PCM contains original words
at natural speed with fixed −2 dB gain; added 25600 zero samples at the
checked F105 silent splice, without truncating a word. No room tone or
synthetic Foley. The credited sample starts at 160085, dominant peak at
161600, and ends before a secondary impact in the original recording.
Both cue edges were faded by 30 ms.

Initial encode session 69806 ended 1: the default 1 kHz MP4 clock
declared audio 16 samples short. Proper recovery preserved the video
segments and exact MOV, used 48 kHz movie timescale for AAC mux, reran full
decode/PTS/mix/boundary audits. No picture rerender. Both streams report
exactly 223/30 s, 720p30 BT.709, 48 kHz stereo; MOV PCM equals expected,
same picture packets in MP4/MOV, 42.6416 dB AAC SNR, −2 dBTP both. MP4 SHA
5094bd7b57ac3af5d8c8a038616a32293c89ae1e8387afde642faeeb4ad391f2.
Six new tests and 20 previous focused tests passed. Inspected decoded
cuts, pose and set-down frames; no normal-speed audible/taste verdict
is claimed. Both local recovery and initial outputs remain under
`outputs/edit/june-rest-your-hands-story-v1*`; no live processes.

## Next substantial target: the actual short, not another micro-demo

The historical 38.8-second seven-shot *The Twelve-Dollar Mug* picture
and old scratch-sound master are present locally and match the SHA-256
values in Phase25 and Phase26 docs. Do not create an unrelated anthology
of demos. Evaluate that first complete narrative as the backbone for a
new source-verifiable cut with the current stronger closing shots. The old
sound master is a comparison, not a source of accepted audio: it contains
synthetic effects that would reintroduce user-rejected sound categories.

Important: **not** “replace the last 303 frames of 38.8s.” The recorded
Foley clock in `cartoon_fullmix_audio_successor._source_indices` is
global 1-based F790–864, F913–936 and F937–1140. Reconcile the authoritative
picture and sound map and check the F789→790 join (inside GS060) before
anything else. Check first-prefix dialogue completeness and comparable
level/room continuity without reincorporating rejected effects; retain
exact approved closing audio/picture where story/editorially viable. If
the join fails, consider a motivated cut or carry over repairs at the
shot level, not byte concatenation on a rounded duration. Preserve the
originals, credit every reused effect, and require full short review before
promotion. A pinned packet-copy proof and independent human playback
are more informative than another render of these same 7.4 seconds.
