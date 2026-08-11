from __future__ import annotations

import ast
import inspect
from pathlib import Path
import unittest

import numpy as np

from pipeline import cartoon_eyelid_alignment_diagnostic as diagnostic
from pipeline import cartoon_source_textured_direct_address as phase35


class EyelidAlignmentDiagnosticTests(unittest.TestCase):
    def test_contract_is_still_only_and_binds_controlling_verdict(self) -> None:
        contract = diagnostic.load_contract()
        self.assertEqual(contract["cash_cost"], 0)
        self.assertFalse(contract["diagnostic"]["video_encode_allowed"])
        self.assertFalse(contract["diagnostic"]["accepted_source_mutation_allowed"])
        self.assertEqual(
            contract["locks"]["controlling_james_verdict"]["sha256"],
            "9f3974ddcfc4715ea40501bcc46f60594da7021b342047eeed6d44992c729bb3",
        )
        self.assertEqual(
            contract["immutable_picture"]["frame_inventory_canonical_sha256"],
            "d09bcdc6a3c86e26e9ce77070f18504f3101e4b87edfc54e169e3b4b641a6451",
        )

    def test_full_closure_variant_suppresses_only_fixed_crease_blend(self) -> None:
        phase33 = phase35.phase34_candidate09.phase33
        shape = (120, 160, 3)
        yy, xx = np.indices(shape[:2])
        plate = np.stack(
            (
                150 + (xx % 40),
                90 + (yy % 50),
                55 + ((xx + yy) % 35),
            ),
            axis=2,
        ).astype(np.uint8)
        lid_texture = np.roll(plate, 7, axis=0)
        center = (80, 60)
        radius = (31, 24)
        baseline = plate.copy()
        baseline_owner = np.zeros(shape[:2], dtype=np.uint8)
        baseline_ratio, baseline_area = phase33._compose_eye_lids(
            baseline, plate, lid_texture, baseline_owner, center, radius, 1.0,
        )
        proposal = plate.copy()
        proposal_owner = np.zeros(shape[:2], dtype=np.uint8)
        with diagnostic._full_closure_crease_suppressed() as suppressions:
            proposal_ratio, proposal_area = phase33._compose_eye_lids(
                proposal, plate, lid_texture, proposal_owner, center, radius, 1.0,
            )
        changed = np.any(baseline != proposal, axis=2)
        _, _, crease_alpha = phase35.phase34_candidate09._semantic_lid_alpha_masks(
            shape[:2], center, radius, 1.0,
        )
        self.assertEqual(baseline_ratio, proposal_ratio)
        self.assertEqual(baseline_area, proposal_area)
        self.assertTrue(np.array_equal(baseline_owner, proposal_owner))
        self.assertEqual(int(changed.sum()), int((crease_alpha > 0).sum()))
        self.assertEqual(len(suppressions), 1)
        self.assertEqual(suppressions[0]["nonzero_alpha_pixels"], int((crease_alpha > 0).sum()))

    def test_partial_closure_is_byte_identical(self) -> None:
        phase33 = phase35.phase34_candidate09.phase33
        plate = np.full((120, 160, 3), [180, 115, 72], dtype=np.uint8)
        lid_texture = plate.copy()
        lid_texture[:, :, 0] = np.arange(160, dtype=np.uint8)[None, :]
        baseline = plate.copy()
        proposal = plate.copy()
        baseline_owner = np.zeros(plate.shape[:2], dtype=np.uint8)
        proposal_owner = np.zeros(plate.shape[:2], dtype=np.uint8)
        expected = phase33._compose_eye_lids(
            baseline, plate, lid_texture, baseline_owner, (80, 60), (31, 24), 0.75,
        )
        with diagnostic._full_closure_crease_suppressed() as suppressions:
            actual = phase33._compose_eye_lids(
                proposal, plate, lid_texture, proposal_owner, (80, 60), (31, 24), 0.75,
            )
        self.assertEqual(expected, actual)
        self.assertTrue(np.array_equal(baseline, proposal))
        self.assertTrue(np.array_equal(baseline_owner, proposal_owner))
        self.assertEqual(suppressions, [])

    def test_renderer_order_rules_out_eye_cage_misalignment(self) -> None:
        phase34_source = inspect.getsource(phase35.phase34_candidate09._native_frame)
        phase35_source = inspect.getsource(phase35.compose_direct_address_frame)
        self.assertLess(
            phase34_source.index("canvas[warp_support > 0]"),
            phase34_source.index("phase33._compose_eye_lids"),
        )
        self.assertLess(
            phase35_source.index("frame.paste(face_frame"),
            phase35_source.index('regions["head"]'),
        )

    def test_implementation_has_no_encoder_or_subprocess_import(self) -> None:
        source = Path(diagnostic.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("subprocess", imported)
        self.assertNotIn("ffmpeg", imported)


if __name__ == "__main__":
    unittest.main()
