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

from pipeline.cartoon_lipsync import cues_to_frames
from pipeline.cartoon_motion import RENDER_PROFILES
from pipeline.cartoon_performance_slice import validate_key_pose_timing
from pipeline.cartoon_vertical_slice import _assemble_video, _contact_sheet, _render_frames, compile_plan


ASSET_CONTRACT_VERSION = 1
LOOK_CONTRACT_VERSION = 1
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
REQUIRED_V6_DISTAL_FINGERS = {
    "finger_tip.0.L", "finger_tip.1.L", "finger_tip.2.L", "finger_tip.3.L", "thumb_tip.L",
    "finger_tip.0.R", "finger_tip.1.R", "finger_tip.2.R", "finger_tip.3.R", "thumb_tip.R",
}
REQUIRED_V6_CORRECTIVES = {
    "mouth_corner.L", "mouth_corner.R", "mouth_press", "inner_brow_raise",
    "lower_lid_engage", "jaw_soften",
}
REQUIRED_V6_HAND_POSES = {
    "relaxed", "mug_grip", "chair_support", "ledger_support", "pencil_tripod", "open_empathy",
}
REQUIRED_V7_MOUTH_COMPONENTS = {
    "mouth_bag", "upper_lip", "lower_lip", "upper_gum", "lower_gum",
    "upper_teeth", "lower_teeth", "tongue",
}
REQUIRED_V8_MOUTH_COMPONENTS = {
    "mouth_bag", "oral_mask", "upper_gum", "lower_gum",
    "upper_teeth", "lower_teeth", "tongue",
}
REQUIRED_V8_SOFT_TISSUE = {
    "corner.L", "corner.R", "cheek.L", "cheek.R", "dental_exposure", "groove_visibility",
}
RENDER_ENGINES = {"CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"}


