"""Check the wardrobe asset's skin weights, reusable dependencies and motion.

This measures declared technical contracts, not clothing collision or art taste.
"""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from pipeline.june_studio import atomic_json,sha256


def facial_signature(bpy):
    """Exact stored head/eye geometry and every facial shape, without evaluation."""
    digest=hashlib.sha256();rig=bpy.data.objects['June_Oxley_Rig']
    for obj in sorted(bpy.data.objects,key=lambda o:o.name):
        parent=obj
        while parent.parent and parent.parent is not rig:parent=parent.parent
        if parent.parent is not rig or parent.parent_bone not in ('head','eye.L','eye.R'):continue
        if obj.type not in ('MESH','CURVE'):continue
        digest.update(obj.name.encode())
        digest.update(array.array('f',(v for row in obj.matrix_local for v in row)).tobytes())
        keys=getattr(obj.data,'shape_keys',None)
        blocks=[(k.name,k.data) for k in keys.key_blocks] if keys else [('Basis',obj.data.vertices if obj.type=='MESH' else [p for s in obj.data.splines for p in s.points])]
        for name,points in blocks:
            digest.update(name.encode());digest.update(array.array('f',(v for p in points for v in p.co)).tobytes())
    return digest.hexdigest()


def projected_mesh_bounds(bpy,scene,objects):
    """Project evaluated vertices; curve boxes include unused shape-key extents."""
    import numpy as np
    depsgraph=bpy.context.evaluated_depsgraph_get()
    camera=scene.camera
    projection=camera.calc_matrix_camera(depsgraph,x=scene.render.resolution_x,
        y=scene.render.resolution_y,scale_x=scene.render.pixel_aspect_x,scale_y=scene.render.pixel_aspect_y)
    view=projection@camera.matrix_world.inverted()
    bounds=[1.,0.,1.,0.]
    for obj in objects:
        ev=obj.evaluated_get(depsgraph);mesh=ev.to_mesh()
        points=np.empty((len(mesh.vertices),3),dtype=np.float32)
        mesh.vertices.foreach_get('co',points.ravel())
        matrix=np.array(view@ev.matrix_world,dtype=np.float64)
        clip=points@matrix[:,:3].T+matrix[:,3]
        ev.to_mesh_clear()
        if not np.isfinite(clip).all() or (clip[:,3]<=0).any():
            raise ValueError('character framing includes invalid or behind-camera geometry')
        xy=.5+.5*clip[:,:2]/clip[:,3,None]
        bounds=[min(bounds[0],float(xy[:,0].min())),max(bounds[1],float(xy[:,0].max())),
                min(bounds[2],float(xy[:,1].min())),max(bounds[3],float(xy[:,1].max()))]
    return bounds


