from __future__ import annotations

from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_mouth_hand_review as review


class IntegratedReviewContractTests(unittest.TestCase):
    def test_review_preserves_complete_speech_window_without_retiming(self) -> None:
        self.assertEqual(review.SOURCE_FRAMES, tuple(range(25, 163)))
        self.assertEqual(len(review.SOURCE_FRAMES), 138)
        self.assertEqual((review.SOURCE_FRAMES[0] + 74) / 30, 3.3)
        self.assertEqual((review.SOURCE_FRAMES[-1] + 75) / 30, 7.9)

    def test_comparison_keeps_both_delivery_crops_at_one_to_one_pixel_scale(self) -> None:
        old = np.full((1080, 1920, 3), (35, 90, 160), np.uint8)
        new = np.full_like(old, (180, 70, 30))
        panel = np.asarray(review.comparison_panel(old, new, 115))
        self.assertEqual(panel.shape, old.shape)
        x1, y1, x2, y2 = review.DELIVERY_CROP
        self.assertTrue(np.array_equal(panel[32:1052, :960], old[y1:y2, x1:x2]))
        self.assertTrue(np.array_equal(panel[32:1052, 960:], new[y1:y2, x1:x2]))

    def test_existing_evidence_fails_before_preparing_or_launching_any_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.object(review.scene.integration, "prepare_repaired_acting") as prepare:
            with self.assertRaises(FileExistsError):
                review.build(Path(temporary))
            prepare.assert_not_called()


class IntegratedRepairLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.old = review.scene.integration.prepare_repaired_acting()
        cls.new = review.candidate_preparation(cls.old)

    def test_simultaneous_adapters_preserve_every_pixel_outside_their_declared_union(self) -> None:
        with review.scene.accepted_lids(self.old), review.scene.accepted_lids(self.new):
            for frame in (27, 115, 148):
                baseline, _ = review.scene.compose_direct_frame(self.old, frame)
                candidate = review.compose_candidate(self.new, frame)
                changed = np.any(baseline != candidate, axis=2)
                self.assertTrue(changed.any(), frame)
                self.assertFalse(np.any(changed & ~review.allowed_support(self.new, frame)), frame)

    def test_full_close_endpoint_remains_exact_under_both_adapters(self) -> None:
        with review.scene.accepted_lids(self.new):
            pixels = review.compose_candidate(self.new, 173)
        self.assertEqual(review.scene.acting._rgb_hash(pixels), "155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40")
        self.assertIsNot(self.old.integration.direct.visemes, self.new.integration.direct.visemes)
        self.assertIsNot(self.old.integration.direct.native_cache, self.new.integration.direct.native_cache)


class IntegratedReviewPublishedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package = review.REPO_ROOT / "collab/phase42_mouth_hand_integrated_ab_v1"
        cls.report = json.loads((cls.package / "integrated-mouth-hand-review-report-v1.json").read_text(encoding="utf-8"))

    def test_all_frames_use_the_exact_reviewed_baseline_and_bound_adapter_sources(self) -> None:
        report = self.report
        self.assertFalse(report["human_accepted"])
        self.assertFalse(report["production_promotion_allowed"])
        self.assertFalse(report["original_scene_framing_and_cuts_modified"])
        self.assertTrue(report["all_303_baseline_cache_frames_verified"])
        self.assertEqual(report["accepted_full_close_frame_rgb_sha256"], "155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40")
        for key, module in (("implementation_sha256", review), ("mouth_adapter_sha256", review.mouth),
                            ("hand_adapter_sha256", review.hand)):
            self.assertEqual(report[key], review.scene._hash(Path(module.__file__)))
        inventory = json.loads((review.PACKAGE / "source-frame-inventory-v1.json").read_text(encoding="utf-8"))
        self.assertEqual([row["source_frame"] for row in report["frames"]], list(review.SOURCE_FRAMES))
        for row in report["frames"]:
            self.assertEqual(row["baseline_rgb_sha256"], inventory[row["output_frame"] - 1]["rgb_sha256"])
            self.assertEqual(row["changed_outside_declared_mouth_hand_support"], 0)
            self.assertEqual(row["mug_changed_pixels"], 0)
        self.assertEqual(sum(row["hand_adapter_active"] for row in report["frames"]), 57)
        for name, entry in report["artifacts"].items():
            self.assertEqual(review.scene._hash(self.package / name), entry["sha256"], name)
        for name in ("ATTRIBUTION.md", "sources.json"):
            self.assertEqual((self.package / name).read_bytes(), (review.PACKAGE / name).read_bytes())

    def test_actual_decoded_timestamps_colors_and_audio_match_the_scene_window(self) -> None:
        ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        self.assertIsNotNone(ffmpeg)
        self.assertIsNotNone(ffprobe)
        mp4, mov = self.package / f"{review.NAME}.mp4", self.package / f"{review.NAME}.mov"
        probe = review.scene._probe(mp4, ffprobe)
        video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
        self.assertEqual((int(video["nb_frames"]), int(video["nb_read_frames"])), (138, 138))
        self.assertEqual((int(video["width"]), int(video["height"])), (1920, 1080))
        self.assertEqual(video["avg_frame_rate"], "30/1")
        self.assertEqual(video["sample_aspect_ratio"], "1:1")
        self.assertEqual(video["color_range"], "tv")
        for key in ("color_space", "color_transfer", "color_primaries"):
            self.assertEqual(video[key], "bt709")
        frames = json.loads(subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_frames",
                                            "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(mp4)],
                                           check=True, capture_output=True).stdout)["frames"]
        self.assertEqual(len(frames), 138)
        for index, frame in enumerate(frames):
            self.assertAlmostEqual(float(frame["best_effort_timestamp_time"]), index / 30, delta=1e-6)
        accepted = review.scene.accepted_components()
        full, _ = review.scene.picture._read_pcm24_wave(review.REPO_ROOT / accepted["audio"]["path"])
        clip = review.mouth.preview_excerpt(full, 25, 162)
        decoded = subprocess.run([ffmpeg, "-v", "error", "-i", str(mov), "-map", "0:a:0", "-f", "s24le", "-"],
                                 check=True, capture_output=True).stdout
        self.assertEqual(hashlib.sha256(decoded).hexdigest(), self.report["mov_excerpt_pcm_sha256"])
        raw = np.frombuffer(decoded, np.uint8).reshape(-1, 3)
        integer = raw[:, 0].astype(np.int32) | raw[:, 1].astype(np.int32) << 8 | raw[:, 2].astype(np.int32) << 16
        integer = np.where(integer & 0x800000, integer - 0x1000000, integer).reshape(-1, 2)
        self.assertTrue(np.array_equal(integer, clip))
        self.assertEqual(review.scene._video_hash(mp4, ffmpeg), review.scene._video_hash(mov, ffmpeg))


if __name__ == "__main__":
    unittest.main()
