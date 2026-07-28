"""Versioned Blender asset-library contract and full-resolution quality gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from pipeline.cartoon_motion import RENDER_PROFILES
from pipeline.cartoon_vertical_slice import _contact_sheet, _render_frames, compile_plan


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


def load_asset_manifest(path: str | Path) -> dict:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_asset_manifest(manifest)
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


def facial_performance_plan(config: dict) -> tuple[dict, list[dict]]:
    """Build a deterministic close-up matrix plan for every facial control."""
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
    plan["render"].update(
        {
            "width": 960,
            "height": 960,
            "engine": "BLENDER_EEVEE_NEXT",
            "samples": 32,
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
) -> dict:
    if int(samples) <= 0:
        raise ValueError("samples must be positive")
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
    face_plan, face_entries = facial_performance_plan(config)
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
    report = {
        "contract_version": ASSET_CONTRACT_VERSION,
        "asset_id": manifest["asset_id"],
        "asset_version": manifest["asset_version"],
        "library": str(library.relative_to(output)),
        "artifact_reopened_for_render": True,
        "human_art_approval_required": bool(manifest["quality_gate"].get("human_art_approval_required")),
        "results": results,
        "facial_performance_gate": {
            "engine": face_plan["render"]["engine"],
            "width": face_plan["render"]["width"],
            "height": face_plan["render"]["height"],
            "matrix": facial_matrix.name,
            "entries": face_entries,
        },
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
    parser.add_argument("--engine", choices=("CYCLES", "BLENDER_WORKBENCH"), default="CYCLES")
    parser.add_argument("--samples", type=int, default=16)
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
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
