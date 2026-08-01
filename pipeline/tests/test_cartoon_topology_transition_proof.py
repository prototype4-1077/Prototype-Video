from __future__ import annotations

import inspect
from pathlib import Path
import unittest

import numpy as np

from pipeline.cartoon_topology_transition_proof import (
    CAGE_CONTACT_PARTS,
    CAGE_PART_IDS,
    CONTACT_PARTS,
    PART_IDS,
    PROOF_FRAMES,
    STAGGERED_SWITCH_FRAME,
    evaluate_transition,
    load_transition_inputs,
    reconstruct_parts,
    render_transition_frame,
    render_transition_proof,
    semantic_part_affines,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "concept/characters/june_oxley_deformable_performance_3q_v1.json"


class CartoonTopologyTransitionProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = load_transition_inputs(CONTRACT)
        cls.report, cls.frames = evaluate_transition(cls.inputs)
        cls.canonical_report, cls.canonical_frames = evaluate_transition(
            cls.inputs,
            mode="canonical_single_texture_cage",
        )

    def test_proof_is_bounded_to_the_requested_pose50_to_pose75_interval(self) -> None:
        self.assertEqual(PROOF_FRAMES, tuple(range(88, 95)))
        self.assertEqual(self.inputs.start.pose_id, "POSE_50_WEIGHT_TRANSFER")
        self.assertEqual(self.inputs.end.pose_id, "POSE_75_RELEASE")
        self.assertEqual(self.report["frame_range"], [88, 94])
        self.assertFalse(self.report["background_pixels_loaded_or_blended"])
        self.assertEqual(self.report["cash_cost"], 0)
        self.assertFalse(self.report["paid_runtime_dependency"])

    def test_partition_is_complete_disjoint_and_pixel_exact_for_both_sources(self) -> None:
        self.assertEqual(set(PART_IDS), set(self.inputs.start.parts))
        self.assertEqual(set(PART_IDS), set(self.inputs.end.parts))
        for pose in (self.inputs.start, self.inputs.end):
            reconstructed = reconstruct_parts(pose.parts)
            self.assertTrue(np.array_equal(reconstructed, pose.rgba))
            ownership = np.zeros(pose.rgba.shape[:2], dtype=np.uint8)
            for part in pose.parts.values():
                present = part[:, :, 3] > 0
                self.assertFalse(np.any(ownership[present]))
                ownership[present] = 1
            self.assertTrue(np.array_equal(ownership > 0, pose.rgba[:, :, 3] > 0))

    def test_partition_names_explicit_contact_parts_and_residual(self) -> None:
        self.assertTrue(
            {
                "head_neck",
                "torso_pelvis",
                "left_arm",
                "left_hand",
                "right_arm",
                "right_hand",
                "left_leg",
                "left_boot",
                "right_leg",
                "right_boot",
                "mug",
                "residual",
            }.issubset(PART_IDS)
        )
        for pose in (self.inputs.start, self.inputs.end):
            self.assertTrue(all(np.count_nonzero(pose.parts[part_id][:, :, 3]) > 0 for part_id in PART_IDS))

    def test_every_semantic_affine_preserves_orientation(self) -> None:
        target = {
            identifier: (self.inputs.start.landmarks[identifier] + self.inputs.end.landmarks[identifier]) / 2.0
            for identifier in self.inputs.landmark_order
        }
        for source in (self.inputs.start, self.inputs.end):
            affines = semantic_part_affines(source.landmarks, target)
            self.assertEqual(set(affines), set(PART_IDS))
            for matrix, determinant in affines.values():
                self.assertEqual(matrix.shape, (2, 3))
                self.assertGreater(determinant, 0.0)

    def test_rendered_endpoints_are_the_registered_source_pixels_not_approximations(self) -> None:
        first, _ = render_transition_frame(self.inputs, 88)
        last, _ = render_transition_frame(self.inputs, 94)
        self.assertTrue(np.array_equal(first, self.inputs.start.rgba))
        self.assertTrue(np.array_equal(last, self.inputs.end.rgba))
        for endpoint in self.report["endpoint_reconstruction"].values():
            self.assertEqual(endpoint["mismatched_pixels"], 0)
            self.assertEqual(endpoint["maximum_channel_error"], 0)
        with self.assertRaisesRegex(ValueError, "88 through 94"):
            render_transition_frame(self.inputs, 87)

    def test_rendered_pixel_report_has_per_part_contact_and_continuity_evidence(self) -> None:
        self.assertEqual(self.report["mode"], "staggered_corrective_activation")
        self.assertEqual(
            set(self.report["per_part_minimum_source_alignment_alpha_iou"]),
            set(PART_IDS),
        )
        self.assertEqual(set(self.report["contact_component_integrity"]), set(CONTACT_PARTS))
        self.assertGreater(self.report["minimum_affine_determinant"], 0.0)
        continuity = self.report["continuity"]
        self.assertGreater(continuity["minimum_adjacent_frame_alpha_iou"], 0.0)
        self.assertGreaterEqual(continuity["maximum_junction_gap_px"], 0.0)
        self.assertGreaterEqual(continuity["maximum_micro_hole_fraction"], 0.0)
        self.assertGreaterEqual(continuity["maximum_contact_centroid_step_px"], 0.0)
        for frame in PROOF_FRAMES:
            self.assertEqual(self.frames[frame].shape, (941, 1672, 4))
            self.assertEqual(self.frames[frame].dtype, np.uint8)

    def test_staggered_correctives_use_one_source_and_keep_contact_groups_together(self) -> None:
        purity = self.report["source_purity"]
        self.assertTrue(purity["every_part_uses_exactly_one_source_per_frame"])
        self.assertEqual(purity["mixed_source_part_count"], 0)
        self.assertEqual(STAGGERED_SWITCH_FRAME["right_hand"], STAGGERED_SWITCH_FRAME["mug"])
        self.assertEqual(STAGGERED_SWITCH_FRAME["right_arm"], STAGGERED_SWITCH_FRAME["right_hand"])
        self.assertEqual(STAGGERED_SWITCH_FRAME["left_leg"], STAGGERED_SWITCH_FRAME["left_boot"])
        self.assertEqual(STAGGERED_SWITCH_FRAME["right_leg"], STAGGERED_SWITCH_FRAME["right_boot"])
        self.assertGreater(
            STAGGERED_SWITCH_FRAME["head_neck"],
            max(STAGGERED_SWITCH_FRAME[part_id] for part_id in PART_IDS if part_id != "head_neck"),
        )
        rows = self.report["continuity"]["per_frame_changed_pixel_and_mae"]
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["switched_parts"], ["left_leg", "left_boot"])
        self.assertTrue(all(row["changed_pixels"] > 0 for row in rows))
        self.assertTrue(all(row["mean_absolute_error_subject_union"] > 0.0 for row in rows))

    def test_canonical_cage_is_a_lossless_refined_partition_of_pose50(self) -> None:
        self.assertEqual(set(self.inputs.cage_start_parts), set(CAGE_PART_IDS))
        self.assertTrue(np.array_equal(reconstruct_parts(self.inputs.cage_start_parts), self.inputs.start.rgba))
        self.assertTrue(
            {
                "left_thigh",
                "left_shin",
                "left_boot",
                "right_thigh",
                "right_shin",
                "right_boot",
                "left_upper_arm",
                "left_forearm_hand",
                "right_upper_arm",
                "right_forearm_hand",
            }.issubset(CAGE_PART_IDS)
        )

    def test_canonical_cage_uses_no_pose75_pixels_and_hits_target_sockets(self) -> None:
        report = self.canonical_report
        self.assertEqual(report["mode"], "canonical_single_texture_cage")
        self.assertEqual(report["canonical_texture_source_pose"], "POSE_50_WEIGHT_TRANSFER")
        self.assertEqual(report["target_landmark_pose"], "POSE_75_RELEASE")
        self.assertEqual(report["end_source_pixel_contribution"], 0)
        self.assertFalse(report["frame94_is_required_to_match_pose75_pixels"])
        self.assertEqual(report["start_reconstruction"]["mismatched_pixels"], 0)
        self.assertLessEqual(report["landmark_socket_integrity"]["maximum_error_px"], 0.05)
        self.assertFalse(np.array_equal(self.canonical_frames[94], self.inputs.end.rgba))

    def test_canonical_cage_underlaps_preserve_contacts_and_positive_geometry(self) -> None:
        report = self.canonical_report
        self.assertEqual(report["underlap_pixels"], 4)
        self.assertEqual(set(report["contact_component_integrity"]), set(CAGE_CONTACT_PARTS))
        self.assertTrue(
            all(value["maximum_significant_count"] == 1 for value in report["contact_component_integrity"].values())
        )
        self.assertGreater(report["minimum_affine_determinant"], 0.0)
        self.assertGreaterEqual(report["seam_integrity"]["minimum_adjacent_joint_overlap_fraction"], 0.0)
        self.assertGreater(report["visual_silhouette"]["frame94_alpha_iou_to_pose75"], 0.0)
        rows = report["temporal_continuity"]["per_frame_changed_pixel_and_mae"]
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["changed_pixels"] > 0 for row in rows))

    def test_machine_gate_is_derived_from_declared_rendered_pixel_thresholds(self) -> None:
        thresholds = self.report["thresholds"]
        contact_iou = min(
            self.report["per_part_minimum_source_alignment_alpha_iou"][part_id]
            for part_id in CONTACT_PARTS
        )
        components = self.report["contact_component_integrity"]
        expected = (
            all(value["mismatched_pixels"] == thresholds["endpoint_mismatched_pixels"] for value in self.report["endpoint_reconstruction"].values())
            and contact_iou >= thresholds["minimum_contact_part_alignment_iou"]
            and max(value["maximum_significant_count"] for value in components.values()) <= thresholds["maximum_contact_significant_components"]
            and min(value["minimum_dominant_fraction"] for value in components.values()) >= thresholds["minimum_contact_dominant_component_fraction"]
            and self.report["minimum_affine_determinant"] >= thresholds["minimum_affine_determinant"]
            and self.report["continuity"]["maximum_junction_gap_px"] <= thresholds["maximum_junction_gap_px"]
            and self.report["continuity"]["maximum_micro_hole_fraction"] <= thresholds["maximum_micro_hole_fraction"]
            and self.report["continuity"]["minimum_adjacent_frame_alpha_iou"] >= thresholds["minimum_adjacent_frame_alpha_iou"]
            and self.report["continuity"]["maximum_contact_centroid_step_px"] <= thresholds["maximum_contact_centroid_step_px"]
            and self.report["source_purity"]["mixed_source_part_count"] <= thresholds["maximum_mixed_source_parts"]
        )
        self.assertEqual(self.report["machine_passed"], expected)
        self.assertIn("bounded", self.report["promotion_scope"])
        self.assertNotIn("audience_quality", self.report)

    def test_cli_entrypoint_keeps_contract_output_and_ffmpeg_explicit(self) -> None:
        signature = inspect.signature(render_transition_proof)
        self.assertEqual(list(signature.parameters)[:2], ["contract_path", "output_dir"])
        self.assertEqual(signature.parameters["ffmpeg"].default, "ffmpeg")
        self.assertEqual(signature.parameters["mode"].default, "staggered_corrective_activation")


if __name__ == "__main__":
    unittest.main()
