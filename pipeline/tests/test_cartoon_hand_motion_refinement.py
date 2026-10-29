from __future__ import annotations

import math
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_hand_motion_refinement as hand


class HandMotionGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = hand.body.prepare_rig()

    def test_coherent_phase_preserves_all_control_distances_and_contact(self) -> None:
        metrics = hand.geometry_measurements(self.prepared)
        self.assertGreater(metrics["old_max_pairwise_distance_change_px"], 3.0)
        self.assertLess(metrics["candidate_coherent_max_pairwise_distance_change_px"], 1e-5)
        self.assertEqual(metrics["candidate_coherent_max_contact_displacement_px"], 0.0)
        self.assertGreater(metrics["candidate_max_control_excursion_px"], 2.5)
        self.assertLess(metrics["candidate_max_adjacent_control_step_px"], 0.5)
        strain = metrics["peak_inverse_map_strain"]
        self.assertGreater(strain["old"]["maximum_local_length_change_percent"], 0.5)
        self.assertLess(strain["candidate"]["maximum_local_length_change_percent"], 0.0001)

    def test_exact_inverse_map_is_isometric_not_gaussian_averaged(self) -> None:
        region = self.prepared.regions["table_hand"]
        left, top, right, bottom = region.bbox
        yy, xx = np.mgrid[top:bottom, left:right]
        grid = np.stack((xx, yy), axis=-1).astype(np.float64)
        source = grid - hand.coherent_inverse_field(self.prepared, 115)
        # Neighbor lengths and orthogonality expose spatial stretching even
        # when sparse landmark offsets claim coherent geometry.
        x_edges = np.diff(source, axis=1)[:-1]
        y_edges = np.diff(source, axis=0)[:, :-1]
        self.assertLess(float(abs(np.linalg.norm(x_edges, axis=2) - 1).max()), 1e-6)
        self.assertLess(float(abs(np.linalg.norm(y_edges, axis=2) - 1).max()), 1e-6)
        self.assertLess(float(abs(np.sum(x_edges * y_edges, axis=2)).max()), 1e-6)
        forward = (source - np.array([731., 920.])) @ hand._rotation(hand.rock_degrees(115)).T + np.array([731., 920.])
        self.assertLess(float(abs(forward - grid).max()), 1e-6)

    def test_active_gesture_has_one_peak_and_a_longer_release_not_a_frozen_hand(self) -> None:
        values = [hand.rock_degrees(frame) for frame in range(90, 149)]
        self.assertTrue(all(b >= a for a, b in zip(values[:22], values[1:22])))
        self.assertTrue(all(b <= a for a, b in zip(values[26:], values[27:])))
        self.assertEqual([frame for frame in range(90, 149) if math.isclose(hand.rock_degrees(frame), hand.PEAK_DEGREES)], list(range(111, 117)))
        self.assertEqual(hand.rock_degrees(90), 0.0)
        self.assertEqual(hand.rock_degrees(148), 0.0)
        self.assertTrue(all(hand.entry_weight(frame) == 1.0 for frame in range(102, 148)))

    def test_late_control_geometry_keeps_contact_depth_restrained(self) -> None:
        region = self.prepared.regions["table_hand"]
        tips = [index for index, name in enumerate(region.names) if name.endswith("tip")]
        maximum = max(float(abs(hand.coherent_control_offsets(self.prepared, frame)[tips, 1]).max()) for frame in range(102, 148))
        self.assertLess(maximum, 1.7)

    def test_override_restores_both_functions_after_an_actual_render_failure(self) -> None:
        original_hand = hand.body._hand_offsets
        original_compose = hand.body._compose_displacement
        with patch.object(hand.body, "_compose_displacement", side_effect=RuntimeError("injected render failure")) as failing:
            with self.assertRaisesRegex(RuntimeError, "injected render failure"):
                with hand.hand_override(self.prepared, 115):
                    hand.body.render_frame(self.prepared, 115)
            self.assertIs(hand.body._hand_offsets, original_hand)
            self.assertIs(hand.body._compose_displacement, failing)
        self.assertIs(hand.body._compose_displacement, original_compose)

    def test_override_restores_nested_caller_and_does_not_adapt_another_state(self) -> None:
        original_hand, original_compose = hand.body._hand_offsets, hand.body._compose_displacement
        expected = original_hand(self.prepared, self.prepared.states[71])
        with hand.hand_override(self.prepared, 115):
            outer_hand, outer_compose = hand.body._hand_offsets, hand.body._compose_displacement
            self.assertTrue(np.array_equal(hand.body._hand_offsets(self.prepared, self.prepared.states[71]), expected))
            with hand.hand_override(self.prepared, 126):
                self.assertIsNot(hand.body._hand_offsets, outer_hand)
            self.assertIs(hand.body._hand_offsets, outer_hand)
            self.assertIs(hand.body._compose_displacement, outer_compose)
        self.assertIs(hand.body._hand_offsets, original_hand)
        self.assertIs(hand.body._compose_displacement, original_compose)

    def test_early_and_endpoint_frames_bypass_without_patch_or_pixel_changes(self) -> None:
        original_hand, original_compose = hand.body._hand_offsets, hand.body._compose_displacement
        for frame in (1, 72, 90, 148, 162, 173, 228):
            with hand.hand_override(self.prepared, frame):
                self.assertIs(hand.body._hand_offsets, original_hand)
                self.assertIs(hand.body._compose_displacement, original_compose)
        for frame in (90, 148):
            before = hand.body.render_frame(self.prepared, frame).image
            with hand.hand_override(self.prepared, frame):
                after = hand.body.render_frame(self.prepared, frame).image
            self.assertTrue(np.array_equal(before, after))

    def test_native_candidate_changes_only_declared_hand_wrist_support(self) -> None:
        support = hand.native_hand_support(self.prepared)
        for frame in (91, 98, 104, 115, 130, 147):
            before = hand.body.render_frame(self.prepared, frame).image
            with hand.hand_override(self.prepared, frame):
                after = hand.body.render_frame(self.prepared, frame).image
            changed = np.any(before != after, axis=2)
            if frame < 147:
                self.assertTrue(changed.any(), frame)
            self.assertEqual(int((changed & ~support).sum()), 0, frame)
            for name, mask in self.prepared.protected.items():
                self.assertEqual(int((changed & mask).sum()), 0, (frame, name))


class HandMotionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from pipeline import cartoon_scene_review as scene
        cls.scene = scene
        cls.prepared = scene.integration.prepare_repaired_acting()

    def test_existing_synchronized_camera_stack_preserves_nonhand_head_face_and_mug(self) -> None:
        scene, prepared = self.scene, self.prepared
        rig = prepared.integration.body
        with scene.accepted_lids(prepared):
            for frame in (91, 104, 115, 130, 147, 148):
                before = scene.acting.compose_integrated_frame(prepared.integration, frame)
                with hand.hand_override(rig, frame):
                    after = scene.acting.compose_integrated_frame(prepared.integration, frame)
                support = hand.delivery_hand_support(prepared.integration, frame)
                changed = np.any(before.candidate != after.candidate, axis=2)
                self.assertEqual(int((changed & ~support).sum()), 0, frame)
                for mask in (before.transformed_head_support, before.transformed_face_support, before.transformed_mug_support):
                    self.assertEqual(int((changed & mask).sum()), 0, frame)
                if frame < 147:
                    self.assertTrue(changed.any(), frame)
                if frame == 148:
                    self.assertFalse(changed.any(), frame)
                self.assertEqual(scene.acting.phase35.production_blink_closure(prepared.integration.direct.contract, frame), 0.0)

    def test_accepted_late_eye_is_byte_exact_and_original_context_restores(self) -> None:
        scene, prepared = self.scene, self.prepared
        with scene.accepted_lids(prepared), hand.hand_override(prepared.integration.body, 173):
            pixels, _ = scene.compose_direct_frame(prepared, 173)
        self.assertEqual(scene.acting._rgb_hash(pixels), "155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40")


if __name__ == "__main__":
    unittest.main()
