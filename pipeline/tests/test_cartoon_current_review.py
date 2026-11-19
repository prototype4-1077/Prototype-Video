"""Check clean-source review contracts without rendering a movie."""

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from pipeline import cartoon_current_review as current


EDGES = (0, 564, 678, 789, 864, 912, 1140)
PROTECTED = ((789, 864), (912, 1140))
INSERT = (608, 628)
CLOCK = [1920, 1080, 30, 1140]
PROOF = os.environ.get("JUNE_CURRENT_BUILD_PROOF")


class CurrentReviewTests(unittest.TestCase):
    def test_dual_preflight_uses_tracked_sources_without_rendering(self):
        with patch.object(current.source.working, "build", side_effect=AssertionError("preflight rendered")):
            checked = current.check("both")
        self.assertEqual(checked["variants"], ["face", "visitor"])
        self.assertEqual(checked["source_edl_zero_based"], list(EDGES))
        self.assertEqual(checked["clock"], CLOCK)
        self.assertEqual(checked["cash_cost"], 0)
        self.assertIs(checked["legacy_master_required"], False)
        self.assertIs(checked["external_render_cache_required"], False)
        self.assertIs(checked["prior_full_movie_required"], False)
        self.assertIs(checked["protected_picture_regenerates_from_source"], True)

    def test_edit_list_partitions_review_and_only_twenty_native_frames_differ(self):
        self.assertEqual(current.EDGES, EDGES)
        self.assertEqual(current.PROTECTED, PROTECTED)
        self.assertEqual(current.REACTION, (564, 678))
        intro, coffee, reactions = current.native_inventories("both")
        self.assertEqual(set(intro), set(range(564)))
        self.assertEqual(set(coffee), set(range(678, 789)) | set(range(864, 912)))
        self.assertEqual(set(reactions), {"face", "visitor"})
        native = [set(intro), set(coffee), set(range(*current.REACTION))]
        protected = set().union(*(set(range(a, b)) for a, b in PROTECTED))
        self.assertEqual(sum(map(len, native)), 837)
        self.assertEqual(len(protected), 303)
        self.assertEqual(set().union(*native, protected), set(range(1140)))
        self.assertEqual(len(reactions["face"]), 114)
        self.assertEqual(len(reactions["visitor"]), 114)
        differences = [i for i, (a, b) in enumerate(zip(reactions["face"], reactions["visitor"]), 564) if a != b]
        self.assertEqual(differences, list(range(*INSERT)))

    def test_inventory_rejects_missing_frames_and_changed_pixels(self):
        wanted = {678: "picture-a", 679: "picture-b"}
        current.assert_frames("test", dict(reversed(list(wanted.items()))), wanted)
        for actual, error in (
            ({678: "picture-a"}, "native frame census changed"),
            ({678: "picture-a", 680: "picture-b"}, "native frame census changed"),
            ({678: "picture-a", 679: "wrong"}, "native pixel mismatch at output frame 679"),
        ):
            with self.subTest(actual=actual), self.assertRaisesRegex(ValueError, error):
                current.assert_frames("test", actual, wanted)
        first = current.visitor.native_reference()
        with patch.object(current.visitor, "native_reference", return_value=["wrong", *first[1:]]):
            with self.assertRaisesRegex(ValueError, "changed outside the story insert"):
                current.native_inventories("both")

    def test_toggle_rejects_picture_drift_outside_reaction_and_audio_drift(self):
        def packet(i):
            return dict(pts=i * 1000, dts=i * 1000, duration=1000, data_hash=f"frame-{i}")

        base = [packet(i) for i in range(1140)]
        alternate = list(base)
        alternate[608] = {**base[608], "data_hash": "insert"}
        a = {"v:0": base, "a:0": [packet(0)], "s:0": [packet(0)]}
        b = {**a, "v:0": alternate}
        with patch.object(current.probe, "packet_info", side_effect=lambda file, stream: {"a": a, "b": b}[file][stream]):
            self.assertEqual(current.only_reaction_differs("a", "b"), {
                "equal_video_packets_outside_reaction": 1026,
                "audio_caption_packets_exact_between_variants": True,
            })
            alternate[789] = {**base[789], "data_hash": "protected picture drift"}
            with self.assertRaisesRegex(ValueError, "story toggle changed another shot"):
                current.only_reaction_differs("a", "b")
            alternate[789] = base[789]
            b["a:0"] = [{**packet(0), "data_hash": "changed sound"}]
            with self.assertRaisesRegex(ValueError, "story toggle altered a:0"):
                current.only_reaction_differs("a", "b")

    @unittest.skipUnless(PROOF, "set JUNE_CURRENT_BUILD_PROOF to a fresh dual-build directory or receipt")
    def test_actual_fresh_dual_build_receipt(self):
        path = Path(PROOF)
        if path.is_dir():
            path /= "current-review-build.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertIs(report["completed"], True)
        self.assertIs(report["prior_full_movie_used_as_source"], False)
        self.assertIs(report["human_accepted"], False)
        self.assertIs(report["production_release"], False)
        self.assertEqual(report["scene_builds_from_source"], 1)
        self.assertEqual(report["frame_clock"], CLOCK)
        self.assertEqual(report["preflight"]["variants"], ["face", "visitor"])
        self.assertEqual(report["mix_sha256"], current.MIX_SHA)
        self.assertEqual(report["captions_sha256"], current.CAPTIONS_SHA)
        current.bound(path.parent / "mix.wav", current.MIX_SHA)
        current.bound(path.parent / "captions.srt", current.CAPTIONS_SHA)
        self.assertEqual(report["same_build_comparison"], {
            "equal_video_packets_outside_reaction": 1026,
            "audio_caption_packets_exact_between_variants": True,
        })
        self.assertEqual(set(report["variants"]), {"face", "visitor"})
        for name, movie in report["variants"].items():
            with self.subTest(variant=name):
                self.assertEqual(movie["native_rgb_frames_matched"], 837)
                self.assertEqual(movie["audit"]["decoded_repaired_frames_exact"], 303)
                self.assertIs(movie["audit"]["mov_pcm_exact"], True)
                self.assertIs(movie["audit"]["all_pts_exact"], True)
                current.bound(path.parent / movie["preview"], movie["preview_sha256"])
                current.bound(path.parent / movie["pcm_master"], movie["pcm_master_sha256"])


if __name__ == "__main__":
    unittest.main()
