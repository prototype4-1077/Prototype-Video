"""Package a completed studio preview with the required numbered scene survey."""
import argparse
import copy
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import review
from pipeline.june_studio import atomic_json, sha256
from pipeline.june_studio_render import check_voice


def package(render_dir, asset, voice_dir, destination, blender='blender'):
    render=Path(render_dir).resolve();asset=Path(asset).resolve();out=Path(destination).resolve()
    voice=Path(voice_dir).resolve();check_voice(voice)
    report=json.loads((render/'studio-render-report.json').read_text())
    video=render/'June_Oxley_Studio_Development.mp4'
    if not report.get('decoded') or report['video_sha256']!=sha256(video):
        raise ValueError('a completed, decoded studio video is required')
    if report['asset_sha256']!=sha256(asset):raise ValueError('package asset differs from rendered character')
    if report['voice_sha256']!=sha256(voice/'vo.mp3'):raise ValueError('package voice differs from rendered take')
    original_script=json.loads((voice/'script.json').read_text())
    dialogue=' '.join(scene['text'] for scene in original_script['scenes'])
    out.mkdir(parents=True,exist_ok=True)
    script={'title':'June Oxley — Studio Development Review','slug':'june-reusable-studio-v1',
            'profile':'june_oxley','development_only':True,'production_approved':False,'scenes':[
        {'start':0,'duration':4,'text':'','query':'June takes two steps into a complete three-dimensional porch set.',
         'rationale':'Check continuity of the walk, foot contact, character silhouette, and set geography.'},
        {'start':4,'duration':7,'text':dialogue,
         'query':'June addresses the camera with the preserved Spuds voice, mouth shapes, blinks, and a conversational gesture.',
         'rationale':'Check lip closure, speech timing, beard deformation, gaze, and whether the thought reads naturally.'},
        {'start':11,'duration':report['duration_seconds']-11,'text':'',
         'query':'June settles into a front-facing reaction and slight smile.',
         'rationale':'Check that the same face holds its identity, the reaction feels motivated, and the mouth returns to rest.'},
    ]}
    atomic_json(out/'script.json',script)
    payload={'schema_version':review.SCHEMA_VERSION,'generated_at':review._now(),
             'slug':script['slug'],'title':script['title'],'genre':'3D development review',
             'script_fingerprint':review._fingerprint(script),'video_file':video.name,
             'development_only':True,'production_approved':False,'scenes':[],
             'overall':{'decision':'unreviewed','comments':''}}
    for index,scene in enumerate(script['scenes']):
        preview=review._preview_data_uri(str(video),scene)
        if not preview:raise ValueError('missing rendered preview for scene '+str(index+1))
        row=review._scene_payload(scene,index,preview);row['why_chosen']=scene['rationale']
        row['motion_mode']='animated 3D geometry';payload['scenes'].append(row)
    metadata=copy.deepcopy(payload)
    for row in metadata['scenes']:row.pop('preview')
    atomic_json(out/'scene-review.json',metadata)
    embedded=json.dumps(payload,ensure_ascii=True).replace('</','<\\/')
    page=review.HTML_TEMPLATE.replace('__TITLE__',html.escape(payload['title'])).replace('__REVIEW_JSON__',embedded)
    (out/'scene-review.html').write_text(page)
    copies={video:out/video.name,asset:out/'june-studio.blend',asset.with_suffix('.json'):out/'june-studio.json',
            render/'june-speaking-scene.blend':out/'june-speaking-scene.blend',
            render/'studio-render-report.json':out/'studio-render-report.json',
            render/'studio-mechanics-report.json':out/'studio-mechanics-report.json'}
    for source,dest in copies.items():
        if source!=dest:shutil.copy2(source,dest)
    audio_job={'scene':str(out/'june-speaking-scene.blend'),'audio':str(voice/'vo.mp3'),
               'voice_sha256':report['voice_sha256'],'frame_start':121}
    atomic_json(out/'scene-audio-job.json',audio_job)
    result=subprocess.run([blender,'-b','-t','2','--python-exit-code','1','--python',str(Path(__file__).resolve()),
                           '--','--scene-audio-job',str(out/'scene-audio-job.json')],
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if result.returncode:raise RuntimeError('editable scene audio packaging failed: '+result.stdout[-3000:])
    for name in ('close.png','front.png','wide.png'):
        source=asset.parent/name
        if source.is_file():shutil.copy2(source,out/name)
    (out/'README.txt').write_text(
        'JUNE OXLEY — REUSABLE STUDIO DEVELOPMENT\n\n'
        'Open scene-review.html to review the three numbered shots and export comments.\n'
        f'This is a {report["duration_seconds"]:g}-second {report["width"]}x{report["height"]}, {report["fps"]} fps development preview, not an approved episode.\n'
        'The original Spuds voice begins at 4 seconds; there is no score in this test.\n\n'
        'june-studio.blend contains the packed character, porch, three cameras, eight\n'
        'body clips, and fifteen facial pose assets. june-speaking-scene.blend contains\n'
        'the editable performance timeline and packed Spuds recording; its active\n'
        'camera is the address shot. The voice plays from timeline frame 121.\n'
        'The final movie combines Wide (frames 1–120), Close (121–330), and Front\n'
        f'(331–{report["frame_count"]}) camera renders. Use Blender 4.2.0 for this version.\n\n'
        'Next art priorities: approved likeness, eyelids and eye scale, wardrobe\n'
        'construction, expression appeal, and a hand-polished acting pass. The\n'
        'mechanical report is not a visual-quality or character-approval certificate.\n\n'
        'Operating guide and source provenance:\n'
        'https://github.com/prototype4-1077/Prototype-Video/pull/13\n'
        'Voice take: https://github.com/prototype4-1077/Prototype-Video/releases/tag/june-studio-voice-benchmark-v1\n'
        'Packed wood and sky: Poly Haven, CC0 — https://polyhaven.com/license\n'
        'Facial source targets: MakeHuman/MPFB core data, CC0.\n')
    archive=out.parent/'June_Oxley_Studio_Review_Package.zip'
    names=['README.txt','script.json','scene-review.html','scene-review.json',video.name,
           'june-studio.blend','june-studio.json','june-speaking-scene.blend',
           'studio-render-report.json','studio-mechanics-report.json','close.png','front.png','wide.png']
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for name in names:
            if (out/name).is_file():bundle.write(out/name,name)
    return archive


def pack_scene_audio(job_path):
    import bpy
    job=json.loads(Path(job_path).read_text())
    if sha256(job['audio'])!=job['voice_sha256']:raise ValueError('editable scene voice checksum mismatch')
    bpy.ops.wm.open_mainfile(filepath=job['scene'])
    scene=bpy.context.scene;editor=scene.sequence_editor_create()
    strip=editor.sequences.new_sound('Preserved Spuds voice',job['audio'],channel=1,frame_start=job['frame_start'])
    strip.sound.pack();scene.render.use_sequencer=False
    scene['ce_embedded_voice_sha256']=job['voice_sha256']
    bpy.ops.wm.save_as_mainfile(filepath=job['scene'],compress=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--render-dir');p.add_argument('--voice-dir')
    p.add_argument('--asset');p.add_argument('--destination');p.add_argument('--blender',default='blender')
    p.add_argument('--scene-audio-job')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None
    args=p.parse_args(argv)
    if args.scene_audio_job:pack_scene_audio(args.scene_audio_job)
    else:
        if not all((args.render_dir,args.asset,args.voice_dir,args.destination)):p.error('render-dir, asset, voice-dir, and destination are required')
        print(package(args.render_dir,args.asset,args.voice_dir,args.destination,args.blender))


if __name__=='__main__':main()
