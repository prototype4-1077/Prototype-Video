"""Bridge literal motion-graphic scenes to the headless Blender renderer."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from video_format import BAND_HEIGHT, BAND_WIDTH, FPS


BACKEND = "blender_3d"
PLAN_VERSION = 3
GRAPHIC_KINDS = (
    "labels", "path", "counters", "clock", "perception", "evidence",
    "filter", "scale", "generic",
)
PALETTES = (
    {
        "background": [0.025, 0.045, 0.065, 1.0],
        "surface": [0.075, 0.105, 0.135, 1.0],
        "cream": [0.88, 0.82, 0.63, 1.0],
        "cyan": [0.12, 0.68, 0.74, 1.0],
        "coral": [0.82, 0.23, 0.20, 1.0],
        "magenta": [0.63, 0.16, 0.48, 1.0],
        "gold": [0.83, 0.57, 0.16, 1.0],
        "muted": [0.28, 0.39, 0.43, 1.0],
    },
    {
        "background": [0.040, 0.028, 0.055, 1.0],
        "surface": [0.115, 0.075, 0.135, 1.0],
        "cream": [0.90, 0.84, 0.68, 1.0],
        "cyan": [0.20, 0.65, 0.70, 1.0],
        "coral": [0.86, 0.31, 0.25, 1.0],
        "magenta": [0.67, 0.23, 0.52, 1.0],
        "gold": [0.88, 0.64, 0.22, 1.0],
        "muted": [0.35, 0.31, 0.43, 1.0],
    },
    {
        "background": [0.025, 0.050, 0.045, 1.0],
        "surface": [0.070, 0.125, 0.110, 1.0],
        "cream": [0.90, 0.84, 0.68, 1.0],
        "cyan": [0.18, 0.68, 0.62, 1.0],
        "coral": [0.86, 0.29, 0.23, 1.0],
        "magenta": [0.56, 0.25, 0.58, 1.0],
        "gold": [0.86, 0.61, 0.17, 1.0],
        "muted": [0.29, 0.42, 0.39, 1.0],
    },
)


class BlenderUnavailable(RuntimeError):
    pass


class BlenderRenderError(RuntimeError):
    pass


def backend_for(script: dict, scene: dict) -> str:
    return str(
        scene.get("graphic_backend_requested")
        or scene.get("graphic_backend")
        or script.get("graphic_backend")
        or "pil_2d"
    ).strip().lower().replace("-", "_")


def requested(script: dict, scene: dict) -> bool:
    return backend_for(script, scene) == BACKEND


def _clean(value: object, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().upper()
    if len(text) <= limit:
        return text
    shortened = text[: limit + 1].rsplit(" ", 1)[0]
    return (shortened or text[:limit]).rstrip(" ,.;:")


def _stable_seed(scene: dict, index: int) -> int:
    source = json.dumps(
        {
            "index": int(index),
            "kind": scene.get("graphic_kind"),
            "anchor": scene.get("semantic_anchor"),
            "query": scene.get("query"),
            "revision": scene.get("visual_revision"),
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return int(hashlib.sha256(source.encode("utf-8")).hexdigest()[:12], 16)


def plan_for(
    script: dict,
    scene: dict,
    index: int,
    labels: list[str],
) -> dict:
    kind = str(scene.get("graphic_kind") or "generic").strip().lower()
    if kind not in GRAPHIC_KINDS:
        raise ValueError(f"unsupported Blender graphic kind: {kind!r}")
    seed = _stable_seed(scene, index)
    variant = seed % 6
    palette_index = (seed // 7) % len(PALETTES)
    cleaned = [_clean(label, 22) for label in labels if str(label).strip()]
    while len(cleaned) < 4:
        defaults = ("NOTICE", "COMPARE", "CHOOSE", "REVISE")
        cleaned.append(defaults[len(cleaned)])
    title = _clean(
        scene.get("semantic_anchor")
        or scene.get("primary_symbol")
        or scene.get("query")
        or scene.get("text"),
        54,
    )
    plan = {
        "schema_version": PLAN_VERSION,
        "backend": BACKEND,
        "kind": kind,
        "variant": variant,
        "seed": seed,
        "scene_index": int(index),
        "title": title or "LOOK AGAIN",
        "labels": cleaned[:4],
        "semantic_anchor": str(scene.get("semantic_anchor") or ""),
        "visual_function": str(scene.get("visual_function") or "literal_anchor"),
        "symbol_family": str(scene.get("symbol_family") or "object_tool"),
        "duration_seconds": max(float(scene.get("duration") or 5.0), 0.5),
        "palette": PALETTES[palette_index],
        "camera": {
            "variant": variant,
            "move": (
                "push_in", "orbit_left", "orbit_right",
                "rise", "push_in", "drift",
            )[variant],
            "intensity": 0.28 + (variant % 3) * 0.07,
        },
        "render": {
            "width": BAND_WIDTH,
            "height": BAND_HEIGHT,
            "fps": FPS,
            "work_fps": 15,
            "work_resolution_percentage": 75,
            "engine": "BLENDER_WORKBENCH",
            "transparent": False,
        },
    }
    validate_plan(plan)
    return plan


def validate_plan(plan: dict) -> None:
    errors = []
    if plan.get("schema_version") != PLAN_VERSION:
        errors.append(f"schema_version must be {PLAN_VERSION}")
    if plan.get("backend") != BACKEND:
        errors.append(f"backend must be {BACKEND!r}")
    if plan.get("kind") not in GRAPHIC_KINDS:
        errors.append("kind is not a supported 3D graphic family")
    if len(plan.get("labels") or []) != 4:
        errors.append("exactly four labels are required")
    render = plan.get("render") or {}
    if int(render.get("width") or 0) <= 0 or int(render.get("height") or 0) <= 0:
        errors.append("render dimensions must be positive")
    if int(render.get("fps") or 0) <= 0:
        errors.append("render fps must be positive")
    work_fps = int(render.get("work_fps") or render.get("fps") or 0)
    if work_fps <= 0 or work_fps > int(render.get("fps") or 0):
        errors.append("work_fps must be positive and no greater than delivery fps")
    if float(plan.get("duration_seconds") or 0) < 0.5:
        errors.append("duration_seconds must be at least 0.5")
    if errors:
        raise ValueError("invalid Blender graphic plan: " + "; ".join(errors))


def find_blender(explicit: str | None = None) -> str:
    candidate = explicit or os.environ.get("BLENDER_BIN") or shutil.which("blender")
    if not candidate or not Path(candidate).exists():
        raise BlenderUnavailable(
            "Blender was requested but is unavailable; install Blender or set BLENDER_BIN"
        )
    return str(candidate)


def _invoke(
    plan: dict,
    output: Path,
    *,
    blender: str | None = None,
    preview: bool = False,
) -> Path:
    validate_plan(plan)
    blender_bin = find_blender(blender)
    renderer = Path(__file__).resolve().parent / "blender" / "render_graphic.py"
    if not renderer.exists():
        raise BlenderRenderError(f"Blender renderer is missing: {renderer}")
    output.parent.mkdir(parents=True, exist_ok=True)
    delivery_fps = max(1, int(plan["render"].get("fps") or FPS))
    work_fps = max(1, int(plan["render"].get("work_fps") or delivery_fps))
    work_percentage = max(
        25, min(100, int(plan["render"].get("work_resolution_percentage") or 100)),
    )
    optimized = not preview and (work_fps < delivery_fps or work_percentage < 100)
    render_output = (
        output.with_name(f"{output.stem}.blender{output.suffix}")
        if optimized else output
    )
    output.unlink(missing_ok=True)
    render_output.unlink(missing_ok=True)
    plan_path = output.with_suffix(".plan.json")
    plan_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    command = [
        blender_bin,
        "--background",
        "--factory-startup",
        "--python",
        str(renderer),
        "--",
        "--plan",
        str(plan_path),
        "--output",
        str(render_output),
    ]
    if preview:
        command.append("--preview")
    timeout = max(
        int(os.environ.get("BLENDER_SCENE_TIMEOUT", "900")),
        int(float(plan["duration_seconds"]) * 20),
    )
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise BlenderRenderError(
            f"Blender scene {plan['scene_index']} exceeded {timeout}s"
        ) from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "unknown Blender error")[-3000:]
        raise BlenderRenderError(
            f"Blender scene {plan['scene_index']} failed: {detail}"
        )
    if (
        not render_output.exists()
        or render_output.stat().st_size < (20_000 if preview else 100_000)
    ):
        raise BlenderRenderError(
            f"Blender scene {plan['scene_index']} produced no usable output"
        )
    if optimized:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise BlenderRenderError("ffmpeg is required to normalize optimized 3D clips")
        filters = (
            f"fps={delivery_fps},"
            f"scale={int(plan['render']['width'])}:{int(plan['render']['height'])}:"
            "flags=lanczos"
        )
        normalized = subprocess.run(
            [
                ffmpeg, "-v", "error", "-y", "-i", str(render_output),
                "-an", "-vf", filters,
                "-t", f"{float(plan['duration_seconds']):.3f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=max(180, int(float(plan["duration_seconds"]) * 15)),
        )
        render_output.unlink(missing_ok=True)
        if normalized.returncode:
            raise BlenderRenderError(
                "3D clip normalization failed: "
                + (normalized.stderr or normalized.stdout or "unknown ffmpeg error")[-1200:]
            )
        if not output.exists() or output.stat().st_size < 100_000:
            raise BlenderRenderError("3D clip normalization produced no usable output")
    return output


def render_scene(
    build_dir: str | os.PathLike[str],
    script: dict,
    index: int,
    labels: list[str],
    *,
    blender: str | None = None,
) -> dict:
    scene = script["scenes"][int(index)]
    plan = plan_for(script, scene, int(index), labels)
    build = Path(build_dir)
    output = build / f"clip_{int(index):02d}.mp4"
    _invoke(plan, output, blender=blender)
    audit_path = build / f"blender_graphic_{int(index):02d}.json"
    audit_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return {
        "output": output,
        "plan": plan,
        "audit_path": audit_path,
    }


def preview_scene(
    build_dir: str | os.PathLike[str],
    index: int,
    output_dir: str | os.PathLike[str],
    *,
    blender: str | None = None,
) -> Path:
    build = Path(build_dir)
    script = json.loads((build / "script.json").read_text(encoding="utf-8"))
    scene = script["scenes"][int(index)]
    raw_labels = scene.get("keywords") or [scene.get("primary_symbol")]
    plan = plan_for(script, scene, int(index), list(raw_labels or []))
    output = Path(output_dir) / f"scene-{int(index) + 1:02d}-{plan['kind']}.png"
    return _invoke(plan, output, blender=blender, preview=True)


def clip_scene(
    build_dir: str | os.PathLike[str],
    index: int,
    output_dir: str | os.PathLike[str],
    *,
    blender: str | None = None,
) -> Path:
    build = Path(build_dir)
    script = json.loads((build / "script.json").read_text(encoding="utf-8"))
    scene = script["scenes"][int(index)]
    raw_labels = scene.get("keywords") or [scene.get("primary_symbol")]
    plan = plan_for(script, scene, int(index), list(raw_labels or []))
    output = Path(output_dir) / f"scene-{int(index) + 1:02d}-{plan['kind']}.mp4"
    return _invoke(plan, output, blender=blender)


def cli(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("build_dir", type=Path)
    parser.add_argument("--scene", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("blender-proof"))
    parser.add_argument("--blender", default=None)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(argv)
    renderer = preview_scene if args.preview else clip_scene
    output = renderer(
        args.build_dir, args.scene, args.output_dir, blender=args.blender,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
