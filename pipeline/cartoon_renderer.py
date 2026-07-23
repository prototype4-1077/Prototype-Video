"""limited_2_5d local cartoon renderer: layered puppet animation via PIL+FFmpeg.

Reads a scene manifest (background + independently-moving layers + camera), applies
per-layer motion curves and depth parallax, and streams composited frames straight
to ffmpeg. No external video API. Enforces the cartoon-only motion floor.
"""
from __future__ import annotations
import io, json, os, subprocess
import numpy as np
from PIL import Image
import cartoon_motion as M

DEF_W, DEF_H, DEF_FPS = 540, 960, 24  # proof res (portrait); final can bump to 1080x1920


def _rgba(path, size):
    im = Image.open(path).convert("RGBA")
    im.thumbnail((size[0]*2, size[1]*2))
    return im


def _place(layer_im, dx, dy, scale, rotate, canvas):
    w, h = canvas
    im = layer_im
    if abs(scale-1.0) > 1e-3:
        im = im.resize((max(1,int(im.width*scale)), max(1,int(im.height*scale))), Image.LANCZOS)
    if abs(rotate) > 1e-2:
        im = im.rotate(rotate, expand=True, resample=Image.BICUBIC)
    base = Image.new("RGBA", canvas, (0,0,0,0))
    x = int((w-im.width)/2 + dx); y = int((h-im.height)/2 + dy)
    base.alpha_composite(im, (x, y))
    return base


def _blink(layer_im):
    # squash the eye layer vertically -> a real 'eyes closed' facial change
    sq = layer_im.resize((layer_im.width, max(1,int(layer_im.height*0.16))), Image.LANCZOS)
    out = Image.new("RGBA", layer_im.size, (0,0,0,0))
    out.alpha_composite(sq, (0, int(layer_im.height*0.42)))
    return out


def moving_layers(manifest):
    return [l for l in manifest.get("layers", []) if (l.get("motion") or "still") != "still"]


CHARACTER_MOTIONS = {"subtle_breath","nod_and_turn","blink_and_glance","shoulder_shift",
                     "arm_gesture","coffee_gesture","sway","rock"}
OBJECT_MOTIONS = {"loop_upward","steam_rise","light_flicker","passing_shadow","curtain_move",
                  "slide_in","door_open","object_rotate"}

def validate(manifest, min_layers=3, min_regions=2, static_pan_zoom_allowed=False, scene_kind=None):
    errs = []
    mov = moving_layers(manifest)
    if len(mov) < min_layers:
        errs.append(f"only {len(mov)} independently moving layers; need >= {min_layers}")
    # distinct active motion regions: group moving layers by coarse anchor
    regions = {(l.get("id") or "")[:6] + str(l.get("depth")) for l in mov}
    if len(regions) < min_regions:
        errs.append(f"only {len(regions)} active motion regions; need >= {min_regions}")
    cam_only = (len(mov) == 0)
    if cam_only and not static_pan_zoom_allowed:
        errs.append("camera move alone is not animation (static_pan_zoom_allowed=false)")
    # require at least one non-camera 'real change' motion (blink/steam/gesture/etc.)
    real = [l for l in mov if l.get("motion") not in ("still",)]
    if not real:
        errs.append("no real subject/prop/environment motion present")
    kinds = {l.get("motion") for l in mov}
    if scene_kind == "character" and not (kinds & CHARACTER_MOTIONS):
        errs.append("character scene requires subject motion (face/head/hand/torso)")
    if scene_kind == "object" and not (kinds & OBJECT_MOTIONS):
        errs.append("object scene requires object or environmental motion")
    return errs


def render(manifest, out_path, W=DEF_W, H=DEF_H):
    fps = int(manifest.get("fps", DEF_FPS))
    dur = float(manifest.get("duration_seconds", 6.0))
    frames = max(1, int(dur*fps))
    canvas = (W, H)
    bg_im = _rgba(manifest["background"], canvas).resize(canvas, Image.LANCZOS).convert("RGBA")
    layers = []
    for l in manifest.get("layers", []):
        p = l["asset"]
        if not os.path.exists(p):
            continue
        layers.append((l, _rgba(p, canvas)))
    cam_name = (manifest.get("camera") or {}).get("move", "slow_push")
    ff = subprocess.Popen(
        ["ffmpeg","-y","-loglevel","error","-f","rawvideo","-pix_fmt","rgb24",
         "-s",f"{W}x{H}","-r",str(fps),"-i","-","-an","-c:v","libx264",
         "-pix_fmt","yuv420p","-crf","20",out_path], stdin=subprocess.PIPE)
    for f in range(frames):
        t = f/fps
        cam = M.camera(cam_name, t, dur)
        frame = Image.new("RGBA", canvas, (12,12,16,255))
        # background with camera scale + slight parallax (depth 0)
        bg = _place(bg_im, cam["dx"]*0.15, cam["dy"]*0.15, cam["scale"], 0, canvas)
        frame.alpha_composite(bg)
        for l, im in layers:
            depth = float(l.get("depth", 3))
            tf = M.get(l.get("motion"))(t, dur)
            par = (depth/8.0)  # nearer layers parallax more with the camera
            dx = l.get("x",0)+tf.get("dx",0)+cam["dx"]*par
            dy = l.get("y",0)+tf.get("dy",0)+cam["dy"]*par
            sc = tf.get("scale",1.0)*cam["scale"]
            rot = tf.get("rotate",0.0)
            use = _blink(im) if tf.get("blink") else im
            placed = _place(use, dx, dy, sc, rot, canvas)
            if tf.get("opacity") is not None:
                a = placed.split()[3].point(lambda v: int(v*tf["opacity"])); placed.putalpha(a)
            frame.alpha_composite(placed)
        ff.stdin.write(np.asarray(frame.convert("RGB"), dtype=np.uint8).tobytes())
    ff.stdin.close(); ff.wait()
    return out_path
