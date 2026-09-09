"""V5 garment construction and extremities from an unchanged v4 library.

Authored rest folds and weighted details keep this asset deterministic. No cloth
simulation, external texture download or per-frame Python handler is required.
"""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.blender import june_hero_v9 as hero
from pipeline.blender import june_studio_assets as studio
from pipeline.blender import refine_june_studio as v2
from pipeline.blender import render_vertical_slice as base
from pipeline.june_studio import atomic_json, sha256


def remove(bpy, names):
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)


def limb_coordinates(point, rig, first, second):
    """Nearest point on the two rest bones, in a continuous length coordinate."""
    a, b = rig.data.bones[first], rig.data.bones[second]
    total = a.length+b.length
    candidates = []
    for bone, offset in ((a, 0.), (b, a.length)):
        delta = bone.tail_local-bone.head_local
        t = min(1., max(0., (point-bone.head_local).dot(delta)/delta.length_squared))
        center = bone.head_local+delta*t
        candidates.append(((point-center).length, (offset+t*bone.length)/total, center))
    return min(candidates, key=lambda v: v[0])


def fold(delta, width, strength):
    # A broad ridge with its adjacent shallow valley, rather than a sine ripple.
    return strength*(math.exp(-(delta/width)**2)-.50*math.exp(-((delta-width*1.4)/(width*.8))**2))


def sculpt_fabric(bpy, rig):
    from mathutils import Vector
    coat = bpy.data.objects['June_Continuous_Coat']
    def jacket(point):
        x, y, z = point
        side = 'L' if x < 0 else 'R'
        _, t, center = limb_coordinates(point, rig, 'upper_arm.'+side, 'forearm.'+side)
        radial = point-center
        arm = hero.smooth((abs(x)-.32)/.15)
        theta = math.atan2(radial.y, radial.x)
        amount = .006*hero.smooth((t-.18)/.4)
        for loc, width, strength, angle in ((.39,.06,.009,.7),(.51,.045,.013,1.8),
                                           (.62,.055,.009,2.6),(.89,.035,.011,.3)):
            amount += fold(t-loc-.035*math.sin(theta+angle), width, strength)
        q = point+radial.normalized()*amount*arm if radial.length else point.copy()
        # Long drape and soft diagonal compression near the jacket hem.
        body = (1-arm)*hero.smooth((z-1.27)/.11)*(1-hero.smooth((z-1.99)/.12))
        a = math.atan2(x, -(y-.02))
        drape = .006*math.sin(a*9+.35)*body
        drape += fold(z-1.43-.055*math.sin(a*3), .035, .009)*body
        n = Vector((x, y-.02, 0)).normalized()
        return q+n*drape
    v2.transform_geometry(coat, jacket)
    reports = {}
    for side in ('L', 'R'):
        obj = bpy.data.objects['June_Weighted_Overall_Leg_'+side]
        first, second = 'thigh.'+side, 'shin.'+side
        def trousers(point):
            _, t, center = limb_coordinates(point, rig, first, second)
            radial = point-center
            if radial.length < .001:
                return point.copy()
            theta = math.atan2(radial.y, radial.x)
            amount = .006*hero.smooth((t-.28)/.22)
            for loc, width, strength, phase in ((.44,.048,.012,.7),(.56,.04,.010,2.1),
                                                (.82,.032,.013,.4),(.90,.028,.014,2.3),
                                                (.965,.024,.010,1.0)):
                amount += fold(t-loc-.026*math.sin(theta+phase), width, strength)
            return point+radial.normalized()*amount
        v2.transform_geometry(obj, trousers)
        v2.rest_attributes(obj)
        reports[side] = {'leg_vertices': len(obj.data.vertices), 'knee_and_ankle_folds': 5}
    v2.rest_attributes(coat)
    return reports


def front_project(surface, x, z, offset=.007):
    from mathutils import Vector
    p, n, _, _ = surface.ray_cast(Vector((x, -2, z)), Vector((0, 1, 0)), 4.)
    if p is None:
        raise ValueError(f'garment fitting ray missed at {x}, {z}')
    return p+Vector((0, -offset, 0))


