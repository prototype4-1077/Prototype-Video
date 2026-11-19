"""GS060 arithmetic for one pencil, one parked pot, and a visible right-hand reach."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from pipeline import cartoon_grounded_coffee as lift

reg=lift.register
exchange=lift.exchange
PARK="june-gs060-right-grip-parked-v1.png"
POISED="june-gs060-right-grip-pencil-v1.png"
PARK_SHA="2f382db055e116f79264f652e5aede810062648e1ff4a74a864e2ecc135ca8e9"
POISED_SHA="1f8120ebd02c2ad884011d7440caec7d8b6370c485f7adab5cff759b6a3ece69"
ARM_ROI=(139,355,757,879)
PEN_ROI=(294,615,666,878)
REST_ARM=[(282,455),(237,508),(196,572),(166,637),(167,681),(188,713),(227,745),
          (275,770),(324,785),(349,805),(375,812),(392,794),(425,797),(455,806),
          (485,812),(521,825),(540,819),(558,827),(575,825),(589,822),(605,821),
          (615,806),(606,788),(588,765),(566,750),(528,735),(480,723),(445,719),
          (430,702),(384,685),(335,655),(316,627),(320,576),(355,494),(358,453)]
GRIP_ARM=[(310,416),(264,475),(231,548),(208,621),(207,682),(219,722),(248,758),
          (293,782),(355,795),(454,794),(529,793),(568,785),(631,785),(674,786),
          (690,774),(701,767),(709,751),(718,730),(722,711),(730,689),(728,672),
          (718,661),(708,651),(724,647),(731,633),(730,623),(718,617),(687,625),
          (677,618),(640,628),(590,647),(548,657),(501,657),(456,643),(404,621),
          (382,604),(403,540),(412,493),(411,446),(402,409)]
REACH=[
    ((292,467),(311,423)), ((349,454),(403,413)),
    ((225,528),(263,482)), ((173,650),(209,649)), ((207,717),(242,751)),
    ((242,654),(280,636)), ((317,672),(377,644)), ((324,763),(437,775)),
    ((370,703),(517,657)), ((391,795),(537,786)),
    ((424,715),(567,667)), ((388,787),(552,767)),
    ((472,721),(623,640)), ((490,730),(661,629)), ((602,801),(724,629)),
    ((599,809),(727,680)), ((583,818),(719,710)), ((561,821),(709,745)),
    ((521,817),(676,780)), ((478,807),(612,773)),
    ((744,779),(744,779)), ((733,838),(733,838)), ((534,846),(534,846)),
    ((158,598),(158,598)), ((158,764),(158,764)),
]
# The two visible sections of the held pencil, and the whole parked pencil.
HELD_PEN=[[(426,658),(440,647),(452,649),(499,697),(497,707),(482,707)],
          [(545,773),(555,773),(585,809),(594,829),(588,837),(568,817),(540,792)]]
REST_PEN=[(404,833),(415,825),(439,824),(545,829),(590,831),(625,843),(621,855),
          (593,852),(469,849),(414,848)]
PEN_FINGERS=[(448,701),(479,698),(505,707),(529,725),(553,754),(564,773),
             (552,791),(547,808),(523,816),(494,827),(450,828),(427,809),(422,765)]
PEN_MAP=[
    ((354,717),(357,708)), ((345,800),(347,785)), ((387,728),(397,720)),
    ((386,791),(394,782)), ((449,703),(462,728)), ((486,702),(505,730)),
    ((513,723),(555,744)), ((548,754),(596,775)), ((557,779),(611,803)),
    ((547,801),(589,823)), ((524,815),(559,824)), ((493,825),(526,820)),
    ((458,828),(479,805)), ((420,804),(427,789)), ((392,772),(393,762)),
    ((608,851),(608,851)), ((600,820),(610,830)),
    ((632,734),(632,734)), ((440,855),(440,855)),
]


def blend(t):
    t=max(0.,min(1.,t))
    return t*t*(3-2*t)


def timing(i):
    """Global zero-based frame to stage/fraction on the unchanged story clock."""
    if type(i) is not int or not 678<=i<912:
        raise ValueError("outside GS060 in the 38-second cut")
    if i<=721:
        return "pencil",blend((i-702)/19)
    if i<=738:
        return "reach",blend((i-723)/15)
    if i<=761:
        return "lift",blend((i-740)/21)
    if i<882:
        return "original",0.
    if i<901:
        return "lift",1-blend((i-882)/18)
    return "reach",1-blend((i-901)/10)


def load(name,digest):
    path=lift.ART/name
    if reg.cut.beat.digest(path)!=digest:
        raise ValueError(f"restaged park art changed: {name}")
    with Image.open(path) as a:
        if a.mode!="RGB" or a.height!=941 or a.width not in (1670,1671):
            raise ValueError("unexpected restaged art geometry")
        return np.array(a.resize((1672,941),Image.Resampling.BICUBIC))


def matte(coords,roi,blur=0):
    x,y,r,b=roi
    return reg.matte(coords,(x,y),(r-x,b-y),blur)


@dataclass
class Acting:
    lift: lift.Prepared
    ground: np.ndarray
    park: np.ndarray
    poise: np.ndarray
    reach: reg.Region
    arm_cels: tuple
    arm_distances: tuple
    arm_underlay: np.ndarray
    pen: reg.Region
    pen_cel: np.ndarray
    fingers: np.ndarray


def prepare():
    p=lift.prepare()
    ground=lift.frame(p,0.)
    rest,held=load(PARK,PARK_SHA),load(POISED,POISED_SHA)
    win=reg.window(ARM_ROI)
    r=reg.region(rest,ground,ARM_ROI,REACH,REST_ARM)
    a0=exchange.refine(r.start,matte(REST_ARM,ARM_ROI))
    a1=exchange.refine(r.end,matte(GRIP_ARM,ARM_ROI))
    # One pot, one unchanged mug. In the shared area the open plate is
    # the only view of the complete C-loop, which is fixed in this step.
    pot=matte([(732,600),(756,600),(756,878),(718,878),(727,815),
               (719,778),(724,731),(735,691),(745,665)],ARM_ROI,1.)
    a0*=1-pot
    a1*=1-pot
    stationary=r.start.copy()
    occluded=cv2.dilate((a0>.05).astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)
    other=cv2.dilate((a1>.03).astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)
    stationary[occluded & ~other]=r.end[occluded & ~other]
    stationary=cv2.inpaint(stationary,(occluded & other).astype(np.uint8),4,cv2.INPAINT_TELEA)
    park=ground.copy()
    # Localize the generative edit; head, left hand, table and shot remain
    # the same actual painting. Allow the open right elbow beyond the old ROI.
    arm_plate=matte([(153,489),(238,403),(353,389),(437,433),(534,579),(719,602),
                    (747,632),(752,814),(744,857),(670,858),(373,835),(159,810),
                    (143,730),(141,548)],ARM_ROI,5)[...,None]
    park[win]=np.rint((1-arm_plate)*ground[win]+arm_plate*rest[win]).astype(np.uint8)
    pen_win=reg.window(PEN_ROI)
    pen_support=[(303,637),(427,628),(473,629),(540,676),(594,716),(650,785),
                 (639,845),(601,863),(377,867),(301,849)]
    pen=reg.region(held,park,PEN_ROI,PEN_MAP,pen_support)
    poise=park.copy()
    reg.apply_region(poise,pen.start,pen)
    pen_alpha=matte(REST_PEN,PEN_ROI,.45)
    pen_cel=exchange.rgba(pen.end,pen_alpha)
    pen.end=cv2.inpaint(pen.end,(pen_alpha>.25).astype(np.uint8),4,cv2.INPAINT_TELEA)
    held_pen=np.maximum.reduce([matte(poly,PEN_ROI) for poly in HELD_PEN])
    pen.start=cv2.inpaint(pen.start,(held_pen>.2).astype(np.uint8),4,cv2.INPAINT_TELEA)
    fingers=matte(PEN_FINGERS,PEN_ROI,.6)
    return Acting(p,ground,park,poise,r,(exchange.rgba(r.start,a0),exchange.rgba(r.end,a1)),
                  (exchange.signed_distance(a0),exchange.signed_distance(a1)),stationary,pen,pen_cel,fingers)


def moving_arm(p,t):
    if t==0:
        return p.park
    if t==1:
        return p.ground
    maps=p.reach.maps(t)
    c0,c1=(cv2.remap(c,*m,cv2.INTER_LINEAR) for c,m in zip(p.arm_cels,maps))
    d0,d1=(cv2.remap(a,*m,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=-32)
           for a,m in zip(p.arm_distances,maps))
    alpha=np.clip((1-t)*d0+t*d1+.5,0,1)[...,None]
    w0=(1-blend(t))*np.clip((d0+2)/7,.08,1)[...,None]
    w1=blend(t)*np.clip((d1+2)/7,.08,1)[...,None]
    rgb=(w0*c0[...,:3]+w1*c1[...,:3])/np.maximum(.01,w0*c0[...,3:]+w1*c1[...,3:])
    data=exchange.over(p.arm_underlay,np.dstack((rgb*alpha,alpha)))
    win=reg.window(ARM_ROI)
    # Restrict compositing to a union of active occlusion and the interior
    # of the wrist paths. No color fade across the full frame.
    moving=cv2.GaussianBlur(cv2.dilate(
        np.maximum.reduce([p.arm_cels[0][...,3],p.arm_cels[1][...,3],alpha[...,0]]),
        np.ones((17,17),np.uint8)),(0,0),5)[...,None]
    landing=blend((t-.84)/.16)
    fixed=p.park[win]*(1-landing)+p.ground[win]*landing
    frac=1-blend(min(t,1-t)*12)
    data=(data*(1-frac)+fixed*frac)*moving+fixed*(1-moving)
    output=p.park.copy()
    output[win]=np.rint(np.clip(data,0,255)).astype(np.uint8)
    return output


def pen_pose(p,t):
    if t==0:
        return p.poise
    if t==1:
        return p.park
    paint,left,_=reg.paint_pair(p.pen,t)
    origin=np.array(PEN_ROI[:2],np.float32)
    eraser0,tip0=np.float32([[413,834],[619,847]])-origin
    eraser1,tip1=np.float32([[439,655],[592,830]])-origin
    tip=(1-t)*tip1+t*tip0
    angle=(1-t)*np.arctan2(*(tip1-eraser1)[::-1])+t*np.arctan2(*(tip0-eraser0)[::-1])
    length=(1-t)*np.linalg.norm(tip1-eraser1)+t*np.linalg.norm(tip0-eraser0)
    eraser=tip-length*np.array([np.cos(angle),np.sin(angle)],np.float32)
    def basis(a,b):
        v=b-a
        return np.float32([a,b,b+np.array([-v[1],v[0]])*.05])
    move=cv2.getAffineTransform(basis(eraser0,tip0),basis(eraser,tip))
    h,w=paint.shape[:2]
    cel=cv2.warpAffine(p.pen_cel,move,(w,h),flags=cv2.INTER_LINEAR)
    occlusion=cv2.remap(p.fingers,*left,cv2.INTER_LINEAR)
    cel*=1-occlusion[...,None]*(1-blend((t-.60)/.37))
    patch=exchange.over(paint,cel)
    art=p.park.copy()
    reg.apply_region(art,np.rint(np.clip(patch,0,255)).astype(np.uint8),p.pen)
    return art


def raw_frame(p,stage,t):
    if stage=="pencil":
        return pen_pose(p,t)
    if stage=="reach":
        return moving_arm(p,t)
    if stage=="lift":
        return lift.frame(p.lift,t)
    raise ValueError(f"unknown restaged action {stage}")
