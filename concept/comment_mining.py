"""Mine audience comments for editorial signals without turning comments into orders.

The classifier is deliberately transparent and low-confidence. It measures proxies
for reflection, application, curiosity, disagreement, confusion, misinterpretation,
distress, dependency and certainty transfer. Public excerpts are minimized and no
author identifiers are stored.

Env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Usage: python3 concept/comment_mining.py
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Mapping, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CUES: Dict[str, Sequence[str]] = {
    "request": (
        "do one", "do a video", "please make", "can you do", "what about",
        "you should do", "next video", "cover this", "explain this",
    ),
    "confusion": (
        "confused", "don't understand", "dont understand", "lost me",
        "makes no sense", "what do you mean", "didn't get", "too fast",
    ),
    "resonance": (
        "needed this", "goosebumps", "chills", "felt this", "hit different",
        "that landed", "this hit", "beautiful",
    ),
    "gratitude": ("thank you", "thanks", "grateful", "appreciate"),
    "reflection": (
        "made me think", "never thought", "i'm questioning", "im questioning",
        "i wonder", "i realized", "i noticed", "caught myself", "now i'm asking",
    ),
    "application": (
        "i tried", "i asked", "i used this", "i did this", "i'm going to test",
        "im going to test", "i wrote it down", "i paused", "i checked",
    ),
    "curiosity": (
        "could it", "what if", "how does", "why does", "is it possible",
        "would this", "i'm curious", "im curious",
    ),
    "constructive_disagreement": (
        "i disagree", "not sure i agree", "i don't think", "i dont think",
        "but what about", "what evidence", "another explanation", "counterpoint",
    ),
    "misinterpretation": (
        "nothing is real", "reality is fake", "this proves we are in a simulation",
        "dmt is the truth", "this proves consciousness creates everything",
        "the brain makes everything up",
    ),
    "dependency": (
        "only you understand", "tell me what to believe", "i need your videos to",
        "only this channel", "you have all the answers", "don't leave us",
    ),
    "distress": (
        "this scared me", "having a panic attack", "nothing feels real",
        "derealization", "dissociation", "losing my mind", "can't sleep after",
    ),
    "certainty_transfer": (
        "this is the truth", "you proved it", "exactly how reality works",
        "now i know for sure", "no doubt anymore",
    ),
    "agency": (
        "i can check", "i can ask", "i can choose", "i noticed the difference",
        "i have a choice", "i can test",
    ),
}

HELPFUL_TAGS = {"reflection", "application", "curiosity", "constructive_disagreement"}
RISK_TAGS = {"misinterpretation", "dependency", "distress", "certainty_transfer"}


def classify(text: str) -> List[str]:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    tags = []
    for tag, cues in CUES.items():
        if any(cue in normalized for cue in cues):
            tags.append(tag)
    return tags


def _proxy(counts: Mapping[str, int], total: int, tags: Iterable[str]) -> float:
    if total <= 0:
        return 0.0
    return round(sum(int(counts.get(tag, 0)) for tag in tags) / total, 4)


def summarize_records(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    counts: collections.Counter[str] = collections.Counter()
    samples: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        tags = list(record.get("tags", []))
        counts.update(tags)
        for tag in tags:
            if len(samples[tag]) < 5:
                samples[tag].append({
                    "comment_id_hash": record.get("comment_id_hash"),
                    "excerpt": record.get("excerpt"),
                    "like_count": record.get("like_count", 0),
                    "published_at": record.get("published_at"),
                })
    total = len(records)
    helpful_comments = sum(
        bool(set(record.get("tags", [])) & HELPFUL_TAGS)
        for record in records
    )
    risk_comments = sum(
        bool(set(record.get("tags", [])) & RISK_TAGS)
        for record in records
    )
    helpful = round(helpful_comments / total, 4) if total else 0.0
    risk = round(risk_comments / total, 4) if total else 0.0
    return {
        "total_comments_scanned": total,
        "tag_counts": dict(sorted(counts.items())),
        "samples": dict(samples),
        "belief_analysis_yield_proxy": helpful,
        "autonomy_risk_proxy": risk,
        "helpfulness_score_proxy": round(max(0.0, helpful - 1.5 * risk) * 100, 2),
        "method_note": "Keyword proxy; interpret with low confidence and read samples before acting.",
    }


def access_token() -> str:
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    request = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


def fetch_comments(video_id: str, token: str, cap: int = 100) -> List[Dict[str, Any]]:
    """Fetch recent top-level comments.

    `order=time` avoids letting YouTube's relevance ranking silently define the
    editorial signal. The cap keeps nightly state compact.
    """
    output: List[Dict[str, Any]] = []
    base = (
        "https://www.googleapis.com/youtube/v3/commentThreads"
        "?part=snippet"
        f"&videoId={urllib.parse.quote(video_id)}"
        "&maxResults=100&order=time&textFormat=plainText"
    )
    page = None
    while len(output) < cap:
        url = base + (f"&pageToken={urllib.parse.quote(page)}" if page else "")
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.load(response)
        except Exception:
            break
        for item in data.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            text = str(snippet.get("textDisplay", "")).strip()
            comment_id = str(item["snippet"]["topLevelComment"].get("id", ""))
            output.append({
                "comment_id_hash": hashlib.sha256(comment_id.encode()).hexdigest()[:12] if comment_id else None,
                "excerpt": re.sub(r"\s+", " ", text)[:180],
                "tags": classify(text),
                "like_count": int(snippet.get("likeCount", 0) or 0),
                "published_at": snippet.get("publishedAt"),
            })
            if len(output) >= cap:
                break
        page = data.get("nextPageToken")
        if not page:
            break
    return output


def main() -> int:
    published_path = os.path.join(ROOT, "pipeline", "published_videos.json")
    with open(published_path, encoding="utf-8") as f:
        published = json.load(f)

    token = access_token()
    signal: Dict[str, Any] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "method": "transparent keyword proxy over recent top-level YouTube comments",
        "editorial_rule": "Audience comments are signals, not commands. Safety, evidence, sequence and mission remain authoritative.",
        "by_video": {},
        "global": {},
    }
    all_records: List[Dict[str, Any]] = []
    for slug, meta in published.items():
        video_id = meta.get("youtube_id")
        if not video_id:
            continue
        records = fetch_comments(video_id, token)
        signal["by_video"][slug] = summarize_records(records)
        all_records.extend(records)

    signal["global"] = summarize_records(all_records)
    output_path = os.path.join(HERE, "audience_signal.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(signal, f, indent=2, ensure_ascii=False)
        f.write("\n")

    global_summary = signal["global"]
    print(
        "audience_signal.json:",
        global_summary["total_comments_scanned"],
        "comments;",
        "belief-analysis proxy",
        global_summary["belief_analysis_yield_proxy"],
        "autonomy-risk proxy",
        global_summary["autonomy_risk_proxy"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
