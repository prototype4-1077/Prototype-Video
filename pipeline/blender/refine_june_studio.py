"""Versioned art refinement of a saved June studio, retaining its animation rig.

Run with Blender 4.2. The source asset and its receipt are required and left
untouched. This is a development sculpt, never an automatic art approval.
"""
import argparse
import json
import math
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.blender import june_hero_v9 as hero
from pipeline.blender import june_studio_character as character
from pipeline.blender import june_studio_assets as studio
from pipeline.blender import render_vertical_slice as base
from pipeline.june_studio import atomic_json, sha256


def sculpt(point):
    """One continuous rest-space field for skin, speech shapes and facial parts."""
    from mathutils import Vector
    x, y, z = point
    original_z = z
    # Smaller orbital masses; the same field fits the eyes and their lids.
    side = -1 if x < 0 else 1
    cx, cz = side * .107, 2.731 if side < 0 else 2.727
    orbital = math.exp(-(((x-cx)/.113)**2 + ((z-cz)/.105)**2)**2)
    orbital *= hero.smooth((-y-.09)/.10)
    x = cx + (x-cx) * (1-.17*orbital)
    z = cz + (z-cz) * (1-.15*orbital)
    # Shorter chin-to-eye distance and less domed forehead.
    if z < 2.731:
        z = 2.731 + (z-2.731)*.90
    if z > 2.84:
        z = 2.84 + (z-2.84)*.82
    x *= 1-.035*hero.smooth((original_z-2.83)/.16)
    if y < -.12:
        cheek = hero.gauss(abs(x), z, .143, 2.65, .071, .070)
        y += .003*cheek
        x += side*.004*cheek
        nose = hero.gauss(x, z, 0, 2.642, .056, .056)
        x *= 1+.13*nose
        y -= .013*nose
    return Vector((x, y, z))


def geometry_points(obj):
    if obj.type == 'MESH':
        return obj.data.vertices
    return [p for s in obj.data.splines for p in s.points]


def transform_geometry(obj, transform):
    """Bake the same transform into every shape, without changing key drivers."""
    from mathutils import Vector
    world, inverse = obj.matrix_world.copy(), obj.matrix_world.inverted()
    keys = getattr(obj.data, 'shape_keys', None)
    blocks = [k.data for k in keys.key_blocks] if keys else [geometry_points(obj)]
    for block in blocks:
        for point in block:
            result = inverse @ transform(world @ Vector(point.co[:3]))
            point.co = (*result, point.co[3]) if len(point.co) == 4 else result
    if keys and obj.type == 'MESH':
        for p, b in zip(obj.data.vertices, keys.key_blocks['Basis'].data):
            p.co = b.co


def refine_face(bpy, rig):
    from mathutils import Vector
    head = bpy.data.objects['June_Head']
    facial = [o for o in bpy.data.objects
              if o.parent is rig and o.parent_bone in ('head', 'eye.L', 'eye.R')
              and o.type in ('MESH', 'CURVE')]
    for obj in facial:
        keys = getattr(obj.data, 'shape_keys', None)
        if keys and keys.key_blocks.get('smile'):
            rest = [p.co.copy() for p in keys.key_blocks['Basis'].data]
            delta = [p.co-b for p, b in zip(keys.key_blocks['smile'].data, rest)]
            for key in keys.key_blocks:
                for p, d in zip(key.data, delta):
                    p.co += d*.32
        transform_geometry(obj, sculpt)
        # Larger iris-to-sclera ratio; keep the same eye pivots and gaze rig.
        if any(token in obj.name for token in ('Iris_', 'Pupil_')):
            side = -1 if obj.name.endswith('_L') else 1
            c = sculpt(Vector((side*.107, -.2445, 2.731 if side < 0 else 2.727)))
            transform_geometry(obj, lambda p: Vector((c.x+(p.x-c.x)*1.20, p.y, c.z+(p.z-c.z)*1.20)))
    head['ce_art_refinement'] = 'studio-v2: shared rest-space face and groom fit'
    return head


def head_surface(bpy, head):
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update()
    evaluated = head.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = evaluated.to_mesh(); data.calc_loop_triangles()
    points = [evaluated.matrix_world @ v.co for v in data.vertices]
    triangles = [tuple(t.vertices) for t in data.loop_triangles]
    bvh = BVHTree.FromPolygons(points, triangles, all_triangles=True)
    evaluated.to_mesh_clear()
    return bvh


