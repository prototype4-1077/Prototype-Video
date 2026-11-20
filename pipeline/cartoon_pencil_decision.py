"""Test a deliberate pencil release before June reaches for the coffee pot."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from pipeline import cartoon_ledger_reverse as ledger
from pipeline import cartoon_story_review as story


BASE_SHA = "5876c731314997c5bcdbf02e168c67f3ffae01727fda97e98fd072c9c5efd50d"
START, STOP = 678, 789
REVIEW = (670, 868)
cut, probe, digest = ledger.cut, ledger.probe, ledger.digest
coffee = story.previous.coffee
acting, pour = coffee.acting, coffee.pour


@dataclass(frozen=True)
class Cue:
    stage: str
    hand: float
    pencil: float


def timing(i):
    if type(i) is not int or not START <= i < STOP:
        raise ValueError("pencil decision is confined to the pre-pour shot")
    ease = acting.blend
    if i <= 744:
        return Cue("pencil",ease((i-714)/27),ease((i-717)/18))
    if i <= 760:
        return Cue("reach",ease((i-745)/15),1.)
    if i <= 781:
        return Cue("lift",ease((i-760)/21),1.)
    return Cue("original",1.,1.)


def independent_pencil(p, finger, shaft):
    if finger == shaft and finger in (0.,1.):
        return acting.pen_pose(p,finger)
    # Same hand registration as the established pot lift. The independent
    # shaft now lands before the fingers finish opening.
    brush,from_hand,_ = acting.reg.paint_pair(p.pen,finger)
    origin = np.array(acting.PEN_ROI[:2],np.float32)
    parked, held = np.float32([[413,834],[619,847]])-origin, np.float32([[439,655],[592,830]])-origin
    t = shaft
    tip = (1-t)*held[1]+t*parked[1]
    v0,v1 = held[1]-held[0],parked[1]-parked[0]
    theta = (1-t)*np.arctan2(v0[1],v0[0])+t*np.arctan2(v1[1],v1[0])
    v = ((1-t)*np.linalg.norm(v0)+t*np.linalg.norm(v1))*np.array([np.cos(theta),np.sin(theta)])
    def basis(beg,end):
        dv = end-beg
        return np.float32([beg,end,end+.05*np.array([-dv[1],dv[0]])])
    m = cv2.getAffineTransform(basis(*parked),basis(tip-v,tip))
    h,w = brush.shape[:2]
    pencil = cv2.warpAffine(p.pen_cel,m,(w,h),flags=cv2.INTER_LINEAR)
    held_by = cv2.remap(p.fingers,*from_hand,cv2.INTER_LINEAR)
    # When the shaft rolls down under the palm, the nominal fingertip matte
    # stops short of the far knuckles. Extend it only during that crossing;
    # the extension is gone before the pen is flat and the fingers clear it.
    over_palm = acting.blend((shaft-.16)/.15)*(1-acting.blend((shaft-.76)/.20))
    far_knuckles = cv2.dilate(held_by,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(47,17)))
    exposure = np.maximum(held_by*(1-acting.blend((finger-.60)/.37)),over_palm*far_knuckles)
    pencil *= 1-exposure[...,None]
    art = p.park.copy()
    patch_pixels = np.clip(np.rint(acting.exchange.over(brush,pencil)),0,255).astype(np.uint8)
    acting.reg.apply_region(art,patch_pixels,p.pen)
    return art


def picture(p, i, contract, bg, layers, smears, ground, legacy):
    q = timing(i)
    local = i-677
    idle = pour.timeline_entry_for_frame(contract["timeline"],local)
    if q.stage == "original" or (q.stage=="lift" and q.hand==1.):
        if i == 781:
            layer = layers["POSE_45_POT_LIFT"]
        elif idle["type"] == "pose":
            layer = layers[idle["pose_id"]]
        else:
            layer = smears[local]
        return pour.compose_pour_frame(bg,layer,contract,local)
    new = independent_pencil(p,q.hand,q.pencil) if q.stage=="pencil" else acting.raw_frame(p,q.stage,q.hand)
    # Same source-camera registration, without replacing the porch or mug.
    rgb = legacy.copy()
    rgb[:,:-16] = np.clip(legacy[:,:-16].astype(np.int16)+new[:,16:].astype(np.int16)-ground[:,16:],0,255)
    with Image.fromarray(rgb).convert("RGBA") as layer:
        return pour.compose_pour_frame(bg,layer,contract,local)


def encode(path):
    p = acting.prepare()
    locked = story.previous.native_inventories("visitor")[1]
    hashes = {}
    with story.source.render_inputs() as (_,_,_,active):
        contract,bg,layers,smears = active
        pose = "POSE_45_POT_LIFT"
        declared = next(row for row in contract["poses"] if row["id"]==pose)
        if pour.registration_offset(declared,contract["contact_registration"])!=(-16,0):
            raise ValueError("underlying table alignment changed")
        with Image.alpha_composite(bg.convert("RGBA"),layers[pose]).convert("RGB") as fixed:
            legacy = np.array(fixed)
        with path.with_suffix(".log").open("wb") as log,subprocess.Popen(
                cut.media.encoder_command("ffmpeg",path),stdin=subprocess.PIPE,stderr=log) as proc:
            try:
                for i in range(START,STOP):
                    im,contact = picture(p,i,contract,bg,layers,smears,p.lift.lifted,legacy)
                    with im:
                        if contact["rendered_spill_pixels_source"] or contact["spout_start_error_px_source"]!=0:
                            raise ValueError("pencil edit affected liquid contact")
                        raw = im.tobytes()
                        hashes[i] = sha256(raw).hexdigest()
                        if i >= 782 and hashes[i]!=locked[i]:
                            raise ValueError(f"changed final approach to protected pour at F{i}")
                        proc.stdin.write(raw)
            finally:
                proc.stdin.close()
            if proc.wait():
                raise ValueError("could not encode the pencil-decision shot")
    return hashes


def build(before, pcm, output):
    if digest(before)!=BASE_SHA or digest(pcm)!=ledger.SOURCE_PCM_SHA:
        raise ValueError("requires the exact source-built handoff cut and its PCM")
    ledger.prior.validate_gops(probe.packet_info(before,"v:0"),(0,START,STOP,ledger.TOTAL))
    samples = cut.beat.decoded_audio(pcm,"s32le","<i4")
    with patch.object(ledger,"PREVIEW",REVIEW):
        ledger.quiet(samples,"WAV")
    output.mkdir(parents=True,exist_ok=False)
    a,b,c = (output/f"{name}.mp4" for name in ("prefix","pencil","suffix"))
    raw = encode(b)
    ledger.prior.payoff.copy_picture(before,a,0,START)
    ledger.prior.payoff.copy_picture(before,c,STOP,ledger.TOTAL)
    if len({probe.codec_hash(p) for p in (a,b,c)})!=1:
        raise ValueError("picture codec configuration changed")
    listing = output/"decision.ffconcat"
    listing.write_text("ffconcat version 1.0\nfile 'prefix.mp4'\nfile 'pencil.mp4'\nfile 'suffix.mp4'\n",encoding="ascii")
    film = output/"twelve-dollar-mug.mp4"
    cut.media._run(cut.CLI+["-f","concat","-safe","1","-auto_convert","0","-i",str(listing),
        "-i",str(before),"-map","0:v:0","-map","1:a:0","-map","1:s:0","-c","copy",
        "-video_track_timescale","30000","-movie_timescale","48000","-movflags","+faststart+write_colr",
        str(film)],output/"join.log")
    # The common audit expects all decoded frames in a selected shot to differ,
    # which would punish the deliberately retained final seven native frames.
    old,new,shot = (probe.packet_info(p,"v:0") for p in (before,film,b))
    ledger.prior.validate_gops(new,(0,START,STOP,ledger.TOTAL))
    ledger.prior.validate_gops(shot,(0,STOP-START))
    expect = probe.signature(old[:START])+story.signature_at(probe.signature(shot),START)+probe.signature(old[STOP:])
    if expect!=probe.signature(new):
        raise ValueError("mux changed protected or new picture payloads")
    old,new,shot = (ledger.frame_hashes(p) for p in (before,film,b))
    if len(old)!=ledger.TOTAL or new!=old[:START]+shot+old[STOP:]:
        raise ValueError("unexpected decoded picture difference")
    with patch.object(ledger,"PREVIEW",REVIEW):
        ledger.quiet(ledger.check_audio(before,film),"decoded AAC")
    with patch.object(ledger.prior.review,"REVIEW",REVIEW):
        review_sha = ledger.prior.review.comparison(output,before,film,samples)
    (output/"coffee-continuity-review.mp4").rename(output/"pencil-decision-review.mp4")
    result = {
        "base_sha256":BASE_SHA,"builder_sha256":digest(Path(__file__)),
        "movie_sha256":digest(film),"review_sha256":review_sha,
        "source_span":[START,STOP],"review_span":REVIEW,"native_rgb_sha256":raw,
        "cue_frames":{"pencil_fully_flat":735,"fingers_released":741,"reach_start":746,
                      "pot_raised":781,"original_pour_leadin_start":782},
        "outside_picture_frames_exact":ledger.TOTAL-(STOP-START),"inside_decoded_frames_exact":
            sum(x==y for x,y in zip(old[START:STOP],shot)),
        "audio_and_captions_unchanged":True,"approved_pour_clock_preserved":True,
        "human_accepted":False,"production_release":False,
    }
    cut.media._json(output/"pencil-decision-proof.json",result)
    return result


if __name__=="__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    for flag in ("before","pcm","output"):
        cli.add_argument("--"+flag,type=Path,required=True)
    args = cli.parse_args()
    print(json.dumps({k:v for k,v in build(args.before,args.pcm,args.output).items()
                      if k!="native_rgb_sha256"},indent=2))
