"""A separate v6 art candidate from a checksum-verified v5 studio library.

The refiner changes the editable asset, never the source or approval state.
It uses the existing rig, facial keys and v5 boots. Run with Blender 4.2.0.
"""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.blender import june_hero_v9 as hero
from pipeline.blender import june_studio_assets as studio
from pipeline.blender import refine_june_studio as common
from pipeline.blender import refine_june_studio_v5 as v5
from pipeline.blender import render_vertical_slice as base
from pipeline.june_studio import atomic_json, sha256

HEAD_SCALE = .86


def checked_source(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source.parent == output.parent:
        raise ValueError('v6 must use a separate output directory')
    receipt = json.loads(source.with_suffix('.json').read_text())
    if receipt.get('asset_version') != 'studio-v5':
        raise ValueError('v6 requires a studio-v5 source')
    if sha256(source) != receipt.get('asset_sha256'):
        raise ValueError('source asset identity mismatch')
    return receipt


def likeness(bpy, rig):
    """Refine cheeks/nose outside the fitted eyelids, and scale the whole head."""
    from mathutils import Vector
    def field(p):
        x, y, z = p
        front = hero.smooth((-y-.12)/.12)
        cheek = hero.gauss(abs(x), z, .155, 2.648, .078, .046)*front
        cheek *= 1-hero.smooth((z-2.677)/.020)
        nose = hero.gauss(x, z, 0., 2.639, .056, .041)*front
        # A fuller, rounder lower cheek and nose tip; leave the orbital rim,
        # lids, eye geometry and fitted rigid mouth assembly alone.
        x += math.copysign(.0055*cheek, x)
        y -= .007*cheek
        x *= 1+.12*nose
        y += .005*nose
        z += .0015*nose
        return Vector((x, y, z))
    changed=[]
    for obj in list(bpy.data.objects):
        if obj.parent is rig and obj.parent_bone == 'head' and obj.type in {'MESH','CURVE'}:
            if obj.name.startswith('June_V3_'):
                continue
            common.transform_geometry(obj, field); changed.append(obj.name)
    rig.pose.bones['head'].scale=(HEAD_SCALE,)*3
    common.rest_attributes(bpy.data.objects['June_Head'])
    # Every child eye/groom/jaw inherits the same uniform scale. Nonuniform
    # resizing of just the skin would break eye and mouth registration.
    return {'head_uniform_scale':HEAD_SCALE, 'shared_rest_field_objects':changed,
            'orbital_region_excluded':True, 'rigid_oral_geometry_unchanged':True}


def soften_groom(bpy):
    """Lay the existing crown strands back and taper their silhouette."""
    count=0
    for name in ['June_Studio_Scalp']+['June_V3_Swept_Clumps_'+str(i) for i in range(3)]:
        obj=bpy.data.objects[name];keys=obj.data.shape_keys.key_blocks;offset=0
        for spline in obj.data.splines:
            n=len(spline.points)
            for j,point in enumerate(spline.points):
                t=j/max(1,n-1)
                point.radius *= .82*(1-.18*t)
                for key in keys:
                    p=key.data[offset+j]
                    if p.co.z>2.91:
                        w=hero.smooth((p.co.z-2.91)/.075)*t
                        q=p.co.copy();q.x+=.006*w;q.y+=.020*w;q.z-=.008*w
                        p.co=q
            offset+=n;count+=1
    return {'existing_strands_softened':count, 'roots_and_shape_key_bindings_preserved':True}


def fitted_fabric(bpy, rig):
    """Take bulk out of the sleeve while retaining the continuous coat mesh."""
    coat=bpy.data.objects['June_Continuous_Coat']
    def slim(p):
        side='L' if p.x<0 else 'R'
        _,t,center=v5.limb_coordinates(p,rig,'upper_arm.'+side,'forearm.'+side)
        weight=hero.smooth((abs(p.x)-.32)/.13)
        weight*=1-.42*hero.smooth((t-.80)/.20)
        q=center+(p-center)*(1-.12*weight)
        # Bring the old wide jacket neck opening in to the anatomical neck.
        # This is the existing continuous shell, not a patch hiding a hole.
        neck=hero.smooth((q.z-2.09)/.15)*(1-hero.smooth((abs(q.x)-.27)/.05))
        q.x*=1-.38*neck;q.y=.024+(q.y-.024)*(1-.28*neck)
        q.z+=.014*neck
        return q
    common.transform_geometry(coat,slim);common.rest_attributes(coat)
    waist=bpy.data.objects['June_Overall_Waist']
    def seat(q):
        from mathutils import Vector
        rise=.17*hero.smooth(abs(q.x)/.22)*hero.smooth((1.32-q.z)/.24)
        return Vector((q.x,q.y,q.z+rise))
    common.transform_geometry(waist,seat);common.rest_attributes(waist)
    return {'maximum_sleeve_radial_reduction':.12, 'continuous_coat_topology_retained':True,
            'jacket_neck_opening_fitted':True,'overall_crotch_contour':'raised side edges meet upper legs'}


def cloth_grid(bpy, name, points, columns, material, rig, source=None):
    rows=len(points)//columns
    faces=[(r*columns+c,r*columns+c+1,(r+1)*columns+c+1,(r+1)*columns+c)
           for r in range(rows-1) for c in range(columns-1)]
    obj=hero.mesh(bpy,name,points,faces,material,sub=1)
    mod=obj.modifiers.new('Woven cloth thickness','SOLIDIFY');mod.thickness=.004;mod.offset=0
    if source is not None:
        obj=v5.weighted_detail(bpy,obj,source,rig)
    else:
        for name in ('pelvis','torso'):obj.vertex_groups.new(name=name)
        for v in obj.data.vertices:
            t=hero.smooth((v.co.z-1.28)/.36)
            obj.vertex_groups['pelvis'].add([v.index],1-t,'REPLACE')
            obj.vertex_groups['torso'].add([v.index],t,'REPLACE')
        mod=obj.modifiers.new('Follow body','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=True
        obj['ce_weight_source']='authored pelvis-to-torso cloth blend'
    common.rest_attributes(obj)
    return obj


def wardrobe(bpy, rig):
    """Model a joined shirt neckline and bib fitted inside the open jacket."""
    from mathutils import Vector
    denim=bpy.data.materials['June v9 denim'];plaid=bpy.data.materials['June v9 plaid']
    overall=bpy.data.materials['June v9 overalls'];thread=bpy.data.materials['June v9 thread']
    brass=bpy.data.materials['June v9 brass']
    remove=['June_Plaid_Torso','June_Overall_Bib','June_V5_Bib_Pocket','June_V5_Bib_Stitch',
            'June_V2_Shirt_Collar_Stand']
    for side in ('L','R'):
        remove += ['June_Jacket_Collar_'+side,'June_Shirt_Collar_'+side,
                   'June_V5_Collar_Stitch_'+side,'June_Overall_Strap_'+side,'June_Overall_Buckle_'+side]
    v5.remove(bpy,remove)
    shirt=hero.loft(bpy,'June_Plaid_Torso',
          ((1.26,.277,.191,.025),(1.55,.289,.204,.020),(1.90,.310,.207,.018),
           (2.07,.282,.184,.016),(2.16,.211,.143,.014),(2.23,.117,.111,.014)),
          plaid,segments=64,rows=40,thickness=.003)
    base._parent_to_bone(shirt,rig,'torso');common.rest_attributes(shirt)
    # A shallow open throat exposes the existing neck instead of buttoning
    # the flannel all the way to the underside of the beard.
    common.transform_geometry(shirt,lambda q:Vector((q.x,q.y,q.z-.040*
        hero.smooth((q.z-2.12)/.11)*hero.smooth((-q.y-.045)/.060)*
        (1-hero.smooth((abs(q.x)-.025)/.075)))))
    common.rest_attributes(shirt)
    shirt_surface=common.head_surface(bpy,shirt)
    stand=hero.loft(bpy,'June_V6_Shirt_Collar_Stand',
          ((2.205,.133,.117,.014),(2.232,.120,.111,.014),(2.258,.115,.109,.014)),
          plaid,arc=(.55,math.tau-.55),segments=48,rows=10,thickness=.004)
    base._parent_to_bone(stand,rig,'torso');common.rest_attributes(stand)
    # Unlike the former rounded fan, this quad surface meets the waist and
    # follows the flannel contour, with no pouch projecting over the jacket.
    columns=17;points=[]
    for r in range(25):
        z=1.435+(1.835-1.435)*r/24
        width=.210-.047*hero.smooth((z-1.42)/.40)
        for c in range(columns):
            x=width*(2*c/(columns-1)-1)
            p=v5.front_project(shirt_surface,x,z,.011)
            p.y-=.0025*math.sin(c/(columns-1)*math.pi)*math.sin(r/24*math.pi)
            points.append(p)
    bib=cloth_grid(bpy,'June_Overall_Bib',points,columns,overall,rig)
    # Small patch pocket sits on the bib, rather than floating ahead of it.
    bib_surface=common.head_surface(bpy,bib)
    pocket=[]
    for r in range(11):
        z=1.51+.197*r/10
        for c in range(13):
            x=.112*(2*c/12-1)
            pocket.append(v5.front_project(bib_surface,x,z,.004))
    patch=cloth_grid(bpy,'June_V6_Bib_Pocket',pocket,13,overall,rig,bib)
    border=[points[c] for c in range(columns)]+[points[r*columns+columns-1] for r in range(1,25)]
    border += [points[24*columns+c] for c in reversed(range(columns-1))]
    border += [points[r*columns] for r in reversed(range(1,24))]
    seam=hero.seam(bpy,'June_V6_Bib_Topstitch',[p+Vector((0,-.003,0)) for p in border+border[:1]],thread,rig,radius=.00085)
    v5.weighted_detail(bpy,seam,bib,rig)
    edge=[pocket[r*13] for r in reversed(range(11))]+pocket[:13]+[pocket[r*13+12] for r in range(1,11)]
    seam=hero.seam(bpy,'June_V6_Bib_Pocket_Stitch',[p+Vector((0,-.002,0)) for p in edge],thread,rig,radius=.0008)
    v5.weighted_detail(bpy,seam,bib,rig)
    coat_surface=common.head_surface(bpy,bpy.data.objects['June_Continuous_Coat'])
    waist_surface=common.head_surface(bpy,bpy.data.objects['June_Overall_Waist'])
    fly=[v5.front_project(waist_surface,.022,1.13+.275*r/30,.004) for r in range(31)]
    hero.seam(bpy,'June_V6_Overall_Fly',fly,thread,rig,bone='pelvis',radius=.00085)
    for side,sign in (('L',-1),('R',1)):
        # Collar leaf rolls out of the neckline and lies on the jacket front.
        outline=[(sign*.110,-.111,2.252),(sign*.156,-.128,2.218),
                 v5.front_project(coat_surface,sign*.274,2.098,.007),
                 v5.front_project(coat_surface,sign*.194,2.015,.010),
                 (sign*.123,-.196,2.139)]
        obj=hero.panel(bpy,'June_Jacket_Collar_'+side,outline,denim,rig,thickness=.004)
        common.rest_attributes(obj)
        seam=hero.seam(bpy,'June_V6_Collar_Stitch_'+side,[Vector(p)+Vector((0,-.002,0)) for p in outline+outline[:1]],thread,rig,radius=.0007)
        collar=[(sign*.058,-.109,2.251),(sign*.106,-.124,2.239),
                v5.front_project(shirt_surface,sign*.122,2.098,.009),
                v5.front_project(shirt_surface,sign*.057,2.122,.010)]
        obj=hero.panel(bpy,'June_Shirt_Collar_'+side,collar,plaid,rig,thickness=.003)
        common.rest_attributes(obj)
        strap_points=[]
        for r in range(21):
            z=1.808+.365*r/20
            center=.143+.013*r/20
            for c in range(3):
                strap_points.append(v5.front_project(shirt_surface,sign*(center+(c-1)*.015),z,.015))
        strap=cloth_grid(bpy,'June_Overall_Strap_'+side,strap_points,3,overall,rig,bib)
        p=v5.front_project(shirt_surface,sign*.143,1.827,.019)
        button=base._sphere(bpy,'June_V6_Overall_Button_'+side,p,(.012,.004,.012),brass,segments=24,rings=12)
        base._parent_to_bone(button,rig,'torso')
        corners=[p+Vector((dx,-.002,dz)) for dx,dz in ((-.016,-.015),(.016,-.015),(.016,.015),(-.016,.015),(-.016,-.015))]
        hero.curves(bpy,'June_Overall_Buckle_'+side,[corners],brass,.0022,rig,'torso')
    return {'joined_shirt_neckline':True,'bib_construction':'fitted quad cloth surface with pelvis/torso skinning',
            'bib_patch_clearance':.004,'cloth_simulation':False}


def materials(bpy):
    # Deep, slightly varied indigo reads as workwear under the existing lights.
    for name,dark,light in [('denim',(.013,.028,.041,1),(.044,.078,.106,1)),
                            ('overalls',(.009,.016,.023,1),(.030,.047,.064,1))]:
        mat=bpy.data.materials['June v9 '+name]
        ramp=next(n for n in mat.node_tree.nodes if n.type=='VALTORGB')
        ramp.color_ramp.elements[0].color=dark;ramp.color_ramp.elements[-1].color=light
    mat=bpy.data.materials['June v9 plaid'];nodes,links=mat.node_tree.nodes,mat.node_tree.links
    nodes.clear();bs=nodes.new('ShaderNodeBsdfPrincipled');out=nodes.new('ShaderNodeOutputMaterial')
    links.new(bs.outputs[0],out.inputs['Surface'])
    attr=nodes.new('ShaderNodeAttribute');attr.attribute_name='june_rest'
    xyz=nodes.new('ShaderNodeSeparateXYZ');links.new(attr.outputs['Vector'],xyz.inputs[0])
    bands=[]
    for axis in ('X','Z'):
        scale=nodes.new('ShaderNodeMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=16
        links.new(xyz.outputs[axis],scale.inputs[0])
        repeat=nodes.new('ShaderNodeMath');repeat.operation='PINGPONG';repeat.inputs[1].default_value=.5
        links.new(scale.outputs[0],repeat.inputs[0])
        band=nodes.new('ShaderNodeMapRange');band.clamp=True
        band.inputs['From Min'].default_value=.31;band.inputs['From Max'].default_value=.34
        links.new(repeat.outputs[0],band.inputs['Value']);bands.append(band)
    cross=nodes.new('ShaderNodeMath');cross.operation='ADD'
    for i,band in enumerate(bands):links.new(band.outputs[0],cross.inputs[i])
    half=nodes.new('ShaderNodeMath');half.operation='MULTIPLY';half.inputs[1].default_value=.5
    links.new(cross.outputs[0],half.inputs[0])
    color=nodes.new('ShaderNodeValToRGB');color.color_ramp.elements[0].position=0.
    color.color_ramp.elements[0].color=(.020,.032,.045,1)
    color.color_ramp.elements[1].position=1.;color.color_ramp.elements[1].color=(.102,.126,.137,1)
    middle=color.color_ramp.elements.new(.5);middle.color=(.050,.070,.081,1)
    links.new(half.outputs[0],color.inputs[0]);links.new(color.outputs['Color'],bs.inputs['Base Color'])
    noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=600
    links.new(attr.outputs['Vector'],noise.inputs['Vector'])
    bump=nodes.new('ShaderNodeBump');bump.inputs['Distance'].default_value=.0005;bump.inputs['Strength'].default_value=.18
    links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bs.inputs['Normal'])
    bs.inputs['Roughness'].default_value=.83;bs.inputs['Sheen Weight'].default_value=.16


def relax_and_rebake(bpy,rig):
    rig['ce_hand_rest_offset_L']=[.10,0.,-.10]
    rig['ce_hand_rest_offset_R']=[-.10,.018,-.085]
    rig['ce_finger_relax_degrees']=[19.,25.,30.,34.,22.]
    rig['ce_finger_distal_fraction']=.62
    rig['ce_thumb_adduction_degrees']=22.
    hidden=[o for o in bpy.data.objects if o.type in {'MESH','CURVE'} and not o.hide_viewport]
    for obj in hidden:obj.hide_viewport=True
    rig.animation_data_create();catalog=[]
    for label in ('Listen','Explain','Skeptical','Chuckle','Point','Reach','Walk_Two_Steps','Stand'):
        action=bpy.data.actions['June_Studio_'+label]
        for curve in list(action.fcurves):action.fcurves.remove(curve)
        rig.animation_data.action=action;walk=label=='Walk_Two_Steps';frames=120 if walk else 90
        for frame in range(1,frames+1):
            amount=math.sin(math.pi*(frame-1)/(frames-1))**2
            if label=='Chuckle':amount*=math.sin(frame*.47)
            studio.body_pose(rig,150+frame if walk else 270,label.lower(),amount)
            for name in ('pelvis','hand_ik.L','hand_ik.R','foot_ik.L','foot_ik.R'):
                rig.pose.bones[name].keyframe_insert('location',frame=frame)
            for name in ('head','torso'):rig.pose.bones[name].keyframe_insert('rotation_euler',frame=frame)
        for curve in action.fcurves:
            for key in curve.keyframe_points:key.interpolation='LINEAR'
        action['ce_rig_version']='studio-v6';catalog.append(action.name)
    rig.animation_data.action=None
    for obj in hidden:obj.hide_viewport=False
    studio.body_pose(rig,270)
    return {'left_rest_offset':list(rig['ce_hand_rest_offset_L']),
            'right_rest_offset':list(rig['ce_hand_rest_offset_R']),
            'thumb_adduction_degrees':rig['ce_thumb_adduction_degrees'],
            'rebaked_body_actions':catalog,'existing_foot_and_speech_clock_preserved':True}


def main():
    import bpy,mathutils
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    p.add_argument('--views',default='body,close');p.add_argument('--width',type=int,default=1280)
    p.add_argument('--samples',type=int,default=32);p.add_argument('--threads',type=int,default=6)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    source,output=Path(args.source).resolve(),Path(args.output).resolve();receipt=checked_source(source,output)
    if bpy.app.version_string!='4.2.0':raise ValueError('this candidate requires Blender 4.2.0')
    bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
    rig=bpy.data.objects['June_Oxley_Rig'];scene=bpy.context.scene;head=bpy.data.objects['June_Head']
    rig.data.pose_position='REST'
    for key in head.data.shape_keys.key_blocks:key.value=0
    bpy.context.view_layer.update();existing=set(bpy.data.objects)
    print('Refining likeness and groom',flush=True);face=likeness(bpy,rig);groom=soften_groom(bpy)
    print('Refining sleeve volume and garment construction',flush=True)
    fabric=fitted_fabric(bpy,rig);garments=wardrobe(bpy,rig);materials(bpy)
    rig.data.pose_position='POSE'
    print('Rebaking relaxed asset poses',flush=True);pose=relax_and_rebake(bpy,rig)
    collection=bpy.data.collections[receipt['character_collection']];collection.name='June_Character_Studio_v6'
    for obj in set(bpy.data.objects)-existing:
        if obj.name not in collection.objects:collection.objects.link(obj)
        for owner in list(obj.users_collection):
            if owner!=collection:owner.objects.unlink(obj)
    rig['ce_asset_version']='studio-v6-development';rig['ce_dialogue_ready']=False
    rig['ce_art_status']='development_not_identity_approved';scene['ce_production_approved']=False
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=args.samples
    scene.cycles.use_denoising=True;scene.cycles.max_bounces=6
    scene.render.threads_mode='FIXED';scene.render.threads=args.threads
    scene.render.resolution_x=args.width;scene.render.resolution_y=args.width*9//16
    scene.render.resolution_percentage=100;scene.render.use_persistent_data=True
    scene.render.image_settings.file_format='PNG';scene.camera=bpy.data.objects['June_Camera_Body']
    studio.aim_control(rig,'gaze',scene.camera.location);scene.frame_set(1)
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
    result={'asset_version':'studio-v6','asset_sha256':sha256(output),'source_asset_sha256':sha256(source),
            'source_version':'studio-v5','blender_version':bpy.app.version_string,
            'refinement_sha256':sha256(__file__),'body_pose_sha256':sha256(studio.__file__),
            'character_collection':collection.name,'set_collection':receipt['set_collection'],
            'cameras':receipt['cameras'],'source_assets':receipt.get('source_assets',{}),
            'face_report':face,'groom_report':groom,'fabric_report':fabric,'wardrobe_report':garments,'pose_report':pose,
            'packed_images':[i.name for i in bpy.data.images if i.packed_file],
            'production_approved':False,'dialogue_quality_approved':False,'art_decision':'unreviewed',
            'validation_status':'awaiting evaluated asset audit and visual review'}
    atomic_json(output.with_suffix('.json'),result)
    views={'body':('Body',{'smile':.28,'warm_eyes':.30}),
           'close':('Close',{'smile':.28,'warm_eyes':.30}),'front':('Front',{}),
           'smile':('Close',{'smile':.65,'warm_eyes':.40}),
           'blink':('Close',{'blink_L':1.,'blink_R':1.}),'speech-d':('Close',{'D':1.})}
    for label in filter(None,args.views.split(',')):
        camera,values=views[label]
        for key in head.data.shape_keys.key_blocks:key.value=values.get(key.name,0)
        scene.camera=bpy.data.objects['June_Camera_'+camera];studio.aim_control(rig,'gaze',scene.camera.location)
        scene.render.filepath=str(output.parent/(label+'.png'))
        print('Rendering v6 '+label,flush=True);bpy.ops.render.render(write_still=True)
    print(json.dumps({'asset':str(output),'asset_sha256':result['asset_sha256'],'review':'unreviewed'}),flush=True)


if __name__=='__main__':main()
