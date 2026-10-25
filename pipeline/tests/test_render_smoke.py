"""Small real-media smoke test; uses generated test patterns and a tone, never TTS."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assemble
import prep
import quality_gate


class LandscapeRenderSmokeTests(unittest.TestCase):
    def test_default_dmt_master_matches_its_manifest_and_decodes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            clip = root / 'test-pattern.mp4'
            voice = root / 'vo.mp3'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=640x360:rate=30','-t','1.5','-an','-c:v','libx264','-pix_fmt','yuv420p',str(clip)],check=True)
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=3',str(voice)],check=True)
            script = {'title':'RENDER CHECK','slug':'technical-fixture-only','genre':'dmt',
                      'voiceover':'vo.mp3','user_vo':True,
                      'scenes':[{'text':'A moving pattern.','keywords':['moving','pattern'],
                                 'start':0,'duration':1.5,'clip':str(clip)},
                                {'text':'Return to this room.','keywords':['room'],
                                 'start':1.5,'duration':1.5,'clip':str(clip)}]}
            (root / 'script.json').write_text(json.dumps(script))
            prep.prep(str(root))
            for index in range(2):
                assemble.render_scene(str(root), index, 'youtube')
            assemble.concat(str(root), 'youtube')
            self.assertEqual([p.name for p in root.glob('final*.mp4')], ['final_youtube.mp4'])
            manifest = json.loads((root / 'music_variants.json').read_text())
            self.assertEqual(manifest['delivery']['label'], 'Deep Portal')
            self.assertEqual(manifest['delivery']['youtube_video'], 'final_youtube.mp4')
            report = quality_gate.run_quality_gate(root, deep=True)
            self.assertTrue(report['passed'], report['failures'])
            probe = report['outputs']['youtube']['probe']
            self.assertEqual((probe['width'], probe['height']), (1920,1080))
            self.assertEqual(probe['video_codec'], 'h264')
            self.assertEqual(probe['audio_codec'], 'aac')
            self.assertAlmostEqual(probe['duration_s'],3,delta=.1)


if __name__ == '__main__':
    unittest.main()
