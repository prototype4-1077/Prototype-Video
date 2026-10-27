"""Build a fresh, unapproved v6 art review from verified rendered frames."""
import argparse
import base64
import copy
import hashlib
import html
import io
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from PIL import Image
from pipeline import review
from pipeline.june_studio import atomic_json, sha256

VIEWS = ('body', 'close', 'front', 'smile', 'blink', 'speech-d')


def verified_frames(asset, render):
    audit = json.loads((render / 'v6-asset-audit.json').read_text())
    frames = json.loads((render / 'render-frames.json').read_text())
    if not audit.get('technical_checks_pass') or audit['asset_sha256'] != sha256(asset):
        raise ValueError('the exact v6 model must pass its technical audit')
    if audit['scene_sha256'] != sha256(render / 'june-speaking-scene.blend'):
        raise ValueError('editable performance changed after audit')
    if any(frames[k] != audit[k] for k in ('asset_sha256', 'scene_sha256')):
        raise ValueError('rendered frames belong to a different model or performance')
    if [frames[k] for k in ('first', 'last', 'fps', 'width', 'height')] != [109, 270, 30, 640, 360]:
        raise ValueError('unexpected study frame range or resolution')
    expected = {f'frame_{i:04d}.png' for i in range(1, 163)}
    if set(frames['frames']) != expected:
        raise ValueError('incomplete study frame sequence')
    for name, digest in frames['frames'].items():
        if sha256(render / 'frames' / name) != digest:
            raise ValueError('rendered frame changed: ' + name)
    if sha256(render / 'voice' / 'vo.mp3') != audit['performance']['voice_sha256']:
        raise ValueError('preserved voice bytes changed')
    return audit, frames


def picture_data(path, width=1000):
    image = Image.open(path).convert('RGB')
    image.thumbnail((width, width * 2), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=90)
    return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()


