"""An optional twenty-frame point-of-view insert for June's change of heart."""
from __future__ import annotations

import argparse
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from pipeline import cartoon_coffee_cut as coffee
from pipeline import cartoon_compassion_review as splice
from pipeline import cartoon_reaction_continuity as reaction


ROOT=reaction.acting.sources.ROOT
PACKAGE=ROOT/"collab/june_visitor_turn_v1"
ART=ROOT/"concept/style_frames/june-gs050-visitor-knee-v1.png"
ART_SHA="6206a2f47450bde84a9aaca494f145c3179f224f8a029a05880c9e2c901ccaf9"
SHA_SOURCE="b339bb0a26e17b573f10a03179f1dd380426377cd474ac20b10c903bb0f3b113"
SHA_NATIVE="474a82f5e9efbb25d073197e1dcfd1082acaad391509c0ba71282bddd773d9f2"
REPLACEMENT=(564,678)
INSERT=(608,628)
REVIEW=(538,678)
ROI=(238,301,891,815)
TIP_WEIGHTS=((352,510,.62),(321,618,.85),(366,698,1.0),(487,712,.90))
# Unequal impulses with nonperiodic timing. Short drawback, stronger first
# twitch, a smaller one after a breath; not a looping sine or whole-image shake.
FLINCH=(0,.10,.59,1,.60,-.22,-.43,-.31,-.12,-.03,.24,.46,.77,.40,-.12,-.27,-.16,-.06,0,0)
CURL=(0,0,.01,.02,.06,.10,.12,.16,.18,.24,.29,.35,.47,.58,.66,.73,.77,.80,.83,.85)


def load_art():
    if splice.cut.beat.digest(ART)!=ART_SHA:
        raise ValueError("visitor hand artwork changed")
    with Image.open(ART) as shot:
        if shot.size!=(1672,941) or shot.mode!="RGB":
            raise ValueError("visitor insert does not match authored local coordinates")
        return np.array(shot)


@lru_cache(maxsize=1)
def fields():
    l,t,r,b=ROI
    y,x=np.indices((b-t,r-l),np.float32)
    def spot(px,py,rx,ry):
        radius=((x+l-px)/rx)**2+((y+t-py)/ry)**2
        return np.maximum(0,1-radius)**2
    tips=np.maximum.reduce([w*spot(px,py,103,111) for px,py,w in TIP_WEIGHTS])
    mid=spot(545,538,274,232)*.47
    flex=spot(413,666,187,147)
    # Preserve the table edge, cuff, heel, thumb and the knee outside
    # each fingertip's immediate envelope. Start at the painted pose.
    distance=np.minimum.reduce([x,y,(r-l-1)-x,(b-t-1)-y])
    boundary=np.clip(distance/14,0,1)
    return x,y,np.minimum(1,tips+mid)*boundary,flex*boundary


def visitor_frame(art, i):
    if type(i) is not int or not INSERT[0]<=i<INSERT[1]:
        raise ValueError("not an authored visitor frame")
    k=i-INSERT[0]
    if k==0:
        return art.copy()
    x,y,d,m=fields()
    l,t,r,b=ROI
    # Inverse sample. The smaller slow movement is a slight finger curl
    # toward the palm; both tics have distinct timing and amplitude.
    mx=x+(6.7*FLINCH[k]-2.8*CURL[k])*d-3.6*CURL[k]*m
    my=y+(-10.7*FLINCH[k]+1.9*CURL[k])*d+4.2*CURL[k]*m
    out=art.copy()
    out[t:b,l:r]=cv2.remap(art[t:b,l:r],mx,my,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
    return out


def native_reference():
    path=PACKAGE/"reference-gs050-native-frames.json"
    if splice.cut.beat.digest(path)!=SHA_NATIVE:
        raise ValueError("original cropped GS050 native inventory changed")
    reference=json.loads(path.read_text(encoding="utf-8"))
    if reference["start_frame_zero_based"]!=564 or len(reference["rgb24_sha256"])!=114:
        raise ValueError("unexpected GS050 inventory")
    return reference["rgb24_sha256"]


def animate(output):
    src=load_art()
    eye=reaction.acting.prepare()
    reference=native_reference()
    hashes=[]
    start,stop=REPLACEMENT
    with output.with_suffix(".log").open("wb") as log,subprocess.Popen(
        splice.cut.media.encoder_command("ffmpeg",output),stdin=subprocess.PIPE,stderr=log
    ) as proc:
        try:
            for i in range(start,stop):
                new=INSERT[0]<=i<INSERT[1]
                if new:
                    with Image.fromarray(visitor_frame(src,i)) as frame:
                        data=frame.resize((1920,1080),Image.Resampling.LANCZOS).tobytes()
                else:
                    with reaction.output_frame(eye,i-start) as frame:
                        data=frame.tobytes()
                digest=sha256(data).hexdigest()
                if (digest==reference[i-start])!=(not new):
                    raise ValueError(f"native source comparison failed at F{i}")
                proc.stdin.write(data)
                hashes.append(digest)
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("could not encode GS050 review")
    a,b=(k-start for k in INSERT)
    distinct=len(set(hashes[a:b]))
    if distinct<17:
        raise ValueError("finger impulse is mostly frozen")
    return {"native_frames_changed":len(set(hashes)),"unique_visitor_frames":distinct,
            "insert_span":INSERT,"anchored_hand_roi":ROI,"motion_keyframes":[611,620]}, hashes


def build(before, output):
    if splice.cut.beat.digest(before)!=SHA_SOURCE:
        raise ValueError("expected the exact full coffee-continuity cut")
    if REPLACEMENT!=(splice.START,splice.STOP):
        raise ValueError("reaction GOP was moved")
    # Reuse the established audit/splice in this process only. The frozen
    # reaction and coffee builder implementations are not modified.
    with patch.multiple(splice,BASELINE=before,BASE_SHA256=SHA_SOURCE,animate=animate):
        receipt=splice.build(output)
    candidate=output/"twelve-dollar-mug-visitor-v1.mp4"
    (output/"twelve-dollar-mug-reaction-v1.mp4").rename(candidate)
    (output/"twelve-dollar-mug-reaction-v1.mov").rename(candidate.with_suffix(".mov"))
    pcm,_=splice.cut.foley.audio.ledger_pour._read_pcm24_wave(splice.PACKAGE/"mix.wav")
    with patch.object(coffee,"REVIEW",REVIEW):
        review_hash=coffee.comparison(output,before,candidate,pcm)
    (output/"coffee-continuity-review.mp4").rename(output/"visitor-turn-review.mp4")
    result={
        "clock":[1920,1080,30,1140],"baseline_sha256":SHA_SOURCE,"candidate_sha256":receipt["candidate_sha256"],
        "asset_sha256":ART_SHA,"baseline_native_gs050_sha256":SHA_NATIVE,
        "builder_sha256":splice.cut.beat.digest(Path(__file__)),
        "replaced_span":REPLACEMENT,"insert_span":INSERT,"review_span":REVIEW,"review_sha256":review_hash,
        "unchanged_video_packets":receipt["strictly_copied_video_packets"],
        "unchanged_other_native_frames":114-(INSERT[1]-INSERT[0]),
        "audio_subtitle_packets_exact":receipt["audio_subtitle_packets_exact"],
        "human_accepted":False,"production_release":False, "motion":receipt["motion"],**receipt["audit"],
    }
    splice.cut.media._json(output/"verification.json",result)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--before",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.before,args.output),indent=2))
