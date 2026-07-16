from __future__ import annotations

import json
import pathlib
import sys

build = pathlib.Path(__file__).resolve().parent
script = json.loads((build / "script.json").read_text(encoding="utf-8"))
scenes = script.get("scenes") or []

allowed_sources = {
    "pexels", "coverr", "mixkit", "pixabay", "nasa", "ia", "internet_archive",
    "wikimedia", "wm", "commons", "stock",
}
forbidden_fields = {
    "hero", "image_prompt", "source_image", "keyframes", "symbolic_kind",
    "portrait_symbolic_render_version", "deterministic_symbolic",
}
failures: list[str] = []
rows: list[dict] = []

if script.get("allow_generated_visuals") is not False:
    failures.append("allow_generated_visuals must be false")
if float(script.get("max_still_source_ratio", 1.0)) != 0.0:
    failures.append("max_still_source_ratio must be exactly zero")

for index, scene in enumerate(scenes):
    source = str(scene.get("motion_source") or "").strip().lower()
    stock_id = scene.get("stock_id") or scene.get("pexels_id")
    kind = str(scene.get("motion_kind") or "").strip().lower()
    mode = str(scene.get("motion_mode") or "").strip().lower()
    verified = scene.get("motion_verified") is True
    present_forbidden = sorted(key for key in forbidden_fields if scene.get(key) not in (None, False, [], ""))
    source_allowed = source in allowed_sources or source.startswith(("nasa", "ia", "wm", "coverr", "mixkit", "pexels", "pixabay"))
    clip = build / f"clip_{index:02d}.mp4"
    row = {
        "index": index,
        "source": source,
        "stock_id": stock_id,
        "kind": kind,
        "mode": mode,
        "motion_verified": verified,
        "clip_exists": clip.exists() and clip.stat().st_size > 100_000,
        "forbidden_fields": present_forbidden,
    }
    row["passed"] = all((
        source_allowed,
        bool(stock_id),
        kind == "video",
        mode == "stock",
        verified,
        row["clip_exists"],
        not present_forbidden,
    ))
    rows.append(row)
    if not row["passed"]:
        failures.append(f"scene {index} is not verified genuine stock: {row}")

motion_path = build / "motion_report.json"
if not motion_path.exists():
    failures.append("motion_report.json is missing")
    motion = {}
else:
    motion = json.loads(motion_path.read_text(encoding="utf-8"))
    if float(motion.get("still_source_ratio", 1.0)) != 0.0:
        failures.append(f"still_source_ratio is {motion.get('still_source_ratio')}, expected 0.0")
    if float(motion.get("true_motion_ratio", 0.0)) < 0.999:
        failures.append(f"true_motion_ratio is {motion.get('true_motion_ratio')}, expected 1.0")
    bad_motion_sources = [
        row for row in motion.get("scenes", [])
        if str(row.get("source") or "").lower() in {
            "deterministic_symbolic", "generated", "hero", "animated_still", "static"
        }
    ]
    if bad_motion_sources:
        failures.append(f"motion report contains forbidden sources: {bad_motion_sources}")

for required in (
    "final.mp4", "scene-review.html", "scene-review.json", "music_variants.json",
    "visual_symbol_report.json", "CREDITS.txt",
):
    path = build / required
    if not path.exists() or path.stat().st_size == 0:
        failures.append(f"required output missing or empty: {required}")

report = {
    "schema_version": 1,
    "slug": script.get("slug"),
    "policy": "genuine_stock_only_no_generated_graphics_no_stills",
    "passed": not failures and len(rows) == len(scenes) == 16,
    "scene_count": len(rows),
    "allowed_sources": sorted(allowed_sources),
    "failures": failures,
    "scenes": rows,
    "motion_summary": {
        "still_source_ratio": motion.get("still_source_ratio"),
        "true_motion_ratio": motion.get("true_motion_ratio"),
    },
}
(build / "stock-only-report.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
print(json.dumps(report, indent=2, ensure_ascii=False))
if not report["passed"]:
    raise SystemExit("ERROR: genuine-stock-only gate failed")
