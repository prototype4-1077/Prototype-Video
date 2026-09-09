"""June v3: mapped skin, rigid oral assemblies and a coherent swept groom."""
import argparse
import json
import math
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.blender import june_anatomy_source as anatomy
from pipeline.blender import june_hero_v9 as hero
from pipeline.blender import june_studio_assets as studio
from pipeline.blender import june_studio_character as character
from pipeline.blender import refine_june_studio as v2
from pipeline.blender import render_vertical_slice as base
from pipeline.june_studio import atomic_json, sha256
from pipeline.june_studio_v3 import MANIFEST, checked_assets, connected_components, match_uvs, read_obj, uv_lookup


def sculpt(point):
    from mathutils import Vector
    x, y, z = point
    side = -1 if x < 0 else 1
    front = hero.smooth((-y-.035)/.13)
    # Fill the sharp under-eye transition and soften its outer ridge.
    cheek = hero.gauss(abs(x), z, .143, 2.650, .073, .061)*front
    outer = hero.gauss(abs(x), z, .196, 2.719, .045, .071)*front
    y += -.029*cheek + .006*outer
    x += side*.004*cheek
    tip = hero.gauss(x, z, 0, 2.639, .063, .064)*front
    x *= 1+.14*tip
    y += .014*tip
    # Small asymmetric lift, retained consistently by every speech shape.
    grin = hero.gauss(abs(x), z, .069, 2.535, .043, .035)*front
    z += (.0032 if side < 0 else .0008)*grin
    z -= .014*hero.smooth((z-2.882)/.15)
    return Vector((x, y, z))


def refine_shapes(bpy, rig, head):
    for obj in list(bpy.data.objects):
        if obj.parent is rig and obj.parent_bone in ('head', 'eye.L', 'eye.R') and obj.type in ('MESH', 'CURVE'):
            v2.transform_geometry(obj, sculpt)
    head['ce_art_refinement'] = 'studio-v3: shared cheek, nose, grin and crown rest field'


def restore_uvs(bpy, resources):
    source = anatomy.load()
    reference = uv_lookup(read_obj(resources['reference_obj']))
    result = {}
    for name, part in [('June_Head', 'head'), ('June_Hand_L', 'left_hand'), ('June_Hand_R', 'right_hand')]:
        obj = bpy.data.objects[name]
        data = source[part]
        if len(obj.data.vertices) != len(data['source_vertex_ids']):
            raise ValueError('source vertex identity count differs: ' + name)
        polygons = [list(p.vertices) for p in obj.data.polygons]
        coordinates = match_uvs(polygons, data['source_vertex_ids'], reference)
        uv = obj.data.uv_layers.get('June_Source_UV') or obj.data.uv_layers.new(name='June_Source_UV')
        for polygon, corners in zip(obj.data.polygons, coordinates):
            for loop, value in zip(polygon.loop_indices, corners):
                uv.data[loop].uv = value
        obj.data.uv_layers.active = uv
        result[name] = {'vertices': len(obj.data.vertices), 'matched_faces': len(coordinates), 'unmatched_faces': 0}
    return result


