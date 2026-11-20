"""GS030: the visitor returns the mug and sets down the pie in two beats."""
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
from pipeline import cartoon_compassion_acting as reg
from pipeline import cartoon_scene_review as media


ROOT=layer.ROOT
SPAN=(225,396)
N=171
W,H=1672,940
ART={
    "carry":("june-gs030-visitor-carry-v1.png","054367eb22d00489a973a2a18ca02c1fd3c9a04f61ffa06f0f610e2f570f674d"),
    "returned":("june-gs030-visitor-returned-v1.png","3b96e5fedf088598a74df946b0e62e9eaeb54bf578c07376d193c9b222cbacda"),
}
MUG=(472,630,793,899)
PIE=(875,665,1309,902)
R=(188,441,610,894)
L=(1000,514,1570,906)
E=(830,162,1088,292)
MUG_DROP=64
PIE_DROP=122
PIE_TRAVEL_X=18
MUG_BODY=[(557,672),(562,663),(588,654),(635,649),(691,649),(729,653),(751,660),
          (764,670),(768,679),(760,690),(760,848),(756,865),(747,873),(724,879),
          (695,883),(641,884),(604,880),(584,874),(569,865),(565,848),(564,691)]
MUG_LOOP=[(565,697),(550,695),(531,697),(518,705),(505,721),(498,740),(499,761),
          (507,784),(522,801),(540,816),(562,823),(571,818),(570,798),(554,794),
          (535,782),(522,762),(517,740),(526,720),(542,715),(566,717)]
PIE_OUT=[(893,764),(906,740),(926,721),(956,712),(985,700),(1023,696),
         (1050,692),(1084,692),(1120,693),(1158,698),(1192,704),(1218,719),
         (1243,724),(1267,741),(1283,758),(1289,773),(1278,795),(1268,819),
         (1256,846),(1240,865),(1203,877),(1156,884),(1095,889),(1050,888),
         (1001,886),(966,878),(941,865),(928,845),(915,815),(902,797)]
R0=[(217,627),(236,555),(281,500),(339,477),(387,458),(455,458),(522,475),
    (561,491),(584,531),(590,552),(567,574),(536,583),(530,600),(552,608),
    (555,619),(541,633),(522,635),(531,650),(543,680),(535,696),(525,704),
    (526,723),(513,740),(513,755),(503,775),(473,789),(441,788),(410,779),
    (389,773),(367,783),(338,795),(299,799),(264,787),(242,758),(224,716)]
R1=[(202,676),(219,617),(249,567),(292,525),(349,497),(397,470),(448,463),
    (497,469),(541,486),(567,508),(579,542),(552,567),(526,586),(511,609),
    (489,640),(459,655),(466,657),(479,657),(487,671),(479,689),(461,699),
    (438,701),(413,707),(432,723),(456,741),(475,756),(478,768),(469,781),
    (452,781),(433,777),(420,778),(447,792),(471,803),(484,817),(484,833),
    (478,847),(469,860),(442,869),(400,870),(366,864),(335,855),(313,840),
    (284,835),(259,824),(235,810),(220,791),(208,764),(198,722)]
L0=[(1230,533),(1285,529),(1356,546),(1400,576),(1435,612),(1464,649),(1483,690),
    (1481,738),(1464,776),(1435,799),(1390,814),(1348,828),(1304,838),(1266,838),
    (1238,829),(1207,845),(1170,842),(1135,827),(1117,816),(1094,810),(1069,802),
    (1047,792),(1030,782),(1031,771),(1043,764),(1074,769),(1092,760),(1133,753),
    (1178,754),(1217,747),(1252,728),(1265,712),(1260,697),(1265,681),(1282,668),
    (1309,676),(1314,657),(1298,625),(1276,607),(1241,585)]
L1=[(1242,535),(1297,529),(1356,545),(1413,572),(1467,601),(1501,635),(1524,673),
    (1545,710),(1550,740),(1538,778),(1516,801),(1490,823),(1455,836),(1421,854),
    (1376,871),(1342,877),(1315,869),(1309,857),(1316,845),(1317,832),(1329,819),
    (1343,808),(1347,796),(1340,787),(1344,776),(1351,768),(1365,756),(1363,744),
    (1348,733),(1326,731),(1307,721),(1297,708),(1291,691),(1295,676),(1306,671),
    (1321,676),(1338,687),(1353,688),(1377,696),(1384,688),(1370,641),(1341,611),
    (1294,584)]
