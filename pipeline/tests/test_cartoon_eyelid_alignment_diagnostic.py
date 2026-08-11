from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path
import subprocess
import unittest

import numpy as np

from pipeline import cartoon_eyelid_alignment_diagnostic as diagnostic
from pipeline import cartoon_source_textured_direct_address as phase35


def _synthetic_sclera(shape: tuple[int, int], center: tuple[int, int], radius: tuple[int, int]) -> dict[str, dict]:
    yy, xx = np.indices(shape)
    hard = (((xx - center[0]) / radius[0]) ** 2 + ((yy - center[1]) / radius[1]) ** 2) <= 1.0
    leak = np.zeros(shape, dtype=bool)
    leak[center[1] + radius[1] - 1:center[1] + radius[1] + 2, center[0] + 8:center[0] + 12] = True
    registered = np.zeros(shape, dtype=bool)
    registered[
        center[1] - radius[1]:center[1] + radius[1] + 1,
        center[0] - radius[0]:center[0] + radius[0] + 1,
    ] = True
    leak &= registered
    baseline_alpha = np.full(shape, 255, dtype=np.uint8)
    baseline_alpha[leak] = 0
    return {
        "synthetic": {
            "eye_name": "synthetic",
            "center": center,
            "radius": radius,
            "leak": leak,
            "registered_patch": registered,
            "planning_alpha": baseline_alpha,
            "planning_hard_owner": hard,
        }
    }


class EyelidAlignmentDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = diagnostic.load_contract()
        cls.prepared = phase35.prepare_direct_address()
        cls.sclera = diagnostic._classified_sclera_masks(cls.prepared, cls.contract)

    def test_contract_is_still_only_and_binds_predecessor_and_verdict(self) -> None:
        self.assertEqual(self.contract["contract_version"], 3)
        self.assertEqual(self.contract["cash_cost"], 0)
        self.assertFalse(self.contract["diagnostic"]["video_encode_allowed"])
        self.assertFalse(self.contract["diagnostic"]["accepted_source_mutation_allowed"])
        self.assertEqual(
            self.contract["predecessor"]["commit_sha"],
            "52d5a6d74a8928fd0ff14cc2c4e3e34adf0c8928",
        )
        self.assertEqual(
            self.contract["locks"]["controlling_james_verdict"]["sha256"],
            "9f3974ddcfc4715ea40501bcc46f60594da7021b342047eeed6d44992c729bb3",
        )

    def test_machine_candidate_masks_and_disputed_canthus_are_frozen(self) -> None:
        left = self.sclera["viewer_left_eye"]
        right = self.sclera["viewer_right_eye"]
        self.assertEqual(left["core_metrics"]["area"], 167)
        self.assertEqual(right["core_metrics"]["area"], 261)
        self.assertEqual(left["leak_metrics"]["area"], 2)
        self.assertEqual(right["leak_metrics"]["area"], 82)
        self.assertEqual(int((left["leak"] & ~left["registered_patch"]).sum()), 0)
        self.assertEqual(int((right["leak"] & ~right["registered_patch"]).sum()), 0)
        self.assertEqual(
            int((left["leak"] & ~left["planning_hard_owner"]).sum())
            + int((right["leak"] & ~right["planning_hard_owner"]).sum()),
            36,
        )
        self.assertEqual(
            int((left["leak"] & left["planning_hard_owner"]).sum())
            + int((right["leak"] & right["planning_hard_owner"]).sum()),
            48,
        )
        self.assertEqual(left["disputed_canthus_metrics"]["area"], 3)
        self.assertEqual(left["disputed_canthus_metrics"]["bbox_xyxy"], [621, 253, 623, 255])
        self.assertEqual(int((left["disputed_canthus"] & left["core"]).sum()), 0)

    def test_full_closure_toggles_are_separable_and_owner_area_is_not_double_counted(self) -> None:
        phase33 = phase35.phase34_candidate09.phase33
        shape = (120, 160, 3)
        yy, xx = np.indices(shape[:2])
        plate = np.stack((150 + xx % 40, 90 + yy % 50, 55 + (xx + yy) % 35), axis=2).astype(np.uint8)
        lid_texture = np.roll(plate, 7, axis=0)
        center = (80, 60)
        radius = (31, 24)
        sclera = _synthetic_sclera(shape[:2], center, radius)
        frames: dict[str, np.ndarray] = {}
        owners: dict[str, np.ndarray] = {}
        areas: dict[str, int] = {}
        for name, suppress, expand in (
            ("baseline", False, False),
            ("crease_only", True, False),
            ("mask_only", False, True),
            ("combined", True, True),
        ):
            frame = plate.copy()
            owner = np.zeros(shape[:2], dtype=np.uint8)
            if name == "baseline":
                _, area = phase33._compose_eye_lids(frame, plate, lid_texture, owner, center, radius, 1.0)
            else:
                with diagnostic._full_closure_variant(
                    sclera, suppress_crease=suppress, expand_sclera=expand,
                ):
                    _, area = phase33._compose_eye_lids(frame, plate, lid_texture, owner, center, radius, 1.0)
            frames[name] = frame
            owners[name] = owner
            areas[name] = area

        crease_diff = np.any(frames["baseline"] != frames["crease_only"], axis=2)
        mask_diff = np.any(frames["baseline"] != frames["mask_only"], axis=2)
        combined_diff = np.any(frames["baseline"] != frames["combined"], axis=2)
        leak = sclera["synthetic"]["leak"]
        hard = sclera["synthetic"]["planning_hard_owner"]
        self.assertEqual(int((mask_diff & ~leak).sum()), 0)
        self.assertTrue(np.array_equal(combined_diff, crease_diff | mask_diff))
        self.assertEqual(
            areas["mask_only"], areas["baseline"] + int((leak & ~hard).sum()),
        )
        self.assertEqual(
            int(((owners["mask_only"] == 8) & leak).sum()), int(leak.sum()),
        )

    def test_partial_closure_is_byte_and_owner_identical_for_all_toggles(self) -> None:
        phase33 = phase35.phase34_candidate09.phase33
        plate = np.full((120, 160, 3), [180, 115, 72], dtype=np.uint8)
        lid_texture = plate.copy()
        lid_texture[:, :, 0] = np.arange(160, dtype=np.uint8)[None, :]
        center = (80, 60)
        radius = (31, 24)
        sclera = _synthetic_sclera(plate.shape[:2], center, radius)
        for closure in (0.0, 0.25, 0.5, 0.75):
            baseline = plate.copy()
            baseline_owner = np.zeros(plate.shape[:2], dtype=np.uint8)
            expected = phase33._compose_eye_lids(
                baseline, plate, lid_texture, baseline_owner, center, radius, closure,
            )
            for suppress, expand in ((True, False), (False, True), (True, True)):
                proposal = plate.copy()
                proposal_owner = np.zeros(plate.shape[:2], dtype=np.uint8)
                with diagnostic._full_closure_variant(
                    sclera, suppress_crease=suppress, expand_sclera=expand,
                ):
                    actual = phase33._compose_eye_lids(
                        proposal, plate, lid_texture, proposal_owner, center, radius, closure,
                    )
                self.assertEqual(expected, actual)
                self.assertTrue(np.array_equal(baseline, proposal))
                self.assertTrue(np.array_equal(baseline_owner, proposal_owner))

    def test_actual_full_closure_call_capture_uses_two_registered_source_writes(self) -> None:
        phase33 = phase35.phase34_candidate09.phase33
        shape = (120, 160, 3)
        plate = np.full(shape, [180, 115, 72], dtype=np.uint8)
        lid_texture = np.roll(plate, 5, axis=0)
        center, radius = (80, 60), (31, 24)
        sclera = _synthetic_sclera(shape[:2], center, radius)
        owner = np.zeros(shape[:2], dtype=np.uint8)
        with diagnostic._full_closure_variant(
            sclera, suppress_crease=True, expand_sclera=True,
        ) as audit:
            phase33._compose_eye_lids(
                plate.copy(), plate, lid_texture, owner, center, radius, 1.0,
            )
        self.assertEqual(len(audit["eye_calls"]), 1)
        call = audit["eye_calls"][0]
        self.assertEqual(call["source_call_count"], 2)
        self.assertEqual(
            call["source_call_order"],
            ["upper_lid_registered_texture", "lower_lid_registered_texture"],
        )
        self.assertTrue(all(row["source_shares_registered_texture_memory"] for row in call["source_call_metrics"]))
        self.assertEqual(int((call["lower_alpha_map"][sclera["synthetic"]["leak"]] < 255).sum()), 0)

    def test_prospective_kernel_bounds_are_declared_and_negative_injection_fails(self) -> None:
        support_contract = self.contract["diagnostic"]["prospective_transform_support"]
        self.assertEqual(support_contract["phase35_head_warp"]["input_support_radius_px"], 2)
        self.assertEqual(support_contract["phase35_camera_resize"]["input_support_radius_px"], 3)
        self.assertEqual(support_contract["phase36_camera_resize"]["input_support_radius_px"], 3)
        native = np.zeros((21, 21), dtype=bool)
        native[10, 10] = True
        prospective = diagnostic._dilate_chebyshev(native, 2)
        diagnostic._require_prospective_containment(native, prospective, "positive control")
        injected = native.copy()
        injected[10, 13] = True
        with self.assertRaises(diagnostic.EyelidDiagnosticError):
            diagnostic._require_prospective_containment(
                injected, prospective, "one-pixel-outside-bound negative injection",
            )

    def test_predecessor_worktree_bytes_equal_committed_head_blobs_and_attrs(self) -> None:
        snapshot = self.contract["diagnostic"]["byte_snapshot"]
        locked_by_path = {
            value["path"]: value
            for value in self.contract["locks"].values()
            if value.get("hash_domain") == "committed_head_blob_bytes"
        }
        for relative, expected_attrs in snapshot["expected_effective_attributes"].items():
            worktree_bytes = (diagnostic.REPO_ROOT / relative).read_bytes()
            head_bytes = subprocess.run(
                ["git", "show", f"HEAD:{relative}"],
                cwd=diagnostic.REPO_ROOT,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
            self.assertEqual(worktree_bytes, head_bytes, relative)
            self.assertEqual(hashlib.sha256(head_bytes).hexdigest(), locked_by_path[relative]["sha256"])
            for attribute, expected in expected_attrs.items():
                line = subprocess.run(
                    ["git", "check-attr", attribute, "--", relative],
                    cwd=diagnostic.REPO_ROOT,
                    check=True,
                    stdout=subprocess.PIPE,
                    text=True,
                ).stdout.strip()
                self.assertEqual(line.rsplit(": ", 1)[-1], expected, f"{relative} {attribute}")

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
        self.assertNotIn("_minimum_chebyshev_guard", source)
        self.assertIn("report_path.write_bytes(report_bytes)", source)


if __name__ == "__main__":
    unittest.main()
