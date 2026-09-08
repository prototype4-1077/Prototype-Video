"""Reproducible neutral-light review of the opt-in June v9 sculpture."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from pipeline.blender import render_vertical_slice as studio
from pipeline.blender import june_hero_v9


def main():
    import bpy,mathutils
    from mathutils import Vector
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',required=True)
    parser.add_argument('--width',type=int,default=960)
    parser.add_argument('--samples',type=int,default=48)
    parser.add_argument('--views',default='front,three_quarter,profile,back,full')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    allowed={'front','three_quarter','profile','back','full','hand'}
    views=args.views.split(',')
    if not set(views)<=allowed:raise ValueError('unknown review view')
    if args.width<320 or args.width%32:raise ValueError('width must be a multiple of 32 >=320')
    if args.samples<1:raise ValueError('positive samples required')
    out=Path(args.output_dir).resolve()
    if out.exists() and any(out.iterdir()):raise FileExistsError('use a fresh review directory')
    out.mkdir(parents=True,exist_ok=True)
    studio._clear(bpy)
    rig,mouth,face=june_hero_v9.build(bpy,mathutils)
    for o in list(bpy.data.objects):
        if o.get('ce_prop_role') or o.name.startswith('Performance_Table'):
            bpy.data.objects.remove(o,do_unlink=True)
    scene=bpy.context.scene
    # Reuse the validated walking rig interface; pose geometry for standing review.
    pelvis=rig.pose.bones['pelvis']
    pelvis.location=pelvis.bone.matrix_local.to_3x3().inverted() @ Vector((0,-.43,.30))
    rig.pose.bones['gaze'].location=rig.data.bones['gaze'].matrix_local.to_3x3().inverted() @ Vector((0,0,.30))
    for side,sign in (('L',-1),('R',1)):
        for kind,owner,position in (
            ('foot','shin.',(sign*.22,-.60,.34)),
            ('hand','forearm.',(sign*.425,-.49,1.63))):
            target=bpy.data.objects.new('Review_'+kind+'_'+side,None);scene.collection.objects.link(target)
            target.location=position
            con=rig.pose.bones[owner+side].constraints.get('CE_'+('Leg' if kind=='foot' else 'Arm')+'_IK_'+side)
            con.target=target;con.subtarget='';con.pole_target=None;con.influence=1.;con.use_stretch=False
            if kind=='foot':
                rot=rig.pose.bones['foot.'+side].constraints.new('COPY_ROTATION')
                rot.target=target;rot.target_space='WORLD';rot.owner_space='WORLD'
                target.rotation_euler=rig.data.bones['foot.'+side].matrix_local.to_euler()
    bpy.context.view_layer.update()
    ground=studio._material(bpy,'Review Studio Warm Grey',(.075,.084,.085,1),roughness=.82)
    studio._box(bpy,'Review_Floor',(0,0,.118),(200,200,.1),ground)
    studio._box(bpy,'Review_Backdrop',(0,4,5),(30,.1,15),ground)
    world=bpy.data.worlds.new('Review_World');scene.world=world;world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.13,.16,.19,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.35
    studio._add_area_light(bpy,mathutils,'Review_Key',(-3,-4,6),550,(1,.85,.69),3,(0,-.43,2.6))
    studio._add_area_light(bpy,mathutils,'Review_Fill',(3,-2,3.7),230,(.66,.80,1),3,(0,-.43,2.6))
    studio._add_area_light(bpy,mathutils,'Review_Rim',(1,2,5),700,(1,.86,.66),2.5,(0,-.43,2.6))
    camera=bpy.data.objects.new('Review_Camera',bpy.data.cameras.new('Review_Camera'))
    scene.collection.objects.link(camera);scene.camera=camera
    camera.data.type='ORTHO';camera.data.ortho_scale=1.42
    scene.render.engine='CYCLES';scene.cycles.samples=args.samples
    scene.cycles.use_denoising=args.samples>=8
    scene.render.use_persistent_data=True
    scene.render.resolution_x=args.width;scene.render.resolution_y=args.width
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Medium High Contrast'
    scene.render.film_transparent=False
    positions={
        'front':((0,-5,2.93),(0,-.43,2.79),1.42),
        'three_quarter':((-3.3,-4.5,2.96),(0,-.43,2.79),1.42),
        'profile':((-5,-.43,2.93),(0,-.43,2.79),1.42),
        'back':((0,5,2.93),(0,-.43,2.79),1.42),
        'full':((-2.9,-7,2.85),(0,-.39,1.79),3.57),
        'hand':((1.0,-3,1.6),(.43,-.49,1.54),.45),
    }
    for name in views:
        location,target,scale=positions[name]
        camera.location=location;camera.data.ortho_scale=scale;studio._look_at(camera,target,mathutils)
        backdrop=bpy.data.objects['Review_Backdrop']
        backdrop.hide_render=name=='back';backdrop.hide_viewport=name=='back'
        bpy.context.view_layer.update()
        direction=(Vector(target)-camera.location).normalized()
        hit,point,normal,index,visible_object,matrix=scene.ray_cast(bpy.context.evaluated_depsgraph_get(),camera.location,direction)
        if not hit or not visible_object.name.startswith('June_'):
            raise RuntimeError(f'{name} view is not centered on the character; refusing an occluded review')
        scene.render.filepath=str(out/(name+'.png'))
        bpy.ops.render.render(write_still=True)
    bpy.data.objects['Review_Backdrop'].hide_render=False
    bpy.data.objects['Review_Backdrop'].hide_viewport=False
    camera.location=positions['three_quarter'][0];camera.data.ortho_scale=1.42
    studio._look_at(camera,positions['three_quarter'][1],mathutils)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'june-character-v9.blend'))
    repo=Path(__file__).resolve().parents[2]
    inputs=['pipeline/blender/june_hero_v9.py','pipeline/blender/june_anatomy_source.py',
            'pipeline/blender/render_vertical_slice.py','pipeline/blender/render_june_hero_review.py',
            'concept/characters/assets/june_anatomy_cc0.json.gz',
            'concept/characters/assets/june_anatomy_cc0_provenance.json']
    report={'asset':'june_v9_development','production_approved':False,'identity_approved':False,
            'dialogue_ready':False,'render_engine':'CYCLES','samples':args.samples,
            'dimensions':[args.width,args.width],'views':views,
            'source_sha256':{p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in inputs},
            'image_sha256':{v:hashlib.sha256((out/(v+'.png')).read_bytes()).hexdigest() for v in views},
            'geometry':{'mesh_objects':sum(o.type=='MESH' and o.name.startswith('June_') for o in bpy.data.objects),
                        'curve_objects':sum(o.type=='CURVE' and o.name.startswith('June_') for o in bpy.data.objects),
                        'bones':len(rig.data.bones)},
            'unverified':['likeness against canonical art','extreme facial shapes','speech','cloth contacts','full performance appeal']}
    (out/'character-review.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__=='__main__':main()