RIGHT_PAIRS=[
    ((245,570),(227,626)),((316,521),(285,567)),((371,481),(340,529)),
    ((441,470),(405,482)),((496,489),(493,505)),((550,542),(551,555)),
    ((287,586),(268,645)),((349,598),(329,672)),((313,754),(255,803)),
    ((367,754),(309,820)),((415,625),(359,695)),((475,590),(393,677)),
    ((551,618),(472,674)),((536,665),(469,765)),((519,702),(473,818)),
    ((497,748),(460,845)),((462,779),(410,855)),((420,777),(361,846)),
]
LEFT_PAIRS=[
    ((1360,555),(1362,564)),((1433,621),(1468,642)),((1466,702),(1525,738)),
    ((1454,768),(1501,799)),((1369,800),(1430,823)),((1321,717),(1435,758)),
    ((1300,689),(1320,688)),((1281,732),(1358,729)),((1249,782),(1405,778)),
    ((1192,806),(1363,794)),((1150,811),(1350,821)),((1101,794),(1327,854)),
    ((1046,776),(1325,861)),((1182,775),(1373,828)),((1243,574),(1250,561)),
]
EYE_PAIRS=[
    ((875,206),(875,198)),((899,206),(898,191)),((930,213),(932,204)),((941,222),(943,213)),
    ((894,229),(895,212)),((911,237),(897,201)),((926,235),(924,208)),
    ((988,231),(989,224)),((1018,242),(1014,226)),((1040,250),(1040,238)),
    ((994,254),(991,232)),((1011,265),(1001,230)),((1033,266),(1028,246)),
]
SAMPLES=(0,41,54,67,77,87,99,108,118,129,140,154,170)


@dataclass(frozen=True)
class Cue:
    mug_progress: float
    right_release: float
    pie_progress: float
    left_release: float
    glance: float


def cues(i):
    if type(i) is not int or not 0<=i<N:
        raise ValueError("visitor shot clock")
    return Cue(layer.smooth(i,39,66),layer.smooth(i,66,84),
               layer.smooth(i,88,119),layer.smooth(i,105,135),layer.smooth(i,134,155))


def matte(points,roi,blur=.65):
    return layer.mask(points,roi,blur)


def load():
    images=[]
    for name,digest in ART.values():
        file=ROOT/"concept/style_frames"/name
        if reg.cut.beat.digest(file)!=digest:
            raise ValueError("visitor source image changed")
        with Image.open(file) as plate:
            if plate.size!=(W,H) or plate.mode!="RGB":
                raise ValueError("visitor source geometry changed")
            images.append(np.array(plate))
    return tuple(images)


def weight(x,y,side):
    k=((x-225)/132 if side=="right" else (1495-x)/165)
    return np.clip(k,0,1)*np.clip((y-480)/114,0,1)


def lower(arm,roi,dx,dy,side):
    if dx==dy==0:
        return arm
    y,x=np.indices(arm.shape[:2],np.float32)
    # Root the sleeve toward the shoulder, with a fully translating hand.
    f=weight(x+roi[0],y+roi[1]-dy*.55,side)
    return cv2.remap(arm,x-dx*f,y-dy*f,cv2.INTER_LINEAR)


def register_arm(start,end,roi,outline0,outline1,pairs,drop,side,remove0):
    region=reg.region(start,end,roi,pairs,outline0)
    a0=layer.cel.refine(region.start,matte(outline0,roi,0))*(1-remove0)
    a1=layer.cel.refine(region.end,matte(outline1,roi,0))
    initial=layer.cel.rgba(region.start,a0)
    lowered=lower(initial,roi,0,drop,side)
    from_lower=[((x,y+drop*float(weight(x,y,side))),b) for (x,y),b in pairs]
    points=[((int(round(a[0])),int(round(a[1]))),b) for a,b in from_lower]
    movement=reg.region(start,end,roi,points,outline1)
    # Here only the premultiplied arm surfaces morph, never the props or porch.
    motion=layer.Arm(movement,(lowered,layer.cel.rgba(region.end,a1)),
                        (layer.cel.signed_distance(lowered[...,3]),layer.cel.signed_distance(a1)))
    return initial,motion,a0,a1


