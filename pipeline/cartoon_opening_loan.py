"""GS020: keep the cash planted and let one hand pick up an empty enamel mug."""
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

from pipeline import cartoon_coffee_thank_you as layer


ROOT, reg, cel, media = layer.ROOT, layer.registration, layer.cel, layer.media
W, H = 1672, 940
SPAN = (129, 225)
N = SPAN[1]-SPAN[0]
DX, DY = 73, -100
ART = {
    "reach": ("june-gs020-loan-reach-v1.png", "40450dfe54cba2652a897442eb153f9dcfe3b7d793a936915c4e55822ae0a944"),
    "lift": ("june-gs020-loan-lift-v1.png", "e2d93068f61d2538ebe54e10e8c601446fb71b889986ad451c73119e12f0998c"),
}
CUP = (573, 460, 1024, 914)
ARM = (784, 408, 1408, 929)
BODY=[(609,629),(614,618),(635,612),(674,607),(719,606),(762,607),(798,611),
      (819,619),(828,625),(830,634),(824,643),(820,654),(819,844),(815,855),
      (805,864),(783,871),(756,875),(703,877),(666,874),(640,871),(624,861),
      (618,848),(618,651),(613,640)]
LOOP=[(820,664),(835,657),(852,655),(871,660),(883,671),(891,687),(895,706),
      (893,733),(886,755),(874,778),(860,795),(842,808),(819,824),(817,801),
      (835,790),(853,772),(865,753),(873,732),(877,713),(875,695),(867,681),
      (852,675),(838,676),(820,684)]
OPEN=[(1275,496),(1309,511),(1332,537),(1352,581),(1361,626),(1357,675),
      (1348,724),(1326,762),(1292,789),(1245,800),(1195,804),(1149,797),
      (1105,784),(1071,749),(1038,764),(998,776),(974,779),(961,773),
      (960,762),(946,764),(938,756),(934,746),(938,734),(952,722),
      (936,730),(926,725),(918,715),(919,705),(926,695),(950,675),
      (939,678),(922,680),(912,674),(906,666),(909,654),(921,641),
      (943,618),(964,600),(957,594),(934,601),(906,607),(892,601),
      (884,590),(885,582),(893,576),(912,569),(934,557),(952,554),
      (974,558),(995,556),(1029,566),(1063,586),(1100,582),(1138,557),
      (1172,529),(1219,510)]
FIST=[(1275,496),(1312,510),(1337,540),(1356,581),(1362,628),(1357,681),
      (1347,728),(1325,768),(1290,793),(1245,805),(1191,807),(1147,802),
      (1100,783),(1067,754),(1042,746),(1008,750),(979,751),(955,743),
      (942,731),(940,722),(930,710),(926,697),(929,684),(922,676),
      (918,663),(921,646),(933,630),(921,620),(917,609),(918,591),
      (928,576),(939,567),(941,560),(928,562),(918,559),(911,548),
      (913,539),(922,527),(944,512),(954,500),(971,494),(993,500),
      (1011,516),(1034,526),(1062,547),(1088,565),(1119,559),(1150,542),
      (1195,518),(1233,511)]
PAIRS=[
    ((1300,518),(1300,518)),((1343,576),(1345,574)),((1345,679),(1346,685)),
    ((1294,775),(1292,781)),((1220,791),(1226,799)),((1180,785),(1181,793)),
    ((1110,608),(1124,580)),((1139,690),(1153,681)),((1100,752),(1105,747)),
    ((1066,647),(1072,622)),((1060,717),(1065,707)),((998,597),(1024,550)),
    ((890,585),(915,545)),((917,590),(938,546)),((953,563),(971,503)),
    ((916,664),(924,598)),((941,639),(947,578)),((929,709),(929,661)),
    ((960,684),(951,642)),((944,746),(939,704)),((971,722),(961,692)),
    ((979,768),(961,733)),((1005,757),(991,728)),
]


@dataclass(frozen=True)
class Cue:
    wrap: float
    rise: float
    x: float
    y: float


def cues(i):
    if type(i) is not int or not 0 <= i < N:
        raise ValueError("opening loan frame is outside [129,225)")
    wrap = layer.smooth(i, 9, 27)
    rise = layer.smooth(i, 29, 44)
    tuck = layer.smooth(i, 56, 82)
    return Cue(wrap, rise, DX*rise+28*tuck, DY*rise+7*tuck)


