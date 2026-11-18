"""A pre-gripped, left-handed GS070 insert. Single cel, no mirrored hand or inter-pose fade."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline.cartoon_scene_review import encoder_command
from pipeline.cartoon_shot_sequence import _ease_in_out_cubic

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "concept/scenes/june-gs070-left-handle-v2.json"
COUNT, FPS, W, H = 84, 30, 800, 450
LEFT, TOP, OVERSCAN, TRAVEL = 872, 477, 410, 78
SAMPLES = (0, 12, 18, 23, 29, 35, 42, 48, 54, 60, 67, 83)

# Source-coordinate contour of the connected sleeve, mug and LEFT hand. Near the left
# edge the sleeve continues offscreen. Narrow edge refinement, not free segmentation.
CONTOUR = [(850,441),(882,464),(910,481),(937,491),(968,503),(1005,516),
           (1023,521),(1056,516),(1104,511),(1145,508),(1175,511),(1210,509),
           (1250,507),(1283,508),(1307,514),(1339,514),(1363,524),(1389,541),
           (1405,554),(1417,571),(1417,595),(1424,609),(1425,625),(1414,642),
           (1409,662),(1394,689),(1373,707),(1347,723),(1323,730),(1306,727),
           (1298,721),(1274,726),(1274,752),(1269,774),(1253,785),(1226,795),
           (1190,800),(1152,801),(1117,797),(1080,789),(1054,779),(1039,767),
           (1032,750),(1030,710),(997,707),(960,704),(920,699),(877,691),(850,689)]


def load_art():
    recipe = json.loads(RECIPE.read_text(encoding="utf-8"))
    if (recipe["frames"],recipe["fps"],recipe["travel_px"],recipe["crop_xyxy"]) != (
            COUNT, FPS, TRAVEL, [LEFT,TOP,LEFT+W,TOP+H]):
        raise ValueError("unexpected motion recipe")
    images = {}
    for name, spec in recipe["art"].items():
        path = ROOT / "concept/style_frames" / spec["file"]
        if sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError(f"{name} artwork changed")
        with Image.open(path) as img:
            if img.size != tuple(spec["size"]) or img.mode != "RGB":
                raise ValueError(f"{name} metadata changed")
            if img.size != (1672,941):
                img = img.resize((1672,941), Image.Resampling.LANCZOS)
            images[name] = np.array(img.crop((LEFT,OVERSCAN,LEFT+W,TOP+H)))
    return images


def elevation(i):
    if type(i) is not int or not 0 <= i < COUNT:
        raise ValueError("frame index out of bounds")
    if i <= 34:
        return _ease_in_out_cubic((i - 10) / 24)
    # The final few pixels ease onto wood, then settle in a longer grounded hold.
    return 1.0 - _ease_in_out_cubic((i - 43) / 24) if i < 67 else 0.0


@dataclass
class Layers:
    backdrop: np.ndarray
    premult: np.ndarray
    alpha: np.ndarray
    x: np.ndarray
    y: np.ndarray
    sleeve_weight: np.ndarray


def prepare_action():
    art = load_art()
    fg = art["raised"]
    h, w = fg.shape[:2]
    outline = np.zeros((h,w), np.uint8)
    cv2.fillPoly(outline, [np.int32(CONTOUR)-[LEFT,OVERSCAN]], 1)
    # Refine only the narrow uncertainty band; the posed finger/rim/chip interior
    # is never synthesized or allowed to vary. Fix RNG/threading before grabCut.
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21,21))
    band = np.where(cv2.dilate(outline,kern), cv2.GC_PR_BGD, cv2.GC_BGD).astype(np.uint8)
    band[outline>0] = cv2.GC_PR_FGD
    band[cv2.erode(outline,kern)>0] = cv2.GC_FGD
    cv2.setNumThreads(1)
    cv2.setRNGSeed(42)
    cv2.grabCut(fg,band,None,np.zeros((1,65),np.float64),np.zeros((1,65),np.float64),4,cv2.GC_INIT_WITH_MASK)
    matte = cv2.GaussianBlur((band%2).astype(np.float32),(3,3),.57)
    y, x = np.indices((h,w),np.float32)
    u = np.clip((x + LEFT - 898)/126,0,1)
    return Layers(art["clean"].astype(np.float32),fg.astype(np.float32)*matte[:,:,None],
                  matte,x,y,u*u*(3-2*u))


def render_frame(p, i):
    fraction = elevation(i)
    # Entire hand and mug are beyond x=1024: they share one rigid translation.
    # Elbow/sleeve eases from a planted entry at the left crop to that translation.
    src_y = p.y - (1-fraction)*TRAVEL*p.sleeve_weight
    rgba = cv2.remap(p.premult,p.x,src_y,cv2.INTER_LINEAR)
    a = cv2.remap(p.alpha,p.x,src_y,cv2.INTER_LINEAR)[:,:,None]
    xx, yy = p.x+LEFT, p.y+OVERSCAN
    shadow = (.46-.28*fraction)*np.exp(-.5*(((xx-1158)/(105+19*fraction))**2
                                            +((yy-878)/(6+11*fraction))**2))
    bg = p.backdrop*(1-shadow[:,:,None])
    return np.rint(np.clip(rgba+bg*(1-a),0,255)).astype(np.uint8)[TOP-OVERSCAN:]


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def audit(movie, refs, output):
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_frames",
        "-show_entries", "stream=codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,time_base,color_space:frame=best_effort_timestamp",
        "-of", "json", str(movie)]))
    streams = probe["streams"]
    if len(streams) != 1:
        raise ValueError("expected one silent picture stream")
    stream = streams[0]
    if (stream["codec_name"], stream["width"], stream["height"], stream["pix_fmt"],
        Fraction(stream["avg_frame_rate"]), stream["color_space"]) != ("h264", W, H, "yuv420p", FPS, "bt709"):
        raise ValueError("delivery format changed")
    times = [int(f["best_effort_timestamp"]) * Fraction(stream["time_base"]) for f in probe["frames"]]
    if times != [Fraction(n, FPS) for n in range(COUNT)]:
        raise ValueError("bad frame count or timestamps")
    sheet = Image.new("RGB", (960, 4 * 202), "#171717")
    draw = ImageDraw.Draw(sheet)
    scores = {}
    with subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(movie), "-f", "rawvideo",
                           "-pix_fmt", "rgb24", "pipe:1"], stdout=subprocess.PIPE) as proc:
        try:
            for index in range(COUNT):
                raw = proc.stdout.read(W * H * 3)
                if len(raw) != W * H * 3:
                    raise ValueError(f"incomplete decode at frame {index}")
                if index not in refs:
                    continue
                decoded = np.frombuffer(raw, np.uint8).reshape(H, W, 3)
                mse = float(np.mean((decoded.astype(np.float32) - refs[index]) ** 2))
                psnr = 10 * math.log10(255 ** 2 / max(mse, 1e-12))
                if psnr < 38:
                    raise ValueError(f"picture quality fell to {psnr:.2f} dB at frame {index}")
                scores[index] = round(psnr, 3)
                x, y = (SAMPLES.index(index) % 3) * 320, (SAMPLES.index(index) // 3) * 202
                sheet.paste(Image.fromarray(decoded).resize((320, 180), Image.Resampling.LANCZOS), (x, y))
                draw.text((x+7, y+182), f"F{index:03d}   {index/FPS:.2f}s", fill="white")
            if proc.stdout.read(1) or proc.wait():
                raise ValueError("unexpected bytes or decode error")
        finally:
            proc.stdout.close()
    sheet.save(output / "decoded-poses.jpg", quality=92)
    return scores


def build(output: Path):
    if output.exists():
        raise FileExistsError(output)
    layers = prepare_action()
    output.mkdir(parents=True, exist_ok=False)
    movie = output / "june-left-handle-v2.mp4"
    command = encoder_command("ffmpeg", movie)
    command[command.index("-s")+1] = f"{W}x{H}"
    refs, hashes = {}, []
    with (output/"encode.log").open("wb") as log, subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log) as proc:
        try:
            for i in range(COUNT):
                frame = render_frame(layers,i)
                raw = frame.tobytes()
                hashes.append(sha256(raw).hexdigest())
                proc.stdin.write(raw)
                if i in SAMPLES:
                    refs[i] = frame.copy()
        finally:
            proc.stdin.close()
        if proc.wait():
            raise ValueError("picture encode failed, see encode.log")
    if hashes[0] != hashes[-1]:
        raise ValueError("set-down did not restore the original supported pose")
    write_json(output/"source-frames.json", {"index_base":0,"sha256_rgb24":hashes})
    scores = audit(movie,refs,output)
    sources=[Path(__file__),RECIPE,ROOT/"pipeline/cartoon_scene_review.py",ROOT/"pipeline/cartoon_shot_sequence.py"]
    report={"id":"june-left-handle-v2","frames":COUNT,"fps":FPS,"seconds":COUNT/FPS,"size":[W,H],
            "decoded_all_frames_and_timestamps":True,"sample_psnr_db":scores,"audio":"intentionally silent",
            "starts_and_ends_already_gripped":True,"identical_native_start_end":True,"human_accepted":False,
            "picture_sha256":sha256(movie.read_bytes()).hexdigest(),"runtime_source_sha256":
            {p.resolve().relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest() for p in sources}}
    write_json(output/"verification.json",report)
    return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path,help="fresh directory (never overwrite)")
    print(json.dumps(build(parser.parse_args().output),indent=2))
