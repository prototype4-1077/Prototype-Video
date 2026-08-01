import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image


PIPELINE = Path(__file__).resolve().parents[1]
ROOT = PIPELINE.parent
FINISH_PROFILE = ROOT / "concept" / "style_frames" / "june_oxley_npr_finish_v1.json"
sys.path.insert(0, str(ROOT))

from pipeline.cartoon_ai_finish import (  # noqa: E402
    _sha256,
    validate_numbered_frames,
    validate_video_contract,
)


class CartoonAiFinishTest(unittest.TestCase):
    def test_finish_profile_pins_free_tool_model_clock_and_temporal_gate(self):
        profile = json.loads(FINISH_PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile["finish_version"], "1.0.0")
        self.assertEqual(profile["tool"]["license_family"], "open_source")
        self.assertRegex(profile["tool"]["archive_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(profile["model"]["binary_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(profile["clock"]["frame_count"], 453)
        self.assertEqual(profile["clock"]["delivery_dimensions"], [1920, 1080])
        self.assertEqual(profile["temporal_audition"]["visual_disposition"], "passed")
        self.assertGreater(profile["temporal_audition"]["static_background_adjacent_luma_difference"]["reduction_percent"], 0)

    def test_numbered_frames_require_exact_sequence_and_dimensions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for number in range(1, 4):
                Image.new("RGB", (16, 9), (number, 0, 0)).save(root / f"frame_{number:04d}.png")
            frames = validate_numbered_frames(root, frame_count=3, width=16, height=9)
            self.assertEqual([path.name for path in frames], ["frame_0001.png", "frame_0002.png", "frame_0003.png"])
            (root / "frame_0002.png").unlink()
            with self.assertRaisesRegex(ValueError, "sequence mismatch"):
                validate_numbered_frames(root, frame_count=3, width=16, height=9)

    def test_numbered_frames_reject_wrong_upscale_dimensions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Image.new("RGB", (15, 9)).save(root / "frame_0001.png")
            with self.assertRaisesRegex(ValueError, "dimensions"):
                validate_numbered_frames(root, frame_count=1, width=16, height=9)

    def test_video_contract_is_exact_and_can_require_audio(self):
        probe = {
            "streams": [
                {"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "30/1", "nb_read_frames": "453"},
                {"codec_type": "audio", "sample_rate": "48000"},
            ],
            "format": {"duration": "15.100"},
        }
        result = validate_video_contract(
            probe, frame_count=453, fps=30, width=1920, height=1080, require_audio=True
        )
        self.assertEqual(result["duration_seconds"], 15.1)
        self.assertEqual(result["audio_sample_rate"], 48000)
        missing_audio = json.loads(json.dumps(probe))
        missing_audio["streams"].pop()
        with self.assertRaisesRegex(ValueError, "missing audio"):
            validate_video_contract(missing_audio, frame_count=453, fps=30, require_audio=True)

    def test_video_contract_rejects_wrong_frame_count(self):
        probe = {
            "streams": [
                {"codec_type": "video", "width": 1920, "height": 1080, "avg_frame_rate": "30/1", "nb_read_frames": "452"}
            ]
        }
        with self.assertRaisesRegex(ValueError, "452 != 453"):
            validate_video_contract(probe, frame_count=453, fps=30)

    def test_sha256_is_stable_for_delivery_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "input.bin"
            source.write_bytes(b"June Oxley delivery evidence\n")
            self.assertEqual(
                _sha256(source),
                "81610af9d74aa95b5f6a313f5b136313ee47ccfb8bc25d88ca7d120bf2d5acfd",
            )


if __name__ == "__main__":
    unittest.main()
