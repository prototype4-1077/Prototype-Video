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
    delivery = manifest.get("delivery") or {}
    if delivery.get("format") != "blend" or delivery.get("generation") != "code_native_runtime_build":
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
    report = {
        "contract_version": ASSET_CONTRACT_VERSION,
        "asset_id": manifest["asset_id"],
        "asset_version": manifest["asset_version"],
        "library": str(library.relative_to(output)),
        "results": results,
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
