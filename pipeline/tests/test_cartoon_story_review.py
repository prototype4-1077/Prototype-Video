"""Audit the source-only story variants without encoding a film."""

import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from pipeline import cartoon_story_review as review


PACKAGE = review.root / "collab/june_story_review_clean_v1"
LOCAL_PROOF = os.environ.get("JUNE_STORY_BUILD_PROOF")
PROOF = Path(LOCAL_PROOF) if LOCAL_PROOF else PACKAGE / "story-review-build.json"
if PROOF.is_dir():
    PROOF /= "story-review-build.json"

COMMON_CLOCK = (0, 129, 225, 396, 452, 564, 678, 789, 864, 912, 963)
CLOCKS = {"handoff": COMMON_CLOCK+(1191,), "reaction": COMMON_CLOCK+(993, 1221)}
PROTECTED = {"handoff": ((789, 864), (963, 1191)), "reaction": ((789, 864), (993, 1221))}


def _sample_packets(n, label):
    return [dict(pts=i*1000, dts=(i-2)*1000, duration=1000, data_hash=f"{label}:packet:{i}",
                 flags="K__" if i == 0 else "___") for i in range(n)]


def _sample_frames(n, label):
    return [f"{label}:decoded:{i}" for i in range(n)]


class StoryReviewTests(unittest.TestCase):
    def test_shared_edl_and_original_protected_source_offsets(self):
        handoff, reaction = review.edit("handoff"), review.edit("reaction")
        self.assertEqual(handoff[:-1], reaction[:-2])
        self.assertEqual(reaction[-2], ("coffee-reaction", 30))
        self.assertEqual(handoff[-1], reaction[-1])
        for variant, edl in (("handoff", handoff), ("reaction", reaction)):
            with self.subTest(variant=variant):
                self.assertEqual(review.clock(edl), CLOCKS[variant])
                locations = {key: (a, b) for (key, _), a, b in zip(edl, CLOCKS[variant], CLOCKS[variant][1:])}
                self.assertEqual((locations["protected-pour"], locations["protected-closer"]), PROTECTED[variant])
                self.assertEqual(sum(b-a for a, b in PROTECTED[variant]), 303)
        with self.assertRaisesRegex(ValueError, "unknown story ending"):
            review.edit("not-a-variant")

    def test_real_preflight_does_not_read_an_older_full_movie_or_render(self):
        real_digest = review.cut.beat.digest

        def without_old_movie(path):
            if Path(path).name in {"twelve-dollar-mug.mp4", "twelve-dollar-mug.mov"}:
                raise AssertionError("preflight looked for a historical full cut")
            return real_digest(path)

        with patch.object(review.cut.beat, "digest", side_effect=without_old_movie), \
                patch.object(review, "digest", side_effect=without_old_movie), \
                patch.object(review, "make_shots", side_effect=AssertionError("preflight rendered shots")), \
                patch.object(review.cut.media, "encoder_command", side_effect=AssertionError("preflight encoded")):
            evidence = review.check("both")
        self.assertEqual(evidence["variants"], CLOCKS)
        self.assertEqual(set(evidence["source_receipts"]), {"loan", "arrival", "handoff", "reaction"})
        self.assertEqual(evidence["cash_cost"], 0)
        self.assertIs(evidence["external_cache_required"], False)
        self.assertIs(evidence["prior_full_movie_required"], False)
        self.assertIs(evidence["protected_source_check"]["protected_picture_regenerates_from_source"], True)

    def test_shared_segment_index_fails_on_bad_decode_count_or_codec(self):
        lengths = dict(review.edit("reaction"))

        def packet_info(path, stream):
            self.assertEqual(stream, "v:0")
            return _sample_packets(lengths[path.stem], path.stem)

        def decode(path):
            return _sample_frames(lengths[path.stem], path.stem)

        with patch.object(review.packets, "packet_info", side_effect=packet_info), \
                patch.object(review.ledger, "frame_hashes", side_effect=decode) as decoded, \
                patch.object(review.packets, "codec_hash", return_value="shared-avc") as codec:
            stage = Path("unwritten-source-shots")
            result = review.index_segments(stage, "both")
            self.assertEqual(set(result), set(lengths))
            self.assertEqual(decoded.call_count, len(lengths))
            self.assertEqual(len(result["protected-closer"][1]), 228)
            decoded.side_effect = lambda p: decode(p)[:-1] if p.stem == "loan" else decode(p)
            with self.assertRaisesRegex(ValueError, "loan: missing decoded samples"):
                review.index_segments(stage, "both")
            decoded.side_effect = decode
            codec.side_effect = lambda p: "different-avc" if p.stem == "return" else "shared-avc"
            with self.assertRaisesRegex(ValueError, "incompatible H.264 parameters"):
                review.index_segments(stage, "both")

    def test_delivery_audit_rejects_changed_packets_decodes_or_protected_frames(self):
        all_packets, all_frames, index = [], [], {}
        for (name, n), start in zip(review.edit("reaction"), CLOCKS["reaction"]):
            packets, frames = _sample_packets(n, name), _sample_frames(n, name)
            index[name] = (review.packets.signature(packets), frames, "shared-avc")
            all_packets.extend({**r, "pts": r["pts"]+start*1000, "dts": r["dts"]+start*1000} for r in packets)
            all_frames.extend(frames)
        protected = _sample_frames(75, "protected-pour") + _sample_frames(228, "protected-closer")
        with patch.object(review.packets, "packet_info", return_value=all_packets), \
                patch.object(review.ledger, "frame_hashes", return_value=all_frames):
            self.assertEqual(review.check_output("reaction", Path("mock.mp4"), index, protected), 1221)
            packet = all_packets[993]
            all_packets[993] = {**packet, "data_hash": "shifted closer packet changed"}
            with self.assertRaisesRegex(ValueError, "mux changed a source picture packet"):
                review.check_output("reaction", Path("mock.mp4"), index, protected)
            all_packets[993] = packet
            frame = all_frames[992]
            all_frames[992] = "bad decode at inserted shot edge"
            with self.assertRaisesRegex(ValueError, "mux changed decoded pictures"):
                review.check_output("reaction", Path("mock.mp4"), index, protected)
            all_frames[992] = frame
            protected[75] = "wrong approved closing pixel"
            with self.assertRaisesRegex(ValueError, "original pour or closer pixels drifted"):
                review.check_output("reaction", Path("mock.mp4"), index, protected)

    @unittest.skipUnless(LOCAL_PROOF or PROOF.is_file(), "no clean story-build receipt")
    def test_complete_clean_build_receipt(self):
        evidence = json.loads(PROOF.read_text(encoding="utf-8"))
        self.assertIs(evidence["completed"], True)
        self.assertIs(evidence["prior_full_movie_used"], False)
        self.assertIs(evidence["shared_shots_built_once"], True)
        self.assertIs(evidence["human_accepted"], False)
        self.assertIs(evidence["production_release"], False)
        self.assertEqual(evidence["builder_sha256"], review.digest(Path(review.__file__)))
        self.assertEqual(evidence["preflight"]["variants"], {k: list(v) for k, v in CLOCKS.items()})
        self.assertEqual(set(evidence["variants"]), set(CLOCKS))
        for name, proof in evidence["variants"].items():
            with self.subTest(variant=name):
                count = CLOCKS[name][-1]
                self.assertEqual(proof["clock"], [1920, 1080, 30, count])
                self.assertEqual(proof["verified_source_packets_and_decoded_frames"], count)
                self.assertEqual(proof["protected_frames_exact"], 303)
                self.assertEqual(proof["pcm_pairs_exact"], count*1600)
                self.assertIs(proof["all_18_captions_verified"], True)
                self.assertGreaterEqual(proof["preview_aac_snr_db"], 40)
                self.assertLessEqual(proof["preview_true_peak_dbtp"], -1.0)
                for key in ("movie", "pcm_master"):
                    recorded = proof[f"{key}_sha256"]
                    self.assertRegex(recorded, r"^[a-f0-9]{64}$")
                    if LOCAL_PROOF:
                        self.assertEqual(recorded, review.digest(PROOF.parent / proof[key]))
                if LOCAL_PROOF:
                    self.assertEqual(proof["pcm_sha256"], review.digest((PROOF.parent / proof["movie"]).with_name("mix.wav")))


if __name__ == "__main__":
    unittest.main()
