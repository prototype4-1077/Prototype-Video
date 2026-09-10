"""Source protection and preserved-performance identity gates for v6."""
import json
from pathlib import Path
import tempfile
import unittest

from pipeline.blender.refine_june_studio_v6 import checked_source
from pipeline.blender.prepare_june_studio_v6_review import checked_inputs
from pipeline.june_studio import sha256
from pipeline.june_studio_v6_package import verified_frames


class V6SourceTests(unittest.TestCase):
    def test_package_rejects_partial_or_modified_frames_before_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset, scene, voice = root / 'model.blend', root / 'june-speaking-scene.blend', root / 'voice' / 'vo.mp3'
            voice.parent.mkdir()
            for path in (asset, scene, voice):
                path.write_bytes(path.name.encode())
            audit = {'technical_checks_pass': True, 'asset_sha256': sha256(asset),
                     'scene_sha256': sha256(scene), 'performance': {'voice_sha256': sha256(voice)}}
            (root / 'v6-asset-audit.json').write_text(json.dumps(audit))
            (root / 'frames').mkdir()
            hashes = {}
            for i in range(1, 163):
                path = root / 'frames' / f'frame_{i:04d}.png'
                path.write_bytes(str(i).encode())
                hashes[path.name] = sha256(path)
            manifest = {k: audit[k] for k in ('asset_sha256', 'scene_sha256')}
            manifest.update(first=109, last=270, fps=30, width=640, height=360, frames=hashes)
            manifest_path = root / 'render-frames.json'
            manifest_path.write_text(json.dumps(manifest))
            verified_frames(asset, root)
            (root / 'frames' / 'frame_0081.png').write_bytes(b'changed frame')
            with self.assertRaisesRegex(ValueError, 'rendered frame changed'):
                verified_frames(asset, root)
            hashes.pop('frame_0081.png')
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'incomplete study'):
                verified_frames(asset, root)

    def test_refinement_rejects_source_directory_and_changed_source_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'v5' / 'june-studio.blend'
            source.parent.mkdir()
            source.write_bytes(b'original v5')
            source.with_suffix('.json').write_text(json.dumps({
                'asset_version': 'studio-v5', 'asset_sha256': sha256(source)}))
            with self.assertRaisesRegex(ValueError, 'separate output'):
                checked_source(source, source.parent / 'other.blend')
            checked_source(source, root / 'v6' / 'june-studio.blend')
            source.write_bytes(b'changed source')
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                checked_source(source, root / 'v6' / 'june-studio.blend')

    def test_performance_reuse_rejects_changed_scene_model_and_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset, source, performance = [root / name for name in ('v6.blend', 'v5.blend', 'scene.blend')]
            for path in (asset, source, performance):
                path.write_bytes(path.name.encode())
            receipt = {'asset_version': 'studio-v6', 'asset_sha256': sha256(asset),
                       'source_asset_sha256': sha256(source)}
            asset.with_suffix('.json').write_text(json.dumps(receipt))
            packed = {'scene_sha256': sha256(performance), 'timeline': [1, 450], 'preview': [109, 270],
                      'voice': [{'frame_start': 121, 'packed': True, 'sha256': 'take identity'}]}
            path = root / 'packed-scene-check.json'
            path.write_text(json.dumps(packed))
            self.assertEqual(checked_inputs(asset, source, performance)[1], 'take identity')
            for target, message in ((asset, 'studio-v6 receipt'), (source, 'v5 source identity'),
                                    (performance, 'performance identity')):
                original = target.read_bytes()
                target.write_bytes(b'different bytes')
                with self.assertRaisesRegex(ValueError, message):
                    checked_inputs(asset, source, performance)
                target.write_bytes(original)
            packed['voice'][0]['frame_start'] = 122
            path.write_text(json.dumps(packed))
            with self.assertRaisesRegex(ValueError, 'frame 121'):
                checked_inputs(asset, source, performance)
            packed['voice'][0]['frame_start'] = 121
            packed['preview'] = [122, 270]
            path.write_text(json.dumps(packed))
            with self.assertRaisesRegex(ValueError, 'performance clock'):
                checked_inputs(asset, source, performance)


if __name__ == '__main__':
    unittest.main()
