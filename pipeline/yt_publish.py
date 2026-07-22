"""Publish finished renders to YouTube as Public, from the repo's release assets,
using the YT OAuth secrets. Runs in CI (youtube.upload scope is sufficient to
insert a public video). Reads pipeline/yt_publish_queue.json.

Env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN, GH_TOKEN (for release download).
Writes pipeline/yt_published_result.json (slug -> video_id).
"""
import json, os, subprocess, urllib.request, urllib.parse, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.environ.get("GH_REPO", "prototype-video/Prototype-Video")

def access_token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=data), timeout=30))
    return r["access_token"]

def download_final(slug):
    out = f"/tmp/{slug}.mp4"
    subprocess.run(["gh", "release", "download", f"video-{slug}", "-R", REPO,
                    "-p", "final.mp4", "-O", out, "--clobber"], check=True,
                   env={**os.environ})
    return out

def upload(path, meta, token):
    size = os.path.getsize(path)
    body = {"snippet": {"title": meta["title"][:100], "description": meta["description"][:4900],
                        "tags": meta.get("tags", []), "categoryId": "22"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"})
    uri = urllib.request.urlopen(req, timeout=30).headers["Location"]
    with open(path, "rb") as f:
        data = f.read()
    put = urllib.request.Request(uri, data=data, method="PUT",
        headers={"Authorization": "Bearer " + token,
                 "Content-Range": f"bytes 0-{size-1}/{size}", "Content-Type": "video/mp4"})
    resp = json.load(urllib.request.urlopen(put, timeout=300))
    return resp["id"]

def main():
    queue = json.load(open(os.path.join(HERE, "yt_publish_queue.json")))
    only = sys.argv[1:] or list(queue.keys())
    token = access_token()
    results = {}
    for slug in only:
        meta = queue[slug]
        path = download_final(slug)
        vid = upload(path, meta, token)
        results[slug] = vid
        print(f"PUBLISHED {slug} -> https://youtube.com/watch?v={vid}", flush=True)
    json.dump(results, open(os.path.join(HERE, "yt_published_result.json"), "w"), indent=1)
    print("ALL DONE:", results)

if __name__ == "__main__":
    main()
