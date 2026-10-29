"""Regression checks on the completed source-built prototype; never rerenders."""
from pathlib import Path
import hashlib
import json
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "collab/phase42_working_model_v1"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class PublishedWorkingModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = read(PACKAGE / "working-model-report-v1.json")
        cls.audit = read(PACKAGE / "phase42-integrated-scene-review-report-v1.json")
        cls.rows = read(PACKAGE / "source-frame-inventory-v1.json")
        cls.proof = read(PACKAGE / "clean-source-build-receipt-v1.json")

    def test_actual_build_completed_without_granting_final_approval(self):
        self.assertTrue(self.report["technical_build_completed"])
        self.assertEqual(self.report["frame_count"], 303)
        self.assertEqual(self.report["duration_seconds"], 10.1)
        self.assertTrue(self.report["provisional_polish_deferred"])
        for key in ("full_performance_final_acceptance", "production_release_allowed", "main_branch_merge_allowed"):
            self.assertIs(self.report[key], False)
        self.assertFalse(self.report["external_prior_scene_cache_used"])
        self.assertEqual(self.report["cash_cost"], 0)

    def test_published_movies_and_audit_match_completed_build(self):
        for key in ("movie", "exact_audio_copy", "scene_audit_report"):
            item = self.report[key]
            self.assertEqual(hashlib.sha256((PACKAGE / item["path"]).read_bytes()).hexdigest(), item["sha256"])

    def test_all_source_frames_keep_the_passed_opening_and_comparison(self):
        self.assertEqual([row["output_frame"] for row in self.rows], list(range(1, 304)))
        self.assertTrue(all(row["built_from_tracked_source"] for row in self.rows))
        old = read(ROOT / "collab/phase42_integrated_scene_review_v1/source-frame-inventory-v1.json")
        self.assertEqual([row["rgb_sha256"] for row in self.rows[:75]], [row["rgb_sha256"] for row in old[:75]])
        passed = read(ROOT / "collab/phase42_mouth_hand_integrated_ab_v1/integrated-mouth-hand-review-report-v1.json")
        self.assertEqual(len(passed["frames"]), 138)
        for row in passed["frames"]:
            self.assertEqual(self.rows[row["output_frame"] - 1]["rgb_sha256"], row["candidate_rgb_sha256"])
        self.assertEqual(self.rows[247]["rgb_sha256"], passed["accepted_full_close_frame_rgb_sha256"])
        self.assertEqual(self.report["hard_cut_output_frames"], [76, 238])

    def test_all_frame_timestamps_and_approved_audio_survive_export(self):
        audit = self.audit["audit"]
        self.assertTrue(audit["all_303_frame_timestamps_exact"])
        self.assertTrue(audit["mov_audio_bit_exact"])
        self.assertTrue(audit["mp4_video_packets_equal_mov"])
        self.assertGreater(audit["aac_preview_snr_db"], 40)
        self.assertTrue(all(row["rgb_psnr_db"] >= 35 for row in audit["compression_sample_checks"]))
        self.assertEqual(self.audit["approved_audio_wav_sha256"], "3c6965f8030d9c7360a418cb19dd6b193396a5c1a37b8084ca247622a259c14f")

    def test_clean_source_receipt_identifies_executed_code(self):
        self.assertEqual(self.proof["source_commit"], "1ec1ce40f84f7fdec2bf21104013cc1dab114184")
        self.assertEqual(self.proof["source_method"], "git archive HEAD; extract tracked files into an isolated directory")
        self.assertFalse(self.proof["external_prior_render_cache_copied"])
        self.assertEqual(self.proof["entrypoint_source_sha256"], self.report["entrypoint_source_sha256"])
        self.assertEqual(hashlib.sha256((ROOT / "pipeline/cartoon_working_model.py").read_bytes()).hexdigest(), self.report["entrypoint_source_sha256"])
        self.assertEqual(self.proof["all_138_passed_comparison_frames_match"], True)


if __name__ == "__main__":
    unittest.main()
