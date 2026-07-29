"""Build and render the reusable June Oxley porch-dialogue scene in Blender.

The asset is intentionally code-native for now: CI can prove the entire shot,
rig, viseme, lighting, and frame-sequence path without committing binary media or
a fragile .blend file.  A later authored June asset can replace ``_make_june``
without changing the compiled plan contract.
"""
from __future__ import annotations

import argparse
import hashlib
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
    plaid_base = (0.15, 0.25, 0.32, 1) if asset_major >= 4 else (0.46, 0.16, 0.10, 1)
    plaid_cross = (0.055, 0.095, 0.14, 1) if asset_major >= 4 else (0.08, 0.13, 0.17, 1)
    materials = {
        "cedar": _material(bpy, "Warm Cedar", (0.38, 0.17, 0.075, 1), texture_scale=5.0, bump_strength=0.20),
        "dark_wood": _material(bpy, "Deep Wood", (0.16, 0.065, 0.032, 1), texture_scale=7.0, bump_strength=0.16),
        "cream": _material(bpy, "Porch Cream", (0.72, 0.66, 0.51, 1)),
        "enamel": _material(bpy, "Cream Enamel", (0.82, 0.78, 0.66, 1), roughness=0.24),
        "coffee": _material(bpy, "Black Coffee", (0.055, 0.020, 0.010, 1), roughness=0.18),
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
        "plaid": _material(bpy, "June Shirt Plaid", plaid_base, texture_scale=35.0, bump_strength=0.09),
        "leather": _material(bpy, "Worn Boot Leather", (0.20, 0.09, 0.035, 1), texture_scale=9.0, bump_strength=0.22),
        "ledger_leather": _material(bpy, "Ledger Leather", (0.15, 0.045, 0.022, 1), texture_scale=14.0, bump_strength=0.16),
        "pencil_cedar": _material(bpy, "Pencil Cedar", (0.64, 0.29, 0.055, 1), roughness=0.50),
        "eye": _material(bpy, "Eye White", (0.90, 0.87, 0.77, 1), roughness=0.25),
        "iris": _material(bpy, "June Blue Gray Iris", (0.12, 0.30, 0.34, 1), roughness=0.16),
        "pupil": _material(bpy, "June Blue Gray Eyes", (0.06, 0.16, 0.19, 1), roughness=0.18),
        "pupil_v2": _material(bpy, "June Pupil", (0.012, 0.018, 0.020, 1), roughness=0.12),
        "catchlight": _material(bpy, "June Eye Catchlight", (1.0, 0.96, 0.82, 1), emission=0.25, roughness=0.12),
        "mouth": _material(bpy, "June Mouth", (0.20, 0.025, 0.025, 1), roughness=0.45),
        "mouth_interior": _material(bpy, "June Mouth Interior", (0.105, 0.012, 0.014, 1), roughness=0.55),
        "lip": _material(bpy, "June Weathered Lip", (0.38, 0.095, 0.075, 1), roughness=0.62),
        "lip_soft": _material(bpy, "June Soft Weathered Lip", (0.58, 0.22, 0.16, 1), roughness=0.72),
        "gum": _material(bpy, "June Healthy Gum", (0.34, 0.055, 0.050, 1), roughness=0.58),
        "tongue": _material(bpy, "June Tongue", (0.48, 0.085, 0.075, 1), roughness=0.54),
        "teeth": _material(bpy, "June Teeth", (0.78, 0.72, 0.58, 1), roughness=0.48),
        "sole": _material(bpy, "June Boot Sole", (0.055, 0.030, 0.022, 1), texture_scale=10.0, bump_strength=0.12),
    }
    if asset_major >= 2:
        _plaid_shader(materials["plaid"], plaid_base, plaid_cross)
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