@dataclass
class Stage:
    still: np.ndarray
    table: np.ndarray
    mug: np.ndarray
    pie: np.ndarray
    right: np.ndarray
    left: np.ndarray
    right_release: layer.Arm
    left_release: layer.Arm
    eyes: reg.Region
    x: np.ndarray
    y: np.ndarray


def prepare():
    cv2.setNumThreads(1)
    first,last=load()
    m=np.maximum(matte(MUG_BODY,MUG),matte(MUG_LOOP,MUG))
    p=layer.cel.refine(last[reg.window(PIE)],matte(PIE_OUT,PIE,0))
    mug=layer.cel.rgba(last[reg.window(MUG)],m)
    pie=layer.cel.rgba(last[reg.window(PIE)],p)
    stationary=np.zeros((H,W),np.float32)
    stationary[reg.window(MUG)]=m
    stationary[reg.window(PIE)]=np.maximum(stationary[reg.window(PIE)],p)
    start_m=np.zeros_like(stationary)
    start_p=np.zeros_like(stationary)
    start_m[reg.window(MUG)]=m
    start_p[reg.window(PIE)]=p
    start_m=layer.slide(start_m,0,-MUG_DROP)
    start_p=layer.slide(start_p,PIE_TRAVEL_X,-PIE_DROP)
    # Include only overlap with painted props from the original first key.
    # The projected matte clears visible cup/plate paint from the two arm cels.
    start_m=np.maximum(start_m,matte([(508,633),(550,627),(568,633),(569,756),(544,751),(523,728)],
                                    (0,0,W,H),1.))
    block_r=start_m[reg.window(R)].copy()
    protected_fingers=matte([(364,612),(423,584),(475,568),(528,579),(551,608),(555,620),
                              (525,635),(527,654),(546,681),(527,700),(522,739),(501,776),
                              (452,786),(395,768),(367,725)],R,1.4)
    block_r*=1-protected_fingers
    block_l=start_p[reg.window(L)].copy()
    thumb=matte([(1274,673),(1299,671),(1314,691),(1318,716),(1301,740),(1276,731),
                (1261,718),(1260,697)],L,.95)
    block_l*=1-thumb
    r,rm,r0,r1=register_arm(first,last,R,R0,R1,RIGHT_PAIRS,MUG_DROP,"right",block_r)
    left,lm,l0,l1=register_arm(first,last,L,L0,L1,LEFT_PAIRS,57,"left",block_l)
    hidden=np.maximum(start_m,start_p)
    hidden[reg.window(R)]=np.maximum(hidden[reg.window(R)],r0)
    hidden[reg.window(L)]=np.maximum(hidden[reg.window(L)],l0)
    hidden=np.maximum(hidden,matte([(561,834),(618,824),(740,828),(793,848),(785,871),
                                    (607,880),(569,868)],(0,0,W,H),4.))
    stationary[reg.window(R)]=np.maximum(stationary[reg.window(R)],r1)
    stationary[reg.window(L)]=np.maximum(stationary[reg.window(L)],l1)
    fg=cv2.dilate((hidden>.05).astype(np.uint8),np.ones((15,15),np.uint8)).astype(bool)
    no_donor=cv2.dilate((stationary>.08).astype(np.uint8),np.ones((7,7),np.uint8)).astype(bool)
    bg=first.copy()
    bg[fg & ~no_donor]=last[fg & ~no_donor]
    bg=cv2.inpaint(bg,(fg & no_donor).astype(np.uint8),7,cv2.INPAINT_TELEA)
    eyes=reg.region(first,last,E,EYE_PAIRS,[(841,208),(864,177),(898,171),(970,181),
                                           (1037,199),(1079,239),(1075,278),(1048,286),
                                           (974,281),(944,252),(875,245)])
    y,x=np.indices((H,W),np.float32)
    return Stage(first,bg.astype(np.float32),mug,pie,r,left,rm,lm,eyes,x,y)


