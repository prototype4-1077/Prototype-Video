from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
import unittest

import numpy as np
from PIL import Image

from pipeline import cartoon_continuous_blink as blink
from pipeline import cartoon_eyelid_source_successor as successor


class ContinuousBlinkTests(unittest.TestCase):
    shape = (120, 180)
    center = (50, 50)
    radius = (20, 16)

    def masks(self, closure: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return blink.lid_alpha_masks(self.shape, self.center, self.radius, closure)

    def test_subpixel_changes_cannot_switch_on_a_whole_socket_ring(self) -> None:
        for first, second in ((0.0, 0.0001), (0.2499, 0.2501), (0.9989, 0.9991), (0.9999, 1.0)):
            a = np.maximum(*self.masks(first)[:2]).astype(np.int16)
            b = np.maximum(*self.masks(second)[:2]).astype(np.int16)
            self.assertLessEqual(int(np.max(np.abs(b - a))), 2, (first, second))

    def test_coverage_is_monotone_across_101_closures(self) -> None:
        prior = np.zeros(self.shape, dtype=np.uint8)
        for closure in np.linspace(0.0, 1.0, 101):
            upper, lower, crease = self.masks(float(closure))
            current = np.maximum(upper, lower)
            self.assertTrue(np.all(current >= prior), float(closure))
            self.assertFalse(np.any(crease))
            prior = current

    def test_open_is_exact_and_closed_iris_has_no_uncovered_pixels(self) -> None:
        self.assertFalse(any(np.any(mask) for mask in self.masks(0.0)))
        upper, lower, _ = self.masks(1.0)
        yy, xx = np.indices(self.shape)
        iris = ((xx - self.center[0]) / 11.5) ** 2 + ((yy - self.center[1]) / 14.0) ** 2 <= 1.0
        self.assertTrue(np.all(np.maximum(upper, lower)[iris] == 255))

    def test_source_compositor_changes_only_declared_support_and_restores_globals(self) -> None:
        geometry = {
            "viewer_left_eye": {"center": list(self.center), "radius": list(self.radius)},
            "viewer_right_eye": {"center": [120, 60], "radius": [20, 17]},
        }
        plate = np.full((*self.shape, 3), 30, dtype=np.uint8)
        texture = np.full_like(plate, 180)
        prepared = SimpleNamespace(face=SimpleNamespace(
            plate=plate, contract={"semantic_geometry_native_xy": geometry},
        ))
        phase34 = successor.v4.v3.phase35.phase34_candidate09
        phase33 = phase34.phase33
        original_compose, original_masks = phase33._compose_eye_lids, phase34._semantic_lid_alpha_masks
        for closure in (0.0, 0.25, 0.75, 0.9989, 1.0):
            canvas = plate.copy()
            owner = np.zeros(self.shape, dtype=np.uint8)
            with successor._natural_blink_variant(prepared, continuous=True):
                ratio, area = phase33._compose_eye_lids(
                    canvas, plate, texture, owner, self.center, self.radius, closure,
                )
            upper, lower, _ = self.masks(closure)
            alpha = np.maximum(upper, lower)
            self.assertFalse(np.any(np.any(canvas != plate, axis=2) & (alpha == 0)))
            expected = np.floor(30.0 * (1.0 - alpha / 255.0) + 180.0 * (alpha / 255.0)).astype(np.uint8)
            self.assertTrue(np.all(np.abs(canvas[:, :, 0].astype(int) - expected.astype(int)) <= 1))
            self.assertEqual(area, int((alpha >= 128).sum()))
            if closure == 1.0:
                self.assertEqual(ratio, 1.0)
            self.assertIs(phase33._compose_eye_lids, original_compose)
            self.assertIs(phase34._semantic_lid_alpha_masks, original_masks)
        with successor._natural_blink_variant(prepared, continuous=True):
            with self.assertRaises(ValueError):
                phase33._compose_eye_lids(
                    plate.copy(), plate, texture, np.zeros(self.shape, dtype=np.uint8),
                    self.center, self.radius, -0.01,
                )
        with self.assertRaisesRegex(RuntimeError, "injected"):
            with successor._natural_blink_variant(prepared, continuous=True):
                raise RuntimeError("injected")
        self.assertIs(phase33._compose_eye_lids, original_compose)
        self.assertIs(phase34._semantic_lid_alpha_masks, original_masks)

    def test_invalid_inputs_fail_instead_of_clamping(self) -> None:
        for closure in (-0.01, 1.01, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.masks(closure)
        with self.assertRaises(ValueError):
            blink.lid_alpha_masks(self.shape, (1, 1), self.radius, 0.5)


class ContinuousBlinkPublishedProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.package = successor.REPO_ROOT / "collab/phase42_continuous_blink_review_v2"
        cls.report = json.loads(
            (cls.package / "phase42-eyelid-source-successor-report-v2.json").read_text(encoding="utf-8")
        )

    def test_proof_is_bound_to_actual_renderer_and_preserved_full_close(self) -> None:
        files = {"source_successor": successor.__file__, "continuous_blink": blink.__file__}
        for name, filename in files.items():
            with open(filename, "rb") as source:
                self.assertEqual(hashlib.sha256(source.read()).hexdigest(), self.report["implementation_sha256"][name])
        predecessor = json.loads((
            successor.REPO_ROOT / "collab/phase42_human_rejected_gates_successors_v1/phase42-eyelid-source-successor-report-v1.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(
            self.report["variants"]["ai_direct"]["phase36_rgb_sha256"],
            predecessor["variants"]["ai_direct"]["phase36_rgb_sha256"],
        )
        self.assertFalse(self.report["human_accepted"])
        self.assertFalse(self.report["encode_authorized"])

    def test_every_published_artifact_has_the_reported_content(self) -> None:
        for name, entry in self.report["artifacts"].items():
            data = (self.package / name).read_bytes()
            self.assertEqual(len(data), entry["bytes"], name)
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"], name)

    def test_control_failure_is_measured_and_removed_on_both_eyes(self) -> None:
        audit = self.report["control_continuity_audit"]
        before = [row for row in audit["phase42_v1"] if row["closure_pair"] == [0.9989, 0.9991]]
        self.assertEqual(len(before), 2)
        self.assertTrue(all(row["maximum_alpha_jump_u8"] == 255.0 for row in before))
        self.assertTrue(all(row["maximum_alpha_jump_u8"] <= 2.0 for row in audit["continuous_v2"]))
        for row in self.report["ai_direct_neighbor_sequence"]["frames"]:
            self.assertEqual(row["native_changes_outside_feature_support"], 0)
            self.assertEqual(row["depth_order_violation_pixels"], 0)
            if row["blink_closure"] == 1.0:
                self.assertEqual(row["iris_occlusion_ratios"], [1.0, 1.0])

    def test_normal_and_slow_loops_decode_to_identical_frames_but_distinct_timing(self) -> None:
        normal = self.package / "phase42-eyelid-ai-direct-30fps-v2.webp"
        slow = self.package / "phase42-eyelid-ai-direct-f240-f256-loop-v2.webp"
        with Image.open(normal) as a, Image.open(slow) as b:
            self.assertEqual(a.n_frames, 17)
            self.assertEqual(a.n_frames, b.n_frames)
            self.assertEqual(a.size, (371, 220))
            normal_duration = slow_duration = 0
            for index in range(a.n_frames):
                a.seek(index)
                b.seek(index)
                self.assertTrue(np.array_equal(np.asarray(a.convert("RGB")), np.asarray(b.convert("RGB"))))
                normal_duration += a.info["duration"]
                slow_duration += b.info["duration"]
            self.assertEqual(normal_duration, 567)
            self.assertEqual(slow_duration, 1285)


if __name__ == "__main__":
    unittest.main()
