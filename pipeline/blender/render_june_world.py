"""Isolated 3D June movement proof; never mutates accepted image masters.

Run with Blender 4.2: --background --python this_file -- --output-dir ...
The inherited procedural v8 mesh is explicitly a development asset. The proof
reports evaluated bone/mesh evidence separately from unverified human quality.
"""
from pathlib import Path
import argparse, hashlib, json, math, sys, time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from pipeline.june_world_motion import sample, audit_evaluated, FRAMES, FPS, BEATS
from pipeline.blender import render_vertical_slice as studio


def main():
    import bpy, mathutils
    from mathutils import Vector, Matrix
    p=argparse.ArgumentParser()
    p.add_argument('--output-dir',required=True)
    p.add_argument('--frames',default='1,95,135,173,233,293,353,450,510,555,625,720')
    p.add_argument('--engine',choices=['CYCLES','BLENDER_WORKBENCH'],default='CYCLES')
    p.add_argument('--width',type=int,default=960)
    p.add_argument('--samples',type=int,default=16)
    p.add_argument('--asset',choices=['v8','v9'],default='v8')
    p.add_argument('--animate',action='store_true')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=Path(args.output_dir).resolve()
    if out.exists() and any(out.iterdir()):raise FileExistsError('Use a fresh proof directory; existing evidence is preserved')
    if args.width < 320 or args.width % 32:raise ValueError('width must be a multiple of 32, at least 320')
    if args.samples < 1:raise ValueError('samples must be positive')
    if any(not 1 <= int(v) <= FRAMES for v in args.frames.split(',') if v.strip()):raise ValueError('review frame outside 1..720')
    out.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    print(f'Building {args.asset} movement audition',flush=True)
    repo=Path(__file__).resolve().parents[2]
    inputs=['pipeline/blender/render_june_world.py','pipeline/june_world_motion.py','pipeline/blender/render_vertical_slice.py']
    if args.asset=='v9':inputs+=['pipeline/blender/june_hero_v9.py','pipeline/blender/june_anatomy_source.py',
                               'concept/characters/assets/june_anatomy_cc0.json.gz']
    source_hashes={name:hashlib.sha256((repo/name).read_bytes()).hexdigest() for name in inputs}
    studio._clear(bpy)
    mats=studio._make_materials(bpy,asset_major=8)
    studio._make_porch(bpy,mathutils,mats,FRAMES)
    if args.asset=='v9':
        from pipeline.blender import june_hero_v9
        rig,mouth,face=june_hero_v9.build(bpy,mathutils,mats)
    else:
        rig,mouth,face=studio._make_june(bpy,mathutils,mats,asset_major=8)
    # Remove legacy staged duplicate props; this shot owns ONE mug throughout.
    for obj in list(bpy.data.objects):
        if obj.get('ce_prop_role') or obj.name.startswith('Performance_Table'):
            bpy.data.objects.remove(obj,do_unlink=True)
    # Inherited boxes use full dimensions. Cover the gaps between legacy planks
    # with a continuous receiver so feet never stand over empty air.
    studio._box(bpy,'World_Porch_Receiver',(0,-.20,.035),(7.4,5.7,.04),mats['dark_wood'])
    for i in range(30):
        studio._box(bpy,f'World_Board_{i}',(-3.55+i*.245,-.20,.065),(.239,5.7,.025),mats['cedar'],bevel=.006)
    # Foot mesh grounding is calibrated from the evaluated v8 sole in rest pose.
    scene=bpy.context.scene
    scene.frame_start=1;scene.frame_end=FRAMES;scene.render.fps=FPS
    bpy.context.view_layer.update()
    soles=[o for o in bpy.data.objects if 'Sole' in o.name or 'sole' in o.name]
    if not soles: raise RuntimeError('missing sole meshes; cannot verify contact')
    def mesh_points(o):
        dep=bpy.context.evaluated_depsgraph_get(); ev=o.evaluated_get(dep)
        mesh=ev.to_mesh()
        pts=[ev.matrix_world @ v.co for v in mesh.vertices]
        ev.to_mesh_clear();return pts
    base_sole=min(p.z for o in soles for p in mesh_points(o))
    ground=.0775
    dz=ground-base_sole
    # Shift complete rig + unparented skinned objects via root pose, while IK
    # targets are expressed in the resulting global space.
    root=rig.pose.bones['root'];root.location= root.bone.matrix_local.to_3x3().inverted() @ Vector((0,0,dz))
    # World-space control targets independent of the moving pelvis.
    targets={}
    for side in ('L','R'):
        for kind,owner in [('foot',f'shin.{side}'),('hand',f'forearm.{side}')]:
            e=bpy.data.objects.new(f'World_{kind}_{side}',None);scene.collection.objects.link(e)
            targets[f'{kind}.{side}']=e
            con=rig.pose.bones[owner].constraints.get(f'CE_{"Leg" if kind=="foot" else "Arm"}_IK_{side}')
            con.target=e;con.subtarget='';con.influence=1.;con.use_stretch=False
            # Preserve the rest bend plane, allowing the solver to choose the
            # nearest solution without the inherited mismatched pole angle.
            con.pole_target=None
            rig.pose.bones[owner].ik_stretch=0
            rig.pose.bones['thigh.'+side if kind=='foot' else 'upper_arm.'+side].ik_stretch=0
    bpy.context.view_layer.update()
    pelvis=rig.pose.bones['pelvis']
    pelvis_rest=pelvis.bone.matrix_local.copy()
    # Keep boot orientation grounded while IK solves knees.
    for side in ('L','R'):
        c=rig.pose.bones['foot.'+side].constraints.new('COPY_ROTATION')
        c.name='World_Foot_Level';c.target=targets['foot.'+side]
        c.target_space='WORLD';c.owner_space='WORLD'
        targets['foot.'+side].rotation_euler=rig.data.bones['foot.'+side].matrix_local.to_euler()
    # One true 3D mug with an open rim and handle, attached without a cut.
    mug=bpy.data.objects.new('World_Mug',None);scene.collection.objects.link(mug)
    cup=studio._cylinder(bpy,'World_Mug_Body',(0,0,0),.085,.14,mats['enamel'],vertices=48)
    coffee=studio._cylinder(bpy,'World_Mug_Coffee',(0,0,.071),.074,.003,mats['coffee'],vertices=48)
    handle=studio._curve(bpy,'World_Mug_Handle',[(.076,0,.045),(.137,0,.05),(.148,0,-.04),(.079,0,-.049)],mats['enamel'],bevel_depth=.012)
    for o in (cup,coffee,handle):o.parent=mug
    mug_start=Vector((.54,-1.97,1.70+dz))
    mug.location=mug_start
    top=mug_start.z-.07
    studio._box(bpy,'World_Table_Top',(.64,-1.97,top-.035),(.40,.48,.07),mats['dark_wood'],bevel=.015)
    for x in (.49,.79):
        for y in (-2.15,-1.79):
            studio._cylinder_between(bpy,mathutils,f'World_Table_Leg_{x}_{y}',(x,y,ground),(x,y,top-.07),.035,mats['dark_wood'])
    # Move the chair receiver to the real rest pelvis height; old seating was
    # decorative proxy geometry, now the top is calibrated explicitly.
    seat=bpy.data.objects['Chair_Seat'];seat.location.z=1.10+dz
    # Camera coverage holds the feet, chair, hands and face in a continuous view.
    data=bpy.data.cameras.new('World_Camera');cam=bpy.data.objects.new('World_Camera',data);scene.collection.objects.link(cam)
    scene.camera=cam;data.lens=45
    studio._add_area_light(bpy,mathutils,'World_Key',(-4,-4,6),1100,(1,.78,.55),5,(0,-.6,1.6))
    studio._add_area_light(bpy,mathutils,'World_Fill',(4,-2,4),650,(.55,.72,1),4,(0,-1,1.5))
    studio._add_area_light(bpy,mathutils,'World_Rim',(0,2,5),900,(1,.52,.24),3,(0,-.5,2))
    scene.world.color=(.15,.18,.23)
    scene.render.engine=args.engine
    if args.engine=='CYCLES':
        scene.cycles.samples=args.samples;scene.cycles.use_denoising=args.samples>=8
        scene.render.use_persistent_data=True
    else:
        scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL'
        scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True
    scene.render.resolution_x=args.width;scene.render.resolution_y=round(args.width*9/16)
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX'
    # No invented speaking take: this is a silent mechanical audition. Mouth
    # remains neutral until exact approved June audio/cues are supplied later.
    for o in bpy.data.objects:
        if o.data and hasattr(o.data,'shape_keys') and o.data.shape_keys:
            for k in o.data.shape_keys.key_blocks:
                if k.name!='Basis':k.value=0
    if mouth.data.shape_keys and mouth.data.shape_keys.key_blocks.get('X'):
        mouth.data.shape_keys.key_blocks['X'].value=1
    # Control measurements have no dependency on skin, hair or cloth surfaces.
    # Suspend only those display meshes while evaluating IK, real soles and prop
    # transforms; restore every object's display state before visual inspection.
    hidden=[]
    for obj in bpy.data.objects:
        measured=obj.name.startswith(('June_Boot_','World_Table_Leg_','World_Mug'))
        if obj.type in {'MESH','CURVE'} and not measured and not obj.hide_viewport:
            hidden.append(obj);obj.hide_viewport=True
    bpy.context.view_layer.update()
    print(f'Control audit: {FRAMES} frames; detailed art is restored for rendering',flush=True)
    report=[];grip_bind=None
    for f in range(1,FRAMES+1):
        scene.frame_set(f);s=sample(f)
        # Pose-bone translation is in its rest local axes, not world XYZ.
        pelvis.location=pelvis_rest.to_3x3().inverted() @ Vector(s['pelvis_offset'])
        pelvis.keyframe_insert('location',frame=f)
        for side in ('L','R'):
            fp,contact=s['feet'][side]
            targets['foot.'+side].location=Vector(fp)+Vector((0,0,dz))
            targets['foot.'+side].keyframe_insert('location',frame=f)
            targets['hand.'+side].location=Vector(s['hand.'+side])+Vector((0,0,dz+s['chuckle']))
            targets['hand.'+side].keyframe_insert('location',frame=f)
            # Articulated fingers: selected v8 poses; separate contact QA still required.
            relaxed=studio._hand_pose_vector('relaxed');gripped=studio._hand_pose_vector('mug_grip')
            g=s['grip'] if side=='R' else 0.
            vals=tuple(a+(b-a)*g for a,b in zip(relaxed,gripped))
            for d in range(5):
                prefix=f'finger.{d}' if d<4 else 'thumb'
                tip=f'finger_tip.{d}' if d<4 else 'thumb_tip'
                for name,angle in [(prefix,vals[d*3]),(tip,vals[d*3+1])]:
                    b=rig.pose.bones[name+'.'+side];b.rotation_euler.x=math.radians(angle)
                    b.keyframe_insert('rotation_euler',frame=f)
        torso=rig.pose.bones['torso'];torso.rotation_euler.y=s['head_yaw']*.45;torso.keyframe_insert('rotation_euler',frame=f)
        head=rig.pose.bones['head'];head.rotation_euler.y=s['head_yaw']
        head.rotation_euler.x=s['chuckle']*2;head.keyframe_insert('rotation_euler',frame=f)
        bpy.context.view_layer.update()
        hand_matrix=rig.matrix_world @ rig.pose.bones['hand.R'].matrix
        if f==465:grip_bind=hand_matrix.inverted() @ Matrix.Translation(mug_start)
        mug.matrix_world=hand_matrix @ grip_bind if grip_bind is not None else Matrix.Translation(mug_start)
        mug.keyframe_insert('location',frame=f);mug.keyframe_insert('rotation_euler',frame=f)
        cam.location=(-4.7+.7*min(f/510,1),-9.6-.7*min(f/510,1),4.0)
        studio._look_at(cam,(0,-.65-.65*min(f/390,1),1.65),mathutils)
        cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_euler',frame=f)
        if args.asset=='v9':
            # The inherited gaze marker is fixed near the seated face. It cannot
            # remain there when June walks forward and addresses this camera.
            gaze=rig.pose.bones['gaze']
            head_origin=(rig.matrix_world @ head.matrix).translation+Vector((0,0,.33))
            forward=Matrix.Rotation(s['head_yaw']*1.45,3,'Z') @ Vector((0,-4,0))
            t=max(0.,min(1.,(f-490)/60));t=t*t*(3-2*t)
            aim=(head_origin+forward).lerp(cam.location,t)
            gaze.location=gaze.bone.matrix_local.to_3x3().inverted() @ (aim-gaze.bone.head_local)
            gaze.keyframe_insert('location',frame=f)
            bpy.context.view_layer.update()
        row={'frame':f,'beat':s['beat'],'feet':{},'hand_target_error':{}}
        for side in ('L','R'):
            ankle=rig.matrix_world @ rig.pose.bones['shin.'+side].tail
            row['feet'][side]={'position':list(ankle),'contact':s['feet'][side][1],
               'target_error':(ankle-targets['foot.'+side].location).length}
            wrist=rig.matrix_world @ rig.pose.bones['forearm.'+side].tail
            row['hand_target_error'][side]=(wrist-targets['hand.'+side].location).length
        row['mug_position']=list(mug.location)
        # Independent furniture bounds; measure evaluated boot meshes, not IK targets.
        table_legs=[o for o in bpy.data.objects if o.name.startswith('World_Table_Leg_')]
        boots=[bpy.data.objects['June_Boot_'+side] for side in ('L','R')]
        def bounds(obj):
            pts=mesh_points(obj)
            return tuple((min(p[i] for p in pts),max(p[i] for p in pts)) for i in range(3))
        def overlaps(a,b):return all(min(a[i][1],b[i][1])-max(a[i][0],b[i][0])>0 for i in range(3))
        row['boot_table_bbox_collisions']=sum(overlaps(bounds(boot),bounds(leg)) for boot in boots for leg in table_legs)
        row['sole_min_z']={o.name:min(p.z for p in mesh_points(o)) for o in soles}
        row['mug_bind_error']=((hand_matrix @ grip_bind).translation-mug.matrix_world.translation).length if grip_bind else None
        report.append(row)
        if f%60==0:print(f'Evaluated frame {f}/{FRAMES}; elapsed {time.monotonic()-started:.1f}s',flush=True)
    for obj in hidden:obj.hide_viewport=False
    bpy.context.view_layer.update()
    for action in bpy.data.actions:
        for fc in action.fcurves:
            for k in fc.keyframe_points:k.interpolation='LINEAR'
    audit=audit_evaluated(report,ground)
    evidence={'status':'DEVELOPMENT_MECHANICS_NOT_ART_APPROVED','fps':FPS,'frame_count':FRAMES,
       'duration_seconds':FRAMES/FPS,'asset':'june_v9_development' if args.asset=='v9' else 'inherited_v8_2_procedural_3d',
       'audio':'silent_no_voice_substitution',**audit,'ground_height':ground,
       'source_sha256':source_hashes,
       'measurement_scope':'evaluated control rig, boot/sole meshes, table legs and mug; hair/cloth/skin visibility restored before renders',
       'human_art_approved':False,'human_motion_approved':False,
       'unverified':['chair hand contact','finger handle contact','identity match to approved artwork',
                     'limb deformation quality','performance at normal playback speed'],
       'beats':BEATS,'frames':report}
    (out/'world-motion-report.json').write_text(json.dumps(evidence,indent=2))
    if not audit['control_mechanics_passed']:raise RuntimeError('Evaluated controls failed; no preview rendered')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'june-world-movement.blend'))
    selected=range(1,FRAMES+1) if args.animate else [int(v) for v in args.frames.split(',') if v.strip()]
    for f in selected:
        scene.frame_set(f);scene.render.filepath=str(out/f'frame_{f:04d}.png')
        bpy.ops.render.render(write_still=True)
    print(json.dumps({k:v for k,v in evidence.items() if k!='frames'}))


if __name__=='__main__':main()
