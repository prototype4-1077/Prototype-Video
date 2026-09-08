"""Build one editable, packed .blend library for June, performances and porch."""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from pipeline.blender import render_vertical_slice as base
from pipeline.blender import june_studio_character as character
from pipeline.june_world_motion import sample, ease
from pipeline.june_studio import sha256, atomic_json


def aim_control(rig, name, position):
    from mathutils import Vector
    bone=rig.pose.bones[name]
    bone.location=bone.bone.matrix_local.to_3x3().inverted() @ (Vector(position)-bone.bone.head_local)


def configure_controls(bpy,rig):
    from mathutils import Vector
    bpy.context.view_layer.update()
    sole=bpy.data.objects['June_Boot_Sole_L']
    evaluated=sole.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    low=min((evaluated.matrix_world @ v.co).z for v in mesh.vertices);evaluated.to_mesh_clear()
    dz=.09-low
    root=rig.pose.bones['root']
    root.location=root.bone.matrix_local.to_3x3().inverted() @ Vector((0,0,dz))
    rig['ce_ground_offset']=dz
    for side in ('L','R'):
        for owner,kind,label in (('shin.','foot','Leg'),('forearm.','hand','Arm')):
            constraint=rig.pose.bones[owner+side].constraints.get('CE_'+label+'_IK_'+side)
            constraint.target=rig;constraint.subtarget=kind+'_ik.'+side
            constraint.pole_target=None;constraint.influence=1;constraint.use_stretch=False
            rig.pose.bones[owner+side].ik_stretch=0
        control=rig.pose.bones['foot_ik.'+side]
        control.rotation_euler=(control.bone.matrix_local.to_3x3().inverted() @ rig.data.bones['foot.'+side].matrix_local.to_3x3()).to_euler()
        constraint=rig.pose.bones['foot.'+side].constraints.new('COPY_ROTATION')
        constraint.name='Studio planted foot orientation';constraint.target=rig;constraint.subtarget='foot_ik.'+side
        constraint.target_space='WORLD';constraint.owner_space='WORLD'
    return dz


def body_pose(rig, source_frame=270, gesture='listen', amount=0):
    from mathutils import Vector
    state=sample(source_frame);dz=rig['ce_ground_offset']
    pelvis=rig.pose.bones['pelvis']
    pelvis.location=pelvis.bone.matrix_local.to_3x3().inverted() @ Vector(state['pelvis_offset'])
    for side in ('L','R'):
        point=Vector(state['feet'][side][0])+Vector((0,0,dz))
        aim_control(rig,'foot_ik.'+side,point)
        hand=Vector(state['hand.'+side])+Vector((0,0,dz))
        if side=='L' and gesture=='explain':hand+=Vector((-.07,-.13,.19))*amount
        if side=='R' and gesture=='point':hand+=Vector((.10,-.24,.27))*amount
        if side=='R' and gesture=='reach':hand+=Vector((.16,-.30,.06))*amount
        aim_control(rig,'hand_ik.'+side,hand)
        for digit in range(5):
            names=(f'finger.{digit}.{side}',f'finger_tip.{digit}.{side}') if digit<4 else ('thumb.'+side,'thumb_tip.'+side)
            for name in names:
                rig.pose.bones[name].rotation_euler.x=math.radians(8 if digit<4 else 12)
    head=rig.pose.bones['head'];head.rotation_euler=(0,0,0)
    torso=rig.pose.bones['torso'];torso.rotation_euler=(0,0,0)
    if gesture=='skeptical':head.rotation_euler.z=.045*amount;head.rotation_euler.y=.08*amount
    if gesture=='chuckle':head.rotation_euler.x=.03*amount;torso.rotation_euler.x=.007*amount
    if gesture=='listen':head.rotation_euler.z=-.016*amount


