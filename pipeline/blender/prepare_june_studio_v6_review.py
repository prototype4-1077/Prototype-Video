"""Audit v6 and reuse the verified, packed v5 performance without a new take.

The recovered bundle retains its facial action and sound, but not its original
cue-source files. This deliberately preserves those actions; it does not claim
to regenerate or revalidate Rhubarb cues that are not available.
"""
import argparse
import array
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.june_studio import atomic_json, sha256, VOICE_ID
from pipeline.blender import audit_june_eyelids as eyelids
from pipeline.blender.audit_june_studio import audit as mechanics
from pipeline.blender.audit_june_wardrobe import projected_mesh_bounds

ACTING = ('June_Shot_Acting', 'June_Spuds_Facial_Performance')


def checked_inputs(asset, source, performance):
    asset, source, performance = map(lambda p: Path(p).resolve(), (asset, source, performance))
    receipt = json.loads(asset.with_suffix('.json').read_text())
    packed = json.loads((performance.parent / 'packed-scene-check.json').read_text())
    if receipt.get('asset_version') != 'studio-v6' or receipt.get('asset_sha256') != sha256(asset):
        raise ValueError('matching studio-v6 receipt is required')
    if receipt.get('source_asset_sha256') != sha256(source):
        raise ValueError('v5 source identity mismatch')
    if packed.get('scene_sha256') != sha256(performance):
        raise ValueError('packed v5 performance identity mismatch')
    voices = packed.get('voice', [])
    if len(voices) != 1 or voices[0].get('frame_start') != 121 or not voices[0].get('packed'):
        raise ValueError('one complete packed take starting at frame 121 is required')
    if packed.get('timeline') != [1, 450] or packed.get('preview') != [109, 270]:
        raise ValueError('unexpected source performance clock')
    return receipt, voices[0]['sha256']


def action_signature(action, paths=None):
    curves = []
    for curve in action.fcurves:
        if paths and not any(p in curve.data_path for p in paths):
            continue
        curves.append((curve.data_path, curve.array_index,
                       [(list(k.co), k.interpolation) for k in curve.keyframe_points]))
    return hashlib.sha256(json.dumps(sorted(curves), sort_keys=True).encode()).hexdigest()


def boot_signature(bpy):
    digest = hashlib.sha256()
    prefixes = ('June_Boot_', 'June_V5_Boot_Welt', 'June_V5_Eyelet',
                'June_V5_Toe_Cap', 'June_V5_Welt_Stitch')
    names = []
    for obj in sorted(bpy.data.objects, key=lambda o: o.name):
        if not obj.name.startswith(prefixes) or obj.type not in {'MESH', 'CURVE'}:
            continue
        names.append(obj.name)
        digest.update(obj.name.encode())
        digest.update(array.array('f', (x for row in obj.matrix_local for x in row)).tobytes())
        points = obj.data.vertices if obj.type == 'MESH' else [p for s in obj.data.splines for p in s.points]
        digest.update(array.array('f', (x for p in points for x in p.co)).tobytes())
        if obj.type == 'MESH':
            digest.update(array.array('I', (i for face in obj.data.polygons for i in face.vertices)).tobytes())
    return {'sha256': digest.hexdigest(), 'objects': names}


def append_audit(bpy, asset, collection_name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(asset), link=False) as (_, dst):
        dst.collections = [collection_name]
    collection = dst.collections[0]
    bpy.context.scene.collection.children.link(collection)
    objects = set(collection.all_objects)
    ids = set(objects)
    missing, weights = [], []
    for obj in objects:
        if obj.data:
            ids.add(obj.data)
            keys = getattr(obj.data, 'shape_keys', None)
            if keys:
                ids.add(keys)
        if obj.parent and obj.parent not in objects:
            missing.append(obj.name + ' parent')
        for modifier in obj.modifiers:
            target = getattr(modifier, 'object', None)
            if target and target not in objects:
                missing.append(obj.name + ' modifier target')
        if obj.type == 'MESH' and obj.get('ce_weight_source'):
            error = max(abs(sum(g.weight for g in v.groups) - 1) for v in obj.data.vertices)
            weights.append({'object': obj.name, 'maximum_weight_sum_error': error})
    drivers = 0
    for item in ids:
        animation = getattr(item, 'animation_data', None)
        if not animation:
            continue
        for curve in animation.drivers:
            for variable in curve.driver.variables:
                for target in variable.targets:
                    drivers += 1
                    if target.id is None or target.id not in ids:
                        missing.append(item.name + ' driver target')
    images = [{'name': i.name, 'packed': bool(i.packed_file)} for i in bpy.data.images if i.users]
    passed = not missing and bool(weights) and all(w['maximum_weight_sum_error'] < 1e-5 for w in weights)
    passed = passed and all(i['packed'] for i in images)
    return {'append_pass': passed, 'object_count': len(objects), 'driver_targets': drivers,
            'missing_dependencies': missing, 'images': images, 'detail_weights': weights}