def weighted_detail(bpy, obj, source, rig):
    """Transfer existing garment weights to trim, then deform both together."""
    from mathutils.kdtree import KDTree
    if obj.type == 'CURVE':
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True); bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target='MESH')
        obj = bpy.context.object
    world = obj.matrix_world.copy()
    obj.parent = None; obj.matrix_world = world
    tree = KDTree(len(source.data.vertices))
    for v in source.data.vertices:
        tree.insert(source.matrix_world@v.co, v.index)
    tree.balance()
    names = {g.index:g.name for g in source.vertex_groups}
    groups = {name:obj.vertex_groups.new(name=name) for name in names.values()}
    for v in obj.data.vertices:
        near = tree.find_n(obj.matrix_world@v.co, 3)
        weights = {}
        for _, index, distance in near:
            for g in source.data.vertices[index].groups:
                name = names[g.group]
                weights[name] = weights.get(name, 0.)+g.weight/max(distance,.002)**2
        total = sum(weights.values())
        if total <= 0:
            raise ValueError('unweighted garment detail')
        for name, value in weights.items():
            groups[name].add([v.index], value/total, 'REPLACE')
    mod = obj.modifiers.new('Follow garment skinning', 'ARMATURE')
    mod.object = rig; mod.use_deform_preserve_volume = True
    v2.rest_attributes(obj)
    obj['ce_weight_source'] = source.name
    return obj


def wardrobe_details(bpy, rig):
    from mathutils import Vector
    denim = bpy.data.materials['June v9 denim']
    thread = bpy.data.materials['June v9 thread']
    overalls = bpy.data.materials['June v9 overalls']
    brass = bpy.data.materials['June v9 brass']
    coat = bpy.data.objects['June_Continuous_Coat']
    surface = v2.head_surface(bpy, coat)
    for side, sign in (('L', -1), ('R', 1)):
        remove(bpy, ['June_Jacket_Pocket_'+side, 'June_Pocket_Stitches_'+side,
                     'June_Jacket_Front_Stitches_'+side, 'June_V2_Collar_Seam_'+side])
        # Keep the fitted collar mesh and trace its actual perimeter.
        collar = bpy.data.objects['June_Jacket_Collar_'+side]
        boundary = [collar.matrix_world@v.co for v in list(collar.data.vertices)[-5:]]
        hero.seam(bpy, 'June_V5_Collar_Stitch_'+side,
                  [p+Vector((0,-.003,0)) for p in boundary+boundary[:1]], thread, rig, radius=.0008)
        # Chest patch and separate flap fit the evaluated shell, not guessed depth.
        outline = [(sign*x,z) for x,z in ((.17,1.97),(.275,1.94),(.277,1.79),(.228,1.765),(.17,1.79))]
        points = [front_project(surface, x, z) for x,z in outline]
        patch = hero.panel(bpy, 'June_V5_Chest_Pocket_'+side, points, denim, rig, thickness=.004)
        v2.rest_attributes(patch)
        hero.seam(bpy, 'June_V5_Pocket_Stitch_'+side,
                  [p+Vector((0,-.003,0)) for p in points+points[:1]], thread, rig, radius=.00085)
        flap_points = [front_project(surface, sign*x,z,.014) for x,z in
                       ((.162,1.979),(.280,1.95),(.278,1.911),(.224,1.897),(.164,1.932))]
        flap = hero.panel(bpy,'June_V5_Pocket_Flap_'+side,flap_points,denim,rig,thickness=.004)
        v2.rest_attributes(flap)
        p = front_project(surface, sign*.225,1.918,.022)
        button = base._sphere(bpy,'June_V5_Flap_Button_'+side,p,(.009,.003,.009),brass,segments=20,rings=12)
        base._parent_to_bone(button,rig,'torso')
        # Parallel front topstitch and back yoke give the jacket a sewn structure.
        for index, angle in enumerate((.49,.56)):
            path=[]
            for j in range(71):
                z=1.32+j/70*.75
                x=sign*(.31+.027*math.sin((z-1.32)*3))*math.sin(angle)
                path.append(front_project(surface,x,z,.009))
            seam=hero.seam(bpy,'June_V5_Placket_'+side+str(index),path,thread,rig,radius=.00085)
            weighted_detail(bpy,seam,coat,rig)
        # Side seam follows the leg's exact authored rings and their weights.
        leg=bpy.data.objects['June_Weighted_Overall_Leg_'+side]
        rings=[leg.data.vertices[i:i+48] for i in range(0,49*48,48)]
        path=[]
        for ring in rings[7:]:
            chosen=max(ring,key=lambda v:sign*(leg.matrix_world@v.co).x)
            path.append(leg.matrix_world@chosen.co+Vector((sign*.002,0,0)))
        for index, dx in enumerate((0.,.006)):
            seam=hero.seam(bpy,'June_V5_Leg_Seam_'+side+str(index),
                          [p+Vector((0,dx,0)) for p in path],thread,rig,radius=.0008)
            weighted_detail(bpy,seam,leg,rig)
        # Actual folded hem band, with a consistent shin attachment.
        shin=rig.data.bones['shin.'+side]
        direction=(shin.tail_local-shin.head_local).normalized()
        center=shin.tail_local-direction*.040
        cuff=base._cylinder_between(bpy,__import__('mathutils'),'June_V5_Trouser_Cuff_'+side,
                                   center-direction*.027,center+direction*.027,.119,overalls)
        base._parent_to_bone(cuff,rig,'shin.'+side);v2.rest_attributes(cuff)
    # Replace the pouch-like bib pocket with a flatter, wider sewn patch.
    remove(bpy,['June_Bib_Pocket','June_Bib_Pocket_Seam'])
    points=[(-.105,-.260,1.72),(.105,-.260,1.72),(.104,-.262,1.58),(0,-.268,1.568),(-.104,-.262,1.58)]
    obj=hero.panel(bpy,'June_V5_Bib_Pocket',points,overalls,rig,thickness=.003)
    v2.rest_attributes(obj)
    hero.seam(bpy,'June_V5_Bib_Stitch',[(x,y-.004,z) for x,y,z in points+points[:1]],thread,rig,radius=.0008)


