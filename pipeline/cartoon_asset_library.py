"""Versioned Blender asset-library contract and tiered visual-quality gate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from pipeline.cartoon_motion import RENDER_PROFILES
from pipeline.cartoon_performance_slice import validate_key_pose_timing
from pipeline.cartoon_vertical_slice import _assemble_video, _contact_sheet, _render_frames, compile_plan


ASSET_CONTRACT_VERSION = 1
REQUIRED_CHARACTER = "june_oxley"
REQUIRED_VISEMES = set("ABCDEFGHX")
REQUIRED_EXPRESSIONS = {"smile", "thoughtful", "soft_chuckle"}
REQUIRED_V2_CORRECTIVES = {"brow_raise", "brow_knit", "squint", "cheek_raise"}
FACIAL_GATE_VISEMES = tuple("ABCDEFGHX")
FACIAL_GATE_EXPRESSIONS = (
    "smile", "thoughtful", "soft_chuckle", "brow_raise", "brow_knit", "squint", "cheek_raise"
)
REQUIRED_BONES = {
    "root", "pelvis", "torso", "neck", "head",
    "upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R",
    "thigh.L", "shin.L", "foot.L", "thigh.R", "shin.R", "foot.R",
}
REQUIRED_V5_IK_TARGETS = {"hand_ik.L", "hand_ik.R", "foot_ik.L", "foot_ik.R"}
REQUIRED_V5_POLES = {"elbow_pole.L", "elbow_pole.R", "knee_pole.L", "knee_pole.R"}
REQUIRED_V5_CLAVICLES = {"clavicle.L", "clavicle.R"}
REQUIRED_V5_FACE_BONES = {"jaw", "eye.L", "eye.R", "gaze"}
REQUIRED_V5_FINGERS = {
    "finger.0.L", "finger.1.L", "finger.2.L", "finger.3.L", "thumb.L",
    "finger.0.R", "finger.1.R", "finger.2.R", "finger.3.R", "thumb.R",
}
REQUIRED_V5_PROPS = {"held_mug", "table_mug", "ledger", "pencil"}


def _string_set(value: Any, field: str) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return set(value)


def validate_asset_manifest(manifest: dict) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("asset manifest must be an object")
    if manifest.get("contract_version") != ASSET_CONTRACT_VERSION:
        raise ValueError(f"asset contract_version must be {ASSET_CONTRACT_VERSION}")
    if manifest.get("character_id") != REQUIRED_CHARACTER:
        raise ValueError("asset manifest must explicitly target june_oxley")
    version = str(manifest.get("asset_version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("asset_version must use semantic versioning")
    asset_major = int(version.split(".", 1)[0])
    delivery = manifest.get("delivery") or {}
    if delivery.get("format") != "blend" or delivery.get("generation") not in {
        "code_native_runtime_build", "artist_directed_runtime_build"
    }:
        raise ValueError("asset delivery must be a runtime-built blend library")
    collections = _string_set(delivery.get("collections"), "delivery.collections")
    if not {"CE_June_Oxley", "CE_June_Porch"}.issubset(collections):
        raise ValueError("asset library must expose June and porch collections")
    design = manifest.get("design_lock") or {}
    if "lean" not in str(design.get("body", "")).lower():
        raise ValueError("June's design lock must preserve his lean body type")
    forbidden = {item.lower() for item in _string_set(design.get("forbidden"), "design_lock.forbidden")}
    if "cowboy hat" not in forbidden or "spherical toy proportions" not in forbidden:
        raise ValueError("design lock must reject cowboy shorthand and spherical proxy proportions")
    bones = _string_set((manifest.get("rig") or {}).get("required_bones"), "rig.required_bones")
    missing_bones = sorted(REQUIRED_BONES - bones)
    if missing_bones:
        raise ValueError("asset rig missing bones: " + ", ".join(missing_bones))
    visemes = _string_set((manifest.get("face") or {}).get("visemes"), "face.visemes")
    if visemes != REQUIRED_VISEMES:
        raise ValueError("face.visemes must contain exactly A-H and X")
    expressions = _string_set((manifest.get("face") or {}).get("expression_controls"), "face.expression_controls")
    if not REQUIRED_EXPRESSIONS.issubset(expressions):
        raise ValueError("face is missing required expression controls")
    hands = manifest.get("hands") or {}
    if int(hands.get("minimum_digits_per_hand", 0)) < 5 or hands.get("contact_safe") is not True:
        raise ValueError("hands must provide five contact-safe digits per hand")
    gate = manifest.get("quality_gate") or {}
    if set(gate.get("profiles") or []) != set(RENDER_PROFILES):
        raise ValueError("quality gate must cover youtube and portrait")
    if int(gate.get("fps", 0)) != 30:
        raise ValueError("quality gate must use the shared 30 fps clock")
    if asset_major >= 2:
        if delivery.get("generation") != "artist_directed_runtime_build":
            raise ValueError("Hero v2 must use the artist-directed runtime builder")
        modeling = manifest.get("modeling") or {}
        if modeling.get("style") != "artist_directed_stylized_3d":
            raise ValueError("Hero v2 must declare the artist-directed stylized 3D standard")
        if "smooth" not in str(modeling.get("surface_standard", "")).lower():
            raise ValueError("Hero v2 must require smooth production surfaces")
        correctives = _string_set(modeling.get("corrective_shapes"), "modeling.corrective_shapes")
        if not REQUIRED_V2_CORRECTIVES.issubset(correctives):
            raise ValueError("Hero v2 is missing facial corrective shapes")
        if not REQUIRED_V2_CORRECTIVES.issubset(expressions):
            raise ValueError("Hero v2 face controls must expose every corrective shape")
        independent = _string_set((manifest.get("face") or {}).get("independent_controls"), "face.independent_controls")
        if not {"blink.L.upper", "blink.L.lower", "blink.R.upper", "blink.R.lower"}.issubset(independent):
            raise ValueError("Hero v2 must expose independent upper and lower eyelids")
        if hands.get("segmented_digits") is not True:
            raise ValueError("Hero v2 hands must use segmented digits")
        if gate.get("artifact_reopen_required") is not True or gate.get("human_art_approval_required") is not True:
            raise ValueError("Hero v2 requires artifact reopen and human art approval gates")
    if asset_major >= 3:
        modeling = manifest.get("modeling") or {}
        if modeling.get("head_topology") != "single_sculpted_surface":
            raise ValueError("Hero v3 must model the facial landmarks on one sculpted head surface")
        unified = _string_set(modeling.get("unified_surfaces"), "modeling.unified_surfaces")
        if not {"head", "plaid_torso", "open_denim_shell", "beard_patch"}.issubset(unified):
            raise ValueError("Hero v3 is missing required unified surfaces")
        if gate.get("facial_performance_matrix_required") is not True:
            raise ValueError("Hero v3 requires a facial performance matrix")
        matrix_visemes = _string_set(gate.get("matrix_visemes"), "quality_gate.matrix_visemes")
        matrix_expressions = _string_set(gate.get("matrix_expressions"), "quality_gate.matrix_expressions")
        if matrix_visemes != set(FACIAL_GATE_VISEMES) or matrix_expressions != set(FACIAL_GATE_EXPRESSIONS):
            raise ValueError("Hero v3 facial matrix must expose every viseme and expression")
        if gate.get("continuous_engine") != "BLENDER_WORKBENCH":
            raise ValueError("Hero v3 must declare Workbench as the continuous geometry engine")
        if gate.get("review_engine") != "BLENDER_EEVEE_NEXT":
            raise ValueError("Hero v3 must declare Eevee as the lookdev review engine")
        if gate.get("promotion_engine") != "CYCLES":
            raise ValueError("Hero v3 must retain Cycles as the final promotion engine")
    if asset_major >= 4:
        canonical = manifest.get("canonical_identity_reference") or {}
        if canonical.get("path") != "concept/style_frames/june-oxley-canonical-turnaround-v1.png":
            raise ValueError("Hero v4 must pin the canonical June turnaround")
        if not re.fullmatch(r"[0-9a-f]{64}", str(canonical.get("sha256", ""))):
            raise ValueError("Hero v4 canonical identity reference must have a SHA-256")
        design_text = " ".join(str(value) for value in design.values()).lower()
        if "large" not in design_text or "blue-and-navy plaid" not in design_text:
            raise ValueError("Hero v4 must lock canonical large eyes and blue-and-navy plaid")
        modeling = manifest.get("modeling") or {}
        weighted = _string_set(modeling.get("weighted_surfaces"), "modeling.weighted_surfaces")
        required_weighted = {"jacket_sleeve.L", "jacket_sleeve.R", "overall_leg.L", "overall_leg.R"}
        if not required_weighted.issubset(weighted):
            raise ValueError("Hero v4 must provide continuous weighted arm and leg surfaces")
        deformation = str(modeling.get("deformation_standard", "")).lower()
        if "preserve-volume" not in deformation or "corrective-smooth" not in deformation:
            raise ValueError("Hero v4 must declare preserve-volume corrective deformation")
        if gate.get("deformation_pose_matrix_required") is not True:
            raise ValueError("Hero v4 requires a deformation pose matrix")
    if asset_major >= 5:
        if "CE_June_Props" not in collections:
            raise ValueError("Hero v5 must expose a dedicated performance-props collection")
        if not (REQUIRED_V5_CLAVICLES | REQUIRED_V5_FACE_BONES).issubset(bones):
            raise ValueError("Hero v5 required bones must include clavicle, jaw, eye, and gaze controls")
        actions = _string_set((manifest.get("rig") or {}).get("action_library"), "rig.action_library")
        if "June_Golden_Performance_v1" not in actions:
            raise ValueError("Hero v5 must publish the reusable Golden Performance action")
        controls = (manifest.get("rig") or {}).get("production_controls") or {}
        if _string_set(controls.get("ik_targets"), "rig.production_controls.ik_targets") != REQUIRED_V5_IK_TARGETS:
            raise ValueError("Hero v5 must expose both arm and leg IK targets")
        if _string_set(controls.get("pole_targets"), "rig.production_controls.pole_targets") != REQUIRED_V5_POLES:
            raise ValueError("Hero v5 must expose elbow and knee pole targets")
        if _string_set(controls.get("clavicles"), "rig.production_controls.clavicles") != REQUIRED_V5_CLAVICLES:
            raise ValueError("Hero v5 must expose both clavicle controls")
        if _string_set(controls.get("facial_bones"), "rig.production_controls.facial_bones") != REQUIRED_V5_FACE_BONES:
            raise ValueError("Hero v5 must expose jaw, eye, and gaze controls")
        if _string_set(controls.get("finger_controls"), "rig.production_controls.finger_controls") != REQUIRED_V5_FINGERS:
            raise ValueError("Hero v5 must expose ten articulated digit controls")
        if not all(controls.get(field) is True for field in ("foot_lock", "arm_ik", "gaze_target", "jaw_follow_through")):
            raise ValueError("Hero v5 production controls must enable IK, foot lock, gaze, and jaw follow-through")
        if hands.get("articulated_digits") is not True:
            raise ValueError("Hero v5 hands must declare articulated digits")
        props = manifest.get("performance_props") or {}
        if _string_set(props.get("required"), "performance_props.required") != REQUIRED_V5_PROPS:
            raise ValueError("Hero v5 must provide the Golden Scene performance props")
        if props.get("visibility_keyed_by_shot") is not True or props.get("hand_attachment_controls") is not True:
            raise ValueError("Hero v5 props require shot visibility and hand attachment controls")
        performance = manifest.get("performance_contract") or {}
        if performance.get("path") != "concept/style_frames/june_golden_scene_performance_slice_v1.json":
            raise ValueError("Hero v5 must pin the Golden Scene performance contract")
        if not re.fullmatch(r"[0-9a-f]{64}", str(performance.get("sha256", ""))):
            raise ValueError("Hero v5 performance contract must have a SHA-256")
        if performance.get("shots") != ["GS030", "GS040", "GS050"]:
            raise ValueError("Hero v5 performance contract must preserve the GS030-GS050 range")
        if (
            int(performance.get("fps", 0)) != 30
            or int(performance.get("frame_count", 0)) != 453
            or abs(float(performance.get("duration_seconds", 0)) - 15.1) > 1e-9
        ):
            raise ValueError("Hero v5 performance contract must preserve the 453-frame clock")
        if gate.get("performance_slice_required") is not True or gate.get("performance_slice_full_frame_render") is not True:
            raise ValueError("Hero v5 requires a full-frame deformation performance gate")


def load_asset_manifest(path: str | Path) -> dict:
    manifest_path = Path(path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_asset_manifest(manifest)
    if int(str(manifest["asset_version"]).split(".", 1)[0]) >= 4:
        canonical = manifest["canonical_identity_reference"]
        repo_root = manifest_path.parents[2]
        reference = repo_root / canonical["path"]
        if not reference.is_file():
            raise ValueError(f"Hero v4 canonical identity reference is missing: {reference}")
        digest = hashlib.sha256(reference.read_bytes()).hexdigest()
        if digest != canonical["sha256"]:
            raise ValueError("Hero v4 canonical identity reference hash does not match")
    if int(str(manifest["asset_version"]).split(".", 1)[0]) >= 5:
        performance = manifest["performance_contract"]
        repo_root = manifest_path.parents[2]
        contract = repo_root / performance["path"]
        if not contract.is_file():
            raise ValueError(f"Hero v5 performance contract is missing: {contract}")
        digest = hashlib.sha256(contract.read_bytes()).hexdigest()
        if digest != performance["sha256"]:
            raise ValueError("Hero v5 performance contract hash does not match")
    return manifest


def _executable(value: str, label: str) -> str:
    result = str(Path(value)) if Path(value).is_file() else shutil.which(value)
    if not result:
        raise FileNotFoundError(f"{label} executable not found: {value}")
    return result


def build_asset_library(
    manifest_path: str | Path,
    output_path: str | Path,
    *,
    blender: str = "blender",
) -> Path:
    manifest_path = Path(manifest_path).resolve()
    load_asset_manifest(manifest_path)
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    builder = Path(__file__).resolve().parent / "blender" / "build_june_asset_library.py"
    subprocess.run(
        [
            _executable(blender, "Blender"),
            "--background",
            "--python-exit-code",
            "1",
            "--python",
            str(builder),
            "--",
            "--manifest",
            str(manifest_path),
            "--output",
            str(output),
        ],
        check=True,
    )
    if not output.is_file():
        raise RuntimeError(f"Blender did not create asset library: {output}")
    return output


def shot_quality_frames(plan: dict) -> list[int]:
    return [
        (int(shot["frame_start"]) + int(shot["frame_end"])) // 2
        for shot in plan["shots"]
    ]


def facial_performance_plan(
    config: dict,
    *,
    size: int = 960,
    engine: str = "BLENDER_EEVEE_NEXT",
    samples: int = 32,
) -> tuple[dict, list[dict]]:
    """Build a deterministic close-up matrix plan for every facial control."""
    if int(size) <= 0 or int(samples) <= 0:
        raise ValueError("facial gate size and samples must be positive")
    plan = compile_plan(config, profile="youtube", quality="production")
    entries = [
        {"kind": "viseme", "label": shape, "viseme": shape, "expression": None}
        for shape in FACIAL_GATE_VISEMES
    ] + [
        {"kind": "expression", "label": expression, "viseme": "X", "expression": expression}
        for expression in FACIAL_GATE_EXPRESSIONS
    ]
    frame_span = 10
    plan["frame_start"] = 1
    plan["frame_end"] = len(entries) * frame_span
    plan["duration_seconds"] = plan["frame_end"] / int(plan["render"]["fps"])
    # The matrix must isolate the authored control under review. Production
    # blinks are intentionally disabled here so a blink cannot contaminate a
    # viseme or expression sample frame.
    plan["disable_blinks"] = True
    plan["render"].update(
        {
            "width": int(size),
            "height": int(size),
            "engine": engine,
            "samples": int(samples),
            "quality": "facial-performance-gate",
        }
    )
    plan["shots"] = [
        {"id": "face-visemes-a", "camera": "close", "frame_start": 1, "frame_end": 60},
        {"id": "face-visemes-b", "camera": "close", "frame_start": 61, "frame_end": 110},
        {"id": "face-expressions", "camera": "close", "frame_start": 111, "frame_end": plan["frame_end"]},
    ]
    mouth_cues = []
    facial_cues = []
    for index, entry in enumerate(entries):
        start = index * frame_span + 1
        end = start + frame_span - 1
        frame = start + frame_span // 2
        entry.update({"frame_start": start, "frame_end": end, "frame": frame})
        mouth_cues.append({"frame_start": start, "frame_end": end, "shape": entry["viseme"]})
        facial_cues.append(
            {
                "frame_start": start,
                "frame_end": end,
                "expression": entry["expression"],
                "strength": 1.0,
            }
        )
    plan["mouth_cues"] = mouth_cues
    plan["facial_performance_cues"] = facial_cues
    return plan, entries


def deformation_pose_plan(
    config: dict,
    *,
    width: int = 960,
    height: int = 540,
    engine: str = "BLENDER_WORKBENCH",
    samples: int = 1,
) -> tuple[dict, list[dict]]:
    """Build a four-pose matrix that exposes elbows, knees, and weight shift."""
    if int(width) <= 0 or int(height) <= 0 or int(samples) <= 0:
        raise ValueError("deformation gate dimensions and samples must be positive")
    plan = compile_plan(config, profile="youtube", quality="production")
    entries = [
        {"label": "grounded_neutral", "gesture": "settle", "performance": "grounded seated neutral"},
        {"label": "elbow_fold", "gesture": "two handed welcome", "performance": "both elbows bend clearly"},
        {"label": "seated_to_stand", "gesture": "seated to stand with mug", "performance": "weight forward through both feet"},
        {"label": "weight_transfer", "gesture": "weight transfer step left", "performance": "asymmetric planted weight transfer"},
    ]
    frame_span = 20
    plan["frame_start"] = 1
    plan["frame_end"] = len(entries) * frame_span
    plan["duration_seconds"] = plan["frame_end"] / int(plan["render"]["fps"])
    plan["render"].update(
        {
            "width": int(width),
            "height": int(height),
            "engine": engine,
            "samples": int(samples),
            "quality": "deformation-pose-gate",
        }
    )
    plan["shots"] = []
    for index, entry in enumerate(entries):
        start = index * frame_span + 1
        end = start + frame_span - 1
        frame = (start + end) // 2
        entry.update({"frame_start": start, "frame_end": end, "frame": frame})
        plan["shots"].append(
            {
                "id": f"deform-{index + 1:02d}",
                "camera": "medium",
                "frame_start": start,
                "frame_end": end,
                "gesture": entry["gesture"],
                "performance": entry["performance"],
                "camera_move": "locked",
            }
        )
    plan["mouth_cues"] = [{"frame_start": 1, "frame_end": plan["frame_end"], "shape": "X"}]
    return plan, entries


def golden_performance_plan(
    config: dict,
    performance_manifest_path: str | Path,
    *,
    width: int = 960,
    height: int = 540,
    engine: str = "BLENDER_WORKBENCH",
    samples: int = 1,
) -> tuple[dict, list[dict]]:
    """Compile the phase-8 acting contract into an exact deforming-rig plan."""
    if min(int(width), int(height), int(samples)) <= 0:
        raise ValueError("performance gate dimensions and samples must be positive")
    performance_path = Path(performance_manifest_path).resolve()
    performance = json.loads(performance_path.read_text(encoding="utf-8"))
    shot_ids = [str(shot.get("id")) for shot in performance.get("shots") or []]
    if shot_ids != ["GS030", "GS040", "GS050"]:
        raise ValueError("performance gate requires the canonical GS030-GS050 shot range")
    if performance.get("production") != config.get("production"):
        raise ValueError("performance gate source production does not match the contract")
    if (
        int(performance.get("fps", 0)) != 30
        or int(config.get("fps", 0)) != 30
        or int(performance.get("frame_count", 0)) != 453
        or abs(float(performance.get("duration_seconds", 0)) - 15.1) > 1e-9
    ):
        raise ValueError("performance gate requires the exact 453-frame contract")
    for shot in performance["shots"]:
        validate_key_pose_timing(shot)

    source_by_id = {str(shot.get("id")): shot for shot in config.get("shots") or []}
    if any(shot_id not in source_by_id for shot_id in shot_ids):
        raise ValueError("performance gate source config is missing a contracted shot")
    selected = [source_by_id[shot_id] for shot_id in shot_ids]
    subset = {
        **config,
        "dialogue": {
            **(config.get("dialogue") or {}),
            "text": " ".join(str(shot.get("line") or "") for shot in selected),
        },
        "shots": selected,
    }
    plan = compile_plan(subset, profile="youtube", quality="production")
    plan["render"].update(
        {
            "width": int(width),
            "height": int(height),
            "engine": engine,
            "samples": int(samples),
            "quality": "golden-performance-deformation-gate",
        }
    )
    plan["performance_contract"] = "june_golden_scene_performance_v1"
    plan["performance_manifest"] = str(performance_path)

    entries: list[dict] = []
    contract_by_id = {str(shot["id"]): shot for shot in performance["shots"]}
    for shot in plan["shots"]:
        contract_shot = contract_by_id[str(shot["id"])]
        expected_frames = int(contract_shot["frame_count"])
        actual_frames = int(shot["frame_end"]) - int(shot["frame_start"]) + 1
        if actual_frames != expected_frames:
            raise ValueError(f"performance gate frame budget changed for {shot['id']}")
        shot["performance_keyframes"] = []
        for keyframe in contract_shot["keyframes"]:
            global_frame = int(shot["frame_start"]) + int(keyframe["frame"])
            entry = {
                "shot": shot["id"],
                "phase": keyframe["phase"],
                "label": f"{shot['id']}-{keyframe['phase']}",
                "frame": global_frame,
            }
            shot["performance_keyframes"].append(entry)
            entries.append(entry)

    if int(plan["frame_end"]) != 453 or len(entries) != 9:
        raise ValueError("performance gate must compile nine poses across exactly 453 frames")

    shapes = tuple("AECDBFGH")
    mouth_cues = []
    for shot_index, shot in enumerate(plan["shots"]):
        cursor = int(shot["frame_start"])
        end = int(shot["frame_end"])
        cue_index = 0
        while cursor <= end:
            cue_end = min(end, cursor + 5)
            shape = "X" if cue_index % 6 == 5 else shapes[(shot_index * 3 + cue_index) % len(shapes)]
            mouth_cues.append({"frame_start": cursor, "frame_end": cue_end, "shape": shape})
            cursor = cue_end + 1
            cue_index += 1
    plan["mouth_cues"] = mouth_cues
    plan["facial_performance_cues"] = [
        {"frame_start": 1, "frame_end": 171, "expression": "smile", "strength": 0.38},
        {"frame_start": 172, "frame_end": 275, "expression": "smile", "strength": 0.68},
        {"frame_start": 276, "frame_end": 339, "expression": "thoughtful", "strength": 0.30},
        {"frame_start": 340, "frame_end": 396, "expression": "thoughtful", "strength": 0.76},
        {"frame_start": 397, "frame_end": 453, "expression": "brow_knit", "strength": 0.62},
    ]
    return plan, entries


def _facial_matrix(ffmpeg: str, frames_dir: Path, entries: list[dict], output: Path) -> None:
    """Assemble a labeled 4x4 face matrix, with a portable unlabeled fallback."""
    command = [ffmpeg, "-y"]
    for entry in entries:
        command.extend(["-i", str(frames_dir / f"frame_{entry['frame']:04d}.png")])
    filters = []
    labels = []
    for index, entry in enumerate(entries):
        label = f"f{index}"
        labels.append(f"[{label}]")
        safe_label = str(entry["label"]).replace("'", "")
        filters.append(
            f"[{index}:v]scale=320:320:force_original_aspect_ratio=decrease,"
            f"pad=320:320:(ow-iw)/2:(oh-ih)/2,"
            f"drawtext=text='{safe_label}':x=16:y=16:fontsize=30:fontcolor=white:"
            f"box=1:boxcolor=black@0.62[{label}]"
        )
    layout = "|".join(f"{(index % 4) * 320}_{(index // 4) * 320}" for index in range(len(entries)))
    filters.append("".join(labels) + f"xstack=inputs={len(entries)}:layout={layout}[matrix]")
    command.extend(["-filter_complex", ";".join(filters), "-map", "[matrix]", "-frames:v", "1", str(output)])
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        # Some FFmpeg packages omit libfreetype. Keep the visual gate usable and
        # rely on the adjacent JSON mapping rather than losing the matrix.
        fallback = [ffmpeg, "-y"]
        for entry in entries:
            fallback.extend(["-i", str(frames_dir / f"frame_{entry['frame']:04d}.png")])
        fallback_filters = [
            f"[{index}:v]scale=320:320:force_original_aspect_ratio=decrease,"
            f"pad=320:320:(ow-iw)/2:(oh-ih)/2[u{index}]"
            for index in range(len(entries))
        ]
        fallback_filters.append(
            "".join(f"[u{index}]" for index in range(len(entries)))
            + f"xstack=inputs={len(entries)}:layout={layout}[matrix]"
        )
        fallback.extend(
            ["-filter_complex", ";".join(fallback_filters), "-map", "[matrix]", "-frames:v", "1", str(output)]
        )
        subprocess.run(fallback, check=True)


def render_quality_gate(
    config_path: str | Path,
    manifest_path: str | Path,
    *,
    output_dir: str | Path,
    blender: str = "blender",
    ffmpeg: str = "ffmpeg",
    engine: str = "CYCLES",
    samples: int = 16,
    facial_engine: str = "BLENDER_EEVEE_NEXT",
    facial_size: int = 960,
    facial_samples: int = 32,
    performance_gate_mode: str = "full",
) -> dict:
    if int(samples) <= 0 or int(facial_size) <= 0 or int(facial_samples) <= 0:
        raise ValueError("samples and facial size must be positive")
    if performance_gate_mode not in {"poses", "full"}:
        raise ValueError("performance_gate_mode must be 'poses' or 'full'")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    manifest = load_asset_manifest(manifest_path)
    output = Path(output_dir).resolve()
    plans_dir = output / "plans"
    frames_root = output / "frames"
    plans_dir.mkdir(parents=True, exist_ok=True)
    library = build_asset_library(
        manifest_path,
        output / "assets" / f"{manifest['asset_id']}-{manifest['asset_version']}.blend",
        blender=blender,
    )
    blender_bin = _executable(blender, "Blender")
    ffmpeg_bin = _executable(ffmpeg, "FFmpeg")
    results = []
    for profile in ("youtube", "portrait"):
        plan = compile_plan(config, profile=profile, quality="production")
        plan["render"]["engine"] = engine
        plan["render"]["samples"] = int(samples)
        plan["asset_library"] = {
            "asset_id": manifest["asset_id"],
            "asset_version": manifest["asset_version"],
            "path": library.name,
        }
        plan_path = plans_dir / f"june-asset-quality-{profile}.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        frames = shot_quality_frames(plan)
        frames_dir = frames_root / profile
        _render_frames(
            blender_bin,
            plan_path,
            frames_dir,
            asset_library=library,
            selected_frames=frames,
        )
        contact_sheet = output / f"june-asset-quality-{profile}.png"
        _contact_sheet(ffmpeg_bin, plan, frames_dir, contact_sheet)
        results.append(
            {
                "profile": profile,
                "width": plan["render"]["width"],
                "height": plan["render"]["height"],
                "engine": engine,
                "samples": int(samples),
                "frames": frames,
                "contact_sheet": contact_sheet.name,
            }
        )
    face_plan, face_entries = facial_performance_plan(
        config,
        size=int(facial_size),
        engine=facial_engine,
        samples=int(facial_samples),
    )
    face_plan["asset_library"] = {
        "asset_id": manifest["asset_id"],
        "asset_version": manifest["asset_version"],
        "path": library.name,
    }
    face_plan_path = plans_dir / "june-facial-performance.json"
    face_plan_path.write_text(json.dumps(face_plan, indent=2) + "\n", encoding="utf-8")
    face_frames_dir = frames_root / "facial-performance"
    _render_frames(
        blender_bin,
        face_plan_path,
        face_frames_dir,
        asset_library=library,
        selected_frames=[int(entry["frame"]) for entry in face_entries],
    )
    facial_matrix = output / "june-facial-performance-matrix.png"
    _facial_matrix(ffmpeg_bin, face_frames_dir, face_entries, facial_matrix)
    deformation_gate = None
    if manifest["quality_gate"].get("deformation_pose_matrix_required"):
        deform_plan, deform_entries = deformation_pose_plan(config, engine=engine, samples=int(samples))
        deform_plan["asset_library"] = {
            "asset_id": manifest["asset_id"],
            "asset_version": manifest["asset_version"],
            "path": library.name,
        }
        deform_plan_path = plans_dir / "june-deformation-poses.json"
        deform_plan_path.write_text(json.dumps(deform_plan, indent=2) + "\n", encoding="utf-8")
        deform_frames_dir = frames_root / "deformation-poses"
        _render_frames(
            blender_bin,
            deform_plan_path,
            deform_frames_dir,
            asset_library=library,
            selected_frames=[int(entry["frame"]) for entry in deform_entries],
        )
        deformation_matrix = output / "june-deformation-pose-matrix.png"
        _contact_sheet(ffmpeg_bin, deform_plan, deform_frames_dir, deformation_matrix)
        deformation_gate = {
            "engine": deform_plan["render"]["engine"],
            "width": deform_plan["render"]["width"],
            "height": deform_plan["render"]["height"],
            "matrix": deformation_matrix.name,
            "entries": deform_entries,
        }
    performance_gate = None
    if manifest["quality_gate"].get("performance_slice_required"):
        repo_root = Path(manifest_path).resolve().parents[2]
        performance_contract_path = repo_root / manifest["performance_contract"]["path"]
        performance_plan, performance_entries = golden_performance_plan(
            config,
            performance_contract_path,
            engine=manifest["quality_gate"]["continuous_engine"],
            samples=1,
        )
        performance_plan["asset_library"] = {
            "asset_id": manifest["asset_id"],
            "asset_version": manifest["asset_version"],
            "path": library.name,
        }
        performance_plan_path = plans_dir / "june-golden-performance-deformation.json"
        performance_plan_path.write_text(json.dumps(performance_plan, indent=2) + "\n", encoding="utf-8")
        performance_frames_dir = frames_root / "golden-performance-deformation"
        selected_performance_frames = (
            None
            if performance_gate_mode == "full"
            else [int(entry["frame"]) for entry in performance_entries]
        )
        _render_frames(
            blender_bin,
            performance_plan_path,
            performance_frames_dir,
            asset_library=library,
            selected_frames=selected_performance_frames,
        )
        performance_matrix = output / "june-golden-performance-deformation-matrix.png"
        _facial_matrix(ffmpeg_bin, performance_frames_dir, performance_entries, performance_matrix)
        performance_video = None
        if performance_gate_mode == "full":
            performance_video = output / "june-golden-performance-deformation.mp4"
            _assemble_video(ffmpeg_bin, performance_plan, performance_frames_dir, performance_video, None)
        performance_gate = {
            "render_mode": performance_gate_mode,
            "engine": performance_plan["render"]["engine"],
            "width": performance_plan["render"]["width"],
            "height": performance_plan["render"]["height"],
            "fps": performance_plan["render"]["fps"],
            "frames": performance_plan["frame_end"],
            "contract_frames": performance_plan["frame_end"],
            "rendered_frames": performance_plan["frame_end"] if performance_gate_mode == "full" else len(performance_entries),
            "duration_seconds": performance_plan["duration_seconds"],
            "matrix": performance_matrix.name,
            "video": performance_video.name if performance_video else None,
            "entries": performance_entries,
        }
    report = {
        "contract_version": ASSET_CONTRACT_VERSION,
        "asset_id": manifest["asset_id"],
        "asset_version": manifest["asset_version"],
        "library": str(library.relative_to(output)),
        "artifact_reopened_for_render": True,
        "human_art_approval_required": bool(manifest["quality_gate"].get("human_art_approval_required")),
        "render_tier": (
            "promotion"
            if engine == manifest["quality_gate"].get("promotion_engine")
            else "lookdev_review"
            if engine == manifest["quality_gate"].get("review_engine")
            else "continuous_geometry"
        ),
        "results": results,
        "facial_performance_gate": {
            "engine": face_plan["render"]["engine"],
            "width": face_plan["render"]["width"],
            "height": face_plan["render"]["height"],
            "matrix": facial_matrix.name,
            "entries": face_entries,
        },
        "deformation_pose_gate": deformation_gate,
        "performance_deformation_gate": performance_gate,
    }
    (output / "asset-quality-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and quality-check the June Oxley Blender asset library")
    parser.add_argument("config")
    parser.add_argument("manifest")
    parser.add_argument("--output-dir", default="build/june-asset-quality")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument(
        "--engine",
        choices=("CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"),
        default="CYCLES",
    )
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument(
        "--facial-engine",
        choices=("CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"),
        default="BLENDER_EEVEE_NEXT",
    )
    parser.add_argument("--facial-size", type=int, default=960)
    parser.add_argument("--facial-samples", type=int, default=32)
    parser.add_argument(
        "--performance-gate",
        choices=("poses", "full"),
        default="full",
        help="Render only the nine contracted poses for fast CI or all 453 frames for promotion.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = render_quality_gate(
        args.config,
        args.manifest,
        output_dir=args.output_dir,
        blender=args.blender,
        ffmpeg=args.ffmpeg,
        engine=args.engine,
        samples=args.samples,
        facial_engine=args.facial_engine,
        facial_size=args.facial_size,
        facial_samples=args.facial_samples,
        performance_gate_mode=args.performance_gate,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
