"""Host-avatar animator: integrated scene + stacked effects (talk cycle, depth
parallax, dust, camera). Implements host_avatar_mode for the June rebuild.

Input: two same-seed integrated frames (mouth closed / open). Output: MP4 where
June is solid, grounded, talking at speech rhythm, background alive with depth.
"""
from __future__ import annotations
import math, os, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

def _load(p, size): return Image.open(p).convert("RGB").resize(size, Image.LANCZOS)

def _dust(size, n=46, seed=7):
    import random; random.seed(seed)
    im=Image.new("RGBA",size,(0,0,0,0)); d=ImageDraw.Draw(im)
    for _ in range(n):
        x,y=random.randint(0,size[0]),random.randint(0,size[1]); r=random.randint(1,3)
        d.ellipse([x,y,x+r,y+r],fill=(255,244,214,105))
    return im.filter(ImageFilter.GaussianBlur(1))

def _talk_weight(t, talking=True):
    """0..1 mouth-open weight at speech rhythm: syllable flutter + word pauses."""
    if not talking: return 0.0
    syl = 0.5+0.5*math.sin(2*math.pi*4.6*t + 1.3*math.sin(2*math.pi*0.9*t))
    pause = 0.5+0.5*math.sin(2*math.pi*0.23*t)
    gate = 1.0 if pause>0.25 else 0.15
    return max(0.0,min(1.0, syl*gate))

def _mouth_mask(W,H,cx,cy,rx,ry,feather=14):
    m=Image.new("L",(W,H),0); d=ImageDraw.Draw(m)
    d.ellipse([cx-rx,cy-ry,cx+rx,cy+ry],fill=255)
    return np.asarray(m.filter(ImageFilter.GaussianBlur(feather))).astype(np.float32)/255.0

def render_host(frameA, frameB, out, dur=8.0, fps=18, W=540, H=960, push=0.045,
                mouth=(0.63,0.30,0.075,0.065)):
    A=_load(frameA,(W,H)); B=_load(frameB,(W,H))
    a=np.asarray(A).astype(np.float32); b=np.asarray(B).astype(np.float32)
    mcx,mcy,mrx,mry=int(mouth[0]*W),int(mouth[1]*H),int(mouth[2]*W),int(mouth[3]*W)
    mask=_mouth_mask(W,H,mcx,mcy,mrx,mry)[:,:,None]
    dust=_dust((W,H))
    ff=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","rawvideo","-pix_fmt","rgb24",
        "-s",f"{W}x{H}","-r",str(fps),"-i","-","-an","-c:v","libx264","-pix_fmt","yuv420p","-crf","19",out],
        stdin=subprocess.PIPE)
    frames=int(dur*fps)
    for f in range(frames):
        t=f/fps
        w=_talk_weight(t)
        # blend ONLY the feathered mouth/jaw ellipse; rest stays frame A (rock solid)
        mix=a*(1-mask*w)+b*(mask*w)
        im=Image.fromarray(mix.astype(np.uint8))
        # deep-page camera: slow push + micro drift; parallax via asymmetric crop
        s=1.0+push*(t/dur); drift=3.0*math.sin(2*math.pi*0.11*t)
        cw,ch=int(W/s),int(H/s)
        cx=int((W-cw)/2 + drift); cy=int((H-ch)/2 + 0.5*drift)
        im=im.crop((max(0,cx),max(0,cy),max(0,cx)+cw,max(0,cy)+ch)).resize((W,H),Image.LANCZOS)
        # foreground dust drifts fastest (near plane)
        dd=dust.rotate(0); ddx=int(10*math.sin(2*math.pi*0.07*t)); ddy=int(-(t*7)%H)
        im=im.convert("RGBA"); im.alpha_composite(dd,(ddx,ddy-H)); im.alpha_composite(dd,(ddx,ddy))
        ff.stdin.write(np.asarray(im.convert("RGB"),dtype=np.uint8).tobytes())
    ff.stdin.close(); ff.wait()
    return out
