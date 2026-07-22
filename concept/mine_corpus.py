"""Regenerate concept/patterns.json weights from the live script corpus.
Usage: python3 concept/mine_corpus.py   (run from repo root)"""
import json, glob, os, collections

PILLARS = {
 "grounding":["room","kitchen","morning","body","breath","hands","door","home","ordinary"],
 "self":["ego","identity","self","mask","observer","witness","who you are"],
 "belief":["belief","true","truth","coherence","evidence","proof","assume","know"],
 "attention":["attention","focus","aim","notice","looking","present","awareness"],
 "mediation":["lens","window","mirror","glass","filter","map","screen","veil"],
 "memory":["memory","remember","recall","reconsolid","edit","rewrite","save","footage"],
 "prediction":["predict","forecast","lag","behind","future","anticipat","expect"],
 "emotion":["love","gratitude","grace","fear","worry","tender"],
 "machine":["machine","render","engine","loading","circuit","processor","graphics"],
 "recursion":["itself","recursion","loop","reflect","infinite","paradox"],
 "threshold":["dmt","dissolve","unravel","ego death","void","threshold","entity","breakthrough"],
}

def corpus_text():
    out=[]
    for f in sorted(glob.glob("build/*/script.json")):
        try: s=json.load(open(f))
        except Exception: continue
        scenes=s.get("scenes") or []
        t=" ".join(sc.get("text","") for sc in scenes)
        if len(t.split())>=40: out.append(t.lower())
    return out

def main():
    texts=corpus_text(); blob=" ".join(texts)
    weights={p:sum(blob.count(k) for k in kw) for p,kw in PILLARS.items()}
    print(f"corpus: {len(texts)} scripts, {sum(len(t.split()) for t in texts)} words")
    for p,w in sorted(weights.items(), key=lambda x:-x[1]):
        print(f"  {w:4d}  {p}")

if __name__=="__main__":
    main()
