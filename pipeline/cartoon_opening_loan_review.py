"""Try a visible mug loan in the existing 39.7s review, without changing sound."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_ledger_reverse as ledger
from pipeline import cartoon_opening_loan as drawing


BASE_SHA = "eba0660fbfe162ea3cc77b3ed56f23b5cf5073c93a878c07be45be928d17afb0"
START, STOP = drawing.SPAN
PREVIEW = (56, 312)
TOTAL = ledger.TOTAL
cut, probe, digest = ledger.cut, ledger.probe, ledger.digest


def check_picture(prior, alternate, shot):
    old, new, add = (probe.packet_info(path, "v:0") for path in (prior, alternate, shot))
    for rows in (old, new):
        ledger.prior.validate_gops(rows, (0, START, STOP, TOTAL))
    ledger.prior.validate_gops(add, (0, STOP-START))
    shifted = [(pts+1000*START, dts+1000*START, ticks, hashed, side)
               for pts, dts, ticks, hashed, side in probe.signature(add)]
    if probe.signature(new) != probe.signature(old[:START]) + shifted + probe.signature(old[STOP:]):
        raise ValueError("changed picture packets outside the loan")
    old, new, add = (ledger.frame_hashes(path) for path in (prior, alternate, shot))
    if (len(old) != TOTAL or len(new) != TOTAL or len(add) != STOP-START or
        new != old[:START] + add + old[STOP:] or any(a == b for a,b in zip(old[START:STOP], add))):
        raise ValueError("changed decoded picture outside the loan")


def quiet(samples):
    if samples.shape != (TOTAL*1600, 2) or any(
            np.any(samples[i*1600-1440:i*1600+1440]) for i in PREVIEW):
        raise ValueError("loan review endpoints must have 30 ms of true silence on each side")


def build(before, pcm, shot_dir, output):
    if digest(before) != BASE_SHA or digest(pcm) != ledger.SOURCE_PCM_SHA:
        raise ValueError("not the exact ledger-reverse picture and payoff narration")
    source = shot_dir/"opening-loan.mp4"
    lock = shot_dir/"opening-loan-proof.json"
    receipt = json.loads(lock.read_text(encoding="utf-8"))
    if (receipt["movie_sha256"] != digest(source) or
        receipt["builder_sha256"] != digest(Path(drawing.__file__)) or receipt["source_span"] != [START, STOP] or
        receipt["source_art"] != {k:list(v) for k,v in drawing.ART.items()} or
        receipt["clock"] != [1920, 1080, 30, STOP-START]):
        raise ValueError("opening loan doesn't match its isolated receipt")
    v, = cut.media._probe(source, "ffprobe")["streams"]
    if (v["codec_name"], v["width"], v["height"], v["avg_frame_rate"],
        int(v["nb_read_frames"]), v.get("color_space")) != ("h264", 1920, 1080, "30/1", STOP-START, "bt709"):
        raise ValueError("wrong shot format or clock")
    original = cut.beat.decoded_audio(pcm, "s32le", "<i4")
    quiet(original)
    output.mkdir(parents=True, exist_ok=False)
    prefix, placed, suffix = (output/name for name in ("prefix.mp4", "loan.mp4", "suffix.mp4"))
    ledger.prior.payoff.copy_picture(before, prefix, 0, START)
    ledger.prior.payoff.copy_picture(before, suffix, STOP, TOTAL)
    if len({probe.codec_hash(path) for path in (prefix, source, suffix)}) != 1:
        raise ValueError("incompatible H.264 parameters")
    shutil.copyfile(source, placed)
    listing = output/"loan.ffconcat"
    listing.write_text("ffconcat version 1.0\nfile 'prefix.mp4'\nfile 'loan.mp4'\nfile 'suffix.mp4'\n",
                       encoding="ascii")
    movie = output/"twelve-dollar-mug.mp4"
    cut.media._run(cut.CLI+["-f", "concat", "-safe", "1", "-auto_convert", "0", "-i", str(listing),
        "-i", str(before), "-map", "0:v:0", "-map", "1:a:0", "-map", "1:s:0", "-c", "copy",
        "-video_track_timescale", "30000", "-movie_timescale", "48000",
        "-movflags", "+faststart+write_colr", str(movie)], output/"join.log")
    check_picture(before, movie, source)
    quiet(ledger.check_audio(before, movie))
    with patch.object(ledger.prior.review, "REVIEW", PREVIEW):
        review_sha = ledger.prior.review.comparison(output, before, movie, original)
    (output/"coffee-continuity-review.mp4").rename(output/"opening-loan-review.mp4")
    evidence = {
        "baseline_movie_sha256": BASE_SHA, "movie_sha256": digest(movie),
        "builder_sha256": digest(Path(__file__)), "shot_receipt_sha256": digest(lock),
        "review_sha256": review_sha, "picture_change_frames": [START, STOP], "review_frames": PREVIEW,
        "duration_seconds": TOTAL/30, "identical_picture_frames": TOTAL-(STOP-START),
        "identical_decoded_audio_pairs": TOTAL*1600, "same_audio_and_caption_packets": True,
        "human_accepted": False, "production_release": False,
    }
    cut.media._json(output/"opening-loan-integration.json", evidence)
    return evidence


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("before", "pcm", "shot-dir", "output"):
        p.add_argument("--"+name, required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(build(args.before, args.pcm, args.shot_dir, args.output), indent=2))
