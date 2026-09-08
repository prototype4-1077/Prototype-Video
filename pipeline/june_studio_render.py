"""Render a short June development scene from the saved studio asset.

Each shot has a content-addressed frame cache. Blender reports actual frames,
and only a complete, checksum-verified sequence can be reused or assembled.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.june_studio import REPO, atomic_json, sha256, input_identity, cache_valid, complete_cache, status, preserved_voice, VOICE_ID

FPS = 30
INTRO_FRAMES = 120


def study_shot(request, total_frames, voice_duration):
    """Select a bounded art study while retaining the complete original take."""
    camera, first, last = request
    first, last = int(first), int(last)
    if camera not in {'Close', 'Front', 'Wide'}:
        raise ValueError('study camera must be Close, Front, or Wide')
    voice_end = INTRO_FRAMES + math.ceil(voice_duration * FPS)
    if not (1 <= first <= INTRO_FRAMES+1 and voice_end <= last <= total_frames):
        raise ValueError('study range must be inside the animation and include the entire voice take')
    return {'name': '01_likeness_study', 'camera': camera, 'start': first, 'end': last}


def cue_weights(cues, seconds, transition=2/FPS):
    """Blend adjacent speech shapes, with a bounded neutral return at silence."""
    result={name:0.0 for name in 'ABCDEFGHX'}
    result['X']=1.0
    for index,cue in enumerate(cues):
        if cue['start']<=seconds<cue['end']:
            current=cue['value'];previous=cues[index-1]['value'] if index else 'X'
            amount=min(1.,(seconds-cue['start'])/transition) if transition else 1.
            result={name:0.0 for name in result}
            result[current]+=amount;result[previous]+=1-amount
            break
    return result


def check_voice(directory):
    directory=Path(directory)
    preserved_voice(directory)
    source=json.loads((directory/'cue-source.json').read_text())
    for name in ('vo.mp3','dialogue.wav','mouth-cues.json','script.json'):
        if sha256(directory/name)!=source.get('files',{}).get(name):
            raise ValueError('mouth cue source mismatch: '+name+'; run prepare-voice again')
    cues=json.loads((directory/'mouth-cues.json').read_text())
    from pipeline.cartoon_lipsync import normalize_rhubarb
    normalized=normalize_rhubarb(cues)
    if abs(source['duration_seconds']-normalized['metadata']['duration'])>.03:
        raise ValueError('mouth cue duration differs from the preserved audio clock')
    return normalized


def animate_scene(bpy,job):
    from mathutils import Vector
    from pipeline.blender.june_studio_assets import aim_control
    rig=bpy.data.objects['June_Oxley_Rig'];head=bpy.data.objects['June_Head']
    scene=bpy.context.scene;frames=job['total_frames']
    hidden=[obj for obj in bpy.data.objects if obj.type in {'MESH','CURVE'} and not obj.hide_viewport]
    for obj in hidden:obj.hide_viewport=True
    rig.animation_data_clear();rig.animation_data_create()
    track=rig.animation_data.nla_tracks.new();track.name='Reusable body performance'
    walk=track.strips.new('Walk two steps',1,bpy.data.actions['June_Studio_Walk_Two_Steps'])
    walk.extrapolation='NOTHING'
    standing=track.strips.new('Stand and address',121,bpy.data.actions['June_Studio_Stand'])
    standing.frame_end=frames;standing.extrapolation='HOLD_FORWARD'
    gestures=rig.animation_data.nla_tracks.new();gestures.name='Reusable conversational gesture'
    strip=gestures.strips.new('Explain',139,bpy.data.actions['June_Studio_Explain'])
    strip.blend_in=12;strip.blend_out=18;strip.extrapolation='NOTHING'
    acting=bpy.data.actions.new('June_Shot_Acting');rig.animation_data.action=acting
    keys=head.data.shape_keys;keys.animation_data_clear();keys.animation_data_create()
    keys.animation_data.action=bpy.data.actions.new('June_Spuds_Facial_Performance')
    cues=json.loads(Path(job['cues']).read_text())['mouthCues']
    camera=bpy.data.objects['June_Camera_'+job['camera']]
    # Keyframe construction does not evaluate the expensive display meshes.
    for frame in range(1,frames+1):
        seconds=(frame-1-INTRO_FRAMES)/FPS
        weights=cue_weights(cues,seconds)
        for name,value in weights.items():
            key=keys.key_blocks[name];key.value=value;key.keyframe_insert('value',frame=frame)
        for name in ('blink_L','blink_R','smile','warm_eyes','brow_raise','concern'):
            value=0.0
            if name.startswith('blink'):
                value=max(max(0.,1-abs(frame-center)/3) for center in (79,136,253,348,426))
            elif name=='smile':
                value=.10+.45*max(0.,min(1.,(frame-250)/70))
            elif name=='warm_eyes':value=.45*max(0.,min(1.,(frame-265)/65))
            elif name=='brow_raise':value=.30*math.exp(-((frame-167)/24)**2)
            key=keys.key_blocks[name];key.value=value;key.keyframe_insert('value',frame=frame)
        attention=max(0.,min(1.,(frame-112)/25));attention=attention*attention*(3-2*attention)
        # Body stays planted while head and eyes lead the thought and settle.
        head_bone=rig.pose.bones['head']
        yaw=math.atan2(camera.location.x-.035,-(camera.location.y+1.06))
        head_bone.rotation_euler.y=yaw*.52*attention
        head_bone.rotation_euler.x=.017*math.sin((frame-125)*.04)*math.exp(-((frame-185)/110)**2)
        head_bone.rotation_euler.z=.012*math.exp(-((frame-205)/45)**2)
        head_bone.keyframe_insert('rotation_euler',frame=frame)
        aim_control(rig,'gaze',camera.location)
        rig.pose.bones['gaze'].keyframe_insert('location',frame=frame)
    for action in (acting,keys.animation_data.action):
        for curve in action.fcurves:
            for key in curve.keyframe_points:key.interpolation='LINEAR'
    scene.camera=camera;scene.frame_start=1;scene.frame_end=frames;scene.render.fps=FPS
    scene.render.resolution_x=job['width'];scene.render.resolution_y=job['height'];scene.render.resolution_percentage=100
    scene.render.engine=job['engine'];scene.cycles.samples=job['samples'];scene.cycles.use_denoising=True
    if job['engine']=='BLENDER_EEVEE_NEXT':scene.eevee.taa_render_samples=job['samples']
    scene.cycles.max_bounces=6;scene.cycles.diffuse_bounces=3;scene.cycles.glossy_bounces=3
    scene.render.use_persistent_data=True;scene.render.image_settings.file_format='PNG'
    scene['ce_voice_id']=VOICE_ID;scene['ce_voice_sha256']=job['voice_sha256'];scene['ce_production_approved']=False
    for obj in hidden:obj.hide_viewport=False
    return rig,head


def blender_job(job_path):
    import bpy
    job=json.loads(Path(job_path).read_text())
    if bpy.app.version_string != job['blender_version']:
        raise ValueError('Blender version differs from the reviewed asset runtime')
    bpy.ops.wm.open_mainfile(filepath=job['asset'])
    animate_scene(bpy,job)
    scene=bpy.context.scene;directory=Path(job['cache_directory']);directory.mkdir(parents=True,exist_ok=True)
    if job.get('audit_output') and not job.get('inspect_frames'):
        from pipeline.blender.audit_june_studio import audit
        status(job['progress_directory'],'checking_mechanics',frame_count=job['total_frames'])
        report=audit(bpy,job['audit_output'])
        report.update(asset_sha256=job['inputs']['files']['asset'],renderer_identity=job['identity'])
        atomic_json(job['audit_output'],report)
        if not report['mechanics_pass']:raise ValueError('evaluated studio mechanics failed; see '+job['audit_output'])
    # Optional inspection produces a real single frame without a completed cache.
    selected=job.get('inspect_frames') or list(range(job['start'],job['end']+1))
    for index,frame in enumerate(selected,1):
        started=time.monotonic()
        scene.frame_set(frame)
        scene.render.filepath=str(directory/f'frame_{frame-job["start"]+1:04d}.png')
        bpy.ops.render.render(write_still=True)
        progress=dict(shot=job['name'],completed_frames=index,total_frames=len(selected),global_frame=frame,
                      frame_seconds=round(time.monotonic()-started,3))
        status(directory,'rendering',**progress)
        if job.get('progress_directory'):status(job['progress_directory'],'rendering',**progress)
    if not job.get('inspect_frames'):
        complete_cache(directory,job['identity'],job['end']-job['start']+1,job['inputs'])
        status(directory,'completed',shot=job['name'],completed_frames=len(selected))
    if job.get('save_scene'):
        bpy.ops.wm.save_as_mainfile(filepath=job['save_scene'],compress=True)


def run(args):
    asset=Path(args.asset).resolve();voice=Path(args.voice_dir).resolve();out=Path(args.output_dir).resolve()
    out.mkdir(parents=True,exist_ok=True)
    if args.width<320 or args.width%32 or args.samples<1:
        raise ValueError('width must be a multiple of 32 >=320, with positive samples')
    receipt=json.loads(asset.with_suffix('.json').read_text())
    if receipt['asset_sha256']!=sha256(asset):raise ValueError('saved character library checksum mismatch')
    cues=check_voice(voice)
    runtime=subprocess.check_output([args.blender,'--version'],text=True)
    total=max(450,INTRO_FRAMES+math.ceil(cues['metadata']['duration']*FPS)+60)
    shots=[{'name':'01_entry','camera':'Wide','start':1,'end':120},
           {'name':'02_address','camera':'Close','start':121,'end':330},
           {'name':'03_reaction','camera':'Front','start':331,'end':total}]
    study=getattr(args,'study',None)
    if study:
        shots=[study_shot(study,total,cues['metadata']['duration'])]
    caches=[];summary=[]
    status(out,'preparing',frame_count=total,voice_id=VOICE_ID)
    for shot in shots:
        settings={**shot,'width':args.width,'height':args.width*9//16,'samples':args.samples,
                  'fps':FPS,'total_frames':total,'engine':args.engine,'blender_version':receipt['blender_version'],
                  'blender_runtime':runtime}
        files={'asset':asset,'renderer':Path(__file__),'body_pose_code':REPO/'pipeline/blender/june_studio_assets.py',
               'speech_clock':REPO/'pipeline/cartoon_lipsync.py','audio':voice/'vo.mp3','cues':voice/'mouth-cues.json',
               'utilities':REPO/'pipeline/june_studio.py','audit':REPO/'pipeline/blender/audit_june_studio.py'}
        identity,inputs=input_identity(files,settings)
        cache=out/'shot-cache'/identity
        hit=cache_valid(cache,identity,shot['end']-shot['start']+1)
        job={**settings,'asset':str(asset),'cues':str(voice/'mouth-cues.json'),
             'voice_sha256':sha256(voice/'vo.mp3'),'cache_directory':str(cache),'identity':identity,'inputs':inputs,
             'progress_directory':str(out)}
        if shot is shots[0]:job['audit_output']=str(out/'studio-mechanics-report.json')
        if args.inspect:
            job['inspect_frames']=[(shot['start']+shot['end'])//2]
            hit=False
        if shot['name']=='02_address' or study:job['save_scene']=str(out/'june-speaking-scene.blend')
        atomic_json(out/(shot['name']+'.json'),job)
        if not hit:
            status(out,'rendering',shot=shot['name'],cache_hit=False)
            log=out/(shot['name']+'.log')
            command=[args.blender,'-b','-t',str(args.threads),'--python-exit-code','1','--python',str(Path(__file__).resolve()),'--','--blender-job',str(out/(shot['name']+'.json'))]
            try:
                with log.open('w') as stream:subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=True)
            except subprocess.CalledProcessError as error:
                tail='\n'.join(log.read_text(errors='replace').splitlines()[-8:])
                raise RuntimeError(f'{shot["name"]} failed with return code {error.returncode}; log: {log}\n{tail}') from error
        summary.append({**shot,'identity':identity,'cache_hit':hit,'cache_directory':str(cache)})
        caches.append(cache)
    if args.inspect:
        atomic_json(out/'inspection.json',summary);status(out,'inspection_complete');return
    sequence=out/'assembly_frames';sequence.mkdir(exist_ok=True)
    frame_number=0
    for shot,cache,record in zip(shots,caches,summary):
        if not cache_valid(cache,record['identity'],shot['end']-shot['start']+1):
            raise ValueError('shot cache lost integrity before assembly')
        for local in range(1,shot['end']-shot['start']+2):
            frame_number+=1;destination=sequence/f'frame_{frame_number:04d}.png';destination.unlink(missing_ok=True)
            try:os.link(cache/f'frame_{local:04d}.png',destination)
            except OSError:shutil.copy2(cache/f'frame_{local:04d}.png',destination)
    status(out,'assembling',frame_count=frame_number)
    video=out/('June_Oxley_Likeness_Study.mp4' if study else 'June_Oxley_Studio_Development.mp4')
    audio_offset=(INTRO_FRAMES-shots[0]['start']+1)/FPS
    duration=frame_number/FPS
    subprocess.run(['ffmpeg','-v','error','-y','-framerate',str(FPS),'-i',str(sequence/'frame_%04d.png'),'-i',str(voice/'vo.mp3'),
                    '-filter_complex',f'[1:a]adelay={round(audio_offset*1000)}:all=1,apad=whole_dur={duration}[voice]',
                    '-map','0:v','-map','[voice]','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p',
                    '-c:a','aac','-b:a','192k','-ac','2','-t',str(duration),'-movflags','+faststart',str(video)],check=True)
    subprocess.run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'],check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(video)],text=True))
    stream=next(s for s in probe['streams'] if s['codec_type']=='video')
    if int(stream['nb_read_frames'])!=frame_number or stream['width']!=args.width or stream['height']!=args.width*9//16:
        raise ValueError('decoded development video does not match its frame clock or dimensions')
    atomic_json(out/'studio-render-report.json',{'status':'development_review','production_approved':False,'voice_id':VOICE_ID,
                 'voice_sha256':sha256(voice/'vo.mp3'),'audio_start_seconds':audio_offset,'voice_duration_seconds':cues['metadata']['duration'],
                 'video_sha256':sha256(video),'frame_count':frame_number,'fps':FPS,'duration_seconds':duration,
                 'study':bool(study),'animation_frame_count':total,
                 'width':args.width,'height':args.width*9//16,'shots':summary,'asset_sha256':sha256(asset),'decoded':True})
    status(out,'completed',video=str(video),frame_count=frame_number)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--blender-job');parser.add_argument('--asset');parser.add_argument('--voice-dir');parser.add_argument('--output-dir')
    parser.add_argument('--blender',default='blender');parser.add_argument('--width',type=int,default=640)
    parser.add_argument('--samples',type=int,default=8);parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--engine',choices=['CYCLES','BLENDER_EEVEE_NEXT'],default='CYCLES')
    parser.add_argument('--inspect',action='store_true')
    parser.add_argument('--study',nargs=3,metavar=('CAMERA','FIRST','LAST'),
                        help='Render one bounded development study, preserving the full voice take')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None
    args=parser.parse_args(argv)
    if args.blender_job:blender_job(args.blender_job)
    else:
        if not all((args.asset,args.voice_dir,args.output_dir)):parser.error('asset, voice-dir and output-dir are required')
        try:run(args)
        except Exception as error:
            status(args.output_dir,'failed',error=str(error));raise


if __name__=='__main__':main()