def canonical_text_sha256(path: str | Path) -> str:
    """Hash UTF-8 contracts after universal-newline normalization."""
    text = Path(path).read_text(encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _string_set(value: Any, field: str) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return set(value)


def validate_look_profile(profile: dict) -> None:
    """Validate a versioned, renderer-independent June look contract."""
    if not isinstance(profile, dict) or profile.get("contract_version") != LOOK_CONTRACT_VERSION:
        raise ValueError(f"look contract_version must be {LOOK_CONTRACT_VERSION}")
    if profile.get("look_id") != "june_oxley_storybook_npr":
        raise ValueError("look profile must explicitly target June's storybook NPR style")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(profile.get("style_version", ""))):
        raise ValueError("look style_version must use semantic versioning")
    if profile.get("engine") != "BLENDER_EEVEE_NEXT":
        raise ValueError("storybook NPR look must use Blender Eevee Next")
    toon = profile.get("toon") or {}
    thresholds = toon.get("thresholds") or []
    levels = toon.get("levels") or []
    if toon.get("enabled") is not True or len(thresholds) != 2 or len(levels) != 3:
        raise ValueError("NPR toon profile requires two thresholds and three levels")
    if not (0.0 < float(thresholds[0]) < float(thresholds[1]) < 1.0):
        raise ValueError("NPR toon thresholds must be ordered inside zero and one")
    if any(float(level) <= 0.0 for level in levels):
        raise ValueError("NPR toon levels must be positive")
    outlines = profile.get("outlines") or {}
    if outlines.get("enabled") is not True or not 0.5 <= float(outlines.get("thickness_px", 0)) <= 3.0:
        raise ValueError("NPR outlines require a production-safe 0.5-3px thickness")
    if outlines.get("mode") not in {"freestyle", "compositor_sobel", "semantic_compositor"}:
        raise ValueError("NPR outline mode must be freestyle, compositor_sobel, or semantic_compositor")
    if outlines.get("mode") == "compositor_sobel" and not 0.0 < float(outlines.get("edge_strength", 0)) <= 1.0:
        raise ValueError("NPR compositor edge_strength must be inside zero and one")
    if outlines.get("mode") == "semantic_compositor":
        layers = outlines.get("semantic_layers") or []
        if len(layers) != 3:
            raise ValueError("NPR semantic compositor requires exactly three ink layers")
        names = {str(layer.get("name", "")) for layer in layers}
        sources = {str(layer.get("source", "")) for layer in layers}
        if names != {"silhouette_contact", "form_crease", "construction_detail"}:
            raise ValueError("NPR semantic ink layers must name silhouette, form, and construction roles")
        if sources != {"mist", "normal", "luminance"}:
            raise ValueError("NPR semantic ink layers must use mist, normal, and luminance sources")
        for layer in layers:
            if not 0.0 < float(layer.get("strength", 0)) <= 1.0:
                raise ValueError("NPR semantic ink strength must be inside zero and one")
            if not 0 <= int(layer.get("dilate_px", -1)) <= 2:
                raise ValueError("NPR semantic ink dilation must be between zero and two pixels")
            multipliers = layer.get("shot_multipliers") or {}
            if set(multipliers) != {"wide", "medium", "close"}:
                raise ValueError("NPR semantic ink requires wide, medium, and close shot multipliers")
            if any(not 0.0 <= float(value) <= 2.0 for value in multipliers.values()):
                raise ValueError("NPR semantic ink shot multipliers must be between zero and two")
    if len(outlines.get("color") or []) != 3:
        raise ValueError("NPR outline color must be RGB")
    lighting = profile.get("lighting") or {}
    for role in ("key", "fill", "lantern", "rim"):
        light = lighting.get(role) or {}
        if float(light.get("energy", 0)) <= 0 or len(light.get("color") or []) != 3:
            raise ValueError(f"NPR lighting.{role} requires positive energy and RGB color")
    camera = profile.get("camera") or {}
    if camera.get("depth_of_field") is not True or float(camera.get("f_stop", 0)) <= 0:
        raise ValueError("NPR camera requires a positive depth-of-field f-stop")
    if len(camera.get("focus_target") or []) != 3:
        raise ValueError("NPR camera focus_target must be XYZ")
    render = profile.get("render") or {}
    if int(render.get("temporal_window_start", 1)) < 1 or int(render.get("temporal_window_frames", 30)) < 2:
        raise ValueError("NPR temporal window requires a positive start and at least two frames")
    acting = profile.get("acting_polish")
    if acting is not None:
        if acting.get("enabled") is not True or not re.fullmatch(r"\d+\.\d+\.\d+", str(acting.get("version", ""))):
            raise ValueError("NPR acting polish must be enabled and semantically versioned")
        for field in ("hold_frames", "anticipation_frames", "settle_frames"):
            if not 1 <= int(acting.get(field, 0)) <= 12:
                raise ValueError(f"NPR acting polish {field} must be between one and twelve")
        if not 12 <= int(acting.get("final_hold_frames", 0)) <= 45:
            raise ValueError("NPR acting polish final hold must be between twelve and forty-five frames")
        for field, minimum, maximum in (
            ("anticipation_ratio", 0.0, 0.12),
            ("breakdown_fraction", 0.35, 0.75),
            ("overshoot_ratio", 0.0, 0.10),
            ("arc_height", 0.0, 0.05),
            ("gaze_lead", 0.0, 0.25),
            ("clavicle_lag", 0.0, 0.25),
        ):
            value = float(acting.get(field, -1))
            if not minimum <= value <= maximum:
                raise ValueError(f"NPR acting polish {field} is outside its safe range")
    facial = profile.get("facial_polish")
    if facial is not None:
        if facial.get("enabled") is not True or not re.fullmatch(r"\d+\.\d+\.\d+", str(facial.get("version", ""))):
            raise ValueError("NPR facial polish must be enabled and semantically versioned")
        for field, minimum, maximum in (
            ("transition_frames", 2, 12),
            ("gaze_lead_frames", 1, 8),
            ("gaze_settle_frames", 1, 8),
            ("breath_period_frames", 48, 120),
        ):
            value = int(facial.get(field, 0))
            if not minimum <= value <= maximum:
                raise ValueError(f"NPR facial polish {field} is outside its safe range")
        for field, minimum, maximum in (
            ("overshoot_ratio", 0.0, 0.12),
            ("breath_amplitude", 0.0, 0.012),
            ("saccade_amplitude", 0.0, 0.020),
        ):
            value = float(facial.get(field, -1))
            if not minimum <= value <= maximum:
                raise ValueError(f"NPR facial polish {field} is outside its safe range")


