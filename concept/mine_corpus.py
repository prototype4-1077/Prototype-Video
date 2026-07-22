"""Build a reproducible concept map from canonical scripts.

The old miner counted raw substrings across every build directory. That made
versioned copies look like independent evidence and could not surface a pattern
that was not already named in the pillar dictionary. This version:

* chooses one canonical build per normalized title;
* counts pillar terms on word boundaries;
* discovers recurring two- and three-word phrases;
* reports recurring conceptual tensions; and
* can rewrite ``concept/patterns.json`` with auditable corpus metadata.

Usage:
    python3 concept/mine_corpus.py
    python3 concept/mine_corpus.py --write
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import json
import os
import re


PILLARS = {
    "grounding": ["room", "kitchen", "morning", "body", "breath", "hands", "door", "home", "ordinary"],
    "self": ["ego", "identity", "self", "mask", "observer", "witness", "who you are"],
    "belief": ["belief", "true", "truth", "coherence", "evidence", "proof", "assume", "know"],
    "attention": ["attention", "focus", "aim", "notice", "looking", "present", "awareness"],
    "mediation": ["lens", "window", "mirror", "glass", "filter", "map", "screen", "veil"],
    "memory": ["memory", "remember", "recall", "reconsolidation", "edit", "rewrite", "save", "footage"],
    "prediction": ["predict", "prediction", "forecast", "lag", "behind", "future", "anticipate", "expect"],
    "emotion": ["love", "gratitude", "grace", "fear", "worry", "tender", "grief"],
    "machine": ["machine", "render", "engine", "loading", "circuit", "processor", "graphics"],
    "recursion": ["itself", "recursion", "loop", "reflect", "infinite", "paradox"],
    "threshold": ["dmt", "dissolve", "unravel", "ego death", "void", "threshold", "entity", "breakthrough"],
}

TENSIONS = {
    "inside / outside": (["inside", "within", "inner"], ["outside", "outer", "world"]),
    "fixed / changing": (["fixed", "permanent", "unchanging"], ["change", "changing", "rewrite", "becoming"]),
    "control / surrender": (["control", "command", "choose"], ["surrender", "release", "let go"]),
    "evidence / belief": (["evidence", "proof", "test"], ["belief", "faith", "assume"]),
    "alone / connected": (["alone", "lonely", "separate"], ["together", "connected", "relationship", "love"]),
    "fear / wonder": (["fear", "panic", "dread"], ["wonder", "awe", "curious"]),
    "real / constructed": (["real", "reality", "true"], ["construct", "render", "model", "story"]),
}

STOPWORDS = {
    "and", "are", "but", "can", "did", "does", "for", "has", "her", "him", "his", "how",
    "not", "one", "our", "out", "she", "the", "was", "were", "who", "why", "you",
    "about", "after", "again", "against", "also", "another", "because", "before", "being",
    "between", "could", "does", "doing", "every", "from", "have", "into", "itself", "just",
    "more", "most", "never", "only", "other", "over", "same", "some", "something", "still",
    "than", "that", "their", "them", "then", "there", "these", "they", "this", "those", "through",
    "under", "very", "what", "when", "where", "which", "while", "with", "would", "your", "youre",
    "didn", "doesn", "don", "hadn", "hasn", "isn", "wasn", "weren", "won", "wouldn",
}


def read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def script_text(script: dict) -> str:
    return " ".join(str(scene.get("text") or "") for scene in script.get("scenes") or []).strip()


def normalize_title(script: dict, path: str) -> str:
    title = str(script.get("title") or script.get("slug") or os.path.basename(os.path.dirname(path)))
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def production_score(path: str, script: dict, published: set[str]) -> tuple:
    build_dir = os.path.dirname(path)
    slug = str(script.get("slug") or os.path.basename(build_dir))
    status = read_json(os.path.join(build_dir, "render-status.json"), {}) or {}
    version_match = re.search(r"(?:^|-)v(\d+)$", slug)
    version = int(version_match.group(1)) if version_match else 0
    return (
        1 if slug in published else 0,
        1 if "final" in slug else 0,
        1 if status.get("state") == "done" else 0,
        1 if os.path.exists(os.path.join(build_dir, "scene-review.json")) else 0,
        version,
        len(script_text(script).split()),
        slug,
    )


def canonical_scripts(repo_root: str = ".") -> tuple[list[dict], dict]:
    published_data = read_json(os.path.join(repo_root, "pipeline", "published_videos.json"), {}) or {}
    published = set(published_data)
    groups: dict[str, list[tuple[str, dict]]] = collections.defaultdict(list)
    total_files = 0

    for path in sorted(glob.glob(os.path.join(repo_root, "build", "*", "script.json"))):
        script = read_json(path)
        if not isinstance(script, dict):
            continue
        total_files += 1
        if len(script_text(script).split()) < 40:
            continue
        groups[normalize_title(script, path)].append((path, script))

    selected = []
    duplicate_titles = {}
    for title_key, candidates in sorted(groups.items()):
        ranked = sorted(candidates, key=lambda item: production_score(item[0], item[1], published))
        path, script = ranked[-1]
        selected.append({
            "path": os.path.relpath(path, repo_root).replace("\\", "/"),
            "slug": script.get("slug") or os.path.basename(os.path.dirname(path)),
            "title": script.get("title"),
            "concept_id": script.get("concept_id"),
            "text": script_text(script).lower(),
        })
        if len(candidates) > 1:
            duplicate_titles[title_key] = [
                str(candidate.get("slug") or os.path.basename(os.path.dirname(candidate_path)))
                for candidate_path, candidate in candidates
            ]

    return selected, {
        "script_files": total_files,
        "qualifying_title_groups": len(groups),
        "canonical_scripts": len(selected),
        "deduplicated_files": sum(max(0, len(items) - 1) for items in groups.values()),
        "duplicate_titles": duplicate_titles,
    }


def count_term(text: str, term: str) -> int:
    pattern = r"(?<![a-z0-9])" + re.escape(term.lower()).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
    return len(re.findall(pattern, text.lower()))


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z']{2,}", text.lower())


def discover_phrases(texts: list[str], limit: int = 24) -> list[dict]:
    corpus_counts = collections.Counter()
    document_counts = collections.Counter()
    known_terms = {term for terms in PILLARS.values() for term in terms}

    for text in texts:
        tokens = tokenize(text)
        seen = set()
        for size in (2, 3):
            for index in range(len(tokens) - size + 1):
                words = tokens[index:index + size]
                if any(word in STOPWORDS for word in words):
                    continue
                phrase = " ".join(words)
                if phrase in known_terms:
                    continue
                corpus_counts[phrase] += 1
                seen.add(phrase)
        document_counts.update(seen)

    ranked = [
        (phrase, count, document_counts[phrase])
        for phrase, count in corpus_counts.items()
        if document_counts[phrase] >= 2
    ]
    ranked.sort(key=lambda item: (item[2], item[1], len(item[0])), reverse=True)
    return [
        {"phrase": phrase, "mentions": count, "scripts": documents}
        for phrase, count, documents in ranked[:limit]
    ]


def recurring_tensions(texts: list[str]) -> list[dict]:
    results = []
    for label, (left, right) in TENSIONS.items():
        scripts = sum(
            1 for text in texts
            if any(count_term(text, term) for term in left)
            and any(count_term(text, term) for term in right)
        )
        if scripts:
            results.append({"tension": label, "scripts": scripts})
    return sorted(results, key=lambda item: item["scripts"], reverse=True)


def frontier_coverage(scripts: list[dict]) -> dict[str, int]:
    coverage = collections.Counter(
        str(item["concept_id"]) for item in scripts if item.get("concept_id")
    )
    return dict(sorted(coverage.items()))


def build_snapshot(repo_root: str = ".") -> dict:
    existing_path = os.path.join(repo_root, "concept", "patterns.json")
    existing = read_json(existing_path, {}) or {}
    scripts, metadata = canonical_scripts(repo_root)
    texts = [item["text"] for item in scripts]
    blob = " ".join(texts)
    weights = {
        pillar: sum(count_term(blob, term) for term in terms)
        for pillar, terms in PILLARS.items()
    }

    pillars = []
    prior = {item.get("id"): item for item in existing.get("pillars") or []}
    for pillar_id in PILLARS:
        item = dict(prior.get(pillar_id) or {"id": pillar_id, "label": pillar_id.replace("_", " ").title()})
        item["weight"] = weights[pillar_id]
        pillars.append(item)
    pillars.sort(key=lambda item: item["weight"], reverse=True)

    metadata.update({
        "canonical_words": sum(len(text.split()) for text in texts),
        "generated_on": dt.date.today().isoformat(),
        "method": "canonical-title deduplication; boundary-aware pillar counts; 2-3 gram discovery",
    })
    return {
        "schema_version": 2,
        "_note": "Reproducible concept map. Frequency describes the corpus; it is not evidence that a belief is true or valuable.",
        "_meta": metadata,
        "pillars": pillars,
        "emergent_phrases": discover_phrases(texts),
        "recurring_tensions": recurring_tensions(texts),
        "frontier_coverage": frontier_coverage(scripts),
        "structural_signatures": existing.get("structural_signatures") or [],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite concept/patterns.json")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)
    snapshot = build_snapshot(args.repo_root)
    meta = snapshot["_meta"]
    print(
        f"corpus: {meta['canonical_scripts']} canonical scripts / "
        f"{meta['canonical_words']} words; deduplicated {meta['deduplicated_files']} files"
    )
    for pillar in snapshot["pillars"]:
        print(f"  {pillar['weight']:4d}  {pillar['id']}")
    print("emergent:", ", ".join(item["phrase"] for item in snapshot["emergent_phrases"][:8]))
    if args.write:
        path = os.path.join(args.repo_root, "concept", "patterns.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
