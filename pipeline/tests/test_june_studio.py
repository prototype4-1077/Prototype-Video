import json
from pathlib import Path
import tempfile
import unittest

from pipeline.june_studio import input_identity, complete_cache, cache_valid, sha256
from pipeline.june_studio_render import cue_weights, check_voice, study_shot, VOICE_ID
from pipeline.blender.june_studio_character import load_targets, EXPRESSIONS


class StudioCacheTests(unittest.TestCase):
    def test_asset_camera_and_action_changes_invalidate_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);asset=root/'asset';action=root/'action'
            asset.write_bytes(b'character A');action.write_bytes(b'gesture A')
            files={'asset':asset,'action':action}
            original,_=input_identity(files,{'camera':'close','samples':16})
            changed,_=input_identity(files,{'camera':'wide','samples':16})
            self.assertNotEqual(original,changed)
            action.write_bytes(b'gesture B')
            changed,_=input_identity(files,{'camera':'close','samples':16})
            self.assertNotEqual(original,changed)
            action.write_bytes(b'gesture A');asset.write_bytes(b'character B')
            changed,_=input_identity(files,{'camera':'close','samples':16})
            self.assertNotEqual(original,changed)

    def test_partial_missing_corrupt_and_wrong_clock_are_not_cache_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'frame_0001.png').write_bytes(b'one')
            self.assertFalse(cache_valid(root,'identity',2))
            with self.assertRaises(FileNotFoundError):complete_cache(root,'identity',2,{})
            (root/'frame_0002.png').write_bytes(b'two')
            complete_cache(root,'identity',2,{})
            self.assertTrue(cache_valid(root,'identity',2))
            self.assertFalse(cache_valid(root,'identity',3))
            self.assertFalse(cache_valid(root,'other',2))
            (root/'frame_0002.png').write_bytes(b'corrupted')
            self.assertFalse(cache_valid(root,'identity',2))

    def test_unrelated_shot_changes_do_not_invalidate_a_shot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);asset=root/'asset';other=root/'other';asset.write_bytes(b'master')
            a,_=input_identity({'asset':asset},{'camera':'wide'})
            other.write_bytes(b'an edit to a separate shot')
            b,_=input_identity({'asset':asset},{'camera':'wide'})
            self.assertEqual(a,b)


class StudioSpeechTests(unittest.TestCase):
    def test_short_study_keeps_complete_voice_and_original_animation_clock(self):
        shot=study_shot(('Close','109','288'),450,4.32)
        self.assertEqual(shot['end']-shot['start']+1,180)
        # The first spoken sample still lands on animation frame 121.
        self.assertAlmostEqual((121-shot['start'])/30,.4)
        for request in (('Close','122','288'),('Close','109','249'),
                        ('Close','0','288'),('Close','109','451'),
                        ('Unknown','109','288')):
            with self.subTest(request=request), self.assertRaises(ValueError):
                study_shot(request,450,4.32)

    def test_replacing_cues_without_realignment_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'vo.mp3').write_bytes(b'preserved audio')
            (root/'dialogue.wav').write_bytes(b'decoded take')
            (root/'script.json').write_text('{}')
            (root/'voiceover-manifest.json').write_text(json.dumps({'voice_id':VOICE_ID}))
            (root/'SHA256SUMS').write_text(sha256(root/'vo.mp3')+'  vo.mp3\n')
            (root/'mouth-cues.json').write_text(json.dumps({'metadata':{'duration':1},
                'mouthCues':[{'start':0,'end':1,'value':'D'}]}))
            receipt={'duration_seconds':1,'files':{name:sha256(root/name) for name in
                       ('vo.mp3','dialogue.wav','mouth-cues.json','script.json')}}
            (root/'cue-source.json').write_text(json.dumps(receipt))
            self.assertEqual(check_voice(root)['metadata']['duration'],1)
            (root/'mouth-cues.json').write_text(json.dumps({'metadata':{'duration':1},
                'mouthCues':[{'start':0,'end':1,'value':'F'}]}))
            with self.assertRaisesRegex(ValueError,'source mismatch'):check_voice(root)

    def test_voice_substitution_and_changed_audio_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'vo.mp3').write_bytes(b'preserved audio')
            (root/'SHA256SUMS').write_text(sha256(root/'vo.mp3')+'  vo.mp3\n')
            (root/'voiceover-manifest.json').write_text(json.dumps({'voice_id':'placeholder'}))
            with self.assertRaisesRegex(ValueError,'Spuds'):check_voice(root)
            (root/'voiceover-manifest.json').write_text(json.dumps({'voice_id':VOICE_ID}))
            (root/'vo.mp3').write_bytes(b'different audio')
            with self.assertRaisesRegex(ValueError,'checksum'):check_voice(root)

    def test_transitions_are_bounded_and_silent_intervals_are_neutral(self):
        cues=[{'start':.2,'end':.5,'value':'D'},{'start':.5,'end':.8,'value':'F'}]
        for i in range(100):
            values=cue_weights(cues,i/100)
            self.assertAlmostEqual(sum(values.values()),1)
            self.assertTrue(all(0<=v<=1 for v in values.values()))
        self.assertEqual(cue_weights(cues,.1)['X'],1)
        self.assertEqual(cue_weights(cues,.9)['X'],1)
        self.assertGreater(cue_weights(cues,.53)['D'],0)
        self.assertGreater(cue_weights(cues,.53)['F'],0)

    def test_every_authored_expression_has_its_real_pinned_source(self):
        targets=load_targets()
        required={name for mix in EXPRESSIONS.values() for name in mix}
        self.assertTrue(required <= set(targets))
        self.assertTrue(all(len(targets[name])>50 for name in required))


if __name__=='__main__':unittest.main()
