"""Nightly audience-retention sync: YouTube Analytics -> per-scene learning.

Reads pipeline/published_videos.json (slug -> youtube_id, mapped via
`learn.py published <slug> <video_id>`), pulls each video's 100-point audience
retention curve plus summary stats, writes build/<slug>/retention.json and
yt_stats.json, then applies learn.audience() and refreshes WHATS_WORKING.md.
Persists structured collection status and fails when required access is unavailable.
Setup guide: pipeline/ANALYTICS.md."""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import learn  # noqa: E402
from yt_stats_refresh import atomic_json

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://youtubeanalytics.googleapis.com/v2/reports"


def access_token():
    cid = os.environ.get("YT_CLIENT_ID")
    sec = os.environ.get("YT_CLIENT_SECRET")
    ref = os.environ.get("YT_REFRESH_TOKEN")
    if not (cid and sec and ref):
        return None
    body = urllib.parse.urlencode({
        "client_id": cid, "client_secret": sec,
        "refresh_token": ref, "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=body), timeout=30) as r:
        return json.load(r)["access_token"]


def query(token, video_id, dimensions, metrics):
    params = {"ids": "channel==MINE", "startDate": "2020-01-01",
              "endDate": date.today().isoformat(), "metrics": metrics,
              "filters": f"video=={video_id}"}
    if dimensions:
        params["dimensions"] = dimensions
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    now = datetime.now(timezone.utc).isoformat()
    status_path = Path(HERE) / "analytics_status.json"
    status = {"schema_version": 1, "generated_at": now, "updated": [], "no_data": [], "errors": []}
    pub = Path(HERE) / "published_videos.json"
    published = json.loads(pub.read_text()) if pub.exists() else {}
    def finish(state, code):
        status["status"] = state
        status["updated_count"] = len(status["updated"])
        atomic_json(status_path, status)
        print(json.dumps(status, indent=2))
        return code
    if not published:
        return finish("no_data", 0)
    try:
        token = access_token()
        if not token:
            status["required_action"] = "Configure YouTube Analytics OAuth read access; public statistics cannot supply retention."
            return finish("not_configured", 2)
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
        # Do not retain request data or credential-bearing response bodies.
        status["errors"].append({"stage": "authorization", "error_type": type(exc).__name__, "http_status": getattr(exc, "code", None)})
        status["required_action"] = "Repair the YouTube OAuth client/grant and authorize yt-analytics.readonly."
        return finish("authorization_failed", 2)
    for slug, info in published.items():
        vid = info.get("youtube_id") if isinstance(info, dict) else str(info)
        bd = Path(HERE).parent / "build" / slug
        if not bd.is_dir():
            status["errors"].append({"slug": slug, "stage": "mapping", "error_type": "missing_build"})
            continue
        try:
            rows = query(token, vid, "elapsedVideoTimeRatio", "audienceWatchRatio,relativeRetentionPerformance").get("rows") or []
            stats = query(token, vid, "", "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage").get("rows") or []
            if not rows:
                status["no_data"].append(slug)
                continue
            payload = {"video_id": vid, "snapshot_at": now,
                       "elapsed": [r[0] for r in rows], "watch_ratio": [r[1] for r in rows],
                       "relative_performance": [r[2] for r in rows]}
            atomic_json(bd / "retention.json", payload)
            if stats:
                measured = dict(zip(["views", "minutes_watched", "avg_view_s", "avg_view_pct"], stats[0]))
                measured.update({"video_id": vid, "retention_snapshot_at": now, "source": "youtube_analytics_api_v2"})
                atomic_json(bd / "retention_stats.json", measured)
            learn.audience(str(bd), str(bd / "retention.json"))
            status["updated"].append(slug)
        except Exception as exc:
            status["errors"].append({"slug": slug, "stage": "collection_or_learning", "error_type": type(exc).__name__, "http_status": getattr(exc, "code", None)})
    learn.digest()
    if status["errors"]:
        return finish("partial" if status["updated"] else "failed", 2)
    return finish("success" if status["updated"] else "no_data", 0)


if __name__ == "__main__":
    sys.exit(main())
