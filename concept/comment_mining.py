"""Tier 2 — audience signal from comments. The audience writes the roadmap in the
comments; this reads it. Runs in CI with the YT OAuth secrets (youtube.readonly).

Pulls comments for each published video, classifies each into resonance / confusion /
request / gratitude, and writes concept/audience_signal.json — a rolling digest the
scriptwriter reads for what landed, what confused, and what viewers asked to see next.

Env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
Usage: python3 concept/comment_mining.py
"""
import json, os, re, urllib.request, urllib.parse, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

REQUEST_CUES = ("do one", "do a video", "please make", "can you do", "what about",
                "you should do", "next video", "cover", "explain", "i want to see")
CONFUSION_CUES = ("confused", "don't understand", "dont understand", "lost me",
                  "makes no sense", "what do you mean", "didn't get", "too fast")
RESONANCE_CUES = ("needed this", "changed", "goosebumps", "chills", "exactly",
                  "felt this", "hit different", "so true", "mind blown", "profound")
GRATITUDE_CUES = ("thank you", "thanks", "grateful", "appreciate")

def classify(text):
    t = text.lower()
    tags = []
    if any(c in t for c in REQUEST_CUES): tags.append("request")
    if any(c in t for c in CONFUSION_CUES): tags.append("confusion")
    if any(c in t for c in RESONANCE_CUES): tags.append("resonance")
    if any(c in t for c in GRATITUDE_CUES): tags.append("gratitude")
    return tags

def access_token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token"}).encode()
    r = json.load(urllib.request.urlopen(
        urllib.request.Request("https://oauth2.googleapis.com/token", data=data), timeout=30))
    return r["access_token"]

def fetch_comments(video_id, token, cap=80):
    out = []
    url = ("https://www.googleapis.com/youtube/v3/commentThreads?part=snippet"
           f"&videoId={video_id}&maxResults=50&order=relevance&textFormat=plainText")
    page = None
    while len(out) < cap:
        u = url + (f"&pageToken={page}" if page else "")
        req = urllib.request.Request(u, headers={"Authorization": f"Bearer {token}"})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception:
            break
        for it in d.get("items", []):
            sn = it["snippet"]["topLevelComment"]["snippet"]
            out.append(sn.get("textDisplay", ""))
        page = d.get("nextPageToken")
        if not page:
            break
    return out

def main():
    pub = json.load(open(os.path.join(ROOT, "pipeline", "published_videos.json")))
    token = access_token()
    signal = {"by_video": {}, "requests": [], "confused_about": [], "resonated": [],
              "tallies": {}}
    tally = collections.Counter()
    for slug, meta in pub.items():
        vid = meta["youtube_id"]
        comments = fetch_comments(vid, token)
        buckets = collections.defaultdict(list)
        for c in comments:
            for tag in classify(c):
                buckets[tag].append(c.strip()[:200])
                tally[tag] += 1
        signal["by_video"][slug] = {k: v[:5] for k, v in buckets.items()}
        signal["requests"] += [(slug, c) for c in buckets.get("request", [])[:3]]
        signal["confused_about"] += [(slug, c) for c in buckets.get("confusion", [])[:2]]
        signal["resonated"] += [(slug, c) for c in buckets.get("resonance", [])[:2]]
    signal["tallies"] = dict(tally)
    out = os.path.join(HERE, "audience_signal.json")
    json.dump(signal, open(out, "w"), indent=1, ensure_ascii=False)
    print(f"audience_signal.json: {sum(tally.values())} tagged comments across {len(pub)} videos")
    print("tallies:", dict(tally))
    if signal["requests"]:
        print("top requests:", signal["requests"][:5])

if __name__ == "__main__":
    main()
