"""Check source inputs and immutable edit routing without expensive full renders."""
from pathlib import Path
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


if __name__=="__main__":
    unittest.main()