def boot_ring(cx, z, rx, ry, cy, count=64):
    result=[]
    for i in range(count):
        a=math.tau*i/count
        sx,sy=math.sin(a),math.cos(a)
        x=cx+rx*math.copysign(abs(sx)**.76,sx)
        y=cy-ry*math.copysign(abs(sy)**.80,sy)
        result.append((x,y,z))
    return result


def ring_mesh(bpy,name,sections,material,rig,bone,closed=True,sub=1):
    n=64;verts=[p for section in sections for p in boot_ring(*section)]
    faces=[(k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j)
           for k in range(len(sections)-1) for j in range(n)]
    if closed:faces+=[tuple(reversed(range(n))),tuple(range(len(verts)-n,len(verts)))]
    obj=hero.mesh(bpy,name,verts,faces,material,sub=sub)
    base._parent_to_bone(obj,rig,bone);v2.rest_attributes(obj)
    return obj


def leather_material(bpy):
    mat=base._material(bpy,'June V5 worn leather',(.08,.036,.014,1),roughness=.64)
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    bs=nodes.get('Principled BSDF')
    attr=nodes.new('ShaderNodeAttribute');attr.attribute_name='june_rest'
    noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=70
    noise.inputs['Detail'].default_value=3;links.new(attr.outputs['Vector'],noise.inputs['Vector'])
    ramp=nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color=(.026,.012,.005,1)
    ramp.color_ramp.elements[1].color=(.155,.080,.034,1)
    links.new(noise.outputs['Fac'],ramp.inputs['Fac']);links.new(ramp.outputs['Color'],bs.inputs['Base Color'])
    fine=nodes.new('ShaderNodeTexNoise');fine.inputs['Scale'].default_value=620
    links.new(attr.outputs['Vector'],fine.inputs['Vector'])
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.20;bump.inputs['Distance'].default_value=.0012
    links.new(fine.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bs.inputs['Normal'])
    return mat