def image_material(bpy, name, path, roughness, tint=(1, 1, 1, 1)):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bs = nodes.get('Principled BSDF')
    image = bpy.data.images.load(str(path), check_existing=True); image.pack()
    texture = nodes.new('ShaderNodeTexImage'); texture.image = image
    multiply = nodes.new('ShaderNodeMixRGB'); multiply.blend_type = 'MULTIPLY'
    multiply.inputs[0].default_value = 1; multiply.inputs[2].default_value = tint
    links.new(texture.outputs['Color'], multiply.inputs[1]); links.new(multiply.outputs[0], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = roughness
    return mat, bs, texture, multiply


def mapped_skin(bpy, resources):
    mat, bs, texture, tone = image_material(bpy, 'June V3 mapped aged skin', resources['skin'], .57, (.70, .73, .75, 1))
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    uv = nodes.new('ShaderNodeUVMap'); uv.uv_map = 'June_Source_UV'
    links.new(uv.outputs['UV'], texture.inputs['Vector'])
    coords = nodes.new('ShaderNodeAttribute'); coords.attribute_name = 'june_rest'
    weight = nodes.new('ShaderNodeAttribute'); weight.attribute_name = 'june_skin_texture_weight'
    blend = nodes.new('ShaderNodeMixRGB'); blend.inputs[1].default_value = (.41, .252, .183, 1)
    links.new(weight.outputs['Fac'], blend.inputs[0]); links.new(tone.outputs[0], blend.inputs[2])
    links.new(blend.outputs[0], bs.inputs['Base Color'])
    pores = nodes.new('ShaderNodeTexNoise'); pores.inputs['Scale'].default_value = 820
    pores.inputs['Detail'].default_value = 2; links.new(coords.outputs['Vector'], pores.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .23
    bump.inputs['Distance'].default_value = .00065
    links.new(pores.outputs['Fac'], bump.inputs['Height']); links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    rough = nodes.new('ShaderNodeMapRange'); rough.inputs['From Min'].default_value = 0
    rough.inputs['From Max'].default_value = 1; rough.inputs['To Min'].default_value = .46; rough.inputs['To Max'].default_value = .65
    links.new(pores.outputs['Fac'], rough.inputs['Value']); links.new(rough.outputs['Result'], bs.inputs['Roughness'])
    bs.inputs['Subsurface Weight'].default_value = .10
    bs.inputs['Subsurface Radius'].default_value = (1, .43, .24)
    bs.inputs['Subsurface Scale'].default_value = .010
    bs.inputs['Specular IOR Level'].default_value = .30
    for name in ('June_Head', 'June_Hand_L', 'June_Hand_R'):
        obj = bpy.data.objects[name]; obj.data.materials.clear(); obj.data.materials.append(mat)
        v2.rest_attributes(obj)
        attr = obj.data.attributes.new('june_skin_texture_weight', 'FLOAT', 'POINT')
        for vertex, value in zip(obj.data.vertices, attr.data):
            x, y, z = obj.matrix_world @ vertex.co
            scalp = hero.smooth((z-2.895)/.055) if name == 'June_Head' else 0
            value.value = 1-.97*scalp
    # Keep the untextured internal neck and groom roots in the same palette.
    for name in ('Scalp', 'Beard', 'Moustache'):
        old = bpy.data.materials['Studio '+name+' undercoat']
        mix = next(n for n in old.node_tree.nodes if n.type == 'MIX_RGB')
        mix.inputs[1].default_value = (.41, .252, .183, 1)
        mix.inputs[2].default_value = (.49, .478, .446, 1)


def mesh_subset(bpy, name, source, chosen, transform, material, sub=1):
    indices = sorted({v for i in chosen for v in source['faces'][i]})
    lookup = {old: new for new, old in enumerate(indices)}
    obj = hero.mesh(bpy, name, [transform(source['vertices'][i]) for i in indices],
                    [[lookup[v] for v in source['faces'][i]] for i in chosen], material, sub=sub)
    uv = obj.data.uv_layers.new(name='UVMap')
    for polygon, original in zip(obj.data.polygons, chosen):
        for loop, value in zip(polygon.loop_indices, source['face_corner_uvs'][original]):
            uv.data[loop].uv = value
    return obj


def parent_preserving_world(obj, parent):
    matrix = obj.matrix_world.copy(); obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = matrix


def oral_assembly(bpy, rig, head, resources):
    from mathutils import Vector
    for obj in list(bpy.data.objects):
        if obj.name.startswith(('June_Studio_Upper_Tooth_', 'June_Studio_Lower_Tooth_')) or obj.name == 'June_Studio_Oral_Cavity':
            bpy.data.objects.remove(obj, do_unlink=True)
    jaw = bpy.data.objects.new('June_V3_Jaw', None); bpy.context.collection.objects.link(jaw)
    jaw.empty_display_type = 'PLAIN_AXES'; jaw.empty_display_size = .05
    jaw.location = (0, -.12, 2.61); bpy.context.view_layer.update()
    base._parent_to_bone(jaw, rig, 'head'); bpy.context.view_layer.update()
    baseline = jaw.rotation_euler.x
    curve = jaw.driver_add('rotation_euler', 0); driver = curve.driver
    terms = []
    for name, amount in {'B': .03, 'C': .14, 'D': .34, 'E': .11, 'F': .065, 'G': .03, 'H': .13}.items():
        var = driver.variables.new(); var.name = name; var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'KEY'; var.targets[0].id = head.data.shape_keys
        var.targets[0].data_path = 'key_blocks["'+name+'"].value'; terms.append(f'{amount}*{name}')
    driver.expression = f'{baseline}+min(.42,max(0,' + '+'.join(terms) + '))'
    jaw['ce_rigid_oral_assembly'] = True
    teeth = read_obj(resources['teeth_mesh'])
    components = connected_components(teeth['faces'], len(teeth['vertices']))
    rows = {}; tooth_components = 0
    for component in components:
        if len(component) > 100:
            continue
        tooth_components += 1
        height = sum(teeth['vertices'][i][1]+.23*teeth['vertices'][i][2] for i in component)/len(component)
        for i in component:
            rows[i] = 'Upper' if height > 6.531 else 'Lower'
    groups = {'Upper': [], 'Lower': []}
    for i, face in enumerate(teeth['faces']):
        row = rows.get(face[0])
        if row is None:
            height = sum(teeth['vertices'][v][1]+.23*teeth['vertices'][v][2] for v in face)/len(face)
            row = 'Upper' if height > 6.531 else 'Lower'
        groups[row].append(i)
    mat, bs, _, _ = image_material(bpy, 'June V3 teeth and gums', resources['teeth_texture'], .36, (.83, .80, .72, 1))
    bs.inputs['Subsurface Weight'].default_value = .04; bs.inputs['Subsurface Scale'].default_value = .003
    for row, chosen in groups.items():
        def fit(p):
            x, y, z = p
            return (x*.30, -.301+(1.30-z)*.28, 2.537+(y+.23*z-6.531)*.25)
        obj = mesh_subset(bpy, 'June_V3_'+row+'_Teeth_Gums', teeth, chosen, fit, mat)
        if row == 'Upper': base._parent_to_bone(obj, rig, 'head')
        else: parent_preserving_world(obj, jaw)
        obj['ce_rigid_teeth'] = True
    tongue = read_obj(resources['tongue_mesh'])
    mat, bs, _, _ = image_material(bpy, 'June V3 tongue', resources['tongue_texture'], .42, (.58, .43, .42, 1))
    bs.inputs['Subsurface Weight'].default_value = .10; bs.inputs['Subsurface Scale'].default_value = .005
    def fit_tongue(p):
        x, y, z = p
        return (x*.22, -.279+(1.394-z)*.145, 2.519+(y-6.51)*.055)
    obj = mesh_subset(bpy, 'June_V3_Tongue', tongue, list(range(len(tongue['faces']))), fit_tongue, mat, sub=2)
    parent_preserving_world(obj, jaw)
    cavity = base._sphere(bpy, 'June_V3_Oral_Cavity', (0, -.12, 2.50), (.093, .133, .092), bpy.data.materials['June v9 mouth'], segments=32, rings=20)
    base._parent_to_bone(cavity, rig, 'head')
    return {'source_tooth_components': tooth_components, 'upper_faces': len(groups['Upper']), 'lower_faces': len(groups['Lower']), 'rigid_driver': jaw.name}


def swept_groom(bpy, rig, head):
    from mathutils import Vector
    old = bpy.data.objects.get('June_V2_Swept_Crown')
    if old: bpy.data.objects.remove(old, do_unlink=True)
    bvh = v2.head_surface(bpy, head); rng = random.Random(30909)
    grouped = [[], [], []]
    # One guide determines a small neighboring clump's direction and arc.
    for _ in range(490):
        x, y = rng.uniform(-.19, .18), rng.uniform(-.135, .18)
        root, normal, _, _ = bvh.ray_cast(Vector((x, y, 3.4)), Vector((0, 0, -1)), 1.)
        if root is None or root.z < 2.925:
            continue
        if y < -.08 and abs(x) < .065 and rng.random() < .40:
            continue
        length = rng.uniform(.115, .20); lift = rng.uniform(.033, .061)
        direction = Vector((.73+rng.uniform(-.15, .15), .66+rng.uniform(-.13, .13), -.08))
        tangent = (direction-normal*direction.dot(normal)).normalized()
        perpendicular = normal.cross(tangent).normalized()
        group = rng.randrange(3)
        phase = rng.uniform(0, math.tau)
        for child in range(6):
            origin = root+perpendicular*((child-2.5)*.0018)+tangent*rng.uniform(-.004, .004)
            strand_length = length*rng.uniform(.87, 1.13)
            strand_lift = lift*rng.uniform(.85, 1.15)
            radius = rng.uniform(.62, .93)
            path = []
            for j in range(12):
                t = j/11
                candidate = origin+tangent*strand_length*t+perpendicular*(.008*math.sin(phase+t*4)*t)
                surface, n, _, _ = bvh.find_nearest(candidate)
                point = surface+n*(.0014+strand_lift*math.sin(math.pi*t*.81))
                path.append((*point, (1-t*.97)*radius))
            grouped[group].append(path)
    for i, paths in enumerate(grouped):
        mat = base._material(bpy, 'June V3 crown tone '+str(i), [( .42, .416, .389, 1),(.62, .606, .555, 1),(.76, .745, .682, 1)][i], roughness=.46)
        bs = mat.node_tree.nodes.get('Principled BSDF'); bs.inputs['Anisotropic'].default_value = .28
        obj = hero.curves(bpy, 'June_V3_Swept_Clumps_'+str(i), paths, mat, .00054, rig)
        obj.data.bevel_resolution = 0; character.follow_face(obj, head)
    # Trim the fuzzy tips without changing roots or speech-following shape keys.
    for name in ('June_Studio_Beard', 'June_Studio_Moustache'):
        obj = bpy.data.objects[name]; offset = 0
        for spline in obj.data.splines:
            count = len(spline.points)
            for key in obj.data.shape_keys.key_blocks:
                root = key.data[offset].co.copy()
                for j in range(1, count):
                    point = key.data[offset+j]
                    point.co = root+(point.co-root)*.86
            offset += count
    return {'guide_seed': 30909, 'crown_strands': sum(len(paths) for paths in grouped), 'tone_groups': 3}


def validate_oral(bpy, head):
    """Check real evaluated motion and rigidity at the open speech extreme."""
    objects = [bpy.data.objects['June_V3_'+row+'_Teeth_Gums'] for row in ('Upper', 'Lower')]
    def snapshot():
        bpy.context.view_layer.update()
        return [[obj.matrix_world@vertex.co for vertex in obj.data.vertices] for obj in objects]
    neutral = snapshot(); head.data.shape_keys.key_blocks['D'].value = 1
    opened = snapshot(); head.data.shape_keys.key_blocks['D'].value = 0; bpy.context.view_layer.update()
    errors = []
    for rest, moved in zip(neutral, opened):
        for i in range(1, min(80, len(rest))):
            errors.append(abs((rest[i]-rest[0]).length-(moved[i]-moved[0]).length))
    centers = [[sum(p.z for p in points)/len(points) for points in state] for state in (neutral, opened)]
    lower_drop = centers[0][1]-centers[1][1]
    if max(errors) > 1e-5 or lower_drop < .02:
        raise ValueError('oral assembly does not move rigidly with the jaw')
    return {'rigidity_max_error': max(errors), 'lower_row_D_drop': lower_drop,
            'upper_row_D_shift': centers[1][0]-centers[0][0], 'oral_mechanics_pass': True}


def main():
    import bpy, mathutils
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--resources', required=True); parser.add_argument('--views', default='')
    parser.add_argument('--width', type=int, default=1280); parser.add_argument('--samples', type=int, default=24)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    source, output = Path(args.source).resolve(), Path(args.output).resolve()
    receipt = json.loads(source.with_suffix('.json').read_text())
    if output.parent == source.parent or receipt.get('asset_version') != 'studio-v2':
        raise ValueError('v3 needs a studio-v2 source and a separate output directory')
    if sha256(source) != receipt['asset_sha256']:
        raise ValueError('source asset identity mismatch')
    executed_sha = sha256(__file__); resources = checked_assets(args.resources)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    rig, head = bpy.data.objects['June_Oxley_Rig'], bpy.data.objects['June_Head']
    rig.data.pose_position = 'REST'
    for key in head.data.shape_keys.key_blocks: key.value = 0
    bpy.context.view_layer.update()
    print('Refining the shared face and facial shapes', flush=True)
    refine_shapes(bpy, rig, head)
    print('Restoring identity-matched skin UVs', flush=True)
    uv_report = restore_uvs(bpy, resources); mapped_skin(bpy, resources)
    print('Building rigid teeth, gums and tongue', flush=True)
    oral_report = oral_assembly(bpy, rig, head, resources)
    print('Building coherent swept crown clumps', flush=True)
    groom_report = swept_groom(bpy, rig, head)
    oral_report.update(validate_oral(bpy, head))
    rig.data.pose_position = 'POSE'; studio.body_pose(rig, 270)
    rig['ce_asset_version'] = 'studio-v3-development'; rig['ce_dialogue_ready'] = False
    character_collection = bpy.data.collections['June_Character_Studio_v2']
    character_collection.name = 'June_Character_Studio_v3'
    set_collection = bpy.data.collections['June_Porch_Studio_v1']
    scene = bpy.context.scene; scene['ce_production_approved'] = False
    for obj in list(scene.objects):
        collection = character_collection if obj.name.startswith('June_') and obj.type not in ('CAMERA', 'LIGHT') else set_collection
        if collection not in obj.users_collection:
            for old in list(obj.users_collection): old.objects.unlink(obj)
            collection.objects.link(obj)
    scene.camera = bpy.data.objects['June_Camera_Close']; studio.aim_control(rig, 'gaze', scene.camera.location)
    scene.frame_set(1); scene.render.resolution_x = args.width; scene.render.resolution_y = args.width*9//16
    scene.render.resolution_percentage = 100; scene.cycles.samples = args.samples
    scene.render.image_settings.file_format = 'PNG'; scene.render.use_persistent_data = True
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), compress=True)
    result = {**receipt, 'asset_version': 'studio-v3', 'asset_sha256': sha256(output),
              'source_asset_sha256': sha256(source), 'refinement_sha256': executed_sha,
              'refinement_helpers_sha256': sha256(Path(__file__).resolve().parents[1]/'june_studio_v3.py'),
              'source_manifest_sha256': sha256(MANIFEST), 'source_assets': {k: sha256(v) for k, v in resources.items()},
              'production_approved': False, 'dialogue_quality_approved': False,
              'character_collection': character_collection.name, 'uv_report': uv_report,
              'oral_report': oral_report, 'groom_report': groom_report,
              'packed_images': [image.name for image in bpy.data.images if image.packed_file]}
    atomic_json(output.with_suffix('.json'), result)
    views = {'close': ('Close', {}), 'front': ('Front', {}), 'smile': ('Close', {'smile': .75, 'warm_eyes': .65}),
             'blink': ('Front', {'blink_L': 1., 'blink_R': 1.}), 'speech-d': ('Close', {'D': .8}), 'wide': ('Wide', {})}
    for label in filter(None, args.views.split(',')):
        if label not in views: raise ValueError('unknown inspection view: '+label)
        camera, values = views[label]
        for key in head.data.shape_keys.key_blocks: key.value = values.get(key.name, 0)
        scene.camera = bpy.data.objects['June_Camera_'+camera]; studio.aim_control(rig, 'gaze', scene.camera.location)
        scene.render.filepath = str(output.parent/(label+'.png'))
        print('Rendering v3 '+label, flush=True); bpy.ops.render.render(write_still=True)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