def volume_groom(bpy, rig, head):
    from mathutils import Vector
    rng = random.Random(90217)
    bvh = head_surface(bpy, head)
    hair = bpy.data.materials['June v9 hair']
    # Lift the existing follicles into softly swept clumps; their roots stay put.
    scalp = bpy.data.objects['June_Studio_Scalp']
    keys = scalp.data.shape_keys.key_blocks
    offset = 0
    for spline in scalp.data.splines:
        n = len(spline.points)
        root = Vector(keys['Basis'].data[offset].co[:3])
        height = rng.uniform(.006, .015)
        for j in range(n):
            t = j/(n-1); direction = Vector((.016*t, .022*t, height*math.sin(math.pi*t)))
            for key in keys:
                key.data[offset+j].co += direction
        offset += n
    # Sparse crown and temple flyaways provide volume, not a painted hair cap.
    paths = []
    for _ in range(1650):
        x = rng.uniform(-.212, .18); y = rng.uniform(-.085, .19)
        point, normal, _, _ = bvh.ray_cast(Vector((x, y, 3.5)), Vector((0, 0, -1)), 1.)
        if point is None or point.z < 2.88:
            continue
        if y < -.02 and abs(x) < .10 and rng.random() < .72:
            continue
        length = rng.uniform(.075, .125)
        lift = rng.uniform(.022, .036)
        radius = rng.uniform(.72, 1.)
        direction = Vector((.28, .92, -.20))
        tangent = (direction-normal*direction.dot(normal)).normalized()
        path = []
        for j in range(9):
            t = j/8
            candidate = point+tangent*length*t
            near, n, _, _ = bvh.find_nearest(candidate)
            p = near+n*(.0015+lift*math.sin(t*math.pi*.86))
            path.append((*p, (1-t*.96)*radius))
        paths.append(path)
    crown = hero.curves(bpy, 'June_V2_Swept_Crown', paths, hair, .00065, rig)
    crown.data.bevel_resolution = 0
    character.follow_face(crown, head)
    # Brows follow the sculpted orbital crest, with a real tufted silhouette.
    for side, sign in (('L', -1), ('R', 1)):
        old = bpy.data.objects.get('June_Studio_Brow_'+side)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        paths = []
        for _ in range(470):
            t = rng.random()
            x = sign*(.048+.133*t)
            z = 2.813+.018*math.sin(math.pi*t)-.025*t+rng.uniform(-.006, .006)
            p, n, _, _ = bvh.ray_cast(Vector((x, -1, z)), Vector((0, 1, 0)), 2.)
            if p is None:
                continue
            path = []
            for j in range(6):
                u=j/5
                q = p+Vector((sign*.021*u, -.003-.006*math.sin(u*math.pi), .012*math.sin(u*2.1)))
                path.append((*q, 1-u*.95))
            paths.append(path)
        brow=hero.curves(bpy, 'June_V2_Brow_'+side, paths, hair, .0009, rig)
        brow.data.bevel_resolution=0
        character.follow_face(brow, head)
    # Fine eye crinkles break the uniformly smooth orbital surface.
    crease=base._material(bpy,'June V2 fine eye creases',(.30,.174,.119,1),roughness=.66)
    for sign in (-1,1):
        paths=[]
        for row in range(3):
            path=[]
            for j in range(25):
                t=j/24;x=sign*(.165+.067*t)
                z=2.737+(row-1)*.010+t*(row-1)*.019
                p,n,_,_=bvh.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2.)
                if p is not None:path.append((*(p+n*.00025),.1+.45*math.sin(math.pi*t)))
            if path:paths.append(path)
        obj=hero.curves(bpy,'June_V2_Eye_Crinkles_'+str(sign),paths,crease,.0008,rig)
        obj.data.bevel_resolution=0;character.follow_face(obj,head)


def rest_attributes(obj):
    if obj.type != 'MESH':
        return
    attribute = obj.data.attributes.get('june_rest') or obj.data.attributes.new('june_rest', 'FLOAT_VECTOR', 'POINT')
    for v, item in zip(obj.data.vertices, attribute.data):
        item.vector = obj.matrix_world @ v.co


