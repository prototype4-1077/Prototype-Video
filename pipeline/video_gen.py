"""Image-to-video backend for cartoon (generated_temporal_video) scenes.

Turns a committed cartoon keyframe (hero/ref art or a per-scene keyframe) into a
short animated clip via Replicate's HTTP API. No stock. Used when a script is
cartoon_only / generated_temporal_video_required so the render honors the cartoon
contract instead of pulling Pexels.

Env:
  REPLICATE_API_TOKEN   required
  VIDEO_GEN_MODEL       owner/name (default cartoon-capable i2v); swap for quality/cost
"""
from __future__ import annotations
import base64, json, mimetypes, os, time, urllib.request, urllib.error

API = "https://api.replicate.com/v1"
DEFAULT_MODEL = os.environ.get("VIDEO_GEN_MODEL", "wan-video/wan-2.1-i2v-480p")


def _token() -> str:
    tok = os.environ.get("REPLICATE_API_TOKEN")
    if not tok:
        raise SystemExit("REPLICATE_API_TOKEN not set")
    return tok


def _data_uri(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()


def _req(url: str, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + _token(),
        "Content-Type": "application/json",
        "Prefer": "wait=60" if method == "POST" else "",
    })
    with urllib.request.urlopen(r, timeout=90) as resp:
        return json.load(resp)


def generate_clip(image_path: str, prompt: str, out_path: str,
                  duration: int = 5, model: str | None = None,
                  build_dir: str | None = None, scene_count: int = 1,
                  scene_limit: int = 5) -> str:
    # paid provider is OFF by default: requires an approved generation-budget.json
    import cartoon_budget
    cartoon_budget.assert_paid_allowed(build_dir or ".", "replicate",
                                       model or DEFAULT_MODEL, scene_count, scene_limit)
    """Animate a still cartoon keyframe into a short clip (PAID; budget-gated). Returns out_path."""
    model = model or DEFAULT_MODEL
    payload = {"input": {
        "image": _data_uri(image_path),
        "prompt": prompt,
        "num_frames": max(16, int(duration * 16)),
        "fps": 16,
    }}
    pred = _req(f"{API}/models/{model}/predictions", "POST", payload)
    # poll to completion
    url = pred.get("urls", {}).get("get") or f"{API}/predictions/{pred['id']}"
    for _ in range(120):
        status = pred.get("status")
        if status == "succeeded":
            break
        if status in ("failed", "canceled"):
            raise SystemExit(f"video_gen {status}: {pred.get('error')}")
        time.sleep(3)
        pred = _req(url)
    out = pred.get("output")
    video_url = out[-1] if isinstance(out, list) else out
    if not video_url:
        raise SystemExit(f"video_gen: no output ({pred.get('status')})")
    with urllib.request.urlopen(video_url, timeout=180) as v, open(out_path, "wb") as f:
        f.write(v.read())
    return out_path


if __name__ == "__main__":
    import sys
    img, prompt, out = sys.argv[1], sys.argv[2], sys.argv[3]
    dur = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    print("wrote", generate_clip(img, prompt, out, dur))