def load():
    frames = []
    for name,digest in ART.values():
        path = ROOT/"concept/style_frames"/name
        if reg.cut.beat.digest(path) != digest:
            raise ValueError("opening loan art changed")
        with Image.open(path) as im:
            if im.size != (W,H) or im.mode != "RGB":
                raise ValueError("opening loan art geometry changed")
            frames.append(np.array(im))
    return frames


def anchoring(x):
    # Fingers and wrist translate with the mug; the shoulder stays fixed.
    r = np.clip((1345-x)/209, 0, 1)
    return r*r*(3-2*r)


def retarget(art, x, y):
    if x == y == 0:
        return art
    gy,gx = np.indices(art.shape[:2], np.float32)
    weight = anchoring(gx+ARM[0]-.55*x)
    return cv2.remap(art, gx-x*weight, gy-y*weight, cv2.INTER_LINEAR)


def restore_wood(bg, first, shared):
    """Borrow grain from the same plank, rather than blur a cup-sized hole."""
    window = np.s_[811:902,585:963]
    area = bg[window].astype(np.float32)
    donor = first[811:902,978:1356].astype(np.float32)
    # Correct the exposure of the borrowed wood to the near and far ends
    # of the actual reveal, leaving the surrounding fixed plate untouched.
    offset = area-donor
    left = np.median(offset[:,:24],axis=1)
    right = np.median(offset[:,-28:],axis=1)
    x = np.linspace(0,1,area.shape[1],dtype=np.float32)[None,:,None]
    correction = left[:,None,:]*(1-x)+right[:,None,:]*x
    correction = cv2.GaussianBlur(correction,(0,0),4)
    matte = cv2.dilate(shared[window].astype(np.float32),np.ones((17,17),np.uint8))
    matte = cv2.GaussianBlur(matte,(0,0),5)
    matte *= np.clip((np.arange(area.shape[0])-1)/17,0,1)[:,None]
    bg[window] = np.clip(np.rint(area*(1-matte[...,None])+
                                (donor+correction)*matte[...,None]),0,255).astype(np.uint8)


@dataclass
class Stage:
    background: np.ndarray
    mug: np.ndarray
    forearm: layer.Arm
    fist: np.ndarray
    floor_x: np.ndarray
    floor_y: np.ndarray


def prepare():
    cv2.setNumThreads(1)
    first,last = load()
    c, a = reg.window(CUP), reg.window(ARM)
    mug_alpha = np.maximum(layer.mask(BODY,CUP),layer.mask(LOOP,CUP,.6))
    mug = cel.rgba(first[c],mug_alpha)
    arm0 = cel.refine(first[a],layer.mask(OPEN,ARM,0))
    arm1 = cel.refine(last[a],layer.mask(FIST,ARM,0))
    cup0 = np.zeros((H,W),np.float32)
    cup0[c] = mug_alpha
    cup1 = layer.slide(cup0,DX,DY)
    # Held-key pottery can overlap the reach of the fingers in the matte.
    # Clear those pixels; the rigid cup and handle are drawn exactly once.
    ceramic = layer.mask([(688,536),(899,536),(899,749),(888,762),(860,774),(715,772),(689,753)],
                         ARM,.75)
    arm1 *= 1-ceramic
    fist = cel.rgba(last[a],arm1)
    landing = retarget(fist,-DX,-DY)
    pairs = [(xy,tuple(int(round(v-d*float(anchoring(out[0])))) for v,d in zip(out,(DX,DY))))
             for xy,out in PAIRS]
    region = reg.region(first,last,ARM,pairs,OPEN)
    open_arm = cel.rgba(first[a],arm0)
    forearm = layer.Arm(region,(open_arm,landing),
                        (cel.signed_distance(arm0),cel.signed_distance(landing[...,3])))
    cover0, cover1 = cup0.copy(), cup1.copy()
    cover0[a] = np.maximum(cover0[a],arm0)
    cover1[a] = np.maximum(cover1[a],arm1)
    # Margin also removes the original hard contact shadow near the base.
    cover0 = np.maximum(cover0,layer.mask([(597,851),(630,845),(789,847),(837,861),(832,881),
                                            (746,882),(632,881),(599,874)],(0,0,W,H),2.))
    cover1 = np.maximum(cover1,layer.mask([(680,850),(738,840),(844,839),(926,845),(974,857),
                                            (966,872),(910,879),(745,879),(688,871)],(0,0,W,H),2.))
    m0 = cv2.dilate((cover0>.04).astype(np.uint8),np.ones((13,13),np.uint8))
    m1 = cv2.dilate((cover1>.04).astype(np.uint8),np.ones((11,11),np.uint8))
    bg = first.copy()
    donate = (m0==1) & (m1==0)
    bg[donate] = last[donate]
    bg = cv2.inpaint(bg,m0*m1,7,cv2.INPAINT_TELEA)
    restore_wood(bg,first,m0*m1)
    y,x = np.indices((H,W),np.float32)
    return Stage(bg.astype(np.float32),mug,forearm,fist,x,y)


