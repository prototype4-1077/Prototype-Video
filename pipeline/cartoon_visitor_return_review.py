"""Swap only the mug-return shot in the locked 39.7-second review candidate."""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import cv2
import numpy as np

from pipeline import cartoon_coffee_cut as review
from pipeline import cartoon_coffee_payoff as payoff
from pipeline import cartoon_compassion_review as probe
from pipeline import cartoon_visitor_return as visitor


BASE_SHA="8e352df5bcd279c03e26e4a401fc8c668bf5dab4d7401396206239b1ae3e499d"
START,STOP=visitor.SPAN
TOTAL=1191
PREVIEW=(172,481)
cut=payoff.cut
digest=cut.beat.digest


def validate_gops(rows,edges):
    if len(rows)!=edges[-1]:
        raise ValueError("unexpected video packet count")
    for a,b in zip(edges,edges[1:]):
        if ("K" not in rows[a]["flags"] or
                {int(p["pts"]) for p in rows[a:b]}!={i*1000 for i in range(a,b)}):
            raise ValueError(f"segment {a}:{b} is not a closed presentation range")


def audit(before,after,source):
    baseline,alternate=(probe.packet_info(path,"v:0") for path in (before,after))
    for rows in (baseline,alternate):
        validate_gops(rows,(0,START,STOP,TOTAL))
    for a,b in ((0,START),(STOP,TOTAL)):
        if probe.signature(baseline[a:b])!=probe.signature(alternate[a:b]):
            raise ValueError(f"protected picture packets changed at {a}:{b}")
    original=probe.packet_info(source,"v:0")
    validate_gops(original,(0,STOP-START))
    shifted=[(pts+START*1000,dts+START*1000,dur,h,side)
             for pts,dts,dur,h,side in probe.signature(original)]
    if shifted!=probe.signature(alternate[START:STOP]):
        raise ValueError("retimed or re-encoded the replacement shot")
    for stream in ("a:0","s:0"):
        if probe.signature(probe.packet_info(before,stream))!=probe.signature(probe.packet_info(after,stream)):
            raise ValueError(f"changed {stream} payload, clock, or metadata")
    v,a,s=cut.media._probe(after,"ffprobe")["streams"]
    if (v["width"],v["height"],v["avg_frame_rate"],v.get("color_space"),
        a["sample_rate"],a["channels"],s["codec_type"])!=(1920,1080,"30/1","bt709","48000",2,"subtitle"):
        raise ValueError("drifted delivery format")
    if any(int(r["start_pts"]) or
           int(r["duration_ts"])*Fraction(r["time_base"])!=Fraction(TOTAL,30) for r in (v,a)):
        raise ValueError("drifted delivery timing")
    original_audio,new_audio=(cut.beat.decoded_audio(path,"s32le","<i4") for path in (before,after))
    padding=len(original_audio)-TOTAL*1600
    if (not 0<=padding<1024 or np.any(original_audio[TOTAL*1600:]) or
            not np.array_equal(original_audio,new_audio)):
        raise ValueError("decoded audio changed")
    frames=(cv2.VideoCapture(str(p)) for p in (before,after))
    base,new=frames
    retained=changed=0
    try:
        for i in range(TOTAL):
            ok,x=base.read()
            valid,y=new.read()
            if not ok or not valid:
                raise ValueError(f"incomplete decoded feature at frame {i}")
            same=np.array_equal(x,y)
            if same==(START<=i<STOP):
                raise ValueError(f"unexpected decoded identity at frame {i}")
            retained+=int(same)
            changed+=int(not same)
        if base.read()[0] or new.read()[0]:
            raise ValueError("unexpected extra decoded picture")
    finally:
        base.release()
        new.release()
    return {"pictures_unchanged":retained,"pictures_replaced":changed,
            "audio_stereo_pairs_identical":TOTAL*1600,"zero_aac_padding_pairs":padding,
            "captions_packets_identical":True}


