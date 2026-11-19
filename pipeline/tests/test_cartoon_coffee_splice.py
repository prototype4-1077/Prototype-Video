"""Guard the GS060 replacement ranges and the retained review evidence."""

import json
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
COLLAB = ROOT / "collab"
CHANGE = ((678, 789), (864, 912))
EDGES = (0, 678, 789, 864, 912, 1140)
SEGMENTS = tuple(zip(EDGES, EDGES[1:]))
PROTECTED = ((789, 864), (912, 1140))
UNCHANGED = 981


def _signature(rows):
    return [
        (int(row["pts"]), int(row["dts"]), int(row["duration"]),
         row["flags"], row["data_hash"], row.get("side_data_list", []))
        for row in rows
    ]


def audit_video_packets(source, candidate):
    """Independently check the 30kHz packet clock and the two splice ranges."""
    if len(source) != EDGES[-1] or len(candidate) != EDGES[-1]:
        raise ValueError("video packet census changed")
    copied = 0
    for first, stop in SEGMENTS:
        original = source[first:stop]
        revised = candidate[first:stop]
        expected = {i * 1000 for i in range(first, stop)}
        for rows in (original, revised):
            if "K" not in rows[0]["flags"] or {int(p["pts"]) for p in rows} != expected:
                raise ValueError(f"frame clock or splice keyframe changed: {first}:{stop}")
            if any(int(p["duration"]) != 1000 for p in rows):
                raise ValueError(f"frame duration changed: {first}:{stop}")
        if (first, stop) in CHANGE:
            if {p["pts"]: p["data_hash"] for p in original} == {p["pts"]: p["data_hash"] for p in revised}:
                raise ValueError(f"replacement did not land: {first}:{stop}")
        else:
            if _signature(original) != _signature(revised):
                raise ValueError(f"copied picture changed: {first}:{stop}")
            copied += stop - first
    return copied


class CoffeeSpliceTests(unittest.TestCase):
    def test_span_census_and_source_receipt(self):
        from pipeline import cartoon_coffee_cut as splice

        self.assertEqual(tuple(splice.CHANGE), CHANGE)
        self.assertEqual(tuple(splice.PLAN), EDGES)
        self.assertEqual(sum(b - a for a, b in CHANGE), 159)
        self.assertEqual(sum(b - a for a, b in PROTECTED), 303)
        self.assertEqual(EDGES[-1] - sum(b - a for a, b in CHANGE), UNCHANGED)
        previous = COLLAB / "june_pencil_continuity_v1/continuity-reviewed-window.json"
        self.assertEqual(splice.SOURCE_SHA, json.loads(previous.read_text(encoding="utf-8"))["candidate_sha256"])

    def test_published_proof_does_not_claim_approval(self):
        receipt = COLLAB / "june_coffee_continuity_v1/verification.json"
        proof = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(proof["replaced_spans"], [list(span) for span in CHANGE])
        self.assertEqual(proof["unchanged_video_packets"], UNCHANGED)
        self.assertEqual(proof["decoded_repaired_frames_exact"], 303)
        self.assertIs(proof["audio_subtitle_packets_exact"], True)
        self.assertIs(proof["human_accepted"], False)
        self.assertIs(proof["production_release"], False)

    def test_independent_packet_audit_rejects_protected_edits_and_missing_replacements(self):
        source = [dict(pts=i * 1000, dts=i * 1000, duration=1000,
                       flags="K__" if i in EDGES else "___", data_hash=f"orig-{i}")
                  for i in range(EDGES[-1])]
        candidate = [dict(row) for row in source]
        for first, _ in CHANGE:
            candidate[first]["data_hash"] = f"edited-{first}"
        self.assertEqual(audit_video_packets(source, candidate), UNCHANGED)
        for index, field, value, error in (
            (789, "data_hash", "wrong", "copied picture changed"),
            (912, "flags", "___", "splice keyframe changed"),
            (865, "pts", 864000, "frame clock"),
            (678, "data_hash", "orig-678", "replacement did not land"),
        ):
            with self.subTest(index=index, field=field):
                broken = list(candidate)
                broken[index] = {**candidate[index], field: value}
                with self.assertRaisesRegex(ValueError, error):
                    audit_video_packets(source, broken)

    @unittest.skipUnless(os.environ.get("JUNE_COFFEE_TEST_SOURCE") and os.environ.get("JUNE_COFFEE_TEST_CANDIDATE"),
                         "full review movies are local-only")
    def test_local_movies_packet_for_packet(self):
        from pipeline import cartoon_compassion_review as review
        from pipeline import cartoon_coffee_cut as splice

        base = Path(os.environ["JUNE_COFFEE_TEST_SOURCE"])
        result = Path(os.environ["JUNE_COFFEE_TEST_CANDIDATE"])
        self.assertEqual(review.cut.beat.digest(base), splice.SOURCE_SHA)
        self.assertEqual(audit_video_packets(review.packet_info(base, "v:0"), review.packet_info(result, "v:0")), UNCHANGED)
        for stream in ("a:0", "s:0"):
            with self.subTest(stream=stream):
                before = review.packet_info(base, stream)
                self.assertTrue(before)
                self.assertEqual(_signature(before), _signature(review.packet_info(result, stream)))


if __name__ == "__main__":
    unittest.main()
