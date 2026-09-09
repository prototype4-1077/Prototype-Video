"""Sample evaluated eye visibility through the actual closed head surface.

This checks polygon centers, not every pixel or every possible gaze. The report
states the tested poses; beauty renders remain necessary for art review.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from pipeline.blender import june_studio_assets as studio
from pipeline.june_studio import atomic_json,sha256


def coverage(bpy,camera):
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    head=bpy.data.objects['June_Head'];graph=bpy.context.evaluated_depsgraph_get()
    ev=head.evaluated_get(graph);mesh=ev.to_mesh();mesh.calc_loop_triangles()
    tree=BVHTree.FromPolygons([ev.matrix_world@v.co for v in mesh.vertices],
                            [tuple(t.vertices) for t in mesh.loop_triangles],all_triangles=True)
    ev.to_mesh_clear();results={}
    for side in ('L','R'):
        for part in ('Eye','Iris','Iris_Rim','Pupil'):
            obj=bpy.data.objects['June_'+part+'_'+side].evaluated_get(graph)
            vertices=[obj.matrix_world@v.co for v in obj.data.vertices]
            normal_matrix=obj.matrix_world.to_3x3().inverted().transposed()
            tested=exposed=0
            for poly in obj.data.polygons:
                point=sum((vertices[i] for i in poly.vertices),Vector())/len(poly.vertices)
                if (normal_matrix@poly.normal).dot(camera-point)<=0:continue
                tested+=1;direction=point-camera
                hit=tree.ray_cast(camera,direction.normalized(),direction.length+.1)
                if hit[0] is None or hit[3]>direction.length+.00005:exposed+=1
            results[part+'_'+side]={'tested':tested,'exposed':exposed}
    return results


def hide_followers(bpy):
    for obj in bpy.data.objects:
        if obj.type in ('MESH','CURVE'):
            obj.hide_viewport=not (obj.name=='June_Head' or obj.parent_bone in ('eye.L','eye.R'))
    for m in bpy.data.objects['June_Head'].modifiers:
        if m.type=='SUBSURF':m.levels=m.render_levels


def audit(bpy,voice_dir=None):
    from mathutils import Vector
    rig=bpy.data.objects['June_Oxley_Rig'];head=bpy.data.objects['June_Head']
    hide_followers(bpy);rig.data.pose_position='POSE';studio.body_pose(rig,270)
    keys=head.data.shape_keys.key_blocks;closed=[];open_checks=[]
    for camera_name in ('Front','Close','Wide'):
        camera=bpy.data.objects['June_Camera_'+camera_name].location.copy()
        for k in keys:k.value=0
        studio.aim_control(rig,'gaze',camera);bpy.context.view_layer.update()
        open_checks.append({'camera':camera_name,'samples':coverage(bpy,camera)})
        for k in keys:k.value=1 if k.name.startswith('blink') else 0
        for dx in (-.75,0,.75):
            for dz in (-.45,0,.45):
                target=camera+Vector((dx,0,dz))
                studio.aim_control(rig,'gaze',target);bpy.context.view_layer.update()
                closed.append({'camera':camera_name,'gaze_offset':[dx,0,dz],
                               'samples':coverage(bpy,camera)})
    moving=[]
    if voice_dir:
        from pipeline.june_studio_render import animate_scene,check_voice
        voice=Path(voice_dir);check_voice(voice)
        animate_scene(bpy,{'total_frames':450,'cues':str(voice/'mouth-cues.json'),
                          'camera':'Close','performance_camera':'Close','width':640,'height':360,
                          'engine':'CYCLES','samples':8,'voice_sha256':sha256(voice/'vo.mp3')})
        hide_followers(bpy)
        for frame in (79,136,253):
            bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
            moving.append({'frame':frame,'samples':coverage(bpy,bpy.data.objects['June_Camera_Close'].location)})
    closed_pass=all(s['exposed']==0 and s['tested']>0 for row in closed+moving for s in row['samples'].values())
    open_pass=all(row['samples']['Iris_'+side]['exposed']>100 for row in open_checks for side in ('L','R'))
    return {'method':'evaluated render-subdivision head ray cast to front-facing eye polygon centers',
            'closed_pose_count':len(closed)+len(moving),'closed_poses':closed,'moving_blinks':moving,
            'open_checks':open_checks,'closed_coverage_pass':closed_pass,'open_iris_visible_pass':open_pass,
            'eyelid_samples_pass':closed_pass and open_pass,
            'limitations':'Sampled polygon centers and declared gaze offsets; not a proof for all blends, pixels or views.'}


def main():
    import bpy
    p=argparse.ArgumentParser();p.add_argument('--asset',required=True);p.add_argument('--output',required=True)
    p.add_argument('--voice-dir');p.add_argument('--allow-failure',action='store_true')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);asset=Path(args.asset).resolve()
    receipt=json.loads(asset.with_suffix('.json').read_text())
    if sha256(asset)!=receipt['asset_sha256']:raise ValueError('asset identity mismatch')
    bpy.ops.wm.open_mainfile(filepath=str(asset))
    report=audit(bpy,args.voice_dir);report.update(asset_sha256=sha256(asset),audit_sha256=sha256(__file__))
    atomic_json(args.output,report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('closed_poses','moving_blinks','open_checks')}),flush=True)
    if not report['eyelid_samples_pass'] and not args.allow_failure:raise ValueError('eyelid fit failed; see '+args.output)


if __name__=='__main__':main()
