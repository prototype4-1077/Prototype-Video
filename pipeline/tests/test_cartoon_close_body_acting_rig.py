from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

import numpy as np

from pipeline import cartoon_close_body_acting_rig as rig


class CloseBodyActingRigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = rig.prepare_rig()

    def test_contract_is_zero_cash_silent_and_fail_closed(self) -> None:
        contract = self.prepared.contract
        self.assertEqual(contract["cash_cost"], 0)
        self.assertEqual(contract["paid_service_calls_allowed"], 0)
        self.assertEqual(contract["network_calls_allowed"], 0)
        self.assertFalse(contract["video_encode_allowed"])
        self.assertFalse(contract["picture_master_mutation_allowed"])
        self.assertFalse(contract["promotion_allowed"])
        self.assertTrue(contract["human_acting_acceptance_required"])
        self.assertEqual(contract["clock"]["frame_count"], 162)

    def test_phase38_gap_and_source_plate_are_exactly_bound(self) -> None:
        report_path = rig._repo_path(self.prepared.contract["locks"]["phase38_machine_report"]["path"])
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "MACHINE_DIAGNOSTIC_PASSED_ACTING_RIG_GAP_CONFIRMED_PLAN_ONLY")
        self.assertTrue(report["machine_passed"])
        self.assertFalse(report["picture_rebuild_authorized"])
        self.assertEqual(rig._sha256(report_path), self.prepared.contract["locks"]["phase38_machine_report"]["sha256"])
        self.assertEqual(rig._rgb_hash(self.prepared.plate), rig._rgb_hash(np.asarray(self.prepared.plate)))

    def test_region_masks_are_soft_bounded_and_protected_regions_are_zero(self) -> None:
        protected = np.logical_or.reduce(list(self.prepared.protected.values()))
        for name, region in self.prepared.regions.items():
            self.assertGreater(float(np.max(region.alpha)), 0.99, name)
            self.assertGreater(int(np.count_nonzero((region.alpha > 0.0) & (region.alpha < 1.0))), 0, name)
            left, top, right, bottom = region.bbox
            local_protected = protected[top:bottom, left:right]
            self.assertEqual(int(np.count_nonzero(region.alpha[local_protected])), 0, name)

    def test_motion_has_four_authored_beats_two_overshoots_and_real_hold(self) -> None:
        self.assertEqual(len(self.prepared.contract["authored_beats"]), 4)
        states = self.prepared.states
        self.assertGreater(states[71]["finger_spread"], states[65]["finger_spread"])
        self.assertGreater(states[71]["finger_spread"], states[81]["finger_spread"])
        self.assertGreater(states[114]["finger_compress"], states[109]["finger_compress"])
        self.assertGreater(states[114]["finger_compress"], states[125]["finger_compress"])
        for state in states[148:162]:
            self.assertTrue(all(abs(value) <= 1e-12 for value in state.values()))

    def test_zero_state_is_byte_identical_and_has_no_support(self) -> None:
        frame = rig.render_frame(self.prepared, 1)
        self.assertTrue(np.array_equal(frame.image, self.prepared.plate))
        self.assertEqual(frame.metrics["changed_pixel_count"], 0)
        self.assertEqual(frame.metrics["prospective_support_area"], 0)
        self.assertEqual(frame.metrics["maximum_displacement_px"], 0.0)

    def test_action_frames_preserve_face_mug_and_prospective_support(self) -> None:
        for number in (24, 66, 72, 110, 115, 148):
            frame = rig.render_frame(self.prepared, number)
            self.assertEqual(frame.metrics["protected_changed_pixels"]["face_head"], 0, number)
            self.assertEqual(frame.metrics["protected_changed_pixels"]["mug"], 0, number)
            self.assertEqual(frame.metrics["changed_pixels_outside_prospective_support"], 0, number)
            self.assertLessEqual(
                frame.metrics["maximum_displacement_px"],
                self.prepared.contract["quality_gates"]["maximum_source_displacement_px"],
                number,
            )

    def test_hand_opening_and_compression_are_geometrically_distinct(self) -> None:
        baseline = rig.render_frame(self.prepared, 1)
        opening = rig.render_frame(self.prepared, 72)
        compression = rig.render_frame(self.prepared, 115)
        baseline_span = rig._finger_span(baseline.landmarks)
        opening_span = rig._finger_span(opening.landmarks)
        compression_span = rig._finger_span(compression.landmarks)
        self.assertGreaterEqual(
            opening_span - baseline_span,
            self.prepared.contract["quality_gates"]["minimum_opening_finger_span_gain_px"],
        )
        self.assertGreaterEqual(
            opening_span - compression_span,
            self.prepared.contract["quality_gates"]["minimum_compression_span_recovery_px"],
        )

    def test_implementation_has_one_remap_and_no_process_network_or_encoder_route(self) -> None:
        source_path = rig._repo_path(rig.IMPLEMENTATION_RELATIVE_PATH)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue({"subprocess", "socket", "requests", "urllib", "moviepy"}.isdisjoint(imports))
        self.assertNotIn("ffmpeg", source.lower())
        self.assertNotIn("popen", source.lower())
        remap_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "cv2"
            and node.func.attr == "remap"
        ]
        self.assertEqual(len(remap_calls), 1)

    def test_output_allowlist_is_png_plus_lf_json_only(self) -> None:
        allowlist = self.prepared.contract["evidence"]["allowlist"]
        self.assertEqual(len(allowlist), 5)
        self.assertEqual(sum(name.endswith(".json") for name in allowlist), 1)
        self.assertEqual(sum(name.endswith(".png") for name in allowlist), 4)
        self.assertEqual(len(set(allowlist)), len(allowlist))


if __name__ == "__main__":
    unittest.main()
