"""Offline, source-built June Oxley prototype using the provisionally passed rig.

Reuse the existing complete-scene builder, encoder and media audits. Only its
frame source and output name are temporarily injected; the locked builder and
all prior proof files stay unchanged. No external prior-render cache is read.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Any, Iterator

import cv2
import numpy as np
import PIL

from pipeline import cartoon_mouth_semantics_refinement as mouth
from pipeline import cartoon_hand_motion_refinement as hand
from pipeline import cartoon_source_opening as opening


scene = mouth.scene
REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = REPO_ROOT / "concept/characters/june_oxley_working_model_component_acceptance_v1.json"
ACCEPTANCE_SHA256 = "36a1f16b5a3deb1a84dc4896f02b058ce6946a83c40872ab22611833c2a4c6f0"
NAME = "june-working-prototype-v1"


def approval(path: Path = ACCEPTANCE) -> dict[str, Any]:
    if scene._hash(path) != ACCEPTANCE_SHA256:
        raise ValueError("working-model provisional component binding changed")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["status"] != "provisional_pass_for_working_prototype_polish_deferred":
        raise ValueError("working prototype lacks James's provisional component pass")
    scope = data["scope"]
    if not scope["passed_mouth_hand_reuse_allowed"] or not scope["source_built_full_prototype_allowed"]:
        raise ValueError("working prototype reuse/source-build scope is not allowed")
    for key in ("full_performance_final_acceptance", "production_release_allowed", "main_branch_merge_allowed"):
        if scope[key] is not False:
            raise ValueError("provisional component pass cannot grant production or main promotion")
    for key in ("verdict", "reviewed_comparison", "mouth_adapter", "hand_adapter", "eye_audio_acceptance"):
        item = data[key]
        target = (REPO_ROOT / item["path"]).resolve()
        if not target.is_relative_to(REPO_ROOT.resolve()) or scene._hash(target) != item["sha256"]:
            raise ValueError(f"provisional pass source drift: {key}")
    scene.accepted_components()
    return data


def preflight() -> dict[str, Any]:
    passed = approval()
    tools = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    if not all(tools.values()):
        raise ValueError("FFmpeg and FFprobe must be installed locally and on PATH; no service/API fallback")
    versions = {name: subprocess.run([str(path), "-version"], check=True, capture_output=True, text=True).stdout.splitlines()[0]
                for name, path in tools.items()}
    return {"classification": "LOCAL_RUNTIME_AND_PRIMARY_INPUT_CHECK_PASSED",
            "cash_cost": 0, "network_required": False, "api_keys_required": False,
            "external_prior_scene_cache_required": False, "clock": {"width": 1920, "height": 1080,
            "fps": 30, "frame_count": 303, "duration_seconds": 10.1},
            "scope": passed["scope"], "opening": opening.preflight(),
            "runtime": {"python": platform.python_version(), "numpy": np.__version__,
                        "pillow": PIL.__version__, "opencv": cv2.__version__, **versions},
            "note": "Primary inputs/tools checked without rendering. The build also validates/decode-checks the deeper locked face/body graph and final media."}


def working_frames(prepared: Any) -> Iterator[tuple[int, np.ndarray, dict[str, Any]]]:
    stream = opening.frames()
    try:
        for number, pixels, metrics in stream:
            yield number, pixels, {**metrics, "original_pour_pixels_preserved": True,
                                    "pour_source_frame": metrics["source_frame"], "built_from_tracked_source": True}
    finally:
        stream.close()
    direct = prepared.integration.direct
    candidate_direct = replace(direct, visemes=mouth.translated_plan(direct.visemes), native_cache={}, adapter_cache={})
    candidate = replace(prepared, integration=replace(prepared.integration, direct=candidate_direct))
    with scene.accepted_lids(candidate):
        for frame in range(1, 229):
            with hand.hand_override(candidate.integration.body, frame):
                pixels, metrics = scene.compose_direct_frame(candidate, frame)
            yield frame + 75, pixels, {**metrics, "mouth_hand_provisionally_passed": True,
                                      "mouth_cue_times_unchanged": True, "hand_adapter_active": 91 <= frame < 148,
                                      "built_from_tracked_source": True}


@contextmanager
def source_build_context() -> Iterator[None]:
    original_source, original_name = scene.scene_frames, scene.NAME
    scene.scene_frames, scene.NAME = working_frames, NAME
    try:
        yield
    finally:
        scene.scene_frames, scene.NAME = original_source, original_name


def build(output: Path) -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"preserve existing output; choose a new directory: {output}")
    checked = preflight()
    approved = approval()
    print("Building the complete scene from tracked artwork and passed components. No prior-render cache or paid service.", flush=True)
    try:
        with source_build_context():
            internal = scene.build(output)
        if approval() != approved or opening.preflight() != checked["opening"]:
            raise ValueError("approved source inputs changed during the build")
        report = {"version": 1, "classification": "WORKING_SOURCE_BUILT_CARTOON_PROTOTYPE",
                  "technical_build_completed": True, "cash_cost": 0, "network_calls": 0,
                  "api_keys_required": False, "external_prior_scene_cache_used": False,
                  "frame_count": internal["frame_count"], "duration_seconds": internal["duration_seconds"],
                  "hard_cut_output_frames": internal["hard_cut_output_frames"],
                  "component_pass": approved, "component_pass_file_sha256": scene._hash(ACCEPTANCE),
                  "primary_input_check": checked, "provisional_polish_deferred": True,
                  "full_performance_final_acceptance": False, "production_release_allowed": False,
                  "main_branch_merge_allowed": False,
                  "entrypoint_source_sha256": scene._hash(Path(__file__)),
                  "reused_scene_builder_sha256": scene._hash(Path(scene.__file__)),
                  "opening_adapter_lf_sha256": checked["opening"]["adapter_lf_sha256"],
                  "scene_audit_report": {"path": "phase42-integrated-scene-review-report-v1.json",
                                         "sha256": scene._hash(output / "phase42-integrated-scene-review-report-v1.json")},
                  "movie": {"path": f"{NAME}.mp4", "sha256": scene._hash(output / f"{NAME}.mp4")},
                  "exact_audio_copy": {"path": f"{NAME}.mov", "sha256": scene._hash(output / f"{NAME}.mov")},
                  "limits": ["One fixed, authored 10.1-second three-shot scene; not arbitrary script-to-cartoon generation.",
                             "Source-art 2.5D acting, not a free-turning 3-D character or episode-scale production system.",
                             "Mouth/hand passed provisionally for the prototype; later polish and whole-film quality remain open.",
                             "Encoded H.264 picture; MOV preserves accepted PCM audio, not a lossless-picture master."]}
        scene._json(output / "working-model-report-v1.json", report)
        print(f"Prototype ready: {output / (NAME + '.mp4')}", flush=True)
        return report
    except BaseException as exc:
        if output.exists():
            scene._json(output / "working-model-failure.json", {"technical_build_completed": False,
                        "error": str(exc), "artifacts_preserved": True, "production_release_allowed": False})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check local tools and primary inputs without rendering")
    parser.add_argument("--output", type=Path, help="NEW output directory; default is a timestamped folder under outputs/edit")
    args = parser.parse_args()
    if args.check:
        checked = preflight()
        print(json.dumps({key: checked[key] for key in ("classification", "cash_cost", "api_keys_required", "external_prior_scene_cache_required", "clock", "runtime")}, indent=2))
    else:
        destination = args.output or REPO_ROOT / "outputs/edit" / ("june-prototype-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
        build(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
