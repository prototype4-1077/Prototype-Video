"""Stage a silent hand-off on a fixed table: two actors, one rigid filled mug."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_compassion_acting as registration
from pipeline import cartoon_mug_exchange as cel
from pipeline import cartoon_scene_review as media


ROOT=registration.sources.ROOT
SCENE=ROOT/"concept/scenes/june-coffee-thank-you-keys-v1.json"
W,H=1672,941
N=40
SLIDE=112
LEFT=(0,61,729,784)
RIGHT=(936,0,W,725)
COFFEE=(561,284,1064,772)
CUP_BODY=[(580,342),(586,333),(606,324),(655,314),(724,308),(803,306),
          (881,311),(932,321),(956,332),(964,345),(962,356),(953,365),
          (947,402),(946,678),(944,696),(932,716),(914,728),(874,741),
          (815,748),(766,752),(706,748),(659,741),(624,730),(603,716),
          (594,697),(591,679),(592,369),(582,358)]
LOOP_OUT=[(946,389),(960,382),(980,380),(999,384),(1015,394),(1028,415),
          (1034,440),(1034,466),(1029,490),(1014,523),(993,550),(970,571),
          (947,589),(944,561),(950,540),(950,413)]
LOOP_HOLE=[(951,416),(967,410),(983,415),(994,427),(1001,447),(1000,473),
           (994,496),(981,516),(965,532),(949,542)]
THUMB=[(975,356),(990,344),(1025,336),(1069,338),(1100,355),(1111,374),
       (1095,392),(1067,405),(1044,414),(1006,412),(985,403),(978,388)]

JUNE_IN=[(0,74),(27,103),(62,146),(88,175),(138,210),(193,246),(246,264),
         (292,283),(337,317),(366,351),(421,344),(456,339),(505,352),
         (552,355),(589,367),(604,398),(606,432),(626,472),(658,516),
         (670,544),(664,566),(645,575),(609,563),(656,612),(677,640),
         (682,660),(669,687),(646,691),(644,710),(629,731),(607,741),
         (583,736),(557,726),(516,727),(474,719),(437,703),(393,684),
         (348,674),(308,649),(263,648),(214,638),(181,655),(138,658),
         (89,648),(37,635),(0,609)]
JUNE_OUT=[(0,189),(34,219),(78,261),(123,290),(160,312),(195,349),
          (234,341),(284,331),(322,326),(350,333),(382,346),(415,350),
          (448,371),(483,384),(505,394),(513,411),(500,429),(469,441),
          (436,438),(411,429),(398,417),(373,414),(354,426),(383,447),
          (412,469),(448,492),(486,517),(510,537),(526,553),(525,569),
          (509,583),(490,584),(453,570),(427,558),(445,586),(478,616),
          (507,638),(521,655),(521,671),(506,687),(486,686),(470,689),
          (478,706),(466,724),(446,732),(421,725),(392,714),(378,718),
          (351,719),(322,709),(287,698),(240,680),(190,661),(147,638),
          (107,620),(87,631),(47,647),(0,656)]
GUEST_IN=[(1553,0),(1671,0),(1671,426),(1643,452),(1591,471),(1540,478),
          (1497,469),(1465,449),(1439,418),(1427,385),(1391,397),(1352,394),
          (1319,391),(1283,390),(1254,397),(1210,401),(1193,427),(1195,466),
          (1183,496),(1160,507),(1144,500),(1135,484),(1131,463),(1126,482),
          (1112,496),(1095,500),(1082,489),(1078,472),(1083,445),(1061,453),
          (1044,445),(1039,432),(1043,401),(1056,362),(1051,350),(1030,365),
          (1010,368),(998,359),(991,345),(1002,319),(1019,287),(1041,252),
          (1066,220),(1092,191),(1128,179),(1164,166),(1210,146),(1264,136),
          (1301,142),(1342,161),(1388,175),(1411,151),(1442,124),(1489,85),
          (1513,45)]
GUEST_OUT=[(1671,0),(1671,493),(1637,529),(1594,553),(1541,581),(1504,600),
           (1456,613),(1416,618),(1381,607),(1351,587),(1328,562),(1322,561),
           (1278,576),(1220,589),(1152,589),(1121,587),(1088,604),(1059,624),
           (1018,639),(980,653),(960,654),(948,646),(946,628),(956,608),
           (970,589),(983,569),(1003,553),(1007,540),(991,549),(974,547),
           (961,534),(956,519),(958,501),(970,490),(960,474),(957,456),
           (962,434),(969,415),(985,401),(978,391),(976,374),(983,357),
           (998,344),(1020,332),(1064,316),(1110,298),(1154,284),(1180,291),
           (1223,305),(1275,320),(1307,326),(1338,310),(1375,279),(1415,249),
           (1462,207),(1503,162),(1543,126),(1584,86),(1615,47)]

LEFT_MAP=[
    ((6,109),(6,221)), ((107,204),(57,258)), ((259,272),(136,306)),
    ((352,348),(179,345)), ((221,417),(100,406)), ((197,609),(75,571)),
    ((144,639),(43,628)), ((422,351),(264,341)), ((464,348),(315,333)),
    ((554,360),(435,372)), ((588,376),(496,403)), ((580,400),(374,415)),
    ((606,466),(424,482)), ((655,546),(505,557)), ((617,556),(480,564)),
    ((602,586),(441,586)), ((661,655),(502,656)), ((631,676),(468,674)),
    ((594,670),(432,675)), ((624,716),(451,706)), ((575,726),(405,712)),
    ((523,715),(359,708)), ((442,687),(270,674)), ((337,647),(177,627)),
]
RIGHT_MAP=[
    ((1638,19),(1652,39)), ((1518,54),(1562,117)), ((1487,125),(1488,192)),
    ((1550,181),(1539,297)), ((1605,307),(1548,417)), ((1577,417),(1491,526)),
    ((1484,428),(1380,577)), ((1491,254),(1364,384)), ((1424,218),(1308,379)),
    ((1415,363),(1294,504)), ((1339,332),(1230,489)), ((1250,184),(1150,294)),
    ((1177,172),(1108,310)), ((1159,259),(1086,371)), ((1162,372),(1019,371)),
    ((1128,363),(982,373)), ((1006,351),(988,459)), ((1040,323),(1028,440)),
    ((1062,431),(983,510)), ((1100,477),(1036,529)), ((1166,489),(980,630)),
    ((1200,425),(1118,587)), ((1250,399),(1193,582)),
]
POSES=(0,4,9,13,16,19,23,26,30,34,39)
QUIVER=(0,1.1,2.7,1.0,-1.1,-2.0,-.4,0,.6,1.4,2.0,.1,-1.6,-1.0,0,
        .55,1.2,.6,-.6,-.4,.12,.2,0)


@dataclass(frozen=True)
class Cue:
    mug_dx: float
    guest_wrap: float
    june_release: float
    guest_quiver: float


def smooth(i,a,b):
    t=max(0.,min(1.,(i-a)/(b-a)))
    return t*t*(3.-2.*t)


def cues(i):
    if type(i) is not int or not 0<=i<N:
        raise ValueError("outside coffee exchange shot clock")
    wrap=smooth(i,13,23)
    return Cue(-SLIDE*(1-smooth(i,4,16)),wrap,smooth(i,23,30),
               QUIVER[i]*(1-wrap) if i<23 else 0.)


def mask(points,box,blur=.65):
    x,y,r,b=box
    return registration.matte(points,(x,y),(r-x,b-y),blur)


def load_art():
    spec=json.loads(SCENE.read_text(encoding="utf-8"))
    if (spec["canvas"],spec["preview_clock"],spec["motion_requirements"]["slide_right_native_px"],
            spec["replace_existing_cut"],spec["production_release"])!=(
            [W,H],{"fps":30,"frames":N,"new_audio":False},SLIDE,False,False):
        raise ValueError("not the locked separate storyboard")
    frames={}
    for key,row in spec["art"].items():
        path=ROOT/row["file"]
        if registration.cut.beat.digest(path)!=row["sha256"]:
            raise ValueError(f"changed exchange source {key}")
        with Image.open(path) as source:
            if source.mode!="RGB" or source.size!=(W,H):
                raise ValueError(f"incorrect source image {key}")
            frames[key]=np.array(source)
    return spec,frames


@dataclass
class Arm:
    area: registration.Region
    pixels: tuple
    distances: tuple


@dataclass
class Setup:
    spec: dict
    table: np.ndarray
    mug: np.ndarray
    june: Arm
    guest: Arm
    thumb: np.ndarray
    floor_x: np.ndarray
    floor_y: np.ndarray


def make_arm(start,end,roi,points,p0,p1,*,subtract=None):
    area=registration.region(start,end,roi,points,p0)
    a0,a1=(cel.refine(p,mask(outline,roi,0)) for p,outline in zip((area.start,area.end),(p0,p1)))
    if subtract is not None:
        a1*=1-subtract
    return Arm(area,(cel.rgba(area.start,a0),cel.rgba(area.end,a1)),
               (cel.signed_distance(a0),cel.signed_distance(a1)))


def over_rgba(back,front):
    return back*(1-front[...,3:])+front


def slide(layer,x,y=0):
    h,w=layer.shape[:2]
    return cv2.warpAffine(layer,np.float32([[1,0,x],[0,1,y]]),(w,h),flags=cv2.INTER_LINEAR)


def prepare():
    cv2.setNumThreads(1)
    spec,f=load_art()
    offer,taken,table=(f[name] for name in ("approach","receiving","table"))
    body_mask=cel.refine(taken[registration.window(COFFEE)],mask(CUP_BODY,COFFEE,0))
    loop_mask=mask(LOOP_OUT,COFFEE)*(1-mask(LOOP_HOLE,COFFEE,.50))
    loop=cel.rgba(offer[registration.window(COFFEE)],loop_mask)
    # Align the reconstructed loop to the two original body attachments
    # before fitting the wider (unobstructed) outer edge from the source.
    q=947-COFFEE[0]
    loop=cv2.warpAffine(loop,np.float32([[1.135,0,-.135*q],[0,1.02,-2]]),
                       (COFFEE[2]-COFFEE[0],COFFEE[3]-COFFEE[1]),flags=cv2.INTER_LINEAR)
    mug=over_rgba(loop,cel.rgba(taken[registration.window(COFFEE)],body_mask))
    bare_pottery=np.zeros((H,W),np.float32)
    bare_pottery[registration.window(COFFEE)]=mug[...,3]
    guest_thumb=mask(THUMB,RIGHT,1.)
    overlap=bare_pottery[registration.window(RIGHT)]
    holdout=cv2.dilate(overlap,np.ones((5,5),np.uint8))*(1-guest_thumb)
    june=make_arm(offer,taken,LEFT,LEFT_MAP,JUNE_IN,JUNE_OUT)
    guest=make_arm(offer,taken,RIGHT,RIGHT_MAP,GUEST_IN,GUEST_OUT,subtract=holdout)
    y,x=np.indices((H,W),np.float32)
    return Setup(spec,table.astype(np.float32),mug,june,guest,guest_thumb,x,y)


def arm_frame(arm,t):
    if t in (0.,1.):
        return arm.pixels[int(t)]
    pair=arm.area.maps(t)
    a,b=(cv2.remap(art,*warp,cv2.INTER_LINEAR) for art,warp in zip(arm.pixels,pair))
    l,r=(cv2.remap(dist,*warp,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=-32)
         for dist,warp in zip(arm.distances,pair))
    opacity=np.clip((1-t)*l+t*r+.5,0,1)[...,None]
    mix=smooth(t,0.,1.)
    aweight=(1-mix)*np.clip((l+2)/7,.07,1)[...,None]
    bweight=mix*np.clip((r+2)/7,.07,1)[...,None]
    color=(aweight*a[...,:3]+bweight*b[...,:3])/np.maximum(
        .01,aweight*a[...,3:]+bweight*b[...,3:])
    return np.dstack((color*opacity,opacity))


def quiver(arm,d):
    if not d:
        return arm
    y,x=np.indices(arm.shape[:2],np.float32)
    # Only the fingertips react. Anchor knuckles to cuff and arm at right.
    field=np.clip(1-((x+RIGHT[0]-1090)/289)**2-((y-392)/203)**2,0,1)**2
    return cv2.remap(arm,x+d*field*.85,y-d*field,cv2.INTER_LINEAR)


def paint(p,index):
    t=cues(index)
    moon=np.clip(1-((p.floor_x-766-t.mug_dx)/245)**2-((p.floor_y-741)/23)**2,0,1)**2
    shade=np.clip(1-((p.floor_x-347-t.mug_dx+95*t.june_release)/300)**2
                    -((p.floor_y-696+6*t.june_release)/76)**2,0,1)**2
    bg=p.table*(1-(.48*moon+.23*shade)[...,None])
    right=quiver(arm_frame(p.guest,t.guest_wrap),t.guest_quiver)
    left=slide(arm_frame(p.june,t.june_release),t.mug_dx)
    cwin=registration.window(COFFEE)
    rwin=registration.window(RIGHT)
    lwin=registration.window(LEFT)
    bg[rwin]=cel.over(bg[rwin],right)
    # Prepare the rigid mug in its own local space at a single fixed
    # height. The larger draw area includes the full engaged translation.
    wide=(COFFEE[0]-SLIDE,*COFFEE[1:])
    stack=np.zeros((p.mug.shape[0],p.mug.shape[1]+SLIDE,4),np.float32)
    stack[:,SLIDE:]=p.mug
    if cwin[0].start!=wide[1]:
        raise ValueError("mug base coordinate changed")
    win=registration.window(wide)
    bg[win]=cel.over(bg[win],slide(stack,t.mug_dx))
    front=smooth(t.guest_wrap,.76,1.)
    if front:
        bg[rwin]=cel.over(bg[rwin],right*(p.thumb*front)[...,None])
    bg[lwin]=cel.over(bg[lwin],left)
    return np.clip(np.rint(bg),0,255).astype(np.uint8)


def contact_sheet(p,path):
    sheet=Image.new("RGB",(3*384,233*((len(POSES)+2)//3)),"#171312")
    draw=ImageDraw.Draw(sheet)
    for j,i in enumerate(POSES):
        x,y=(j%3)*384,(j//3)*233
        with Image.fromarray(paint(p,i)) as src:
            sheet.paste(src.resize((384,216),Image.Resampling.LANCZOS),(x,y))
        t=cues(i)
        draw.text((x+7,y+216),f"F{i:02} slide {t.mug_dx:+.0f}px | guest {t.guest_wrap:.2f} | release {t.june_release:.2f}",fill="white")
    sheet.save(path,quality=93)


def build(output,inspect=False):
    output.mkdir(parents=True,exist_ok=False)
    p=prepare()
    contact_sheet(p,output/"painted-blocking.jpg")
    if inspect:
        return {}
    movie=output/"coffee-handoff.mp4"
    raw=[]
    with (output/"encode.log").open("wb") as log,subprocess.Popen(
        media.encoder_command("ffmpeg",movie),stdin=subprocess.PIPE,stderr=log
    ) as proc:
        try:
            for i in range(N):
                frame=paint(p,i)
                raw.append(sha256(frame).hexdigest())
                with Image.fromarray(frame) as picture:
                    proc.stdin.write(picture.resize((1920,1080),Image.Resampling.LANCZOS).tobytes())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("handoff preview encode failed")
    video,=media._probe(movie,"ffprobe")["streams"]
    if (video["codec_type"],int(video["nb_read_frames"]),video["avg_frame_rate"],
            video["width"],video["height"])!=("video",N,"30/1",1920,1080):
        raise ValueError("encoded study clock changed")
    proof={"source_art":p.spec["art"],"state":"isolated_silent_motion_test","clock":[1920,1080,30,N],
           "renderer_sha256":registration.cut.beat.digest(Path(__file__)),
           "movie_sha256":registration.cut.beat.digest(movie),"rgb24_native_frame_sha256":raw,
           "handoff_contact_frame":23,"mug_slide_px_native":SLIDE,"mug_lift_px_native":0,
           "cues":[asdict(cues(i)) for i in range(N)],
           "approach_handedness_interpretation":{"June":"right","visitor":"right","replaces_wide_left_brace":False},
           "integrated_into_full_cut":False,"human_accepted":False,"production_release":False}
    media._json(output/"handoff-proof.json",proof)
    return proof


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--poses-only",action="store_true")
    args=parser.parse_args()
    print(json.dumps({k:v for k,v in build(args.output,args.poses_only).items()
                      if k not in ("cues","rgb24_native_frame_sha256")},indent=2))
