"""Render one cartoon motion-plan scene with local Blender.

Usage:
    blender --background --python pipeline/blender/render_scene.py -- \
        --plan path/to/motion-plan.json --output path/to/scene.mp4

The file imports ``bpy`` only at runtime so normal Python tests do not require
Blender. Phase 1 creates a clean 9:16 stage, camera, lighting and atmosphere.
Character rigs and authored environments can be linked later without changing the
motion-plan contract.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


def _args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--template", default=None, help="Optional .blend file to open first")
    parser.add_argument("--preview", action="store_true", help="Render PNG frame instead of MP4")
    return parser.parse_args(argv)


def _clear_scene(bpy) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def _look_at(obj, target, mathutils) -> None:
    direction = mathutils.Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _make_camera(bpy, mathutils, plan: dict, frame_end: int):
    data = plan["camera"]
    cam_data = bpy.data.cameras.new("CE_Camera")
    cam_data.lens = float(data.get("lens_mm", 50.0))
    cam = bpy.data.objects.new("CE_Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    start = data.get("start", [0.0, -12.0, 1.5])
    end = data.get("end", start)
    cam.location = start
    _look_at(cam, (0.0, 0.0, 1.5), mathutils)
    cam.keyframe_insert(data_path="location", frame=1)

    move = data.get("move", "locked")
    intensity = float(data.get("intensity", 0.0))
    if move != "locked" and end == start:
        end = list(start)
        delta = 2.0 * intensity
        if move == "push_in":
            end[1] += delta
        elif move == "pull_out":
            end[1] -= delta
        elif move == "pan_left":
            end[0] -= delta
        elif move == "pan_right":
            end[0] += delta
        elif move == "tilt_up":
            end[2] += delta
        elif move == "tilt_down":
            end[2] -= delta
        elif move == "orbit":
            angle = math.radians(12.0 * intensity)
            radius = abs(start[1])
            end[0] = math.sin(angle) * radius
            end[1] = -math.cos(angle) * radius
    cam.location = end
    _look_at(cam, (0.0, 0.0, 1.5), mathutils)
    cam.keyframe_insert(data_path="location", frame=frame_end)
    bpy.context.scene.camera = cam
    return cam


def _add_area_light(bpy, name: str, location, energy: float, size: float, target=(0, 0, 1.5)):
    import mathutils

    light_data = bpy.data.lights.new(name, type="AREA")
    light_data.energy = energy
    light_data.shape = "DISK"
    light_data.size = size
    obj = bpy.data.objects.new(name, light_data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    _look_at(obj, target, mathutils)
    return obj


def _make_lighting(bpy, plan: dict) -> None:
    data = plan["lighting"]
    _add_area_light(bpy, "CE_Key", (-4, -5, 7), float(data.get("key_energy", 800)), 5.0)
    _add_area_light(bpy, "CE_Fill", (4, -2, 4), float(data.get("fill_energy", 300)), 4.0)
    _add_area_light(bpy, "CE_Rim", (0, 4, 6), float(data.get("rim_energy", 500)), 3.0)
    world = bpy.context.scene.world or bpy.data.worlds.new("CE_World")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = float(data.get("world_strength", 0.35))


def _make_stage(bpy, frame_end: int) -> None:
    # Ground plane
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "CE_Ground"
    mat = bpy.data.materials.new("CE_Ground_Material")
    mat.diffuse_color = (0.035, 0.04, 0.055, 1.0)
    ground.data.materials.append(mat)

    # A simple moving focus object proves true temporal rendering in Phase 1.
    bpy.ops.mesh.primitive_cube_add(size=2.2, location=(0, 0, 1.1))
    focus = bpy.context.object
    focus.name = "CE_Focus_Proxy"
    focus.scale = (0.8, 0.25, 1.2)
    focus.keyframe_insert(data_path="rotation_euler", frame=1)
    focus.rotation_euler[2] = math.radians(6)
    focus.keyframe_insert(data_path="rotation_euler", frame=frame_end)
    mat2 = bpy.data.materials.new("CE_Focus_Material")
    mat2.diffuse_color = (0.18, 0.28, 0.5, 1.0)
    focus.data.materials.append(mat2)


def _make_atmosphere(bpy, plan: dict, frame_end: int) -> None:
    data = plan["atmosphere"]
    if data.get("dust"):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.08, location=(-1.5, 0, 2.0))
        dust = bpy.context.object
        dust.name = "CE_Dust_Proxy"
        dust.keyframe_insert(data_path="location", frame=1)
        dust.location.x = 1.5
        dust.location.z += 0.8
        dust.keyframe_insert(data_path="location", frame=frame_end)
    if data.get("steam"):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.18, location=(1.2, 0, 1.5))
        steam = bpy.context.object
        steam.name = "CE_Steam_Proxy"
        steam.scale = (0.6, 0.6, 1.8)
        steam.keyframe_insert(data_path="location", frame=1)
        steam.location.z += 1.3
        steam.scale *= 1.6
        steam.keyframe_insert(data_path="location", frame=frame_end)
        steam.keyframe_insert(data_path="scale", frame=frame_end)


def _configure_render(bpy, plan: dict, output: Path, preview: bool) -> None:
    scene = bpy.context.scene
    render = plan["render"]
    scene.render.resolution_x = int(render.get("width", 1080))
    scene.render.resolution_y = int(render.get("height", 1920))
    scene.render.resolution_percentage = 100
    scene.render.fps = int(render.get("fps", 24))
    scene.render.image_settings.file_format = "PNG" if preview else "FFMPEG"
    scene.render.film_transparent = bool(render.get("transparent", False))
    if preview:
        scene.render.filepath = str(output.with_suffix(".png"))
    else:
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.ffmpeg.audio_codec = "AAC"
        scene.render.filepath = str(output)
    _select_engine(bpy, scene, render)


def _select_engine(bpy, scene, render: dict) -> None:
    """Pick a headless-safe render engine.

    GitHub-hosted runners have no GPU, so BLENDER_EEVEE_NEXT (GPU-only in 4.2+)
    cannot render there. Cycles on CPU always works headless, so we try the
    requested engine first, then fall back through Cycles and both EEVEE names.
    """
    desired = str(render.get("engine", "CYCLES"))
    for eng in (desired, "CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = eng
            break
        except Exception:
            continue
    if scene.render.engine == "CYCLES":
        scene.cycles.device = "CPU"
        try:
            scene.cycles.samples = int(render.get("samples", 24))
        except (TypeError, ValueError):
            scene.cycles.samples = 24


def main() -> None:
    args = _args()
    import bpy
    import mathutils

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if args.template:
        bpy.ops.wm.open_mainfile(filepath=str(Path(args.template).resolve()))
    else:
        _clear_scene(bpy)

    fps = int(plan["render"].get("fps", 24))
    frame_end = max(1, round(float(plan["duration_seconds"]) * fps))
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = frame_end

    _make_stage(bpy, frame_end)
    _make_camera(bpy, mathutils, plan, frame_end)
    _make_lighting(bpy, plan)
    _make_atmosphere(bpy, plan, frame_end)
    _configure_render(bpy, plan, Path(args.output), args.preview)

    if args.preview:
        bpy.context.scene.frame_set(max(1, frame_end // 2))
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
