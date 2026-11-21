"""A bounded story study: June sets the ledger aside before choosing coffee."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image

from pipeline import cartoon_pencil_decision as previous


cut, digest, story = previous.cut, previous.digest, previous.story
acting, pour = previous.acting, previous.pour
reg, cel = acting.reg, acting.exchange
START, STOP = previous.START, previous.STOP
CONTEXT = (538,868)
TRAVEL = 58
BOX = (208,629,752,941)
BOOK = [(329,835),(343,832),(366,826),(395,822),(434,814),(470,806),
        (512,799),(549,805),(590,812),(646,824),(691,832),(724,841),
        (730,846),(733,856),(733,870),(730,883),(723,890),(716,888),(674,899),
        (629,912),(580,928),(535,940),(504,940),(437,921),(389,905),
        (354,892),(330,878)]
A = [(342,744),(374,728),(404,717),(428,717),(440,701),(461,697),
     (484,702),(504,713),(526,724),(547,742),(556,755),(558,768),
     (550,781),(544,795),(530,810),(511,821),(483,830),(454,832),
     (425,828),(399,819),(376,805),(350,807),(337,811),(326,803),
     (324,783),(332,761)]
B = [(330,738),(356,718),(386,712),(424,714),(450,720),(476,725),
     (514,726),(536,731),(559,739),(579,753),(595,777),(608,798),
     (612,807),(607,818),(598,824),(583,827),(574,822),(563,828),
     (552,828),(542,820),(529,820),(517,825),(505,819),(493,807),
     (478,795),(458,799),(432,803),(407,803),(385,800),(363,807),
     (344,813),(326,813),(323,793),(329,769)]
SAMPLES = (678,696,705,709,716,722,726,730,735,739,745,752,760,781,788)


@dataclass(frozen=True)
class Beat:
    finger: float
    shaft: float
    book_x: float
    contact_y: float


def beat(i):
    if type(i) is not int or not START<=i<STOP:
        raise ValueError("outside ledger slide study")
    ease = lambda a,b: acting.blend((i-a)/(b-a))
    return Beat(ease(692,716),ease(695,709),-TRAVEL*(1-ease(722,739)),
                12*ease(715,721)*(1-ease(739,745)))


def over(bg, art, mask):
    return np.clip(np.rint(bg*(1-mask[...,None])+art*mask[...,None]),0,255).astype(np.uint8)


def stage(p):
    register = reg.region(p.poise,p.park,BOX,acting.PEN_MAP,A)
    a,b = (acting.matte(coords,BOX,1.3) for coords in (A,B))
    book = acting.matte(BOOK,BOX,.72)
    win = reg.window(BOX)
    sample = p.lift.lifted[win]
    eraser = acting.matte(acting.REST_PEN,BOX,1.1)
    blank = cv2.inpaint(sample,(eraser>.12).astype(np.uint8),4,cv2.INPAINT_TELEA)
    cover_grain = cv2.warpAffine(sample,np.float32([[1,0,0],[0,1,-23]]),
        (sample.shape[1],sample.shape[0])).astype(np.float32)
    grain = cover_grain-cv2.GaussianBlur(cover_grain,(0,0),3.5)
    blank = np.clip(np.rint(blank.astype(np.float32)+grain*eraser[...,None]),0,255).astype(np.uint8)
    body = cel.rgba(blank,book)
    parked = cel.rgba(sample,book)
    # Replace the painted copy of the arm using the uncovered cloth in the
    # held-pot pose. The same ground pixels and view never move with props.
    reveal = acting.matte([(340,758),(369,717),(421,684),(487,681),(544,697),
                           (598,731),(633,773),(626,835),(601,855),(438,850),
                           (362,840)],BOX,6.5)
    distilled = over(p.park[win],sample,reveal)
    # The book's looped tab is visible on the lifted-pot donor, but the
    # parked pot overlaps part of it. Keep the pot itself as a holdout.
    pot = acting.matte([(719,770),(730,790),(731,810),(726,833),(728,843),
                        (733,858),(740,868),(750,872),(752,870),(752,768)],BOX,1.2)
    remove = cv2.dilate((book>.025).astype(np.uint8),np.ones((11,11),np.uint8))
    remove = (remove*(1-pot)>.45).astype(np.uint8)
    clean = cv2.inpaint(distilled,remove,5,cv2.INPAINT_TELEA)
    # Only a narrow strip at the right is exposed during the move; use
    # texture from the same table there (not the "clean porch" book bake).
    y,x = np.indices(remove.shape,np.float32)
    donor = p.park[BOX[1]:BOX[3],1080:1080+remove.shape[1]].astype(np.float32)
    xx,yy = x+BOX[0],y+BOX[1]
    lower = (xx>641)&(xx<728)&(yy>925)
    correction = np.median(sample[lower].astype(np.float32)-donor[lower],axis=0)
    weight = np.clip((xx-622)/57,0,1)*np.clip((yy-820)/34,0,1)*remove
    clean = over(clean,donor+correction,cv2.GaussianBlur(weight,(0,0),2.2)*(1-pot))
    return p,register,a,b,body,parked,clean,book,reveal,x,y


def shaft_shadow(part,t):
    # Include only the physical shaft in the moving-hand layover.
    # Coordinates follow the base independent-pencils renderer.
    p0,p1 = np.array([592,830.]),np.array([619,847.])
    tip = p0*(1-t)+p1*t
    angle = (1-t)*np.arctan2(175,153)+t*np.arctan2(13,206)
    length = (1-t)*np.hypot(153,175)+t*np.hypot(206,13)
    end = tip-length*np.array([np.cos(angle),np.sin(angle)])
    canvas = np.zeros(part.shape[:2],np.uint8)
    a,b = (tuple(np.rint(v-BOX[:2]).astype(int)) for v in (tip,end))
    cv2.line(canvas,a,b,255,20,cv2.LINE_AA)
    return canvas.astype(np.float32)/255


def art(s,i):
    p,registration,a,b,body,parked,clean,book,reveal,x,y = s
    q = beat(i)
    if q.book_x == q.contact_y == 0 and q.finger==1:
        return p.park
    source = previous.independent_pencil(p,q.finger,q.shaft)
    win = reg.window(BOX)
    if q.finger in (0.,1.):
        alpha = a if q.finger==0 else b
    else:
        m,n = registration.maps(q.finger)
        alpha = np.clip((1-q.finger)*reg.remap(a,m)+q.finger*reg.remap(b,n),0,1)
    if q.shaft < 1:
        # Tip above the writing surface while the pencil is still held.
        pen_area = shaft_shadow(source[win],q.shaft)
        alpha = np.maximum(alpha,pen_area)
    wipe = cv2.GaussianBlur(cv2.dilate(np.maximum(alpha,book),np.ones((9,9),np.uint8)),(0,0),1.6)
    plain = over(source[win],clean,np.maximum(wipe,reveal))
    move = np.float32([[1,0,q.book_x],[0,1,0]])
    prop = cv2.warpAffine(parked if q.shaft==1 else body,move,(x.shape[1],x.shape[0]),flags=cv2.INTER_LINEAR)
    # Real distal motion; the denim cuff roots back into the shoulder.
    anchored = np.clip((x+BOX[0]-.5*q.book_x-342)/94,0,1)
    hand = cv2.remap(cel.rgba(source[win],alpha),x-q.book_x*anchored,y-q.contact_y*anchored,cv2.INTER_LINEAR)
    new = cel.over(cel.over(plain,prop),hand)
    # The last fraction rejoins the literal parked plate, not an
    # inpainted approximation; this only affects nearly zero offsets.
    contour = np.clip((abs(q.book_x)+abs(q.contact_y))/4,0,1)
    out = source.copy()
    out[win] = over(source[win],new,np.full(x.shape,contour,np.float32))
    return out


def registered_layer(p,s,legacy,i):
    q = beat(i)
    posed = art(s,i)
    rgb = legacy.copy()
    rgb[:,:-16] = np.clip(legacy[:,:-16].astype(np.int16)+
        posed[:,16:].astype(np.int16)-p.lift.lifted[:,16:],0,255)
    if q.book_x:
        # Old POSE_45 foreground and the raw lifted RGB do not agree at
        # the bound corners; an additive delta leaves two outlines there.
        # Overwrite the swept book underlay before the camera pass, leaving
        # the surrounding original plate and the later parked plate intact.
        _,_,_,_,_,_,_,book,_,x,_ = s
        moved = cv2.warpAffine(book,np.float32([[1,0,q.book_x],[0,1,0]]),
            (book.shape[1],book.shape[0]),flags=cv2.INTER_LINEAR)
        replace = cv2.GaussianBlur(cv2.dilate(np.maximum(book,moved),
            np.ones((21,23),np.uint8)),(0,0),2.2)
        xx,yy,rr,bb = BOX
        target = np.s_[yy:bb,xx-16:rr-16]
        rgb[target] = over(rgb[target],posed[reg.window(BOX)],
                          replace*np.clip(abs(q.book_x)/5,0,1))
    return rgb


def plot(path,poses=False,hashes_only=False):
    p = acting.prepare()
    s = stage(p)
    if poses:
        sheet = Image.new("RGB",(1200,675))
        for j,i in enumerate(SAMPLES[:9]):
            native = art(s,i)
            tile = Image.fromarray(native).resize((400,225),Image.Resampling.LANCZOS)
            sheet.paste(tile,(j%3*400,j//3*225))
        sheet.save(path,quality=94)
        return {}
    hashes = {}
    locked = story.previous.native_inventories("visitor")[1]
    with story.source.render_inputs() as (_,_,_,active):
        contract,bg,layers,smears = active
        canon = "POSE_45_POT_LIFT"
        declared = next(row for row in contract["poses"] if row["id"]==canon)
        if pour.registration_offset(declared,contract["contact_registration"])!=(-16,0):
            raise ValueError("unaligned ledger and porch")
        with Image.alpha_composite(bg.convert("RGBA"),layers[canon]).convert("RGB") as fixed:
            legacy = np.array(fixed)
        with ExitStack() as stack:
            proc = None
            if not hashes_only:
                log = stack.enter_context(path.with_suffix(".log").open("wb"))
                proc = stack.enter_context(subprocess.Popen(
                    cut.media.encoder_command("ffmpeg",path),stdin=subprocess.PIPE,stderr=log))
            try:
                for i in range(START,STOP):
                    if i>745:
                        image,contact = previous.picture(p,i,contract,bg,layers,smears,p.lift.lifted,legacy)
                    else:
                        rgb = registered_layer(p,s,legacy,i)
                        with Image.fromarray(rgb).convert("RGBA") as fore:
                            image,contact = pour.compose_pour_frame(bg,fore,contract,i-677)
                    with image:
                        if contact["rendered_spill_pixels_source"] or contact["spout_start_error_px_source"]:
                            raise ValueError("liquid contact scope changed")
                        raw = image.tobytes()
                        hashes[i] = sha256(raw).hexdigest()
                        if i>=782 and hashes[i]!=locked[i]:
                            raise ValueError("protected pour lead-in drifted")
                        if proc:
                            proc.stdin.write(raw)
            finally:
                if proc:
                    proc.stdin.close()
            if proc and proc.wait():
                raise ValueError("ledger shot encode failed")
    return hashes


def preview(before, shot, output):
    first,end = CONTEXT
    count = end-first
    duration = count/30
    a,b = START-first,STOP-first
    scale = "scale=768:432:flags=lanczos"
    af = (f"atrim=end_sample={count*1600},asetpts=PTS-STARTPTS,"
          f"afade=t=in:d=0.03,afade=t=out:st={duration-.03:.6f}:d=0.03")
    ticks = ",settb=1/30000,setpts=N*1000"
    v = (f"[0:v]trim=end_frame={count},setpts=PTS-STARTPTS,split=3[l0][p0][s0];"
         f"[l0]{scale}{ticks}[left];[p0]trim=end_frame={a},setpts=PTS-STARTPTS,{scale}[p];"
         f"[s0]trim=start_frame={b},setpts=PTS-STARTPTS,{scale}[s];"
         f"[1:v]{scale},setpts=PTS-STARTPTS[m];[p][m][s]concat=n=3:v=1:a=0{ticks}[r];"
         f"[left][r]hstack[v];[0:a]{af}[audio]")
    cut.media._run(cut.CLI+["-ss",str(first/30),"-i",str(before),"-i",str(shot),
        "-filter_complex",v,"-map","[v]","-map","[audio]","-r","30",
        "-c:v","libx264","-threads","4","-crf","16","-pix_fmt","yuv420p",
        "-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709",
        "-c:a","aac","-b:a","256k","-ar","48000","-movie_timescale","48000","-video_track_timescale","30000",
        "-movflags","+faststart",str(output)],output.with_suffix(".log"))
    video,audio = cut.media._probe(output,"ffprobe")["streams"]
    if (int(video["nb_read_frames"])!=count or
        any(abs(float(s["duration"])-duration)>.001 for s in (video,audio))):
        raise ValueError("changed review clock")


def build(before, pcm, output, poses=False, *, existing=None, existing_sha=None):
    if not poses and (digest(before)!=previous.BASE_SHA or digest(pcm)!=previous.ledger.SOURCE_PCM_SHA):
        raise ValueError("requires the exact clean story and its source mix")
    output.mkdir(parents=True,exist_ok=False)
    if poses:
        return plot(output/"ledger-poses.jpg",True)
    for path in (before,pcm):
        s = cut.beat.decoded_audio(path,"s32le","<i4")
        if any(np.any(s[i*1600-1440:i*1600+1440]) for i in CONTEXT):
            raise ValueError("comparison boundaries must be silent")
    shot = output/"ledger-slide.mp4"
    if existing is None:
        raw = plot(shot)
    else:
        if not existing_sha or digest(existing)!=existing_sha:
            raise ValueError("explicit preserved shot hash required")
        story.previous.clip_check(existing,STOP-START)
        shutil.copyfile(existing,shot)
        raw = plot(shot,hashes_only=True)
    movie = output/"ledger-slide-review.mp4"
    preview(before,shot,movie)
    report = {
        "baseline_sha256":previous.BASE_SHA,"builder_sha256":digest(Path(__file__)),
        "silent_shot_sha256":digest(shot),"review_sha256":digest(movie),
        "source_span":[START,STOP],"review_span":CONTEXT,"native_rgb_sha256":raw,
        "timing":{"shaft_flat":709,"contact":721,"slide_start":723,"slide_end":739,"release":745},
        "screen_space_displacement":TRAVEL,"comparison_only":True,
        "human_accepted":False,"production_release":False,
    }
    cut.media._json(output/"ledger-slide-proof.json",report)
    return report


if __name__=="__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    for flag in ("before","pcm","output"):
        cli.add_argument("--"+flag,type=Path,required=(flag=="output"))
    cli.add_argument("--poses-only",action="store_true")
    cli.add_argument("--existing-shot",type=Path)
    cli.add_argument("--existing-shot-sha")
    args = cli.parse_args()
    if not args.poses_only and (not args.before or not args.pcm):
        cli.error("--before and --pcm required for review")
    result = build(args.before,args.pcm,args.output,args.poses_only,
                   existing=args.existing_shot,existing_sha=args.existing_shot_sha)
    print(json.dumps({k:v for k,v in result.items() if k!="native_rgb_sha256"},indent=2))
