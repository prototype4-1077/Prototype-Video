"""Pre-generate committed hero art for a build from build/<slug>/hero_manifest.json.

Manifest: {"heroes": {"05": "full image prompt", ...}, "key": 5}
Writes hero_NN_raw.jpg for every entry plus hero.jpg (copy of `key`).
LOUD failure: exits 1 if any image is missing after retries - never silently
downgrades the package the way runtime fallback used to.
"""
import json, os, shutil, sys, time, urllib.parse, urllib.request

def valid(path):
    return os.path.exists(path) and os.path.getsize(path) > 25_000

def gen(prompt, out, attempts=10):
    for a in range(attempts):
        seed = 41 + a * 137
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
               + f"?width=1280&height=720&nologo=true&model=flux&seed={seed}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=90).read()
            if len(data) > 25_000:
                with open(out, "wb") as fh:
                    fh.write(data)
                print(f"  {os.path.basename(out)}: ok ({len(data)//1024} KB, attempt {a+1})", flush=True)
                return True
            print(f"  {os.path.basename(out)}: tiny response, retrying", flush=True)
        except Exception as exc:
            print(f"  {os.path.basename(out)}: attempt {a+1} failed: {exc}", flush=True)
        time.sleep(8 + a * 4)
    return False

def main():
    slug = sys.argv[1]
    bd = f"build/{slug}"
    man = json.load(open(f"{bd}/hero_manifest.json", encoding="utf-8"))
    missing = []
    for idx, prompt in sorted(man["heroes"].items(), key=lambda kv: int(kv[0])):
        out = f"{bd}/hero_{int(idx):02d}_raw.jpg"
        if valid(out):
            print(f"  {os.path.basename(out)}: already committed", flush=True)
            continue
        if not gen(prompt, out):
            missing.append(idx)
    key = int(man.get("key", 0))
    key_file = f"{bd}/hero_{key:02d}_raw.jpg"
    if valid(key_file):
        shutil.copyfile(key_file, f"{bd}/hero.jpg")
    if missing:
        print(f"FAILED: {len(missing)} hero image(s) missing: {missing}", flush=True)
        sys.exit(1)
    print("all hero art committed", flush=True)

if __name__ == "__main__":
    main()
