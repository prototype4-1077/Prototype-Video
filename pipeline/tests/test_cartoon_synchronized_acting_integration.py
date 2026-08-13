from __future__ import annotations

import ast
import unittest

import numpy as np

from pipeline import cartoon_synchronized_acting_integration as integration


class SynchronizedActingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = integration.prepare_integration()

    def test_contract_is_zero_cash_unencoded_and_fail_closed(self) -> None:
        contract = self.prepared.contract
        self.assertEqual(contract["cash_cost"], 0)
        self.assertEqual(contract["paid_service_calls_allowed"], 0)
        self.assertEqual(contract["network_calls_allowed"], 0)
        self.assertFalse(contract["video_encode_allowed"])
        self.assertFalse(contract["picture_master_mutation_allowed"])
        self.assertFalse(contract["promotion_allowed"])
        self.assertTrue(contract["human_acting_acceptance_required"])
        self.assertEqual(contract["clock"]["frame_count"], 228)

    def test_stage_order_places_body_before_features_head_atmosphere_and_camera(self) -> None:
        order = self.prepared.contract["integration"]["stage_order"]
        body = order.index("phase39_body_inverse_remap")
        features = order.index("accepted_source_textured_face_features")
        head = order.index("existing_head_warp")
        atmosphere = order.index("existing_lantern_and_atmosphere")
        camera = order.index("existing_camera_push")
        self.assertLess(body, features)
        self.assertLess(features, head)
        self.assertLess(head, atmosphere)
        self.assertLess(atmosphere, camera)
        self.assertTrue(self.prepared.contract["integration"]["phase39_replaces_existing_rectangular_shoulders_warp"])

    def test_phase39_phase35_share_exact_plate_and_clocks(self) -> None:
        self.assertTrue(np.array_equal(self.prepared.body.plate, self.prepared.direct.face.plate))
        self.assertEqual(len(self.prepared.direct.visemes), 228)
        self.assertEqual(len(self.prepared.direct.expressions), 228)
        self.assertEqual(len(self.prepared.direct.motion), 228)
        self.assertEqual(len(self.prepared.body.states), 162)

    def test_zero_additive_frames_return_exact_baseline(self) -> None:
        for number in (1, 17, 44, 148, 149, 162, 163, 180, 228):
            frame = integration.compose_integrated_frame(self.prepared, number)
            self.assertTrue(np.array_equal(frame.candidate, frame.baseline), number)
            self.assertEqual(frame.metrics["changed_pixel_count"], 0, number)
            self.assertFalse(frame.metrics["state_nonzero"], number)

    def test_action_frames_preserve_transformed_face_mug_and_support(self) -> None:
        for number in (24, 66, 72, 110, 115, 126):
            frame = integration.compose_integrated_frame(self.prepared, number)
            self.assertTrue(frame.metrics["state_nonzero"], number)
            self.assertGreater(frame.metrics["changed_pixel_count"], 0, number)
            self.assertEqual(frame.metrics["changed_pixels_outside_transformed_phase39_support"], 0, number)
            self.assertEqual(frame.metrics["changed_pixels_in_transformed_head_support"], 0, number)
            self.assertEqual(frame.metrics["changed_pixels_in_transformed_face_feature_support"], 0, number)
            self.assertEqual(frame.metrics["changed_pixels_in_transformed_mug_support"], 0, number)

    def test_candidate_keeps_existing_face_delivery_bytes_at_transformed_feature_support(self) -> None:
        frame = integration.compose_integrated_frame(self.prepared, 115)
        self.assertTrue(
            np.array_equal(
                frame.candidate[frame.transformed_face_support],
                frame.baseline[frame.transformed_face_support],
            )
        )

    def test_implementation_has_no_process_network_encoder_or_video_route(self) -> None:
        source_path = integration._repo_path(integration.IMPLEMENTATION_RELATIVE_PATH)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue({"subprocess", "socket", "requests", "urllib", "moviepy"}.isdisjoint(imports))
        lowered = source.lower()
        self.assertNotIn("ffmpeg", lowered)
        self.assertNotIn("video_writer", lowered)
        self.assertNotIn("popen", lowered)

    def test_output_allowlist_is_five_pngs_plus_lf_json(self) -> None:
        allowlist = self.prepared.contract["evidence"]["allowlist"]
        self.assertEqual(len(allowlist), 6)
        self.assertEqual(sum(name.endswith(".png") for name in allowlist), 5)
        self.assertEqual(sum(name.endswith(".json") for name in allowlist), 1)
        self.assertEqual(len(set(allowlist)), len(allowlist))


if __name__ == "__main__":
    unittest.main()
