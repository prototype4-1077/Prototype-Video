"""Measure the evaluated studio rig; these checks do not approve acting or art."""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.june_studio import atomic_json
from pipeline.june_world_motion import sample


def audit(bpy, output):
    scene=bpy.context.scene;rig=bpy.data.objects['June_Oxley_Rig']
    head=bpy.data.objects['June_Head'];restore_frame=scene.frame_current
    hidden=[obj for obj in bpy.data.objects if obj.type in {'MESH','CURVE'} and not obj.hide_viewport]
    soles=[bpy.data.objects['June_Boot_Sole_'+side] for side in ('L','R')]
    for obj in hidden:
        if obj not in soles:obj.hide_viewport=True
    max_leg=max_arm=0.;min_sole=100.;max_planted_height=0.;nonfinite=[]
    for frame in range(1,scene.frame_end+1):
        scene.frame_set(frame)
        state=sample(min(270,150+frame))
        for side,sole in zip(('L','R'),soles):
            for owner,control in (('shin.','foot_ik.'),('forearm.','hand_ik.')):
                error=(rig.pose.bones[owner+side].tail-rig.pose.bones[control+side].head).length
                if owner=='shin.':max_leg=max(max_leg,error)
                else:max_arm=max(max_arm,error)
            evaluated=sole.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh=evaluated.to_mesh()
            low=min((evaluated.matrix_world@v.co).z for v in mesh.vertices)
            evaluated.to_mesh_clear();min_sole=min(min_sole,low)
            if state['feet'][side][1]:max_planted_height=max(max_planted_height,abs(low-.09))
        for bone in rig.pose.bones:
            if not all(math.isfinite(value) for row in bone.matrix for value in row):
                nonfinite.append({'frame':frame,'bone':bone.name})
    keys=head.data.shape_keys.key_blocks
    deformations={name:max((a.co-b.co).length for a,b in zip(keys[name].data,keys['Basis'].data))
                  for name in ('D','F','blink_L','blink_R','smile')}
    report={'scope':'evaluated rig and sole contacts; visual quality remains unapproved',
            'frame_count':scene.frame_end,'max_leg_target_error':max_leg,
            'max_hand_target_error':max_arm,'minimum_sole_z':min_sole,
            'max_planted_sole_distance_from_floor':max_planted_height,
            'nonfinite_transforms':nonfinite,'maximum_shape_displacements':deformations,
            'production_approved':False}
    report['mechanics_pass']=not nonfinite and max_leg<.025 and max_arm<.025 and min_sole>=.07 and max_planted_height<.025 and all(v>.002 for v in deformations.values())
    for obj in hidden:obj.hide_viewport=False
    scene.frame_set(restore_frame)
    atomic_json(output,report)
    return report


def main():
    import bpy
    p=argparse.ArgumentParser();p.add_argument('--scene',required=True);p.add_argument('--output',required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.scene).resolve()))
    result=audit(bpy,args.output);print(json.dumps(result),flush=True)
    if not result['mechanics_pass']:raise ValueError('studio mechanics require correction; see report')


if __name__=='__main__':main()
