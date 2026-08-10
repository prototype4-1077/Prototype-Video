from __future__ import annotations

import inspect
import json
import unittest

import numpy as np

import pipeline.cartoon_source_textured_acceptance_audit as audit


class SourceTexturedAcceptanceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = audit.load_contract()

    def test_contract_is_canonical_and_locks_consumed_attempt(self) -> None:
        self.assertEqual(audit._canonical_hash(self.contract), audit.EXPECTED_CONTRACT_CANONICAL_SHA256)
        self.assertEqual(self.contract["contract_version"], 2)
        self.assertFalse(self.contract["original_attempt_state"]["retry_allowed"])
        self.assertFalse(self.contract["promotion"]["new_render_or_encode_authorized"])
        self.assertFalse(self.contract["promotion"]["accept_full_cartoon_production_delivery"])
        for reference in self.contract["locks"].values():
            self.assertEqual(audit._locked_hash(reference), reference["sha256"])

    def test_metric_uses_same_8x8_mean_absolute_rgb_domain(self) -> None:
        first = np.zeros((24, 24, 3), dtype=np.uint8)
        second = first.copy()
        second[8:16, 8:16] = 120
        self.assertAlmostEqual(audit._maximum_8x8_mean_absolute_rgb_delta(first, second), 120.0)
        self.assertEqual(audit._maximum_8x8_mean_absolute_rgb_delta(first, first), 0.0)

    def test_original_attempt_has_only_the_expected_failed_gate(self) -> None:
        report_path = audit._repo_path(self.contract["locks"]["attempt01_report"]["path"])
        report = json.loads(report_path.read_text(encoding="utf-8"))
        gates = audit._original_attempt_gates(self.contract, report)
        self.assertEqual(len(gates), 8)
        self.assertTrue(all(gate["passed"] for gate in gates))

    def test_audit_has_no_render_encode_or_network_process_path(self) -> None:
        source = inspect.getsource(audit)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("Popen", source)
        self.assertNotIn("VideoWriter", source)
        self.assertNotIn("compose_frame", source)
        self.assertNotIn("write_unencoded_preview", source)
        self.assertNotIn("ffmpeg", source.lower())

    def test_output_is_contract_pinned_and_immutable(self) -> None:
        output = audit._output_path(self.contract)
        self.assertEqual(output.name, "phase34-candidate08-successor-audit-v2")
        self.assertTrue(self.contract["output"]["immutable"])
        signature = inspect.signature(audit.run_successor_audit)
        self.assertEqual(len(signature.parameters), 0)

    def test_codec_gate_is_pairwise_and_stronger_than_worst_only_comparison(self) -> None:
        gate = self.contract["temporal_codec_gate"]
        self.assertEqual(gate["pair_count"], 95)
        self.assertEqual(gate["maximum_absolute_pairwise_decoded_minus_source_delta"], 2.0)
        self.assertTrue(gate["absolute_ceiling_is_advisory_only"])


if __name__ == "__main__":
    unittest.main()