def _loft_mesh(bpy, name: str, rings, material, *, segments: int = 48):
    """Build one closed, tapered surface from elliptical profile rings."""
    vertices = []
    for z, radius_x, radius_y, center_y in rings:
        for index in range(segments):
            angle = math.tau * index / segments
            vertices.append((radius_x * math.cos(angle), center_y + radius_y * math.sin(angle), z))
    faces = []
    for ring_index in range(len(rings) - 1):
        offset = ring_index * segments
        next_offset = offset + segments
        for index in range(segments):
            following = (index + 1) % segments
            faces.append((offset + index, offset + following, next_offset + following, next_offset + index))
    bottom_center = len(vertices)
    top_center = bottom_center + 1
    vertices.extend(((0, rings[0][3], rings[0][0]), (0, rings[-1][3], rings[-1][0])))
    for index in range(segments):
        following = (index + 1) % segments
        faces.append((bottom_center, following, index))
        top_offset = (len(rings) - 1) * segments
        faces.append((top_center, top_offset + index, top_offset + following))
    mesh = bpy.data.meshes.new(f"{name}_Data")
    mesh.from_pydata(vertices, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bevel = obj.modifiers.new("CE_Loft_Soften", "BEVEL")
    bevel.width = 0.014
    bevel.segments = 3
    return _smooth(_assign(obj, material))


def _open_ellipsoid_shell(
    bpy,
    name: str,
    rings,
    material,
    *,
    arc_start: float,
    arc_end: float,
    segments: int = 48,
    thickness: float = 0.012,
):
    """Build a fitted open shell for garments or hair without proxy spheres."""
    vertices = []
    for z, radius_x, radius_y, center_y in rings:
        for index in range(segments + 1):
            blend = index / segments
            angle = arc_start + (arc_end - arc_start) * blend
            vertices.append((radius_x * math.cos(angle), center_y + radius_y * math.sin(angle), z))
    stride = segments + 1
    faces = []
    for ring_index in range(len(rings) - 1):
        offset = ring_index * stride
        next_offset = offset + stride
        for index in range(segments):
            faces.append((offset + index, offset + index + 1, next_offset + index + 1, next_offset + index))
    mesh = bpy.data.meshes.new(f"{name}_Data")
    mesh.from_pydata(vertices, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    solidify = obj.modifiers.new("CE_Fitted_Shell", "SOLIDIFY")
    solidify.thickness = thickness
    solidify.offset = 0.0
    bevel = obj.modifiers.new("CE_Shell_Edges", "BEVEL")
    bevel.width = thickness * 0.72
    bevel.segments = 3
    return _smooth(_assign(obj, material))


def _sculpted_head_v3(bpy, material):
    """Create June's nose, cheeks, jaw, and chin as one deformed head surface."""
    head = _sphere(
        bpy,
        "June_Head",
        (0, 0, 2.64),
        (0.285, 0.245, 0.39),
        material,
        segments=96,
        rings=64,
    )

    def field(x, z, center_x, center_z, width_x, width_z):
        return math.exp(-(((x - center_x) / width_x) ** 2 + ((z - center_z) / width_z) ** 2))

    for vertex in head.data.vertices:
        x, y, z = vertex.co
        if y >= 0:
            continue
        front = min(1.0, max(0.0, -y / 0.245))
        nose = field(x, z, 0.010, -0.005, 0.052, 0.115)
        bridge = field(x, z, 0.006, 0.115, 0.060, 0.150)
        cheek_l = field(x, z, -0.158, -0.020, 0.090, 0.115)
        cheek_r = field(x, z, 0.150, -0.040, 0.085, 0.110)
        chin = field(x, z, 0.010, -0.245, 0.125, 0.085)
        jaw_l = field(x, z, -0.145, -0.180, 0.105, 0.105)
        jaw_r = field(x, z, 0.137, -0.190, 0.100, 0.100)
        socket_l = field(x, z, -0.105, 0.075, 0.070, 0.055)
        socket_r = field(x, z, 0.108, 0.069, 0.070, 0.055)
        vertex.co.y -= front * (
            0.102 * nose
            + 0.030 * bridge
            + 0.040 * cheek_l
            + 0.035 * cheek_r
            + 0.038 * chin
            + 0.020 * jaw_l
            + 0.017 * jaw_r
            - 0.018 * socket_l
            - 0.016 * socket_r
        )
        vertex.co.x += front * (0.004 * nose + 0.003 * cheek_r - 0.002 * cheek_l)
        vertex.co.z -= front * 0.012 * nose

    basis = head.shape_key_add(name="Basis")
    expression_controls = ("smile", "thoughtful", "soft_chuckle", "brow_raise", "brow_knit", "squint", "cheek_raise")
    for control in expression_controls:
        key = head.shape_key_add(name=control)
        for source, target in zip(basis.data, key.data):
            front = max(0.0, min(1.0, -source.co.y / 0.28))
            lower = max(0.0, min(1.0, (0.08 - source.co.z) / 0.34))
            upper = max(0.0, min(1.0, (source.co.z + 0.02) / 0.34))
            center = max(0.0, 1.0 - abs(source.co.x) / 0.20)
            if control == "smile":
                target.co.x *= 1.0 + 0.055 * front * lower
                target.co.z += 0.022 * front * lower * min(1.0, abs(source.co.x) / 0.18)
            elif control == "thoughtful":
                target.co.x += 0.010 * front * lower
                target.co.z -= 0.010 * front * lower
            elif control == "soft_chuckle":
                target.co.x *= 1.0 + 0.040 * front
                target.co.z += 0.018 * front * lower
            elif control == "brow_raise":
                target.co.z += 0.014 * front * upper
            elif control == "brow_knit":
                target.co.x *= 1.0 - 0.028 * front * upper * center
            elif control == "squint":
                target.co.z -= 0.011 * front * upper
            elif control == "cheek_raise":
                target.co.z += 0.016 * front * lower * (1.0 - center * 0.4)
    head["ce_expression_controls"] = ",".join(expression_controls)
    head["ce_unified_landmarks"] = "nose,bridge,cheeks,jaw,chin"
    head["ce_surface_topology"] = "single_sculpted_head_surface"
    return head


def _beard_patch_v3(bpy, material):
    """Create one fitted beard surface that follows the lower face and jaw."""
    rows = (
        (2.515, 0.170, -0.262),
        (2.480, 0.205, -0.260),
        (2.435, 0.190, -0.240),
        (2.390, 0.145, -0.208),
        (2.365, 0.072, -0.185),
    )
    columns = 20
    vertices = []
    for z, width, center_y in rows:
        for index in range(columns + 1):
            normalized = -1.0 + 2.0 * index / columns
            x = width * normalized + 0.005
            y = center_y + 0.085 * abs(normalized) ** 1.8
            vertices.append((x, y, z - 0.010 * normalized))
    faces = []
    stride = columns + 1
    for row in range(len(rows) - 1):
        for index in range(columns):
            offset = row * stride + index
            faces.append((offset, offset + 1, offset + stride + 1, offset + stride))
    mesh = bpy.data.meshes.new("June_Fitted_Beard_Data")
    mesh.from_pydata(vertices, [], faces)
    obj = bpy.data.objects.new("June_Fitted_Beard", mesh)
    bpy.context.collection.objects.link(obj)
    solidify = obj.modifiers.new("CE_Beard_Depth", "SOLIDIFY")
    solidify.thickness = 0.018
    solidify.offset = -0.2
    subdivision = obj.modifiers.new("CE_Beard_Subdivision", "SUBSURF")
    subdivision.levels = 2
    subdivision.render_levels = 2
    return _smooth(_assign(obj, material))


def _parent_to_bone(obj, rig, bone_name: str) -> None:
    matrix = obj.matrix_world.copy()
    obj.parent = rig
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = matrix


def _weighted_chain_surface(
    bpy,
    mathutils,
    name: str,
    points,
    radii,
    ring_weights,
    rig,
    material,
    *,
    radial_segments: int = 28,
):
    """Create a continuous preserve-volume limb driven by two or more bones."""
    if not (len(points) == len(radii) == len(ring_weights)) or len(points) < 2:
        raise ValueError("weighted chain points, radii, and weights must align")
    path = [mathutils.Vector(point) for point in points]
    vertices = []
    vertex_weights = []
    for ring_index, (point, radius, weights) in enumerate(zip(path, radii, ring_weights)):
        if ring_index == 0:
            tangent = path[1] - point
        elif ring_index == len(path) - 1:
            tangent = point - path[-2]
        else:
            tangent = path[ring_index + 1] - path[ring_index - 1]
        tangent.normalize()
        reference = mathutils.Vector((0.0, 0.0, 1.0))
        if abs(tangent.dot(reference)) > 0.92:
            reference = mathutils.Vector((0.0, 1.0, 0.0))
        axis_u = tangent.cross(reference).normalized()
        axis_v = tangent.cross(axis_u).normalized()
        for segment in range(radial_segments):
            angle = math.tau * segment / radial_segments
            offset = axis_u * (math.cos(angle) * radius) + axis_v * (math.sin(angle) * radius)
            vertices.append(tuple(point + offset))
            vertex_weights.append(weights)
    faces = []
    for ring_index in range(len(path) - 1):
        offset = ring_index * radial_segments
        next_offset = offset + radial_segments
        for segment in range(radial_segments):
            following = (segment + 1) % radial_segments
            faces.append((offset + segment, offset + following, next_offset + following, next_offset + segment))
    start_center = len(vertices)
    end_center = start_center + 1
    vertices.extend((tuple(path[0]), tuple(path[-1])))
    vertex_weights.extend((ring_weights[0], ring_weights[-1]))
    for segment in range(radial_segments):
        following = (segment + 1) % radial_segments
        faces.append((start_center, following, segment))
        last = (len(path) - 1) * radial_segments
        faces.append((end_center, last + segment, last + following))

    mesh = bpy.data.meshes.new(f"{name}_Data")
    mesh.from_pydata(vertices, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    _assign(obj, material)
    _smooth(obj)
    group_names = sorted({bone for weights in ring_weights for bone in weights})
    groups = {bone: obj.vertex_groups.new(name=bone) for bone in group_names}
    for vertex_index, weights in enumerate(vertex_weights):
        total = sum(max(0.0, float(weight)) for weight in weights.values())
        if total <= 0:
            raise ValueError(f"weighted chain vertex has no deformation weight: {name}")
        for bone, weight in weights.items():
            groups[bone].add([vertex_index], max(0.0, float(weight)) / total, "REPLACE")
    armature = obj.modifiers.new("CE_Preserve_Volume_Rig", "ARMATURE")
    armature.object = rig
    armature.use_deform_preserve_volume = True
    corrective = obj.modifiers.new("CE_Joint_Corrective", "CORRECTIVE_SMOOTH")
    corrective.factor = 0.38
    corrective.iterations = 4
    subdivision = obj.modifiers.new("CE_Production_Subdivision", "SUBSURF")
    subdivision.levels = 2
    subdivision.render_levels = 2
    obj["ce_deformation_standard"] = "weighted_chain_preserve_volume_corrective_smooth"
    obj["ce_weighted_bones"] = ",".join(group_names)
    return obj


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


def _make_june_v3(bpy, mathutils, materials: dict):
    """Hero v3: unified facial sculpture plus fitted hair, beard, and garments."""
    rig, mouth, face_controls = _make_june_v2(bpy, mathutils, materials)

    replace_names = {
        "June_Head",
        "June_Cheek_L",
        "June_Cheek_R",
        "June_Chin",
        "June_Nose",
        "June_Close_Beard",
        "June_Plaid_Torso",
        "June_Denim_Jacket_L",
        "June_Denim_Jacket_R",
    }
    replace_names.update(
        obj.name for obj in bpy.data.objects if obj.name.startswith("June_White_Hair_")
    )
    for name in replace_names:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)

    torso = _loft_mesh(
        bpy,
        "June_Plaid_Torso",
        (
            (1.22, 0.270, 0.185, 0.025),
            (1.42, 0.300, 0.205, 0.020),
            (1.72, 0.325, 0.215, 0.020),
            (1.98, 0.315, 0.205, 0.015),
            (2.16, 0.275, 0.185, 0.010),
            (2.25, 0.205, 0.145, 0.005),
        ),
        materials["plaid"],
        segments=56,
    )
    torso["ce_surface_topology"] = "single_tapered_torso_loft"
    _parent_to_bone(torso, rig, "torso")

    jacket = _open_ellipsoid_shell(
        bpy,
        "June_Denim_Jacket_Shell",
        (
            (1.34, 0.315, 0.220, 0.020),
            (1.63, 0.355, 0.245, 0.020),
            (1.92, 0.365, 0.245, 0.015),
            (2.15, 0.315, 0.205, 0.010),
        ),
        materials["denim"],
        arc_start=math.radians(-67),
        arc_end=math.radians(247),
        segments=64,
        thickness=0.020,
    )
    jacket["ce_garment_pattern"] = "single_open_denim_shell"
    _parent_to_bone(jacket, rig, "torso")

    head = _sculpted_head_v3(bpy, materials["skin"])
    _parent_to_bone(head, rig, "head")

    hair_shell = _open_ellipsoid_shell(
        bpy,
        "June_White_Hair_Shell",
        (
            (2.625, 0.283, 0.238, 0.026),
            (2.735, 0.278, 0.238, 0.030),
            (2.835, 0.246, 0.216, 0.038),
            (2.915, 0.190, 0.170, 0.045),
            (2.970, 0.105, 0.095, 0.050),
        ),
        materials["hair"],
        arc_start=math.radians(-18),
        arc_end=math.radians(198),
        segments=56,
        thickness=0.014,
    )
    hair_shell["ce_hair_design"] = "fitted_horseshoe_shell_with_bald_crown"
    _parent_to_bone(hair_shell, rig, "head")
    for index, x in enumerate((-0.16, -0.09, 0.085, 0.15)):
        wisp = _curve(
            bpy,
            f"June_Hair_Wisp_{index}",
            ((x, -0.070, 2.935), (x * 1.04, -0.092, 2.975), (x * 1.10, -0.060, 3.005)),
            materials["hair"],
            bevel_depth=0.006,
        )
        _parent_to_bone(wisp, rig, "head")

    beard = _beard_patch_v3(bpy, materials["hair"])
    beard["ce_beard_design"] = "single_fitted_jaw_patch"
    _parent_to_bone(beard, rig, "head")

    # Keep the established viseme topology, but make its performance readable in
    # a hero close-up and keep teeth tucked behind the lip rim.
    mouth.scale.x *= 1.10
    mouth.scale.z *= 1.18
    teeth = bpy.data.objects.get("June_Upper_Teeth")
    if teeth is not None:
        teeth.scale.x *= 1.06

    rig["ce_asset_major"] = 3
    rig["ce_surface_standard"] = "unified_sculpted_hero_surfaces"
    rig["ce_face_topology"] = "single_head_surface_radial_lip_rim_independent_lids"
    rig["ce_garment_topology"] = "lofted_torso_open_denim_shell"
    return rig, mouth, face_controls


def _make_june_v4(bpy, mathutils, materials: dict):
    """Hero v4: canonical identity tuning plus continuous weighted deformation."""
    rig, mouth, face_controls = _make_june_v3(bpy, mathutils, materials)

    # Replace segmented tubes with continuous weighted surfaces. Closely spaced
    # rings around elbows and knees provide a deformation zone rather than a
    # rigid hinge; preserve-volume and corrective smoothing finish the bend.
    legacy_limbs = {
        "June_upper_arm.L", "June_forearm.L", "June_upper_arm.R", "June_forearm.R",
        "June_thigh.L", "June_shin.L", "June_thigh.R", "June_shin.R",
    }
    for name in legacy_limbs:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)

    for side in ("L", "R"):
        upper_name = f"upper_arm.{side}"
        fore_name = f"forearm.{side}"
        upper = rig.data.bones[upper_name]
        fore = rig.data.bones[fore_name]
        shoulder = upper.head_local.copy()
        elbow = upper.tail_local.copy()
        wrist = fore.tail_local.copy()
        arm_points = (
            shoulder,
            shoulder.lerp(elbow, 0.48),
            shoulder.lerp(elbow, 0.86),
            elbow.lerp(wrist, 0.14),
            elbow.lerp(wrist, 0.58),
            wrist,
        )
        arm_radii = (0.112, 0.105, 0.090, 0.086, 0.076, 0.066)
        arm_weights = (
            {upper_name: 1.0},
            {upper_name: 1.0},
            {upper_name: 0.82, fore_name: 0.18},
            {upper_name: 0.18, fore_name: 0.82},
            {fore_name: 1.0},
            {fore_name: 1.0},
        )
        sleeve = _weighted_chain_surface(
            bpy,
            mathutils,
            f"June_Weighted_Jacket_Sleeve_{side}",
            arm_points,
            arm_radii,
            arm_weights,
            rig,
            materials["denim"],
            radial_segments=32,
        )
        sleeve["ce_joint"] = "continuous_elbow"

        thigh_name = f"thigh.{side}"
        shin_name = f"shin.{side}"
        thigh = rig.data.bones[thigh_name]
        shin = rig.data.bones[shin_name]
        hip = thigh.head_local.copy()
        knee = thigh.tail_local.copy()
        ankle = shin.tail_local.copy()
        leg_points = (
            hip,
            hip.lerp(knee, 0.48),
            hip.lerp(knee, 0.86),
            knee.lerp(ankle, 0.14),
            knee.lerp(ankle, 0.58),
            ankle,
        )
        leg_radii = (0.124, 0.116, 0.101, 0.098, 0.086, 0.073)
        leg_weights = (
            {thigh_name: 1.0},
            {thigh_name: 1.0},
            {thigh_name: 0.82, shin_name: 0.18},
            {thigh_name: 0.18, shin_name: 0.82},
            {shin_name: 1.0},
            {shin_name: 1.0},
        )
        trouser = _weighted_chain_surface(
            bpy,
            mathutils,
            f"June_Weighted_Overall_Leg_{side}",
            leg_points,
            leg_radii,
            leg_weights,
            rig,
            materials["overalls"],
            radial_segments=32,
        )
        trouser["ce_joint"] = "continuous_knee"

    # Canonical June has large, emotionally legible blue-gray eyes. Scale the
    # complete eye stack together and widen the lids around their own centers.
    for side, center_x, center_z in (("L", -0.105, 2.715), ("R", 0.108, 2.709)):
        for prefix, scale_x, scale_z in (
            ("June_Eye_", 1.48, 1.45),
            ("June_Iris_", 1.50, 1.50),
            ("June_Pupil_", 1.38, 1.42),
            ("June_Catchlight_", 1.35, 1.35),
        ):
            obj = bpy.data.objects.get(f"{prefix}{side}")
            if obj is not None:
                obj.scale.x *= scale_x
                obj.scale.z *= scale_z
        for prefix in ("June_Eyelid_Upper_", "June_Eyelid_Lower_", "June_Brow_"):
            curve = bpy.data.objects.get(f"{prefix}{side}")
            if curve is None:
                continue
            for spline in curve.data.splines:
                for point in spline.bezier_points:
                    point.co.x = center_x + (point.co.x - center_x) * 1.43
                    point.co.z = center_z + (point.co.z - center_z) * 1.34
            curve.data.bevel_depth *= 1.12

    # Increase expression displacement while retaining the v3 sculpt as basis.
    head = bpy.data.objects["June_Head"]
    basis = head.data.shape_keys.key_blocks.get("Basis")
    if basis is not None:
        for key in head.data.shape_keys.key_blocks:
            if key.name == "Basis":
                continue
            for base_point, target in zip(basis.data, key.data):
                target.co = base_point.co + (target.co - base_point.co) * 1.65
    head["ce_expression_readability_gain"] = 1.65

    # A fuller, rounder beard and stronger mouth opening bring the face back to
    # the canonical turnaround and make visemes survive medium-shot framing.
    beard = bpy.data.objects.get("June_Fitted_Beard")
    if beard is not None:
        for vertex in beard.data.vertices:
            vertex.co.x = 0.005 + (vertex.co.x - 0.005) * 1.16
            vertex.co.z = 2.455 + (vertex.co.z - 2.455) * 1.30
            vertex.co.y -= 0.012
        beard["ce_beard_design"] = "canonical_full_rounded_fitted_patch"
    mouth.scale.x *= 1.12
    mouth.scale.z *= 1.58
    mouth.location.y -= 0.018
    mouth["ce_performance_scale"] = "canonical_large_eye_full_beard_closeup"
    teeth = bpy.data.objects.get("June_Upper_Teeth")
    if teeth is not None:
        teeth.scale.z *= 0.72

    # Soft side masses read as swept white hair from the front; the fitted v3
    # shell remains underneath for profile continuity.
    hair_specs = (
        ("L_Temple", (-0.266, 0.020, 2.820), (0.080, 0.108, 0.120)),
        ("R_Temple", (0.258, 0.024, 2.806), (0.076, 0.104, 0.114)),
        ("L_Sweep", (-0.205, 0.035, 2.925), (0.110, 0.125, 0.070)),
        ("R_Sweep", (0.190, 0.040, 2.915), (0.102, 0.120, 0.066)),
    )
    for label, location, scale in hair_specs:
        tuft = _sphere(
            bpy,
            f"June_Canonical_Hair_{label}",
            location,
            scale,
            materials["hair"],
            segments=48,
            rings=24,
        )
        _parent_to_bone(tuft, rig, "head")

    rig["ce_asset_major"] = 4
    rig["ce_identity_reference"] = "june-oxley-canonical-turnaround-v1.png"
    rig["ce_body_deformation"] = "continuous_weighted_sleeves_and_trousers"
    rig["ce_surface_standard"] = "canonical_identity_weighted_deformation_hero"
    rig["ce_face_topology"] = "unified_sculpt_large_eye_full_beard_radial_lip"
    return rig, mouth, face_controls


MOUTH_V5_SHAPE_SCALE = {
    "A": (1.00, 1.25),
    "B": (0.74, 1.65),
    "C": (1.20, 0.68),
    "D": (0.90, 1.42),
    "E": (1.22, 0.44),
    "F": (0.72, 0.72),
    "G": (0.64, 1.50),
    "H": (0.56, 1.08),
    "X": (1.00, 0.14),
}


# Artist-authored mouth poses.  These values describe anatomy, not global
# object scale: the mouth bag keeps its upper attachment, the two lips change
# contour independently, and dental/tongue exposure is bounded per phoneme.
MOUTH_V7_POSES = {
    "A": {"width": 1.00, "opening": 0.48, "round": 0.12, "upper_roll": 0.18, "lower_roll": 0.20, "upper_teeth": 0.42, "lower_teeth": 0.04, "tongue": 0.12, "beard_follow": 0.18},
    "B": {"width": 0.82, "opening": 0.82, "round": 0.58, "upper_roll": 0.26, "lower_roll": 0.30, "upper_teeth": 0.52, "lower_teeth": 0.08, "tongue": 0.18, "beard_follow": 0.28},
    "C": {"width": 1.16, "opening": 0.38, "round": 0.04, "upper_roll": 0.12, "lower_roll": 0.14, "upper_teeth": 0.62, "lower_teeth": 0.06, "tongue": 0.20, "beard_follow": 0.12},
    "D": {"width": 0.98, "opening": 0.72, "round": 0.24, "upper_roll": 0.24, "lower_roll": 0.28, "upper_teeth": 0.48, "lower_teeth": 0.12, "tongue": 0.26, "beard_follow": 0.24},
    "E": {"width": 1.18, "opening": 0.24, "round": 0.02, "upper_roll": 0.08, "lower_roll": 0.10, "upper_teeth": 0.66, "lower_teeth": 0.04, "tongue": 0.14, "beard_follow": 0.08},
    "F": {"width": 0.84, "opening": 0.32, "round": 0.20, "upper_roll": 0.10, "lower_roll": 0.34, "upper_teeth": 0.70, "lower_teeth": 0.00, "tongue": 0.06, "beard_follow": 0.10},
    "G": {"width": 0.72, "opening": 0.86, "round": 0.78, "upper_roll": 0.34, "lower_roll": 0.38, "upper_teeth": 0.28, "lower_teeth": 0.06, "tongue": 0.10, "beard_follow": 0.30},
    "H": {"width": 0.68, "opening": 0.58, "round": 0.64, "upper_roll": 0.22, "lower_roll": 0.26, "upper_teeth": 0.24, "lower_teeth": 0.26, "tongue": 0.72, "beard_follow": 0.20},
    "X": {"width": 1.00, "opening": 0.06, "round": 0.00, "upper_roll": 0.04, "lower_roll": 0.05, "upper_teeth": 0.00, "lower_teeth": 0.00, "tongue": 0.00, "beard_follow": 0.00},
}


MOUTH_V8_SOFT_TISSUE = {
    "A": {"opening": 0.50, "corner_l": 0.10, "corner_r": 0.04, "cheek_l": 0.12, "cheek_r": 0.08, "dental_exposure": 0.42, "groove_visibility": 0.48},
    "B": {"opening": 0.86, "corner_l": 0.04, "corner_r": -0.03, "cheek_l": 0.18, "cheek_r": 0.12, "dental_exposure": 0.60, "groove_visibility": 0.68},
    "C": {"opening": 0.24, "corner_l": 0.35, "corner_r": 0.24, "cheek_l": 0.38, "cheek_r": 0.28, "dental_exposure": 0.68, "groove_visibility": 0.72},
    "D": {"opening": 0.62, "corner_l": 0.12, "corner_r": 0.03, "cheek_l": 0.20, "cheek_r": 0.14, "dental_exposure": 0.54, "groove_visibility": 0.62},
    "E": {"opening": 0.14, "corner_l": 0.42, "corner_r": 0.30, "cheek_l": 0.44, "cheek_r": 0.32, "dental_exposure": 0.74, "groove_visibility": 0.80},
    "F": {"opening": 0.13, "corner_l": -0.04, "corner_r": 0.03, "cheek_l": 0.12, "cheek_r": 0.16, "dental_exposure": 0.82, "groove_visibility": 0.82},
    "G": {"opening": 0.82, "corner_l": -0.08, "corner_r": -0.03, "cheek_l": 0.12, "cheek_r": 0.10, "dental_exposure": 0.30, "groove_visibility": 0.30},
    "H": {"opening": 0.44, "corner_l": 0.08, "corner_r": -0.06, "cheek_l": 0.16, "cheek_r": 0.08, "dental_exposure": 0.38, "groove_visibility": 0.38},
    "X": {"opening": 0.00, "corner_l": 0.02, "corner_r": -0.02, "cheek_l": 0.04, "cheek_r": 0.02, "dental_exposure": 0.00, "groove_visibility": 0.00},
}


MOUTH_V8_POSES = {
    shape: {**MOUTH_V7_POSES[shape], **MOUTH_V8_SOFT_TISSUE[shape]}
    for shape in MOUTH_V7_POSES
}


FACIAL_V6_CORRECTIVES = (
    "mouth_corner.L",
    "mouth_corner.R",
    "mouth_press",
    "inner_brow_raise",
    "lower_lid_engage",
    "jaw_soften",
)


HAND_V6_POSES = {
    # Five (proximal, distal, spread) triplets: index through little finger,
    # then thumb.  Values are degrees and intentionally asymmetric by role.
    "relaxed": (
        (18.0, 24.0, -3.0), (22.0, 30.0, -1.0), (25.0, 34.0, 1.0),
        (30.0, 39.0, 3.0), (21.0, 28.0, -10.0),
    ),
    "mug_grip": (
        (44.0, 58.0, -1.0), (52.0, 66.0, 0.0), (56.0, 70.0, 1.0),
        (50.0, 64.0, 2.0), (36.0, 48.0, -18.0),
    ),
    "chair_support": (
        (12.0, 18.0, -7.0), (16.0, 22.0, -2.0), (18.0, 25.0, 2.0),
        (21.0, 28.0, 6.0), (24.0, 31.0, -13.0),
    ),
    "ledger_support": (
        (28.0, 36.0, -5.0), (34.0, 42.0, -2.0), (38.0, 47.0, 1.0),
        (42.0, 52.0, 4.0), (30.0, 38.0, -16.0),
    ),
    "pencil_tripod": (
        (24.0, 18.0, -4.0), (56.0, 68.0, -1.0), (62.0, 72.0, 1.0),
        (66.0, 76.0, 3.0), (22.0, 16.0, -21.0),
    ),
    "open_empathy": (
        (8.0, 10.0, -9.0), (10.0, 12.0, -4.0), (12.0, 14.0, 2.0),
        (15.0, 18.0, 8.0), (17.0, 20.0, -15.0),
    ),
}


FACIAL_V6_DRIVERS = {
    "smile": {
        "smile": 1.0, "mouth_corner.L": 0.92, "mouth_corner.R": 0.82,
        "cheek_raise": 0.38, "lower_lid_engage": 0.16,
    },
    "soft_chuckle": {
        "soft_chuckle": 1.0, "mouth_corner.L": 0.78, "mouth_corner.R": 0.70,
        "cheek_raise": 0.62, "lower_lid_engage": 0.34, "jaw_soften": 0.22,
    },
    "thoughtful": {
        "thoughtful": 1.0, "mouth_press": 0.46, "mouth_corner.L": 0.12,
        "inner_brow_raise": 0.30, "lower_lid_engage": 0.28, "jaw_soften": 0.18,
    },
    "brow_raise": {"brow_raise": 1.0, "inner_brow_raise": 0.58},
    "brow_knit": {
        "brow_knit": 1.0, "mouth_press": 0.34, "lower_lid_engage": 0.40,
        "jaw_soften": 0.28,
    },
    "squint": {"squint": 1.0, "lower_lid_engage": 0.72, "cheek_raise": 0.28},
    "cheek_raise": {"cheek_raise": 1.0, "lower_lid_engage": 0.46},
}


def _hand_pose_vector(name: str) -> tuple[float, ...]:
    """Flatten a named five-digit hand pose into an interpolation-safe vector."""
    try:
        pose = HAND_V6_POSES[name]
    except KeyError as exc:
        raise ValueError(f"unsupported June hand pose: {name}") from exc
    return tuple(value for digit in pose for value in digit)


def _facial_driver_weights(expression: str, strength: float) -> dict[str, float]:
    """Resolve a primary acting cue into coordinated deformation controls."""
    drivers = FACIAL_V6_DRIVERS.get(str(expression), {str(expression): 1.0})
    return {
        name: max(0.0, min(1.0, float(value) * float(strength)))
        for name, value in drivers.items()
    }


def _weights_blend(start: dict[str, float], target: dict[str, float], amount: float) -> dict[str, float]:
    names = set(start) | set(target)
    return {
        name: float(start.get(name, 0.0)) + (float(target.get(name, 0.0)) - float(start.get(name, 0.0))) * amount
        for name in names
    }


def _facial_polish_keys(cues: list[dict], frame_end: int, polish: dict) -> list[dict]:
    """Compile facial cues into eased anticipation, overlap, and settle keys."""
    if not cues:
        return []
    enabled = bool(polish.get("enabled"))
    transition = int(polish.get("transition_frames", 0)) if enabled else 0
    overshoot = float(polish.get("overshoot_ratio", 0.0)) if enabled else 0.0
    result: dict[int, dict] = {}
    previous_weights: dict[str, float] = {}
    for index, cue in enumerate(cues):
        start = max(1, int(cue["frame_start"]))
        end = min(int(frame_end), int(cue["frame_end"]))
        expression = str(cue["expression"])
        strength = float(cue.get("strength", 1.0))
        target = _facial_driver_weights(expression, strength)
        if index == 0 or transition <= 0:
            result[start] = {
                "frame": start, "role": "facial_cue", "expression": expression,
                "strength": strength, "weights": target,
            }
        else:
            anticipate_frame = max(int(cues[index - 1]["frame_start"]), start - transition)
            breakdown_frame = start
            settle_frame = min(end, start + transition)
            # The previous cue normally contributes a hold key at ``start - 1``.
            # Remove keys inside the transition window so interpolation can
            # actually begin at anticipation instead of popping one frame late.
            for existing_frame in tuple(result):
                if anticipate_frame < existing_frame < start:
                    result.pop(existing_frame)
            result[anticipate_frame] = {
                "frame": anticipate_frame, "role": "facial_anticipation",
                "expression": expression, "strength": strength, "weights": dict(previous_weights),
            }
            result[breakdown_frame] = {
                "frame": breakdown_frame, "role": "facial_breakdown",
                "expression": expression, "strength": strength,
                "weights": _weights_blend(previous_weights, target, 0.58),
            }
            result[settle_frame] = {
                "frame": settle_frame, "role": "facial_settle",
                "expression": expression, "strength": strength,
                "weights": {name: min(1.0, value * (1.0 + overshoot)) for name, value in target.items()},
            }
            if settle_frame + 2 <= end:
                result[settle_frame + 2] = {
                    "frame": settle_frame + 2, "role": "facial_hold",
                    "expression": expression, "strength": strength, "weights": target,
                }
        result[end] = {
            "frame": end, "role": "facial_hold", "expression": expression,
            "strength": strength, "weights": target,
        }
        previous_weights = target
    return [result[frame] for frame in sorted(result)]


def _make_mouth_v5(bpy, rig, materials: dict):
    """Build a camera-facing mouth cavity that survives beard and mustache overlap."""
    lip_rim = _sphere(
        bpy,
        "June_Mouth_Lip_Rim",
        (0.0, -0.423, 2.490),
        (0.142, 0.014, 0.043),
        materials["lip"],
        segments=48,
        rings=24,
    )
    lip_rim["ce_mouth_role"] = "deforming_lip_rim"
    _parent_to_bone(lip_rim, rig, "jaw")
    mouth = _sphere(
        bpy,
        "June_Mouth_Viseme",
        (0.0, -0.432, 2.490),
        (0.132, 0.010, 0.034),
        materials["mouth_interior"],
        segments=48,
        rings=24,
    )
    basis = mouth.shape_key_add(name="Basis")
    for name, (width, height) in MOUTH_V5_SHAPE_SCALE.items():
        key = mouth.shape_key_add(name=name)
        for source, target in zip(basis.data, key.data):
            target.co.x = source.co.x * width
            target.co.z = source.co.z * height
    mouth["ce_mouth_topology"] = "camera_facing_cavity_with_readable_viseme_extremes"
    _parent_to_bone(mouth, rig, "jaw")

    teeth = _box(
        bpy,
        "June_Upper_Teeth",
        (0.0, -0.445, 2.508),
        (0.060, 0.003, 0.009),
        materials["teeth"],
        bevel=0.006,
    )
    _parent_to_bone(teeth, rig, "jaw")
    return mouth


def _make_performance_props_v5(bpy, mathutils, rig, materials: dict) -> None:
    """Create the Golden Scene's contact props with explicit shot roles."""
    held_mug = _cylinder(bpy, "June_Held_Mug", (0.64, -0.53, 1.43), 0.070, 0.115, materials["enamel"], vertices=36)
    held_coffee = _cylinder(bpy, "June_Held_Mug_Coffee", (0.64, -0.53, 1.489), 0.059, 0.003, materials["coffee"], vertices=36)
    held_handle = _curve(
        bpy,
        "June_Held_Mug_Handle",
        ((0.70, -0.53, 1.47), (0.76, -0.53, 1.47), (0.77, -0.53, 1.40), (0.70, -0.53, 1.39)),
        materials["enamel"],
        bevel_depth=0.010,
    )
    for obj in (held_mug, held_coffee, held_handle):
        obj["ce_prop_role"] = "held_mug"
        _parent_to_bone(obj, rig, "hand.R")

    table_mug = _cylinder(bpy, "June_Table_Mug", (0.76, -0.50, 1.30), 0.072, 0.118, materials["enamel"], vertices=36)
    table_coffee = _cylinder(bpy, "June_Table_Mug_Coffee", (0.76, -0.50, 1.361), 0.061, 0.003, materials["coffee"], vertices=36)
    table_handle = _curve(
        bpy,
        "June_Table_Mug_Handle",
        ((0.82, -0.50, 1.34), (0.88, -0.50, 1.34), (0.89, -0.50, 1.27), (0.82, -0.50, 1.26)),
        materials["enamel"],
        bevel_depth=0.010,
    )
    for obj in (table_mug, table_coffee, table_handle):
        obj["ce_prop_role"] = "table_mug"

    ledger = _box(bpy, "June_Ledger", (-0.49, -0.49, 1.44), (0.095, 0.018, 0.135), materials["ledger_leather"], bevel=0.012)
    ledger.rotation_euler[1] = math.radians(-10)
    ledger["ce_prop_role"] = "ledger"
    _parent_to_bone(ledger, rig, "hand.L")

    pencil = _cylinder_between(
        bpy,
        mathutils,
        "June_Pencil",
        (0.57, -0.50, 1.47),
        (0.66, -0.58, 1.38),
        0.008,
        materials["pencil_cedar"],
    )
    pencil["ce_prop_role"] = "pencil"
    _parent_to_bone(pencil, rig, "hand.R")

    _box(bpy, "Performance_Table_Top", (0.76, -0.50, 1.22), (0.28, 0.22, 0.035), materials["dark_wood"], bevel=0.025)
    for x in (0.58, 0.94):
        for y in (-0.36, -0.64):
            _cylinder_between(
                bpy,
                mathutils,
                f"Performance_Table_Leg_{x}_{y}",
                (x, y, 0.28),
                (x, y, 1.20),
                0.025,
                materials["dark_wood"],
            )

    for obj in bpy.context.scene.objects:
        if obj.get("ce_prop_role"):
            obj.hide_render = True
            obj.hide_viewport = True


def _make_june_v5(bpy, mathutils, materials: dict):
    """Hero v5: production IK, facial aim, digit controls, and contact props."""
    rig, mouth, face_controls = _make_june_v4(bpy, mathutils, materials)
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    edit = rig.data.edit_bones

    def add_control(name, head, tail, parent=None, *, deform=False):
        bone = edit.new(name)
        bone.head = head
        bone.tail = tail
        bone.use_deform = deform
        if parent:
            bone.parent = edit[parent]
        return bone

    add_control("clavicle.L", (-0.10, 0.0, 2.16), (-0.35, 0.0, 2.10), "torso", deform=True)
    add_control("clavicle.R", (0.10, 0.0, 2.16), (0.35, 0.0, 2.10), "torso", deform=True)
    edit["upper_arm.L"].parent = edit["clavicle.L"]
    edit["upper_arm.R"].parent = edit["clavicle.R"]

    add_control("jaw", (0.0, -0.01, 2.57), (0.0, -0.16, 2.47), "head", deform=True)
    add_control("eye.L", (-0.105, -0.24, 2.715), (-0.105, -0.36, 2.715), "head", deform=True)
    add_control("eye.R", (0.108, -0.24, 2.709), (0.108, -0.36, 2.709), "head", deform=True)
    add_control("gaze", (0.0, -2.55, 2.70), (0.0, -2.55, 2.86))

    for side, sign in (("L", -1.0), ("R", 1.0)):
        add_control(f"hand_ik.{side}", (0.64 * sign, -0.40, 1.50), (0.64 * sign, -0.40, 1.66))
        add_control(f"elbow_pole.{side}", (0.92 * sign, -0.15, 1.82), (0.92 * sign, -0.15, 1.98))
        add_control(f"foot_ik.{side}", (0.22 * sign, -0.60, 0.34), (0.22 * sign, -0.60, 0.50))
        add_control(f"knee_pole.{side}", (0.22 * sign, -1.18, 1.00), (0.22 * sign, -1.18, 1.16))
        hand_parent = f"hand.{side}"
        for digit, offset in enumerate((-0.043, -0.015, 0.015, 0.043)):
            x = 0.56 * sign + offset
            add_control(
                f"finger.{digit}.{side}",
                (x, -0.42, 1.37),
                (x, -0.45, 1.28),
                hand_parent,
                deform=True,
            )
        add_control(
            f"thumb.{side}",
            (0.56 * sign + 0.055 * sign, -0.414, 1.425),
            (0.56 * sign + 0.112 * sign, -0.450, 1.36),
            hand_parent,
            deform=True,
        )

    bpy.ops.object.mode_set(mode="POSE")
    for bone in rig.pose.bones:
        bone.rotation_mode = "XYZ"
    for side in ("L", "R"):
        arm_ik = rig.pose.bones[f"forearm.{side}"].constraints.new("IK")
        arm_ik.name = f"CE_Arm_IK_{side}"
        arm_ik.target = rig
        arm_ik.subtarget = f"hand_ik.{side}"
        arm_ik.pole_target = rig
        arm_ik.pole_subtarget = f"elbow_pole.{side}"
        arm_ik.chain_count = 2
        arm_ik.influence = 0.0

        leg_ik = rig.pose.bones[f"shin.{side}"].constraints.new("IK")
        leg_ik.name = f"CE_Leg_IK_{side}"
        leg_ik.target = rig
        leg_ik.subtarget = f"foot_ik.{side}"
        leg_ik.pole_target = rig
        leg_ik.pole_subtarget = f"knee_pole.{side}"
        leg_ik.chain_count = 2
        leg_ik.influence = 0.0

        eye_track = rig.pose.bones[f"eye.{side}"].constraints.new("DAMPED_TRACK")
        eye_track.name = f"CE_Eye_Aim_{side}"
        eye_track.target = rig
        eye_track.subtarget = "gaze"
        eye_track.track_axis = "TRACK_Y"
    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.data.objects.remove(mouth, do_unlink=True)
    old_teeth = bpy.data.objects.get("June_Upper_Teeth")
    if old_teeth is not None:
        bpy.data.objects.remove(old_teeth, do_unlink=True)
    mouth = _make_mouth_v5(bpy, rig, materials)

    for side in ("L", "R"):
        for prefix in ("June_Eye_", "June_Iris_", "June_Pupil_", "June_Catchlight_"):
            obj = bpy.data.objects.get(f"{prefix}{side}")
            if obj is not None:
                _parent_to_bone(obj, rig, f"eye.{side}")
        for digit in range(4):
            for segment in ("A", "B"):
                obj = bpy.data.objects.get(f"June_Finger_{side}_{digit}_{segment}")
                if obj is not None:
                    _parent_to_bone(obj, rig, f"finger.{digit}.{side}")
        for segment in ("A", "B"):
            obj = bpy.data.objects.get(f"June_Thumb_{side}_{segment}")
            if obj is not None:
                _parent_to_bone(obj, rig, f"thumb.{side}")
    _make_performance_props_v5(bpy, mathutils, rig, materials)

    rig["ce_asset_major"] = 5
    rig["ce_control_rig"] = "arm_leg_ik_foot_lock_clavicle_digits_jaw_gaze"
    rig["ce_performance_contract"] = "june_golden_scene_performance_v1"
    rig["ce_contact_props"] = "held_mug,table_mug,ledger,pencil"
    return rig, mouth, face_controls


def _make_june_v6(bpy, mathutils, materials: dict):
    """Hero v6: coarticulated face, deforming beard, and two-joint hand shapes."""
    rig, mouth, face_controls = _make_june_v5(bpy, mathutils, materials)

    # Split every digit at its modeled knuckle so the two visible segments no
    # longer rotate as one rigid stick.  The existing proximal control remains
    # stable for old actions; the new distal child adds contact-safe curvature.
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    edit = rig.data.edit_bones
    for side in ("L", "R"):
        for digit in range(4):
            proximal_name = f"finger.{digit}.{side}"
            distal_name = f"finger_tip.{digit}.{side}"
            proximal = edit[proximal_name]
            original_tail = proximal.tail.copy()
            knuckle = proximal.head.lerp(original_tail, 0.55)
            proximal.tail = knuckle
            distal = edit.new(distal_name)
            distal.head = knuckle
            distal.tail = original_tail
            distal.parent = proximal
            distal.use_connect = True
            distal.use_deform = True
        proximal_name = f"thumb.{side}"
        distal_name = f"thumb_tip.{side}"
        proximal = edit[proximal_name]
        original_tail = proximal.tail.copy()
        knuckle = proximal.head.lerp(original_tail, 0.56)
        proximal.tail = knuckle
        distal = edit.new(distal_name)
        distal.head = knuckle
        distal.tail = original_tail
        distal.parent = proximal
        distal.use_connect = True
        distal.use_deform = True
    bpy.ops.object.mode_set(mode="POSE")
    for bone in rig.pose.bones:
        bone.rotation_mode = "XYZ"
    bpy.ops.object.mode_set(mode="OBJECT")

    for side in ("L", "R"):
        for digit in range(4):
            segment = bpy.data.objects.get(f"June_Finger_{side}_{digit}_B")
            if segment is not None:
                _parent_to_bone(segment, rig, f"finger_tip.{digit}.{side}")
        thumb_segment = bpy.data.objects.get(f"June_Thumb_{side}_B")
        if thumb_segment is not None:
            _parent_to_bone(thumb_segment, rig, f"thumb_tip.{side}")

    # Add localized correctives to the existing dense sculpt instead of adding
    # proxy cheek or mouth volumes.  These keys preserve June's canonical basis
    # while allowing asymmetrical corners, lower-lid engagement, and jaw mass.
    head = bpy.data.objects["June_Head"]
    basis = head.data.shape_keys.key_blocks["Basis"]

    def field(x, z, center_x, center_z, width_x, width_z):
        return math.exp(-(((x - center_x) / width_x) ** 2 + ((z - center_z) / width_z) ** 2))

    for control in FACIAL_V6_CORRECTIVES:
        key = head.shape_key_add(name=control)
        for source, target in zip(basis.data, key.data):
            x, y, z = source.co
            front = max(0.0, min(1.0, -y / 0.28))
            if control in {"mouth_corner.L", "mouth_corner.R"}:
                side = -1.0 if control.endswith(".L") else 1.0
                corner = field(x, z, side * 0.125, -0.135, 0.075, 0.070)
                target.co.x += side * 0.010 * front * corner
                target.co.z += 0.030 * front * corner
                target.co.y -= 0.006 * front * corner
            elif control == "mouth_press":
                press = field(x, z, 0.0, -0.135, 0.170, 0.065)
                target.co.z += 0.009 * front * press
                target.co.y += 0.008 * front * press
            elif control == "inner_brow_raise":
                brow = field(x, z, 0.0, 0.180, 0.105, 0.070)
                target.co.z += 0.022 * front * brow
                target.co.y -= 0.004 * front * brow
            elif control == "lower_lid_engage":
                lid_l = field(x, z, -0.105, 0.052, 0.080, 0.050)
                lid_r = field(x, z, 0.108, 0.046, 0.080, 0.050)
                target.co.z += 0.014 * front * (lid_l + lid_r)
            elif control == "jaw_soften":
                jaw = field(x, z, 0.005, -0.205, 0.205, 0.125)
                target.co.x *= 1.0 + 0.018 * front * jaw
                target.co.y -= 0.010 * front * jaw
                target.co.z -= 0.006 * front * jaw
    head["ce_facial_deformation"] = "localized_asymmetric_coarticulation_v1"

    # The upper teeth and upper lip stay with the skull.  A separate lower lip
    # follows the jaw, preventing the whole mouth rim from sliding downward.
    lip_rim = bpy.data.objects.get("June_Mouth_Lip_Rim")
    if lip_rim is not None:
        _parent_to_bone(lip_rim, rig, "head")
        lip_rim["ce_lip_role"] = "upper_lip"
    upper_teeth = bpy.data.objects.get("June_Upper_Teeth")
    if upper_teeth is not None:
        _parent_to_bone(upper_teeth, rig, "head")
        upper_teeth["ce_dental_role"] = "upper_teeth_skull_locked"
    lower_lip = _sphere(
        bpy,
        "June_Mouth_Lower_Lip",
        (0.0, -0.427, 2.474),
        (0.126, 0.012, 0.018),
        materials["lip"],
        segments=48,
        rings=20,
    )
    lower_lip["ce_lip_role"] = "lower_lip_jaw_follow"
    _parent_to_bone(lower_lip, rig, "jaw")

    beard = bpy.data.objects.get("June_Fitted_Beard")
    if beard is not None:
        beard_basis = beard.shape_key_add(name="Basis")
        for control in ("jaw_follow", "smile_follow", "thoughtful_follow", "cheek_follow"):
            key = beard.shape_key_add(name=control)
            for source, target in zip(beard_basis.data, key.data):
                x, y, z = source.co
                lower = max(0.0, min(1.0, (2.515 - z) / 0.155))
                side = max(0.0, min(1.0, abs(x) / 0.205))
                if control == "jaw_follow":
                    target.co.z -= 0.032 * lower
                    target.co.y -= 0.010 * lower
                elif control == "smile_follow":
                    target.co.z += 0.018 * side * (1.0 - lower * 0.45)
                    target.co.x *= 1.0 + 0.025 * side
                elif control == "thoughtful_follow":
                    target.co.z += (0.007 if x < 0 else -0.004) * side
                    target.co.x += 0.004
                elif control == "cheek_follow":
                    target.co.z += 0.012 * side * (1.0 - lower)
        beard["ce_beard_deformation"] = "jaw_expression_follow_v1"

    moustache = [
        obj for side in ("L", "R")
        if (obj := bpy.data.objects.get(f"June_Moustache_{side}")) is not None
    ]
    for obj in moustache:
        obj["ce_moustache_deformation"] = "expression_overlap_transform_v1"

    face_controls["beard"] = beard
    face_controls["moustache"] = moustache
    face_controls["lower_lip"] = lower_lip
    rig["ce_asset_major"] = 6
    rig["ce_control_rig"] = "v5_plus_distal_digits_facial_coarticulation_microacting"
    rig["ce_hand_topology"] = "five_digit_two_joint_contact_safe"
    rig["ce_face_topology"] = "unified_sculpt_local_correctives_skull_upper_lip_jaw_lower_lip"
    return rig, mouth, face_controls


def _mouth_v7_lip_vertices(pose: dict, *, upper: bool, segments: int = 24, sides: int = 8):
    """Return a closed tube following one authored lip contour."""
    vertices = []
    width = 0.112 * float(pose["width"])
    opening = float(pose["opening"])
    roll = float(pose["upper_roll"] if upper else pose["lower_roll"])
    separation = (0.001 + 0.014 * opening) if upper else -(0.002 + 0.022 * opening)
    radius_y = 0.0045 + 0.0015 * roll
    radius_z = 0.0030 + 0.0015 * roll
    for index in range(segments + 1):
        normalized = -1.0 + 2.0 * index / segments
        arch = (1.0 - normalized * normalized)
        if upper:
            cupid_peaks = math.exp(-((abs(normalized) - 0.30) / 0.18) ** 2)
            cupid_notch = math.exp(-(normalized / 0.13) ** 2)
            center_z = separation + 0.0065 * arch + 0.0022 * cupid_peaks - 0.0012 * cupid_notch
        else:
            center_z = separation - 0.0050 * arch
        center_y = -0.0018 * arch * float(pose["round"])
        for side in range(sides):
            angle = math.tau * side / sides
            vertices.append(
                (
                    width * normalized,
                    center_y + radius_y * math.cos(angle),
                    center_z + radius_z * math.sin(angle),
                )
            )
    return vertices


def _make_mouth_v7_lip(bpy, name: str, material, *, upper: bool):
    segments = 24
    sides = 8
    vertices = _mouth_v7_lip_vertices(MOUTH_V7_POSES["X"], upper=upper, segments=segments, sides=sides)
    faces = []
    for segment in range(segments):
        start = segment * sides
        following = (segment + 1) * sides
        for side in range(sides):
            next_side = (side + 1) % sides
            faces.append((start + side, start + next_side, following + next_side, following + side))
    faces.append(tuple(reversed(range(sides))))
    last = segments * sides
    faces.append(tuple(last + side for side in range(sides)))
    mesh = bpy.data.meshes.new(f"{name}_Data")
    mesh.from_pydata(vertices, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (0.0, -0.342, 2.490)
    _smooth(_assign(obj, material))
    obj.shape_key_add(name="Basis")
    for shape, pose in MOUTH_V7_POSES.items():
        key = obj.shape_key_add(name=shape)
        coordinates = _mouth_v7_lip_vertices(pose, upper=upper, segments=segments, sides=sides)
        for point, coordinate in zip(key.data, coordinates):
            point.co = coordinate
    obj["ce_mouth_component"] = "upper_lip" if upper else "lower_lip"
    obj["ce_deformation_model"] = "authored_contour_shape_keys"
    return obj


def _add_mouth_v7_transform_keys(obj, transform) -> None:
    basis = obj.shape_key_add(name="Basis")
    source_coordinates = [point.co.copy() for point in basis.data]
    for shape, pose in MOUTH_V7_POSES.items():
        key = obj.shape_key_add(name=shape)
        for point, source in zip(key.data, source_coordinates):
            point.co = transform(source.copy(), pose)


def _make_mouth_v7(bpy, rig, materials: dict):
    """Build a recessed mouth bag with independent soft tissue and oral anatomy."""
    mouth = _sphere(
        bpy,
        "June_Mouth_Viseme",
        (0.0, -0.306, 2.478),
        (0.112, 0.015, 0.036),
        materials["mouth_interior"],
        segments=48,
        rings=24,
    )
    cavity_basis = mouth.shape_key_add(name="Basis")
    for shape, pose in MOUTH_V7_POSES.items():
        key = mouth.shape_key_add(name=shape)
        height = 0.16 + 0.70 * float(pose["opening"])
        depth = 0.80 + 0.30 * float(pose["opening"])
        width = float(pose["width"]) * (1.0 - 0.10 * float(pose["round"]))
        for source, target in zip(cavity_basis.data, key.data):
            target.co.x = source.co.x * width
            target.co.y = source.co.y * depth
            target.co.z = source.co.z * height + 0.036 * (1.0 - height) * 0.65
    mouth["ce_mouth_component"] = "recessed_mouth_bag"
    mouth["ce_mouth_rig_version"] = 2
    mouth["ce_mouth_topology"] = "volumetric_upper_anchored_mouth_bag_v1"
    _parent_to_bone(mouth, rig, "head")

    upper_lip = _make_mouth_v7_lip(bpy, "June_Mouth_Upper_Lip", materials["lip"], upper=True)
    lower_lip = _make_mouth_v7_lip(bpy, "June_Mouth_Lower_Lip", materials["lip"], upper=False)
    _parent_to_bone(upper_lip, rig, "head")
    # Lower oral tissue uses jaw-coordinated shapes in head space.  Rigid bone
    # parenting would apply the jaw arc a second time after the authored lip
    # separation and visibly detach the lower cluster in wide-open phonemes.
    _parent_to_bone(lower_lip, rig, "head")
    lower_lip["ce_jaw_coupling"] = "soft_viseme_corrective"

    upper_gum = _sphere(
        bpy, "June_Upper_Gum", (0.0, -0.334, 2.508), (0.083, 0.006, 0.009),
        materials["gum"], segments=36, rings=16,
    )
    upper_gum["ce_mouth_component"] = "upper_gum"
    _add_mouth_v7_transform_keys(
        upper_gum,
        lambda source, pose: type(source)((source.x, source.y, source.z - 0.010 * float(pose["upper_teeth"]))),
    )
    _parent_to_bone(upper_gum, rig, "head")

    lower_gum = _sphere(
        bpy, "June_Lower_Gum", (0.0, -0.334, 2.461), (0.076, 0.006, 0.008),
        materials["gum"], segments=36, rings=16,
    )
    lower_gum["ce_mouth_component"] = "lower_gum"
    _add_mouth_v7_transform_keys(
        lower_gum,
        lambda source, pose: type(source)((source.x, source.y, source.z + 0.012 * float(pose["lower_teeth"]))),
    )
    _parent_to_bone(lower_gum, rig, "head")
    lower_gum["ce_jaw_coupling"] = "soft_viseme_corrective"

    # At this stylized close-up scale individual tooth cubes read as beads.
    # Rounded banks preserve one clean dental silhouette; narrow dark grooves
    # provide just enough segmentation to suggest six teeth without visual grit.
    upper_teeth = _box(
        bpy, "June_Upper_Teeth", (0.0, -0.337, 2.503),
        (0.058, 0.0035, 0.0085), materials["teeth"], bevel=0.0060,
    )
    upper_teeth["ce_mouth_component"] = "upper_teeth"
    _add_mouth_v7_transform_keys(
        upper_teeth,
        lambda source, pose: type(source)(
            (
                source.x * (0.86 + 0.14 * float(pose["width"])),
                source.y,
                source.z - 0.013 * float(pose["upper_teeth"]),
            )
        ),
    )
    _parent_to_bone(upper_teeth, rig, "head")

    lower_teeth = _box(
        bpy, "June_Lower_Teeth", (0.0, -0.336, 2.466),
        (0.053, 0.0033, 0.0068), materials["teeth"], bevel=0.0050,
    )
    lower_teeth["ce_mouth_component"] = "lower_teeth"
    _add_mouth_v7_transform_keys(
        lower_teeth,
        lambda source, pose: type(source)(
            (
                source.x * (0.88 + 0.12 * float(pose["width"])),
                source.y,
                source.z + 0.014 * float(pose["lower_teeth"]),
            )
        ),
    )
    _parent_to_bone(lower_teeth, rig, "head")
    lower_teeth["ce_jaw_coupling"] = "soft_viseme_corrective"

    tooth_grooves = []
    for index, x in enumerate((-0.038, -0.019, 0.0, 0.019, 0.038)):
        upper_groove = _box(
            bpy, f"June_Upper_Tooth_Groove_{index}", (x, -0.341, 2.503),
            (0.00065, 0.0008, 0.0062), materials["mouth_interior"], bevel=0.0004,
        )
        upper_groove["ce_mouth_component"] = "upper_tooth_groove"
        _add_mouth_v7_transform_keys(
            upper_groove,
            lambda source, pose: type(source)((source.x, source.y, source.z - 0.013 * float(pose["upper_teeth"]))),
        )
        _parent_to_bone(upper_groove, rig, "head")
        tooth_grooves.append(upper_groove)

        lower_groove = _box(
            bpy, f"June_Lower_Tooth_Groove_{index}", (x * 0.91, -0.340, 2.466),
            (0.00060, 0.0008, 0.0048), materials["mouth_interior"], bevel=0.00035,
        )
        lower_groove["ce_mouth_component"] = "lower_tooth_groove"
        _add_mouth_v7_transform_keys(
            lower_groove,
            lambda source, pose: type(source)((source.x, source.y, source.z + 0.014 * float(pose["lower_teeth"]))),
        )
        _parent_to_bone(lower_groove, rig, "head")
        lower_groove["ce_jaw_coupling"] = "soft_viseme_corrective"
        tooth_grooves.append(lower_groove)

    tongue = _sphere(
        bpy, "June_Tongue", (0.0, -0.334, 2.454), (0.070, 0.010, 0.010),
        materials["tongue"], segments=36, rings=16,
    )
    tongue["ce_mouth_component"] = "tongue"
    _add_mouth_v7_transform_keys(
        tongue,
        lambda source, pose: type(source)(
            (
                source.x * (0.92 + 0.08 * float(pose["width"])),
                source.y - 0.004 * float(pose["tongue"]),
                source.z + 0.020 * float(pose["tongue"]),
            )
        ),
    )
    _parent_to_bone(tongue, rig, "head")
    tongue["ce_jaw_coupling"] = "soft_viseme_corrective"

    components = [
        upper_lip, lower_lip, upper_gum, lower_gum,
        upper_teeth, lower_teeth, *tooth_grooves, tongue,
    ]
    return mouth, components


def _make_june_v7(bpy, mathutils, materials: dict):
    """Hero v7: volumetric mouth anatomy with bounded beard clearance."""
    rig, old_mouth, face_controls = _make_june_v6(bpy, mathutils, materials)
    for name in ("June_Mouth_Lip_Rim", "June_Mouth_Lower_Lip", "June_Upper_Teeth"):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
    if bpy.data.objects.get(old_mouth.name) is not None:
        bpy.data.objects.remove(old_mouth, do_unlink=True)
    mouth, components = _make_mouth_v7(bpy, rig, materials)

    beard = bpy.data.objects.get("June_Fitted_Beard")
    if beard is not None and beard.data.shape_keys is not None:
        beard_keys = beard.data.shape_keys.key_blocks
        basis = beard_keys.get("Basis")
        jaw_follow = beard_keys.get("jaw_follow")
        if basis is not None and jaw_follow is not None:
            for base_point, target in zip(basis.data, jaw_follow.data):
                target.co = base_point.co + (target.co - base_point.co) * 0.38
        clearance = beard.shape_key_add(name="mouth_clearance")
        for source, target in zip(basis.data, clearance.data):
            x, y, z = source.co
            mouth_field = math.exp(-((x / 0.165) ** 2 + ((z - 2.475) / 0.105) ** 2))
            target.co.x += (0.010 if x >= 0.0 else -0.010) * mouth_field
            target.co.y += 0.008 * mouth_field
            target.co.z -= 0.004 * mouth_field
        beard["ce_beard_deformation"] = "bounded_jaw_follow_with_mouth_clearance_v2"

    face_controls["lower_lip"] = next(obj for obj in components if obj.name == "June_Mouth_Lower_Lip")
    face_controls["mouth_components"] = components
    rig["ce_asset_major"] = 7
    rig["ce_control_rig"] = "v6_plus_volumetric_oral_anatomy"
    rig["ce_face_topology"] = "upper_anchored_mouth_bag_contoured_lips_dual_dentition_gums_tongue"
    rig["ce_mouth_components"] = "mouth_bag,upper_lip,lower_lip,upper_gum,lower_gum,upper_teeth,lower_teeth,tongue"
    return rig, mouth, face_controls


def _oral_mask_v8_vertices(pose: dict, *, segments: int = 48):
    """Return a three-ring oral mask fitted from beard/cheek into the aperture.

    The outer two rings are deliberately broad enough to disappear into June's
    fitted beard rather than reading as another floating lip prop.  The inner
    ring retains a true hole so the v7 mouth bag and oral anatomy stay recessed.
    """
    if segments < 12 or segments % 4:
        raise ValueError("oral mask segments must be a multiple of four and at least twelve")
    vertices = []
    opening = float(pose["opening"])
    roundness = float(pose["round"])
    aperture_width = 0.104 * float(pose["width"]) * (1.0 - 0.18 * roundness)
    top_height = 0.0012 + 0.0200 * opening
    bottom_height = 0.0012 + 0.0300 * opening
    upper_lip = 0.0040 + 0.0050 * float(pose["upper_roll"])
    lower_lip = 0.0045 + 0.0055 * float(pose["lower_roll"])
    for ring in range(3):
        for index in range(segments):
            angle = math.tau * index / segments
            horizontal = math.cos(angle)
            vertical = math.sin(angle)
            left_side = horizontal < 0.0
            cheek = float(pose["cheek_l"] if left_side else pose["cheek_r"])
            corner = float(pose["corner_l"] if left_side else pose["corner_r"])
            side_weight = abs(horizontal) ** 3
            corner_weight = abs(horizontal) ** 7
            arch = abs(vertical) ** 0.72
            if ring == 2:
                width = aperture_width
                upper_height = top_height
                lower_height = bottom_height
            elif ring == 1:
                width = aperture_width + 0.0065 + 0.0030 * roundness
                upper_height = top_height + upper_lip
                lower_height = bottom_height + lower_lip
            else:
                # Only a narrow hair-to-lip transition remains visible.  Its
                # edge is planted on the existing fitted beard in depth, which
                # prevents the white clamshell silhouette from the first v8.
                width = aperture_width + 0.020 + 0.005 * cheek
                upper_height = top_height + upper_lip + 0.013
                lower_height = bottom_height + lower_lip + 0.014
            x = width * horizontal * (1.0 + 0.018 * cheek)
            z = (upper_height if vertical >= 0.0 else -lower_height) * arch
            z += (0.006 if ring < 2 else 0.008) * corner * corner_weight
            if ring == 0:
                # June's fitted beard recedes sharply toward the cheeks.  Match
                # that depth field at the outer edge instead of laying a flat
                # annulus over it.
                y = 0.062 + 0.046 * side_weight - 0.004 * cheek
            elif ring == 1:
                y = 0.012 - 0.004 * roundness * arch
            else:
                y = -0.007 - 0.005 * roundness * arch
            vertices.append((x, y, z))
    return vertices


def _make_oral_mask_v8(bpy, materials: dict):
    segments = 48
    vertices = _oral_mask_v8_vertices(MOUTH_V8_POSES["X"], segments=segments)
    faces = []
    material_indices = []
    for ring in range(2):
        for index in range(segments):
            following = (index + 1) % segments
            faces.append(
                (
                    ring * segments + index,
                    ring * segments + following,
                    (ring + 1) * segments + following,
                    (ring + 1) * segments + index,
                )
            )
            material_indices.append(0 if ring == 0 else 1)
    mesh = bpy.data.meshes.new("June_Oral_Mask_Data")
    mesh.from_pydata(vertices, [], faces)
    obj = bpy.data.objects.new("June_Oral_Mask", mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = (0.0, -0.339, 2.490)
    obj.data.materials.append(materials["hair"])
    obj.data.materials.append(materials["lip_soft"])
    for polygon, material_index in zip(obj.data.polygons, material_indices):
        polygon.material_index = material_index
        polygon.use_smooth = True
    obj.shape_key_add(name="Basis")
    for shape, pose in MOUTH_V8_POSES.items():
        key = obj.shape_key_add(name=shape)
        coordinates = _oral_mask_v8_vertices(pose, segments=segments)
        for point, coordinate in zip(key.data, coordinates):
            point.co = coordinate
    solidify = obj.modifiers.new("Oral Mask Soft-Tissue Thickness", "SOLIDIFY")
    solidify.thickness = 0.0045
    solidify.offset = 0.0
    bevel = obj.modifiers.new("Oral Mask Soft Edge", "BEVEL")
    bevel.width = 0.0020
    bevel.segments = 2
    obj["ce_mouth_component"] = "cheek_integrated_oral_mask"
    obj["ce_deformation_model"] = "three_ring_corner_cheek_shape_keys"
    obj["ce_aperture_topology"] = "open_annulus_recessed_oral_anatomy"
    return obj


def _add_mouth_v8_beard_keys(beard) -> None:
    """Put the broad viseme motion into June's fitted beard/muzzle surface."""
    shape_keys = getattr(beard.data, "shape_keys", None)
    if shape_keys is None:
        return
    basis = shape_keys.key_blocks.get("Basis")
    if basis is None:
        return
    source_coordinates = [point.co.copy() for point in basis.data]
    for shape, pose in MOUTH_V8_POSES.items():
        key = shape_keys.key_blocks.get(shape)
        if key is None:
            key = beard.shape_key_add(name=shape)
        for point, source in zip(key.data, source_coordinates):
            x, y, z = source
            mouth_field = math.exp(-((x / 0.180) ** 2 + ((z - 2.485) / 0.115) ** 2))
            corner_field = math.exp(-(((abs(x) - 0.105) / 0.052) ** 2 + ((z - 2.490) / 0.070) ** 2))
            lower_field = max(0.0, min(1.0, (2.500 - z) / 0.145)) * mouth_field
            left_side = x < 0.0
            cheek = float(pose["cheek_l"] if left_side else pose["cheek_r"])
            corner = float(pose["corner_l"] if left_side else pose["corner_r"])
            direction = -1.0 if left_side else 1.0
            width_delta = float(pose["width"]) - 1.0
            point.co.x = x + direction * (
                0.010 * width_delta * mouth_field
                + 0.008 * cheek * corner_field
            )
            point.co.y = y - 0.010 * float(pose["round"]) * mouth_field
            point.co.z = z + 0.013 * corner * corner_field - 0.010 * float(pose["beard_follow"]) * lower_field
    beard["ce_mouth_component"] = "fitted_beard_muzzle_soft_tissue"
    beard["ce_beard_deformation"] = "expression_follow_plus_per_viseme_muzzle_v3"


def _replace_v8_dental_shape_keys(obj, *, upper: bool, groove: bool) -> None:
    """Upgrade v7 dental keys with exposure and groove-visibility controls."""
    shape_keys = getattr(obj.data, "shape_keys", None)
    if shape_keys is None:
        return
    basis = shape_keys.key_blocks.get("Basis")
    if basis is None:
        return
    source_coordinates = [point.co.copy() for point in basis.data]
    for shape, pose in MOUTH_V8_POSES.items():
        key = shape_keys.key_blocks.get(shape)
        if key is None:
            continue
        width = 0.86 + 0.14 * float(pose["width"]) if upper else 0.88 + 0.12 * float(pose["width"])
        travel = -0.013 * float(pose["upper_teeth"]) if upper else 0.014 * float(pose["lower_teeth"])
        exposure = float(pose["dental_exposure"])
        visibility = float(pose["groove_visibility"])
        for point, source in zip(key.data, source_coordinates):
            point.co.x = source.x * width
            point.co.z = source.z * (0.25 + 0.75 * visibility if groove else 0.82 + 0.30 * exposure) + travel
            point.co.y = source.y + (0.012 * (1.0 - visibility) if groove else -0.0015 * exposure)
    obj["ce_dental_visibility"] = "per_viseme_groove_mask" if groove else "per_viseme_exposure"


def _make_june_v8(bpy, mathutils, materials: dict):
    """Hero v8: cheek-integrated oral mask over the proven v7 mouth bag."""
    rig, mouth, face_controls = _make_june_v7(bpy, mathutils, materials)
    for name in ("June_Mouth_Upper_Lip", "June_Mouth_Lower_Lip"):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
    oral_mask = _make_oral_mask_v8(bpy, materials)
    _parent_to_bone(oral_mask, rig, "head")
    beard = bpy.data.objects.get("June_Fitted_Beard")
    if beard is not None:
        _add_mouth_v8_beard_keys(beard)
    for obj in list(mouth.parent.children):
        role = str(obj.get("ce_mouth_component", ""))
        if role in {"upper_teeth", "lower_teeth", "upper_tooth_groove", "lower_tooth_groove"}:
            _replace_v8_dental_shape_keys(
                obj,
                upper=role.startswith("upper"),
                groove=role.endswith("groove"),
            )
    mouth["ce_mouth_rig_version"] = 3
    mouth["ce_mouth_topology"] = "cheek_integrated_oral_mask_over_recessed_mouth_bag_v1"
    face_controls["lower_lip"] = None
    face_controls["oral_mask"] = oral_mask
    face_controls["mouth_components"] = [
        obj for obj in mouth.parent.children
        if obj is not mouth and obj.get("ce_mouth_component")
    ]
    rig["ce_asset_major"] = 8
    rig["ce_control_rig"] = "v7_plus_asymmetric_corner_cheek_oral_mask"
    rig["ce_face_topology"] = "fitted_beard_cheek_oral_annulus_recessed_dentition"
    rig["ce_mouth_components"] = "mouth_bag,oral_mask,upper_gum,lower_gum,upper_teeth,lower_teeth,tongue"
    return rig, mouth, face_controls


def _make_june(bpy, mathutils, materials: dict, *, asset_major: int = 2):
    if asset_major == 1:
        return _make_june_v1(bpy, mathutils, materials)
    if asset_major == 2:
        return _make_june_v2(bpy, mathutils, materials)
    if asset_major == 3:
        return _make_june_v3(bpy, mathutils, materials)
    if asset_major == 4:
        return _make_june_v4(bpy, mathutils, materials)
    if asset_major == 5:
        return _make_june_v5(bpy, mathutils, materials)
    if asset_major == 6:
        return _make_june_v6(bpy, mathutils, materials)
    if asset_major == 7:
        return _make_june_v7(bpy, mathutils, materials)
    if asset_major == 8:
        return _make_june_v8(bpy, mathutils, materials)
    raise ValueError(f"unsupported June asset major version: {asset_major}")


def _cue_text(*values) -> str:
    """Normalize authored direction while preserving a deterministic fallback."""
    text = " ".join(str(value or "") for value in values).lower()
    return " ".join("".join(character if character.isalnum() else " " for character in text).split())


def _cue_signed_value(cue: str, salt: str) -> float:
    """Map free-form direction to a stable value in [-1, 1]."""
    digest = hashlib.sha256(f"{salt}:{cue}".encode("utf-8")).digest()
    integer = int.from_bytes(digest[:4], "big")
    return (integer / 0xFFFFFFFF) * 2.0 - 1.0


def _head_performance_poses(shot: dict, index: int) -> tuple[tuple[float, float], ...]:
    """Return authored start, emphasis, and settle head poses in degrees."""
    cue = _cue_text(shot.get("performance"), shot.get("gesture"))
    turn = 3.0 * _cue_signed_value(cue or str(index), "head-turn")
    nod = 2.2 * _cue_signed_value(cue or str(index), "head-nod")

    if "turn" in cue or "glance" in cue or "look" in cue:
        direction = -1.0 if "left" in cue else 1.0 if "right" in cue else (-1.0 if index % 2 else 1.0)
        turn = 5.0 * direction
    if "eye contact" in cue or "faces camera" in cue:
        turn *= 0.25
    if "nod" in cue:
        nod = 4.5
    elif "leans" in cue or "lean " in f"{cue} ":
        nod = -3.0
    elif "settle" in cue:
        nod = 1.2

    return (
        (-0.20 * turn, -0.15 * nod),
        (turn, nod),
        (0.18 * turn, 0.22 * nod),
    )


def _gesture_pose(shot: dict, index: int) -> dict[str, float]:
    """Translate an authored gesture into bounded degrees for every arm control."""
    cue = _cue_text(shot.get("gesture"), shot.get("performance"))
    presets = {
        "open hand": {
            "upper_arm.L": -18.0, "forearm.L": 12.0, "hand.L": -8.0,
            "upper_arm.R": 8.0, "forearm.R": -5.0, "hand.R": 5.0,
        },
        "measured point": {
            "upper_arm.L": -4.0, "forearm.L": 3.0, "hand.L": -2.0,
            "upper_arm.R": 19.0, "forearm.R": -17.0, "hand.R": 11.0,
        },
        "lean and nod": {
            "upper_arm.L": -9.0, "forearm.L": 7.0, "hand.L": -5.0,
            "upper_arm.R": 10.0, "forearm.R": -6.0, "hand.R": 4.0,
        },
        "shrug": {
            "upper_arm.L": -14.0, "forearm.L": 8.0, "hand.L": -10.0,
            "upper_arm.R": 14.0, "forearm.R": -8.0, "hand.R": 10.0,
        },
        "two handed": {
            "upper_arm.L": -16.0, "forearm.L": 13.0, "hand.L": -8.0,
            "upper_arm.R": 16.0, "forearm.R": -13.0, "hand.R": 8.0,
        },
    }
    for name, pose in presets.items():
        if name in cue:
            return dict(pose)

    # Unknown prose remains useful instead of silently becoming the same stock
    # gesture. SHA-256 keeps the choice stable across machines and Python runs.
    names = ("upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R")
    limits = (14.0, 16.0, 9.0, 14.0, 16.0, 9.0)
    source = cue or f"subtle gesture {index}"
    pose = {
        name: round(limit * _cue_signed_value(source, f"gesture-{name}"), 3)
        for name, limit in zip(names, limits)
    }
    if "left" in cue and "right" not in cue:
        for name in ("upper_arm.R", "forearm.R", "hand.R"):
            pose[name] *= 0.25
    elif "right" in cue and "left" not in cue:
        for name in ("upper_arm.L", "forearm.L", "hand.L"):
            pose[name] *= 0.25
    return pose


def _body_performance_pose(shot: dict, index: int) -> tuple[float, float]:
    """Return a small torso lift and lean (meters, degrees) from direction."""
    cue = _cue_text(shot.get("performance"), shot.get("gesture"))
    lift = 0.006 * _cue_signed_value(cue or str(index), "torso-lift")
    lean = 1.0 * _cue_signed_value(cue or str(index), "torso-lean")
    if "leans toward" in cue or "leans forward" in cue or "lean and nod" in cue:
        return (0.014, -2.8)
    if "leans back" in cue:
        return (-0.005, 2.4)
    if "settle" in cue:
        return (-0.008, 0.6)
    return (lift, lean)


def _leg_performance_pose(shot: dict, index: int) -> dict[str, float]:
    """Translate weight-transfer direction into bounded hip and knee flexion."""
    cue = _cue_text(shot.get("gesture"), shot.get("performance"))
    if "seated to stand" in cue or "stand with mug" in cue:
        return {"thigh.L": -24.0, "shin.L": 31.0, "thigh.R": -22.0, "shin.R": 29.0}
    if "weight transfer" in cue or "step" in cue:
        return {"thigh.L": -11.0, "shin.L": 15.0, "thigh.R": 5.0, "shin.R": -7.0}
    if "settle" in cue or "sit" in cue:
        return {"thigh.L": 8.0, "shin.L": -10.0, "thigh.R": 7.0, "shin.R": -9.0}
    source = cue or f"grounded legs {index}"
    return {
        name: round(limit * _cue_signed_value(source, f"leg-{name}"), 3)
        for name, limit in (
            ("thigh.L", 5.0), ("shin.L", 7.0), ("thigh.R", 5.0), ("shin.R", 7.0)
        )
    }


def _camera_motion_delta(shot: dict, index: int) -> dict[str, tuple[float, float, float]]:
    """Compile an authored camera move into deterministic location/target deltas."""
    cue = _cue_text(shot.get("camera_move")) or "slow push"
    camera = str(shot.get("camera") or "medium")
    push = 0.22 if camera == "wide" else 0.16
    drift = 0.045 * (-1.0 if index % 2 else 1.0)
    location = [0.0, 0.0, 0.0]
    target = [0.0, 0.0, 0.0]

    if "locked" in cue or "static" in cue:
        pass
    elif "pull" in cue or "dolly out" in cue:
        location[1] = -push
    elif "pan left" in cue or "drift left" in cue:
        location[0] = -0.18
    elif "pan right" in cue or "drift right" in cue:
        location[0] = 0.18
    elif "orbit" in cue:
        location[0] = -0.24 if "left" in cue else 0.24
        location[1] = push * 0.35
    elif "tilt up" in cue:
        target[2] = 0.16
    elif "tilt down" in cue:
        target[2] = -0.16
    elif "drift" in cue:
        location[0] = drift
        location[1] = push * 0.35
    else:
        scale = 0.55 if "subtle" in cue else 0.80 if "slow" in cue or "gentle" in cue else 1.0
        location[0] = drift * scale
        location[1] = push * scale
        if not any(word in cue for word in ("push", "dolly", "track")):
            location[0] = 0.08 * _cue_signed_value(cue, "camera-x")
            location[1] = 0.08 * (0.5 + 0.5 * _cue_signed_value(cue, "camera-y"))

    return {"location": tuple(location), "target": tuple(target)}


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


def _golden_pose(shot_id: str, phase: str) -> dict:
    """Return artist-authored v5 control values for one locked acting pose."""
    poses = {
        "GS030": {
            "start": {
                "pelvis": (0.0, 0.0, 0.0), "torso": (-3.0, 0.0), "head": (2.0, -3.0),
                "hand.L": (-0.02, 0.10, -0.03), "hand.R": (-0.05, -0.04, 0.02),
                "gaze": (-0.10, 0.0, -0.02), "clavicle": (-4.0, 2.0), "curl": (22.0, 34.0),
            },
            "mid": {
                "pelvis": (0.0, -0.05, 0.18), "torso": (-11.0, -1.0), "head": (-2.0, 2.0),
                "hand.L": (-0.08, 0.14, -0.08), "hand.R": (-0.10, -0.08, 0.10),
                "gaze": (-0.04, 0.0, 0.02), "clavicle": (-8.0, 3.0), "curl": (28.0, 38.0),
            },
            "end": {
                "pelvis": (0.0, 0.13, 0.43), "torso": (0.5, 0.0), "head": (1.0, 0.0),
                "hand.L": (0.02, 0.06, 0.12), "hand.R": (-0.08, -0.03, 0.22),
                "gaze": (0.02, 0.0, 0.03), "clavicle": (-1.0, 3.0), "curl": (12.0, 40.0),
            },
        },
        "GS040": {
            "start": {
                "pelvis": (0.0, 0.02, 0.06), "torso": (-1.0, 1.0), "head": (3.0, -2.0),
                "hand.L": (0.12, -0.05, 0.04), "hand.R": (-0.10, -0.03, 0.04),
                "gaze": (-0.08, 0.0, -0.02), "clavicle": (-2.0, 2.0), "curl": (12.0, 18.0),
            },
            "mid": {
                "pelvis": (0.0, 0.02, 0.07), "torso": (-3.0, 2.0), "head": (-1.0, 4.0),
                "hand.L": (0.38, -0.13, 0.17), "hand.R": (-0.38, -0.15, 0.20),
                "gaze": (0.02, 0.0, -0.04), "clavicle": (-5.0, 5.0), "curl": (34.0, 30.0),
            },
            "end": {
                "pelvis": (0.0, 0.02, 0.06), "torso": (-1.0, -2.0), "head": (5.0, 7.0),
                "hand.L": (0.35, -0.11, 0.15), "hand.R": (-0.34, -0.12, 0.18),
                "gaze": (0.18, 0.0, -0.03), "clavicle": (-3.0, 4.0), "curl": (38.0, 32.0),
            },
        },
        "GS050": {
            "start": {
                "pelvis": (0.0, 0.02, 0.06), "torso": (-1.0, -1.0), "head": (4.0, 6.0),
                "hand.L": (0.30, -0.10, 0.10), "hand.R": (-0.31, -0.10, 0.13),
                "gaze": (0.14, 0.0, 0.00), "clavicle": (-2.0, 3.0), "curl": (34.0, 30.0),
            },
            "mid": {
                "pelvis": (0.0, 0.02, 0.05), "torso": (-2.0, 0.0), "head": (7.0, 2.0),
                "hand.L": (0.28, -0.09, 0.08), "hand.R": (-0.30, -0.09, 0.11),
                "gaze": (0.10, 0.0, -0.14), "clavicle": (-4.0, 1.0), "curl": (32.0, 28.0),
            },
            "end": {
                "pelvis": (0.0, 0.02, 0.04), "torso": (-1.5, 0.0), "head": (10.0, -2.0),
                "hand.L": (0.28, -0.09, 0.08), "hand.R": (-0.30, -0.09, 0.11),
                "gaze": (0.06, 0.0, -0.22), "clavicle": (-5.0, 0.0), "curl": (30.0, 27.0),
            },
        },
    }
    hand_roles = {
        "GS030": {
            "start": ("chair_support", "mug_grip"),
            "mid": ("chair_support", "mug_grip"),
            "end": ("relaxed", "mug_grip"),
        },
        "GS040": {
            "start": ("open_empathy", "relaxed"),
            "mid": ("ledger_support", "pencil_tripod"),
            "end": ("ledger_support", "pencil_tripod"),
        },
        "GS050": {
            "start": ("ledger_support", "pencil_tripod"),
            "mid": ("relaxed", "relaxed"),
            "end": ("open_empathy", "relaxed"),
        },
    }
    try:
        pose = dict(poses[shot_id][phase])
        left_role, right_role = hand_roles[shot_id][phase]
        pose["digits.L"] = _hand_pose_vector(left_role)
        pose["digits.R"] = _hand_pose_vector(right_role)
        pose["hand_role.L"] = left_role
        pose["hand_role.R"] = right_role
        return pose
    except KeyError as exc:
        raise ValueError(f"unsupported Golden Scene pose: {shot_id}/{phase}") from exc


def _tuple_blend(start, target, amount: float):
    return tuple(float(left) + (float(right) - float(left)) * amount for left, right in zip(start, target))


def _golden_pose_between(start: dict, target: dict, amount: float, polish: dict) -> dict:
    gaze_amount = amount
    clavicle_amount = amount
    if 0.0 < amount < 1.0:
        gaze_amount = min(1.0, amount + float(polish["gaze_lead"]))
        clavicle_amount = max(0.0, amount - float(polish["clavicle_lag"]))
    arc = 0.0
    if 0.0 < amount < 1.0:
        arc = float(polish["arc_height"]) * 4.0 * amount * (1.0 - amount)
    pelvis = list(_tuple_blend(start["pelvis"], target["pelvis"], amount))
    hand_l = list(_tuple_blend(start["hand.L"], target["hand.L"], amount))
    hand_r = list(_tuple_blend(start["hand.R"], target["hand.R"], amount))
    head = list(_tuple_blend(start["head"], target["head"], amount))
    pelvis[2] += arc
    hand_l[2] += arc * 0.55
    hand_r[2] += arc * 0.55
    head[0] -= arc * 45.0
    return {
        "pelvis": tuple(pelvis),
        "torso": _tuple_blend(start["torso"], target["torso"], amount),
        "head": tuple(head),
        "hand.L": tuple(hand_l),
        "hand.R": tuple(hand_r),
        "gaze": _tuple_blend(start["gaze"], target["gaze"], gaze_amount),
        "clavicle": _tuple_blend(start["clavicle"], target["clavicle"], clavicle_amount),
        "curl": _tuple_blend(start["curl"], target["curl"], amount),
        "digits.L": _tuple_blend(start["digits.L"], target["digits.L"], amount),
        "digits.R": _tuple_blend(start["digits.R"], target["digits.R"], amount),
        "hand_role.L": target["hand_role.L"] if amount >= 0.5 else start["hand_role.L"],
        "hand_role.R": target["hand_role.R"] if amount >= 0.5 else start["hand_role.R"],
    }


def _golden_polish_keys(shot_id: str, keyframes: list[dict], polish: dict) -> list[dict]:
    """Expand approved poses into deterministic acting beats without moving them."""
    authored = [
        {
            "frame": int(keyframe["frame"]),
            "role": f"authored_{keyframe['phase']}",
            "pose": _golden_pose(shot_id, str(keyframe["phase"])),
        }
        for keyframe in keyframes
    ]
    if not polish.get("enabled"):
        return authored
    result = {entry["frame"]: entry for entry in authored}
    for index, (start, target) in enumerate(zip(authored, authored[1:])):
        start_frame = int(start["frame"])
        target_frame = int(target["frame"])
        arrival_frame = target_frame
        if shot_id == "GS050" and index == len(authored) - 2:
            arrival_frame = target_frame - int(polish["final_hold_frames"])
        span = arrival_frame - start_frame
        if span < 16:
            continue
        hold_frame = start_frame + int(polish["hold_frames"])
        anticipation_frame = hold_frame + int(polish["anticipation_frames"])
        breakdown_frame = start_frame + round(span * float(polish["breakdown_fraction"]))
        overshoot_frame = arrival_frame - int(polish["settle_frames"])
        candidates = (
            (hold_frame, "held_start", start["pose"]),
            (
                anticipation_frame,
                "anticipation",
                _golden_pose_between(start["pose"], target["pose"], -float(polish["anticipation_ratio"]), polish),
            ),
            (
                breakdown_frame,
                "arced_breakdown",
                _golden_pose_between(
                    start["pose"], target["pose"], float(polish["breakdown_fraction"]), polish
                ),
            ),
            (
                overshoot_frame,
                "restrained_overshoot",
                _golden_pose_between(start["pose"], target["pose"], 1.0 + float(polish["overshoot_ratio"]), polish),
            ),
            (arrival_frame, "settle", target["pose"]),
        )
        for frame, role, pose in candidates:
            if start_frame < frame < target_frame:
                result[int(frame)] = {"frame": int(frame), "role": role, "pose": pose}
    return [result[frame] for frame in sorted(result)]


def _animate_phase13_microperformance(bpy, rig, plan: dict, polish: dict) -> None:
    """Layer breath, gaze lead, and controlled stillness additively over poses."""
    if not polish.get("enabled"):
        return
    frame_end = int(plan["frame_end"])
    acting = (plan.get("look_profile") or {}).get("acting_polish") or {}
    hold_start = frame_end - int(acting.get("final_hold_frames", 24))
    breath_period = max(24, int(polish.get("breath_period_frames", 72)))
    breath_amplitude = float(polish.get("breath_amplitude", 0.0045))
    gaze_amplitude = float(polish.get("saccade_amplitude", 0.009))
    gaze_lead = max(1, int(polish.get("gaze_lead_frames", 4)))
    gaze_settle = max(1, int(polish.get("gaze_settle_frames", 3)))

    def microperformance():
        torso = rig.pose.bones["torso"]
        head = rig.pose.bones["head"]
        gaze = rig.pose.bones["gaze"]
        clavicle_l = rig.pose.bones["clavicle.L"]
        clavicle_r = rig.pose.bones["clavicle.R"]

        half_period = max(12, breath_period // 2)
        for frame in range(1, max(2, hold_start), half_period):
            phase = (frame // half_period) % 2
            lift = breath_amplitude if phase else -breath_amplitude * 0.55
            torso.location = (0.0, 0.0, lift)
            head.rotation_euler = (math.radians(-0.22 if phase else 0.12), 0.0, 0.0)
            clavicle_l.rotation_euler = (0.0, 0.0, math.radians(0.28 if phase else -0.15))
            clavicle_r.rotation_euler = (0.0, 0.0, math.radians(-0.24 if phase else 0.13))
            torso.keyframe_insert(data_path="location", frame=frame)
            head.keyframe_insert(data_path="rotation_euler", frame=frame)
            clavicle_l.keyframe_insert(data_path="rotation_euler", frame=frame)
            clavicle_r.keyframe_insert(data_path="rotation_euler", frame=frame)

        # Gaze anticipates each meaningful facial change, then returns to the
        # authored target.  Hash-derived polarity preserves asymmetry without
        # random or frame-to-frame noise.
        for cue in (plan.get("facial_performance_cues") or [])[1:]:
            center = int(cue["frame_start"])
            if center >= hold_start:
                continue
            polarity = _cue_signed_value(str(cue.get("expression")), f"micro-gaze-{center}")
            for frame, blend in (
                (max(1, center - gaze_lead), 0.0),
                (center, 1.0),
                (min(hold_start, center + gaze_settle), 0.0),
            ):
                gaze.location = (
                    gaze_amplitude * polarity * blend,
                    0.0,
                    gaze_amplitude * -0.42 * blend,
                )
                gaze.keyframe_insert(data_path="location", frame=frame)

        for frame in (hold_start, frame_end):
            torso.location = (0.0, 0.0, 0.0)
            head.rotation_euler = (0.0, 0.0, 0.0)
            gaze.location = (0.0, 0.0, 0.0)
            clavicle_l.rotation_euler = (0.0, 0.0, 0.0)
            clavicle_r.rotation_euler = (0.0, 0.0, 0.0)
            for bone, path in (
                (torso, "location"), (head, "rotation_euler"), (gaze, "location"),
                (clavicle_l, "rotation_euler"), (clavicle_r, "rotation_euler"),
            ):
                bone.keyframe_insert(data_path=path, frame=frame)

        action = rig.animation_data.action
        if action:
            for curve in action.fcurves:
                for point in curve.keyframe_points:
                    point.interpolation = "BEZIER"
                    point.handle_left_type = "AUTO_CLAMPED"
                    point.handle_right_type = "AUTO_CLAMPED"

    _stash_action(bpy, rig, "June_Micro_Performance_v1", microperformance)


def _animate_golden_performance(bpy, rig, plan: dict) -> None:
    """Drive the v5 production controls on the exact phase-8 453-frame clock."""
    frame_end = int(plan["frame_end"])
    rig.animation_data_create()
    for track in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(track)
    rig.animation_data.action = None

    def performance():
        pelvis = rig.pose.bones["pelvis"]
        torso = rig.pose.bones["torso"]
        head = rig.pose.bones["head"]
        gaze = rig.pose.bones["gaze"]
        clavicle_l = rig.pose.bones["clavicle.L"]
        clavicle_r = rig.pose.bones["clavicle.R"]
        hand_l = rig.pose.bones["hand_ik.L"]
        hand_r = rig.pose.bones["hand_ik.R"]
        feet = (rig.pose.bones["foot_ik.L"], rig.pose.bones["foot_ik.R"])
        fingers_l = [rig.pose.bones[f"finger.{index}.L"] for index in range(4)] + [rig.pose.bones["thumb.L"]]
        fingers_r = [rig.pose.bones[f"finger.{index}.R"] for index in range(4)] + [rig.pose.bones["thumb.R"]]
        distal_l = (
            [rig.pose.bones[f"finger_tip.{index}.L"] for index in range(4)] + [rig.pose.bones["thumb_tip.L"]]
            if rig.pose.bones.get("finger_tip.0.L") else []
        )
        distal_r = (
            [rig.pose.bones[f"finger_tip.{index}.R"] for index in range(4)] + [rig.pose.bones["thumb_tip.R"]]
            if rig.pose.bones.get("finger_tip.0.R") else []
        )

        for side in ("L", "R"):
            for owner_name, constraint_name in (
                (f"forearm.{side}", f"CE_Arm_IK_{side}"),
                (f"shin.{side}", f"CE_Leg_IK_{side}"),
            ):
                constraint = rig.pose.bones[owner_name].constraints[constraint_name]
                constraint.influence = 1.0
                constraint.keyframe_insert(data_path="influence", frame=1)
                constraint.keyframe_insert(data_path="influence", frame=frame_end)

        for foot in feet:
            foot.location = (0.0, 0.0, 0.0)
            foot.keyframe_insert(data_path="location", frame=1)
            foot.keyframe_insert(data_path="location", frame=frame_end)

        acting_polish = (plan.get("look_profile") or {}).get("acting_polish") or {}
        for shot in plan["shots"]:
            shot_id = str(shot["id"])
            performance_keys = _golden_polish_keys(
                shot_id,
                shot.get("performance_keyframes") or [],
                acting_polish,
            )
            for keyframe in performance_keys:
                frame = int(keyframe["frame"])
                pose = keyframe["pose"]
                pelvis.location = pose["pelvis"]
                pelvis.keyframe_insert(data_path="location", frame=frame)
                torso.rotation_euler = (math.radians(pose["torso"][0]), math.radians(pose["torso"][1]), 0.0)
                torso.keyframe_insert(data_path="rotation_euler", frame=frame)
                head.rotation_euler = (math.radians(pose["head"][0]), 0.0, math.radians(pose["head"][1]))
                head.keyframe_insert(data_path="rotation_euler", frame=frame)
                clavicle_l.rotation_euler[2] = math.radians(pose["clavicle"][0])
                clavicle_r.rotation_euler[2] = math.radians(pose["clavicle"][1])
                clavicle_l.keyframe_insert(data_path="rotation_euler", frame=frame)
                clavicle_r.keyframe_insert(data_path="rotation_euler", frame=frame)
                hand_l.location = pose["hand.L"]
                hand_r.location = pose["hand.R"]
                hand_l.keyframe_insert(data_path="location", frame=frame)
                hand_r.keyframe_insert(data_path="location", frame=frame)
                gaze.location = pose["gaze"]
                gaze.keyframe_insert(data_path="location", frame=frame)
                if distal_l and distal_r:
                    for side, proximal, distal, values in (
                        ("L", fingers_l, distal_l, pose["digits.L"]),
                        ("R", fingers_r, distal_r, pose["digits.R"]),
                    ):
                        spread_sign = -1.0 if side == "L" else 1.0
                        for digit, (near, far) in enumerate(zip(proximal, distal)):
                            proximal_angle, distal_angle, spread = values[digit * 3 : digit * 3 + 3]
                            near.rotation_euler = (
                                math.radians(proximal_angle), 0.0,
                                math.radians(spread * spread_sign),
                            )
                            far.rotation_euler = (math.radians(distal_angle), 0.0, 0.0)
                            near.keyframe_insert(data_path="rotation_euler", frame=frame)
                            far.keyframe_insert(data_path="rotation_euler", frame=frame)
                else:
                    for finger in fingers_l:
                        finger.rotation_euler[0] = math.radians(pose["curl"][0])
                        finger.keyframe_insert(data_path="rotation_euler", frame=frame)
                    for finger in fingers_r:
                        finger.rotation_euler[0] = math.radians(pose["curl"][1])
                        finger.keyframe_insert(data_path="rotation_euler", frame=frame)

        jaw = rig.pose.bones["jaw"]
        jaw_open = {"A": 9.0, "B": 13.0, "C": 5.0, "D": 10.0, "E": 4.0, "F": 7.0, "G": 12.0, "H": 8.0, "X": 0.0}
        for cue in plan.get("mouth_cues") or []:
            start = int(cue["frame_start"])
            end = int(cue["frame_end"])
            degrees = jaw_open[str(cue["shape"])]
            jaw.rotation_euler[0] = math.radians(degrees)
            jaw.keyframe_insert(data_path="rotation_euler", frame=start)
            jaw.keyframe_insert(data_path="rotation_euler", frame=end)

        action = rig.animation_data.action
        if action:
            for curve in action.fcurves:
                for point in curve.keyframe_points:
                    point.interpolation = "BEZIER"
                    point.handle_left_type = "AUTO_CLAMPED"
                    point.handle_right_type = "AUTO_CLAMPED"

    action_name = "June_Golden_Performance_v2_Polished" if (plan.get("look_profile") or {}).get("acting_polish") else "June_Golden_Performance_v1"
    _stash_action(bpy, rig, action_name, performance)
    facial_polish = (plan.get("look_profile") or {}).get("facial_polish") or {}
    _animate_phase13_microperformance(bpy, rig, plan, facial_polish)


def _animate_performance_props(bpy, plan: dict) -> None:
    if plan.get("performance_contract") != "june_golden_scene_performance_v1":
        return
    visibility = {
        "held_mug": {"GS030"},
        "table_mug": {"GS040", "GS050"},
        "ledger": {"GS040", "GS050"},
        "pencil": {"GS040", "GS050"},
    }
    props = [obj for obj in bpy.context.scene.objects if obj.get("ce_prop_role")]
    for shot in plan["shots"]:
        start = int(shot["frame_start"])
        end = int(shot["frame_end"])
        shot_id = str(shot["id"])
        for obj in props:
            visible = shot_id in visibility.get(str(obj["ce_prop_role"]), set())
            obj.hide_render = not visible
            obj.hide_viewport = not visible
            obj.keyframe_insert(data_path="hide_render", frame=start)
            obj.keyframe_insert(data_path="hide_render", frame=end)
            obj.keyframe_insert(data_path="hide_viewport", frame=start)
            obj.keyframe_insert(data_path="hide_viewport", frame=end)
        for obj in (item for item in bpy.context.scene.objects if item.name.startswith("Chair_")):
            visible = shot_id == "GS030"
            obj.hide_render = not visible
            obj.hide_viewport = not visible
            obj.keyframe_insert(data_path="hide_render", frame=start)
            obj.keyframe_insert(data_path="hide_render", frame=end)
            obj.keyframe_insert(data_path="hide_viewport", frame=start)
            obj.keyframe_insert(data_path="hide_viewport", frame=end)


def _animate_rig(bpy, rig, plan: dict) -> None:
    if plan.get("performance_contract") == "june_golden_scene_performance_v1":
        _animate_golden_performance(bpy, rig, plan)
        return
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
    hand_l = rig.pose.bones["hand.L"]
    upper_r = rig.pose.bones["upper_arm.R"]
    fore_r = rig.pose.bones["forearm.R"]
    hand_r = rig.pose.bones["hand.R"]
    thigh_l = rig.pose.bones["thigh.L"]
    shin_l = rig.pose.bones["shin.L"]
    thigh_r = rig.pose.bones["thigh.R"]
    shin_r = rig.pose.bones["shin.R"]

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
        poses = [(1, 0.0, 0.0)]
        for index, shot in enumerate(plan["shots"]):
            start = int(shot["frame_start"])
            end = int(shot["frame_end"])
            midpoint = (start + end) // 2
            authored = _head_performance_poses(shot, index)
            poses.extend((frame, turn, nod) for frame, (turn, nod) in zip((start, midpoint, end), authored))
        for frame, turn, nod in poses:
            head.rotation_euler[2] = math.radians(turn)
            head.rotation_euler[0] = math.radians(nod)
            head.keyframe_insert(data_path="rotation_euler", frame=frame)

    def gestures():
        gesture_bones = {
            "upper_arm.L": upper_l,
            "forearm.L": fore_l,
            "hand.L": hand_l,
            "upper_arm.R": upper_r,
            "forearm.R": fore_r,
            "hand.R": hand_r,
            "thigh.L": thigh_l,
            "shin.L": shin_l,
            "thigh.R": thigh_r,
            "shin.R": shin_r,
        }
        for bone in gesture_bones.values():
            bone.rotation_euler = (0, 0, 0)
            bone.keyframe_insert(data_path="rotation_euler", frame=1)
        torso.location.z = 0.0
        torso.rotation_euler[1] = 0.0
        torso.keyframe_insert(data_path="location", frame=1)
        torso.keyframe_insert(data_path="rotation_euler", frame=1)
        for index, shot in enumerate(plan["shots"]):
            start = int(shot["frame_start"])
            end = int(shot["frame_end"])
            midpoint = (start + end) // 2
            pose = {**_gesture_pose(shot, index), **_leg_performance_pose(shot, index)}
            lift, lean = _body_performance_pose(shot, index)
            for frame, strength in ((start, 0.0), (midpoint, 1.0), (end, 0.18)):
                for name, bone in gesture_bones.items():
                    degrees = pose[name] * strength
                    if name.startswith(("thigh.", "shin.")):
                        bone.rotation_euler = (math.radians(degrees), 0.0, math.radians(degrees * 0.08))
                    else:
                        bone.rotation_euler = (0.0, math.radians(degrees), math.radians(degrees * 0.35))
                    bone.keyframe_insert(data_path="rotation_euler", frame=frame)
                torso.location.z = lift * strength
                torso.rotation_euler[1] = math.radians(lean * strength)
                torso.keyframe_insert(data_path="location", frame=frame)
                torso.keyframe_insert(data_path="rotation_euler", frame=frame)

    _stash_action(bpy, rig, "June_Breathing_Idle", breathing)
    _stash_action(bpy, rig, "June_Head_Performance", head_performance)
    _stash_action(bpy, rig, "June_Gesture_Performance", gestures)


def _animate_mouth(mouth, plan: dict) -> None:
    if mouth.data.shape_keys.animation_data:
        mouth.data.shape_keys.animation_data_clear()
    keys = mouth.data.shape_keys.key_blocks
    shapes = tuple("ABCDEFGHX")
    mouth_rig_version = int(mouth.get("ce_mouth_rig_version", 1))
    volumetric = mouth_rig_version >= 2
    pose_table = MOUTH_V8_POSES if mouth_rig_version >= 3 else MOUTH_V7_POSES
    mouth_components = [
        obj for obj in mouth.parent.children
        if obj is not mouth and obj.get("ce_mouth_component")
    ]
    if volumetric:
        for component in mouth_components:
            shape_keys = getattr(component.data, "shape_keys", None)
            if shape_keys is not None and shape_keys.animation_data:
                shape_keys.animation_data_clear()
    lip_rim = next(
        (obj for obj in mouth.parent.children if obj.name == "June_Mouth_Lip_Rim"),
        None,
    )
    lower_lip = next(
        (obj for obj in mouth.parent.children if obj.name == "June_Mouth_Lower_Lip"),
        None,
    )
    beard = next(
        (obj for obj in mouth.parent.children if obj.name == "June_Fitted_Beard"),
        None,
    )
    if lip_rim is not None and lip_rim.animation_data:
        lip_rim.animation_data_clear()
    if lower_lip is not None and lower_lip.animation_data:
        lower_lip.animation_data_clear()
    lip_base = lip_rim.scale.copy() if lip_rim is not None else None
    lower_lip_base = lower_lip.scale.copy() if lower_lip is not None else None
    beard_keys = (
        beard.data.shape_keys.key_blocks
        if beard is not None and beard.data.shape_keys is not None else None
    )
    if beard_keys is not None and beard.data.shape_keys.animation_data:
        beard.data.shape_keys.animation_data_clear()
    cues = plan.get("mouth_cues") or [{"frame_start": 1, "frame_end": plan["frame_end"], "shape": "X"}]
    lip_contract = plan.get("lip_sync_contract") or {}
    transition_frames = max(0, int(lip_contract.get("transition_frames", 0)))
    jaw_follow = {"A": 0.68, "B": 1.0, "C": 0.34, "D": 0.76, "E": 0.28, "F": 0.48, "G": 0.92, "H": 0.60, "X": 0.0}

    def key_state(frame: int, active: str) -> None:
        for shape in shapes:
            keys[shape].value = 1.0 if shape == active else 0.0
            keys[shape].keyframe_insert(data_path="value", frame=frame)
        if volumetric:
            for component in mouth_components:
                component_keys = getattr(component.data, "shape_keys", None)
                if component_keys is None:
                    continue
                for shape in shapes:
                    component_keys.key_blocks[shape].value = 1.0 if shape == active else 0.0
                    component_keys.key_blocks[shape].keyframe_insert(data_path="value", frame=frame)
        elif lip_rim is not None and active in MOUTH_V5_SHAPE_SCALE:
            width, height = MOUTH_V5_SHAPE_SCALE[active]
            lip_rim.scale = lip_base.copy()
            lip_rim.scale.x *= width
            lip_rim.scale.z *= max(0.58, 0.42 + height * 0.34)
            lip_rim.keyframe_insert(data_path="scale", frame=frame)
            if lower_lip is not None:
                lower_lip.scale = lower_lip_base.copy()
                lower_lip.scale.x *= width
                lower_lip.scale.z *= max(0.52, height * 0.72)
                lower_lip.keyframe_insert(data_path="scale", frame=frame)
        if beard_keys is not None and beard_keys.get("jaw_follow") is not None:
            follow = (
                float(pose_table[active]["beard_follow"])
                if volumetric else jaw_follow.get(active, 0.0)
            )
            beard_keys["jaw_follow"].value = follow
            beard_keys["jaw_follow"].keyframe_insert(data_path="value", frame=frame)
            if volumetric and beard_keys.get("mouth_clearance") is not None:
                beard_keys["mouth_clearance"].value = min(0.55, float(pose_table[active]["opening"]) * 0.48)
                beard_keys["mouth_clearance"].keyframe_insert(data_path="value", frame=frame)

    for index, cue in enumerate(cues):
        frame = int(cue["frame_start"])
        active = str(cue["shape"])
        if index and transition_frames:
            previous = cues[index - 1]
            anticipation_frame = max(int(previous["frame_start"]), frame - transition_frames)
            if anticipation_frame < frame:
                key_state(anticipation_frame, str(previous["shape"]))
        key_state(frame, active)
    final_frame = int(plan["frame_end"])
    for shape in shapes:
        keys[shape].value = 1.0 if shape == "X" else 0.0
        keys[shape].keyframe_insert(data_path="value", frame=final_frame)
    if volumetric:
        for component in mouth_components:
            component_keys = getattr(component.data, "shape_keys", None)
            if component_keys is None:
                continue
            for shape in shapes:
                component_keys.key_blocks[shape].value = 1.0 if shape == "X" else 0.0
                component_keys.key_blocks[shape].keyframe_insert(data_path="value", frame=final_frame)
    elif lip_rim is not None:
        width, height = MOUTH_V5_SHAPE_SCALE["X"]
        lip_rim.scale = lip_base.copy()
        lip_rim.scale.x *= width
        lip_rim.scale.z *= max(0.58, 0.42 + height * 0.34)
        lip_rim.keyframe_insert(data_path="scale", frame=final_frame)
    if lower_lip is not None and not volumetric:
        width, height = MOUTH_V5_SHAPE_SCALE["X"]
        lower_lip.scale = lower_lip_base.copy()
        lower_lip.scale.x *= width
        lower_lip.scale.z *= max(0.52, height * 0.72)
        lower_lip.keyframe_insert(data_path="scale", frame=final_frame)
    if beard_keys is not None and beard_keys.get("jaw_follow") is not None:
        beard_keys["jaw_follow"].value = 0.0
        beard_keys["jaw_follow"].keyframe_insert(data_path="value", frame=final_frame)
        if volumetric and beard_keys.get("mouth_clearance") is not None:
            beard_keys["mouth_clearance"].value = 0.0
            beard_keys["mouth_clearance"].keyframe_insert(data_path="value", frame=final_frame)
    action = mouth.data.shape_keys.animation_data.action
    interpolation = "LINEAR" if transition_frames else "CONSTANT"
    for curve in action.fcurves:
        for point in curve.keyframe_points:
            point.interpolation = interpolation
    if lip_rim is not None and lip_rim.animation_data and lip_rim.animation_data.action:
        for curve in lip_rim.animation_data.action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = interpolation
    if lower_lip is not None and lower_lip.animation_data and lower_lip.animation_data.action:
        for curve in lower_lip.animation_data.action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = interpolation
    if beard_keys is not None and beard.data.shape_keys.animation_data and beard.data.shape_keys.animation_data.action:
        for curve in beard.data.shape_keys.animation_data.action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = interpolation


def _animate_expressions(head, plan: dict, face_controls: dict | None = None) -> None:
    """Layer readable acting beats independently from phoneme mouth shapes."""
    if head.data.shape_keys.animation_data:
        head.data.shape_keys.animation_data_clear()
    keys = head.data.shape_keys.key_blocks
    controls = tuple(
        name
        for name in (
            "smile", "thoughtful", "soft_chuckle", "brow_raise", "brow_knit", "squint", "cheek_raise",
            *FACIAL_V6_CORRECTIVES,
        )
        if keys.get(name) is not None
    )
    if face_controls:
        for obj in (
            (face_controls.get("brows") or [])
            + (face_controls.get("upper_lids") or [])
            + (face_controls.get("lower_lids") or [])
            + (face_controls.get("moustache") or [])
        ):
            if obj.animation_data:
                obj.animation_data_clear()
    facial_cues = plan.get("facial_performance_cues") or []
    if facial_cues:
        brows = (face_controls.get("brows") or []) if face_controls else []
        upper_lids = (face_controls.get("upper_lids") or []) if face_controls else []
        lower_lids = (face_controls.get("lower_lids") or []) if face_controls else []
        moustache = (face_controls.get("moustache") or []) if face_controls else []
        beard = face_controls.get("beard") if face_controls else None
        brow_bases = [(brow.location.copy(), brow.rotation_euler.copy()) for brow in brows]
        upper_bases = [lid.location.copy() for lid in upper_lids]
        lower_bases = [lid.location.copy() for lid in lower_lids]
        moustache_bases = [(item.location.copy(), item.scale.copy()) for item in moustache]
        facial_polish = (plan.get("look_profile") or {}).get("facial_polish") or {}
        performance_keys = _facial_polish_keys(facial_cues, int(plan["frame_end"]), facial_polish)
        beard_keys = (
            beard.data.shape_keys.key_blocks
            if beard is not None and beard.data.shape_keys is not None else None
        )
        for cue in performance_keys:
            active = str(cue.get("expression"))
            strength = float(cue.get("strength", 1.0))
            weights = cue.get("weights") or _facial_driver_weights(active, strength)
            frame = int(cue["frame"])
            for control in controls:
                keys[control].value = float(weights.get(control, 0.0))
                keys[control].keyframe_insert(data_path="value", frame=frame)
            smile = float(weights.get("smile", 0.0))
            thoughtful = float(weights.get("thoughtful", 0.0))
            chuckle = float(weights.get("soft_chuckle", 0.0))
            brow_raise = float(weights.get("brow_raise", 0.0))
            brow_knit = float(weights.get("brow_knit", 0.0))
            squint = float(weights.get("squint", 0.0))
            cheek = float(weights.get("cheek_raise", 0.0))
            inner_raise = float(weights.get("inner_brow_raise", 0.0))
            lower_engage = float(weights.get("lower_lid_engage", 0.0))
            for index, brow in enumerate(brows):
                base_location, base_rotation = brow_bases[index]
                brow.location = base_location.copy()
                brow.rotation_euler = base_rotation.copy()
                brow.location.z += (
                    0.006 * smile + 0.003 * thoughtful + 0.010 * chuckle
                    + 0.034 * brow_raise - 0.006 * brow_knit - 0.004 * squint
                    + 0.012 * cheek + 0.018 * inner_raise
                )
                brow.location.z += (0.010 if index == 0 else -0.006) * thoughtful
                brow.location.x += (0.007 if index == 0 else -0.007) * brow_knit
                brow.rotation_euler[1] += math.radians(
                    (-6.0 if index == 0 else 4.0) * thoughtful
                    + (5.0 if index == 0 else -5.0) * brow_knit
                )
                brow.keyframe_insert(data_path="location", frame=frame)
                brow.keyframe_insert(data_path="rotation_euler", frame=frame)
            upper_drop = 0.003 * smile + 0.014 * chuckle + 0.026 * squint + 0.012 * cheek
            lower_raise = 0.002 * smile + 0.007 * chuckle + 0.011 * squint + 0.008 * cheek + 0.016 * lower_engage
            for index, upper in enumerate(upper_lids):
                upper.location = upper_bases[index].copy()
                upper.location.z -= upper_drop
                upper.keyframe_insert(data_path="location", frame=frame)
            for index, lower in enumerate(lower_lids):
                lower.location = lower_bases[index].copy()
                lower.location.z += lower_raise
                lower.keyframe_insert(data_path="location", frame=frame)
            if beard_keys is not None:
                beard_values = {
                    "smile_follow": max(smile, chuckle * 0.9),
                    "thoughtful_follow": thoughtful,
                    "cheek_follow": max(cheek, lower_engage * 0.55),
                }
                for name, value in beard_values.items():
                    if beard_keys.get(name) is not None:
                        beard_keys[name].value = min(1.0, value)
                        beard_keys[name].keyframe_insert(data_path="value", frame=frame)
            for index, item in enumerate(moustache):
                base_location, base_scale = moustache_bases[index]
                side_corner = float(weights.get("mouth_corner.L" if index == 0 else "mouth_corner.R", 0.0))
                item.location = base_location.copy()
                item.scale = base_scale.copy()
                item.location.z += 0.010 * side_corner - 0.004 * thoughtful
                item.location.x += (-0.004 if index == 0 else 0.004) * side_corner
                item.scale.x *= 1.0 + 0.025 * max(smile, chuckle)
                item.keyframe_insert(data_path="location", frame=frame)
                item.keyframe_insert(data_path="scale", frame=frame)
        action = head.data.shape_keys.animation_data.action
        eased = bool(facial_polish.get("enabled"))
        for curve in action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "BEZIER" if eased else "CONSTANT"
                if eased:
                    point.handle_left_type = "AUTO_CLAMPED"
                    point.handle_right_type = "AUTO_CLAMPED"
        for obj in brows + upper_lids + lower_lids + moustache:
            if obj.animation_data and obj.animation_data.action:
                for curve in obj.animation_data.action.fcurves:
                    for point in curve.keyframe_points:
                        point.interpolation = "BEZIER" if eased else "CONSTANT"
                        if eased:
                            point.handle_left_type = "AUTO_CLAMPED"
                            point.handle_right_type = "AUTO_CLAMPED"
        if beard_keys is not None and beard.data.shape_keys.animation_data and beard.data.shape_keys.animation_data.action:
            for curve in beard.data.shape_keys.animation_data.action.fcurves:
                for point in curve.keyframe_points:
                    point.interpolation = "BEZIER" if eased else "LINEAR"
                    if eased:
                        point.handle_left_type = "AUTO_CLAMPED"
                        point.handle_right_type = "AUTO_CLAMPED"
        return
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
    if plan.get("performance_contract") == "june_golden_scene_performance_v1":
        presets["close"] = ((0.02, -2.65, 2.70), 68, (0.0, -0.06, 2.58))
    elif plan.get("facial_performance_cues"):
        presets["close"] = ((0.02, -1.72, 2.70), 82, (0.0, -0.08, 2.66))
    scene = bpy.context.scene
    for index, shot in enumerate(plan["shots"]):
        preset = presets[shot["camera"]]
        base_target = preset[2]
        data = bpy.data.cameras.new(f"Camera_{shot['id']}")
        data.lens = preset[1]
        data.dof.use_dof = False
        camera = bpy.data.objects.new(f"Camera_{shot['id']}", data)
        bpy.context.collection.objects.link(camera)
        camera.location = preset[0]
        _look_at(camera, base_target, mathutils)
        start = int(shot["frame_start"])
        end = int(shot["frame_end"])
        camera.keyframe_insert(data_path="location", frame=start)
        camera.keyframe_insert(data_path="rotation_euler", frame=start)
        move = _camera_motion_delta(shot, index)
        for axis, delta in enumerate(move["location"]):
            camera.location[axis] += delta
        end_target = tuple(value + move["target"][axis] for axis, value in enumerate(base_target))
        _look_at(camera, end_target, mathutils)
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


def _look_light(plan: dict, role: str, fallback: tuple) -> tuple:
    lighting = (plan.get("look_profile") or {}).get("lighting") or {}
    spec = lighting.get(role) or {}
    return (
        float(spec.get("energy", fallback[0])),
        tuple(float(value) for value in spec.get("color", fallback[1])),
        float(spec.get("size", fallback[2])),
    )


def _lighting(bpy, mathutils, plan: dict) -> None:
    key = _look_light(plan, "key", (950, (1.0, 0.67, 0.40), 4.5))
    fill = _look_light(plan, "fill", (450, (0.50, 0.67, 1.0), 5.0))
    lantern = _look_light(plan, "lantern", (520, (1.0, 0.38, 0.12), 2.0))
    _add_area_light(bpy, mathutils, "Warm_Window_Key", (-3.8, -3.0, 6.0), key[0], key[1], key[2], (0, 0, 2))
    _add_area_light(bpy, mathutils, "Sky_Fill", (4.5, -2.0, 4.0), fill[0], fill[1], fill[2], (0, 0, 1.8))
    _add_area_light(bpy, mathutils, "Porch_Lantern_Light", (1.05, 1.95, 3.45), lantern[0], lantern[1], lantern[2], (0, 0, 2.1))
    if plan.get("look_profile"):
        rim = _look_light(plan, "rim", (720, (0.42, 0.62, 1.0), 3.2))
        _add_area_light(bpy, mathutils, "Cool_Story_Rim", (2.7, 3.6, 4.8), rim[0], rim[1], rim[2], (0, 0, 2.25))
    world = bpy.context.scene.world or bpy.data.worlds.new("June_Porch_World")
    bpy.context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    palette = (plan.get("look_profile") or {}).get("palette") or {}
    world_color = tuple(palette.get("world", (0.055, 0.075, 0.12)))
    background.inputs["Color"].default_value = (*world_color, 1.0)
    background.inputs["Strength"].default_value = float(
        ((plan.get("look_profile") or {}).get("lighting") or {}).get("world_strength", 0.42)
    )


def _apply_npr_material(material, profile: dict) -> None:
    """Convert a Principled material to deterministic three-band Eevee shading."""
    toon = profile.get("toon") or {}
    if not toon.get("enabled") or material.name in set(toon.get("exclude_materials") or []):
        return
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    if nodes.get("CE_NPR_Toon_Light"):
        return
    principled = nodes.get("Principled BSDF")
    output = nodes.get("Material Output")
    if principled is None or output is None:
        return
    shader_to_rgb = nodes.new("ShaderNodeShaderToRGB")
    shader_to_rgb.name = "CE_NPR_Shader_To_RGB"
    rgb_to_bw = nodes.new("ShaderNodeRGBToBW")
    rgb_to_bw.name = "CE_NPR_Luminance"
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.name = "CE_NPR_Toon_Light"
    ramp.color_ramp.interpolation = "CONSTANT"
    thresholds = [float(value) for value in toon["thresholds"]]
    levels = [float(value) for value in toon["levels"]]
    first, second = ramp.color_ramp.elements
    first.position = 0.0
    first.color = (levels[0], levels[0], levels[0], 1.0)
    second.position = thresholds[0]
    second.color = (levels[1], levels[1], levels[1], 1.0)
    highlight = ramp.color_ramp.elements.new(thresholds[1])
    highlight.color = (levels[2], levels[2], levels[2], 1.0)
    multiply = nodes.new("ShaderNodeMixRGB")
    multiply.name = "CE_NPR_Base_x_Light"
    multiply.blend_type = "MULTIPLY"
    multiply.inputs[0].default_value = 1.0
    emission = nodes.new("ShaderNodeEmission")
    emission.name = "CE_NPR_Color_Output"
    emission.inputs["Strength"].default_value = 1.0
    base = principled.inputs.get("Base Color")
    if base and base.is_linked:
        links.new(base.links[0].from_socket, multiply.inputs[1])
    elif base:
        multiply.inputs[1].default_value = base.default_value
    else:
        multiply.inputs[1].default_value = material.diffuse_color
    links.new(principled.outputs[0], shader_to_rgb.inputs[0])
    links.new(shader_to_rgb.outputs[0], rgb_to_bw.inputs[0])
    links.new(rgb_to_bw.outputs[0], ramp.inputs[0])
    links.new(ramp.outputs[0], multiply.inputs[2])
    links.new(multiply.outputs[0], emission.inputs["Color"])
    links.new(emission.outputs[0], output.inputs["Surface"])


def _configure_npr_outlines(bpy, profile: dict) -> None:
    outlines = profile.get("outlines") or {}
    if not outlines.get("enabled") or outlines.get("mode", "freestyle") != "freestyle":
        return
    scene = bpy.context.scene
    if not hasattr(scene.render, "use_freestyle"):
        return
    scene.render.use_freestyle = True
    settings = scene.view_layers[0].freestyle_settings
    line_set = settings.linesets[0]
    line_style = line_set.linestyle
    line_style.color = tuple(float(value) for value in outlines["color"])
    line_style.thickness = float(outlines["thickness_px"])
    for attribute, value in (
        ("select_silhouette", outlines.get("silhouette", True)),
        ("select_border", True),
        ("select_crease", outlines.get("crease", True)),
        ("select_material_boundary", outlines.get("material_boundary", False)),
    ):
        if hasattr(line_set, attribute):
            setattr(line_set, attribute, bool(value))


def _semantic_shot_scale(shot: dict) -> str:
    camera = str(shot.get("camera", "medium")).lower()
    if "wide" in camera:
        return "wide"
    if "close" in camera:
        return "close"
    return "medium"


def _animate_semantic_strength(socket, layer: dict, plan: dict) -> None:
    base = float(layer["strength"])
    shots = plan.get("shots") or []
    if not shots:
        socket.default_value = base
        return
    multipliers = layer["shot_multipliers"]
    for shot in shots:
        value = max(0.0, min(1.0, base * float(multipliers[_semantic_shot_scale(shot)])))
        for frame in (int(shot["frame_start"]), int(shot["frame_end"])):
            socket.default_value = value
            socket.keyframe_insert(data_path="default_value", frame=frame)


def _semantic_edge_source(nodes, links, render_layers, source_image, layer: dict):
    source = str(layer["source"])
    if source == "luminance":
        edge_input = source_image
    else:
        edge_input = render_layers.outputs["Mist" if source == "mist" else "Normal"]
    sobel = nodes.new("CompositorNodeFilter")
    sobel.name = f"CE_Ink_{layer['name']}_Sobel"
    sobel.filter_type = "SOBEL"
    links.new(edge_input, sobel.inputs["Image"])
    neutral = nodes.new("CompositorNodeRGBToBW")
    neutral.name = f"CE_Ink_{layer['name']}_Neutral"
    links.new(sobel.outputs["Image"], neutral.inputs["Image"])
    edge_output = neutral.outputs["Val"]
    dilation = int(layer.get("dilate_px", 0))
    if dilation:
        dilate = nodes.new("CompositorNodeDilateErode")
        dilate.name = f"CE_Ink_{layer['name']}_Dilation"
        dilate.mode = "DISTANCE"
        dilate.distance = dilation
        links.new(edge_output, dilate.inputs["Mask"])
        edge_output = dilate.outputs["Mask"]
    return edge_output


def _configure_npr_compositor(bpy, profile: dict, plan: dict) -> None:
    compositor = profile.get("compositor") or {}
    outlines = profile.get("outlines") or {}
    outline_mode = outlines.get("mode") if outlines.get("enabled") else None
    use_sobel = outline_mode == "compositor_sobel"
    use_semantic = outline_mode == "semantic_compositor"
    if not compositor.get("glow") and not use_sobel and not use_semantic:
        return
    scene = bpy.context.scene
    scene.use_nodes = True
    nodes = scene.node_tree.nodes
    links = scene.node_tree.links
    nodes.clear()
    render_layers = nodes.new("CompositorNodeRLayers")
    source_image = render_layers.outputs["Image"]
    image_output = source_image
    if use_sobel:
        sobel = nodes.new("CompositorNodeFilter")
        sobel.name = "CE_NPR_Temporal_Sobel"
        sobel.filter_type = "SOBEL"
        neutral = nodes.new("CompositorNodeRGBToBW")
        neutral.name = "CE_NPR_Neutral_Ink"
        invert = nodes.new("CompositorNodeInvert")
        invert.name = "CE_NPR_Invert_Edges"
        multiply = nodes.new("CompositorNodeMixRGB")
        multiply.name = "CE_NPR_Screen_Ink"
        multiply.blend_type = "MULTIPLY"
        multiply.inputs[0].default_value = float(outlines.get("edge_strength", 0.62))
        links.new(image_output, sobel.inputs["Image"])
        links.new(sobel.outputs["Image"], neutral.inputs["Image"])
        links.new(neutral.outputs["Val"], invert.inputs["Color"])
        links.new(image_output, multiply.inputs[1])
        links.new(invert.outputs["Color"], multiply.inputs[2])
        image_output = multiply.outputs[0]
    if use_semantic:
        view_layer = scene.view_layers[0]
        view_layer.use_pass_normal = True
        view_layer.use_pass_mist = True
        if scene.world:
            scene.world.mist_settings.start = 0.0
            scene.world.mist_settings.depth = 24.0
            scene.world.mist_settings.falloff = "QUADRATIC"
        ink = nodes.new("CompositorNodeRGB")
        ink.name = "CE_Semantic_Ink_Color"
        ink.outputs["RGBA"].default_value = (*tuple(float(value) for value in outlines["color"]), 1.0)
        for layer in outlines["semantic_layers"]:
            edge_output = _semantic_edge_source(nodes, links, render_layers, source_image, layer)
            strength = nodes.new("CompositorNodeMath")
            strength.name = f"CE_Ink_{layer['name']}_Shot_Strength"
            strength.operation = "MULTIPLY"
            strength.use_clamp = True
            strength.inputs[1].default_value = float(layer["strength"])
            links.new(edge_output, strength.inputs[0])
            _animate_semantic_strength(strength.inputs[1], layer, plan)
            mix = nodes.new("CompositorNodeMixRGB")
            mix.name = f"CE_Ink_{layer['name']}_Composite"
            mix.blend_type = "MIX"
            links.new(strength.outputs[0], mix.inputs[0])
            links.new(image_output, mix.inputs[1])
            links.new(ink.outputs["RGBA"], mix.inputs[2])
            image_output = mix.outputs[0]
    if compositor.get("glow"):
        glare = nodes.new("CompositorNodeGlare")
        glare.name = "CE_NPR_Lantern_Glow"
        glare.glare_type = "FOG_GLOW"
        glare.quality = "HIGH"
        glare.threshold = float(compositor.get("glow_threshold", 1.15))
        glare.mix = float(compositor.get("glow_mix", -0.93))
        links.new(image_output, glare.inputs["Image"])
        image_output = glare.outputs["Image"]
    composite = nodes.new("CompositorNodeComposite")
    links.new(image_output, composite.inputs["Image"])


def _configure_npr_cameras(bpy, profile: dict) -> None:
    camera_profile = profile.get("camera") or {}
    if not camera_profile.get("depth_of_field"):
        return
    target = tuple(float(value) for value in camera_profile["focus_target"])
    for camera_obj in (obj for obj in bpy.data.objects if obj.type == "CAMERA"):
        dx = camera_obj.location.x - target[0]
        dy = camera_obj.location.y - target[1]
        dz = camera_obj.location.z - target[2]
        camera_obj.data.dof.use_dof = True
        focus_distance = max(0.1, math.sqrt(dx * dx + dy * dy + dz * dz))
        focus = bpy.data.objects.new(f"{camera_obj.name}_NPR_Focus", None)
        bpy.context.collection.objects.link(focus)
        focus.parent = camera_obj
        focus.location = (0.0, 0.0, -focus_distance)
        camera_obj.data.dof.focus_object = focus
        camera_obj.data.dof.focus_distance = focus_distance
        camera_obj.data.dof.aperture_fstop = float(camera_profile.get("f_stop", 4.2))
        camera_obj.data.dof.aperture_blades = 7


def _apply_npr_look(bpy, plan: dict) -> None:
    profile = plan.get("look_profile")
    if not profile:
        return
    for material in bpy.data.materials:
        _apply_npr_material(material, profile)
    _configure_npr_outlines(bpy, profile)
    _configure_npr_compositor(bpy, profile, plan)
    _configure_npr_cameras(bpy, profile)


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
    elif selected == "BLENDER_EEVEE_NEXT":
        if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = int(render.get("samples", 24))
        if hasattr(scene.render, "use_motion_blur"):
            look_render = (plan.get("look_profile") or {}).get("render") or {}
            scene.render.use_motion_blur = bool(look_render.get("motion_blur", False))
        _apply_npr_look(bpy, plan)
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
        rig, mouth, face_controls = _make_june(bpy, mathutils, materials, asset_major=3)
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
            "beard": bpy.data.objects.get("June_Fitted_Beard"),
            "moustache": [obj for side in ("L", "R") if (obj := bpy.data.objects.get(f"June_Moustache_{side}")) is not None],
            "lower_lip": bpy.data.objects.get("June_Mouth_Lower_Lip"),
        }
    head = bpy.data.objects["June_Head"]
    _animate_rig(bpy, rig, plan)
    _animate_performance_props(bpy, plan)
    _animate_mouth(mouth, plan)
    _animate_expressions(head, plan, face_controls)
    if not plan.get("disable_blinks", False):
        _animate_blinks(face_controls, int(plan["frame_end"]))
    _make_cameras(bpy, mathutils, plan)
    _lighting(bpy, mathutils, plan)
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
