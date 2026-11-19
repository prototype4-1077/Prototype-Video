"""Local GS060 right-hand pickup/return study; no full-film edit or audio."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_compassion_acting as register
from pipeline import cartoon_mug_exchange as exchange
from pipeline import cartoon_scene_review as media


ART = register.sources.ROOT / "concept/style_frames"
GROUND = "june-gs060-right-grip-grounded-v1.png"
AIR = "june-golden-scene-gs060-performance-pot-lift-v1.png"
HASHES = {
    GROUND: "fba6a0e07a2f1759b58d13df539a5e58f7795f8ed6acb5bd60ac9ac8bb81558a",
    AIR: "fa41253a8094b0f6663ea7e057201fc0ed0dd2939f417c12d12d224543eaee24",
}
ROI = (165, 277, 1011, 925)
ART_POINTS = {
    # Screen-left is June's right. Follow that shoulder to elbow and cuff;
    # these are paired observations in the un-cropped native paintings.
    "shoulder_seam": ((419, 298), (420, 298)),
    "upper_sleeve": ((317, 368), (320, 367)),
    "outer_elbow": ((211, 674), (203, 572)),
    "inner_elbow": ((285, 646), (283, 514)),
    "lower_sleeve": ((271, 771), (265, 649)),
    "upper_cuff": ((471, 657), (497, 447)),
    "lower_cuff": ((484, 787), (510, 569)),
    "wrist_top": ((553, 672), (583, 430)),
    "wrist_bottom": ((552, 782), (579, 535)),
    "thumb": ((726, 631), (767, 418)),
    "knuckles": ((722, 709), (756, 485)),
    "little_finger": ((676, 782), (706, 548)),
    "upper_loop": ((735, 649), (757, 434)),
    "loop_bottom": ((717, 820), (719, 607)),
    "lid_knob": ((810, 584), (849, 406)),
    "lid_left": ((749, 634), (771, 427)),
    "lid_right": ((877, 637), (898, 458)),
    "body_mid": ((807, 751), (807, 550)),
    "foot_left": ((727, 857), (711, 645)),
    "foot_right": ((884, 860), (866, 673)),
    "base": ((806, 875), (793, 676)),
    "spout_root": ((879, 775), (874, 611)),
    "spout_tip": ((937, 643), (960, 487)),
    # Pin the table/actor surroundings rather than warping the entire image.
    "ledger_far": ((714, 838), (714, 838)),
    "cuff_table_gap": ((553, 800), (553, 800)),
    "table_front": ((811, 907), (811, 907)),
    "table_cup_gap": ((910, 874), (910, 874)),
    "mug_rim_left": ((921, 697), (921, 697)),
    "mug_foot_left": ((923, 853), (923, 853)),
    "left_sleeve_far": ((975, 650), (975, 650)),
    "porch": ((990, 436), (990, 436)),
    "beard_edge": ((741, 386), (741, 386)),
}
# Seed matte contours including the portion of right sleeve that articulates.
# A narrow GrabCut band refines those marks to each painted silhouette.
GROUND_OUTLINE = [(312,417),(268,475),(232,548),(208,621),(207,681),(217,721),
                  (248,756),(293,780),(359,795),(453,791),(530,793),(568,784),
                  (635,784),(674,785),(692,775),(699,792),(716,813),(720,851),
                  (725,866),(750,876),(807,879),(857,876),(883,870),(889,858),
                  (885,798),(908,764),(919,700),(929,667),(943,647),(943,639),
                  (919,636),(907,648),(887,691),(878,715),(874,646),(881,631),
                  (879,619),(858,603),(822,595),(834,586),(832,579),(818,575),
                  (798,576),(792,584),(797,596),(770,607),(750,618),(741,629),
                  (729,646),(715,640),(729,633),(729,622),(721,618),(696,622),
                  (681,618),(640,628),(589,647),(555,657),(501,656),(457,645),
                  (406,623),(382,607),(398,554),(414,493),(411,444),(401,407)]
AIR_OUTLINE = [(315,418),(265,455),(224,495),(204,536),(197,574),(199,617),
               (213,645),(240,665),(273,673),(327,665),(390,644),(443,619),
               (490,596),(540,574),(570,553),(578,530),(614,541),(643,551),
               (674,557),(692,550),(699,537),(709,557),(717,581),(717,603),
               (706,632),(703,647),(708,659),(731,670),(777,684),(830,691),
               (861,689),(869,679),(881,620),(899,600),(913,574),(932,524),
               (952,501),(966,492),(968,485),(954,479),(938,479),(921,489),
               (906,511),(895,542),(887,569),(905,479),(911,464),(905,450),
               (887,434),(865,423),(868,411),(866,403),(846,395),(832,395),
               (826,402),(829,414),(804,415),(784,419),(774,424),(767,420),
               (770,412),(762,405),(744,405),(713,403),(675,411),(616,420),
               (582,425),(542,435),(472,447),(418,461),(395,472),(393,437)]
LOOP_HOLES = (
    [(697,780),(709,791),(721,803),(724,766),(728,709),(726,731),(716,763)],
    [(709,543),(722,522),(735,501),(735,528),(729,558),(724,579)],
)
COUNT = 90
SAMPLES = (0, 10, 16, 22, 28, 34, 49, 56, 63, 71, 77, 89)


def load(name):
    path = ART / name
    if register.cut.beat.digest(path) != HASHES[name]:
        raise ValueError(f"grounded-study asset changed: {name}")
    with Image.open(path) as art:
        expected = (1671 if name == GROUND else 1672, 941)
        if art.size != expected or art.mode != "RGB":
            raise ValueError(f"unexpected art geometry: {art.size}/{art.mode}")
        return np.asarray(art.resize((1672, 941), Image.Resampling.BICUBIC))


@dataclass
class Prepared:
    lifted: np.ndarray
    area: register.Region
    cels: tuple
    distances: tuple
    background: np.ndarray
    cup: np.ndarray
    shadow: np.ndarray


def prepare():
    cv2.setNumThreads(1)
    grounded, lifted = load(GROUND), load(AIR)
    x, y, r, b = ROI
    size=(r-x,b-y)
    support=[(x,y),(r-1,y),(r-1,b-1),(x,b-1)]
    area = register.region(grounded,lifted,ROI,list(ART_POINTS.values()),support)
    # Keep the exact original mug and its left-hand brace. If the spout
    # approaches it, occlude the spout like a physical object behind it.
    cup=register.matte([(920,695),(946,683),(1010,685),(1010,897),
                       (934,889),(917,859),(918,731)],(x,y),size,.8)
    alphas=[]
    for art,outline,hole in zip((area.start,area.end),(GROUND_OUTLINE,AIR_OUTLINE),LOOP_HOLES):
        mask=exchange.refine(art,register.matte(outline,(x,y),size))
        mask*= (1-register.matte(hole,(x,y),size,.64))*(1-cup)
        alphas.append(mask)
    a0,a1=alphas
    bg=area.end.copy()
    # A pixel concealed in the lift drawing can be exposed in the grounded
    # drawing. Use that real paint where available and inpaint only the
    # residual double-occlusion, primarily dark denim beneath the sleeve.
    hidden=cv2.dilate((a1>.06).astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)
    no_donor=cv2.dilate((a0>.04).astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)
    bg[hidden & ~no_donor]=area.start[hidden & ~no_donor]
    bg=cv2.inpaint(bg,(hidden & no_donor).astype(np.uint8),4,cv2.INPAINT_TELEA)
    g_y,g_x=np.ogrid[y:b,x:r]
    shadow=.26*np.exp(-.5*(((g_x-805)/69)**2+((g_y-874)/4.2)**2))
    return Prepared(lifted,area,tuple(exchange.rgba(a,m) for a,m in zip((area.start,area.end),alphas)),
                    tuple(exchange.signed_distance(m) for m in alphas),bg,cup,shadow.astype(np.float32))


def rise(index):
    if type(index) is not int or not 0 <= index < COUNT:
        raise ValueError("study frame outside time base")
    if index <= 34:
        s = max(0., min(1., (index-8)/26))
    else:
        s = 1.-max(0., min(1., (index-49)/28))
    # Smoothstep keeps acceleration gentler around contact than cubic-in-out
    # at mid-swing. Return has a longer deceleration into the tabletop.
    return s*s*(3.-2.*s)


def frame(p, t):
    if not 0 <= t <= 1:
        raise ValueError("phase outside closed interval")
    image=p.lifted.copy()
    if t == 1:
        return image
    area=p.area
    if t == 0:
        cel=p.cels[0]
    else:
        map0,map1=area.maps(t)
        first,last=(cv2.remap(cel,*warp,cv2.INTER_LINEAR) for cel,warp in zip(p.cels,(map0,map1)))
        d0,d1=(cv2.remap(sd,*warp,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=-32)
               for sd,warp in zip(p.distances,(map0,map1)))
        # One silhouette. Never cross-dissolve the porch, face or ledger.
        silhouette=np.clip((1-t)*d0+t*d1+.48,0,1)[...,None]*(1-p.cup[...,None])
        mix=register.ease(t,0,1)
        w0=(1-mix)*np.clip((d0+2)/7,.06,1)[...,None]
        w1=mix*np.clip((d1+2)/7,.06,1)[...,None]
        color=(w0*first[...,:3]+w1*last[...,:3])/np.maximum(
            .009,w0*first[...,3:]+w1*last[...,3:])
        cel=np.concatenate([color*silhouette,silhouette],axis=2)
    bg=p.background*(1-p.shadow[...,None]*(1-min(1,t/.14)))
    patch=exchange.over(bg,cel)
    # Recover exact untouched pixels through both masks and remove only a
    # small reassembly seam approaching the original end key.
    correction_ramp=max(0.,(t-.94)/.06)
    patch=(patch*(1-correction_ramp)+area.end*correction_ramp)*(1-p.cup[...,None])+area.end*p.cup[...,None]
    image[register.window(ROI)]=np.rint(np.clip(patch,0,255)).astype(np.uint8)
    return image


def sheet(prepared, path, samples=SAMPLES):
    rows = (len(samples)+2)//3
    board = Image.new("RGB",(1200,269*rows), "#15100d")
    draw = ImageDraw.Draw(board)
    for i, index in enumerate(samples):
        x,y = (i%3)*400,(i//3)*269
        with Image.fromarray(frame(prepared,rise(index))) as art:
            board.paste(art.crop((161,341,1161,916)).resize((400,230),Image.Resampling.LANCZOS),(x,y))
        draw.text((x+10,y+239),f"F{index:02} | lift fraction {rise(index):.2f}",fill="white")
    board.save(path,quality=95)


def build(output):
    output.mkdir(parents=True, exist_ok=False)
    prepared=prepare()
    sheet(prepared,output/"grounded-poses.jpg")
    clip=output/"grounded-lift-study.mp4"
    with (output/"encode.log").open("wb") as log, subprocess.Popen(
        media.encoder_command("ffmpeg",clip),stdin=subprocess.PIPE,stderr=log
    ) as proc:
        digests=[]
        try:
            for index in range(COUNT):
                raw=frame(prepared,rise(index))
                digests.append(sha256(raw).hexdigest())
                with Image.fromarray(raw) as art:
                    proc.stdin.write(art.resize((1920,1080),Image.Resampling.LANCZOS).tobytes())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("could not encode grounded lift study")
    streams=media._probe(clip,"ffprobe")["streams"]
    if len(streams)!=1 or int(streams[0]["nb_read_frames"])!=COUNT or streams[0]["duration"]!="3.000000":
        raise ValueError("unexpected encoded preview clock")
    result={"source_sha256":HASHES, "builder_sha256":register.cut.beat.digest(Path(__file__)),
            "video_sha256":register.cut.beat.digest(clip),"clock":[1920,1080,30,COUNT],
            "active_roi":ROI,"lift_hold_return_inclusive":[[8,34],[34,49],[49,77]],
            "native_rgb24_sha256":digests,
            "silent_picture_study":True,"full_film_integrated":False,
            "human_accepted":False,"production_release":False}
    media._json(output/"lift-study-proof.json",result)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    options=parser.parse_args()
    print(json.dumps({k:v for k,v in build(options.output).items() if k!="native_rgb24_sha256"},indent=2))
