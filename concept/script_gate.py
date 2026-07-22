"""Pre-render integrity gate for concept-led scripts.

This gate does not decide whether an idea is true. It catches preventable handoff
errors: duplicated narration, impossible duration promises, overlong scenes,
untraceable evidence labels, excess hero stills, and visual keywords that do not
appear in the spoken line.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys


VALID_ROLES = {"evidence", "interpretation", "metaphor", "speculation", "invitation"}


def load_json(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", text, flags=re.UNICODE))


def validate(script_path: str, evidence_path: str | None = None) -> dict:
    script = load_json(script_path)
    scenes = script.get("scenes") or []
    if evidence_path is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(script_path))))
        evidence_path = os.path.join(repo_root, "concept", "evidence.json")
    evidence = load_json(evidence_path) if os.path.exists(evidence_path) else {"sources": {}}
    known_sources = set((evidence.get("sources") or {}).keys())
    failures = []
    warnings = []

    if not script.get("title") or not script.get("slug"):
        failures.append("script requires title and slug")
    if not scenes:
        failures.append("script has no scenes")

    texts = [str(scene.get("text") or "") for scene in scenes]
    words = sum(word_count(text) for text in texts)
    wps = float(script.get("estimated_words_per_second") or 2.1)
    estimate = words / max(wps, 0.1)
    target = float(script.get("target_duration_seconds") or 0)
    if target and abs(estimate - target) > max(15.0, target * 0.20):
        failures.append(
            f"estimated narration {estimate:.1f}s differs from target {target:.1f}s by more than tolerance"
        )

    for left in range(len(texts)):
        for right in range(left + 1, len(texts)):
            a, b = normalize(texts[left]), normalize(texts[right])
            if min(len(a.split()), len(b.split())) < 5:
                continue
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            if ratio >= 0.82:
                failures.append(f"near-duplicate narration in scenes {left} and {right} ({ratio:.0%})")

    hero_count = 0
    for index, scene in enumerate(scenes):
        text = texts[index]
        count = word_count(text)
        if count > 25:
            failures.append(f"scene {index} has {count} words (maximum 25)")
        role = scene.get("epistemic_role")
        if script.get("concept_id") and role not in VALID_ROLES:
            failures.append(f"scene {index} requires epistemic_role ({', '.join(sorted(VALID_ROLES))})")
        source_ids = [str(item) for item in scene.get("source_ids") or []]
        if role == "evidence" and not source_ids:
            failures.append(f"scene {index} is evidence but has no source_ids")
        unknown = sorted(set(source_ids) - known_sources)
        if unknown:
            failures.append(f"scene {index} references unknown source_ids: {', '.join(unknown)}")

        keywords = [normalize(str(item)) for item in scene.get("keywords") or [] if normalize(str(item))]
        spoken = normalize(text)
        if keywords and not any(re.search(r"(?<!\w)" + re.escape(item) + r"(?!\w)", spoken) for item in keywords):
            failures.append(f"scene {index} has no spoken keyword matching its visual keywords")

        if scene.get("hero"):
            hero_count += 1
            if not scene.get("image_prompt"):
                failures.append(f"scene {index} is a hero without image_prompt")

    if script.get("concept_id") and hero_count > 4:
        failures.append(f"script has {hero_count} hero stills (maximum 4)")
    if script.get("render_outputs") and script.get("render_outputs") != ["youtube"]:
        warnings.append("additional canvases requested; confirm they were explicitly requested")

    concept_id = script.get("concept_id")
    claim = (evidence.get("claims") or {}).get(concept_id) if concept_id else None
    if concept_id and not claim:
        failures.append(f"concept_id {concept_id!r} has no claim record in evidence.json")

    return {
        "passed": not failures,
        "script": os.path.normpath(script_path),
        "scenes": len(scenes),
        "words": words,
        "estimated_duration_seconds": round(estimate, 1),
        "hero_count": hero_count,
        "failures": failures,
        "warnings": warnings,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script")
    parser.add_argument("--evidence")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = validate(args.script, args.evidence)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        state = "PASS" if report["passed"] else "FAIL"
        print(
            f"{state}: {report['scenes']} scenes, {report['words']} words, "
            f"~{report['estimated_duration_seconds']}s, {report['hero_count']} heroes"
        )
        for item in report["failures"]:
            print(f"ERROR: {item}")
        for item in report["warnings"]:
            print(f"WARN: {item}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