def build_boots(bpy,rig):
    from mathutils import Vector
    leather=leather_material(bpy);sole=bpy.data.materials['June v9 sole']
    thread=bpy.data.materials['June v9 thread'];brass=bpy.data.materials['June v9 brass']
    trim=base._material(bpy,'June V5 welt edge',(.12,.073,.034,1),roughness=.76)
    for side,cx in (('L',-.22),('R',.22)):
        remove(bpy,[name+side for name in ('June_Boot_','June_Boot_Sole_','June_Boot_Quarter_','June_Boot_Laces_')])
        bone='foot.'+side
        # Preserve the original sole's exact support height for the existing walk.
        ring_mesh(bpy,'June_Boot_Sole_'+side,
                  [(cx,z,rx,ry,-.750) for z,rx,ry in ((.1675,.117,.215),(.170,.123,.218),
                     (.200,.123,.218),(.204,.119,.214))],sole,rig,bone,sub=0)
        ring_mesh(bpy,'June_V5_Boot_Welt_'+side,
                  [(cx,z,.122,.215,-.750) for z in (.203,.206,.216,.218)],trim,rig,bone)
        upper=ring_mesh(bpy,'June_Boot_'+side,
              [(cx,z,rx,ry,cy) for z,rx,ry,cy in ((.213,.116,.204,-.750),(.224,.116,.204,-.750),
                (.274,.113,.200,-.747),(.310,.109,.190,-.734),(.340,.103,.154,-.700),
                (.378,.094,.110,-.635),(.426,.092,.096,-.604),(.451,.095,.097,-.604))],
              leather,rig,bone,closed=False,sub=2)
        mod=upper.modifiers.new('Leather thickness','SOLIDIFY');mod.thickness=.006
        surface=v2.head_surface(bpy,upper)
        # Laces and eyelets follow the actual curved instep.
        left=[];right=[]
        for j in range(6):
            z=.318+j*.020
            points=[]
            for sign in (-1,1):
                p=front_project(surface,cx+sign*.035,z,.005)
                eyelet=base._sphere(bpy,'June_V5_Eyelet_'+side+str(j)+str(sign),p,
                                    (.006,.002,.006),brass,segments=16,rings=8)
                base._parent_to_bone(eyelet,rig,bone)
                points.append(p+Vector((0,-.003,0)))
            left.append(points[0]);right.append(points[1])
        paths=[]
        for j in range(5):
            for a,b in ((left[j],right[j+1]),(right[j],left[j+1])):
                paths.append([a,a.lerp(b,.5)+Vector((0,-.004,.002)),b])
        laces=hero.curves(bpy,'June_Boot_Laces_'+side,paths,sole,.0025,rig,bone)
        # Cap seam and doubled welt topstitch give distinct construction layers.
        path=[]
        for j in range(37):
            x=cx-.095+j/36*.190;y=-.838+.013*math.cos(j/36*math.pi)
            p,n,_,_=surface.ray_cast(Vector((x,y,1)),Vector((0,0,-1)),1.)
            if p is not None:path.append(p+n*.002)
        hero.seam(bpy,'June_V5_Toe_Cap_'+side,path,thread,rig,bone,radius=.00075)
        ring=boot_ring(cx,.219,.119,.211,-.750)
        hero.seam(bpy,'June_V5_Welt_Stitch_'+side,ring+ring[:1],thread,rig,bone,radius=.0008)


def refine_hands(bpy,rig):
    # Bone scale carries the connected palm, weighted digits and their controls.
    # It is constant asset structure, not overwritten by any existing body clip.
    for side in ('L','R'):
        hand=bpy.data.objects['June_Hand_'+side]
        forearm=rig.data.bones['forearm.'+side]
        wrist=forearm.tail_local
        direction=(forearm.tail_local-forearm.head_local).normalized()
        def wrist_fit(point):
            delta=point-wrist;along=delta.dot(direction)
            if along>=0:return point.copy()
            radial=delta-direction*along
            if radial.length>.040:radial*=.040/radial.length
            return wrist+direction*max(-.035,along)+radial
        # The source hand includes a long forearm stub. Keep that hidden portion
        # inside the cuff when the hand is enlarged, without changing the digits.
        v2.transform_geometry(hand,wrist_fit);v2.rest_attributes(hand)
        rig.pose.bones['hand.'+side].scale=(1.23,1.20,1.23)
    rig['ce_finger_relax_degrees']=[15.,20.,24.,27.,18.]
    rig['ce_finger_distal_fraction']=.72
    return {'hand_bone_scale':[1.23,1.20,1.23],
            'relaxed_proximal_degrees':list(rig['ce_finger_relax_degrees']),
            'distal_ratio':.72,'wrist_stub_max_length':.035,
            'topology_and_digit_weights_preserved':True}


