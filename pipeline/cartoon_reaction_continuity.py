"""Reframe GS050 so the pencil never jumps to June's other hand on screen."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import numpy as np
from PIL import Image

from pipeline import cartoon_compassion_acting as acting
from pipeline import cartoon_compassion_review as review


CROP = (75, 0, 1195, 630)  # native plate pixels, exact 16:9; includes shoulder and eyeline room
BEFORE_SHA256 = "37c03343eebb6b28655f51a66939f469a836357f040a69fb187dad1f52a7992f"
# From the registered GS040 and GS060 plates and the decoded cut. The
# GS050 source actually shows the opposite sleeve. This is an editorial
# solution, not a claim that the pencil grip art has been redrawn.
PENCIL = {"GS040_out": "June_right", "GS050_old": "June_left",
          "GS050_new": "offscreen", "GS060_in": "June_right"}
# Actual locked PCM is silent at both edges, between the authored lines.
CONTEXT = (481, 744)


def source_frame(prepared, local_frame):
    eye, _ = acting.cues(local_frame)
    source = prepared.start.copy()
    if eye:
        face = prepared.head.end if eye == 1 else acting.paint_pair(prepared.head, eye)[0]
        acting.apply_region(source, face, prepared.head)
    x, y, r, b = CROP
    return source[y:b, x:r]


def output_frame(prepared, local_frame):
    clock = review.START + 1 + local_frame
    seg = review.golden.segment_for_frame(prepared.segments, clock)
    with Image.fromarray(source_frame(prepared, local_frame)) as source:
        art = source.resize((1920, 1080), Image.Resampling.LANCZOS)
    return review.golden.apply_shot_effects(art, seg.get("effects") or {}, clock - seg["start_frame"], 30)


def animate(output):
    prepared = acting.prepare()
    if CROP[3] > acting.HAND_ROI[1]:
        raise ValueError("reaction crop intersects the reversed grip")
    args = review.cut.media.encoder_command("ffmpeg", output)
    digests = []
    with output.with_suffix(".log").open("wb") as log, subprocess.Popen(args, stdin=subprocess.PIPE, stderr=log) as proc:
        try:
            for frame in range(review.STOP - review.START):
                with output_frame(prepared, frame) as image:
                    data = image.tobytes()
                proc.stdin.write(data)
                digests.append(sha256(data).hexdigest())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("reframed GS050 encode failed; check shot02.log")
    return {"native_frames_changed": len(set(digests)), "crop_native_xyxy": CROP,
            "pencil_continuity": PENCIL, "gaze_ease_local_frames": [31, 54],
            "hand_animation_applied": False, "input_art": acting.ASSETS}, digests


def compare(before, after, output):
    start, stop = (f / 30 for f in CONTEXT)
    count = CONTEXT[1] - CONTEXT[0]
    duration = stop - start
    video_filter = (f"[0:v]trim=end_frame={count},setpts=PTS-STARTPTS,scale=768:432[l];"
                    f"[1:v]trim=end_frame={count},setpts=PTS-STARTPTS,scale=768:432[r];"
                    "[l][r]hstack[v];"
                    f"[0:a]atrim=end_sample={count*1600},asetpts=PTS-STARTPTS,"
                    f"afade=t=in:d=0.03,afade=t=out:st={duration-.03:.3f}:d=0.03[a]")
    review.cut.media._run(review.cut.CLI + ["-ss", str(start), "-i", str(before),
        "-ss", str(start), "-i", str(after), "-filter_complex", video_filter, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-threads", "4", "-crf", "16", "-pix_fmt", "yuv420p", "-colorspace", "bt709",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
        "-movie_timescale", "48000", "-movflags", "+faststart", str(output)], output.with_suffix(".log"))
    video, audio = review.cut.media._probe(output, "ffprobe")["streams"]
    if (int(video["nb_read_frames"]) != count or
            any(abs(float(s["duration"]) - duration) > .001 for s in (video, audio))):
        raise ValueError("side-by-side clock mismatch")


def review_window(output, before, receipt):
    candidate = output / "twelve-dollar-mug-reaction-v1.mp4"
    comparison = output / "pencil-continuity-review.mp4"
    if review.cut.beat.digest(before) != BEFORE_SHA256 or review.cut.beat.digest(candidate) != receipt["candidate_sha256"]:
        raise ValueError("not the exact staged and replacement films")
    if comparison.exists():
        raise FileExistsError(comparison)
    compare(before, candidate, comparison)
    for selector in ("a:0", "s:0"):
        if review.signature(review.packet_info(before, selector)) != review.signature(review.packet_info(candidate, selector)):
            raise ValueError(f"changed {selector} since staged candidate")
    receipt["repair_source_sha256"] = review.cut.beat.digest(Path(__file__))
    receipt["previous_staged_sha256"] = BEFORE_SHA256
    receipt["ab_sha256"] = review.cut.beat.digest(comparison)
    receipt["ab_full_cut_span_half_open"] = CONTEXT
    review.cut.media._json(output / "continuity-reviewed-window.json", receipt)
    return receipt


def build(output: Path, before: Path):
    if review.cut.beat.digest(before) != BEFORE_SHA256:
        raise ValueError("not the exact previously staged GS050 film")
    # Scoped to this single-process command. Reuse the established lossless
    # splice and audit; don't edit the frozen earlier renderer or assets.
    with patch.object(review, "animate", animate):
        receipt = review.build(output)
    return review_window(output, before, receipt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--before", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.before), indent=2))
