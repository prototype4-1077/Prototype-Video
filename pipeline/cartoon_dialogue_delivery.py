"""Retry a verified AAC-only export failure without rerendering its picture."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil

from pipeline import cartoon_dialogue_scene as new


def pixel_code_hash(path: Path) -> str:
    # Parse, do not execute, the earlier job's source. The two actual pixel
    # adapters must be identical; only delivery/audit changes may be recovered.
    nodes = ast.parse(path.read_text(encoding="utf-8")).body
    selected = [node for node in nodes if isinstance(node, ast.FunctionDef) and node.name in ("runtime_prepared", "frames")]
    if len(selected) != 2:
        raise ValueError("Missing original pixel renderer functions")
    return hashlib.sha256("\n".join(ast.dump(node, include_attributes=False) for node in selected).encode()).hexdigest()


def recover(recipe: Path, previous: Path, output: Path, *, expected_picture_sha256: str, render_source: Path) -> dict:
    if output.exists():
        raise FileExistsError("Preserve existing export; select a NEW directory")
    plan = new.compile_scene(recipe)
    if json.loads((previous / "failure.json").read_text())["error"] != "AAC preview quality/headroom failed":
        raise ValueError("Only the observed AAC-quality failure is recoverable here")
    picture = previous / "silent.mp4"
    if new.scene._hash(picture) != expected_picture_sha256:
        raise ValueError("Prior picture changed")
    if pixel_code_hash(render_source) != pixel_code_hash(Path(new.__file__)):
        raise ValueError("Pixel renderer changed; this is not an export-only recovery")
    motion = json.loads((previous / "compiled-motion-v1.json").read_text())
    if motion["performance_id"] != plan["config"]["id"] or motion["frame_count"] != plan["frame_count"] or motion["keyframes"] != plan["keyframes"]:
        raise ValueError("Prior picture used a different authored scene plan")
    if new.scene._video_hash(picture, "ffmpeg") != new.scene._video_hash(previous / "scene.mov", "ffmpeg"):
        raise ValueError("Prior MOV changed the rendered picture")
    approved = new.bank.approval()
    # Run all inherited source-asset loaders again. No rendering is needed.
    validated = new.scene.integration.prepare_repaired_acting()
    del validated
    count = plan["frame_count"]
    samples = sorted({1, count//4, count//2, count*3//4, count, *[start+5 for start in plan["blink_starts"]]})
    for number in samples:
        if not (previous / "references" / f"f{number:04d}.png").is_file():
            raise ValueError("Missing actual source reference pixels")
    output.mkdir(parents=True)
    try:
        shutil.copytree(previous / "references", output / "references")
        for name in ("scene.mov", "silent.mp4", "compiled-motion-v1.json"):
            shutil.copyfile(previous / name, output / name)
        new.scene._run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-i", str(output / "scene.mov"),
                       "-c:v", "copy", "-c:a", "aac", "-b:a", new.AAC_BITRATE,
                       "-movflags", "+faststart+write_colr", str(output / "scene.mp4")], output / "mux-mp4.log")
        measured = new.audit(output, plan, samples)
        if new.bank.approval() != approved or new.compile_scene(recipe)["recipe_sha256"] != plan["recipe_sha256"]:
            raise ValueError("Source recipe or frozen components changed during recovery")
        report = {"classification": "NEW_AUDIO_CLOCKED_AUTHORED_SCENE_TECHNICALLY_COMPLETE_HUMAN_REVIEW_PENDING",
                  "scene_id": plan["config"]["id"], "frame_count": count, "duration_seconds": count/30,
                  "recipe_sha256": plan["recipe_sha256"], "audio": plan["config"]["audio"], "cues": plan["config"]["cues"],
                  "source_built": True, "accepted_first_scene_cache_used": False,
                  "current_job_picture_reused_after_audio_only_failure": True,
                  "previous_picture_sha256": expected_picture_sha256,
                  "original_render_source_sha256": new.scene._hash(render_source),
                  "pixel_renderer_ast_sha256": pixel_code_hash(render_source),
                  "delivery_source_sha256": new.scene._hash(Path(__file__)),
                  "auditor_source_sha256": new.scene._hash(Path(new.__file__)),
                  "new_aac_bitrate": new.AAC_BITRATE, "picture_reencoded": False, "audit": measured,
                  "cash_cost": 0, "network_calls": 0,
                  "voice_status": "LOCAL_SCRATCH_NON_CANONICAL_NOT_HUMAN_ACCEPTED",
                  "new_performance_human_accepted": False, "production_release_allowed": False, "main_branch_merge_allowed": False,
                  "source_raw_all_frame_inventory_available": False,
                  "inventory_limit": "The initial renderer saved native inventory after its audio gate and exited before writing it. All207 decoded preview frame hashes and six actual raw reference PNGs are retained instead; decoded hashes are not claimed as raw source pixels. Future builds now save native inventory before export.",
                  "limits": ["One porch view/resting hand pose, not full-body action or a new camera angle.",
                             "New voice/head/camera/blink performance remains human-unaccepted."],
                  "artifacts": {path.name: new.scene._hash(path) for path in output.iterdir() if path.is_file()}}
        new.scene._json(output / "new-scene-report.json", report)
        print(f"New authored scene delivery passed: {output / 'scene.mp4'}", flush=True)
        return report
    except BaseException as exc:
        new.scene._json(output / "failure.json", {"error": str(exc), "prior_job_preserved": True})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--render-source", type=Path, required=True)
    parser.add_argument("--expected-picture-sha256", required=True)
    args = parser.parse_args()
    recover(args.scene, args.previous, args.output, expected_picture_sha256=args.expected_picture_sha256, render_source=args.render_source)


if __name__ == "__main__":
    main()
