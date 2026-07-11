"""Autonomous scriptwriter: turns an idea into script.json via the Anthropic API.
Usage: python3 idea_writer.py <build_dir> "<idea text>"
Env: ANTHROPIC_API_KEY. Reads style_profile.md + memory.json (notes, motifs) so the
script sounds like James and obeys his standing feedback."""
import json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def _llm(prompt):
    """Anthropic if a key exists; otherwise pollinations.ai text API (keyless, free)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        req = urllib.request.Request("https://api.anthropic.com/v1/messages",
            data=json.dumps({"model": "claude-sonnet-5", "max_tokens": 4000,
                             "messages": [{"role": "user", "content": prompt}]}).encode(),
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"})
        out = json.loads(urllib.request.urlopen(req, timeout=180).read())
        return out["content"][0]["text"]
    last = None
    for _ in range(3):
        try:
            req = urllib.request.Request("https://text.pollinations.ai/",
                data=json.dumps({"model": "openai", "messages":
                                 [{"role": "user", "content": prompt}]}).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(req, timeout=180).read().decode()
        except Exception as e:
            last = e
    sys.exit(f"ERROR: free LLM unavailable ({last}) | FIX: rerun, or add ANTHROPIC_API_KEY secret")


def main(bd, idea):
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
    text = _llm(prompt).strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.M).strip()
    s = json.loads(text)
    os.makedirs(bd, exist_ok=True)
    json.dump(s, open(f"{bd}/script.json", "w"), indent=1, ensure_ascii=False)
    words = sum(len(x["text"].split()) for x in s["scenes"])
    print(f"script written: '{s['title']}' — {len(s['scenes'])} scenes, {words} words")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