def save_actions(bpy, rig, head):
    catalog=[]
    rig.animation_data_create()
    names=('Listen','Explain','Skeptical','Chuckle','Point','Reach','Walk_Two_Steps','Stand')
    for label in names:
        action=bpy.data.actions.new('June_Studio_'+label);action.use_fake_user=True
        rig.animation_data.action=action
        walk=label=='Walk_Two_Steps';frames=120 if walk else 90
        for frame in range(1,frames+1):
            amount=math.sin(math.pi*(frame-1)/(frames-1))**2
            if label=='Chuckle':amount*=math.sin(frame*.47)
            body_pose(rig,150+frame if walk else 270,label.lower(),amount)
            for name in ('pelvis','hand_ik.L','hand_ik.R','foot_ik.L','foot_ik.R'):
                rig.pose.bones[name].keyframe_insert('location',frame=frame)
            for name in ('head','torso'):
                rig.pose.bones[name].keyframe_insert('rotation_euler',frame=frame)
        for curve in action.fcurves:
            for point in curve.keyframe_points:point.interpolation='LINEAR'
        action.asset_mark();action.asset_data.description='Reusable June '+label.replace('_',' ').lower()+'. Development performance; contact and acting require shot review.'
        action['ce_rig_version']='studio-v1';action['ce_action_kind']='body_clip'
        catalog.append({'name':action.name,'kind':'body_clip','frames':frames,'fps':30})
    rig.animation_data.action=None
    # Single-frame facial pose assets can be blended in Blender's Asset Browser.
    keys=head.data.shape_keys;keys.animation_data_create()
    for label in character.EXPRESSIONS:
        action=bpy.data.actions.new('June_Face_'+label);action.use_fake_user=True;keys.animation_data.action=action
        for name in character.EXPRESSIONS:
            key=keys.key_blocks[name];key.value=float(name==label);key.keyframe_insert('value',frame=1)
        action.asset_mark();action.asset_data.description='June facial pose: '+label
        catalog.append({'name':action.name,'kind':'face_pose','frames':1,'fps':30})
    keys.animation_data.action=None
    for key in keys.key_blocks:key.value=0
    body_pose(rig,150)
    return catalog


