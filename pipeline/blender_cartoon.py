"""CLI bridge between script.json motion plans and local Blender renders."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from pipeline.cartoon_motion import apply_motion_defaults, validate_script_motion


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("script", type=Path, help="Path to build/<slug>/script.json")
    parser.add_argument("--scene", type=int, default=None, help="Render one zero-based scene index")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--blender", default=None, help="Blender executable; defaults to BLENDER_BIN or PATH")
    parser.add_argument("--template", type=Path, default=None)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--write-normalized", action="store_true")
    return parser.parse_args()


def find_blender(explicit: str | None = None) -> str:
    import os

    candidate = explicit or os.environ.get("BLENDER_BIN") or shutil.which("blender")
    if not candidate:
        raise RuntimeError("Blender not found. Install Blender or set BLENDER_BIN to its executable.")
    return candidate


def render_script(
    script_path: Path,
    *,
    scene_index: int | None = None,
    output_dir: Path | None = None,
    blender: str | None = None,
    template: Path | None = None,
    preview: bool = False,
    write_normalized: bool = False,
) -> list[Path]:
    script_path = script_path.resolve()
    script = json.loads(script_path.read_text(encoding="utf-8"))
    changed = apply_motion_defaults(script)
    errors = validate_script_motion(script)
    if errors:
        raise ValueError("Invalid cartoon motion plan:\n- " + "\n- ".join(errors))
    if write_normalized and changed:
        script_path.write_text(json.dumps(script, indent=2) + "\n", encoding="utf-8")

    scenes = script.get("scenes") or []
    selected = range(len(scenes)) if scene_index is None else [scene_index]
    destination = (output_dir or script_path.parent / "cartoon-renders").resolve()
    destination.mkdir(parents=True, exist_ok=True)
    blender_bin = find_blender(blender)
    renderer = Path(__file__).with_name("blender") / "render_scene.py"
    outputs: list[Path] = []

    for index in selected:
        if index < 0 or index >= len(scenes):
            raise IndexError(f"scene index {index} outside 0..{len(scenes)-1}")
        plan = scenes[index].get("motion_plan")
        if not plan:
            continue
        suffix = ".png" if preview else ".mp4"
        output = destination / f"scene-{index + 1:02d}{suffix}"
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
            json.dump(plan, handle, indent=2)
            plan_path = Path(handle.name)
        command = [
            blender_bin,
            "--background",
            "--python",
            str(renderer),
            "--",
            "--plan",
            str(plan_path),
            "--output",
            str(output),
        ]
        if template:
            command += ["--template", str(template.resolve())]
        if preview:
            command.append("--preview")
        try:
            subprocess.run(command, check=True)
        finally:
            plan_path.unlink(missing_ok=True)
        outputs.append(output)
    return outputs


def main() -> None:
    args = _parse_args()
    outputs = render_script(
        args.script,
        scene_index=args.scene,
        output_dir=args.output_dir,
        blender=args.blender,
        template=args.template,
        preview=args.preview,
        write_normalized=args.write_normalized,
    )
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
