from __future__ import annotations

import json
import pathlib

build = pathlib.Path(__file__).resolve().parent
path = build / "script.json"
script = json.loads(path.read_text(encoding="utf-8"))
policy = script.get("visual_policy")
if not isinstance(policy, dict):
    policy = {"mode": "diverse_symbols"}
policy.update({
    "mode": "diverse_symbols",
    "max_human_ratio": 0.80,
    "max_family_run": 3,
    "max_generic_human_run": 1,
    "min_families": 6,
})
script["visual_policy"] = policy
script["max_still_source_ratio"] = 0.0
script["minimum_true_motion_ratio"] = 1.0
script["stock_only"] = True
script["allow_generated_visuals"] = False
for scene in script.get("scenes") or []:
    for field in (
        "hero", "image_prompt", "source_image", "keyframes", "symbolic_kind",
        "pexels_id", "stock_id", "clip", "motion_source", "motion_kind",
        "motion_mode", "motion_verified", "motion_evidence", "source_url",
        "source_title", "stock_frame_url", "portrait_symbolic_render_version",
    ):
        scene.pop(field, None)
path.write_text(json.dumps(script, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("Prepared fresh stock-only script with no inherited source selections or generated-visual fields.")