def build(before,pcm,shot_dir,output,*,finish_existing=False):
    if digest(before)!=BASE_SHA:
        raise ValueError("not the exact 39.7-second coffee-payoff review MP4")
    baseline=probe.packet_info(before,"v:0")
    validate_gops(baseline,(0,START,STOP,TOTAL))
    source=shot_dir/"visitor-return.mp4"
    lock=shot_dir/"visitor-return-proof.json"
    receipt=json.loads(lock.read_text(encoding="utf-8"))
    if (digest(source)!=receipt["movie_sha256"] or
        receipt["source_builder_sha256"]!=digest(Path(visitor.__file__)) or
        receipt["source_span"]!=[START,STOP] or
        receipt["clock"]!=[1920,1080,30,STOP-START]):
        raise ValueError("visitor shot does not match its exact build receipt")
    # Also verify silence in the actual decoded source, not just in its WAV.
    audio=cut.beat.decoded_audio(before,"s32le","<i4")
    for index in PREVIEW:
        if np.max(np.abs(audio[index*1600-1440:index*1600+1440].astype(np.int64)))>2**31*10**(-65/20):
            raise ValueError("decoded review boundary is not quiet")
    product=output/"twelve-dollar-mug.mp4"
    if finish_existing:
        for name in ("visitor-return-integration.json","visitor-return-review.mp4",
                     "coffee-continuity-review.mp4"):
            if (output/name).exists():
                raise ValueError("completed or partial evidence already exists; will not overwrite")
    else:
        output.mkdir(parents=True,exist_ok=False)
        prefix,suffix=output/"prefix.mp4",output/"suffix.mp4"
        payoff.copy_picture(before,prefix,0,START)
        payoff.copy_picture(before,suffix,STOP,TOTAL)
        if len({probe.codec_hash(p) for p in (prefix,source,suffix)})!=1:
            raise ValueError("incompatible H.264 sequence parameters")
        shutil.copyfile(source,output/"return.mp4")
        listing=output/"visitor.ffconcat"
        listing.write_text("ffconcat version 1.0\nfile 'prefix.mp4'\nfile 'return.mp4'\nfile 'suffix.mp4'\n",
                           encoding="ascii")
        cut.media._run(cut.CLI+["-f","concat","-safe","1","-auto_convert","0","-i",str(listing),
            "-i",str(before),"-map","0:v:0","-map","1:a:0","-map","1:s:0","-c","copy",
            "-video_track_timescale","30000","-movie_timescale","48000","-movflags","+faststart+write_colr",
            str(product)],output/"join.log")
    checks=audit(before,product,source)
    samples=cut.beat.decoded_audio(pcm,"s32le","<i4")
    if samples.shape!=(TOTAL*1600,2):
        raise ValueError("side-by-side source PCM does not match the full scene clock")
    with patch.object(review,"REVIEW",PREVIEW):
        comparison_hash=review.comparison(output,before,product,samples)
    comparison=output/"visitor-return-review.mp4"
    (output/"coffee-continuity-review.mp4").rename(comparison)
    report={
        "base_sha256":BASE_SHA,"movie_sha256":digest(product),
        "shot_receipt_sha256":digest(lock),"builder_sha256":digest(Path(__file__)),
        "before_after_sha256":comparison_hash,"shot_frames":[START,STOP],
        "preview_frames":PREVIEW,"duration_seconds":TOTAL/30,**checks,
        "human_accepted":False,"production_release":False,
    }
    cut.media._json(output/"visitor-return-integration.json",report)
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before",type=Path,required=True)
    parser.add_argument("--pcm",type=Path,required=True)
    parser.add_argument("--shot-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--finish-existing",action="store_true")
    args=parser.parse_args()
    print(json.dumps(build(args.before,args.pcm,args.shot_dir,args.output,
                           finish_existing=args.finish_existing),indent=2))