def package(asset, render, comparison, destination, license_file):
    asset, render, comparison, out = map(lambda p: Path(p).resolve(), (asset, render, comparison, destination))
    if out in (asset.parent, render, Path(license_file).resolve().parent):
        raise ValueError('use a separate delivery directory')
    audit, frames = verified_frames(asset, render)
    receipt = json.loads(asset.with_suffix('.json').read_text())
    if receipt['asset_sha256'] != sha256(asset):
        raise ValueError('asset receipt does not match')
    code = Path(__file__).resolve().parent
    if receipt['refinement_sha256'] != sha256(code / 'blender' / 'refine_june_studio_v6.py') or receipt['body_pose_sha256'] != sha256(code / 'blender' / 'june_studio_assets.py'):
        raise ValueError('rebuild the art candidate after changing its refinement or pose code')
    for name in VIEWS:
        with Image.open(asset.parent / (name + '.png')) as image:
            if image.size != (1280, 720):
                raise ValueError('all art views must be the completed 1280 x 720 renders')
            image.verify()
    out.mkdir(parents=True, exist_ok=True)
    video = out / 'June_Oxley_v6_Full_Body_Study.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', '30', '-i',
        str(render / 'frames' / 'frame_%04d.png'), '-i', str(render / 'voice' / 'vo.mp3'),
        '-filter_complex', '[1:a]adelay=400:all=1,apad[a]', '-map', '0:v:0', '-map', '[a]',
        '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-movflags', '+faststart', '-t', '5.4', str(video)], check=True)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
        '-show_format', '-of', 'json', str(video)], text=True))
    stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    audio_stream = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
    if [stream[k] for k in ('width', 'height', 'nb_frames', 'r_frame_rate')] != [640, 360, '162', '30/1']:
        raise ValueError('encoded movie differs from the verified frame clock')
    if stream['pix_fmt'] != 'yuv420p' or audio_stream['codec_name'] != 'aac' or abs(float(probe['format']['duration']) - 5.4) > .01:
        raise ValueError('encoded study delivery contract failed')
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'], check=True)
    report = {'asset_sha256': sha256(asset), 'scene_sha256': audit['scene_sha256'],
        'voice_sha256': audit['performance']['voice_sha256'], 'video_sha256': sha256(video),
        'frame_count': 162, 'duration_seconds': 5.4, 'fps': 30, 'width': 640, 'height': 360,
        'voice_offset_seconds': .4, 'decoded': True, 'production_approved': False,
        'art_views': {name: sha256(asset.parent / (name + '.png')) for name in VIEWS},
        'comparison_sha256': sha256(comparison)}
    atomic_json(out / 'studio-render-report.json', report)
    identity = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()[:20]
    scene = {'start': 0, 'duration': 5.4,
        'text': 'Funny thing: the account got lighter before the debt did.',
        'query': 'June stands on the porch, speaks the preserved Spuds line, gestures and settles.',
        'rationale': 'Judge the face and groom, collar and bib construction, relaxed hands, work boots and full-body framing.'}
    row = review._scene_payload(scene, 0, picture_data(render / 'frames' / 'frame_0083.png'))
    row['why_chosen'], row['motion_mode'] = scene['rationale'], 'animated 3D geometry'
    payload = {'schema_version': review.SCHEMA_VERSION, 'generated_at': review._now(),
        'slug': 'june-studio-v6-' + identity, 'script_fingerprint': identity,
        'title': 'June Oxley · v6 art review', 'genre': '3D artwork development',
        'video_file': video.name, 'development_only': True, 'production_approved': False,
        'asset_sha256': report['asset_sha256'], 'video_sha256': report['video_sha256'],
        'voice_sha256': report['voice_sha256'], 'art_views': report['art_views'],
        'scenes': [row], 'overall': {'decision': 'unreviewed', 'comments': ''}}
    metadata = copy.deepcopy(payload)
    for item in metadata['scenes']:
        item.pop('preview')
    atomic_json(out / 'scene-review.json', metadata)
    page = review.HTML_TEMPLATE.replace('__TITLE__', html.escape(payload['title'])).replace(
        '__REVIEW_JSON__', json.dumps(payload, ensure_ascii=True).replace('</', '<\\/'))
    gallery = '<section class="art"><h2>Artwork comparison</h2><img alt="Approved target, v5 and v6 comparison" src="' + picture_data(comparison, 1800) + '">'
    gallery += '<p>V6 improves the silhouette and clothing construction. Facial softness, groom roots, the waist-to-leg transition and finer hand acting still need art review.</p><div class="art-grid">'
    for name, label in (('body', 'Full body · gentle smile'), ('close', 'Likeness and neckline'),
                        ('smile', 'Smile'), ('blink', 'Closed eyelids'), ('speech-d', 'Open speech shape'), ('front', 'Front camera · neutral')):
        gallery += '<figure><img alt="' + label + '" src="' + picture_data(asset.parent / (name + '.png')) + '"><figcaption>' + label + '</figcaption></figure>'
    gallery += '</div></section>'
    movie = '<section class="art"><h2>Scene 1 · full-body study</h2><video controls playsinline preload="metadata" src="data:video/mp4;base64,' + base64.b64encode(video.read_bytes()).decode() + '"></video><p>5.4 seconds · original Spuds take · artwork remains unapproved. Record face, clothing, pose and boot feedback below.</p></section>'
    page = page.replace('<main>', '<main>' + movie + gallery)
    page = page.replace('Overall Video Decision', 'Overall Art Study Decision').replace('Approve video', 'Approve art study').replace('Video needs changes', 'Art study needs changes')
    page = page.replace('</style>', '.art{margin:24px 0}.art img,.art video{display:block;width:100%;height:auto}.art-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.art-grid figure{margin:0}.art p,.art figcaption{line-height:1.5}.preview{min-height:0;aspect-ratio:16/9;align-self:start}.scene{grid-template-columns:minmax(300px,.9fr) minmax(0,1fr)}@media(max-width:760px){.art-grid,.scene{grid-template-columns:1fr}}\n</style>')
    (out / 'June_Oxley_v6_Scene_Review.html').write_text(page)
    copies = {asset: out / 'june-studio.blend', asset.with_suffix('.json'): out / 'june-studio.json',
        comparison: out / 'June_Oxley_v6_Comparison.jpg', Path(license_file): out / 'SOURCE_LICENSE.txt'}
    for name in ('june-speaking-scene.blend', 'v6-asset-audit.json', 'eyelid-report.json',
                 'studio-mechanics-report.json', 'render-frames.json'):
        copies[render / name] = out / name
    for name in VIEWS:
        copies[asset.parent / (name + '.png')] = out / (name + '.png')
    (out / 'voice').mkdir(exist_ok=True)
    copies[render / 'voice' / 'vo.mp3'] = out / 'voice' / 'vo.mp3'
    for source, target in copies.items():
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
    (out / 'scene-review.html').write_text(page)
    (out / 'README.txt').write_text(
        'JUNE OXLEY V6 ART CANDIDATE — UNAPPROVED\n\n'
        'Open scene-review.html for the numbered review, comparison, six art views and movie.\n'
        'Scene 1 and the overall decision start unreviewed. Export feedback after judging the artwork.\n\n'
        'june-studio.blend is the editable master. Append June_Character_Studio_v6 to reuse June.\n'
        'june-speaking-scene.blend has the original packed Spuds take and preserved facial/acting actions.\n'
        'Blender 4.2.0. The timeline is 1–450; preview is 109–270; voice begins at 121.\n'
        'The movie is 640 x 360 at 30 fps. Art stills are 1280 x 720.\n'
        'The original Rhubarb cue-source folder was absent from the recovered v5 bundle.\n'
        'This review reuses its exact packed audio and facial action; it does not regenerate speech cues.\n\n'
        'Technical checks measure dependencies, weights, boot identity, foot actions, rig contacts,\n'
        'eleven framing poses and thirty sampled closed-eye poses. They do not approve likeness,\n'
        'acting or all possible cloth collisions. Keep the next art pass focused on facial softness,\n'
        'groom roots, the waist-to-leg transition and hand acting. The porch remains a development set.\n\n'
        'Source branch: prototype4-1077/Prototype-Video, agent/june-studio-art-v6.\n'
        'See docs/JUNE_STUDIO_ART_V6.md for reproduction and validation details.\n'
        'The v5 source package and its existing approvals were not changed.\n')
    files = [p for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS.txt']
    (out / 'SHA256SUMS.txt').write_text(''.join(sha256(p) + '  ' + str(p.relative_to(out)) + '\n' for p in files))
    archive = out.parent / 'June_Oxley_v6_Artwork_Package.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(out.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(out))
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError('delivery archive failed CRC verification')
    return {'archive': str(archive), 'archive_sha256': sha256(archive), 'video_sha256': sha256(video),
            'art_decision': 'unreviewed', 'production_approved': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('asset', 'render-dir', 'comparison', 'output-dir', 'license-file'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.asset, args.render_dir, args.comparison, args.output_dir, args.license_file)))
