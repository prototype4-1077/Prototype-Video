"""Check source inputs and immutable edit routing without expensive full renders."""
from pathlib import Path
import json
import tempfile
import unittest

from pipeline import cartoon_full_short_source as source


class FullShortSourceTests(unittest.TestCase):
    def test_preflight_needs_no_external_render_master(self):
        report=source.preflight()
        self.assertEqual(report["clock"],[1920,1080,30,1140])
        self.assertEqual(report["plate_count"],7)
        self.assertEqual(report["stand_pose_count"],5)
        self.assertIs(report["legacy_master_required"],False)
        self.assertIs(report["external_render_cache_required"],False)

    def test_only_earlier_spans_are_replaced(self):
        self.assertEqual(source.original_spans(),[(0,789),(864,912)])
        earlier={n for a,b in source.original_spans() for n in range(a,b)}
        passed=set(range(789,864))|set(range(912,1140))
        self.assertEqual(len(earlier),837)
        self.assertEqual(len(passed),303)
        self.assertFalse(earlier & passed)
        self.assertEqual(earlier | passed,set(range(1140)))

    def test_existing_work_is_preserved(self):
        with tempfile.TemporaryDirectory() as td, self.assertRaises(FileExistsError):
            source.build(Path(td))

    def test_wrong_historical_reference_never_used_for_comparison(self):
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/"not-a-review.mp4"
            bad.touch()
            with self.assertRaisesRegex(ValueError,"pinned historical review"):
                source.compare_review(bad,bad)

    def test_clean_archive_receipt_binds_to_actual_source_and_protected_media(self):
        pkg=source.ROOT/"collab/june_full_short_source_v1"
        receipt=json.loads((pkg/"clean-build-receipt.json").read_text(encoding="utf-8"))
        report_path=pkg/"source-build-report.json"
        self.assertEqual(source.cut.beat.digest(report_path),receipt["source_build_report_sha256"])
        result=json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(result["entrypoint_sha256"],source.cut.beat.digest(Path(source.__file__)))
        edit,_,_=source.cut.load_plan()
        self.assertEqual(receipt["rebuilt_protected_mov_sha256"],edit["repaired"]["sha256"])
        self.assertEqual(receipt["baseline_pcm_sha256"],result["sha256"]["mix.wav"])
        self.assertTrue(receipt["isolated_tracked_snapshot"])
        self.assertFalse(receipt["render_cache_copied"])
        self.assertFalse(receipt["human_acceptance"])
        self.assertEqual(receipt["exit_code"],0)
        self.assertEqual(result["repaired_render_source"],"fresh tracked-art invocation")
        self.assertEqual(result["audit"]["decoded_repaired_frames_exact"],303)
        self.assertGreater(result["comparison_after_render"]["minimum_psnr_db"],32)

    def test_native_inventory_has_exact_unmodified_earlier_frame_clock(self):
        pkg=source.ROOT/"collab/june_full_short_source_v1"
        inventory=pkg/"native-early-frames.json"
        report=json.loads((pkg/"source-build-report.json").read_text(encoding="utf-8"))
        self.assertEqual(source.cut.beat.digest(inventory),report["sha256"][inventory.name])
        frames=json.loads(inventory.read_text(encoding="utf-8"))["frames"]
        self.assertEqual([r["frame"] for r in frames],[*range(789),*range(864,912)])
        self.assertEqual(frames[225]["shot"],"GS030")
        self.assertEqual(frames[225]["shot_frame_1based"],1)
        self.assertEqual(frames[789]["shot"],"GS060")
        self.assertEqual(frames[789]["shot_frame_1based"],187)


if __name__=="__main__":
    unittest.main()
