"""Review-only GS020 variation: June offers the same empty mug the visitor lifts."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_ledger_slide as review
from pipeline import cartoon_opening_loan as loan


layer, cel, reg, media = loan.layer, loan.cel, loan.reg, loan.media
SPAN = loan.SPAN
CONTEXT = (56, 312)
BASE_SHA = "5876c731314997c5bcdbf02e168c67f3ffae01727fda97e98fd072c9c5efd50d"
PCM_SHA = "85d9baecc08faefc0b2b09177d0da3ed449f21dd324c3a950081dc05907eef58"
CUP = (loan.CUP[0]-48, *loan.CUP[1:])
FRONT = (0, 708, 735, loan.H)
SAMPLES = (0, 10, 16, 20, 24, 27, 32, 38, 43, 49, 58, 95)
digest = reg.cut.beat.digest


@dataclass(frozen=True)
class Cue:
    slide: float
    release: float
    withdrawn: float
    borrow: loan.Cue


def cues(i):
    if type(i) is not int or not 0 <= i < loan.N:
        raise ValueError("offer is outside the original borrowing shot")
    smooth = layer.smooth
    slide = -48*(1-smooth(i, 3, 16))
    take = loan.cues(max(0, i-12))
    # Preserve the existing final tuck and exact tail, after slowing the start.
    tuck = smooth(i, 68, 82)-smooth(i-12, 56, 82)
    borrow = loan.Cue(take.wrap, take.rise, take.x+28*tuck, take.y+7*tuck)
    return Cue(slide, smooth(i,16,24), smooth(i,20,32), borrow)


def donor_warp(q):
    # Anatomical left hand from the unmirrored GS070A contact keys.
    # Rotate and uniformly scale about the painted middle-fingertip contact.
    angle = np.deg2rad(73)
    a, b = .60*np.cos(angle), .60*np.sin(angle)
    anchor_x, anchor_y = 650, 650-layer.LEFT[1]
    x = 646+q.slide-80*q.withdrawn
    y = 819+230*q.withdrawn
    return np.float32([[a,b,x-a*anchor_x-b*anchor_y],
                       [-b,a,y+b*anchor_x-a*anchor_y-FRONT[1]]])


@dataclass
class Stage:
    loan: loan.Stage
    mug: np.ndarray
    june: layer.Arm
    donor_art: dict


def prepare():
    borrowed = loan.prepare()
    donor = layer.prepare()
    mug = np.pad(borrowed.mug, ((0,0),(loan.CUP[0]-CUP[0],0),(0,0)))
    return Stage(borrowed, mug, donor.june,
                 {key: donor.spec["art"][key] for key in ("approach","receiving")})


def paint(stage, i):
    q = cues(i)
    p = stage.loan
    cup, arm, fg = (reg.window(box) for box in (CUP, loan.ARM, FRONT))
    guest = q.borrow
    x, y = q.slide+guest.x, guest.y
    shadow = np.clip(1-((p.floor_x-724-q.slide-guest.x*.85)/(137+44*guest.rise))**2
                     -((p.floor_y-869)/(19+9*guest.rise))**2,0,1)**2
    out = p.background*(1-(.56-.40*guest.rise)*shadow[...,None])
    if q.withdrawn < 1:
        rgba = layer.arm_frame(stage.june, q.release)
        june = cv2.warpAffine(rgba, donor_warp(q),
                              (FRONT[2]-FRONT[0],FRONT[3]-FRONT[1]))
        # Match the cool porch bounce without killing the painted golden rim.
        june[...,0] *= .98
        june[...,2] *= 1.04
        contact = cv2.GaussianBlur(layer.slide(june[...,3],2,5),(0,0),5)
        table_only = np.clip((p.floor_y[fg]-809)/10,0,1)
        out[fg] *= 1-(.26*(1-q.withdrawn)*contact*table_only)[...,None]
    out[cup] = cel.over(out[cup], layer.slide(stage.mug,x,y))
    front = (layer.arm_frame(p.forearm,guest.wrap) if guest.rise == 0
             else loan.retarget(p.fist,guest.x-loan.DX,guest.y-loan.DY))
    out[arm] = cel.over(out[arm],front)
    if q.withdrawn < 1:
        out[fg] = cel.over(out[fg], june)
    return np.clip(np.rint(out),0,255).astype(np.uint8)


def sheet(stage, path):
    board = Image.new("RGB",(1320,4*239),"#201810")
    draw = ImageDraw.Draw(board)
    for n,i in enumerate(SAMPLES):
        x,y = n%3*440,n//3*239
        im = Image.fromarray(paint(stage,i)).crop((224,499,1106,940))
        board.paste(im.resize((440,220),Image.Resampling.LANCZOS),(x,y))
        q = cues(i)
        draw.text((x+5,y+222),f"F{i+SPAN[0]}  release {q.release:.2f}  wrap {q.borrow.wrap:.2f}",
                  fill="white")
    board.save(path,quality=95)


def build(output, before=None, pcm=None):
    if (before is None)!=(pcm is None):
        raise ValueError("provide the exact baseline picture and PCM together")
    if before:
        for source, expected in ((before,BASE_SHA),(pcm,PCM_SHA)):
            if digest(source)!=expected:
                raise ValueError("requires unchanged clean handoff picture and PCM")
            decoded = reg.cut.beat.decoded_audio(source,"s32le","<i4")
            if any(np.any(decoded[i*1600-1440:i*1600+1440]) for i in CONTEXT):
                raise ValueError("comparison boundaries must be silent")
    output.mkdir(parents=True,exist_ok=False)
    stage = prepare()
    sheet(stage, output/"mug-offer-poses.jpg")
    if not before:
        return
    shot = output/"mug-offer-shot.mp4"
    with (output/"encode.log").open("wb") as log, subprocess.Popen(
            media.encoder_command("ffmpeg",shot),stdin=subprocess.PIPE,stderr=log) as proc:
        try:
            for i in range(loan.N):
                im = Image.fromarray(paint(stage,i)).resize((1920,1080),Image.Resampling.LANCZOS)
                proc.stdin.write(im.tobytes())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("offer shot encode failed")
    video, = media._probe(shot,"ffprobe")["streams"]
    if (video["width"],video["height"],video["avg_frame_rate"],int(video["nb_read_frames"])) != (
            1920,1080,"30/1",loan.N):
        raise ValueError("offer changed the borrowing shot clock")
    movie = output/"mug-offer-review.mp4"
    with patch.multiple(review,CONTEXT=CONTEXT,START=SPAN[0],STOP=SPAN[1]):
        review.preview(before,shot,movie)
    media._json(output/"mug-offer-proof.json",{
        "span": SPAN,"review_span": CONTEXT,"native_canvas": [loan.W,loan.H],
        "baseline_sha256": BASE_SHA,"baseline_pcm_sha256": PCM_SHA,
        "builder_sha256": digest(Path(__file__)),"review_sha256": digest(movie),
        "source_mug_and_borrower_art": loan.ART,"donor_unchanged": stage.donor_art,
        "new_sounds": False,"human_accepted": False,"production_release": False,
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--baseline",type=Path)
    parser.add_argument("--pcm",type=Path)
    args = parser.parse_args()
    build(args.output,args.baseline,args.pcm)
