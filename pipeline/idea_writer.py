"""Autonomous scriptwriter: turns an idea into script.json via the Anthropic API.
Usage: python3 idea_writer.py <build_dir> "<idea text>"
Env: ANTHROPIC_API_KEY. Reads style_profile.md + memory.json (notes, motifs) so the
script sounds like James and obeys his standing feedback."""
import json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def main(bd, idea):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ERROR: ANTHROPIC_API_KEY not set | FIX: add it to repo Actions secrets")
    style = open(os.path.join(HERE, "style_profile.md")).read()
    mem = {}
    mp = os.path.join(HERE, "memory.json")
    if os.path.exists(mp):
        mem = json.load(open(mp))
    motifs = "\n".join(f"- {m['name']}: \"{m['line']}\" (from {m['video']})"
                       for m in mem.get("motifs", []))
    notes = "\n".join(f"- {n}" for n in mem.get("notes", []))
    prompt = f"""Write a script for a short philosophical TikTok video in James's voice.

IDEA: {idea}

JAMES'S STYLE (follow closely):
{style[:4000]}

HIS STANDING FEEDBACK (obey all):
{notes}

EARLIER MOTIFS (echo exactly ONE of these with a brief, natural callback phrase mid-video —
do not explain it, just let returning viewers feel it):
{motifs}

OUTPUT: pure JSON only, no markdown fences, exactly this shape:
{{"title": "Three Or Four Words", "slug": "short-dashed-title", "scenes": [
  {{"text": "One sentence or beat, max 25 words.",
    "keywords": ["2-4 words that literally appear in text"],
    "query": "pexels search, lit-but-moody, literal to the line"}} ]}}
Rules: 18-26 scenes; 300-400 words total; second person; conversational hook opener;
quiet powerful realization ending (never "you create everything"); queries favor
window light, god rays, lamplight, golden hour, silhouettes; only a few dark scenes."""
    req = urllib.request.Request("https://api.anthropic.com/v1/messages",
        data=json.dumps({"model": "claude-sonnet-5", "max_tokens": 4000,
                         "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=180).read())
    text = out["content"][0]["text"].strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.M).strip()
    s = json.loads(text)
    os.makedirs(bd, exist_ok=True)
    json.dump(s, open(f"{bd}/script.json", "w"), indent=1, ensure_ascii=False)
    words = sum(len(x["text"].split()) for x in s["scenes"])
    print(f"script written: '{s['title']}' — {len(s['scenes'])} scenes, {words} words")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
