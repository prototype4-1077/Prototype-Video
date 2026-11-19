"""Reach and release around the byte-pinned GS070 mug lift."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_mug_action as lift

W, H, FPS = lift.W, lift.H, lift.FPS
RECIPE = lift.ROOT / "concept/scenes/june-gs070-left-handle-v3.json"
V2 = lift.ROOT / "collab/june_left_handle_v2/source-frames.json"
COUNT = 147
LIFT_IN, LIFT_OUT, V2_IN = 35, 101, 4
SAMPLES = (0, 11, 17, 21, 25, 30, 35, 54, 67, 97, 103, 108, 111, 116, 121, 146)
HALF = np.s_[0:347, 0:633]

# Two traced, same-handed drawings. Mug/body paint is not part of either cel.
OPEN_ARM = [(0,0),(33,0),(62,30),(90,45),(108,68),(133,66),(170,50),(207,53),
    (247,42),(291,28),(334,26),(372,13),(404,9),(420,12),(430,19),(451,21),
    (492,27),(527,40),(548,53),(565,71),(577,96),(586,113),(599,134),(600,149),
    (595,168),(590,187),(580,208),(564,230),(547,250),(532,269),(522,275),
    (513,272),(509,262),(513,249),(508,245),(503,238),(504,227),(512,215),
    (527,198),(531,180),(517,190),(506,202),(497,204),(489,199),(487,192),
    (493,180),(502,167),(517,148),(500,149),(481,140),(460,128),(456,116),
    (451,134),(440,148),(424,152),(412,146),(409,139),(412,128),(410,120),
    (392,126),(373,138),(220,137),(167,172),(157,227),(132,218),(96,209),
    (55,194),(25,199),(0,202)]
CLOSED_ARM = [(0,0),(35,4),(77,43),(101,95),(133,114),(181,121),(217,111),
    (260,112),(315,109),(362,108),(398,111),(426,115),(457,115),(479,123),
    (503,132),(520,150),(534,166),(544,177),(542,192),(551,211),(554,224),
    (545,240),(541,258),(535,276),(523,287),(505,304),(486,321),(465,328),
    (443,330),(435,325),(432,313),(423,305),(411,302),(404,289),(402,259),
    (402,206),(413,192),(444,187),(428,176),(405,176),(376,158),(222,142),
    (162,174),(160,306),(145,303),(122,293),(97,271),(77,248),(42,229),(0,212)]
CUP_BODY = [(151,161),(161,148),(184,140),(222,135),(287,132),(346,136),
    (380,143),(400,151),(409,160),(407,174),(401,199),(402,343),(392,373),
    (367,391),(312,404),(249,406),(201,396),(171,380),(154,354),(151,185)]
HANDLE_OUT = [(399,176),(414,171),(441,172),(458,180),(470,194),(477,215),
    (478,239),(474,260),(462,283),(447,302),(423,319),(400,328),(399,308)]
HANDLE_HOLE = [(400,194),(415,189),(432,188),(445,194),(450,203),(456,220),
    (457,238),(453,257),(440,281),(424,297),(400,304)]
HANDLE_FRONT = [(400,303),(422,294),(440,274),(450,250),(451,232),(474,228),
    (477,249),(469,271),(456,290),(441,309),(422,321),(400,328)]
# Remove the glazed highlights from the animated cel, including the partially
# occluded upper root in the closed reference. They belong to the rigid loop.
CLOSED_ROOT = [(394,176),(414,171),(440,172),(450,178),(462,191),
               (448,194),(436,189),(414,193),(404,202),(397,192)]

# Paired joints, cuff and silhouette landmarks; cup silhouette handled separately.
# Correspondence is chosen by anatomy, not a whole-frame optical flow guess.
PAIRS = [
    ((0,0),(0,0)),((0,201),(0,212)),((0,347),(0,347)),
    ((80,40),(80,64)),((78,199),(78,251)),((152,64),(152,116)),
    ((175,166),(175,172)),((255,46),(255,111)),((264,130),(264,139)),
    ((325,31),(325,110)),((343,124),(357,151)),((376,34),(398,124)),
    ((376,112),(393,155)),((408,24),(427,118)),((436,33),(446,120)),
    ((489,36),(479,129)),((532,48),(503,137)),((559,78),(525,157)),
    ((583,119),(541,180)),((593,144),(542,205)),((590,181),(548,229)),
    ((577,211),(541,255)),((546,250),(513,297)),((522,269),(461,322)),
    ((514,249),(439,316)),((525,222),(451,284)),((546,190),(486,263)),
    ((504,194),(421,225)),((518,170),(443,211)),((534,137),(491,191)),
    ((480,117),(466,164)),((451,105),(447,144)),((424,141),(420,155)),
    ((416,115),(408,144)),((620,0),(620,0)),((625,335),(625,335)),
    ((388,340),(388,340)),((203,338),(203,338)),
]


def polygon(points):
    mask = np.zeros((H, W), np.uint8)
    cv2.fillPoly(mask, [np.array(points, np.int32)], 255, lineType=cv2.LINE_AA)
    return mask.astype(np.float32) / 255


def rgba(image, matte):
    return np.dstack((image.astype(np.float32) * matte[..., None], matte))


def over(bg, fg):
    return bg * (1 - fg[..., 3:]) + fg[..., :3]


def refine(image, outline):
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    rough = (outline >= .5).astype(np.uint8)
    band = np.where(cv2.dilate(rough,kernel), cv2.GC_PR_BGD, cv2.GC_BGD).astype(np.uint8)
    band[rough != 0] = cv2.GC_PR_FGD
    band[cv2.erode(rough,kernel) != 0] = cv2.GC_FGD
    cv2.setRNGSeed(93)
    cv2.grabCut(image, band, None, np.zeros((1,65)), np.zeros((1,65)), 3, cv2.GC_INIT_WITH_MASK)
    return cv2.GaussianBlur((band % 2).astype(np.float32), (3,3), .56)


@dataclass
class Prepared:
    lift_layers: lift.Layers
    ground: np.ndarray
    underlay: np.ndarray
    open_arm: np.ndarray
    closed_arm: np.ndarray
    body: np.ndarray
    loop_front: np.ndarray
    distances: tuple[np.ndarray, np.ndarray]
    transition_correction: np.ndarray | None = None


def signed_distance(alpha):
    inside = (alpha >= .5).astype(np.uint8)
    return cv2.distanceTransform(inside,cv2.DIST_L2,5) - cv2.distanceTransform(1-inside,cv2.DIST_L2,5)


def prepare():
    info = json.loads(RECIPE.read_text(encoding="utf-8"))
    art_path = lift.ROOT / info["source"]
    if sha256(art_path.read_bytes()).hexdigest() != info["sha256"]:
        raise ValueError("changed open-hand cel")
    with Image.open(art_path) as image:
        if image.mode != "RGB":
            raise ValueError("expected RGB open-hand cel")
        open_image = np.asarray(image.resize((W, H), Image.Resampling.LANCZOS))
    p = lift.prepare_action()
    ground = lift.render_frame(p, 0)
    cut = lift.TOP - lift.OVERSCAN
    _, yy = p.x+lift.LEFT, p.y+lift.OVERSCAN
    shadow = .46*np.exp(-.5*(((p.x+lift.LEFT-1158)/105)**2 + ((yy-878)/6)**2))
    clean = (p.backdrop * (1-shadow[..., None]))[cut:].copy()
    ground_map = p.y - lift.TRAVEL*p.sleeve_weight
    a = cv2.remap(p.alpha,p.x,ground_map,cv2.INTER_LINEAR)[cut:]
    col = cv2.remap(p.premult,p.x,ground_map,cv2.INTER_LINEAR)[cut:]
    cup = polygon(CUP_BODY)
    body = np.dstack((col * cup[..., None], a * cup))
    handle = polygon(HANDLE_OUT) * (1 - polygon(HANDLE_HOLE))
    outline = polygon(OPEN_ARM)
    unclosed = refine(open_image, outline) * (1-cup) * (1-handle)
    # The published ground cel supplies the closed hand and the exposed part
    # of the lower handle. The open painting supplies only the hidden arc.
    lower_loop = polygon(HANDLE_FRONT)
    low = handle * lower_loop
    grip_alpha = polygon(CLOSED_ARM) * (1 - cup) * (1 - low) * (1-polygon(CLOSED_ROOT)) * a
    result = Prepared(p,ground,over(clean,rgba(open_image,handle)),
                      rgba(open_image,unclosed)[HALF].copy(),
                      rgba(ground,grip_alpha)[HALF].copy(),body,
                      rgba(open_image,low),
                      (signed_distance(unclosed[HALF]),signed_distance(grip_alpha[HALF])))
    result.transition_correction = ground.astype(np.float32) - blend_pose(result,1)
    return result


def thin_plate(r2):
    return r2*np.log(np.maximum(r2,1e-8))


# Solve the two inverse maps on an economical lattice, then sample paint once.
_Y, _X = np.mgrid[0:349:4,0:637:4]
_Q = np.column_stack((_X.ravel(),_Y.ravel())).astype(np.float64)/400
_SRC, _DST = np.asarray(PAIRS,np.float64).transpose(1,0,2)/400


def maps(t):
    nodes = (1-t)*_SRC + t*_DST
    n = len(nodes)
    poly = np.column_stack((np.ones(n),nodes))
    radial = thin_plate(np.sum((nodes[:,None]-nodes[None,:])**2,axis=-1))
    system = np.block([[radial+np.eye(n)*.00019,poly],[poly.T,np.zeros((3,3))]])
    delta = np.column_stack((_SRC-nodes,_DST-nodes))
    weights = np.linalg.solve(system,np.vstack((delta,np.zeros((3,4)))))
    basis = thin_plate(np.sum((_Q[:,None]-nodes[None,:])**2,axis=-1))
    displacement = basis @ weights[:n] + np.column_stack((np.ones(len(_Q)),_Q)) @ weights[n:]
    displacement = (displacement*400).reshape((*_X.shape,4)).astype(np.float32)
    # Rescale the lattice with exact corner coordinates (not pixel-center scaling).
    y, x = np.mgrid[:347,:633].astype(np.float32)
    dense = cv2.remap(displacement,x/4,y/4,cv2.INTER_LINEAR)
    return x+dense[...,0], y+dense[...,1], x+dense[...,2], y+dense[...,3]


def blend_pose(p, t):
    if t == 0:
        arm = p.open_arm
    elif t == 1:
        arm = p.closed_arm
    else:
        ax,ay,bx,by = maps(t)
        start = cv2.remap(p.open_arm,ax,ay,cv2.INTER_LINEAR)
        stop = cv2.remap(p.closed_arm,bx,by,cv2.INTER_LINEAR)
        d0 = cv2.remap(p.distances[0],ax,ay,cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT,borderValue=-32)
        d1 = cv2.remap(p.distances[1],bx,by,cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT,borderValue=-32)
        # Only one contour is drawn. Blending the source alphas would show
        # translucent copies of fingertips wherever the cels do not overlap.
        alpha = np.clip((1-t)*d0+t*d1+.5,0,1)[...,None]
        # Mix only paint, never the underlying scene. Give the interior of a
        # well-supported cel priority over color from the edge of another.
        mix = lift._ease_in_out_cubic(t)
        a = (1-mix)*np.clip((d0+2)/7,.07,1)[...,None]
        b = mix*np.clip((d1+2)/7,.07,1)[...,None]
        color = (a*start[...,:3]+b*stop[...,:3])/np.maximum(.01,a*start[...,3:]+b*stop[...,3:])
        arm = np.concatenate((color*alpha,alpha),axis=2)
    canvas = p.underlay.copy()
    canvas[HALF] = over(canvas[HALF],arm)
    canvas = over(canvas,p.loop_front)
    return over(canvas,p.body)


def closure(i):
    if type(i) is not int or not 0 <= i < COUNT:
        raise ValueError("exchange frame out of bounds")
    if i < LIFT_IN:
        return lift._ease_in_out_cubic((i-6)/24)
    if i <= LIFT_OUT:
        return 1.0
    return 1-lift._ease_in_out_cubic((i-102)/15)


def render_frame(p, i):
    t = closure(i)
    if LIFT_IN <= i <= LIFT_OUT:
        return lift.render_frame(p.lift_layers,i-LIFT_IN+V2_IN)
    if t == 1:
        return p.ground.copy()
    raw = blend_pose(p,t)
    # Close the last paint differences locally, not by changing the whole shot.
    if t > .89:
        raw += p.transition_correction*lift._ease_in_out_cubic((t-.89)/.11)
    result = np.rint(np.clip(raw,0,255)).astype(np.uint8)
    # Keep the thick enamel below the rim exact, even when the thumb is nearest.
    result[184:369,177:395] = p.ground[184:369,177:395]
    return result


def audit_movie(movie, refs, output):
    probe = json.loads(subprocess.check_output([
        "ffprobe","-v","error","-show_streams","-show_frames",
        "-show_entries","stream=codec_name,width,height,pix_fmt,color_space,time_base,avg_frame_rate:frame=best_effort_timestamp",
        "-of","json",str(movie)]))
    expected = ("h264",W,H,"yuv420p","bt709","30/1")
    keys = ("codec_name","width","height","pix_fmt","color_space","avg_frame_rate")
    if len(probe["streams"]) != 1 or tuple(probe["streams"][0].get(k) for k in keys) != expected:
        raise ValueError("unexpected video format")
    tb = Fraction(probe["streams"][0]["time_base"])
    if [int(f["best_effort_timestamp"])*tb for f in probe["frames"]] != [Fraction(i,FPS) for i in range(COUNT)]:
        raise ValueError("frame timing mismatch")
    sheet = Image.new("RGB",(1280,4*202),"#171717")
    draw = ImageDraw.Draw(sheet)
    scores = []
    with subprocess.Popen(["ffmpeg","-v","error","-i",str(movie),"-f","rawvideo","-pix_fmt","rgb24","pipe:1"],
                          stdout=subprocess.PIPE) as proc:
        try:
            for i in range(COUNT):
                raw = proc.stdout.read(W*H*3)
                if len(raw) != W*H*3:
                    raise ValueError(f"incomplete frame {i}")
                if i not in refs:
                    continue
                image = np.frombuffer(raw,np.uint8).reshape(H,W,3)
                mse = np.mean((image.astype(np.float32)-refs[i])**2)
                scores.append(round(float(10*np.log10(255**2/max(float(mse),1e-12))),3))
                m = SAMPLES.index(i)
                x,y = (m%4)*320,(m//4)*202
                sheet.paste(Image.fromarray(image).resize((320,180), Image.Resampling.LANCZOS),(x,y))
                draw.text((x+8,y+181),f"F{i:03d}  {i/FPS:.2f}s",fill="white")
            if proc.stdout.read(1) or proc.wait():
                raise ValueError("decode failed or returned extra data")
        finally:
            proc.stdout.close()
    if min(scores) < 38:
        raise ValueError("sample picture PSNR is below 38 dB")
    sheet.save(output/"decoded-poses.jpg",quality=94)
    return scores


def build(output):
    if output.exists():
        raise FileExistsError(output)
    p = prepare()
    output.mkdir(parents=True, exist_ok=False)
    movie = output/"june-left-handle-exchange-v3.mp4"
    command = lift.encoder_command("ffmpeg",movie)
    command[command.index("-s")+1] = f"{W}x{H}"
    hashes, refs = [], {}
    upstream = json.loads(V2.read_text(encoding="utf-8"))["sha256_rgb24"]
    with (output/"encode.log").open("wb") as log, subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log) as proc:
        try:
            for i in range(COUNT):
                frame = render_frame(p,i)
                raw = frame.tobytes()
                digest = sha256(raw).hexdigest()
                if LIFT_IN <= i <= LIFT_OUT and digest != upstream[i-LIFT_IN+V2_IN]:
                    raise ValueError(f"v2 lift pixels changed at {i}")
                hashes.append(digest)
                if i in SAMPLES:
                    refs[i] = frame
                proc.stdin.write(raw)
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("encoder failed")
    lift.write_json(output/"source-frames.json",{"index_base":0,"sha256_rgb24":hashes})
    psnr = audit_movie(movie,refs,output)
    result = {"frames":COUNT,"seconds":COUNT/FPS,"source_sha256":sha256(Path(__file__).read_bytes()).hexdigest(),
              "movie_sha256":sha256(movie.read_bytes()).hexdigest(),"v2_exact_frames":LIFT_OUT-LIFT_IN+1,
              "sample_psnr_db":psnr,"human_accepted":False}
    lift.write_json(output/"verification.json",result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    print(json.dumps(build(parser.parse_args().output),indent=2))
