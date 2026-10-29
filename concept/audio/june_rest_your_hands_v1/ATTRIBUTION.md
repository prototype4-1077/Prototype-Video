# Local scratch dialogue provenance — not June's final canonical voice

Original prototype text: "Some days, the bravest thing you do is set the
bucket down. Ain't no shame in resting your hands."

Generated locally with the already installed Piper executable and
`en_US-norman-medium.onnx`. No external inference, paid API, account
credential or network request. The included model card identifies its
LibriVox dataset as public domain and credits the training account at
https://brycebeattie.com/files/tts/. The model and runtime are not redistributed
in this package. The exact model/config/executable hashes are in
`dialogue-media-report.json`; the copied original model card is adjacent.

Processing: natural synthesis at length_scale1.08; resample to48kHz mono
PCM24 before padding/trimming;30ms fades at speech edges;400ms lead and at
least1s quiet tail; exact30fps audio-frame clock. No speech time stretching.
Rhubarb1.14.0 generated cached phoneme cues from that exact padded audio.

This new scratch voice/performance is not human-accepted and does not inherit
the approved first film's audio verdict. No synthetic Foley or continuous
noise bed was added. Keep this provenance with derived previews.
