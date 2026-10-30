import json
from pathlib import Path
import unittest

from pipeline import cartoon_dialogue_delivery as delivery


ROOT = delivery.new.ROOT
PACKAGE = ROOT / "collab/june_rest_your_hands_v1"


class PublishedDialogueSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((PACKAGE/"new-scene-report.json").read_text())
        cls.receipt = json.loads((PACKAGE/"source-build-receipt.json").read_text())

    def test_completed_new_scene_is_not_a_human_or_release_approval(self):
        self.assertEqual(self.report["frame_count"], 207)
        self.assertEqual(self.report["duration_seconds"], 6.9)
        for key in ("new_performance_human_accepted", "production_release_allowed", "main_branch_merge_allowed"):
            self.assertFalse(self.report[key])
        self.assertTrue(self.report["current_job_picture_reused_after_audio_only_failure"])
        self.assertFalse(self.report["picture_reencoded"])
        self.assertEqual(self.report["cash_cost"], 0)

    def test_actual_media_and_executed_pixel_code_match_the_reports(self):
        for name in ("scene.mp4", "scene.mov", "compiled-motion-v1.json", "decoded-frame-inventory.json", "decoded-contact-sheet.png"):
            self.assertEqual(delivery.new.scene._hash(PACKAGE/name), self.report["artifacts"][name])
        self.assertEqual(delivery.pixel_code_hash(Path(delivery.new.__file__)), self.report["pixel_renderer_ast_sha256"])
        self.assertEqual(delivery.new.scene._hash(Path(delivery.new.__file__)), self.report["auditor_source_sha256"])
        self.assertEqual(delivery.new.scene._hash(Path(delivery.__file__)), self.report["delivery_source_sha256"])

    def test_quality_gate_was_fixed_not_lowered_and_pcm_timestamps_pass(self):
        audit = self.report["audit"]
        self.assertLess(self.receipt["original_aac_snr_db"], 40)
        self.assertGreater(audit["aac_snr_db"], 40)
        self.assertTrue(audit["mov_source_audio_exact_with_mono_stereo_duplication"])
        self.assertTrue(audit["mp4_picture_packets_equal_mov"])
        self.assertTrue(audit["all_frame_timestamps_exact"])
        self.assertEqual(audit["all_frames_decoded"], 207)
        self.assertTrue(all(item["psnr_db"] >= 38 for item in audit["compression_samples"]))

    def test_decoded_inventory_is_not_mislabeled_as_raw_source_provenance(self):
        rows = json.loads((PACKAGE/"decoded-frame-inventory.json").read_text())
        self.assertEqual([row["frame"] for row in rows], list(range(1,208)))
        self.assertTrue(all(row["hash_domain"] == "decoded_preview_rgb24_not_source_pixels" for row in rows))
        self.assertFalse(self.report["source_raw_all_frame_inventory_available"])
        self.assertEqual(len(list((PACKAGE/"references").glob("*.png"))), 6)
        delivery.new.bank.approval()


if __name__ == "__main__":
    unittest.main()
