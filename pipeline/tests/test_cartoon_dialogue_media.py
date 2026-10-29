from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np

from pipeline import cartoon_dialogue_media as media
from pipeline import cartoon_dialogue_scene as scene


class DialogueMediaTests(unittest.TestCase):
    def test_resample_precedes_padding_and_exact_sample_trim(self):
        # Synthetic22.05kHz Piper output exercises the actual FFmpeg path that
        # previously padded/trimmed in the wrong sample-rate domain.
        real_run = subprocess.run
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            model = base / "fixture.onnx"
            model.write_bytes(b"test fixture; never loaded as a model")
            Path(str(model)+".json").write_text("{}", encoding="utf-8")
            def local_run(command, **kwargs):
                if str(command[0]) == str(Path(sys.executable).resolve()):
                    audio = Path(command[command.index("--output_file")+1])
                    signal = (2000*np.sin(np.arange(11025)*2*np.pi*220/22050)).astype("<i2")
                    with wave.open(str(audio), "wb") as output:
                        output.setparams((1,2,22050,0,"NONE","not compressed"))
                        output.writeframes(signal.tobytes())
                    return subprocess.CompletedProcess(command, 0)
                return real_run(command, **kwargs)
            def fake_rhubarb(audio, output, **kwargs):
                payload = {"metadata": {"duration": 1.9}, "mouthCues": [
                    {"start": 0, "end": .4, "value": "X"},
                    {"start": .4, "end": .9, "value": "D"},
                    {"start": .9, "end": 1.9, "value": "X"}]}
                output.write_text(json.dumps(payload), encoding="utf-8")
                return payload
            with patch.object(media.subprocess, "run", side_effect=local_run), patch.object(media, "run_rhubarb", side_effect=fake_rhubarb):
                report = media.prepare("Fixture speech", base/"output", piper=sys.executable, voice=model, rhubarb=sys.executable)
            samples, probe = scene.scene.picture._read_pcm24_wave(base/"output/dialogue.wav")
            self.assertEqual(report["frame_count"], 57)
            self.assertEqual(probe["sample_count"], 91200)
            self.assertTrue(np.any(samples))
            self.assertFalse(np.any(samples[:19200]))
            self.assertFalse(np.any(samples[-48000:]))
            self.assertFalse(report["speech_time_stretch_used"])

    def test_existing_media_is_rejected_before_invoking_any_tool(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(media, "executable") as tool:
            with self.assertRaises(FileExistsError):
                media.prepare("Words", Path(folder), piper="unused", voice=Path("unused"), rhubarb="unused")
            tool.assert_not_called()


if __name__ == "__main__":
    unittest.main()