def load_look_profile(path: str | Path) -> dict:
    profile = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_look_profile(profile)
    return profile


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
    if asset_major >= 6:
        if not REQUIRED_V6_DISTAL_FINGERS.issubset(bones):
            raise ValueError("Hero v6 must expose ten independent distal digit controls")
        modeling = manifest.get("modeling") or {}
        correctives = _string_set(modeling.get("corrective_shapes"), "modeling.corrective_shapes")
        if not REQUIRED_V6_CORRECTIVES.issubset(correctives):
            raise ValueError("Hero v6 is missing localized facial coarticulation correctives")
        face = manifest.get("face") or {}
        if _string_set(face.get("deformation_controls"), "face.deformation_controls") != REQUIRED_V6_CORRECTIVES:
            raise ValueError("Hero v6 must publish the exact facial deformation-control set")
        distal = _string_set(
            ((manifest.get("rig") or {}).get("production_controls") or {}).get("distal_finger_controls"),
            "rig.production_controls.distal_finger_controls",
        )
        if distal != REQUIRED_V6_DISTAL_FINGERS:
            raise ValueError("Hero v6 production controls must publish every distal digit")
        if hands.get("independent_distal_controls") is not True:
            raise ValueError("Hero v6 hands must enable independent distal controls")
        if _string_set(hands.get("pose_library"), "hands.pose_library") != REQUIRED_V6_HAND_POSES:
            raise ValueError("Hero v6 must publish all six authored hand shapes")
        actions = _string_set((manifest.get("rig") or {}).get("action_library"), "rig.action_library")
        if "June_Micro_Performance_v1" not in actions:
            raise ValueError("Hero v6 must publish the additive micro-performance action")
        if gate.get("facial_coarticulation_required") is not True or gate.get("hand_pose_matrix_required") is not True:
            raise ValueError("Hero v6 requires facial-coarticulation and hand-pose visual gates")
    if asset_major >= 7:
        face = manifest.get("face") or {}
        mouth_components = _string_set(face.get("mouth_components"), "face.mouth_components")
        if asset_major == 7 and mouth_components != REQUIRED_V7_MOUTH_COMPONENTS:
            raise ValueError("Hero v7 must publish the exact volumetric mouth component set")
        if face.get("volumetric_mouth") is not True or face.get("per_viseme_deformation") is not True:
            raise ValueError("Hero v7 requires volumetric per-viseme oral deformation")
        max_follow = float(face.get("beard_jaw_follow_max", 1.0))
        if not 0.0 <= max_follow <= 0.35:
            raise ValueError("Hero v7 beard jaw follow must be bounded at or below 0.35")
        if gate.get("volumetric_mouth_required") is not True or gate.get("mouth_temporal_gate_required") is not True:
            raise ValueError("Hero v7 requires volumetric-mouth and focused temporal visual gates")
        window = gate.get("mouth_temporal_window") or []
        if window != [399, 415]:
            raise ValueError("Hero v7 mouth temporal gate must preserve frames 399-415")
    if asset_major >= 8:
        face = manifest.get("face") or {}
        if _string_set(face.get("mouth_components"), "face.mouth_components") != REQUIRED_V8_MOUTH_COMPONENTS:
            raise ValueError("Hero v8 must publish the exact oral-mask mouth component set")
        if face.get("oral_mask") is not True or face.get("detached_lip_objects") is not False:
            raise ValueError("Hero v8 requires one integrated oral mask and forbids detached lip objects")
        controls = _string_set(face.get("soft_tissue_controls"), "face.soft_tissue_controls")
        if controls != REQUIRED_V8_SOFT_TISSUE:
            raise ValueError("Hero v8 must publish the exact corner, cheek, and dental visibility controls")
        if face.get("dental_visibility_per_viseme") is not True:
            raise ValueError("Hero v8 requires per-viseme dental visibility")
        if gate.get("nine_viseme_matrix_required") is not True or gate.get("cheek_integration_required") is not True:
            raise ValueError("Hero v8 requires nine-viseme and cheek-integration visual gates")


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
        digest = canonical_text_sha256(contract)
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

    lip_sync = performance.get("lip_sync") or {}
    lip_sync_path = performance_path.parent / str(lip_sync.get("path") or "")
    if not lip_sync_path.is_file():
        raise ValueError("performance gate requires a versioned Rhubarb lip-sync contract")
    actual_lip_sha256 = canonical_text_sha256(lip_sync_path)
    if actual_lip_sha256 != str(lip_sync.get("sha256") or "").lower():
        raise ValueError("performance Rhubarb lip-sync contract digest changed")
    lip_payload = json.loads(lip_sync_path.read_text(encoding="utf-8"))
    plan["mouth_cues"] = cues_to_frames(lip_payload, fps=30, duration=15.1)
    if (
        len(plan["mouth_cues"]) != int(lip_sync.get("cue_count", 0))
        or int(plan["mouth_cues"][-1]["frame_end"]) != 453
        or str(plan["mouth_cues"][-1]["shape"]) != "X"
    ):
        raise ValueError("performance Rhubarb cues must close the exact 453-frame clock on X")
    plan["lip_sync_contract"] = {
        "path": lip_sync_path.name,
        "sha256": actual_lip_sha256,
        "generator": lip_sync.get("generator"),
        "recognizer": lip_sync.get("recognizer"),
        "cue_count": len(plan["mouth_cues"]),
        "transition_frames": int(lip_sync.get("transition_frames", 2)),
        "interpolation": str(lip_sync.get("interpolation") or "LINEAR"),
    }
    plan["facial_performance_cues"] = [
        {"frame_start": 1, "frame_end": 171, "expression": "smile", "strength": 0.38},
        {"frame_start": 172, "frame_end": 275, "expression": "smile", "strength": 0.68},
        {"frame_start": 276, "frame_end": 339, "expression": "thoughtful", "strength": 0.30},
        {"frame_start": 340, "frame_end": 396, "expression": "thoughtful", "strength": 0.76},
        {"frame_start": 397, "frame_end": 453, "expression": "brow_knit", "strength": 0.62},
    ]
    return plan, entries


