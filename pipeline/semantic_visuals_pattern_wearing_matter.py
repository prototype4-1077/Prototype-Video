"""Generate semantically exact custom motion scenes for Pattern Wearing Matter.

This deterministic scene source bypasses broad-topic stock selection. The generated
clips still pass through the standard TikTok Video Pipeline for captions, music,
voice mastering, Governor supervision, quality checks, artifacts, and Releases.
"""
from pathlib import Path
import importlib.util
import json
import sys

import motion


def load_renderer(repo_root: Path):
    source = repo_root / "build" / "pattern-wearing-matter-semantic-pipeline" / "render_semantic_assets.py"
    spec = importlib.util.spec_from_file_location("pwm_semantic_assets", source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load semantic renderer: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate(build_dir: str | Path) -> None:
    build = Path(build_dir).resolve()
    repo_root = Path(__file__).resolve().parents[1]
    module = load_renderer(repo_root)
    module.generate_all(build)
    script_path = build / "script.json"
    script = json.loads(script_path.read_text(encoding="utf-8"))
    for index, scene in enumerate(script["scenes"]):
        clip = build / f"clip_{index:02d}.mp4"
        if not clip.exists() or clip.stat().st_size < 100_000:
            raise RuntimeError(f"semantic clip missing or undersized: {clip}")
        evidence = motion.temporal_evidence(str(clip))
        if not evidence.get("passes"):
            raise RuntimeError(f"semantic clip {index} failed temporal-motion verification: {evidence}")
        evidence["provenance"] = "deterministic evolving frame sequence"
        scene.update({
            "clip": str(clip),
            "motion_kind": "video",
            "motion_mode": "recorded",
            "motion_source": "deterministic_semantic_animation",
            "motion_verified": True,
            "motion_evidence": evidence,
            "semantic_visual_locked": True,
        })
    script_path.write_text(json.dumps(script, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    generate(sys.argv[1])