def paint(p,i):
    q = cues(i)
    c, a = reg.window(CUP), reg.window(ARM)
    shadow = np.clip(1-((p.floor_x-724-q.x*.85)/(137+44*q.rise))**2
                       -((p.floor_y-869)/(19+9*q.rise))**2,0,1)**2
    out = p.background*(1-(.56-.40*q.rise)*shadow[...,None])
    out[c] = cel.over(out[c],layer.slide(p.mug,q.x,q.y))
    if q.rise == 0:
        front = layer.arm_frame(p.forearm,q.wrap)
    else:
        front = retarget(p.fist,q.x-DX,q.y-DY)
    out[a] = cel.over(out[a],front)
    return np.clip(np.rint(out),0,255).astype(np.uint8)


def sheet(prepared,target):
    choices = (0,12,17,22,27,33,38,44,57,70,82,95)
    board = Image.new("RGB",(1440,4*289),"#21160f")
    draw = ImageDraw.Draw(board)
    for k,i in enumerate(choices):
        x,y = k%3*480,k//3*289
        im = Image.fromarray(paint(prepared,i))
        board.paste(im.resize((480,270),Image.Resampling.LANCZOS),(x,y))
        q = cues(i)
        draw.text((x+5,y+272),f"F{i+SPAN[0]}  grip {q.wrap:.2f}   lift {q.rise:.2f}",fill="white")
    board.save(target,quality=94)


def build(output, *, poses=False):
    output.mkdir(parents=True,exist_ok=False)
    prepared = prepare()
    sheet(prepared,output/"opening-loan-poses.jpg")
    if poses:
        return {}
    movie = output/"opening-loan.mp4"
    hashes = []
    with (output/"encode.log").open("wb") as log, subprocess.Popen(
            media.encoder_command("ffmpeg",movie),stdin=subprocess.PIPE,stderr=log) as proc:
        try:
            for i in range(N):
                rgb = paint(prepared,i)
                hashes.append(sha256(rgb).hexdigest())
                im = Image.fromarray(rgb).resize((1920,1080),Image.Resampling.LANCZOS)
                proc.stdin.write(im.tobytes())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("opening loan encode failed")
    video, = media._probe(movie,"ffprobe")["streams"]
    if (video["width"],video["height"],video["avg_frame_rate"],int(video["nb_read_frames"])) != (1920,1080,"30/1",N):
        raise ValueError("opening loan picture clock changed")
    digest = reg.cut.beat.digest
    receipt = {
        "clock": [1920,1080,30,N], "source_span": SPAN, "source_art": ART,
        "movie_sha256": digest(movie), "builder_sha256": digest(Path(__file__)),
        "native_rgb_sha256_by_frame": hashes,
        "events": {"grip_held": 156, "lift_start_after": 158, "lift_landed":173, "draw_back_complete":211},
        "cup_handle_anatomical_hand": "left", "cash_anatomical_hand": "right",
        "human_accepted": False, "production_release": False, "isolated_silent_shot":True,
    }
    media._json(output/"opening-loan-proof.json",receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--poses-only",action="store_true")
    args = parser.parse_args()
    receipt = build(args.output,poses=args.poses_only)
    print(json.dumps({k:v for k,v in receipt.items() if k!="native_rgb_sha256_by_frame"},indent=2))