def skin_material(bpy):
    skin = bpy.data.materials['June v9 skin']
    nodes, links = skin.node_tree.nodes, skin.node_tree.links
    nodes.clear()
    bs = nodes.new('ShaderNodeBsdfPrincipled'); out = nodes.new('ShaderNodeOutputMaterial')
    links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    color = nodes.new('ShaderNodeAttribute'); color.attribute_name = 'june_skin_color'
    coords = nodes.new('ShaderNodeAttribute'); coords.attribute_name = 'june_rest'
    noise = nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 42; noise.inputs['Detail'].default_value = 3
    links.new(coords.outputs['Vector'], noise.inputs['Vector'])
    mix = nodes.new('ShaderNodeMixRGB'); mix.blend_type='MULTIPLY'; mix.inputs[0].default_value=.14
    links.new(color.outputs['Color'], mix.inputs[1]); links.new(noise.outputs['Fac'], mix.inputs[2]); links.new(mix.outputs['Color'],bs.inputs['Base Color'])
    pores = nodes.new('ShaderNodeTexNoise'); pores.inputs['Scale'].default_value=310; pores.inputs['Detail'].default_value=3
    links.new(coords.outputs['Vector'],pores.inputs['Vector'])
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.30;bump.inputs['Distance'].default_value=.0011
    links.new(pores.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bs.inputs['Normal'])
    bs.inputs['Roughness'].default_value=.55;bs.inputs['Specular IOR Level'].default_value=.28
    bs.inputs['Subsurface Weight'].default_value=.085;bs.inputs['Subsurface Radius'].default_value=(1,.45,.25)
    bs.inputs['Subsurface Scale'].default_value=.012
    for obj in bpy.data.objects:
        if obj.type!='MESH' or skin.name not in [m.name for m in obj.data.materials if m]:
            continue
        rest_attributes(obj)
        attr=obj.data.color_attributes.get('june_skin_color') or obj.data.color_attributes.new('june_skin_color','FLOAT_COLOR','POINT')
        for v,c in zip(obj.data.vertices,attr.data):
            x,y,z=obj.matrix_world@v.co
            blush=(hero.gauss(abs(x),z,.148,2.66,.075,.060)*.45+hero.gauss(x,z,0,2.64,.063,.060)*.45) if obj.name=='June_Head' and y<-.10 else 0
            c.color=(.43+.023*blush,.254-.080*blush,.182-.062*blush,1)
    for name in ('Scalp','Beard','Moustache'):
        mat=bpy.data.materials['Studio '+name+' undercoat']
        mix=next(n for n in mat.node_tree.nodes if n.type=='MIX_RGB')
        mix.inputs[1].default_value=(.43,.25,.175,1)
        mix.inputs[2].default_value=(.49,.473,.435,1)
    hair=bpy.data.materials['June v9 hair'].node_tree.nodes.get('Principled BSDF')
    hair.inputs['Base Color'].default_value=(.65,.625,.575,1)
    hair.inputs['Roughness'].default_value=.42;hair.inputs['Specular IOR Level'].default_value=.32
    eye=bpy.data.materials['June v9 eye'].node_tree.nodes.get('Principled BSDF')
    eye.inputs['Base Color'].default_value=(.60,.63,.56,1);eye.inputs['Roughness'].default_value=.12
    iris=bpy.data.materials['June v9 iris'].node_tree.nodes.get('Principled BSDF')
    iris.inputs['Base Color'].default_value=(.125,.205,.215,1)


