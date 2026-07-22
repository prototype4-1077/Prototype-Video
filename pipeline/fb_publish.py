"""Publish finished renders to a Facebook Page from the repo's release assets.

Env: FB_PAGE_ID, FB_PAGE_TOKEN, GH_TOKEN (for release download).
Usage: python3 pipeline/fb_publish.py [slug ...]   (no slug = whole queue)

Uploads the 16:9 final (falls back if only one exists) as a regular Page video
via the Graph video endpoint, with title + description from fb_publish_queue.json.
"""
import json, os, subprocess, sys

REPO = os.environ.get("FB_REPO", "prototype-video/Prototype-Video")
API = "https://graph-video.facebook.com/v25.0"
QUEUE = os.path.join(os.path.dirname(__file__), "fb_publish_queue.json")

def download_final(slug):
    out = f"/tmp/{slug}.mp4"
    last = None
    for pat in ("final_youtube.mp4", "final.mp4"):   # FB feed favors 16:9 first
        try:
            subprocess.run(["gh", "release", "download", f"video-{slug}", "-R", REPO,
                            "-p", pat, "-O", out, "--clobber"], check=True, env={**os.environ})
            return out
        except subprocess.CalledProcessError as e:
            last = e
    raise last

def publish(slug, meta, page_id, token):
    path = download_final(slug)
    r = subprocess.run(["curl", "-sS", "-X", "POST", f"{API}/{page_id}/videos",
                        "-F", f"access_token={token}",
                        "-F", f"title={meta.get('title','')}",
                        "-F", f"description={meta.get('description','')}",
                        "-F", f"source=@{path}"], capture_output=True, text=True)
    try:
        resp = json.loads(r.stdout)
    except Exception:
        raise SystemExit(f"FB upload failed for {slug}: {r.stdout[:400]} {r.stderr[:200]}")
    if "id" not in resp:
        raise SystemExit(f"FB upload error for {slug}: {json.dumps(resp)[:500]}")
    return resp["id"]

def main():
    page_id = os.environ["FB_PAGE_ID"]; token = os.environ["FB_PAGE_TOKEN"]
    q = json.load(open(QUEUE))
    slugs = sys.argv[1:] or list(q.keys())
    results = {}
    for slug in slugs:
        if slug not in q:
            print(f"skip {slug}: not in queue"); continue
        vid = publish(slug, q[slug], page_id, token)
        url = f"https://www.facebook.com/watch/?v={vid}"
        print(f"PUBLISHED {slug} -> {url}")
        results[slug] = {"video_id": vid, "url": url}
    json.dump(results, open("fb_published_result.json", "w"), indent=2)

if __name__ == "__main__":
    main()
