from __future__ import annotations

import json
import pathlib

build = pathlib.Path(__file__).resolve().parent
path = build / "script.json"
script = json.loads(path.read_text(encoding="utf-8"))
queries = [
    "cinematic aerial highway interchange at dusk with real traffic visibly splitting into several directions, genuine stock video, no animation, no text",
    "close-up stock footage of a hand sliding an unsigned job offer paper away on an office desk and putting down a pen, natural window light, no face, no readable company text",
    "close-up stock footage of one hand holding a smartphone, finger hovers over call button then pulls away, genuine screen and hand motion, no face, no readable contact",
    "cinematic stock footage of suitcase on train platform as real train departs toward city skyline at golden hour, genuine motion, no close faces",
    "cinematic stock footage from behind one adult at a busy pedestrian intersection while crowds cross in different directions, real traffic and people motion, no close faces",
    "cinematic stock footage of station clock reflected in glass while train and commuters move past, real repeating reflections, no close faces",
    "cinematic stock footage of sleeping adult near window while moving city lights and curtains cross the room, readable natural night light, no graphics",
    "close-up stock footage of a hand holding an old photograph above an empty picture frame then lowering it, natural light and reflections, no face, no readable text",
    "close-up stock footage of artist hand drawing in notebook beside an open landscape, rack focus between drawing and real scenery, no face",
    "macro stock footage of photographic film negatives moving across a bright light table, mechanical reel motion and rack focus, no people",
    "cinematic stock footage from behind one person walking down a single straight road between walls in golden light, genuine body and environmental motion, no close face",
    "high aerial stock footage of circular city plaza with many real pedestrians leaving along radiating streets, clear geometry and continuous movement",
    "macro stock footage of real camera lens rotating from blur into sharp focus, warm practical light, no digital graphics",
    "cinematic stock footage of traveler lowering binoculars and folding a paper map as real landscape comes into focus, face not visible, genuine natural motion",
    "macro stock footage of domino chain falling until one piece redirects the chain onto a different branch, real practical object motion, no animation",
    "cinematic stock footage from behind one adult walking past real glass reflections and into clear morning light, continuous walking and reflection motion, no close face",
]
policy = script.get("visual_policy") if isinstance(script.get("visual_policy"), dict) else {}
policy.update({
    "mode": "diverse_symbols",
    "max_human_ratio": 0.95,
    "max_family_run": 4,
    "max_generic_human_run": 1,
    "min_families": 6,
})
script["visual_policy"] = policy
script["max_still_source_ratio"] = 0.0
script["minimum_true_motion_ratio"] = 1.0
script["stock_only"] = True
script["allow_generated_visuals"] = False
for scene, query in zip(script.get("scenes") or [], queries):
    scene["query"] = query
    scene.pop("symbol_query", None)
    for field in (
        "hero", "image_prompt", "source_image", "keyframes", "symbolic_kind",
        "pexels_id", "stock_id", "clip", "motion_source", "motion_kind",
        "motion_mode", "motion_verified", "motion_evidence", "source_url",
        "source_title", "stock_frame_url", "portrait_symbolic_render_version",
    ):
        scene.pop(field, None)
path.write_text(json.dumps(script, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("Prepared broader literal stock-only contingency with no inherited sources or graphics.")
