"""Intake licensed local humanoid FBX motion into a separate Blender library.

Mixamo requires an Adobe account for downloads. This importer neither logs in
nor claims a downloaded motion is already retargeted or approved for June.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    import bpy
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--license-note',required=True);p.add_argument('--fps',type=int,default=30)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    path=Path(args.input).resolve();output=Path(args.output).resolve()
    if path.suffix.lower()!='.fbx' or not path.is_file():raise ValueError('a local FBX file is required')
    if args.fps<1:raise ValueError('fps must be positive')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps=args.fps
    bpy.ops.import_scene.fbx(filepath=str(path),use_anim=True,anim_offset=0.0,automatic_bone_orientation=False)
    rigs=[o for o in bpy.data.objects if o.type=='ARMATURE']
    if len(rigs)!=1:raise ValueError('expected one humanoid source armature')
    rig=rigs[0]
    names={b.name.split(':')[-1] for b in rig.data.bones}
    required={'Hips','Head','LeftArm','RightArm','LeftForeArm','RightForeArm','LeftUpLeg','RightUpLeg','LeftLeg','RightLeg'}
    if not required<=names:raise ValueError('missing standard Mixamo humanoid bones: '+str(sorted(required-names)))
    actions=[a for a in bpy.data.actions if a.fcurves]
    if not actions:raise ValueError('FBX has no motion curves')
    for action in actions:
        action.use_fake_user=True;action.asset_mark()
        action.asset_data.description='Imported source motion. Retargeting and contact review required before June use.'
        action['ce_motion_source_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
    output.with_suffix('.json').write_text(json.dumps({'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
       'source_file':path.name,'license_note':args.license_note,'fps':args.fps,
       'actions':[{'name':a.name,'frame_range':list(a.frame_range)} for a in actions],
       'retargeted_to_june':False,'production_approved':False},indent=2)+'\n')


if __name__=='__main__':main()
