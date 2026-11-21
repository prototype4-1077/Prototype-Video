"""Give the seated opening a grounded thought beat and a single breeze."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image

from pipeline import cartoon_coffee_thank_you as layers
from pipeline import cartoon_pencil_decision as reviewed


N = 129
WINDOW = (1,172)
LAB = reviewed.story.source
cut, digest = reviewed.cut, reviewed.digest
PLATE = "gs010_establishing"
PLATE_SHA = "bb8bf8a21ab05710325d03480f245debf3407ae8fd328dd7ecab0a9d4a3f0481"
ACTOR = (356,42,651,424)
HEAD = [(473,111),(475,94),(488,76),(511,65),(536,58),(570,53),
        (594,60),(610,77),(616,94),(618,113),(612,136),(607,155),
        (605,177),(601,196),(593,217),(581,228),(563,235),(545,233),
        (527,224),(507,209),(493,185),(491,172),(480,174),(473,164),
        (472,142),(474,127)]
CHEST = [(453,197),(473,195),(503,209),(540,221),(571,226),(597,239),
         (623,264),(636,287),(630,330),(609,370),(571,407),(522,410),
         (474,397),(431,373),(404,339),(384,302),(393,261),(412,230)]
TAG = (1337,300,1389,388)
PIVOT = (1364,306)
DROP = [(1364,306),(1365,307),(1366,327),(1370,331),(1372,337),
        (1372,363),(1370,370),(1366,373),(1360,373),(1356,369),
        (1354,363),(1354,338),(1356,332),(1362,327),(1363,308)]
SWAY = ((0,0.),(15,0.),(38,-5.6),(63,5.1),(82,-2.4),(101,1.1),(120,0.),(128,0.))


@dataclass(frozen=True)
class Beat:
    chest_y: float
    nod_deg: float
    tag_deg: float


def cues(i):
    if type(i) is not int or not 0<=i<N:
        raise ValueError("outside the 129-frame porch clock")
    s = lambda start,stop: layers.smooth(i,start,stop)
    breathe = -1.9*s(11,38)+2.5*s(41,79)-.6*s(86,113)
    look = 2.15*s(59,98)-.38*s(99,118)
    if i == N-1:
        sway = SWAY[-1][1]
    else:
        a,b = next((a,b) for a,b in zip(SWAY,SWAY[1:]) if a[0]<=i<b[0])
        sway = a[1]+(b[1]-a[1])*s(a[0],b[0])
    return Beat(breathe,look,sway)


@dataclass
class Porch:
    plate: np.ndarray
    x: np.ndarray
    y: np.ndarray
    head: np.ndarray
    head_cel: np.ndarray
    head_rest: np.ndarray
    head_fill: np.ndarray
    chest: np.ndarray
    sky: np.ndarray
    drop: np.ndarray
    segment: dict


def window(rect):
    return np.s_[rect[1]:rect[3],rect[0]:rect[2]]


def prepare():
    _,master,files,_ = LAB.source_inputs()
    shot = LAB.golden.shot_for_frame(master["shots"],1)
    segment, = shot["segments"]
    if (shot["id"],shot["end_frame"],segment["plate_id"])!=("GS010",N,PLATE) or digest(files[PLATE])!=PLATE_SHA:
        raise ValueError("opening source or camera changed")
    with Image.open(files[PLATE]) as ref:
        if ref.mode!="RGB" or ref.size!=(1672,941):
            raise ValueError("opening plate calibration changed")
        plate = np.array(ref)
    y,x = np.indices(plate[window(ACTOR)].shape[:2],np.float32)
    # Feather the silhouette edges but keep the hand, armrest and mug
    # outside both support zones. No pose is transferred from another view.
    actor = plate[window(ACTOR)]
    hull = layers.mask(HEAD,ACTOR,0.)
    silhouette = (hull>.5).astype(np.uint8)
    diff = np.full(silhouette.shape,cv2.GC_BGD,np.uint8)
    diff[cv2.dilate(silhouette,np.ones((13,13),np.uint8))==1] = cv2.GC_PR_BGD
    diff[silhouette==1] = cv2.GC_PR_FGD
    diff[cv2.erode(silhouette,np.ones((9,9),np.uint8))==1] = cv2.GC_FGD
    cv2.setRNGSeed(106)
    cv2.grabCut(actor,diff,None,np.zeros((1,65),np.float64),np.zeros((1,65),np.float64),
                3,cv2.GC_INIT_WITH_MASK)
    foreground = np.isin(diff,(cv2.GC_FGD,cv2.GC_PR_FGD)).astype(np.uint8)
    head = cv2.GaussianBlur(foreground.astype(np.float32),(0,0),.70)
    fill_head = cv2.dilate(foreground,np.ones((5,5),np.uint8))
    head_rest = cv2.inpaint(actor,fill_head,5,cv2.INPAINT_TELEA)
    chest = layers.mask(CHEST,ACTOR,13.)
    chest *= np.clip(1-(x+ACTOR[0]-604)/27,0,1)*np.clip(1-(y+ACTOR[1]-374)/41,0,1)
    chest *= np.clip((y+ACTOR[1]-185)/62,0,1)*(1-head)
    tag = plate[window(TAG)]
    drop = layers.mask(DROP,TAG,.37)
    fill = cv2.dilate((drop>.05).astype(np.uint8),np.ones((7,7),np.uint8))
    fill[:6,:] = 0
    sky = cv2.inpaint(tag,fill,4,cv2.INPAINT_TELEA)
    return Porch(plate,x,y,head,layers.cel.rgba(actor,head),head_rest,fill_head,chest,
                 sky,layers.cel.rgba(tag,drop),segment)


def frame(p,i):
    q = cues(i)
    out = p.plate.copy()
    if q.chest_y or q.nod_deg:
        x,y = p.x,p.y
        body = cv2.remap(p.plate[window(ACTOR)],x,(y-q.chest_y*p.chest).astype(np.float32),
            cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
        if q.nod_deg:
            # Rotate only a cutout, not the background window or its mullion.
            # Small optical fill is used solely in the vacated silhouette.
            pivot = (546-ACTOR[0],229-ACTOR[1])
            mat = cv2.getRotationMatrix2D(pivot,-q.nod_deg,1.)
            tilted = cv2.warpAffine(p.head_cel,mat,(x.shape[1],x.shape[0]),flags=cv2.INTER_LINEAR)
            rest = body.copy()
            rest[p.head_fill==1] = p.head_rest[p.head_fill==1]
            expression = layers.cel.over(rest,tilted)
            frac = min(1.,q.nod_deg/.3)
            body = np.clip(np.rint(expression*frac+body*(1-frac)),0,255).astype(np.uint8)
        out[window(ACTOR)] = body
    if q.tag_deg:
        px,py = (a-b for a,b in zip(PIVOT,TAG))
        mat = cv2.getRotationMatrix2D((px,py),q.tag_deg,1.)
        foot = cv2.warpAffine(p.drop,mat,(TAG[2]-TAG[0],TAG[3]-TAG[1]),flags=cv2.INTER_LINEAR)
        swung = np.clip(np.rint(layers.cel.over(p.sky,foot)),0,255).astype(np.uint8)
        # The small fixed upper connection is kept intact, even when the
        # cord and wood paddle below it have swung to either side.
        swung[:8,:] = p.plate[window(TAG)][:8,:]
        out[window(TAG)] = swung
    return out


def encode(p,path):
    raw = []
    with path.with_suffix(".log").open("wb") as log,subprocess.Popen(
            cut.media.encoder_command("ffmpeg",path),stdin=subprocess.PIPE,stderr=log) as proc:
        try:
            for i in range(N):
                native = frame(p,i)
                raw.append(sha256(native.tobytes()).hexdigest())
                with Image.fromarray(native) as plate,LAB.golden.compose_plate_frame(plate,p.segment,i+1) as shot:
                    proc.stdin.write(shot.tobytes())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("porch study encode failed")
    reviewed.story.previous.clip_check(path,N)
    return raw


def compare(before, shot, output):
    start,stop = WINDOW
    count = stop-start
    scale = "scale=768:432:flags=lanczos"
    clock = "settb=1/30000,setpts=N*1000"
    chain = (
        f"[0:v]trim=end_frame={count},{scale},split=2[base][tail0];"
        f"[base]{clock}[l];[tail0]trim=start_frame={N-start},setpts=PTS-STARTPTS[t];"
        f"[1:v]trim=start_frame={start},setpts=PTS-STARTPTS,{scale}[head];"
        f"[head][t]concat=n=2:v=1:a=0,{clock}[r];[l][r]hstack[v];"
        f"[0:a]atrim=end_sample={count*1600},asetpts=PTS-STARTPTS,"
        f"afade=t=in:d=0.03,afade=t=out:st={count/30-.03:.6f}:d=0.03[a]"
    )
    cut.media._run(cut.CLI+["-ss",str(start/30),"-i",str(before),"-i",str(shot),
        "-filter_complex",chain,"-map","[v]","-map","[a]","-r","30","-c:v","libx264",
        "-threads","4","-crf","16","-pix_fmt","yuv420p","-colorspace","bt709",
        "-color_primaries","bt709","-color_trc","bt709","-c:a","aac","-b:a","256k","-ar","48000",
        "-movie_timescale","48000","-video_track_timescale","30000","-movflags","+faststart",str(output)],
        output.with_suffix(".log"))
    v,a = cut.media._probe(output,"ffprobe")["streams"]
    if int(v["nb_read_frames"])!=count or any(abs(float(k["duration"])-count/30)>.001 for k in (v,a)):
        raise ValueError("shifted porch review clock")


def build(before,pcm,output):
    if digest(before)!=reviewed.BASE_SHA or digest(pcm)!=reviewed.ledger.SOURCE_PCM_SHA:
        raise ValueError("use the exact clean story and its mix")
    for p in (before,pcm):
        sound = cut.beat.decoded_audio(p,"s32le","<i4")
        if any(np.any(sound[f*1600-1440:f*1600+1440]) for f in WINDOW):
            raise ValueError("review edges are not quiet")
    output.mkdir(parents=True,exist_ok=False)
    shot,review = output/"porch-life.mp4",output/"porch-life-review.mp4"
    raw = encode(prepare(),shot)
    compare(before,shot,review)
    evidence = {
        "baseline_sha256":reviewed.BASE_SHA,"source_plate_sha256":PLATE_SHA,
        "builder_sha256":digest(Path(__file__)),"movie_sha256":digest(shot),"review_sha256":digest(review),
        "native_rgb_sha256":raw,"source_span":[0,N],"review_span":WINDOW,
        "actor_box":ACTOR,"tag_box":TAG,"tag_pivot":PIVOT,
        "no_new_audio":True,"comparison_only":True,"human_accepted":False,"production_release":False,
    }
    cut.media._json(output/"porch-life-proof.json",evidence)
    return evidence


if __name__=="__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    for flag in ("before","pcm","output"):
        cli.add_argument("--"+flag,type=Path,required=True)
    args = cli.parse_args()
    print(json.dumps({k:v for k,v in build(args.before,args.pcm,args.output).items()
                      if k!="native_rgb_sha256"},indent=2))