def reuse_performance(bpy, performance, voice_hash, output):
    master = bpy.context.scene
    master_collections = list(master.collection.children)
    master_root_objects = list(master.collection.objects)
    master_objects = set(master.objects)
    existing_actions = set(bpy.data.actions)
    # Reuse the original scene's packed sound strip as well as its actions.
    # The official bpy wheel can read these strips, but is built without
    # Audaspace and cannot create a new sound strip. Full Blender can play it.
    with bpy.data.libraries.load(str(performance), link=False) as (src, dst):
        if len(src.scenes) != 1:
            raise ValueError('one packed source scene is required')
        dst.scenes = src.scenes
    scene = dst.scenes[0]
    source_objects = set(scene.objects)
    source_collections = list(scene.collection.children)
    source_rig = next(o for o in source_objects if o.type == 'ARMATURE' and o.name.startswith('June_Oxley_Rig'))
    source_head = next(o for o in source_objects if o.name == 'June_Head' or o.name.startswith('June_Head.'))
    actions = {ACTING[0]: source_rig.animation_data.action,
               ACTING[1]: source_head.data.shape_keys.animation_data.action}
    if not all(action and action.name.startswith(name) for name, action in actions.items()):
        raise ValueError('source facial and acting actions are missing')
    strips = [s for s in scene.sequence_editor.sequences_all if s.type == 'SOUND']
    if len(strips) != 1 or strips[0].frame_start != 121:
        raise ValueError('original packed sound strip has an unexpected clock')
    sound = strips[0].sound
    if not sound.packed_file or hashlib.sha256(sound.packed_file.data).hexdigest() != voice_hash:
        raise ValueError('packed voice bytes do not match the source receipt')
    audio = output / 'voice' / 'vo.mp3'
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(sound.packed_file.data)
    for collection in source_collections:
        scene.collection.children.unlink(collection)
    for collection in master_collections:
        scene.collection.children.link(collection)
    for obj in master_root_objects:
        scene.collection.objects.link(obj)
    scene.world = master.world
    for attr in ('view_transform', 'look', 'exposure', 'gamma'):
        setattr(scene.view_settings, attr, getattr(master.view_settings, attr))
    bpy.context.window.scene = scene
    rig = bpy.data.objects['June_Oxley_Rig']
    keys = bpy.data.objects['June_Head'].data.shape_keys
    rig.animation_data_clear()
    rig.animation_data_create()
    track = rig.animation_data.nla_tracks.new()
    track.name = 'Reusable body performance'
    walk = track.strips.new('Walk two steps', 1, bpy.data.actions['June_Studio_Walk_Two_Steps'])
    walk.extrapolation = 'NOTHING'
    standing = track.strips.new('Stand and address', 121, bpy.data.actions['June_Studio_Stand'])
    standing.frame_end = 450
    standing.extrapolation = 'HOLD_FORWARD'
    track = rig.animation_data.nla_tracks.new()
    track.name = 'Reusable conversational gesture'
    strip = track.strips.new('Explain', 139, bpy.data.actions['June_Studio_Explain'])
    strip.blend_in, strip.blend_out, strip.extrapolation = 12, 18, 'NOTHING'
    rig.animation_data.action = actions[ACTING[0]]
    keys.animation_data_clear()
    keys.animation_data_create()
    keys.animation_data.action = actions[ACTING[1]]
    scene.frame_start, scene.frame_end, scene.render.fps = 1, 450, 30
    scene.timeline_markers.clear()
    scene.camera = bpy.data.objects['June_Camera_Body']
    scene.frame_preview_start, scene.frame_preview_end = 109, 270
    scene.use_preview_range = True
    sound.filepath = '//voice/vo.mp3'
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.max_bounces = 6
    scene.cycles.use_denoising = True
    scene.render.threads_mode, scene.render.threads = 'FIXED', 6
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.use_persistent_data = True
    scene.render.use_sequencer = False
    scene['ce_voice_id'], scene['ce_voice_sha256'] = VOICE_ID, voice_hash
    scene['ce_production_approved'] = False
    # Remove the imported v5 display objects. Only v6 geometry and the two
    # original acting actions belong in this speaking scene.
    bpy.data.scenes.remove(master)
    for obj in source_objects - master_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in source_collections:
        if collection not in master_collections:
            bpy.data.collections.remove(collection)
    for action in set(bpy.data.actions) - existing_actions - set(actions.values()):
        action.use_fake_user = False
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=False, do_recursive=True)
    return {'source_scene_sha256': sha256(performance), 'voice_id': VOICE_ID,
            'voice_sha256': sha256(audio), 'voice_start_frame': 121,
            'timeline': [1, 450], 'preview': [109, 270],
            'source_action_signatures': {name: action_signature(action) for name, action in actions.items()},
            'speech_method': 'unchanged packed v5 facial action and exact original audio bytes; no new cue generation'}


