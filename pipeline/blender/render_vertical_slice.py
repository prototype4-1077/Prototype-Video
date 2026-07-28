"""Build and render the reusable June Oxley porch-dialogue scene in Blender.

The asset is intentionally code-native for now: CI can prove the entire shot,
rig, viseme, lighting, and frame-sequence path without committing binary media or
a fragile .blend file.  A later authored June asset can replace ``_make_june``
without changing the compiled plan contract.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


def _args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--asset-library", help="Optional runtime-built June + porch .blend library")
    parser.add_argument("--frames", help="Comma-separated frames for a still-only quality gate")
    return parser.parse_args(argv)


def _clear(bpy) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.armatures,
        bpy.data.actions,
    ):
        for block in list(blocks):
            if block.users == 0:
                blocks.remove(block)


def _material(
    bpy,
    name: str,
    color,
    *,
    emission: float = 0.0,
    roughness: float = 0.75,
    texture_scale: float = 0.0,
    bump_strength: float = 0.0,
):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = (*color[:3], color[3] if len(color) > 3 else 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = material.diffuse_color
        principled.inputs["Roughness"].default_value = roughness
        if principled.inputs.get("Specular IOR Level") is not None:
            principled.inputs["Specular IOR Level"].default_value = 0.28
        if emission:
            emission_input = principled.inputs.get("Emission Color") or principled.inputs.get("Emission")
            strength_input = principled.inputs.get("Emission Strength")
            if emission_input:
                emission_input.default_value = material.diffuse_color
            if strength_input:
                strength_input.default_value = emission
        if texture_scale and bump_strength and not material.node_tree.nodes.get("CE_Tactile_Texture"):
            noise = material.node_tree.nodes.new("ShaderNodeTexNoise")
            noise.name = "CE_Tactile_Texture"
            noise.inputs["Scale"].default_value = texture_scale
            noise.inputs["Detail"].default_value = 3.0
            noise.inputs["Roughness"].default_value = 0.7
            bump = material.node_tree.nodes.new("ShaderNodeBump")
            bump.name = "CE_Tactile_Bump"
            bump.inputs["Strength"].default_value = bump_strength
            bump.inputs["Distance"].default_value = 0.04
            material.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
            material.node_tree.links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    return material


def _plaid_shader(material, base_color, stripe_color) -> None:
    """Add woven crossing bands without relying on committed bitmap textures."""
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = nodes.get("Principled BSDF")
    if principled is None or nodes.get("CE_Plaid_X"):
        return
    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.name = "CE_Plaid_Coordinates"
    wave_x = nodes.new("ShaderNodeTexWave")
    wave_x.name = "CE_Plaid_X"
    wave_x.wave_type = "BANDS"
    wave_x.bands_direction = "X"
    wave_x.inputs["Scale"].default_value = 7.0
    wave_x.inputs["Distortion"].default_value = 1.2
    wave_z = nodes.new("ShaderNodeTexWave")
    wave_z.name = "CE_Plaid_Z"
    wave_z.wave_type = "BANDS"
    wave_z.bands_direction = "Z"
    wave_z.inputs["Scale"].default_value = 10.0
    wave_z.inputs["Distortion"].default_value = 0.7
    maximum = nodes.new("ShaderNodeMath")
    maximum.name = "CE_Plaid_Cross"
    maximum.operation = "MAXIMUM"
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.name = "CE_Plaid_Color"
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].position = 0.56
    ramp.color_ramp.elements[0].color = base_color
    ramp.color_ramp.elements[1].position = 0.72
    ramp.color_ramp.elements[1].color = stripe_color
    links.new(texcoord.outputs["Generated"], wave_x.inputs["Vector"])
    links.new(texcoord.outputs["Generated"], wave_z.inputs["Vector"])
    links.new(wave_x.outputs["Color"], maximum.inputs[0])
    links.new(wave_z.outputs["Color"], maximum.inputs[1])
    links.new(maximum.outputs[0], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], principled.inputs["Base Color"])


def _make_materials(bpy, *, asset_major: int = 2) -> dict:
    """Create the canonical tactile porch and June material library."""
    materials = {
        "cedar": _material(bpy, "Warm Cedar", (0.38, 0.17, 0.075, 1), texture_scale=5.0, bump_strength=0.20),
        "dark_wood": _material(bpy, "Deep Wood", (0.16, 0.065, 0.032, 1), texture_scale=7.0, bump_strength=0.16),
        "cream": _material(bpy, "Porch Cream", (0.72, 0.66, 0.51, 1)),
        "sage": _material(bpy, "Sage Door", (0.22, 0.34, 0.27, 1), texture_scale=4.0, bump_strength=0.08),
        "metal": _material(bpy, "Aged Metal", (0.24, 0.27, 0.26, 1), roughness=0.35),
        "brass": _material(bpy, "Aged Brass", (0.48, 0.29, 0.08, 1), roughness=0.28),
        "window": _material(bpy, "Window Warmth", (0.95, 0.46, 0.15, 1), emission=2.2),
        "lantern": _material(bpy, "Visible Lantern Glow", (1.0, 0.30, 0.055, 1), emission=4.0),
        "terracotta": _material(bpy, "Terracotta", (0.44, 0.16, 0.08, 1), texture_scale=5.0, bump_strength=0.12),
        "leaf": _material(bpy, "Porch Plant", (0.13, 0.34, 0.16, 1)),
        "skin": _material(bpy, "June Skin", (0.72, 0.48, 0.34, 1), texture_scale=18.0, bump_strength=0.07),
        "skin_shadow": _material(bpy, "June Skin Shadow", (0.58, 0.33, 0.24, 1), texture_scale=18.0, bump_strength=0.06),
        "hair": _material(bpy, "June White Hair", (0.86, 0.84, 0.76, 1), roughness=0.9),
        "denim": _material(bpy, "June Faded Denim", (0.10, 0.22, 0.31, 1), texture_scale=45.0, bump_strength=0.13),
        "dark_denim": _material(bpy, "June Denim Shadow", (0.035, 0.075, 0.11, 1), texture_scale=45.0, bump_strength=0.12),
        "overalls": _material(bpy, "June Dark Overalls", (0.045, 0.10, 0.14, 1), texture_scale=48.0, bump_strength=0.14),
        "plaid": _material(bpy, "June Shirt Plaid", (0.46, 0.16, 0.10, 1), texture_scale=35.0, bump_strength=0.09),
        "leather": _material(bpy, "Worn Boot Leather", (0.20, 0.09, 0.035, 1), texture_scale=9.0, bump_strength=0.22),
        "eye": _material(bpy, "Eye White", (0.90, 0.87, 0.77, 1), roughness=0.25),
        "iris": _material(bpy, "June Blue Gray Iris", (0.12, 0.30, 0.34, 1), roughness=0.16),
        "pupil": _material(bpy, "June Blue Gray Eyes", (0.06, 0.16, 0.19, 1), roughness=0.18),
        "pupil_v2": _material(bpy, "June Pupil", (0.012, 0.018, 0.020, 1), roughness=0.12),
        "catchlight": _material(bpy, "June Eye Catchlight", (1.0, 0.96, 0.82, 1), emission=0.25, roughness=0.12),
        "mouth": _material(bpy, "June Mouth", (0.20, 0.025, 0.025, 1), roughness=0.45),
        "mouth_interior": _material(bpy, "June Mouth Interior", (0.105, 0.012, 0.014, 1), roughness=0.55),
        "lip": _material(bpy, "June Weathered Lip", (0.38, 0.095, 0.075, 1), roughness=0.62),
        "teeth": _material(bpy, "June Teeth", (0.78, 0.72, 0.58, 1), roughness=0.48),
        "sole": _material(bpy, "June Boot Sole", (0.055, 0.030, 0.022, 1), texture_scale=10.0, bump_strength=0.12),
    }
    if asset_major >= 2:
        _plaid_shader(materials["plaid"], (0.46, 0.16, 0.10, 1), (0.08, 0.13, 0.17, 1))
        skin_principled = materials["skin"].node_tree.nodes.get("Principled BSDF")
        if skin_principled and skin_principled.inputs.get("Subsurface Weight") is not None:
            skin_principled.inputs["Subsurface Weight"].default_value = 0.08
    return materials


def _assign(obj, material):
    if getattr(obj.data, "materials", None) is not None:
        obj.data.materials.append(material)
    return obj


def _smooth(obj):
    if getattr(obj, "data", None) and getattr(obj.data, "polygons", None) is not None:
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    return obj


def _box(bpy, name: str, location, scale, material, *, bevel: float = 0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new("Soft production edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return _smooth(_assign(obj, material))


def _sphere(bpy, name: str, location, scale, material, *, segments: int = 24, rings: int = 12):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _smooth(_assign(obj, material))


def _cylinder(bpy, name: str, location, radius: float, depth: float, material, *, vertices: int = 20):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    return _smooth(_assign(obj, material))


def _cylinder_between(bpy, mathutils, name: str, start, end, radius: float, material):
    start_v = mathutils.Vector(start)
    end_v = mathutils.Vector(end)
    delta = end_v - start_v
    obj = _cylinder(bpy, name, (start_v + end_v) / 2.0, radius, delta.length, material)
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    return obj


def _tapered_between(bpy, mathutils, name: str, start, end, radius_start: float, radius_end: float, material, *, vertices: int = 24):
    start_v = mathutils.Vector(start)
    end_v = mathutils.Vector(end)
    delta = end_v - start_v
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius_end,
        radius2=radius_start,
        depth=delta.length,
        location=(start_v + end_v) / 2.0,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    bevel = obj.modifiers.new("CE_Soft_Joint", "BEVEL")
    bevel.width = min(radius_start, radius_end) * 0.32
    bevel.segments = 3
    return _smooth(_assign(obj, material))


def _curve(bpy, name: str, points, material, *, bevel_depth: float = 0.008, cyclic: bool = False):
    curve_data = bpy.data.curves.new(f"{name}_Data", "CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 8
    curve_data.bevel_depth = bevel_depth
    curve_data.bevel_resolution = 3
    spline = curve_data.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, coordinate in zip(spline.bezier_points, points):
        point.co = coordinate
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    return _assign(obj, material)


def _parent_to_bone(obj, rig, bone_name: str) -> None:
    matrix = obj.matrix_world.copy()
    obj.parent = rig
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = matrix


def _look_at(obj, target, mathutils) -> None:
    direction = mathutils.Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _make_porch(bpy, mathutils, materials: dict, frame_end: int) -> None:
    cedar = materials["cedar"]
    dark_wood = materials["dark_wood"]
    cream = materials["cream"]
    sage = materials["sage"]
    metal = materials["metal"]

    for index in range(15):
        plank = _box(
            bpy,
            f"Porch_Floor_Plank_{index:02d}",
            ((index - 7) * 0.48, 0.25, 0.02),
            (0.225, 4.0, 0.07),
            cedar if index % 2 else dark_wood,
            bevel=0.025,
        )
        plank.rotation_euler[2] = math.radians(0.25 * ((index % 3) - 1))
    _box(bpy, "Porch_Back_Wall", (0, 2.75, 2.55), (4.4, 0.12, 2.55), cream, bevel=0.04)
    _box(bpy, "Porch_Door", (2.35, 2.58, 2.1), (0.72, 0.08, 1.55), sage, bevel=0.07)
    _sphere(bpy, "Door_Knob", (1.88, 2.47, 2.08), (0.08, 0.04, 0.08), metal)
    _box(bpy, "Window_Frame", (-2.1, 2.52, 2.65), (0.98, 0.07, 0.85), dark_wood, bevel=0.04)
    _box(bpy, "Window_Glow", (-2.1, 2.43, 2.65), (0.82, 0.035, 0.69), materials["window"], bevel=0.02)
    _box(bpy, "Window_Mullion_V", (-2.1, 2.35, 2.65), (0.035, 0.04, 0.72), dark_wood)
    _box(bpy, "Window_Mullion_H", (-2.1, 2.35, 2.65), (0.85, 0.04, 0.035), dark_wood)

    for x in (-3.7, 3.7):
        _cylinder(bpy, f"Porch_Column_{x}", (x, 1.0, 2.7), 0.18, 5.35, cream)
    for x in (-3.65, 3.65):
        for z in (0.65, 1.13):
            _box(bpy, f"Rail_{x}_{z}", (x, -0.25, z), (0.10, 2.35, 0.09), cream, bevel=0.03)
        for y in (-2.2, -1.3, -0.4, 0.5, 1.4):
            _box(bpy, f"Spindle_{x}_{y}", (x, y, 0.88), (0.07, 0.07, 0.55), cream, bevel=0.02)

    # Rocking chair silhouette behind June.
    _box(bpy, "Chair_Back", (0, 0.72, 1.65), (0.72, 0.10, 0.82), dark_wood, bevel=0.12)
    _box(bpy, "Chair_Seat", (0, 0.20, 1.18), (0.78, 0.67, 0.10), cedar, bevel=0.09)
    for x in (-0.68, 0.68):
        _cylinder_between(bpy, mathutils, f"Chair_Leg_{x}", (x, 0.48, 0.35), (x, 0.15, 1.22), 0.075, dark_wood)
        _box(bpy, f"Chair_Arm_{x}", (x, -0.02, 1.55), (0.08, 0.72, 0.07), dark_wood, bevel=0.04)
        rocker = _box(bpy, f"Chair_Rocker_{x}", (x, 0.25, 0.27), (0.08, 1.05, 0.07), dark_wood, bevel=0.07)
        rocker.rotation_euler[0] = math.radians(-3)

    # A lantern is both set dressing and the required visible warm light source.
    _box(bpy, "Lantern_Backplate", (1.05, 2.38, 3.55), (0.22, 0.08, 0.28), dark_wood, bevel=0.05)
    _cylinder(bpy, "Lantern_Glow", (1.05, 2.27, 3.40), 0.18, 0.42, materials["lantern"], vertices=16)
    _box(bpy, "Lantern_Top", (1.05, 2.27, 3.65), (0.26, 0.21, 0.05), metal, bevel=0.03)

    # Plant and wind chimes guarantee independent secondary motion.
    _cylinder(bpy, "Plant_Pot", (-2.9, 1.7, 0.36), 0.34, 0.58, materials["terracotta"], vertices=20)
    plant_control = bpy.data.objects.new("Plant_Drift_Control", None)
    bpy.context.collection.objects.link(plant_control)
    plant_control.location = (-2.9, 1.7, 0.62)
    for index, angle in enumerate((-55, -25, 8, 38, 68)):
        leaf = _sphere(bpy, f"Plant_Leaf_{index}", (-2.9, 1.7, 0.82), (0.12, 0.035, 0.55), materials["leaf"])
        leaf.rotation_euler[1] = math.radians(angle)
        matrix = leaf.matrix_world.copy()
        leaf.parent = plant_control
        leaf.matrix_world = matrix
    plant_control.rotation_euler[1] = math.radians(-2)
    plant_control.keyframe_insert(data_path="rotation_euler", frame=1)
    plant_control.rotation_euler[1] = math.radians(3)
    plant_control.keyframe_insert(data_path="rotation_euler", frame=max(2, frame_end // 2))
    plant_control.rotation_euler[1] = math.radians(-2)
    plant_control.keyframe_insert(data_path="rotation_euler", frame=frame_end)

    chime_control = bpy.data.objects.new("Wind_Chime_Control", None)
    bpy.context.collection.objects.link(chime_control)
    chime_control.location = (-1.0, 2.18, 4.25)
    _cylinder_between(bpy, mathutils, "Chime_Cord", (-1.0, 2.18, 4.82), (-1.0, 2.18, 4.18), 0.018, metal)
    for index, x in enumerate((-0.18, -0.06, 0.07, 0.2)):
        tube = _cylinder(bpy, f"Wind_Chime_{index}", (-1.0 + x, 2.18, 3.92 - abs(x)), 0.035, 0.55, metal, vertices=12)
        matrix = tube.matrix_world.copy()
        tube.parent = chime_control
        tube.matrix_world = matrix
    for frame, degrees in ((1, -4), (frame_end // 3, 5), (2 * frame_end // 3, -3), (frame_end, 4)):
        chime_control.rotation_euler[1] = math.radians(degrees)
        chime_control.keyframe_insert(data_path="rotation_euler", frame=max(1, frame))


def _make_armature(bpy):
    armature = bpy.data.armatures.new("June_Oxley_Rig_Data")
    rig = bpy.data.objects.new("June_Oxley_Rig", armature)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bones = {
        "root": ((0, 0, 0.72), (0, 0, 1.04), None),
        "pelvis": ((0, 0, 1.04), (0, 0, 1.34), "root"),
        "torso": ((0, 0, 1.34), (0, 0, 2.24), "pelvis"),
        "neck": ((0, 0, 2.24), (0, 0, 2.40), "torso"),
        "head": ((0, 0, 2.40), (0, 0, 2.82), "neck"),
        "upper_arm.L": ((-0.35, 0, 2.10), (-0.62, -0.05, 1.82), "torso"),
        "forearm.L": ((-0.62, -0.05, 1.82), (-0.64, -0.40, 1.50), "upper_arm.L"),
        "hand.L": ((-0.64, -0.40, 1.50), (-0.64, -0.49, 1.35), "forearm.L"),
        "upper_arm.R": ((0.35, 0, 2.10), (0.62, -0.05, 1.82), "torso"),
        "forearm.R": ((0.62, -0.05, 1.82), (0.64, -0.40, 1.50), "upper_arm.R"),
        "hand.R": ((0.64, -0.40, 1.50), (0.64, -0.49, 1.35), "forearm.R"),
        "thigh.L": ((-0.19, 0, 1.16), (-0.22, -0.55, 1.00), "pelvis"),
        "shin.L": ((-0.22, -0.55, 1.00), (-0.22, -0.60, 0.34), "thigh.L"),
        "foot.L": ((-0.22, -0.60, 0.34), (-0.22, -0.90, 0.25), "shin.L"),
        "thigh.R": ((0.19, 0, 1.16), (0.22, -0.55, 1.00), "pelvis"),
        "shin.R": ((0.22, -0.55, 1.00), (0.22, -0.60, 0.34), "thigh.R"),
        "foot.R": ((0.22, -0.60, 0.34), (0.22, -0.90, 0.25), "shin.R"),
    }
    created = {}
    for name, (head, tail, parent) in bones.items():
        bone = armature.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
        if parent:
            bone.parent = created[parent]
        created[name] = bone
    bpy.ops.object.mode_set(mode="POSE")
    for bone in rig.pose.bones:
        bone.rotation_mode = "XYZ"
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = True
    armature.display_type = "BBONE"
    return rig


def _make_mouth_v1(bpy, rig, material):
    mouth = _sphere(bpy, "June_Mouth_Viseme", (0, -0.365, 2.48), (0.22, 0.035, 0.075), material, segments=32, rings=12)
    basis = mouth.shape_key_add(name="Basis")
    shape_scale = {
        "A": (1.00, 0.80),
        "B": (0.70, 1.35),
        "C": (1.15, 0.55),
        "D": (0.82, 1.10),
        "E": (1.18, 0.35),
        "F": (0.62, 0.72),
        "G": (0.52, 1.22),
        "H": (0.42, 0.92),
        "X": (0.92, 0.16),
    }
    for name, (width, height) in shape_scale.items():
        key = mouth.shape_key_add(name=name)
        for source, target in zip(basis.data, key.data):
            target.co.x = source.co.x * width
            target.co.z = source.co.z * height
    _parent_to_bone(mouth, rig, "head")
    return mouth


def _make_june_v1(bpy, mathutils, materials: dict):
    rig = _make_armature(bpy)
    skin = materials["skin"]
    skin_shadow = materials["skin_shadow"]
    hair = materials["hair"]
    denim = materials["denim"]
    dark_denim = materials["dark_denim"]

    # Phase 3 replaces the round integration proxy with June's canonical lean,
    # wiry silhouette and a layered work-shirt / overalls / jacket wardrobe.
    torso = _sphere(bpy, "June_Plaid_Torso", (0, 0.02, 1.78), (0.43, 0.255, 0.66), materials["plaid"])
    _parent_to_bone(torso, rig, "torso")
    bib = _box(bpy, "June_Overall_Bib", (0, -0.258, 1.70), (0.255, 0.025, 0.36), materials["overalls"], bevel=0.045)
    _parent_to_bone(bib, rig, "torso")
    for side, x in (("L", -0.23), ("R", 0.23)):
        strap = _box(bpy, f"June_Overall_Strap_{side}", (x, -0.266, 2.00), (0.042, 0.018, 0.34), materials["overalls"], bevel=0.018)
        strap.rotation_euler[1] = math.radians(-7 if side == "L" else 7)
        _parent_to_bone(strap, rig, "torso")
        button = _sphere(bpy, f"June_Overall_Button_{side}", (x, -0.292, 1.89), (0.037, 0.018, 0.037), materials["brass"])
        _parent_to_bone(button, rig, "torso")
    for side, x in (("L", -0.39), ("R", 0.39)):
        jacket = _sphere(bpy, f"June_Denim_Jacket_{side}", (x, 0.025, 1.80), (0.16, 0.275, 0.62), denim)
        _parent_to_bone(jacket, rig, "torso")
    shirt_placket = _box(bpy, "June_Shirt_Placket", (0, -0.283, 1.92), (0.026, 0.014, 0.30), dark_denim, bevel=0.008)
    _parent_to_bone(shirt_placket, rig, "torso")
    for index, z in enumerate((1.54, 1.74, 1.94, 2.14)):
        stripe = _box(bpy, f"June_Plaid_Stripe_{index}", (0, -0.278, z), (0.34, 0.011, 0.014), dark_denim, bevel=0.006)
        _parent_to_bone(stripe, rig, "torso")
    for index, x in enumerate((-0.26, 0.26)):
        stripe = _box(bpy, f"June_Plaid_Vertical_{index}", (x, -0.279, 1.91), (0.012, 0.012, 0.31), dark_denim, bevel=0.004)
        _parent_to_bone(stripe, rig, "torso")
    neck = _cylinder(bpy, "June_Neck", (0, 0, 2.27), 0.145, 0.25, skin)
    _parent_to_bone(neck, rig, "neck")

    head = _sphere(bpy, "June_Head", (0, 0, 2.63), (0.315, 0.275, 0.405), skin, segments=40, rings=20)
    head_basis = head.shape_key_add(name="Basis")
    for control in ("smile", "thoughtful", "soft_chuckle"):
        key = head.shape_key_add(name=control)
        for source, target in zip(head_basis.data, key.data):
            front = max(0.0, min(1.0, -source.co.y / 0.27))
            lower = max(0.0, min(1.0, (0.10 - source.co.z) / 0.34))
            if control == "smile":
                target.co.x *= 1.0 + 0.035 * front * lower
                target.co.z += 0.012 * front * lower * min(1.0, abs(source.co.x) / 0.22)
            elif control == "thoughtful":
                target.co.x += 0.008 * front * lower
                target.co.z -= 0.006 * front * lower
            else:
                target.co.x *= 1.0 + 0.025 * front
                target.co.z += 0.010 * front * lower
    head["ce_expression_controls"] = "smile,thoughtful,soft_chuckle"
    _parent_to_bone(head, rig, "head")
    for x in (-0.32, 0.32):
        ear = _sphere(bpy, f"June_Ear_{x}", (x, 0, 2.63), (0.065, 0.042, 0.105), skin_shadow)
        _parent_to_bone(ear, rig, "head")
    nose = _sphere(bpy, "June_Nose", (0, -0.304, 2.61), (0.067, 0.084, 0.115), skin_shadow)
    _parent_to_bone(nose, rig, "head")

    # Thinning hair and a close beard match the June bible without cowboy shorthand.
    for index, (x, z, sx) in enumerate(((-0.20, 2.94, 0.13), (0.20, 2.94, 0.13), (-0.285, 2.80, 0.095), (0.285, 2.80, 0.095))):
        tuft = _sphere(bpy, f"June_White_Hair_{index}", (x, 0.04, z), (sx, 0.22, 0.105), hair)
        _parent_to_bone(tuft, rig, "head")
    beard = _sphere(bpy, "June_Close_Beard", (0, -0.155, 2.42), (0.248, 0.16, 0.23), hair, segments=32, rings=16)
    _parent_to_bone(beard, rig, "head")
    for index, x in enumerate((-0.085, 0.085)):
        moustache = _sphere(bpy, f"June_Moustache_{index}", (x, -0.315, 2.535), (0.095, 0.022, 0.033), hair)
        moustache.rotation_euler[1] = math.radians((-1 if x < 0 else 1) * 10)
        _parent_to_bone(moustache, rig, "head")

    eyes = []
    for side, x in (("L", -0.12), ("R", 0.12)):
        eye = _sphere(bpy, f"June_Eye_{side}", (x, -0.269, 2.72), (0.062, 0.030, 0.046), materials["eye"])
        pupil = _sphere(bpy, f"June_Pupil_{side}", (x, -0.300, 2.72), (0.023, 0.015, 0.027), materials["pupil"])
        brow = _box(bpy, f"June_Brow_{side}", (x, -0.291, 2.81), (0.082, 0.015, 0.014), hair, bevel=0.010)
        brow.rotation_euler[1] = math.radians(5 if side == "L" else -5)
        brow["ce_face_control"] = f"brow.{side}"
        for obj in (eye, pupil, brow):
            _parent_to_bone(obj, rig, "head")
        eyes.extend((eye, pupil))

    # Fine silhouette marks make the weathered face readable without texture maps.
    for index, z in enumerate((2.835, 2.865, 2.892)):
        wrinkle = _box(bpy, f"June_Forehead_Line_{index}", (0, -0.277, z), (0.105 - index * 0.012, 0.006, 0.004), skin_shadow, bevel=0.003)
        _parent_to_bone(wrinkle, rig, "head")
    for side, x in (("L", -0.19), ("R", 0.19)):
        smile_line = _cylinder_between(bpy, mathutils, f"June_Smile_Line_{side}", (x, -0.286, 2.56), (x * 0.92, -0.292, 2.47), 0.006, skin_shadow)
        _parent_to_bone(smile_line, rig, "head")

    limb_specs = (
        ("upper_arm.L", (-0.35, 0, 2.10), (-0.62, -0.05, 1.82), denim),
        ("forearm.L", (-0.62, -0.05, 1.82), (-0.64, -0.40, 1.50), skin),
        ("upper_arm.R", (0.35, 0, 2.10), (0.62, -0.05, 1.82), denim),
        ("forearm.R", (0.62, -0.05, 1.82), (0.64, -0.40, 1.50), skin),
    )
    for bone, start, end, material in limb_specs:
        limb = _cylinder_between(bpy, mathutils, f"June_{bone}", start, end, 0.105 if "upper" in bone else 0.082, material)
        _parent_to_bone(limb, rig, bone)
    for side, x in (("L", -0.64), ("R", 0.64)):
        palm = _sphere(bpy, f"June_Hand_{side}", (x, -0.445, 1.43), (0.092, 0.056, 0.115), skin)
        _parent_to_bone(palm, rig, f"hand.{side}")
        sign = -1 if side == "L" else 1
        for digit, offset in enumerate((-0.060, -0.030, 0.0, 0.030)):
            finger = _cylinder_between(
                bpy,
                mathutils,
                f"June_Finger_{side}_{digit}",
                (x + offset, -0.458, 1.40),
                (x + offset * 1.08, -0.474, 1.305 + abs(offset) * 0.35),
                0.014,
                skin,
            )
            _parent_to_bone(finger, rig, f"hand.{side}")
        thumb = _cylinder_between(bpy, mathutils, f"June_Thumb_{side}", (x + sign * 0.075, -0.45, 1.45), (x + sign * 0.125, -0.49, 1.39), 0.020, skin)
        _parent_to_bone(thumb, rig, f"hand.{side}")

    leg_specs = (
        ("thigh.L", (-0.19, 0, 1.16), (-0.22, -0.55, 1.00)),
        ("shin.L", (-0.22, -0.55, 1.00), (-0.22, -0.60, 0.34)),
        ("thigh.R", (0.19, 0, 1.16), (0.22, -0.55, 1.00)),
        ("shin.R", (0.22, -0.55, 1.00), (0.22, -0.60, 0.34)),
    )
    for bone, start, end in leg_specs:
        leg = _cylinder_between(bpy, mathutils, f"June_{bone}", start, end, 0.115 if "thigh" in bone else 0.10, materials["overalls"])
        _parent_to_bone(leg, rig, bone)
    for side, x in (("L", -0.22), ("R", 0.22)):
        boot = _box(bpy, f"June_Boot_{side}", (x, -0.76, 0.25), (0.13, 0.24, 0.10), materials["leather"], bevel=0.07)
        _parent_to_bone(boot, rig, f"foot.{side}")

    mouth = _make_mouth_v1(bpy, rig, materials["mouth"])
    rig["ce_character_id"] = "june_oxley"
    rig["ce_body_type"] = "lean_wiry"
    rig["ce_hand_digits"] = 5
    rig["ce_asset_major"] = 1
    return rig, mouth, {"eyes": eyes, "upper_lids": [], "lower_lids": [], "brows": []}


def _make_mouth_v2(bpy, rig, materials: dict):
    """Build a compact lip-rim mouth with deformation-safe radial topology."""
    segment_count = 32
    outer_radius = (0.155, 0.062)
    inner_radius = (0.122, 0.038)
    vertices = []
    for index in range(segment_count):
        angle = 2.0 * math.pi * index / segment_count
        vertices.append((outer_radius[0] * math.cos(angle), -0.007, outer_radius[1] * math.sin(angle)))
    for index in range(segment_count):
        angle = 2.0 * math.pi * index / segment_count
        vertices.append((inner_radius[0] * math.cos(angle), -0.003, inner_radius[1] * math.sin(angle)))
    vertices.append((0.0, 0.0, 0.0))
    center = len(vertices) - 1
    faces = []
    for index in range(segment_count):
        next_index = (index + 1) % segment_count
        faces.append((index, next_index, segment_count + next_index, segment_count + index))
        faces.append((segment_count + index, segment_count + next_index, center))
    mesh = bpy.data.meshes.new("June_Mouth_Viseme_Data")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(materials["mouth_interior"])
    mesh.materials.append(materials["lip"])
    for index, polygon in enumerate(mesh.polygons):
        polygon.material_index = 1 if index % 2 == 0 else 0
        polygon.use_smooth = True
    mouth = bpy.data.objects.new("June_Mouth_Viseme", mesh)
    bpy.context.collection.objects.link(mouth)
    mouth.location = (0, -0.338, 2.485)
    basis = mouth.shape_key_add(name="Basis")
    shape_scale = {
        "A": (1.00, 0.95),
        "B": (0.72, 1.45),
        "C": (1.18, 0.62),
        "D": (0.84, 1.18),
        "E": (1.15, 0.42),
        "F": (0.67, 0.78),
        "G": (0.58, 1.32),
        "H": (0.48, 1.02),
        "X": (0.94, 0.28),
    }
    for name, (width, height) in shape_scale.items():
        key = mouth.shape_key_add(name=name)
        for source, target in zip(basis.data, key.data):
            target.co.x = source.co.x * width
            target.co.z = source.co.z * height
    bevel = mouth.modifiers.new("CE_Lip_Soften", "BEVEL")
    bevel.width = 0.004
    bevel.segments = 3
    _parent_to_bone(mouth, rig, "head")
    teeth = _box(bpy, "June_Upper_Teeth", (0, -0.344, 2.505), (0.070, 0.004, 0.012), materials["teeth"], bevel=0.008)
    _parent_to_bone(teeth, rig, "head")
    return mouth


def _make_june_v2(bpy, mathutils, materials: dict):
    """Artist-directed Hero v2: smoother topology, authored planes, and facial controls."""
    rig = _make_armature(bpy)
    skin = materials["skin"]
    skin_shadow = materials["skin_shadow"]
    hair = materials["hair"]
    denim = materials["denim"]
    dark_denim = materials["dark_denim"]

    # A tapered torso and separated garment panels keep June wiry and remove the
    # spherical toy silhouette from the integration puppet.
    torso = _sphere(bpy, "June_Plaid_Torso", (0, 0.025, 1.78), (0.345, 0.215, 0.61), materials["plaid"], segments=48, rings=24)
    _parent_to_bone(torso, rig, "torso")
    waist = _sphere(bpy, "June_Overall_Waist", (0, 0.01, 1.35), (0.315, 0.215, 0.22), materials["overalls"], segments=40, rings=20)
    _parent_to_bone(waist, rig, "pelvis")
    bib = _box(bpy, "June_Overall_Bib", (0, -0.222, 1.70), (0.215, 0.018, 0.31), materials["overalls"], bevel=0.035)
    _parent_to_bone(bib, rig, "torso")
    pocket = _box(bpy, "June_Overall_Pocket", (0.015, -0.245, 1.62), (0.115, 0.010, 0.095), dark_denim, bevel=0.024)
    _parent_to_bone(pocket, rig, "torso")
    for side, x in (("L", -0.19), ("R", 0.19)):
        strap = _curve(
            bpy,
            f"June_Overall_Strap_{side}",
            ((x * 1.18, -0.232, 2.08), (x, -0.245, 1.92), (x * 0.96, -0.246, 1.80)),
            dark_denim,
            bevel_depth=0.025,
        )
        _parent_to_bone(strap, rig, "torso")
        button = _sphere(bpy, f"June_Overall_Button_{side}", (x, -0.267, 1.83), (0.026, 0.012, 0.026), materials["brass"], segments=24, rings=12)
        _parent_to_bone(button, rig, "torso")
    for side, x, width in (("L", -0.31, 0.125), ("R", 0.315, 0.118)):
        jacket = _sphere(bpy, f"June_Denim_Jacket_{side}", (x, 0.03, 1.82), (width, 0.225, 0.54), denim, segments=40, rings=20)
        jacket.rotation_euler[1] = math.radians(-2 if side == "L" else 3)
        _parent_to_bone(jacket, rig, "torso")
        lapel = _curve(
            bpy,
            f"June_Jacket_Lapel_{side}",
            ((x * 0.82, -0.219, 2.14), (x * 0.58, -0.252, 1.98), (x * 0.72, -0.255, 1.82)),
            dark_denim,
            bevel_depth=0.015,
        )
        _parent_to_bone(lapel, rig, "torso")
    shirt_placket = _curve(bpy, "June_Shirt_Placket", ((0, -0.235, 2.08), (0.008, -0.248, 1.88)), dark_denim, bevel_depth=0.009)
    _parent_to_bone(shirt_placket, rig, "torso")
    for index, z in enumerate((1.90, 1.99, 2.08)):
        button = _sphere(bpy, f"June_Shirt_Button_{index}", (0.008, -0.254, z), (0.012, 0.007, 0.012), materials["brass"], segments=16, rings=8)
        _parent_to_bone(button, rig, "torso")

    neck = _cylinder(bpy, "June_Neck", (0, 0, 2.28), 0.125, 0.25, skin, vertices=32)
    _parent_to_bone(neck, rig, "neck")
    for side, x in (("L", -0.115), ("R", 0.115)):
        collar = _curve(
            bpy,
            f"June_Shirt_Collar_{side}",
            ((x * 0.45, -0.215, 2.21), (x, -0.242, 2.15), (x * 1.28, -0.235, 2.08)),
            materials["plaid"],
            bevel_depth=0.022,
        )
        _parent_to_bone(collar, rig, "torso")

    head = _sphere(bpy, "June_Head", (0, 0, 2.64), (0.285, 0.245, 0.39), skin, segments=64, rings=32)
    head_basis = head.shape_key_add(name="Basis")
    expression_controls = ("smile", "thoughtful", "soft_chuckle", "brow_raise", "brow_knit", "squint", "cheek_raise")
    for control in expression_controls:
        key = head.shape_key_add(name=control)
        for source, target in zip(head_basis.data, key.data):
            front = max(0.0, min(1.0, -source.co.y / 0.24))
            lower = max(0.0, min(1.0, (0.08 - source.co.z) / 0.34))
            upper = max(0.0, min(1.0, (source.co.z + 0.02) / 0.34))
            center = max(0.0, 1.0 - abs(source.co.x) / 0.20)
            if control == "smile":
                target.co.x *= 1.0 + 0.040 * front * lower
                target.co.z += 0.014 * front * lower * min(1.0, abs(source.co.x) / 0.18)
            elif control == "thoughtful":
                target.co.x += 0.007 * front * lower
                target.co.z -= 0.007 * front * lower
            elif control == "soft_chuckle":
                target.co.x *= 1.0 + 0.028 * front
                target.co.z += 0.012 * front * lower
            elif control == "brow_raise":
                target.co.z += 0.009 * front * upper
            elif control == "brow_knit":
                target.co.x *= 1.0 - 0.018 * front * upper * center
            elif control == "squint":
                target.co.z -= 0.007 * front * upper
            elif control == "cheek_raise":
                target.co.z += 0.010 * front * lower * (1.0 - center * 0.4)
    head["ce_expression_controls"] = ",".join(expression_controls)
    _parent_to_bone(head, rig, "head")

    # Cheek and jaw planes introduce recognizable asymmetry while preserving a
    # clean close-up silhouette from both profiles.
    for side, x, scale_x, z in (("L", -0.185, 0.102, 2.59), ("R", 0.178, 0.094, 2.575)):
        cheek = _sphere(bpy, f"June_Cheek_{side}", (x, -0.178, z), (scale_x, 0.092, 0.105), skin, segments=36, rings=18)
        _parent_to_bone(cheek, rig, "head")
    chin = _sphere(bpy, "June_Chin", (0.012, -0.205, 2.405), (0.142, 0.085, 0.095), skin_shadow, segments=40, rings=20)
    _parent_to_bone(chin, rig, "head")
    for side, x, size in (("L", -0.287, 0.055), ("R", 0.283, 0.052)):
        ear = _sphere(bpy, f"June_Ear_{side}", (x, 0.008, 2.64), (size, 0.035, 0.092), skin_shadow, segments=32, rings=16)
        _parent_to_bone(ear, rig, "head")
    nose = _sphere(bpy, "June_Nose", (0.010, -0.273, 2.61), (0.052, 0.076, 0.105), skin_shadow, segments=40, rings=20)
    nose.rotation_euler[2] = math.radians(-4)
    _parent_to_bone(nose, rig, "head")

    # Thinning white hair hugs the skull rather than reading as four spheres.
    hair_specs = (
        ("Crown_L", (-0.145, 0.045, 2.965), (0.105, 0.155, 0.055)),
        ("Crown_R", (0.135, 0.050, 2.962), (0.095, 0.150, 0.050)),
        ("Temple_L", (-0.255, 0.020, 2.82), (0.075, 0.115, 0.105)),
        ("Temple_R", (0.250, 0.025, 2.80), (0.070, 0.110, 0.100)),
        ("Side_L", (-0.275, 0.025, 2.68), (0.055, 0.090, 0.080)),
        ("Side_R", (0.272, 0.030, 2.67), (0.052, 0.087, 0.076)),
    )
    for name, location, scale in hair_specs:
        tuft = _sphere(bpy, f"June_White_Hair_{name}", location, scale, hair, segments=36, rings=18)
        _parent_to_bone(tuft, rig, "head")
    beard = _sphere(bpy, "June_Close_Beard", (0.004, -0.165, 2.445), (0.205, 0.105, 0.155), hair, segments=48, rings=24)
    _parent_to_bone(beard, rig, "head")
    for side, points in (
        ("L", ((-0.125, -0.293, 2.535), (-0.065, -0.324, 2.548), (-0.005, -0.326, 2.535))),
        ("R", ((0.005, -0.326, 2.535), (0.068, -0.324, 2.545), (0.128, -0.290, 2.525))),
    ):
        moustache = _curve(bpy, f"June_Moustache_{side}", points, hair, bevel_depth=0.022)
        _parent_to_bone(moustache, rig, "head")

    face_controls = {"eyes": [], "upper_lids": [], "lower_lids": [], "brows": []}
    for side, x, asymmetry in (("L", -0.105, 0.0), ("R", 0.108, -0.006)):
        eye = _sphere(bpy, f"June_Eye_{side}", (x, -0.242, 2.715 + asymmetry), (0.052, 0.023, 0.035), materials["eye"], segments=40, rings=20)
        iris = _sphere(bpy, f"June_Iris_{side}", (x, -0.265, 2.715 + asymmetry), (0.024, 0.006, 0.024), materials["iris"], segments=32, rings=16)
        pupil = _sphere(bpy, f"June_Pupil_{side}", (x, -0.271, 2.715 + asymmetry), (0.010, 0.004, 0.012), materials["pupil_v2"], segments=24, rings=12)
        catchlight = _sphere(bpy, f"June_Catchlight_{side}", (x - 0.006, -0.276, 2.724 + asymmetry), (0.004, 0.002, 0.005), materials["catchlight"], segments=16, rings=8)
        upper = _curve(
            bpy,
            f"June_Eyelid_Upper_{side}",
            ((x - 0.055, -0.274, 2.714 + asymmetry), (x, -0.279, 2.752 + asymmetry), (x + 0.055, -0.274, 2.714 + asymmetry)),
            skin_shadow,
            bevel_depth=0.006,
        )
        lower = _curve(
            bpy,
            f"June_Eyelid_Lower_{side}",
            ((x - 0.050, -0.273, 2.707 + asymmetry), (x, -0.277, 2.687 + asymmetry), (x + 0.050, -0.273, 2.707 + asymmetry)),
            skin_shadow,
            bevel_depth=0.0045,
        )
        brow = _curve(
            bpy,
            f"June_Brow_{side}",
            ((x - 0.066, -0.264, 2.805), (x, -0.275, 2.824 + (0.006 if side == "L" else 0.0)), (x + 0.068, -0.262, 2.810)),
            hair,
            bevel_depth=0.009,
        )
        brow["ce_face_control"] = f"brow.{side}"
        upper["ce_face_control"] = f"blink.{side}.upper"
        lower["ce_face_control"] = f"blink.{side}.lower"
        for obj in (eye, iris, pupil, catchlight, upper, lower, brow):
            _parent_to_bone(obj, rig, "head")
        face_controls["eyes"].extend((eye, iris, pupil, catchlight))
        face_controls["upper_lids"].append(upper)
        face_controls["lower_lids"].append(lower)
        face_controls["brows"].append(brow)

    for index, (z, width) in enumerate(((2.855, 0.085), (2.882, 0.072), (2.906, 0.054))):
        wrinkle = _curve(
            bpy,
            f"June_Forehead_Line_{index}",
            ((-width, -0.249, z), (0.004, -0.263, z + 0.003), (width, -0.248, z - 0.002)),
            skin_shadow,
            bevel_depth=0.0035,
        )
        _parent_to_bone(wrinkle, rig, "head")
    for side, x in (("L", -0.165), ("R", 0.168)):
        smile_line = _curve(
            bpy,
            f"June_Smile_Line_{side}",
            ((x, -0.267, 2.57), (x * 1.08, -0.273, 2.515), (x * 0.92, -0.258, 2.47)),
            skin_shadow,
            bevel_depth=0.004,
        )
        _parent_to_bone(smile_line, rig, "head")

    # Tapered, softened limbs replace tubes and maintain readable seated joints.
    limb_specs = (
        ("upper_arm.L", (-0.31, 0, 2.10), (-0.54, -0.045, 1.82), 0.090, 0.073, denim),
        ("forearm.L", (-0.54, -0.045, 1.82), (-0.56, -0.36, 1.49), 0.066, 0.054, skin),
        ("upper_arm.R", (0.31, 0, 2.10), (0.54, -0.045, 1.82), 0.086, 0.070, denim),
        ("forearm.R", (0.54, -0.045, 1.82), (0.56, -0.36, 1.49), 0.064, 0.052, skin),
    )
    for bone, start, end, radius_start, radius_end, material in limb_specs:
        limb = _tapered_between(bpy, mathutils, f"June_{bone}", start, end, radius_start, radius_end, material)
        _parent_to_bone(limb, rig, bone)
    for side, x in (("L", -0.56), ("R", 0.56)):
        cuff = _cylinder_between(bpy, mathutils, f"June_Jacket_Cuff_{side}", (x, -0.30, 1.57), (x, -0.36, 1.49), 0.066, dark_denim)
        _parent_to_bone(cuff, rig, f"forearm.{side}")
        palm = _sphere(bpy, f"June_Hand_{side}", (x, -0.405, 1.40), (0.070, 0.046, 0.092), skin, segments=36, rings=18)
        _parent_to_bone(palm, rig, f"hand.{side}")
        finger_lengths = (0.092, 0.105, 0.101, 0.084)
        for digit, (offset, length) in enumerate(zip((-0.043, -0.015, 0.015, 0.043), finger_lengths)):
            start = (x + offset, -0.420, 1.37)
            middle = (x + offset * 1.02, -0.438, 1.37 - length * 0.55)
            end = (x + offset * 0.98, -0.450, 1.37 - length)
            first = _tapered_between(bpy, mathutils, f"June_Finger_{side}_{digit}_A", start, middle, 0.012, 0.010, skin, vertices=16)
            second = _tapered_between(bpy, mathutils, f"June_Finger_{side}_{digit}_B", middle, end, 0.010, 0.007, skin, vertices=16)
            _parent_to_bone(first, rig, f"hand.{side}")
            _parent_to_bone(second, rig, f"hand.{side}")
        sign = -1 if side == "L" else 1
        thumb_a = _tapered_between(bpy, mathutils, f"June_Thumb_{side}_A", (x + sign * 0.055, -0.414, 1.425), (x + sign * 0.092, -0.438, 1.39), 0.015, 0.012, skin, vertices=16)
        thumb_b = _tapered_between(bpy, mathutils, f"June_Thumb_{side}_B", (x + sign * 0.092, -0.438, 1.39), (x + sign * 0.112, -0.450, 1.36), 0.012, 0.008, skin, vertices=16)
        _parent_to_bone(thumb_a, rig, f"hand.{side}")
        _parent_to_bone(thumb_b, rig, f"hand.{side}")

    leg_specs = (
        ("thigh.L", (-0.17, 0, 1.16), (-0.20, -0.52, 0.98), 0.105, 0.088),
        ("shin.L", (-0.20, -0.52, 0.98), (-0.20, -0.58, 0.34), 0.086, 0.071),
        ("thigh.R", (0.17, 0, 1.16), (0.20, -0.52, 0.98), 0.102, 0.086),
        ("shin.R", (0.20, -0.52, 0.98), (0.20, -0.58, 0.34), 0.084, 0.069),
    )
    for bone, start, end, radius_start, radius_end in leg_specs:
        leg = _tapered_between(bpy, mathutils, f"June_{bone}", start, end, radius_start, radius_end, materials["overalls"])
        _parent_to_bone(leg, rig, bone)
    for side, x in (("L", -0.20), ("R", 0.20)):
        boot = _sphere(bpy, f"June_Boot_{side}", (x, -0.73, 0.245), (0.115, 0.205, 0.085), materials["leather"], segments=40, rings=20)
        _parent_to_bone(boot, rig, f"foot.{side}")
        sole = _box(bpy, f"June_Boot_Sole_{side}", (x, -0.75, 0.205), (0.118, 0.215, 0.022), materials["sole"], bevel=0.025)
        _parent_to_bone(sole, rig, f"foot.{side}")

    mouth = _make_mouth_v2(bpy, rig, materials)
    rig["ce_character_id"] = "june_oxley"
    rig["ce_body_type"] = "lean_wiry"
    rig["ce_hand_digits"] = 5
    rig["ce_asset_major"] = 2
    rig["ce_surface_standard"] = "smooth_subdivided_artist_directed"
    rig["ce_face_topology"] = "radial_lip_rim_independent_lids"
    return rig, mouth, face_controls


def _make_june(bpy, mathutils, materials: dict, *, asset_major: int = 2):
    if asset_major == 1:
        return _make_june_v1(bpy, mathutils, materials)
    if asset_major == 2:
        return _make_june_v2(bpy, mathutils, materials)
    raise ValueError(f"unsupported June asset major version: {asset_major}")


def _stash_action(bpy, rig, name: str, animator) -> None:
    rig.animation_data_create()
    action = bpy.data.actions.new(name)
    rig.animation_data.action = action
    animator()
    rig.animation_data.action = None
    track = rig.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, 1, action)
    strip.blend_type = "ADD"
    strip.extrapolation = "NOTHING"


def _animate_rig(bpy, rig, plan: dict) -> None:
    frame_end = int(plan["frame_end"])
    rig.animation_data_create()
    # Runtime performances replace the library preview strips while the source
    # actions remain stored in the .blend for reuse and inspection.
    for track in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(track)
    rig.animation_data.action = None
    torso = rig.pose.bones["torso"]
    head = rig.pose.bones["head"]
    upper_l = rig.pose.bones["upper_arm.L"]
    fore_l = rig.pose.bones["forearm.L"]
    upper_r = rig.pose.bones["upper_arm.R"]
    fore_r = rig.pose.bones["forearm.R"]

    def breathing():
        for frame in range(1, frame_end + 1, 30):
            torso.location.z = 0.012 if ((frame // 30) % 2) else -0.006
            torso.rotation_euler[1] = math.radians(0.7 if ((frame // 30) % 2) else -0.4)
            torso.keyframe_insert(data_path="location", frame=frame)
            torso.keyframe_insert(data_path="rotation_euler", frame=frame)
        torso.location.z = 0
        torso.rotation_euler[1] = 0
        torso.keyframe_insert(data_path="location", frame=frame_end)
        torso.keyframe_insert(data_path="rotation_euler", frame=frame_end)

    def head_performance():
        poses = [(1, 0, 0)]
        for index, shot in enumerate(plan["shots"]):
            start = int(shot["frame_start"])
            end = int(shot["frame_end"])
            midpoint = (start + end) // 2
            poses.extend(
                [
                    (start, (-2, 1, 1)[index], (0, 1, -1)[index]),
                    (midpoint, (2, -3, 2)[index], (1, -1, 2)[index]),
                    (end, (0, 1, -2)[index], (0, 0, 1)[index]),
                ]
            )
        for frame, turn, nod in poses:
            head.rotation_euler[2] = math.radians(turn)
            head.rotation_euler[0] = math.radians(nod)
            head.keyframe_insert(data_path="rotation_euler", frame=frame)

    def gestures():
        for bone in (upper_l, fore_l, upper_r, fore_r):
            bone.rotation_euler = (0, 0, 0)
            bone.keyframe_insert(data_path="rotation_euler", frame=1)
        shot_a, shot_b, shot_c = plan["shots"][:3]
        beats = (
            (int(shot_a["frame_start"]), (0, 0, 0, 0)),
            ((int(shot_a["frame_start"]) + int(shot_a["frame_end"])) // 2, (-18, 12, 8, -5)),
            (int(shot_a["frame_end"]), (-5, 4, 2, 0)),
            ((int(shot_b["frame_start"]) + int(shot_b["frame_end"])) // 2, (-4, 3, 19, -17)),
            (int(shot_b["frame_end"]), (0, 0, 5, -3)),
            ((int(shot_c["frame_start"]) + int(shot_c["frame_end"])) // 2, (-9, 7, 10, -6)),
            (int(shot_c["frame_end"]), (0, 0, 0, 0)),
        )
        for frame, values in beats:
            for bone, degrees in zip((upper_l, fore_l, upper_r, fore_r), values):
                bone.rotation_euler[1] = math.radians(degrees)
                bone.rotation_euler[2] = math.radians(degrees * 0.35)
                bone.keyframe_insert(data_path="rotation_euler", frame=frame)

    _stash_action(bpy, rig, "June_Breathing_Idle", breathing)
    _stash_action(bpy, rig, "June_Head_Performance", head_performance)
    _stash_action(bpy, rig, "June_Gesture_Performance", gestures)


def _animate_mouth(mouth, plan: dict) -> None:
    if mouth.data.shape_keys.animation_data:
        mouth.data.shape_keys.animation_data_clear()
    keys = mouth.data.shape_keys.key_blocks
    shapes = tuple("ABCDEFGHX")
    cues = plan.get("mouth_cues") or [{"frame_start": 1, "frame_end": plan["frame_end"], "shape": "X"}]
    for cue in cues:
        frame = int(cue["frame_start"])
        active = str(cue["shape"])
        for shape in shapes:
            keys[shape].value = 1.0 if shape == active else 0.0
            keys[shape].keyframe_insert(data_path="value", frame=frame)
    final_frame = int(plan["frame_end"])
    for shape in shapes:
        keys[shape].value = 1.0 if shape == "X" else 0.0
        keys[shape].keyframe_insert(data_path="value", frame=final_frame)
    action = mouth.data.shape_keys.animation_data.action
    for curve in action.fcurves:
        for point in curve.keyframe_points:
            point.interpolation = "CONSTANT"


def _animate_expressions(head, plan: dict, face_controls: dict | None = None) -> None:
    """Layer readable acting beats independently from phoneme mouth shapes."""
    keys = head.data.shape_keys.key_blocks
    controls = tuple(
        name
        for name in ("smile", "thoughtful", "soft_chuckle", "brow_raise", "brow_knit", "squint", "cheek_raise")
        if keys.get(name) is not None
    )
    shots = plan["shots"][:3]
    assignments = ("smile", "thoughtful", "soft_chuckle")
    for shot, active in zip(shots, assignments):
        start = int(shot["frame_start"])
        middle = (start + int(shot["frame_end"])) // 2
        end = int(shot["frame_end"])
        for frame, strength in ((start, 0.0), (middle, 0.75), (end, 0.20)):
            for control in controls:
                keys[control].value = strength if control == active else 0.0
                keys[control].keyframe_insert(data_path="value", frame=frame)
    if not face_controls:
        return
    brows = face_controls.get("brows") or []
    for index, brow in enumerate(brows):
        base = brow.location.copy()
        base_rotation = brow.rotation_euler.copy()
        for shot_index, shot in enumerate(shots):
            start = int(shot["frame_start"])
            middle = (start + int(shot["frame_end"])) // 2
            end = int(shot["frame_end"])
            lift = (0.006, -0.003, 0.010)[shot_index]
            tilt = (2.0, -3.0, 1.5)[shot_index] * (-1 if index == 0 else 1)
            for frame, blend in ((start, 0.0), (middle, 1.0), (end, 0.2)):
                brow.location = base.copy()
                brow.location.z += lift * blend
                brow.rotation_euler = base_rotation.copy()
                brow.rotation_euler[1] += math.radians(tilt * blend)
                brow.keyframe_insert(data_path="location", frame=frame)
                brow.keyframe_insert(data_path="rotation_euler", frame=frame)


def _animate_blinks(face_controls: dict, frame_end: int) -> None:
    upper_lids = face_controls.get("upper_lids") or []
    lower_lids = face_controls.get("lower_lids") or []
    if upper_lids:
        for eye_index, upper in enumerate(upper_lids):
            lower = lower_lids[eye_index]
            upper_base = upper.location.copy()
            lower_base = lower.location.copy()
            for center in range(52 + eye_index * 3, frame_end, 83):
                for frame, blend in ((center - 2, 0.0), (center, 1.0), (center + 2, 0.0)):
                    upper.location = upper_base.copy()
                    lower.location = lower_base.copy()
                    upper.location.z -= 0.038 * blend
                    lower.location.z += 0.012 * blend
                    upper.keyframe_insert(data_path="location", frame=max(1, min(frame_end, frame)))
                    lower.keyframe_insert(data_path="location", frame=max(1, min(frame_end, frame)))
        return
    for eye_index, eye in enumerate(face_controls.get("eyes") or []):
        if eye.animation_data:
            eye.animation_data_clear()
        base = eye.scale.copy()
        for center in range(52 + eye_index % 2, frame_end, 83):
            for frame, factor in ((center - 2, 1.0), (center, 0.12), (center + 2, 1.0)):
                eye.scale = base.copy()
                eye.scale.z *= factor
                eye.keyframe_insert(data_path="scale", frame=max(1, min(frame_end, frame)))


def _make_cameras(bpy, mathutils, plan: dict) -> None:
    portrait = plan["render"]["profile"] == "portrait"
    presets = {
        "wide": ((0.0, -10.6 if portrait else -8.8, 3.15), 54 if portrait else 50, (0, 0.25, 1.88)),
        "medium": ((0.18, -7.2 if portrait else -5.9, 2.72), 62 if portrait else 58, (0, 0.05, 2.05)),
        "close": ((0.08, -5.1 if portrait else -3.9, 2.69), 72 if portrait else 68, (0, -0.02, 2.48)),
    }
    scene = bpy.context.scene
    for index, shot in enumerate(plan["shots"]):
        preset = presets[shot["camera"]]
        data = bpy.data.cameras.new(f"Camera_{shot['id']}")
        data.lens = preset[1]
        data.dof.use_dof = False
        camera = bpy.data.objects.new(f"Camera_{shot['id']}", data)
        bpy.context.collection.objects.link(camera)
        camera.location = preset[0]
        _look_at(camera, preset[2], mathutils)
        start = int(shot["frame_start"])
        end = int(shot["frame_end"])
        camera.keyframe_insert(data_path="location", frame=start)
        camera.keyframe_insert(data_path="rotation_euler", frame=start)
        camera.location.y += 0.16 if shot["camera"] != "wide" else 0.22
        camera.location.x += (-0.035, 0.045, -0.02)[index % 3]
        _look_at(camera, preset[2], mathutils)
        camera.keyframe_insert(data_path="location", frame=end)
        camera.keyframe_insert(data_path="rotation_euler", frame=end)
        marker = scene.timeline_markers.new(f"SHOT_{index + 1}_{shot['id']}", frame=start)
        marker.camera = camera
        if index == 0:
            scene.camera = camera


def _add_area_light(bpy, mathutils, name: str, location, energy: float, color, size: float, target):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    _look_at(obj, target, mathutils)


def _lighting(bpy, mathutils) -> None:
    _add_area_light(bpy, mathutils, "Warm_Window_Key", (-3.8, -3.0, 6.0), 950, (1.0, 0.67, 0.40), 4.5, (0, 0, 2))
    _add_area_light(bpy, mathutils, "Sky_Fill", (4.5, -2.0, 4.0), 450, (0.50, 0.67, 1.0), 5.0, (0, 0, 1.8))
    _add_area_light(bpy, mathutils, "Porch_Lantern_Light", (1.05, 1.95, 3.45), 520, (1.0, 0.38, 0.12), 2.0, (0, 0, 2.1))
    world = bpy.context.scene.world or bpy.data.worlds.new("June_Porch_World")
    bpy.context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.055, 0.075, 0.12, 1.0)
    background.inputs["Strength"].default_value = 0.42


def _configure_render(bpy, plan: dict, output_dir: Path) -> None:
    scene = bpy.context.scene
    render = plan["render"]
    scene.frame_start = int(plan["frame_start"])
    scene.frame_end = int(plan["frame_end"])
    scene.render.resolution_x = int(render["width"])
    scene.render.resolution_y = int(render["height"])
    scene.render.resolution_percentage = 100
    scene.render.fps = int(render["fps"])
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.filepath = str(output_dir / "frame_")

    desired = str(render.get("engine", "BLENDER_WORKBENCH"))
    selected = None
    for engine in (desired, "BLENDER_WORKBENCH", "CYCLES"):
        try:
            scene.render.engine = engine
            selected = engine
            break
        except Exception:
            pass
    if selected == "BLENDER_WORKBENCH":
        shading = scene.display.shading
        shading.light = "STUDIO"
        shading.color_type = "MATERIAL"
        shading.show_shadows = True
        shading.show_cavity = True
        shading.cavity_type = "BOTH"
        shading.show_object_outline = True
        # Blender 4.2 exposes the outline toggle but not ``outline_color`` on
        # View3DShading. Newer builds may add it, so keep the richer setting
        # feature-detected while retaining 4.2 worker compatibility.
        if hasattr(shading, "outline_color"):
            shading.outline_color = (0.025, 0.018, 0.018)
        shading.show_specular_highlight = True
    elif selected == "CYCLES":
        scene.cycles.device = "CPU"
        scene.cycles.samples = int(render.get("samples", 64))
        scene.cycles.use_denoising = True
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass


def main() -> None:
    args = _args()
    import bpy
    import mathutils

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.asset_library:
        library = Path(args.asset_library).resolve()
        if not library.is_file():
            raise FileNotFoundError(f"asset library not found: {library}")
        bpy.ops.wm.open_mainfile(filepath=str(library))
        rig = bpy.data.objects["June_Oxley_Rig"]
        mouth = bpy.data.objects["June_Mouth_Viseme"]
    else:
        _clear(bpy)
        materials = _make_materials(bpy)
        _make_porch(bpy, mathutils, materials, int(plan["frame_end"]))
        rig, mouth, face_controls = _make_june(bpy, mathutils, materials, asset_major=2)
    if args.asset_library:
        face_controls = {
            "eyes": [
                obj for name in (
                    "June_Eye_L", "June_Iris_L", "June_Pupil_L", "June_Catchlight_L",
                    "June_Eye_R", "June_Iris_R", "June_Pupil_R", "June_Catchlight_R",
                ) if (obj := bpy.data.objects.get(name)) is not None
            ],
            "upper_lids": [obj for side in ("L", "R") if (obj := bpy.data.objects.get(f"June_Eyelid_Upper_{side}")) is not None],
            "lower_lids": [obj for side in ("L", "R") if (obj := bpy.data.objects.get(f"June_Eyelid_Lower_{side}")) is not None],
            "brows": [obj for side in ("L", "R") if (obj := bpy.data.objects.get(f"June_Brow_{side}")) is not None],
        }
    head = bpy.data.objects["June_Head"]
    _animate_rig(bpy, rig, plan)
    _animate_mouth(mouth, plan)
    _animate_expressions(head, plan, face_controls)
    _animate_blinks(face_controls, int(plan["frame_end"]))
    _make_cameras(bpy, mathutils, plan)
    _lighting(bpy, mathutils)
    _configure_render(bpy, plan, output_dir)
    if args.frames:
        selected = sorted({int(frame) for frame in args.frames.split(",") if frame.strip()})
        if not selected or any(frame < int(plan["frame_start"]) or frame > int(plan["frame_end"]) for frame in selected):
            raise ValueError("--frames must contain in-range frame numbers")
        for frame in selected:
            bpy.context.scene.frame_set(frame)
            bpy.context.scene.render.filepath = str(output_dir / f"frame_{frame:04d}.png")
            bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
