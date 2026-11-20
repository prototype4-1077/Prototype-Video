"""Review a tighter first reverse on June; keep the ledger detail and audio."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_visitor_return_review as prior


BASE_SHA = "4707cc3b6d774776f4ffcb5691e72b342e2a7312eae45fcf8b9d061e72c04562"
SOURCE_PCM_SHA = "85d9baecc08faefc0b2b09177d0da3ed449f21dd324c3a950081dc05907eef58"
START, STOP = 396, 452
TOTAL = prior.TOTAL
PREVIEW = (312, 538)
CROP = (1280, 720, 120, 4)   # width, height, left, top in source pixels
cut, probe, digest = prior.cut, prior.probe, prior.digest


def frame_hashes(path):
    rows = subprocess.check_output(cut.CLI[:-1] + ["-i", str(path), "-map", "0:v:0",
        "-pix_fmt", "yuv420p", "-f", "framehash", "-hash", "sha256", "-"]).decode("ascii")
    return [row.rsplit(",", 1)[-1].strip() for row in rows.splitlines() if not row.startswith("#")]


def check_picture(before, after, new):
    """Check first/last exact decoded frames and every intervening packet."""
    v0, v1, source = (probe.packet_info(p, "v:0") for p in (before, after, new))
    for rows in (v0, v1):
        prior.validate_gops(rows, (0, START, STOP, TOTAL))
    prior.validate_gops(source, (0, STOP-START))
    moved = [(pts+START*1000, dts+START*1000, ticks, h, side)
             for pts, dts, ticks, h, side in probe.signature(source)]
    if (probe.signature(v0[:START]) + moved + probe.signature(v0[STOP:])
            != probe.signature(v1)):
        raise ValueError("picture packets moved or changed beyond the one reverse")
    original, edited, isolated = (frame_hashes(p) for p in (before, after, new))
    if (len(original) != TOTAL or len(edited) != TOTAL or len(isolated) != STOP-START or
        edited != original[:START] + isolated + original[STOP:] or
        any(a == b for a, b in zip(original[START:STOP], isolated))):
        raise ValueError("decoded frame audit failed")


def check_audio(before, after):
    for stream in ("a:0", "s:0"):
        a, b = (probe.signature(probe.packet_info(p, stream)) for p in (before, after))
        if not a or a != b:
            raise ValueError(f"changed {stream} packets")
    a, b = (cut.beat.decoded_audio(p, "s32le", "<i4") for p in (before, after))
    if (not np.array_equal(a, b) or len(a) < TOTAL*1600 or
        np.any(a[TOTAL*1600:])):
        raise ValueError("changed decoded audio")
    return a[:TOTAL*1600]


def quiet(samples, description):
    if samples.shape != (TOTAL*1600, 2) or any(
            np.any(samples[f*1600-1440:f*1600+1440]) for f in PREVIEW):
        raise ValueError(f"{description} review edges are not digitally silent")


def build(before, pcm, output):
    if digest(before) != BASE_SHA or digest(pcm) != SOURCE_PCM_SHA:
        raise ValueError("only the exact visitor-return review and narration PCM can be used")
    prior.validate_gops(probe.packet_info(before, "v:0"), (0, START, STOP, TOTAL))
    samples = cut.beat.decoded_audio(pcm, "s32le", "<i4")
    quiet(samples, "WAV")
    output.mkdir(parents=True, exist_ok=False)
    new, result = output/"reverse.mp4", output/"twelve-dollar-mug.mp4"
    cmd = cut.media.encoder_command("ffmpeg", new)
    cmd[cmd.index("-f"):cmd.index("-an")] = [
        "-ss", str(START/30), "-i", str(before), "-map", "0:v:0", "-frames:v", str(STOP-START)]
    cmd[cmd.index("-vf")+1] = (
        "crop=" + ":".join(map(str, CROP)) + ",scale=1920:1080:flags=lanczos,"
        + cut.media.FRAME_FILTERS.split(",", 1)[1])
    cut.media._run(cmd, output/"reverse.log")
    prefix, suffix = output/"prefix.mp4", output/"suffix.mp4"
    prior.payoff.copy_picture(before, prefix, 0, START)
    prior.payoff.copy_picture(before, suffix, STOP, TOTAL)
    if len({probe.codec_hash(p) for p in (prefix, new, suffix)}) != 1:
        raise ValueError("cannot join different H.264 sequence parameters")
    listing = output/"ledger.ffconcat"
    listing.write_text("ffconcat version 1.0\nfile 'prefix.mp4'\nfile 'reverse.mp4'\nfile 'suffix.mp4'\n",
                       encoding="ascii")
    cut.media._run(cut.CLI + ["-f", "concat", "-safe", "1", "-auto_convert", "0",
        "-i", str(listing), "-i", str(before), "-map", "0:v:0", "-map", "1:a:0", "-map", "1:s:0",
        "-c", "copy", "-video_track_timescale", "30000", "-movie_timescale", "48000",
        "-movflags", "+faststart+write_colr", str(result)], output/"join.log")
    check_picture(before, result, new)
    quiet(check_audio(before, result), "decoded AAC")
    with patch.object(prior.review, "REVIEW", PREVIEW):
        comparison_sha = prior.review.comparison(output, before, result, samples)
    (output/"coffee-continuity-review.mp4").rename(output/"ledger-reverse-review.mp4")
    receipt = {
        "base_sha256": BASE_SHA, "source_pcm_sha256": SOURCE_PCM_SHA,
        "builder_sha256": digest(Path(__file__)), "movie_sha256": digest(result),
        "reverse_sha256": digest(new), "review_sha256": comparison_sha,
        "picture_change_frames": [START, STOP], "review_frames": PREVIEW, "crop_xywh": [*CROP[2:], *CROP[:2]],
        "duration_seconds": TOTAL/30, "identical_picture_frames": TOTAL-(STOP-START),
        "identical_audio_stereo_pairs": TOTAL*1600, "same_audio_and_caption_packets": True,
        "human_accepted": False, "production_release": False,
    }
    cut.media._json(output/"ledger-reverse-proof.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--pcm", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.before, args.pcm, args.output), indent=2))
