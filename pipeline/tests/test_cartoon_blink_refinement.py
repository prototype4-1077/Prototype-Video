from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

from pipeline import cartoon_blink_refinement as blink


class BlinkRefinementControlTests(unittest.TestCase):
    shape, center, radius = (120, 180), (50, 50), (20, 16)

    def masks(self, value: float):
        return blink.curved_masks(self.shape, self.center, self.radius, value)

    def test_schedule_is_slower_one_blink_with_two_full_close_frames(self) -> None:
        schedule = [blink.candidate_closure(frame) for frame in range(1, 229)]
        starts = sum(value > 0 and (index == 0 or schedule[index - 1] == 0) for index, value in enumerate(schedule))
        self.assertEqual(starts, 1)
        self.assertEqual(sum(value == 1 for value in schedule), 2)
        self.assertEqual(schedule[80], 0.0)
        self.assertEqual(blink.candidate_closure(167), 0.0)
        self.assertEqual(blink.candidate_closure(179), 0.0)
        self.assertTrue(all(blink.candidate_closure(frame + 1) >= blink.candidate_closure(frame) for frame in range(167, 172)))
        self.assertTrue(all(blink.candidate_closure(frame + 1) <= blink.candidate_closure(frame) for frame in range(173, 179)))

    def test_open_and_closed_art_masks_are_exact_predecessor_endpoints(self) -> None:
        for value in (0.0, 1.0):
            for actual, expected in zip(self.masks(value), blink.BASE_MASKS(self.shape, self.center, self.radius, value)):
                self.assertTrue(np.array_equal(actual, expected))

    def test_gentle_curve_changes_intermediate_shape_without_escaping_socket(self) -> None:
        upper, lower, crease = self.masks(0.5)
        a, b, _ = blink.BASE_MASKS(self.shape, self.center, self.radius, 0.5)
        socket = np.maximum(*self.masks(1.0)[:2])
        self.assertTrue(np.any(upper != a) or np.any(lower != b))
        self.assertFalse(np.any(np.maximum(upper, lower)[socket == 0]))
        self.assertTrue(np.all(np.maximum(upper, lower) <= socket))
        self.assertFalse(np.any(crease))

    def test_combined_coverage_stays_monotone_and_has_no_full_close_threshold(self) -> None:
        previous = np.zeros(self.shape, dtype=np.uint8)
        for value in np.linspace(0, 1, 101):
            current = np.maximum(*self.masks(float(value))[:2])
            self.assertTrue(np.all(current >= previous), float(value))
            previous = current
        for first, second in ((0.0, 0.0001), (0.9989, 0.9991), (0.9999, 1.0)):
            a = np.maximum(*self.masks(first)[:2]).astype(np.int16)
            b = np.maximum(*self.masks(second)[:2]).astype(np.int16)
            self.assertLessEqual(int(np.abs(b - a).max()), 2)

    def test_global_mask_function_is_restored_on_exception(self) -> None:
        original = blink.continuous.lid_alpha_masks
        with self.assertRaisesRegex(RuntimeError, "injected"):
            with blink.shape_override(True):
                self.assertIs(blink.continuous.lid_alpha_masks, blink.curved_masks)
                raise RuntimeError("injected")
        self.assertIs(blink.continuous.lid_alpha_masks, original)


class BlinkRefinementPublishedProofTests(unittest.TestCase):
    def test_real_cadence_and_rendered_endpoints_are_verified(self) -> None:
        package = blink.REPO_ROOT / "collab/phase42_blink_refinement_v3"
        report = json.loads((package / "phase42-blink-refinement-report-v3.json").read_text(encoding="utf-8"))
        self.assertEqual(report["implementation_sha256"], blink.integration._sha256(Path(blink.__file__)))
        self.assertEqual(report["candidate_blink_count"], 1)
        self.assertEqual(report["candidate_control_span_ms"], 400)
        self.assertFalse(report["full_scene_rendered"])
        self.assertFalse(report["human_accepted"])
        self.assertEqual(report["candidate_render_hashes"]["1.0"]["full_frame_rgb_sha256"], "155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40")
        for name, entry in report["artifacts"].items():
            self.assertEqual(blink.integration._sha256(package / name), entry["sha256"])
        with Image.open(package / "phase42-blink-refined-real-cadence-v3.webp") as image:
            total = 0
            for index in range(image.n_frames):
                image.seek(index)
                image.load()
                if index == 0:
                    self.assertGreaterEqual(image.info["duration"], 5000)
                total += image.info["duration"]
            self.assertEqual(total, 7600)


if __name__ == "__main__":
    unittest.main()