def _facial_matrix(ffmpeg: str, frames_dir: Path, entries: list[dict], output: Path) -> None:
    """Assemble a labeled face matrix, with a portable unlabeled fallback."""
    command = [ffmpeg, "-y"]
    for entry in entries:
        command.extend(["-i", str(frames_dir / f"frame_{entry['frame']:04d}.png")])
    cell = 480 if len(entries) == len(FACIAL_GATE_VISEMES) else 320
    filters = []
    labels = []
    for index, entry in enumerate(entries):
        label = f"f{index}"
        labels.append(f"[{label}]")
        safe_label = str(entry["label"]).replace("'", "")
        filters.append(
            f"[{index}:v]scale={cell}:{cell}:force_original_aspect_ratio=decrease,"
            f"pad={cell}:{cell}:(ow-iw)/2:(oh-ih)/2,"
            f"drawtext=text='{safe_label}':x=20:y=20:fontsize={int(cell * 0.095)}:fontcolor=white:"
            f"box=1:boxcolor=black@0.62[{label}]"
        )
    columns = 3 if len(entries) == len(FACIAL_GATE_VISEMES) else 4
    layout = "|".join(
        f"{(index % columns) * cell}_{(index // columns) * cell}"
        for index in range(len(entries))
    )
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
            f"[{index}:v]scale={cell}:{cell}:force_original_aspect_ratio=decrease,"
            f"pad={cell}:{cell}:(ow-iw)/2:(oh-ih)/2[u{index}]"
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


