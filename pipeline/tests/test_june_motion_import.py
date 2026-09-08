"""Optional real Blender FBX round trip; no third-party motion is downloaded."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('BLENDER_BIN'), 'set BLENDER_BIN for the FBX integration test')
class MotionIntakeTests(unittest.TestCase):
    def test_fbx_action_survives_intake_without_being_marked_retargeted(self):
        blender=os.environ['BLENDER_BIN']
        repo=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'synthetic.fbx';output=root/'source-motion.blend'
            fixture=root/'fixture.py'
            fixture.write_text('''import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.render.fps=30;scene.frame_start=1;scene.frame_end=31
rig=bpy.data.objects.new('SyntheticSource',bpy.data.armatures.new('SyntheticSource'))
scene.collection.objects.link(rig);bpy.context.view_layer.objects.active=rig;rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
names=('Hips','Head','LeftArm','RightArm','LeftForeArm','RightForeArm','LeftUpLeg','RightUpLeg','LeftLeg','RightLeg')
for i,name in enumerate(names):
    bone=rig.data.edit_bones.new('mixamorig:'+name);bone.head=(0,0,1+i*.1);bone.tail=(0,0,1.1+i*.1)
    if i:bone.parent=rig.data.edit_bones['mixamorig:Hips']
bpy.ops.object.mode_set(mode='POSE')
arm=rig.pose.bones['mixamorig:LeftArm'];arm.rotation_mode='XYZ'
for frame,angle in ((1,0),(16,.5),(31,0)):
    arm.rotation_euler.x=angle;arm.keyframe_insert('rotation_euler',frame=frame)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.export_scene.fbx(filepath='''+repr(str(source))+''',object_types={'ARMATURE'},
    bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,add_leaf_bones=False)
''')
            for command in (
                [blender,'-b','-t','2','--python-exit-code','1','--python',str(fixture)],
                [blender,'-b','-t','2','--python-exit-code','1','--python',str(repo/'pipeline/blender/import_june_motion.py'),
                 '--','--input',str(source),'--output',str(output),'--license-note','Synthetic test fixture; no external motion'],
            ):
                result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60)
                self.assertEqual(result.returncode,0,result.stdout[-4000:])
            report=json.loads(output.with_suffix('.json').read_text())
            self.assertTrue(output.is_file())
            self.assertEqual(report['fps'],30)
            self.assertTrue(report['actions'])
            self.assertEqual(report['actions'][0]['frame_range'],[1.,31.])
            self.assertFalse(report['retargeted_to_june'])
            self.assertFalse(report['production_approved'])


if __name__=='__main__':unittest.main()
