#!/usr/bin/env python3
"""Export render and scene-feedback evidence to a FiftyOne-compatible manifest."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build"
DEFAULT_OUT = ROOT / "concept" / "visual_memory"

sys.path.insert(0, str(ROOT / "pipeline"))
from visual_risk import assess_scene  # noqa: E402


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def feedback_for(build_dir: Path, count: int) -> tuple[dict[int, dict[str, Any]], str | None]:
    candidates = [
        build_dir / "scene-feedback.request.json",
        build_dir / "scene-review-feedback.json",
        build_dir / "scene-review.json",
    ]
    for path in candidates:
        payload = load(path, {})
        scenes = payload.get("scenes") if isinstance(payload, dict) else None
        if not isinstance(scenes, list):
            continue
        output: dict[int, dict[str, Any]] = {}
        for item in scenes:
            if not isinstance(item, dict):
                continue
            index = item.get("scene_index", item.get("index"))
            try:
                index = int(index)
            except (TypeError, ValueError):
                continue
            if 0 <= index < count:
                output[index] = item
        return output, path.name
    return {}, None


def failure_tags(comment: str, scene: dict[str, Any], risk: dict[str, Any]) -> list[str]:
    text = " ".join(
        [comment, str(scene.get("revision_note") or "")]
    ).lower()
    patterns = {
        "extra_or_fused_fingers": ("extra finger", "fused finger", "malformed finger"),
        "deformed_anatomy": ("deform", "anatom", "limb", "hand looks"),
        "object_contact_failure": ("incoherent", "contact", "grasp", "interaction"),
        "muddy_or_unclear": ("muddy", "unclear", "difficult to parse", "confusing"),
        "synthetic_appearance": ("synthetic", "fake-looking", "ai-looking"),
        "semantic_mismatch": ("does not match", "wrong", "unrelated"),
        "title_or_caption_occlusion": ("title", "caption", "cut off", "covering"),
    }
    tags = [name for name, cues in patterns.items() if any(cue in text for cue in cues)]
    tags.extend(item["code"] for item in risk.get("findings") or [])
    return sorted(set(tags))


def asset_candidates(build_dir: Path, index: int, scene: dict[str, Any]) -> list[Path]:
    values = []
    for key in ("enhanced_source_image", "clip"):
        if scene.get(key):
            path = Path(str(scene[key]))
            values.append(path if path.is_absolute() else build_dir / path.name)
    values.extend([
        build_dir / f"hero_{index:02d}.jpg",
        build_dir / f"hero_{index:02d}_raw.jpg",
        build_dir / f"clip_{index:02d}.mp4",
    ])
    seen = set()
    return [path for path in values if not (str(path) in seen or seen.add(str(path)))]


def make_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not BUILD.exists():
        return records
    for script_path in sorted(BUILD.glob("*/script.json")):
        build_dir = script_path.parent
        script = load(script_path, {})
        scenes = script.get("scenes") or []
        if not isinstance(scenes, list):
            continue
        feedback, feedback_file = feedback_for(build_dir, len(scenes))
        for index, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                continue
            review = feedback.get(index, {})
            decision = str(review.get("decision") or "unreviewed").lower()
            comment = str(review.get("comments") or "").strip()
            risk = assess_scene(scene, index)
            assets = asset_candidates(build_dir, index, scene)
            existing = next((path for path in assets if path.exists()), None)
            record = {
                "id": f"{script.get('slug', build_dir.name)}:{index}",
                "slug": script.get("slug", build_dir.name),
                "title": script.get("title"),
                "scene_index": index,
                "scene_number": index + 1,
                "narration": scene.get("text"),
                "semantic_anchor": scene.get("semantic_anchor"),
                "query": scene.get("query"),
                "image_prompt": scene.get("image_prompt"),
                "visual_function": scene.get("visual_function"),
                "symbol_family": scene.get("symbol_family"),
                "generation_route": scene.get("generation_route") or scene.get("motion_mode"),
                "provider": scene.get("motion_source") or scene.get("still_reference_generation_model"),
                "workflow_id": scene.get("comfy_workflow_id"),
                "seed": scene.get("seed"),
                "lower_model_safe": bool(scene.get("lower_model_safe")),
                "generation_constraints": scene.get("generation_constraints") or [],
                "risk": risk,
                "decision": decision,
                "comment": comment,
                "feedback_file": feedback_file,
                "failure_tags": failure_tags(comment, scene, risk),
                "asset_path": str(existing.relative_to(ROOT)) if existing else None,
                "asset_sha256": sha256(existing) if existing else None,
                "asset_bytes": existing.stat().st_size if existing else None,
                "exported_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            }
            records.append(record)
    return records


def write_manifest(records: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "manifest.jsonl"
    manifest.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8",
    )
    decisions: dict[str, int] = {}
    failures: dict[str, int] = {}
    for item in records:
        decisions[item["decision"]] = decisions.get(item["decision"], 0) + 1
        for tag in item["failure_tags"]:
            failures[tag] = failures.get(tag, 0) + 1
    summary = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "records": len(records),
        "with_assets": sum(bool(item["asset_path"]) for item in records),
        "decisions": dict(sorted(decisions.items())),
        "failure_tags": dict(sorted(failures.items(), key=lambda pair: (-pair[1], pair[0]))),
        "note": "Scene feedback is higher-trust craft evidence than automated visual-risk tags.",
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def import_fiftyone(records: list[dict[str, Any]], dataset_name: str) -> None:
    try:
        import fiftyone as fo
    except ImportError as exc:
        raise SystemExit("FiftyOne is not installed; pip install fiftyone") from exc

    if dataset_name in fo.list_datasets():
        fo.delete_dataset(dataset_name)
    dataset = fo.Dataset(dataset_name)
    samples = []
    for item in records:
        if not item.get("asset_path"):
            continue
        path = ROOT / item["asset_path"]
        if not path.exists():
            continue
        sample = fo.Sample(filepath=str(path))
        for key, value in item.items():
            if key not in {"asset_path", "risk"}:
                sample[key] = value
        sample["risk_json"] = json.dumps(item["risk"], ensure_ascii=False)
        samples.append(sample)
    if samples:
        dataset.add_samples(samples)
    dataset.persistent = True
    print(f"FiftyOne dataset {dataset_name}: {len(samples)} media samples")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--import-fiftyone", action="store_true")
    parser.add_argument("--dataset-name", default="prototype_video_visual_memory")
    args = parser.parse_args()

    records = make_records()
    write_manifest(records, Path(args.out_dir))
    if args.import_fiftyone:
        import_fiftyone(records, args.dataset_name)
    print(f"visual memory: {len(records)} scene records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