def _assemble_video_window(
    ffmpeg: str,
    plan: dict,
    frames_dir: Path,
    output: Path,
    *,
    start_frame: int,
    frame_count: int,
) -> None:
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate",
            str(plan["render"]["fps"]),
            "-start_number",
            str(start_frame),
            "-i",
            str(frames_dir / "frame_%04d.png"),
            "-frames:v",
            str(frame_count),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )


def temporal_review_entries(start_frame: int, frame_count: int, *, sample_count: int = 9) -> list[dict]:
    """Select an evenly distributed, endpoint-inclusive temporal review matrix."""
    if int(start_frame) < 1 or int(frame_count) < 2 or int(sample_count) < 2:
        raise ValueError("temporal review requires a positive start and at least two frames and samples")
    samples = min(int(sample_count), int(frame_count))
    span = int(frame_count) - 1
    frames = [int(start_frame) + ((span * index) // (samples - 1)) for index in range(samples)]
    return [
        {
            "shot": "GS050",
            "phase": "temporal_review",
            "label": f"GS050-t+{frame - int(start_frame):02d}",
            "frame": frame,
        }
        for frame in frames
    ]


def render_performance_look_gate(
    config_path: str | Path,
    manifest_path: str | Path,
    *,
    look_profile_path: str | Path,
    output_dir: str | Path,
    blender: str = "blender",
    ffmpeg: str = "ffmpeg",
    engine: str | None = None,
    samples: int = 12,
    performance_gate_mode: str = "poses",
    performance_frame_start: int | None = None,
    performance_frame_end: int | None = None,
) -> dict:
    """Render a focused viseme, decision-pose, or promoted performance gate.

    Structural profile, face, and deformation matrices stay in the fast
    Workbench lane. This focused lane makes real Eevee look development cheap
    enough to use repeatedly rather than treating art review as a rare event.
    """
    if performance_gate_mode not in {"visemes", "poses", "temporal", "chunk", "full"}:
        raise ValueError("performance_gate_mode must be 'visemes', 'poses', 'temporal', 'chunk', or 'full'")
    if performance_gate_mode == "chunk":
        if (
            performance_frame_start is None
            or performance_frame_end is None
            or int(performance_frame_start) < 1
            or int(performance_frame_end) < int(performance_frame_start)
        ):
            raise ValueError("chunk mode requires an ordered positive performance frame range")
    elif performance_frame_start is not None or performance_frame_end is not None:
        raise ValueError("performance frame range is only valid in chunk mode")
    if int(samples) <= 0:
        raise ValueError("performance look samples must be positive")
    profile = load_look_profile(look_profile_path)
    selected_engine = engine or str(profile["engine"])
    if selected_engine not in RENDER_ENGINES:
        raise ValueError("performance look engine is not supported")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    manifest = load_asset_manifest(manifest_path)
    output = Path(output_dir).resolve()
    plans_dir = output / "plans"
    frames_dir = output / "frames" / "golden-performance-look"
    plans_dir.mkdir(parents=True, exist_ok=True)
    library = build_asset_library(
        manifest_path,
        output / "assets" / f"{manifest['asset_id']}-{manifest['asset_version']}.blend",
        blender=blender,
    )
    if performance_gate_mode == "visemes":
        plan, all_entries = facial_performance_plan(
            config,
            size=960,
            engine=selected_engine,
            samples=int(samples),
        )
        entries = [entry for entry in all_entries if entry["kind"] == "viseme"]
    else:
        repo_root = Path(manifest_path).resolve().parents[2]
        performance_contract_path = repo_root / manifest["performance_contract"]["path"]
        plan, entries = golden_performance_plan(
            config,
            performance_contract_path,
            engine=selected_engine,
            samples=int(samples),
        )
    look_sha256 = hashlib.sha256(Path(look_profile_path).read_bytes()).hexdigest()
    plan["look_profile"] = profile
    plan["look_profile_sha256"] = look_sha256
    plan["asset_library"] = {
        "asset_id": manifest["asset_id"],
        "asset_version": manifest["asset_version"],
        "path": library.name,
    }
    plan_path = plans_dir / "june-golden-performance-look.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    blender_bin = _executable(blender, "Blender")
    ffmpeg_bin = _executable(ffmpeg, "FFmpeg")
    look_render = profile.get("render") or {}
    temporal_start = int(look_render.get("temporal_window_start", 1))
    temporal_frames = int(look_render.get("temporal_window_frames", 30))
    temporal_end = temporal_start + temporal_frames - 1
    if performance_gate_mode != "visemes" and (temporal_start < 1 or temporal_end > int(plan["frame_end"])):
        raise ValueError("NPR temporal window must stay inside the performance contract")
    chunk_start = int(performance_frame_start or 1)
    chunk_end = int(performance_frame_end or plan["frame_end"])
    if performance_gate_mode == "chunk" and chunk_end > int(plan["frame_end"]):
        raise ValueError("NPR chunk must stay inside the performance contract")
    selected_frames = None
    if performance_gate_mode in {"visemes", "poses"}:
        selected_frames = [int(entry["frame"]) for entry in entries]
    elif performance_gate_mode == "temporal":
        selected_frames = list(range(temporal_start, temporal_end + 1))
    elif performance_gate_mode == "chunk":
        selected_frames = list(range(chunk_start, chunk_end + 1))
    _render_frames(
        blender_bin,
        plan_path,
        frames_dir,
        asset_library=library,
        selected_frames=selected_frames,
    )
    matrix_entries = (
        temporal_review_entries(temporal_start, temporal_frames)
        if performance_gate_mode == "temporal"
        else temporal_review_entries(chunk_start, chunk_end - chunk_start + 1)
        if performance_gate_mode == "chunk"
        else entries
    )
    matrix = output / "june-golden-performance-look-matrix.png"
    _facial_matrix(ffmpeg_bin, frames_dir, matrix_entries, matrix)
    video = None
    if performance_gate_mode in {"temporal", "full"}:
        video = output / (
            "june-golden-performance-look-temporal.mp4"
            if performance_gate_mode == "temporal"
            else "june-golden-performance-look.mp4"
        )
        if performance_gate_mode == "temporal":
            _assemble_video_window(
                ffmpeg_bin,
                plan,
                frames_dir,
                video,
                start_frame=temporal_start,
                frame_count=temporal_frames,
            )
        else:
            _assemble_video(ffmpeg_bin, plan, frames_dir, video, None)
    report = {
        "contract_version": ASSET_CONTRACT_VERSION,
        "gate": "focused_performance_look",
        "asset_id": manifest["asset_id"],
        "asset_version": manifest["asset_version"],
        "library": str(library.relative_to(output)),
        "artifact_reopened_for_render": True,
        "look_profile": {
            "look_id": profile["look_id"],
            "style_version": profile["style_version"],
            "engine": selected_engine,
            "samples": int(samples),
            "sha256": look_sha256,
        },
        "performance": {
            "render_mode": performance_gate_mode,
            "width": plan["render"]["width"],
            "height": plan["render"]["height"],
            "fps": plan["render"]["fps"],
            "contract_frames": plan["frame_end"],
            "rendered_frames": (
                plan["frame_end"]
                if performance_gate_mode == "full"
                else chunk_end - chunk_start + 1
                if performance_gate_mode == "chunk"
                else temporal_frames
                if performance_gate_mode == "temporal"
                else len(entries)
            ),
            "temporal_window": (
                {"frame_start": temporal_start, "frame_end": temporal_end}
                if performance_gate_mode == "temporal"
                else None
            ),
            "chunk_window": (
                {"frame_start": chunk_start, "frame_end": chunk_end}
                if performance_gate_mode == "chunk"
                else None
            ),
            "duration_seconds": plan["duration_seconds"],
            "matrix": matrix.name,
            "video": video.name if video else None,
            "matrix_entries": matrix_entries,
            "entries": entries,
        },
    }
    (output / "asset-quality-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


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
    performance_engine: str | None = None,
    performance_samples: int | None = None,
    look_profile_path: str | Path | None = None,
) -> dict:
    if int(samples) <= 0 or int(facial_size) <= 0 or int(facial_samples) <= 0:
        raise ValueError("samples and facial size must be positive")
    if performance_gate_mode not in {"poses", "full"}:
        raise ValueError("performance_gate_mode must be 'poses' or 'full'")
    if performance_engine is not None and performance_engine not in RENDER_ENGINES:
        raise ValueError("performance_engine is not supported")
    if performance_samples is not None and int(performance_samples) <= 0:
        raise ValueError("performance_samples must be positive")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    manifest = load_asset_manifest(manifest_path)
    look_profile = load_look_profile(look_profile_path) if look_profile_path else None
    look_profile_sha256 = (
        hashlib.sha256(Path(look_profile_path).read_bytes()).hexdigest()
        if look_profile_path
        else None
    )

    def attach_look(plan: dict) -> None:
        if look_profile:
            plan["look_profile"] = look_profile
            plan["look_profile_sha256"] = look_profile_sha256
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
        attach_look(plan)
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
    attach_look(face_plan)
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
        attach_look(deform_plan)
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
            engine=performance_engine or manifest["quality_gate"]["continuous_engine"],
            samples=int(performance_samples or 1),
        )
        attach_look(performance_plan)
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
        "look_profile": (
            {
                "look_id": look_profile["look_id"],
                "style_version": look_profile["style_version"],
                "engine": look_profile["engine"],
                "sha256": look_profile_sha256,
            }
            if look_profile
            else None
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
        choices=("visemes", "poses", "temporal", "chunk", "full"),
        default="full",
        help="Render all nine visemes, decision poses, a temporal window, one promotion chunk, or all 453 frames.",
    )
    parser.add_argument("--performance-frame-start", type=int)
    parser.add_argument("--performance-frame-end", type=int)
    parser.add_argument(
        "--performance-engine",
        choices=tuple(sorted(RENDER_ENGINES)),
        help="Override the performance gate engine; defaults to the manifest continuous engine.",
    )
    parser.add_argument("--performance-samples", type=int)
    parser.add_argument("--look-profile", help="Versioned NPR look-profile JSON applied to every render plan.")
    parser.add_argument(
        "--performance-only",
        action="store_true",
        help="Skip structural matrices and render only the focused Golden Scene look gate.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.performance_only:
        if not args.look_profile:
            raise ValueError("--performance-only requires --look-profile")
        report = render_performance_look_gate(
            args.config,
            args.manifest,
            look_profile_path=args.look_profile,
            output_dir=args.output_dir,
            blender=args.blender,
            ffmpeg=args.ffmpeg,
            engine=args.performance_engine,
            samples=int(args.performance_samples or 12),
            performance_gate_mode=args.performance_gate,
            performance_frame_start=args.performance_frame_start,
            performance_frame_end=args.performance_frame_end,
        )
    else:
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
            performance_engine=args.performance_engine,
            performance_samples=args.performance_samples,
            look_profile_path=args.look_profile,
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
