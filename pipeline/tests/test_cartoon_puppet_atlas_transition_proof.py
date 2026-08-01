from __future__ import annotations

import inspect
from pathlib import Path
import unittest

import numpy as np

from pipeline.cartoon_puppet_atlas_transition_proof import (
    PROOF_FRAMES,
    evaluate_atlas_transition,
    load_puppet_atlas_contract,
    render_atlas_frame,
    render_puppet_atlas_transition_proof,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "concept/characters/june_oxley_puppet_atlas_v1.json"


class CartoonPuppetAtlasTransitionProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = load_puppet_atlas_contract(CONTRACT)
        cls.report, cls.frames, cls.details = evaluate_atlas_transition(cls.inputs)

    def test_atlas_is_content_addressed_zero_cash_and_exactly_fourteen_components(self) -> None:
        self.assertEqual(self.inputs.contract["asset_id"], "june_oxley_puppet_atlas_v1")
        self.assertEqual(self.inputs.contract["cash_cost"], 0)
        self.assertFalse(self.inputs.contract["paid_runtime_dependency"])
        self.assertEqual(self.inputs.atlas_rgba.shape, (1024, 1536, 4))
        self.assertEqual(self.inputs.atlas_substantial_component_count, 14)
        self.assertEqual(len(self.inputs.components), 14)
        self.assertEqual(len(set(self.inputs.atlas_component_labels.values())), 14)

    def test_declared_boxes_map_one_to_one_to_nonempty_single_source_crops(self) -> None:
        expected_boxes = {
            "head": (195, 27, 196, 323),
            "torso": (635, 34, 278, 450),
            "left_upper_arm": (452, 58, 151, 329),
            "right_upper_arm": (946, 58, 160, 329),
            "left_forearm": (261, 372, 243, 134),
            "right_forearm": (1012, 370, 224, 137),
            "left_hand": (393, 532, 131, 152),
            "right_hand_mug": (986, 534, 228, 130),
            "left_thigh": (607, 518, 137, 185),
            "right_thigh": (791, 521, 127, 178),
            "left_shin": (590, 711, 119, 145),
            "right_shin": (804, 710, 119, 147),
            "left_boot": (498, 856, 196, 127),
            "right_boot": (811, 857, 200, 125),
        }
        self.assertEqual({component.identifier: component.bbox for component in self.inputs.components}, expected_boxes)
        self.assertTrue(all(np.count_nonzero(component.rgba[:, :, 3] > 8) >= 500 for component in self.inputs.components))
        self.assertEqual(
            [component.identifier for component in self.inputs.components],
            self.report["fixed_depth_order"],
        )

    def test_atlas_rig_uses_articulated_arms_legs_hands_mug_and_boots(self) -> None:
        identifiers = {component.identifier for component in self.inputs.components}
        self.assertTrue(
            {
                "left_upper_arm", "left_forearm", "left_hand",
                "right_upper_arm", "right_forearm", "right_hand_mug",
                "left_thigh", "left_shin", "left_boot",
                "right_thigh", "right_shin", "right_boot",
            }.issubset(identifiers)
        )
        self.assertEqual(
            self.report["source_policy"],
            "single immutable atlas crop per rig component; no corrective-pose pixels",
        )

    def test_seven_frame_render_is_transparent_deterministic_and_full_canvas(self) -> None:
        self.assertEqual(PROOF_FRAMES, tuple(range(88, 95)))
        self.assertEqual(set(self.frames), set(PROOF_FRAMES))
        for frame in PROOF_FRAMES:
            self.assertEqual(self.frames[frame].shape, (941, 1672, 4))
            self.assertEqual(self.frames[frame].dtype, np.uint8)
            self.assertGreater(np.count_nonzero(self.frames[frame][:, :, 3] > 8), 10000)
        repeated, _ = render_atlas_frame(self.inputs, 91)
        self.assertTrue(np.array_equal(repeated, self.frames[91]))
        with self.assertRaisesRegex(ValueError, "88 through 94"):
            render_atlas_frame(self.inputs, 87)

    def test_report_gates_real_sockets_determinants_seams_and_contacts(self) -> None:
        mechanics = self.report["mechanics"]
        self.assertLessEqual(mechanics["maximum_mapping_residual_to_extended_target_px"], 0.05)
        self.assertAlmostEqual(mechanics["maximum_authored_socket_offset_due_to_underlap_px"], 10.0, delta=0.001)
        self.assertGreaterEqual(mechanics["minimum_affine_determinant"], 0.2)
        self.assertLessEqual(mechanics["maximum_joint_gap_px"], 6.0)
        self.assertEqual(mechanics["default_joint_underlap_pixels"], 4)
        self.assertEqual(mechanics["per_component_underlap"]["left_upper_arm"]["proximal"], 10.0)
        self.assertEqual(mechanics["per_component_underlap"]["right_upper_arm"]["proximal"], 10.0)
        contacts = self.report["contact_coherence"]
        self.assertEqual(set(contacts), {"left_hand", "right_hand_mug", "left_boot", "right_boot"})
        self.assertTrue(all(value["maximum_significant_count"] == 1 for value in contacts.values()))
        self.assertTrue(all(value["minimum_dominant_fraction"] >= 0.95 for value in contacts.values()))

    def test_report_keeps_temporal_and_silhouette_quality_separate_from_readability(self) -> None:
        temporal = self.report["temporal_continuity"]
        self.assertEqual(len(temporal["per_frame_changed_pixel_and_mae"]), 6)
        self.assertGreater(temporal["minimum_adjacent_frame_alpha_iou"], 0.0)
        silhouette = self.report["frame94_silhouette"]
        self.assertGreater(silhouette["alpha_iou_to_pose75"], 0.0)
        self.assertGreater(silhouette["alpha_area_ratio_to_pose75"], 0.0)
        self.assertGreater(silhouette["substantial_connected_components"], 0)
        self.assertEqual(silhouette["human_readability_status"], "unevaluated")
        self.assertIn("bounded", self.report["promotion_scope"].lower())

    def test_cli_boundary_is_explicit_and_does_not_hide_ffmpeg(self) -> None:
        signature = inspect.signature(render_puppet_atlas_transition_proof)
        self.assertEqual(list(signature.parameters)[:2], ["contract_path", "output_dir"])
        self.assertEqual(signature.parameters["ffmpeg"].default, "ffmpeg")


if __name__ == "__main__":
    unittest.main()