def textile_materials(bpy):
    """Rest-bound macro dye variation and diagonal twill with finer cross fibers."""
    for obj in bpy.data.objects:
        if obj.name.startswith('June_'):
            rest_attributes(obj)
    for name,dark,light in (
        ('denim',(.019,.045,.072,1),(.067,.119,.154,1)),
        ('overalls',(.010,.024,.036,1),(.042,.071,.090,1))):
        material=bpy.data.materials['June v9 '+name]
        nodes,links=material.node_tree.nodes,material.node_tree.links
        nodes.clear();bs=nodes.new('ShaderNodeBsdfPrincipled');out=nodes.new('ShaderNodeOutputMaterial')
        links.new(bs.outputs[0],out.inputs['Surface'])
        coords=nodes.new('ShaderNodeAttribute');coords.attribute_name='june_rest'
        noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=65;noise.inputs['Detail'].default_value=3
        links.new(coords.outputs['Vector'],noise.inputs['Vector'])
        tone=nodes.new('ShaderNodeValToRGB');tone.color_ramp.elements[0].color=dark;tone.color_ramp.elements[1].color=light
        links.new(noise.outputs['Fac'],tone.inputs['Fac']);links.new(tone.outputs['Color'],bs.inputs['Base Color'])
        wave=nodes.new('ShaderNodeTexWave');wave.bands_direction='DIAGONAL';wave.inputs['Scale'].default_value=260
        links.new(coords.outputs['Vector'],wave.inputs['Vector'])
        bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.26;bump.inputs['Distance'].default_value=.00085
        links.new(wave.outputs['Color'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bs.inputs['Normal'])
        bs.inputs['Roughness'].default_value=.79;bs.inputs['Sheen Weight'].default_value=.20;bs.inputs['Specular IOR Level'].default_value=.20
    plaid=bpy.data.materials['June v9 plaid']
    nodes,links=plaid.node_tree.nodes,plaid.node_tree.links
    rest=nodes.new('ShaderNodeAttribute');rest.attribute_name='june_rest'
    for axis in ('X','Z'):
        wave=nodes.get('CE_Plaid_'+axis)
        wave.inputs['Scale'].default_value=12
        wave.inputs['Distortion'].default_value=.12
        links.new(rest.outputs['Vector'],wave.inputs['Vector'])
    ramp=nodes.get('CE_Plaid_Color').color_ramp
    ramp.elements[0].position=.55;ramp.elements[0].color=(.023,.039,.052,1)
    ramp.elements[1].position=.80;ramp.elements[1].color=(.065,.087,.10,1)
    fine=ramp.elements.new(.97);fine.color=(.14,.079,.048,1)
    thread=bpy.data.materials['June v9 thread'].node_tree.nodes.get('Principled BSDF')
    thread.inputs['Base Color'].default_value=(.37,.265,.155,1)
    brass=bpy.data.materials['June v9 brass'].node_tree.nodes.get('Principled BSDF')
    brass.inputs['Base Color'].default_value=(.27,.18,.075,1);brass.inputs['Metallic'].default_value=.70


def wardrobe_details(bpy, rig):
    from mathutils import Vector
    coat=bpy.data.objects['June_Continuous_Coat']
    # The old wide shirt opening and narrow inner neck left a dark annular gap.
    neck=bpy.data.objects['June_Studio_Neck_Interior']
    transform_geometry(neck,lambda p:Vector((p.x*1.22,.014+(p.y-.014)*1.22,p.z)))
    stand=hero.loft(bpy,'June_V2_Shirt_Collar_Stand',
        ((2.16,.205,.141,.014),(2.197,.154,.122,.014),(2.24,.117,.115,.014)),
        bpy.data.materials['June v9 plaid'],arc=(.40,math.tau-.40),segments=48,rows=20,thickness=.004)
    base._parent_to_bone(stand,rig,'torso')
    # Gentle compression folds, confined to elbow and lower jacket regions.
    for v in coat.data.vertices:
        x,y,z=v.co
        elbow=math.exp(-((abs(x)-.54)/.13)**2-((z-1.65)/.19)**2)
        lower=math.exp(-((z-1.40)/.10)**2)*hero.smooth((abs(x)-.17)/.15)
        v.co += v.normal*(.0045*elbow*math.sin(z*100+x*17)+.0025*lower*math.sin(x*51+z*28))
    bpy.context.view_layer.update()
    bvh=head_surface(bpy,coat)
    def project(p,offset=.006):
        hit,n,_,_=bvh.ray_cast(Vector((p.x,-1,p.z)),Vector((0,1,0)),2)
        return Vector((p.x,hit.y-offset,p.z)) if hit is not None else p
    # Existing details were authored before the voxel coat and sank under it.
    for obj in list(bpy.data.objects):
        if obj.name.startswith(('June_Jacket_Pocket_','June_Pocket_Stitches_','June_Jacket_Front_Stitches_')):
            transform_geometry(obj, project)
        elif obj.name.startswith('June_Jacket_Button_'):
            center=obj.matrix_world.translation.copy();new=project(center,.009)
            delta=new-center;transform_geometry(obj,lambda p: p+delta)
    # Shoulder yokes and collar topstitching are real curves, parented to torso.
    thread=bpy.data.materials['June v9 thread']
    for side,sign in (('L',-1),('R',1)):
        for row in range(2):
            path=[]
            for j in range(36):
                t=j/35;p=Vector((sign*(.155+.24*t),0,2.055-.028*t-row*.008))
                path.append(tuple(project(p,.007)))
            hero.seam(bpy,'June_V2_Yoke_'+side+str(row),path,thread,rig,radius=.00085)
        collar=bpy.data.objects['June_Jacket_Collar_'+side]
        coords=[collar.matrix_world@v.co for v in collar.data.vertices]
        n=(len(coords)-1)//2
        boundary=[tuple(p+Vector((0,-.004,0))) for p in coords[n+1:]]
        hero.seam(bpy,'June_V2_Collar_Seam_'+side,boundary+[boundary[0]],thread,rig,radius=.0008)


def lighting(bpy, mathutils):
    scene=bpy.context.scene
    scene.view_settings.look='AgX - Medium High Contrast'
    bpy.data.objects['Porch_Key'].data.energy=800
    bpy.data.objects['Porch_Key'].data.color=(1,.88,.76)
    bpy.data.objects['Porch_Fill'].data.energy=230
    base._add_area_light(bpy,mathutils,'June_V2_Hair_Rim',(2.2,.4,4.3),220,(1,.77,.51),2,(0,-1,2.8))
    # Focus at the actual standing face; the rig's head moves during the walk.
    for name in ('Close','Front'):
        camera=bpy.data.objects['June_Camera_'+name]
        camera.data.dof.use_dof=True;camera.data.dof.aperture_fstop=6.3
        camera.data.dof.focus_distance=(camera.location-mathutils.Vector((0,-1.0,2.87))).length


def main():
    import bpy,mathutils
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--review',action='store_true');parser.add_argument('--width',type=int,default=1280)
    parser.add_argument('--samples',type=int,default=32)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    source=Path(args.source).resolve();output=Path(args.output).resolve()
    if output.parent==source.parent:
        raise ValueError('The refinement needs a separate directory to preserve source review files')
    receipt=json.loads(source.with_suffix('.json').read_text())
    if receipt.get('asset_version')!='studio-v1':
        raise ValueError('This refinement expects studio-v1; do not apply it twice')
    if sha256(source)!=receipt['asset_sha256']:
        raise ValueError('Source asset does not match its receipt')
    executed_refinement_sha=sha256(Path(__file__))
    bpy.ops.wm.open_mainfile(filepath=str(source))
    rig=bpy.data.objects['June_Oxley_Rig'];rig.data.pose_position='REST'
    bpy.context.view_layer.update()
    print('Refining shared face geometry',flush=True)
    head=refine_face(bpy,rig)
    print('Adding swept groom volume',flush=True)
    volume_groom(bpy,rig,head)
    print('Refining wardrobe and material finish',flush=True)
    wardrobe_details(bpy,rig);skin_material(bpy);textile_materials(bpy);lighting(bpy,mathutils)
    rig.data.pose_position='POSE';studio.body_pose(rig,270)
    # A rest offset on the existing head control keeps eyes, jaw and grooming
    # together throughout every inherited action, and reduces the exposed neck.
    rig.pose.bones['head'].location=rig.data.bones['head'].matrix_local.to_3x3().inverted() @ mathutils.Vector((0,0,-.072))
    rig['ce_asset_version']='studio-v2-development';rig['ce_dialogue_ready']=False
    scene=bpy.context.scene;scene['ce_production_approved']=False
    # Newly authored parts must travel with the character when its collection
    # is appended into another shot, rather than remaining in the root scene.
    character_collection=bpy.data.collections['June_Character_Studio_v1']
    character_collection.name='June_Character_Studio_v2'
    set_collection=bpy.data.collections['June_Porch_Studio_v1']
    for obj in list(scene.objects):
        collection=character_collection if obj.name.startswith('June_') and obj.type not in {'CAMERA','LIGHT'} else set_collection
        if collection not in obj.users_collection:
            for previous in list(obj.users_collection):previous.objects.unlink(obj)
            collection.objects.link(obj)
    scene.camera=bpy.data.objects['June_Camera_Close'];studio.aim_control(rig,'gaze',scene.camera.location)
    scene.frame_set(1);scene.render.resolution_x=args.width;scene.render.resolution_y=args.width*9//16
    scene.cycles.samples=args.samples;scene.render.image_settings.file_format='PNG'
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
    result={**receipt,'asset_version':'studio-v2','asset_sha256':sha256(output),
            'source_asset_sha256':sha256(source),'production_approved':False,'dialogue_quality_approved':False,
            'refinement_sha256':executed_refinement_sha,'blender_version':bpy.app.version_string,
            'character_collection':character_collection.name,'set_collection':set_collection.name}
    atomic_json(output.with_suffix('.json'),result)
    if args.review:
        for label,camera,values in (
            ('close','Close',{}),('front','Front',{}),('smile','Close',{'smile':.75,'warm_eyes':.65}),
            ('blink','Front',{'blink_L':1.,'blink_R':1.}),('speech-d','Close',{'D':.8}),('wide','Wide',{})):
            for k in head.data.shape_keys.key_blocks:k.value=values.get(k.name,0)
            scene.camera=bpy.data.objects['June_Camera_'+camera];studio.aim_control(rig,'gaze',scene.camera.location)
            scene.render.filepath=str(output.parent/(label+'.png'))
            print('Rendering art review '+label,flush=True);bpy.ops.render.render(write_still=True)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
