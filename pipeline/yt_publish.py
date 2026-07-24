"""Publish explicitly requested finished renders to YouTube as Public.

Publishing is idempotent by default. A committed receipt is checked before any
upload, updated atomically after every successful video, and may be bypassed only
with the explicit ``--force`` flag. The YouTube-specific master is preferred.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = os.environ.get("GH_REPO", "prototype-video/Prototype-Video")
QUEUE = HERE / "yt_publish_queue.json"
RESULT = HERE / "yt_published_result.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def atomic_json(path: Path, payload: Any) -> None:
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def normalized_history() -> dict[str, dict[str, Any]]:
    raw = load_json(RESULT, {}) or {}
    output: dict[str, dict[str, Any]] = {}
    for slug, value in raw.items() if isinstance(raw, dict) else []:
        if isinstance(value, str):
            output[str(slug)] = {"video_id": value, "url": f"https://youtube.com/watch?v={value}"}
        elif isinstance(value, dict) and value.get("video_id"):
            output[str(slug)] = dict(value)
    return output


def access_token() -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    response = json.load(urllib.request.urlopen(request, timeout=30))
    return str(response["access_token"])


def download_final(slug: str) -> str:
    out = f"/tmp/{slug}.mp4"
    last: subprocess.CalledProcessError | None = None
    # The landscape YouTube master is the canonical platform asset.
    for pattern in ("final_youtube.mp4", "final.mp4"):
        try:
            subprocess.run(
                ["gh", "release", "download", f"video-{slug}", "-R", REPO,
                 "-p", pattern, "-O", out, "--clobber"],
                check=True,
                env={**os.environ},
            )
            return out
        except subprocess.CalledProcessError as error:
            last = error
    if last is None:
        raise RuntimeError(f"no release asset pattern attempted for {slug}")
    raise last


def upload(path: str, meta: dict[str, Any], token: str) -> str:
    size = os.path.getsize(path)
    body = {
        "snippet": {
            "title": str(meta["title"])[:100],
            "description": str(meta["description"])[:4900],
            "tags": meta.get("tags", []),
            "categoryId": "22",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    request = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(size),
            "X-Upload-Content-Type": "video/mp4",
        },
    )
    uri = urllib.request.urlopen(request, timeout=30).headers["Location"]
    with open(path, "rb") as handle:
        data = handle.read()
    put = urllib.request.Request(
        uri,
        data=data,
        method="PUT",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Range": f"bytes 0-{size-1}/{size}",
            "Content-Type": "video/mp4",
        },
    )
    response = json.load(urllib.request.urlopen(put, timeout=300))
    return str(response["id"])


def publish(slugs: list[str], *, force: bool = False) -> dict[str, dict[str, Any]]:
    if not slugs:
        raise ValueError("explicit slug required; refusing to publish the entire queue")
    queue = load_json(QUEUE, {}) or {}
    history = normalized_history()
    missing = [slug for slug in slugs if slug not in queue]
    if missing:
        raise KeyError("not in YouTube publish queue: " + ", ".join(missing))

    pending = [slug for slug in slugs if force or slug not in history]
    for slug in slugs:
        if slug not in pending:
            print(f"SKIP already published {slug} -> {history[slug].get('url')}", flush=True)
    if not pending:
        return history

    token = access_token()
    for slug in pending:
        meta = queue[slug]
        path = download_final(slug)
        video_id = upload(path, meta, token)
        record = {
            "video_id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}",
            "published_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "title": meta.get("title"),
            "forced": bool(force),
        }
        history[slug] = record
        atomic_json(RESULT, history)
        print(f"PUBLISHED {slug} -> {record['url']}", flush=True)
    return history


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="allow an intentional duplicate upload")
    parser.add_argument("slugs", nargs="*")
    args = parser.parse_args(argv)
    result = publish(args.slugs, force=args.force)
    print("ALL DONE:", json.dumps({slug: result.get(slug) for slug in args.slugs}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