def main():
    import bpy
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    p.add_argument('--views',default='');p.add_argument('--width',type=int,default=1280)
    p.add_argument('--samples',type=int,default=16)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    source,output=Path(args.source).resolve(),Path(args.output).resolve()
    receipt=json.loads(source.with_suffix('.json').read_text())
    if receipt.get('asset_version')!='studio-v4' or source.parent==output.parent:
        raise ValueError('v5 requires an unchanged studio-v4 source in a separate directory')
    if sha256(source)!=receipt['asset_sha256']:raise ValueError('source asset identity mismatch')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    rig=bpy.data.objects['June_Oxley_Rig'];head=bpy.data.objects['June_Head'];scene=bpy.context.scene
    rig.data.pose_position='REST'
    for key in head.data.shape_keys.key_blocks:key.value=0
    bpy.context.view_layer.update()
    existing=set(bpy.data.objects)
    print('Sculpting garment folds',flush=True);fabric=sculpt_fabric(bpy,rig)
    print('Fitting sewn wardrobe details',flush=True);wardrobe_details(bpy,rig)
    print('Building shaped work boots',flush=True);build_boots(bpy,rig)
    hands=refine_hands(bpy,rig)
    collection=bpy.data.collections[receipt['character_collection']]
    collection.name='June_Character_Studio_v5'
    for obj in set(bpy.data.objects)-existing:
        if obj.name not in collection.objects:collection.objects.link(obj)
        for owner in list(obj.users_collection):
            if owner!=collection:owner.objects.unlink(obj)
    # Dedicated full-body study camera; existing close/front/wide shots retain
    # their framing and can still be compared with the v4 benchmark.
    camera=bpy.data.objects.new('June_Camera_Body',bpy.data.cameras.new('June_Camera_Body'))
    scene.collection.objects.link(camera)
    camera.location=(-1.7,-8.4,2.2);camera.data.lens=40
    base._look_at(camera,(.035,-1.06,1.67),__import__('mathutils'))
    rig.data.pose_position='POSE';studio.body_pose(rig,270)
    rig['ce_asset_version']='studio-v5-development';rig['ce_dialogue_ready']=False
    scene['ce_production_approved']=False
    scene.camera=bpy.data.objects['June_Camera_Close'];studio.aim_control(rig,'gaze',scene.camera.location)
    scene.frame_set(1);scene.render.resolution_x=args.width;scene.render.resolution_y=args.width*9//16
    scene.render.resolution_percentage=100;scene.cycles.samples=args.samples;scene.cycles.use_denoising=True
    scene.render.use_persistent_data=True;scene.render.image_settings.file_format='PNG'
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
    result={**receipt,'asset_version':'studio-v5','asset_sha256':sha256(output),
            'source_asset_sha256':sha256(source),'refinement_sha256':sha256(__file__),
            'body_pose_sha256':sha256(studio.__file__),'character_collection':collection.name,
            'fabric_report':fabric,'hand_report':hands,'new_boot_support_height':.1675,
            'cloth_simulation':False,'production_approved':False,'dialogue_quality_approved':False}
    atomic_json(output.with_suffix('.json'),result)
    for label in filter(None,args.views.split(',')):
        camera={'wide':'Wide','front':'Front','close':'Close','body':'Body'}[label]
        scene.camera=bpy.data.objects['June_Camera_'+camera];studio.aim_control(rig,'gaze',scene.camera.location)
        scene.render.filepath=str(output.parent/(label+'.png'))
        print('Rendering v5 '+label,flush=True);bpy.ops.render.render(write_still=True)
    print('Saved '+str(output),flush=True)


if __name__=='__main__':main()
