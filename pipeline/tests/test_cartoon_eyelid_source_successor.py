from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from PIL import Image

from pipeline import cartoon_eyelid_source_successor as successor


class EyelidSourceSuccessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.review = successor.REPO_ROOT / "collab/phase42_human_rejected_gates_successors_v1"
        cls.report = json.loads(
            (cls.review / "phase42-eyelid-source-successor-report-v1.json").read_text(encoding="utf-8")
        )

    def test_ai_source_is_provenance_locked_and_same_size_as_plate(self) -> None:
        source = successor.REPO_ROOT / successor.AI_SOURCE_RELATIVE
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), successor.AI_SOURCE_SHA256)
        plate = successor.REPO_ROOT / "concept/style_frames/june-golden-scene-gs070-resolution-plate-v1.png"
        with Image.open(source) as source_image, Image.open(plate) as plate_image:
            self.assertEqual(source_image.size, (1672, 941))
            self.assertEqual(source_image.size, plate_image.size)
        provenance = json.loads(source.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertFalse(provenance["usage_policy"]["whole_generated_frame_allowed"])
        self.assertTrue(provenance["usage_policy"]["eye_region_extraction_only"])

    def test_review_artifact_proves_full_occlusion_and_bounded_motion(self) -> None:
        direct = self.report["variants"]["ai_direct"]
        self.assertEqual(direct["render_audit"]["evidence"]["iris_occlusion_ratios"], [1.0, 1.0])
        sequence = self.report["ai_direct_neighbor_sequence"]
        self.assertLessEqual(sequence["maximum_adjacent_eye_crop_8x8_mean_delta"], 130.0)
        self.assertEqual([row["phase36_frame"] for row in sequence["frames"]], list(range(240, 257)))
        self.assertEqual(
            [row["blink_closure"] for row in sequence["frames"]],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0],
        )

    def test_review_loop_contains_every_neighbor_frame(self) -> None:
        path = self.review / "phase42-eyelid-ai-direct-f240-f256-loop-v1.webp"
        with Image.open(path) as image:
            self.assertEqual(image.n_frames, 17)
            self.assertEqual(image.size, (371, 220))

    def test_rejected_v4_hash_is_reproduced_without_mutation(self) -> None:
        self.assertEqual(
            self.report["variants"]["rejected_v4"]["phase36_rgb_sha256"],
            "13788db7275b7b62c0f5d18987fd954803334481c48ef65091035d12ff8009de",
        )
        self.assertEqual(
            self.report["rejected_v4_report_sha256"],
            "fd08ee030123fc96585994825fc49942a937e9e631722478fa54bcee6bc36a7f",
        )


if __name__ == "__main__":
    unittest.main()