def main():
    import bpy
    parser = argparse.ArgumentParser()
    parser.add_argument('--asset', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--performance', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    asset, source, performance = [Path(p).resolve() for p in (args.asset, args.source, args.performance)]
    output = Path(args.output_dir).resolve()
    if output in (source.parent, performance.parent):
        raise ValueError('review output must be separate from the source package')
    receipt, voice_hash = checked_inputs(asset, source, performance)
    if bpy.app.version_string != '4.2.0':
        raise ValueError('Blender 4.2.0 is required')
    output.mkdir(parents=True, exist_ok=True)
    print('Verifying original boots and planted-foot actions', flush=True)
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    boots = boot_signature(bpy)
    foot_actions = {a.name: action_signature(a, ('foot_ik.', 'pelvis'))
                    for a in bpy.data.actions if a.name.startswith('June_Studio_')}
    append = append_audit(bpy, asset, receipt['character_collection'])
    bpy.ops.wm.open_mainfile(filepath=str(asset), use_scripts=False)
    boots_preserved = boot_signature(bpy) == boots
    feet_preserved = foot_actions == {a.name: action_signature(a, ('foot_ik.', 'pelvis'))
                                      for a in bpy.data.actions if a.name.startswith('June_Studio_')}
    print('Checking closed eyelids across 27 declared gaze poses', flush=True)
    eye_report = eyelids.audit(bpy)
    atomic_json(output / 'eyelid-report.json', {**eye_report, 'asset_sha256': sha256(asset)})
    # The eyelid audit deliberately hides followers and changes the pose.
    # Reload the saved asset before attaching the preserved performance.
    bpy.ops.wm.open_mainfile(filepath=str(asset), use_scripts=False)
    speech = reuse_performance(bpy, performance, voice_hash, output)
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = 640, 360
    scene.cycles.samples = 12
    scene.frame_set(109)
    scene_path = output / 'june-speaking-scene.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path), compress=True)
    motion = mechanics(bpy, output / 'studio-mechanics-report.json')
    collection = bpy.data.collections[receipt['character_collection']]
    geometry = [o for o in collection.all_objects if o.type in {'MESH', 'CURVE'} and not o.hide_render]
    poses = []
    for frame in (1, 35, 60, 98, 109, 136, 191, 218, 253, 270, 450):
        print('Checking full character framing at frame ' + str(frame), flush=True)
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        poses.append({'frame': frame, 'body_camera_bounds': projected_mesh_bounds(bpy, scene, geometry)})
    framing_pass = all(min(p['body_camera_bounds']) >= .02 and max(p['body_camera_bounds']) <= .98 for p in poses)
    hidden = {o: o.hide_viewport for o in bpy.data.objects}
    eyelids.hide_followers(bpy)
    moving = []
    for frame in (79, 136, 253):
        scene.frame_set(frame)
        samples = eyelids.coverage(bpy, scene.camera.location)
        moving.append({'frame': frame, 'samples': samples})
    for obj, was_hidden in hidden.items():
        obj.hide_viewport = was_hidden
    moving_pass = all(s['exposed'] == 0 and s['tested'] > 0 for row in moving for s in row['samples'].values())
    result = {'asset_sha256': sha256(asset), 'scene_sha256': sha256(scene_path),
              'audit_code_sha256': sha256(__file__), 'blender_version': bpy.app.version_string,
              'append': append, 'v5_boots_preserved': boots_preserved, 'boot_geometry': boots,
              'foot_and_pelvis_action_curves_preserved': feet_preserved, 'performance': speech,
              'mechanics_pass': motion['mechanics_pass'], 'eyelid_samples_pass': eye_report['eyelid_samples_pass'],
              'sampled_poses': poses, 'body_camera_framing_pass': framing_pass,
              'moving_blinks': moving, 'moving_blinks_pass': moving_pass,
              'production_approved': False, 'dialogue_quality_approved': False, 'art_decision': 'unreviewed',
              'limitations': 'Declared pose, polygon-center eye and rig checks. No general cloth-collision guarantee or aesthetic approval.'}
    result['technical_checks_pass'] = all((append['append_pass'], boots_preserved, feet_preserved,
        motion['mechanics_pass'], eye_report['eyelid_samples_pass'], framing_pass, moving_pass))
    atomic_json(output / 'v6-asset-audit.json', result)
    if not result['technical_checks_pass']:
        raise ValueError('v6 technical audit failed; inspect v6-asset-audit.json')
    if args.render:
        frames = output / 'frames'
        frames.mkdir(exist_ok=True)
        for frame in range(109, 271):
            scene.frame_set(frame)
            scene.render.filepath = str(frames / f'frame_{frame - 108:04d}.png')
            bpy.ops.render.render(write_still=True)
            atomic_json(output / 'render-progress.json', {'completed': frame - 108, 'total': 162})
        atomic_json(output / 'render-frames.json', {
            'asset_sha256': sha256(asset), 'scene_sha256': sha256(scene_path),
            'first': 109, 'last': 270, 'fps': 30, 'width': 640, 'height': 360,
            'frames': {p.name: sha256(p) for p in sorted(frames.glob('frame_*.png'))}})
    print(json.dumps({'technical_checks_pass': True, 'scene': str(scene_path)}), flush=True)


if __name__ == '__main__':
    main()