def prop(bg,cel,roi,dx,dy):
    # Room above and to the right for the original held registration.
    work=(roi[0],roi[1]-127,min(W,roi[2]+23),roi[3])
    x,y,r,b=work
    inset=np.zeros((b-y,r-x,4),np.float32)
    inset[127:, :cel.shape[1]]=cel
    z=reg.window(work)
    bg[z]=layer.cel.over(bg[z],layer.slide(inset,dx,dy))


def paint(p,i):
    t=cues(i)
    mug_y=-MUG_DROP*(1-t.mug_progress)
    pie_y=-PIE_DROP*(1-t.pie_progress)
    pie_x=PIE_TRAVEL_X*(1-t.pie_progress)
    mug_shade=np.clip(1-((p.x-655)/140)**2-((p.y-878)/14)**2,0,1)**2
    pie_shade=np.clip(1-((p.x-1101-pie_x)/203)**2-((p.y-885)/16)**2,0,1)**2
    bg=p.table*(1-((.27+.20*t.mug_progress)*mug_shade+
                 (.12+.38*t.pie_progress)*pie_shade)[...,None])
    if t.glance:
        reg.apply_region(bg,p.eyes.end if t.glance==1 else reg.paint_pair(p.eyes,t.glance)[0],p.eyes)
    prop(bg,p.mug,MUG,0,mug_y)
    prop(bg,p.pie,PIE,pie_x,pie_y)
    right=layer.arm_frame(p.right_release,t.right_release) if t.right_release else lower(
        p.right,R,0,MUG_DROP*t.mug_progress,"right")
    left=layer.arm_frame(p.left_release,t.left_release) if t.left_release else lower(
        p.left,L,0,min(57,PIE_DROP*t.pie_progress),"left")
    for roi,arm in ((R,right),(L,left)):
        zone=reg.window(roi)
        bg[zone]=layer.cel.over(bg[zone],arm)
    return np.clip(np.rint(bg),0,255).astype(np.uint8)


def sheet(prepared,path):
    board=Image.new("RGB",(1152,233*((len(SAMPLES)+2)//3)),"#180f0a")
    draw=ImageDraw.Draw(board)
    for n,i in enumerate(SAMPLES):
        x,y=(n%3)*384,(n//3)*233
        with Image.fromarray(paint(prepared,i)) as frame:
            board.paste(frame.resize((384,216),Image.Resampling.LANCZOS),(x,y))
        t=cues(i)
        draw.text((x+5,y+216),f"F{i+225} mug {t.mug_progress:.2f} pie {t.pie_progress:.2f} eyes {t.glance:.2f}",fill="white")
    board.save(path,quality=94)


def build(output,poses=False):
    output.mkdir(parents=True,exist_ok=False)
    p=prepare()
    sheet(p,output/"visitor-poses.jpg")
    if poses:
        return {}
    movie=output/"visitor-return.mp4"
    with (output/"encode.log").open("wb") as log,subprocess.Popen(
        media.encoder_command("ffmpeg",movie),stdin=subprocess.PIPE,stderr=log) as proc:
        try:
            raw={}
            for i in range(N):
                a=paint(p,i)
                raw[i]=sha256(a).hexdigest()
                with Image.fromarray(a) as image:
                    proc.stdin.write(image.resize((1920,1080),Image.Resampling.LANCZOS).tobytes())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("visitor scene encode failed")
    video,=media._probe(movie,"ffprobe")["streams"]
    if (video["width"],video["height"],video["avg_frame_rate"],int(video["nb_read_frames"]))!=(1920,1080,"30/1",N):
        raise ValueError("visitor source shot clock changed")
    report={"clock":[1920,1080,30,N],"source_span":SPAN,"source_art":ART,
            "source_builder_sha256":reg.cut.beat.digest(Path(__file__)),
            "movie_sha256":reg.cut.beat.digest(movie),"native_rgb24_sha256":raw,
            "global_event_frames":{"mug_settles":291,"mug_release_done":309,
                                   "pie_settles":344,"left_release_done":360,"looks_to_june":380},
            "no_audio_in_study":True,"integrated":False,"human_accepted":False,"production_release":False}
    media._json(output/"visitor-return-proof.json",report)
    return report


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--poses-only",action="store_true")
    args=ap.parse_args()
    print(json.dumps({k:v for k,v in build(args.output,args.poses_only).items()
                      if k!="native_rgb24_sha256"},indent=2))
