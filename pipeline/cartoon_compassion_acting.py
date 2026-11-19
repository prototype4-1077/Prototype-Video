"""GS050: eyes notice first, then the pencil hand eases. Source art stays immutable."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_full_short as cut
from pipeline import cartoon_golden_master as golden
from pipeline import cartoon_full_short_source as sources
from pipeline.cartoon_shot_sequence import _ease_in_out_cubic


SPAN = (564, 678)  # zero-based; only one existing shot
ASSETS = {
    "start": ("gs050-performance-start", "1d88794a72bc0e2e1531e5f39c09fc6552df37804c202f114696b4cb6a4ec6d1"),
    "end": ("gs050-performance-end", "a9082eeb9b8eba5aea8ec15790425f2893aee6325d57c4c6e965e93c4e2b2ce3"),
    "prop": ("gs060-performance-pencil-down", "acc7d53a4c656429e67566e4803398519397da81b6ee400efff851b254630907"),
}

# Register anatomy (not thumbnail position) on each 1672x941 source painting.
# Within each ROI the shape follows a single set of intermediate landmarks.
HEAD_ROI = (341, 13, 774, 558)
HAND_ROI = (638, 710, 943, 941)
HEAD_POINTS = (
    ((526,38),(546,41)),((608,46),(620,50)),((718,153),(735,152)),
    ((410,129),(426,128)),((400,194),(414,188)),((389,252),(402,247)),
    ((423,335),(433,333)),((454,343),(459,343)),((445,378),(448,383)),
    ((487,464),(486,466)),((536,501),(539,509)),((591,520),(591,534)),
    ((631,511),(635,522)),((658,449),(656,455)),((678,367),(682,388)),
    ((706,285),(711,320)),((708,229),(720,256)),
    ((529,211),(546,240)),((582,198),(595,231)),((627,200),(645,236)),
    ((669,215),(682,248)),((707,231),(721,273)),
    ((543,253),(553,278)),((576,239),(580,275)),((597,246),(601,285)),
    ((580,255),(584,289)),((574,269),(579,299)),((600,266),(604,299)),
    ((650,266),(652,300)),((674,261),(679,298)),((691,272),(696,311)),
    ((671,275),(674,311)),((669,291),(671,324)),
    ((621,276),(628,303)),((627,328),(633,352)),((632,368),(632,387)),
    ((585,347),(584,365)),((598,370),(602,392)),((519,365),(523,384)),
    ((555,387),(550,403)),((601,401),(599,418)),((626,409),(630,432)),
    ((650,400),(651,420)),((575,417),(573,438))
)
HAND_POINTS = (
    ((676,848),(676,849)),((715,805),(724,802)),((787,783),(781,779)),
    ((835,799),(835,797)),((868,823),(873,823)),((882,849),(890,848)),
    ((896,899),(907,902)),((867,939),(887,939)),((701,910),(727,923)),
    ((700,881),(706,887)),((738,874),(762,878)),((736,926),(778,930)),
    ((777,901),(802,907)),((800,917),(825,924)),((837,883),(858,892)),
    ((855,858),(872,872)),((765,832),(784,836)),((814,820),(819,820)),
    ((804,771),(805,770)),((843,772),(841,771)),((890,825),(892,827)),
)
HEAD_SUPPORT = [(357,141),(380,92),(444,36),(530,15),(644,17),(735,60),
                (760,137),(765,226),(735,368),(692,457),(650,531),
                (591,551),(477,526),(425,472),(409,399),(372,346),(350,250)]
HAND_SUPPORT = [(642,803),(696,763),(746,731),(800,731),(872,750),(908,791),
                (929,845),(933,917),(928,940),(639,940)]
A_SHAFT = [(672,940),(707,940),(743,869),(756,830),(792,762),(789,745),
           (773,743),(761,761),(729,818),(710,856)]
B_SHAFT = [(717,918),(744,907),(794,874),(786,851),(741,871),(725,890)]
PROP_POLY = [(417,824),(451,824),(596,832),(624,841),(624,845),(594,850),
             (445,844),(418,842)]
START_FINGERS = [
    [(677,821),(710,808),(727,811),(729,838),(724,869),(714,897),(705,912),(690,910),(677,880)],
    [(753,814),(790,785),(840,796),(882,835),(897,897),(866,940),(715,940),(743,882)],
]
END_FINGERS = [
    [(678,828),(704,811),(730,818),(746,837),(751,862),(738,885),(726,900),(728,921),(713,929),(695,908),(680,881)],
    [(763,810),(782,777),(827,790),(884,823),(906,903),(887,940),(761,940),(779,896),(789,861)],
    # The far end swings under the cuff after the hand unclenches.
    [(813,756),(846,746),(894,766),(924,801),(928,864),(877,844),(841,805)],
]


def matte(points, origin, size, blur=0):
    x,y=origin
    w,h=size
    result=np.zeros((h,w),np.uint8)
    cv2.fillPoly(result,[np.array(points,np.int32)-(x,y)],255,lineType=cv2.LINE_AA)
    if blur:
        result=cv2.GaussianBlur(result,(0,0),blur,borderType=cv2.BORDER_REPLICATE)
    return result.astype(np.float32)/255


def window(roi):
    x,y,r,b=roi
    return np.s_[y:b,x:r]


def ease(i,a,b):
    return _ease_in_out_cubic((i-a)/(b-a))


def cues(i):
    """Read/recognize the discomfort; then let go of the impulse to write."""
    if type(i) is not int or not 0<=i<114:
        raise ValueError("GS050 frame outside existing shot")
    return ease(i,31,54),ease(i,57,82)


def thinplate(r2):
    return r2*np.log(np.maximum(r2,1e-8))


@dataclass
class Region:
    roi: tuple[int,int,int,int]
    start: np.ndarray
    end: np.ndarray
    support: np.ndarray
    src: np.ndarray
    dst: np.ndarray
    x: np.ndarray
    y: np.ndarray
    coarse: np.ndarray

    def maps(self,t):
        # Bidirectional inverse maps evaluated on a 4 px lattice. When the
        # landmarks agree, both paintings describe the same single contour.
        nodes=(1-t)*self.src+t*self.dst
        n=len(nodes)
        poly=np.column_stack((np.ones(n),nodes))
        radial=thinplate(np.sum((nodes[:,None]-nodes[None,:])**2,axis=-1))
        w=np.linalg.solve(np.block([[radial+np.eye(n)*.00016,poly],[poly.T,np.zeros((3,3))]]),
                          np.vstack((np.column_stack((self.src-nodes,self.dst-nodes)),np.zeros((3,4)))))
        basis=thinplate(np.sum((self.coarse[...,None,:]-nodes)**2,axis=-1))
        displacement=(basis@w[:n]+np.dstack((np.ones(self.coarse.shape[:2]),self.coarse))@w[n:])*450
        dense=cv2.remap(displacement.astype(np.float32),self.x/4,self.y/4,cv2.INTER_LINEAR)
        return (self.x+dense[...,0],self.y+dense[...,1]),(self.x+dense[...,2],self.y+dense[...,3])


def region(a,b,roi,points,support):
    x,y,r,bottom=roi
    w,h=r-x,bottom-y
    anchor=[((x+u,y+v),(x+u,y+v)) for u,v in (
        (0,0),(w//2,0),(w-1,0),(0,h//2),(w-1,h//2),(0,h-1),(w//2,h-1),(w-1,h-1))]
    src,dst=(np.asarray([*points,*anchor],np.float64).transpose(1,0,2)-(x,y))/450
    gy,gx=np.mgrid[0:h+4:4,0:w+4:4]
    j,i=np.indices((h,w),np.float32)
    return Region(roi,a[window(roi)].copy(),b[window(roi)].copy(),matte(support,(x,y),(w,h),8),
                  src,dst,i,j,np.dstack((gx,gy))/450)


def remap(image,xy):
    return cv2.remap(image,*xy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)


def paint_pair(area,t):
    a,b=area.maps(t)
    left,right=remap(area.start,a),remap(area.end,b)
    texture_mix=_ease_in_out_cubic(t)
    return cv2.addWeighted(left,1-texture_mix,right,texture_mix,0),a,b


def load_art():
    result={}
    for name,(stem,digest) in ASSETS.items():
        path=sources.ROOT/f"concept/style_frames/june-golden-scene-{stem}-v1.png"
        if cut.beat.digest(path)!=digest:
            raise ValueError(f"changed acting reference {stem}")
        with Image.open(path) as image:
            if image.mode!="RGB" or image.size!=(1672,941):
                raise ValueError("invalid reference picture")
            result[name]=np.array(image)
    return result


def skin(polys):
    x,y,r,b=HAND_ROI
    return np.maximum.reduce([matte(poly,(x,y),(r-x,b-y),.7) for poly in polys])


def clean_pencil(paint,polygon):
    x,y,r,b=HAND_ROI
    alpha=matte(polygon,(x,y),(r-x,b-y))
    # This is a temporary occlusion fill in the renderer, not a source art edit.
    # Only the shaft's swept area is replaced; the single painted shaft goes back above it.
    return cv2.inpaint(paint,(alpha>.15).astype(np.uint8),3,cv2.INPAINT_TELEA)


@dataclass
class Prepared:
    start: np.ndarray
    head: Region
    hand: Region
    fingers: tuple[np.ndarray,np.ndarray]
    hand_keys: tuple[np.ndarray,np.ndarray]
    prop_cel: np.ndarray
    segments: list


def prepare():
    art=load_art()
    head=region(art["start"],art["end"],HEAD_ROI,HEAD_POINTS,HEAD_SUPPORT)
    hand=region(art["start"],art["end"],HAND_ROI,HAND_POINTS,HAND_SUPPORT)
    keys=(hand.start,hand.end)
    hand.end=clean_pencil(hand.end,B_SHAFT)
    # The original erased shaft crosses the sleeve and lit knuckles. Fill its
    # swept patch with actual key-B cloth/skin registered back to key A, rather
    # than stretching a synthesized dark line between the two fingertips.
    _,from_end=hand.maps(0)
    x,y,r,b=HAND_ROI
    donor=remap(hand.end,from_end)
    fill=matte(A_SHAFT,(x,y),(r-x,b-y),1.4)[...,None]
    hand.start=np.rint(hand.start*(1-fill)+donor*fill).astype(np.uint8)
    cel=art["prop"][819:853,411:629].astype(np.float32)
    alpha=matte(PROP_POLY,(411,819),(218,34),.55)
    prop=np.dstack((cel*alpha[...,None],alpha))
    master,_=golden.load_master_contract(sources.ROOT/sources.MASTER)
    shot=next(s for s in master["shots"] if s["id"]=="GS050")
    cv2.setNumThreads(1)
    return Prepared(art["start"],head,hand,(skin(START_FINGERS),skin(END_FINGERS)),keys,prop,shot["segments"])


def pencil(p,t):
    # One rigid painted prop, pivoted from the graphite tip toward the eraser.
    x,y,r,b=HAND_ROI
    tip=np.array([693+38*t,947-46*t],np.float32)-(x,y)
    angle=np.radians(-64+36*t)
    direction=np.array([np.cos(angle),np.sin(angle)])
    # Source points are eraser, graphite and a perpendicular control.
    src=np.float32([[6,14],[213,23],[213,33]])
    eraser=tip+np.hypot(207,9)*direction
    angle_change=np.arctan2((tip-eraser)[1],(tip-eraser)[0])-np.arctan2(9,207)
    c,s=np.cos(angle_change),np.sin(angle_change)
    rotation=np.array([[c,-s],[s,c]],np.float32)
    transform=np.column_stack((rotation,tip-rotation@src[1]))
    return cv2.warpAffine(p.prop_cel,transform,(r-x,b-y),flags=cv2.INTER_LINEAR)


def apply_region(image,paint,area):
    zone=image[window(area.roi)]
    zone[:] = np.rint(zone*(1-area.support[...,None])+paint*area.support[...,None]).astype(np.uint8)


def plate(p,i):
    eye,hand=cues(i)
    image=p.start.copy()
    if eye:
        apply_region(image,p.head.end if eye==1 else paint_pair(p.head,eye)[0],p.head)
    if hand:
        if hand==1:
            patch=p.hand_keys[1]
        else:
            patch,a,b=paint_pair(p.hand,hand)
            d1,d2=remap(p.fingers[0],a),remap(p.fingers[1],b)
            hands=np.clip(((1-hand)*d1+hand*d2-.34)*5,0,1)
            cel=pencil(p,hand)*(1-hands[...,None])
            patch=np.rint(np.clip(cel[...,:3]+patch*(1-cel[...,3:]),0,255)).astype(np.uint8)
        apply_region(image,patch,p.hand)
    return image


def output_frame(p,i):
    # Preserve the original moment, camera and illumination clock exactly.
    original_one_based=SPAN[0]+1+i
    seg=golden.segment_for_frame(p.segments,original_one_based)
    with Image.fromarray(plate(p,i)) as image:
        return golden.compose_plate_frame(image,seg,original_one_based)


def inspect(output: Path):
    """Render a few intermediate poses before spending time on video."""
    p=prepare()
    numbers=(0,37,43,49,56,63,68,73,78,82)
    sheet=Image.new("RGB",(1080,5*248),"#16100b")
    draw=ImageDraw.Draw(sheet)
    for i,frame in enumerate(numbers):
        a=Image.fromarray(plate(p,frame))
        x,y=(i%2)*540,(i//2)*248
        sheet.paste(a.crop((363,142,754,534)).resize((223,223)),(x,y))
        sheet.paste(a.crop(HAND_ROI).resize((306,223)),(x+228,y))
        draw.text((x+8,y+225),f"F{frame} eyes {cues(frame)[0]:.2f}, hand {cues(frame)[1]:.2f}",fill="white")
    output.mkdir(parents=True,exist_ok=False)
    sheet.save(output/"acting-poses.jpg",quality=95)
