"""Build and render one production 3D motion-graphic scene inside Blender."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


def _args():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--preview", action="store_true")
    return parser.parse_args(argv)


def _clear(bpy):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    collections = (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    )
    for collection in collections:
        for block in list(collection):
            if block.users == 0:
                collection.remove(block)


def _color(obj, rgba):
    obj.color = tuple(rgba)
    return obj


def _cube(bpy, name, location, dimensions, rgba, bevel=0.10, rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    if rotation is not None:
        obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        modifier = obj.modifiers.new("Soft edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
    return _color(obj, rgba)


def _sphere(bpy, name, location, radius, rgba):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=32, ring_count=16, radius=radius, location=location,
    )
    obj = bpy.context.object
    obj.name = name
    return _color(obj, rgba)


def _disc(bpy, name, location, radius, depth, rgba):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64,
        radius=radius,
        depth=depth,
        location=location,
        rotation=(math.pi / 2, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    bevel = obj.modifiers.new("Disc bevel", "BEVEL")
    bevel.width = min(depth * 0.35, 0.08)
    bevel.segments = 3
    return _color(obj, rgba)


def _torus(bpy, name, location, major_radius, minor_radius, rgba):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=64,
        minor_segments=12,
        location=location,
        rotation=(math.pi / 2, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    return _color(obj, rgba)


def _curve(bpy, name, points, rgba, width=0.07):
    data = bpy.data.curves.new(name, type="CURVE")
    data.dimensions = "3D"
    data.resolution_u = 10
    data.bevel_depth = width
    data.bevel_resolution = 4
    spline = data.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, coordinate in zip(spline.bezier_points, points):
        point.co = coordinate
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return _color(obj, rgba)


def _text(bpy, name, value, location, size, rgba, width=5.0, align="CENTER"):
    data = bpy.data.curves.new(name, type="FONT")
    data.body = str(value)
    data.align_x = align
    data.align_y = "CENTER"
    data.size = size
    data.extrude = 0.025
    data.bevel_depth = 0.008
    data.bevel_resolution = 2
    data.space_character = 1.05
    # Blender offsets centered text when a wrapping box is also assigned. Keep
    # centered labels geometry-centered; wrapping boxes are only for left copy.
    if width and align != "CENTER":
        data.text_boxes[0].width = width
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (math.pi / 2, 0.0, 0.0)
    return _color(obj, rgba)


def _empty(bpy, name, location=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    return obj


def _key(obj, frame, paths=("location", "rotation_euler", "scale")):
    for path in paths:
        obj.keyframe_insert(data_path=path, frame=frame)


def _pop(obj, start, end, overshoot=1.10):
    target = tuple(obj.scale)
    obj.scale = (0.02, 0.02, 0.02)
    obj.keyframe_insert(data_path="scale", frame=max(1, start))
    obj.scale = tuple(value * overshoot for value in target)
    obj.keyframe_insert(data_path="scale", frame=max(start + 1, end - 3))
    obj.scale = target
    obj.keyframe_insert(data_path="scale", frame=end)


def _slide(obj, start_location, end_location, start, end):
    obj.location = start_location
    obj.keyframe_insert(data_path="location", frame=max(1, start))
    obj.location = end_location
    obj.keyframe_insert(data_path="location", frame=end)


def _grow_z(obj, final_location, final_scale, start, end):
    obj.location = (final_location[0], final_location[1], 0.45)
    obj.scale = (final_scale[0], final_scale[1], 0.03)
    _key(obj, start, ("location", "scale"))
    obj.location = final_location
    obj.scale = final_scale
    _key(obj, end, ("location", "scale"))


def _look_at(obj, target, mathutils):
    direction = mathutils.Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _camera(bpy, mathutils, plan, frame_end):
    variant = int(plan["variant"])
    starts = (
        (0.0, -19.0, 3.15),
        (-0.4, -19.3, 3.35),
        (0.4, -19.1, 3.05),
        (-0.3, -18.8, 2.85),
        (0.35, -19.2, 3.45),
        (0.0, -19.4, 3.10),
    )
    ends = (
        (0.3, -17.8, 3.30),
        (0.35, -18.0, 3.15),
        (-0.35, -17.9, 3.30),
        (0.2, -18.1, 3.55),
        (-0.3, -17.7, 3.20),
        (0.4, -18.2, 3.28),
    )
    data = bpy.data.cameras.new("Graphic Camera")
    data.lens = 46 - (variant % 3)
    camera = bpy.data.objects.new("Graphic Camera", data)
    bpy.context.collection.objects.link(camera)
    camera.location = starts[variant]
    _look_at(camera, (0.0, 0.1, 2.6), mathutils)
    _key(camera, 1, ("location", "rotation_euler"))
    camera.location = ends[variant]
    _look_at(camera, (0.0, 0.15, 2.55), mathutils)
    _key(camera, frame_end, ("location", "rotation_euler"))
    bpy.context.scene.camera = camera
    return camera


def _stage(bpy, plan):
    palette = plan["palette"]
    _cube(
        bpy, "Deep background", (0, 2.4, 2.7), (18.5, 0.5, 7.4),
        palette["background"], 0.18,
    )
    _cube(
        bpy, "Ground", (0, 0.8, -0.05), (20.0, 8.0, 0.18),
        palette["surface"], 0.06,
    )
    for x in range(-8, 9, 2):
        _curve(
            bpy,
            f"Grid vertical {x}",
            [(x, 2.08, 0.15), (x, 2.08, 5.9)],
            palette["muted"],
            0.012,
        )
    for z in (0.6, 1.6, 2.6, 3.6, 4.6, 5.6):
        _curve(
            bpy,
            f"Grid horizontal {z}",
            [(-8.4, 2.08, z), (8.4, 2.08, z)],
            palette["muted"],
            0.012,
        )


def _header(bpy, plan):
    palette = plan["palette"]
    title = plan["title"]
    size = max(0.23, min(0.38, 14.0 / max(len(title), 18)))
    plate = _cube(
        bpy, "Title rail", (0, 0.9, 5.25), (15.5, 0.22, 0.72),
        palette["surface"], 0.15,
    )
    text = _text(
        bpy, "Title", title, (0, 0.75, 5.25), size,
        palette["cream"], 14.5,
    )
    _pop(plate, 1, 10)
    _pop(text, 4, 14)


def _panel(bpy, plan, name, label, x, z, width=2.8, height=1.0, color="cream", y=0.0):
    palette = plan["palette"]
    card = _cube(
        bpy, name, (x, y, z), (width, 0.34, height),
        palette[color], min(0.16, height * 0.16),
    )
    text_color = palette["background"] if color in {"cream", "gold"} else palette["cream"]
    font_size = max(0.16, min(0.30, width * 1.55 / max(len(label), 8)))
    label_obj = _text(
        bpy, f"{name} text", label, (x, y - 0.205, z),
        font_size,
        text_color, width * 0.84,
    )
    return card, label_obj


def _labels_scene(bpy, plan, frame_end):
    mirror = -1 if plan["variant"] % 2 else 1
    colors = ("cream", "cyan", "coral", "gold")
    for index, label in enumerate(plan["labels"]):
        x = mirror * (-5.4 + index * 3.6)
        z = 2.65 + (0.35 if index % 2 else -0.10)
        y = 0.25 + index * 0.22
        card, text = _panel(
            bpy, plan, f"Physical label {index}", label, x, z,
            2.75, 1.12, colors[index], y,
        )
        final_card = tuple(card.location)
        final_text = tuple(text.location)
        direction = -1 if index % 2 else 1
        _slide(
            card,
            (final_card[0] + direction * 4.0, final_card[1] + 1.4, final_card[2] + 1.2),
            final_card,
            3 + index * 5,
            18 + index * 5,
        )
        _slide(
            text,
            (final_text[0] + direction * 4.0, final_text[1] + 1.4, final_text[2] + 1.2),
            final_text,
            3 + index * 5,
            18 + index * 5,
        )
        card.rotation_euler.y = math.radians(-4 * direction)
        card.keyframe_insert(data_path="rotation_euler", frame=18 + index * 5)
        card.rotation_euler.y = 0.0
        card.keyframe_insert(data_path="rotation_euler", frame=min(frame_end, 34 + index * 5))


def _path_scene(bpy, plan, frame_end):
    palette = plan["palette"]
    mirror = -1 if plan["variant"] % 2 else 1
    points = [
        (-6.0 * mirror, 0.35, 1.0),
        (-3.8 * mirror, 0.20, 2.45),
        (-0.8 * mirror, 0.65, 1.55),
        (2.2 * mirror, 0.10, 3.20),
        (5.3 * mirror, 0.55, 2.25),
    ]
    road = _curve(bpy, "Extruded route", points, palette["coral"], 0.13)
    road.data.bevel_factor_end = 0.01
    road.data.keyframe_insert(data_path="bevel_factor_end", frame=1)
    road.data.bevel_factor_end = 1.0
    road.data.keyframe_insert(data_path="bevel_factor_end", frame=min(frame_end, 56))
    for index, point in enumerate(points[1:]):
        ring = _torus(
            bpy, f"Route node {index}",
            (point[0], point[1] - 0.12, point[2]),
            0.34 + index * 0.025, 0.08,
            (palette["cyan"], palette["gold"], palette["magenta"], palette["cream"])[index],
        )
        _pop(ring, 12 + index * 10, 25 + index * 10)
        card, text = _panel(
            bpy, plan, f"Route label {index}", plan["labels"][index],
            point[0], point[2] + 0.82, 2.35, 0.62,
            ("cream", "cyan", "gold", "coral")[index], point[1] + 0.10,
        )
        _pop(card, 18 + index * 9, 30 + index * 9)
        _pop(text, 21 + index * 9, 33 + index * 9)


def _counters_scene(bpy, plan, frame_end):
    palette = plan["palette"]
    colors = ("cyan", "magenta", "gold", "coral")
    heights = (2.1, 3.0, 1.7, 2.6)
    for index, label in enumerate(plan["labels"]):
        x = -5.4 + index * 3.6
        height = heights[(index + plan["variant"]) % len(heights)]
        bar = _cube(
            bpy, f"Counter tower {index}", (x, 0.35 + index * 0.10, 0.6 + height / 2),
            (1.65, 0.75, height), palette[colors[index]], 0.14,
        )
        final_location = tuple(bar.location)
        final_scale = tuple(bar.scale)
        _grow_z(bar, final_location, final_scale, 3 + index * 6, 36 + index * 5)
        cap = _disc(
            bpy, f"Counter cap {index}", (x, 0.0 + index * 0.10, 0.72 + height),
            0.42, 0.18, palette["cream"],
        )
        _pop(cap, 24 + index * 6, 38 + index * 6)
        text = _text(
            bpy, f"Counter text {index}", label,
            (x, -0.18 + index * 0.10, 0.56), 0.22,
            palette["cream"], 2.7,
        )
        _pop(text, 10 + index * 5, 23 + index * 5)


def _clock_scene(bpy, plan, frame_end):
    palette = plan["palette"]
    center = (-3.5, 0.2, 2.65)
    _disc(bpy, "Clock body", center, 2.05, 0.30, palette["cream"])
    _torus(bpy, "Clock rim", (center[0], -0.21, center[2]), 2.08, 0.11, palette["gold"])
    pivot = _empty(bpy, "Clock hand pivot", (center[0], -0.42, center[2]))
    hand = _cube(
        bpy, "Clock hand", (0, 0, 0.92), (0.13, 0.12, 1.84),
        palette["coral"], 0.05,
    )
    hand.parent = pivot
    pivot.rotation_euler.y = math.radians(-38)
    pivot.keyframe_insert(data_path="rotation_euler", frame=1)
    pivot.rotation_euler.y = math.radians(155 + plan["variant"] * 12)
    pivot.keyframe_insert(data_path="rotation_euler", frame=frame_end)
    _sphere(bpy, "Clock pivot", (center[0], -0.58, center[2]), 0.17, palette["coral"])
    for index, label in enumerate(plan["labels"]):
        z = 4.05 - index * 1.02
        node = _sphere(bpy, f"Timeline node {index}", (2.1 + index * 0.75, 0.25, z), 0.18, palette[("cyan", "gold", "magenta", "coral")[index]])
        _pop(node, 8 + index * 10, 20 + index * 10)
        text = _text(
            bpy, f"Timeline label {index}", label,
            (4.3, -0.05, z), 0.23, palette["cream"], 3.5,
        )
        _pop(text, 12 + index * 10, 25 + index * 10)
        if index:
            _curve(
                bpy, f"Timeline link {index}",
                [(2.1 + (index - 1) * 0.75, 0.30, z + 1.02), (2.1 + index * 0.75, 0.30, z)],
                palette["muted"], 0.045,
            )


def _focus_frame(bpy, palette, parent):
    parts = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            horizontal = _cube(
                bpy, f"Focus horizontal {sx} {sz}",
                (sx * 1.15, -0.35, sz * 0.68), (0.65, 0.10, 0.09),
                palette["cyan"], 0.03,
            )
            vertical = _cube(
                bpy, f"Focus vertical {sx} {sz}",
                (sx * 1.43, -0.35, sz * 0.44), (0.09, 0.10, 0.58),
                palette["cyan"], 0.03,
            )
            horizontal.parent = parent
            vertical.parent = parent
            parts.extend((horizontal, vertical))
    return parts


def _perception_scene(bpy, plan, frame_end):
    palette = plan["palette"]
    positions = (-4.9, -1.65, 1.65, 4.9)
    depths = (0.15, 0.65, 1.15, 1.65)
    for index, label in enumerate(plan["labels"]):
        card, text = _panel(
            bpy, plan, f"Perception card {index}", label,
            positions[index], 2.55 + (index % 2) * 0.32,
            2.55, 1.28, ("cream", "cyan", "coral", "magenta")[index],
            depths[index],
        )
        _pop(card, 2 + index * 5, 16 + index * 6)
        _pop(text, 5 + index * 5, 19 + index * 6)
    focus = _empty(bpy, "Moving focus", (positions[0], -0.65, 2.55))
    _focus_frame(bpy, palette, focus)
    for index, x in enumerate(positions):
        focus.location = (x, -0.65, 2.55 + (index % 2) * 0.32)
        focus.keyframe_insert(
            data_path="location",
            frame=max(1, round((frame_end - 1) * index / 3) + 1),
        )
    lens = _torus(bpy, "Perception lens", (0, -1.2, 2.6), 1.15, 0.10, palette["gold"])
    lens.scale = (0.25, 0.25, 0.25)
    lens.keyframe_insert(data_path="scale", frame=1)
    lens.scale = (1.0, 1.0, 1.0)
    lens.keyframe_insert(data_path="scale", frame=min(frame_end, 42))


def _evidence_scene(bpy, plan, frame_end):
    palette = plan["palette"]
    _cube(bpy, "Evidence board", (-0.7, 0.9, 2.65), (12.7, 0.38, 3.75), palette["surface"], 0.18)
    positions = ((-4.8, 3.55), (-1.7, 3.25), (-4.1, 1.75), (-0.8, 1.55))
    colors = ("cream", "cyan", "coral", "gold")
    for index, (label, position) in enumerate(zip(plan["labels"], positions)):
        card, text = _panel(
            bpy, plan, f"Evidence note {index}", label,
            position[0], position[1], 2.55, 0.90, colors[index], 0.48,
        )
        angle = math.radians((-5, 4, 3, -4)[index])
        card.rotation_euler.y = angle
        text.rotation_euler.y += angle
        _pop(card, 3 + index * 8, 19 + index * 8)
        _pop(text, 6 + index * 8, 22 + index * 8)
        pin = _sphere(
            bpy, f"Evidence pin {index}",
            (position[0], 0.16, position[1] + 0.33), 0.11,
            palette["magenta"],
        )
        _pop(pin, 12 + index * 8, 24 + index * 8)
    lens = _torus(bpy, "Magnifying lens", (3.8, -0.55, 2.75), 1.20, 0.11, palette["cyan"])
    handle = _cube(
        bpy, "Magnifying handle", (4.85, -0.45, 1.60),
        (0.22, 0.18, 1.85), palette["cyan"], 0.07,
        rotation=(0.0, math.radians(-42), 0.0),
    )
    for obj in (lens, handle):
        start = tuple(obj.location)
        _slide(obj, (start[0] + 2.8, start[1], start[2] - 0.8), start, 1, min(frame_end, 48))


def _filter_scene(bpy, plan, frame_end):
    palette = plan["palette"]
    for index, color in enumerate(("cream", "cyan", "gold")):
        slab = _cube(
            bpy, f"Incoming layer {index}",
            (-5.2 + index * 0.75, 0.85 + index * 0.28, 2.65),
            (2.4, 0.20, 3.25), palette[color], 0.14,
            rotation=(0.0, math.radians(-10 + index * 10), 0.0),
        )
        _slide(
            slab,
            (-7.7, 2.0 + index * 0.2, 2.65),
            tuple(slab.location),
            2 + index * 5,
            25 + index * 5,
        )
    _cube(bpy, "Filter console", (3.25, 0.45, 2.65), (6.9, 0.36, 3.85), palette["surface"], 0.20)
    for index, label in enumerate(plan["labels"]):
        z = 3.85 - index * 0.82
        _text(
            bpy, f"Filter label {index}", label,
            (1.5, 0.20, z), 0.23, palette["cream"], 3.3, "LEFT",
        )
        _cube(
            bpy, f"Toggle track {index}", (4.95, 0.08, z),
            (1.55, 0.18, 0.42), palette["muted"], 0.18,
        )
        knob = _sphere(
            bpy, f"Toggle knob {index}", (4.50, -0.15, z),
            0.25, palette[("cyan", "gold", "coral", "magenta")[index]],
        )
        knob.keyframe_insert(data_path="location", frame=5 + index * 8)
        knob.location.x = 5.38 if (index + plan["variant"]) % 2 else 4.62
        knob.keyframe_insert(data_path="location", frame=min(frame_end, 36 + index * 10))


def _scale_scene(bpy, plan, frame_end):
    palette = plan["palette"]
    _cube(bpy, "Scale pedestal", (0, 0.65, 1.45), (0.65, 0.75, 2.55), palette["gold"], 0.20)
    _sphere(bpy, "Scale pivot", (0, -0.05, 2.72), 0.34, palette["cream"])
    beam = _cube(bpy, "Scale beam", (0, 0.15, 2.80), (10.5, 0.35, 0.26), palette["gold"], 0.10)
    beam.rotation_euler.y = math.radians(-8)
    beam.keyframe_insert(data_path="rotation_euler", frame=1)
    beam.rotation_euler.y = math.radians(7)
    beam.keyframe_insert(data_path="rotation_euler", frame=round(frame_end * 0.55))
    beam.rotation_euler.y = math.radians(-2)
    beam.keyframe_insert(data_path="rotation_euler", frame=frame_end)
    for index, x in enumerate((-3.95, 3.95)):
        z = 2.2 + (0.35 if index else -0.25)
        _curve(
            bpy, f"Scale cord {index}",
            [(x, 0.05, 2.75), (x, 0.05, z + 0.25)],
            palette["muted"], 0.045,
        )
        pan = _disc(bpy, f"Scale pan {index}", (x, 0.05, z), 1.45, 0.18, palette[("coral", "cyan")[index]])
        pan.keyframe_insert(data_path="location", frame=1)
        pan.location.z += 0.55 if index else -0.55
        pan.keyframe_insert(data_path="location", frame=round(frame_end * 0.55))
        pan.location.z = z + (0.10 if index else -0.10)
        pan.keyframe_insert(data_path="location", frame=frame_end)
        pair = plan["labels"][index * 2 : index * 2 + 2]
        label = "\n".join(pair)
        text = _text(
            bpy, f"Scale label {index}", label,
            (x, -0.28, z), 0.22, palette["cream"], 2.20,
        )
        _pop(text, 15 + index * 12, 30 + index * 12)


def _generic_scene(bpy, plan, frame_end):
    palette = plan["palette"]
    positions = ((-5.5, 1.35), (-2.0, 3.35), (1.8, 1.75), (5.3, 3.55))
    colors = ("cream", "cyan", "coral", "gold")
    points = []
    for index, (label, (x, z)) in enumerate(zip(plan["labels"], positions)):
        y = 0.15 + index * 0.30
        card, text = _panel(
            bpy, plan, f"Mechanism node {index}", label,
            x, z, 2.55, 0.95, colors[index], y,
        )
        _pop(card, 2 + index * 9, 18 + index * 9)
        _pop(text, 5 + index * 9, 21 + index * 9)
        ring = _torus(
            bpy, f"Mechanism orbit {index}", (x, y - 0.28, z),
            0.74, 0.055, palette[("gold", "magenta", "cyan", "coral")[index]],
        )
        ring.rotation_euler.y = 0.0
        ring.keyframe_insert(data_path="rotation_euler", frame=1)
        ring.rotation_euler.y = math.radians(160 + index * 35)
        ring.keyframe_insert(data_path="rotation_euler", frame=frame_end)
        points.append((x, y + 0.25, z))
    link = _curve(bpy, "Mechanism chain", points, palette["magenta"], 0.075)
    link.data.bevel_factor_end = 0.01
    link.data.keyframe_insert(data_path="bevel_factor_end", frame=1)
    link.data.bevel_factor_end = 1.0
    link.data.keyframe_insert(data_path="bevel_factor_end", frame=min(frame_end, 70))


BUILDERS = {
    "labels": _labels_scene,
    "path": _path_scene,
    "counters": _counters_scene,
    "clock": _clock_scene,
    "perception": _perception_scene,
    "evidence": _evidence_scene,
    "filter": _filter_scene,
    "scale": _scale_scene,
    "generic": _generic_scene,
}


def _interpolation(bpy):
    for action in bpy.data.actions:
        for curve in action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "BEZIER"


def _configure(bpy, plan, output, preview):
    scene = bpy.context.scene
    render = plan["render"]
    scene.render.resolution_x = int(render["width"])
    scene.render.resolution_y = int(render["height"])
    scene.render.resolution_percentage = (
        100 if preview else int(render.get("work_resolution_percentage") or 100)
    )
    scene.render.fps = int(render["fps"])
    scene.frame_step = 1 if preview else max(1, int(render.get("frame_step") or 1))
    scene.render.image_settings.file_format = "PNG" if preview else "FFMPEG"
    scene.render.film_transparent = bool(render.get("transparent", False))
    engines = (
        str(render.get("engine") or "BLENDER_WORKBENCH"),
        "BLENDER_WORKBENCH",
        "BLENDER_EEVEE_NEXT",
        "CYCLES",
    )
    for engine in engines:
        try:
            scene.render.engine = engine
            break
        except Exception:
            continue
    if scene.render.engine == "BLENDER_WORKBENCH":
        shading = scene.display.shading
        shading.light = "STUDIO"
        shading.color_type = "OBJECT"
        shading.show_shadows = True
        shading.show_cavity = True
        shading.cavity_type = "WORLD"
        shading.curvature_ridge_factor = 1.4
        shading.curvature_valley_factor = 1.1
        shading.background_type = "WORLD"
    elif scene.render.engine == "CYCLES":
        scene.cycles.device = "CPU"
        scene.cycles.samples = 6
        scene.cycles.use_denoising = True
    world = scene.world or bpy.data.worlds.new("Graphic World")
    scene.world = world
    world.color = tuple(plan["palette"]["background"][:3])
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    scene.render.use_file_extension = True
    if preview:
        scene.render.filepath = str(Path(output).with_suffix(".png"))
    else:
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.ffmpeg.ffmpeg_preset = "GOOD"
        scene.render.filepath = str(Path(output).with_suffix(".mp4"))


def main():
    args = _args()
    import bpy
    import mathutils

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    _clear(bpy)
    fps = int(plan["render"]["fps"])
    frame_end = max(2, round(float(plan["duration_seconds"]) * fps))
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = frame_end
    _stage(bpy, plan)
    _header(bpy, plan)
    BUILDERS[plan["kind"]](bpy, plan, frame_end)
    _camera(bpy, mathutils, plan, frame_end)
    _interpolation(bpy)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    _configure(bpy, plan, output, args.preview)
    if args.preview:
        bpy.context.scene.frame_set(max(2, round(frame_end * 0.58)))
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
