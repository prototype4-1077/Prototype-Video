"""Hero shots: free AI-generated imagery animated with 2.5D depth parallax.
No paid APIs: images via pollinations.ai (keyless), depth via MiDaS-small ONNX (local).

Usage: python3 hero.py <build_dir> <scene_index>
Scene needs: "hero": true, "image_prompt": "what the shot shows"
Writes clip_XX.mp4 (which footage.py then skips). Stages are cached and resumable:
hero_XX.jpg -> hero_XX_depth.npy -> clip_XX.mp4 (atomic)."""
import json, os, subprocess, sys, urllib.parse, urllib.request

import numpy as np

import profiles

W, H, FPS = 1344, 768, 30
MODEL_URL = "https://github.com/isl-org/MiDaS/releases/download/v2_1/model-small.onnx"

STYLE = {
    None:  (", natural documentary photograph, candid unstaged contemporary people, "
            "neutral true-to-life color, soft diffused daylight, realistic skin texture, "
            "practical lived-in location, ordinary clothing, clean clear air, subtle film grain, "
            "no haze or fog, no silhouetted figures, no fantasy lighting, no surreal effects"),
    "dmt": ", visionary psychedelic art, hyperdetailed, vivid luminous colors on deep black, intricate sacred geometry",
}


def model_path():
    p = os.environ.get("HERO_DEPTH_MODEL", "/tmp/models/midas-small.onnx")
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        op = urllib.request.build_opener(); op.addheaders = [("User-Agent", "Mozilla/5.0")]
        urllib.request.install_opener(op)
        urllib.request.urlretrieve(MODEL_URL, p + ".part")
        os.replace(p + ".part", p)
    return p


def gen_image(prompt, genre, out, profile=None):
    if os.path.exists(out) and os.path.getsize(out) > 20_000:
        return
    style = profiles.hero_style(profile, genre) or STYLE.get(genre, STYLE[None])
    q = urllib.parse.quote(profiles.hero_prompt(prompt, profile) + style)
    last = None
    for seed in (7, 77, 777):
        try:
            url = (f"https://image.pollinations.ai/prompt/{q}"
                   f"?width={W}&height={H}&nologo=true&seed={seed}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=90).read()
            if len(data) > 20_000:
                open(out, "wb").write(data)
                return
        except Exception as e:
            last = e
    sys.exit(f"ERROR: image generation failed ({last}) | FIX: rerun; pollinations.ai may be busy")


def depth_map(img_path, out):
    import cv2, onnxruntime as ort
    if os.path.exists(out):
        return np.load(out)
    img = cv2.imread(img_path)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    inp = cv2.resize(rgb, (256, 256)).transpose(2, 0, 1)[None]
    mean = np.array([0.485, 0.456, 0.406], np.float32).reshape(1, 3, 1, 1)
    std = np.array([0.229, 0.224, 0.225], np.float32).reshape(1, 3, 1, 1)
    sess = ort.InferenceSession(model_path(), providers=["CPUExecutionProvider"])
    d = sess.run(None, {sess.get_inputs()[0].name: (inp - mean) / std})[0][0]
    d = (d - d.min()) / (d.max() - d.min() + 1e-6)          # 0=far 1=near
    d = cv2.resize(d, (img.shape[1], img.shape[0]))
    d = cv2.GaussianBlur(d, (31, 31), 0)                     # soft edges = fewer tears
    np.save(out, d.astype(np.float32))
    return d


def render(img_path, depth, dur, out, mode=0):
    """2.5D parallax: remap pixels by depth as a virtual camera drifts + slow dolly."""
    import cv2
    img = cv2.imread(img_path)
    img = cv2.resize(img, (W, H), interpolation=cv2.INTER_LANCZOS4)  # normalize size (even dims)
    depth = cv2.resize(depth, (W, H))
    ih, iw = img.shape[:2]
    n = max(int(dur * FPS), FPS)
    gx, gy = np.meshgrid(np.arange(iw, dtype=np.float32), np.arange(ih, dtype=np.float32))
    dc = depth - depth.mean()
    amp = iw * 0.018                                          # parallax strength
    tmp = out + ".part.mp4"
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo",
                          "-pix_fmt", "bgr24", "-s", f"{iw}x{ih}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                          "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for f in range(n):
        t = f / max(n - 1, 1)
        e = t * t * (3 - 2 * t)                               # ease in-out
        if mode % 3 == 0:   ox, oy = amp * (2 * e - 1), amp * 0.25 * (2 * e - 1)
        elif mode % 3 == 1: ox, oy = amp * (1 - 2 * e), -amp * 0.2 * (2 * e - 1)
        else:               ox, oy = amp * 0.3 * np.sin(e * np.pi), amp * (2 * e - 1) * 0.6
        zoom = 1.06 + 0.05 * e                                # dolly-in, hides edge gaps
        mx = (gx - iw / 2) / zoom + iw / 2 - dc * ox
        my = (gy - ih / 2) / zoom + ih / 2 - dc * oy
        frame = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        p.stdin.write(frame.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        sys.exit("ERROR: hero encode failed | FIX: rerun")
    os.replace(tmp, out)


def main(bd, i):
    s = json.load(open(f"{bd}/script.json"))
    sc = s["scenes"][i]
    out = f"{bd}/clip_{i:02d}.mp4"
    if os.path.exists(out) and os.path.getsize(out) > 100_000:
        print(f"hero {i}: exists"); return
    prompt = sc.get("image_prompt") or sc["text"]
    img, dep = f"{bd}/hero_{i:02d}.jpg", f"{bd}/hero_{i:02d}_depth.npy"
    gen_image(prompt, s.get("genre"), img, profiles.resolve(s))
    d = depth_map(img, dep)
    render(img, d, sc.get("duration", 8) + 0.5, out, mode=i)
    sc["clip"] = out
    sc["hero_generated"] = True
    json.dump(s, open(f"{bd}/script.json", "w"), indent=1, ensure_ascii=False)
    print(f"hero {i}: generated ({prompt[:60]}...)")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