def porch(bpy,mathutils,tools):
    wood=base._material(bpy,'Studio weathered wood',(.15,.10,.058,1),roughness=.86)
    nodes=wood.node_tree.nodes;links=wood.node_tree.links;bs=nodes.get('Principled BSDF')
    image=bpy.data.images.load(str(Path(tools)/'porch_wood.jpg'));image.pack()
    texture=nodes.new('ShaderNodeTexImage');texture.image=image;texture.projection='BOX';texture.projection_blend=.12
    coordinates=nodes.new('ShaderNodeTexCoord');links.new(coordinates.outputs['Generated'],texture.inputs['Vector'])
    links.new(texture.outputs['Color'],bs.inputs['Base Color'])
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.22;bump.inputs['Distance'].default_value=.004
    links.new(texture.outputs['Color'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bs.inputs['Normal'])
    paint=base._material(bpy,'Studio faded sage paint',(.035,.064,.053,1),roughness=.8)
    dark=base._material(bpy,'Studio dark timber',(.034,.021,.012,1),roughness=.78)
    cream=base._material(bpy,'Studio aged trim',(.31,.27,.18,1),roughness=.78)
    metal=base._material(bpy,'Studio iron',(.025,.029,.026,1),roughness=.45)
    metal.node_tree.nodes.get('Principled BSDF').inputs['Metallic'].default_value=.72
    enamel=base._material(bpy,'Studio enamel',(.52,.43,.26,1),roughness=.3)
    coffee=base._material(bpy,'Studio coffee',(.012,.005,.002,1),roughness=.19)
    def box(name,location,size,material=wood,bevel=.012):
        return base._box(bpy,'Porch_'+name,location,size,material,bevel=bevel)
    box('Foundation',(0,-.40,-.20),(8.5,6.2,.54),dark)
    for i in range(34):
        board=box('Floor_'+str(i),(-4.125+i*.25,-.4,.065),(.243,6.2,.05))
        board['ce_surface']='Poly Haven wood_planks_dirt, CC0'
    # A continuous back wall with real door/window frames; all boxes use full dimensions.
    box('Wall',(0,2.53,2.32),(8.5,.24,4.5),paint)
    for row in range(23):box('Siding_'+str(row),(0,2.39,.18+row*.19),(8.5,.035,.177),paint,bevel=.005)
    for x in (-4.04,4.04):
        box('Post_'+str(x),(x,-2.76,2.41),(.20,.20,4.65),cream)
        box('Side_Rail_'+str(x),(x,-.11,1.40),(.15,5.2,.15),cream)
        for i in range(17):box('Baluster_'+str(x)+'_'+str(i),(x,-2.53+i*.30,.74),(.065,.065,1.2),cream)
    box('Roof_Beam',(0,-2.76,4.69),(8.6,.25,.24),dark)
    box('Ceiling',(0,-.1,4.92),(8.7,6.0,.18),dark)
    box('Door',(-2.13,2.35,1.61),(1.40,.16,3.05),wood)
    for x in (-2.90,-1.36):box('Door_Frame_'+str(x),(x,2.22,1.64),(.13,.13,3.23),cream)
    box('Door_Lintel',(-2.13,2.22,3.24),(1.67,.13,.15),cream)
    base._sphere(bpy,'Porch_Door_Knob',(-1.55,2.14,1.52),(.045,.045,.045),metal,segments=24,rings=12)
    glass=base._material(bpy,'Studio window glass',(.043,.072,.088,1),roughness=.16)
    glass.node_tree.nodes.get('Principled BSDF').inputs['Metallic'].default_value=.45
    box('Window',(1.45,2.31,2.57),(1.6,.05,1.60),glass)
    for x in (.58,1.45,2.32):box('Window_V_'+str(x),(x,2.21,2.57),(.065,.12,1.81),cream)
    for z in (1.69,2.57,3.45):box('Window_H_'+str(z),(1.45,2.21,z),(1.81,.12,.065),cream)
    # Chair and table are complete structures, with their legs touching the floor.
    cx,cy=-1.25,.20
    box('Chair_Seat',(cx,cy,.93),(.74,.75,.10),dark)
    for x in (cx-.29,cx+.29):
        for y in (cy-.29,cy+.29):box('Chair_Leg_'+str(x)+str(y),(x,y,.51),(.07,.07,.84),dark)
        box('Chair_Back_Post_'+str(x),(x,cy+.31,1.40),(.07,.07,1.12),dark)
    for z in (1.25,1.50,1.75):box('Chair_Back_'+str(z),(cx,cy+.31,z),(.61,.055,.16),wood)
    tx,ty=1.03,-1.30
    box('Table_Top',(tx,ty,1.59),(.85,.78,.12))
    for x in (tx-.32,tx+.32):
        for y in (ty-.29,ty+.29):box('Table_Leg_'+str(x)+str(y),(x,y,.82),(.07,.07,1.46),dark)
    mug=base._cylinder(bpy,'Porch_Mug',(tx,ty,1.76),.102,.20,enamel,vertices=48)
    base._cylinder(bpy,'Porch_Coffee',(tx,ty,1.862),.088,.005,coffee,vertices=48)
    base._curve(bpy,'Porch_Mug_Handle',[(tx+.09,ty,1.82),(tx+.18,ty,1.81),(tx+.18,ty,1.69),(tx+.09,ty,1.69)],enamel,bevel_depth=.013)
    # Warm practical lamp and its visible housing.
    lamp=base._material(bpy,'Studio lantern glass',(.62,.25,.048,1),roughness=.35)
    lamp.node_tree.nodes.get('Principled BSDF').inputs['Emission Color'].default_value=(1,.35,.06,1)
    lamp.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=1.2
    box('Lantern_Glass',(-.80,2.13,2.86),(.21,.16,.32),lamp)
    for z in (2.66,3.06):box('Lantern_Cap_'+str(z),(-.80,2.13,z),(.30,.23,.07),metal)
    base._add_area_light(bpy,mathutils,'Porch_Lantern_Light',(-.80,1.96,2.90),22,(1,.48,.20),.5,(0,-1,2.6))
    world=bpy.data.worlds.new('June packed Poly Haven daylight');bpy.context.scene.world=world;world.use_nodes=True
    wn=world.node_tree.nodes;wl=world.node_tree.links
    sky=bpy.data.images.load(str(Path(tools)/'porch_sky.hdr'));sky.pack()
    env=wn.new('ShaderNodeTexEnvironment');env.image=sky;wl.new(env.outputs['Color'],wn.get('Background').inputs[0])
    wn.get('Background').inputs['Strength'].default_value=.20
    base._add_area_light(bpy,mathutils,'Porch_Key',(-4,-4,6),650,(1,.90,.78),4,(0,-1,2.5))
    base._add_area_light(bpy,mathutils,'Porch_Fill',(4,-1,4),180,(.65,.78,1),4,(0,-1,2.2))
    cameras={}
    for name,location,target,lens in (
        ('Wide',(-4.4,-8.8,4.1),(0,-.5,1.9),47),
        ('Close',(-1.20,-4.15,3.22),(.035,-1.06,2.88),58),
        ('Front',(.13,-4.5,3.12),(.035,-1.06,2.87),62)):
        camera=bpy.data.objects.new('June_Camera_'+name,bpy.data.cameras.new('June_Camera_'+name));bpy.context.scene.collection.objects.link(camera)
        camera.location=location;camera.data.lens=lens;base._look_at(camera,target,mathutils);cameras[name]=camera
    return cameras


def main():
    import bpy,mathutils
    parser=argparse.ArgumentParser()
    parser.add_argument('--tools',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--review',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    output=Path(args.output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    base._clear(bpy)
    print('Building June studio character',flush=True)
    rig,head=character.build(bpy,mathutils)
    for obj in list(bpy.data.objects):
        if not obj.name.startswith('June_'):bpy.data.objects.remove(obj,do_unlink=True)
    configure_controls(bpy,rig)
    print('Authoring reusable performance assets',flush=True)
    catalog=save_actions(bpy,rig,head)
    print('Assembling packed porch set',flush=True)
    cameras=porch(bpy,mathutils,args.tools)
    body_pose(rig,270)
    aim_control(rig,'gaze',cameras['Close'].location)
    character_collection=bpy.data.collections.new('June_Character_Studio_v1')
    set_collection=bpy.data.collections.new('June_Porch_Studio_v1')
    scene=bpy.context.scene
    for collection in (character_collection,set_collection):scene.collection.children.link(collection);collection.asset_mark()
    for obj in list(scene.objects):
        collection=character_collection if obj.name.startswith('June_') and obj.type!='CAMERA' else set_collection
        for old in list(obj.users_collection):old.objects.unlink(obj)
        collection.objects.link(obj)
    scene.camera=cameras['Close'];scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
    scene.render.use_persistent_data=True;scene.render.fps=30;scene.frame_start=1;scene.frame_end=450
    scene.render.resolution_x=960;scene.render.resolution_y=540;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Medium High Contrast'
    scene['ce_asset_library']=True;scene['ce_production_approved']=False
    scene['ce_dependencies_packed']=True
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
    repo=Path(__file__).resolve().parents[2]
    inputs=['pipeline/blender/june_studio_assets.py','pipeline/blender/june_studio_character.py',
            'pipeline/blender/june_hero_v9.py','pipeline/blender/june_anatomy_source.py','pipeline/blender/render_vertical_slice.py',
            'pipeline/june_world_motion.py','concept/characters/assets/june_anatomy_cc0.json.gz',
            'concept/characters/assets/june_expression_cc0.json.gz','concept/characters/june_studio_sources_v1.json']
    receipt={'asset_sha256':sha256(output),'source_sha256':{p:sha256(repo/p) for p in inputs},
             'production_approved':False,'dialogue_quality_approved':False,'asset_version':'studio-v1',
             'blender_version':bpy.app.version_string,'actions':catalog,'cameras':list(cameras),
             'facial_shapes':list(character.EXPRESSIONS),'packed_images':[i.name for i in bpy.data.images if i.packed_file],
             'coat_faces':len(bpy.data.objects['June_Continuous_Coat'].data.polygons)}
    atomic_json(output.with_suffix('.json'),receipt)
    if args.review:
        for name in ('Close','Front','Wide'):
            scene.camera=cameras[name];aim_control(rig,'gaze',cameras[name].location)
            scene.render.filepath=str(output.parent/(name.lower()+'.png'));bpy.ops.render.render(write_still=True)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
