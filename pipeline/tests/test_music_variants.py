import json
import os
import sys
import tempfile
import unittest
import wave

import numpy as np

PIPELINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PIPELINE)

import audio_variants
import music
import prep


class MusicVariantTests(unittest.TestCase):
    def test_three_score_families_are_distinct_stereo_wavs(self):
        with tempfile.TemporaryDirectory() as td:
            audio = []
            for variant in (1, 2, 3):
                path = os.path.join(td, f"music_{variant:02d}.wav")
                music.gen(path, 1.5, variant=variant)
                with wave.open(path, "rb") as w:
                    self.assertEqual(2, w.getnchannels())
                    self.assertEqual(music.SR, w.getframerate())
                    self.assertGreaterEqual(w.getnframes(), int(1.49 * music.SR))
                    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                audio.append(x)
            for i in range(3):
                for j in range(i + 1, 3):
                    self.assertFalse(np.array_equal(audio[i], audio[j]))
                    self.assertGreater(float(np.mean(np.abs(audio[i].astype(float)
                                                       - audio[j].astype(float)))), 20.0)

    def test_profile_specific_labels_are_stable(self):
        self.assertEqual("Cinematic Pulse", music.variant_label(1))
        self.assertEqual("Glass Horizon", music.variant_label(2))
        self.assertEqual("Deep Current", music.variant_label(3))
        self.assertEqual("Prism Drift", music.variant_label(1, "dmt"))
        self.assertEqual("Porch Shuffle", music.variant_label(1, profile="june_oxley"))

    def test_manifest_requires_at_least_three_existing_tracks(self):
        with tempfile.TemporaryDirectory() as td:
            variants = []
            for i in range(1, 4):
                name = f"music_{i:02d}.wav"
                open(os.path.join(td, name), "wb").close()
                variants.append({"file": name, "label": f"Choice {i}"})
            script = {"music": "music_01.wav", "music_variants": variants}
            self.assertEqual(3, len(audio_variants.require(script, td)))
            manifest = audio_variants.write_manifest(td, variants)
            self.assertEqual("final_music_03.mp4", manifest["variants"][2]["video"])
            self.assertEqual(
                "final_youtube_music_03.mp4",
                manifest["variants"][2]["youtube_video"],
            )
            with open(os.path.join(td, "music_variants.json")) as f:
                loaded = json.load(f)
            self.assertEqual(3, loaded["minimum_choices"])

    def test_first_generated_filename_remains_backward_compatible(self):
        with tempfile.TemporaryDirectory() as td:
            script = {
                "title": "Compatibility",
                "scenes": [{"text": "One.", "start": 0.0, "duration": 1.0}],
            }
            with open(os.path.join(td, "script.json"), "w") as f:
                json.dump(script, f)
            saved = prep.prepare_music(td, script)
            self.assertEqual("music.wav", saved["music"])
            self.assertEqual(
                ["music.wav", "music_02.wav", "music_03.wav"],
                [item["file"] for item in saved["music_variants"]],
            )


if __name__ == "__main__":
    unittest.main()