def audit(bpy,asset,voice,output,source):
    from pipeline.june_studio_render import animate_scene
    from pipeline.blender.audit_june_studio import audit as mechanics
    asset=Path(asset).resolve();voice=Path(voice).resolve();output=Path(output).resolve()
    receipt=json.loads(asset.with_suffix('.json').read_text())
    if receipt['asset_version']!='studio-v5' or receipt['asset_sha256']!=sha256(asset):
        raise ValueError('matching studio-v5 receipt is required')
    if sha256(source)!=receipt['source_asset_sha256']:raise ValueError('v4 source identity mismatch')
    print('Checking original facial geometry',flush=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(source).resolve()))
    original_face=facial_signature(bpy)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    print('Appending the standalone character collection',flush=True)
    with bpy.data.libraries.load(str(asset),link=False) as (src,dst):
        dst.collections=[receipt['character_collection']]
    collection=dst.collections[0];bpy.context.scene.collection.children.link(collection)
    objects=set(collection.all_objects);missing=[];ids=set(objects)
    for obj in objects:
        if obj.data:
            ids.add(obj.data)
            keys=getattr(obj.data,'shape_keys',None)
            if keys:ids.add(keys)
        if obj.parent and obj.parent not in objects:missing.append(obj.name+' parent')
        for mod in obj.modifiers:
            target=getattr(mod,'object',None)
            if target and target not in objects:missing.append(obj.name+' modifier target')
    driver_targets=0
    for item in ids:
        ad=getattr(item,'animation_data',None)
        if not ad:continue
        for fc in ad.drivers:
            for var in fc.driver.variables:
                for target in var.targets:
                    driver_targets+=1
                    if target.id is None or target.id not in ids:missing.append(item.name+' driver target')
    images=[{'name':i.name,'packed':bool(i.packed_file)} for i in bpy.data.images if i.users]
    detail_weights=[]
    for obj in objects:
        if obj.type!='MESH' or not obj.get('ce_weight_source'):continue
        error=max(abs(sum(g.weight for g in v.groups)-1) for v in obj.data.vertices)
        detail_weights.append({'object':obj.name,'maximum_weight_sum_error':error,'vertices':len(obj.data.vertices)})
    append_pass=not missing and all(i['packed'] for i in images)
    bpy.ops.wm.open_mainfile(filepath=str(asset))
    face_preserved=original_face==facial_signature(bpy)
    job={'total_frames':450,'cues':str(voice/'mouth-cues.json'),'camera':'Body',
         'performance_camera':'Body','width':640,'height':360,'engine':'CYCLES',
         'samples':8,'voice_sha256':sha256(voice/'vo.mp3')}
    animate_scene(bpy,job)
    rig=bpy.data.objects['June_Oxley_Rig'];scene=bpy.context.scene
    geometry=[];poses=(1,35,60,98,136,191,218,253,300,450)
    relevant=[bpy.data.objects['June_Hand_'+s] for s in ('L','R')]
    relevant += [o for o in bpy.data.objects if o.name.startswith('June_V5_') or o.name.startswith('June_Boot_')]
    framing=[bpy.data.objects[n] for n in ('June_Head','June_Studio_Scalp',
             'June_V3_Swept_Clumps_0','June_V3_Swept_Clumps_1','June_V3_Swept_Clumps_2',
             'June_Boot_Sole_L','June_Boot_Sole_R','June_Continuous_Coat')]
    for frame in poses:
        print('Checking wardrobe pose '+str(frame),flush=True)
        scene.frame_set(frame);bpy.context.view_layer.update();nonfinite=0
        for obj in relevant:
            if obj.type!='MESH':continue
            evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
            nonfinite+=sum(not all(math.isfinite(c) for c in v.co) for v in mesh.vertices)
            evaluated.to_mesh_clear()
        # The body and NLA actions must keep the fitted hand size and rest pose.
        fingers=[math.degrees(rig.pose.bones[f'finger.{n}.L'].rotation_euler.x) for n in range(4)]
        scales=list(rig.pose.bones['hand.L'].scale)
        bounds=projected_mesh_bounds(bpy,scene,framing)
        geometry.append({'frame':frame,'nonfinite_vertices':nonfinite,'left_hand_scale':scales,
                         'left_proximal_curl_degrees':fingers,'body_camera_bounds':bounds})
    motion=mechanics(bpy,output.with_name('studio-mechanics-report.json'))
    expected=list(rig['ce_finger_relax_degrees'])[:4]
    expected_scale=receipt['hand_report']['hand_bone_scale']
    pose_pass=all(row['nonfinite_vertices']==0 and max(abs(a-b) for a,b in zip(row['left_proximal_curl_degrees'],expected))<1e-4
                  and max(abs(a-b) for a,b in zip(row['left_hand_scale'],expected_scale))<1e-5 for row in geometry)
    framing_pass=all(min(row['body_camera_bounds'])>=.02 and max(row['body_camera_bounds'])<=.98 for row in geometry)
    result={'asset_sha256':sha256(asset),'scope':'append dependencies, normalized detail weights, finite sampled poses and complete rig contacts; no collision or art approval',
        'object_count':len(objects),'driver_targets':driver_targets,'missing_dependencies':missing,'images':images,
        'append_pass':append_pass,'detail_weights':detail_weights,'sampled_poses':geometry,
        'body_camera_framing_pass':framing_pass,
        'framing_measurement':'evaluated head, groom, coat and sole vertices; 2 percent margin at ten declared poses',
        'v4_facial_geometry_preserved':face_preserved,'facial_geometry_sha256':original_face,
        'mechanics_pass':motion['mechanics_pass'],'production_approved':False,'dialogue_quality_approved':False,
        'wardrobe_checks_pass':append_pass and pose_pass and framing_pass and face_preserved and motion['mechanics_pass'] and bool(detail_weights) and all(r['maximum_weight_sum_error']<1e-5 for r in detail_weights)}
    atomic_json(output,result)
    if not result['wardrobe_checks_pass']:raise ValueError('v5 wardrobe checks failed; inspect '+str(output))
    print(json.dumps({'wardrobe_checks_pass':True,'sampled_poses':len(geometry),'object_count':len(objects)}),flush=True)


if __name__=='__main__':
    import bpy
    parser=argparse.ArgumentParser();parser.add_argument('--asset',required=True);parser.add_argument('--source',required=True)
    parser.add_argument('--voice-dir',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);audit(bpy,args.asset,args.voice_dir,args.output,args.source)
