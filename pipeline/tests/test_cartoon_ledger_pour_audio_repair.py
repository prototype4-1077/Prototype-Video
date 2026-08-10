import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_ledger_pour_audio_repair as repair


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / repair.CONTRACT_RELATIVE_PATH
class CartoonLedgerPourAudioRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = repair.load_contract()
        cls.candidate01, cls.candidate02 = repair.assemble_candidate02(
            cls.contract,
            verify_phase26_provenance=False,
        )

    def test_contract_canonical_hash_and_all_repository_locks_match(self) -> None:
        parsed = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(repair._canonical_hash(parsed), repair.EXPECTED_CONTRACT_CANONICAL_SHA256)
        for reference in parsed["locks"].values():
            self.assertEqual(repair._sha256(repair._repo_path(reference["path"])), reference["sha256"])

    def test_contract_is_audio_only_free_and_fail_closed(self) -> None:
        contract = self.contract
        self.assertEqual(contract["cash_cost"], 0)
        self.assertFalse(contract["paid_runtime_dependency"])
        self.assertFalse(contract["network_runtime_required"])
        self.assertFalse(contract["failure_policy"]["picture_render_allowed"])
        self.assertFalse(contract["failure_policy"]["subprocess_allowed"])
        self.assertFalse(contract["failure_policy"]["encode_allowed"])
        self.assertTrue(contract["failure_policy"]["future_encode_requires_new_binding"])

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_values(self) -> None:
        with self.assertRaisesRegex(repair.AudioRepairError, "duplicate key"):
            repair._strict_json_loads(b'{"a":1,"a":2}', "test")
        with self.assertRaisesRegex(repair.AudioRepairError, "non-finite"):
            repair._strict_json_loads(b'{"a":NaN}', "test")

    def test_candidate01_failure_and_picture_manifest_are_exactly_bound(self) -> None:
        failure = repair._candidate01_failure(self.contract)
        manifest = repair._candidate01_manifest(self.contract)
        self.assertEqual(failure["defect"]["duration_samples"], 38400)
        self.assertEqual(failure["defect"]["affected_output_frames"], [76, 99])
        self.assertEqual(len(manifest["frame_hashes"]), 303)
        self.assertEqual(
            repair._canonical_hash(manifest["frame_hashes"]),
            "d09bcdc6a3c86e26e9ce77070f18504f3101e4b87edfc54e169e3b4b641a6451",
        )

    def test_locked_json_inputs_are_hashed_and_parsed_from_one_byte_snapshot(self) -> None:
        failure_path = repair._repo_path(self.contract["locks"]["candidate01_failure_receipt"]["path"])
        failure_payload = failure_path.read_bytes()
        with patch.object(Path, "read_bytes", return_value=failure_payload) as read_bytes:
            repair._candidate01_failure(self.contract)
        self.assertEqual(read_bytes.call_count, 1)
        manifest_path = repair._repo_path(self.contract["locks"]["candidate01_manifest"]["path"])
        manifest_payload = manifest_path.read_bytes()
        with patch.object(Path, "read_bytes", return_value=manifest_payload) as read_bytes:
            repair._candidate01_manifest(self.contract)
        self.assertEqual(read_bytes.call_count, 1)

    def test_bridge_asset_has_exact_geometry_and_hashes(self) -> None:
        path = repair._repo_path(self.contract["locks"]["candidate02_bridge_wav"]["path"])
        samples, probe = repair._read_pcm24_wave(path)
        self.assertEqual(samples.shape, (39840, 2))
        self.assertEqual(path.stat().st_size, 239084)
        self.assertEqual(repair._sha256(path), "ed938d8b77ed43939018ebabf875ef50d6dd5385ebf5648ef559659780ff432f")
        self.assertEqual(probe["data_sha256"], "5dcd0513a742b197bbbc39f5796f311c81e234d90891e2e543835b5a7b9dcaf7")
        source_path = repair._repo_path(self.contract["locks"]["candidate02_phase26_source_wav"]["path"])
        source, source_probe = repair._read_pcm24_wave(source_path)
        self.assertEqual(source.shape, (39840, 2))
        self.assertEqual(repair._sha256(source_path), "e902365f51006d3018af3ffd57e014c11e2e264cedb0a0e0aafa070823460570")
        self.assertEqual(source_probe["data_sha256"], "6c49c390d1c201a0a6e5c8e3ebfc86d06ae4228c4c5b8b792854f23a9d8eec71")

    def test_candidate02_replaces_only_the_declared_audio_span(self) -> None:
        self.assertTrue(np.array_equal(self.candidate02[:118560], self.candidate01[:118560]))
        self.assertTrue(np.array_equal(self.candidate02[158400:], self.candidate01[158400:]))
        self.assertEqual(int(np.count_nonzero(np.any(self.candidate02 != self.candidate01, axis=1))), 39839)
        self.assertEqual(self.candidate02.shape, (484800, 2))

    def test_candidate02_predicted_pcm_and_wav_hashes_are_exact(self) -> None:
        self.assertEqual(
            hashlib.sha256(repair._pcm24_bytes(self.candidate02)).hexdigest(),
            "24f32febdb18206956fff3ea2de7119dc43a00f9eab37780b94edc948871cb46",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate02.wav"
            repair._write_pcm24_wave(path, self.candidate02, 48000)
            written = repair._verify_written_candidate(self.contract, path, self.candidate02)
        self.assertEqual(written["wav_sha256"], "f498ba44f9443b2b025da6fe607322df7f47a7b22ce2a82e987419602ff3d781")
        self.assertEqual(written["pcm24_readback_channel_values"], 969600)

    def test_candidate02_signal_metrics_pass_all_new_continuity_gates(self) -> None:
        metrics = repair.measure_candidate02(self.contract, self.candidate01, self.candidate02)
        metrics.update({
            "picture_archive_reference_hash_unchanged": True,
            "picture_frame_hash_inventory_unchanged": True,
            "pcm24_readback_channel_values": 969600,
            "output_files": 2,
            "encoded_media_files": 0,
        })
        gates = repair._gate_report(self.contract, metrics)
        self.assertEqual(len(gates), 16)
        self.assertTrue(all(gate["passed"] for gate in gates))
        self.assertEqual(metrics["maximum_stereo_exact_zero_run_samples"], 0)
        self.assertEqual(metrics["fully_zero_picture_frames"], 0)
        self.assertAlmostEqual(metrics["minimum_output_frame_rms_dbfs"], -44.2136298222, places=6)
        self.assertAlmostEqual(metrics["same_porch_cut_100ms_rms_difference_db"], 4.3317685181, places=6)
        self.assertAlmostEqual(metrics["peak_dbfs"], -1.2935266236, places=6)

    def test_candidate01_zero_hole_fails_energy_gates_even_when_boundary_step_passed(self) -> None:
        metrics = repair.measure_candidate02(self.contract, self.candidate01, self.candidate01)
        self.assertEqual(metrics["maximum_stereo_exact_zero_run_samples"], 38400)
        self.assertEqual(metrics["fully_zero_picture_frames"], 24)
        self.assertLess(metrics["minimum_output_frame_rms_dbfs"], -100.0)
        boundary_step = float(np.max(np.abs(
            self.candidate01[120000].astype(np.float64) - self.candidate01[119999].astype(np.float64)
        )) / repair.PCM24_MAX)
        self.assertLessEqual(boundary_step, 0.01)

    def test_one_bit_dither_cannot_evade_the_energy_gate(self) -> None:
        dithered = self.candidate01.copy()
        pattern = np.where(np.arange(38400) % 2 == 0, 1, -1).astype(np.int32)
        dithered[120000:158400, 0] = pattern
        dithered[120000:158400, 1] = -pattern
        metrics = repair.measure_candidate02(self.contract, self.candidate01, dithered)
        self.assertLessEqual(metrics["maximum_stereo_exact_zero_run_samples"], 48)
        self.assertLess(metrics["minimum_output_frame_rms_dbfs"], -100.0)
        self.assertLess(metrics["minimum_output_frame_rms_dbfs"], self.contract["gates"]["minimum_output_frame_rms_dbfs"])

    def test_legitimate_quiet_room_tone_passes_the_energy_floor(self) -> None:
        metrics = repair.measure_candidate02(self.contract, self.candidate01, self.candidate02)
        self.assertEqual(metrics["minimum_output_frame_rms_frame"], 16)
        self.assertGreaterEqual(metrics["minimum_output_frame_rms_dbfs"], -60.0)

    def test_bridge_rederives_exactly_from_the_committed_phase26_source_slice(self) -> None:
        candidate01, candidate02 = repair.assemble_candidate02(self.contract, verify_phase26_provenance=True)
        self.assertTrue(np.array_equal(candidate01, self.candidate01))
        self.assertTrue(np.array_equal(candidate02, self.candidate02))

    def test_exact_claude_authorization_is_bound(self) -> None:
        authorization = repair._authorization(self.contract)
        self.assertEqual(
            authorization,
            {
                "path": "collab/CLAUDE_REVIEW_2026-08-10_2116Z.md",
                "hash_domain": "lf_normalized_text",
                "sha256": "649fb80582554ec639385c4c61716dc01c7e15efb13183be141588a763155df8",
                "verdict": "PHASE36_CANDIDATE02_AUDIO_ONLY_UNENCODED_BUILD_ALLOWED",
            },
        )

    def test_published_candidate02_evidence_is_exact_and_nonpromotable(self) -> None:
        root = REPO_ROOT / "collab/phase36_candidate_02"
        wav = root / "june-phase36-ledger-pour-mix-v2.wav"
        manifest_path = root / "june-phase36-ledger-pour-audio-repair-manifest-v2.json"
        receipt_path = root / "candidate02-build-receipt-v1.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["build_attempt"], 1)
        self.assertEqual(receipt["source_commit"], "82f03c451de22c781b5279473a30ec0b7ec8b952")
        self.assertEqual(repair._sha256(wav), "f498ba44f9443b2b025da6fe607322df7f47a7b22ce2a82e987419602ff3d781")
        self.assertEqual(repair._sha256(manifest_path), "7393f75faafa19e3102ca4be356b4b50380a83ed89628a500797108f946cddf4")
        self.assertEqual(receipt["artifacts"][wav.name]["sha256"], repair._sha256(wav))
        self.assertEqual(receipt["artifacts"][manifest_path.name]["sha256"], repair._sha256(manifest_path))
        self.assertTrue(manifest["machine_passed"])
        self.assertFalse(manifest["promotion_allowed"])
        self.assertFalse(manifest["encode_authorized"])
        self.assertEqual(manifest["failed_gates"], [])
        self.assertTrue(all(gate["passed"] for gate in manifest["gates"]))
        self.assertEqual(receipt["disposition"]["further_build_attempt_allowed"], False)
        self.assertEqual(receipt["disposition"]["human_audio_review_required"], True)

    def test_execution_source_state_binds_the_current_authorization_receipt(self) -> None:
        authorization = {"path": "review.md", "sha256": "review-hash", "verdict": "allowed"}
        with patch("pipeline.cartoon_ledger_pour_audio_repair._authorization", return_value=authorization):
            state = repair._source_state(self.contract, include_external_picture=False)
        self.assertEqual(state["authorization"], authorization)

    def test_execution_source_state_rejects_a_drifted_lock_instead_of_baselining_it(self) -> None:
        drifted = copy.deepcopy(self.contract)
        drifted["locks"]["candidate02_bridge_wav"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(repair.AudioRepairError, "source-state locked candidate02_bridge_wav SHA-256"):
            repair._source_state(drifted, include_external_picture=False)

    def test_exact_authorization_requires_one_verdict_and_all_binding_tokens(self) -> None:
        contract = copy.deepcopy(self.contract)
        gate = contract["authorization"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = root / "authorization.md"
            verdict = f"{gate['required_verdict_field']} {gate['required_verdict']}"
            review.write_text(verdict + "\n" + "\n".join(gate["required_binding_tokens"]) + "\n", encoding="utf-8")
            gate["receipt"] = {
                "path": "authorization.md",
                "hash_domain": "lf_normalized_text",
                "sha256": hashlib.sha256(review.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
            }
            with patch.object(repair, "REPO_ROOT", root):
                receipt = repair._authorization(contract)
            self.assertEqual(receipt["verdict"], gate["required_verdict"])
            review.write_text(verdict + "\n" + "\n".join(gate["required_binding_tokens"][:-1]) + "\n", encoding="utf-8")
            gate["receipt"]["sha256"] = hashlib.sha256(review.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            with patch.object(repair, "REPO_ROOT", root), self.assertRaisesRegex(repair.AudioRepairError, "omits binding token"):
                repair._authorization(contract)
            review.write_text(
                verdict + "\n## Verdict: PHASE36_CANDIDATE02_AUDIO_ONLY_BUILD_BLOCKED\n"
                + "\n".join(gate["required_binding_tokens"]) + "\n",
                encoding="utf-8",
            )
            gate["receipt"]["sha256"] = hashlib.sha256(review.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            with patch.object(repair, "REPO_ROOT", root), self.assertRaisesRegex(repair.AudioRepairError, "verdict lines"):
                repair._authorization(contract)

    def test_authorized_builder_writes_only_wav_and_manifest_to_fresh_output(self) -> None:
        authorization = {"path": "review.md", "sha256": "review-hash", "verdict": "allowed"}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate02"
            state = {"stable": True}
            with patch("pipeline.cartoon_ledger_pour_audio_repair._authorization", return_value=authorization), patch(
                "pipeline.cartoon_ledger_pour_audio_repair._output_path", return_value=output
            ), patch("pipeline.cartoon_ledger_pour_audio_repair._external_picture_archive", return_value={}), patch(
                "pipeline.cartoon_ledger_pour_audio_repair._source_state", return_value=state
            ), patch(
                "pipeline.cartoon_ledger_pour_audio_repair.assemble_candidate02",
                return_value=(self.candidate01, self.candidate02),
            ):
                result = repair.write_audio_candidate()
            self.assertTrue(result["machine_passed"])
            self.assertFalse(result["picture_rerendered"])
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {"june-phase36-ledger-pour-mix-v2.wav", "june-phase36-ledger-pour-audio-repair-manifest-v2.json"},
            )

    def test_builder_rejects_authorization_drift_before_publication_and_cleans_stage(self) -> None:
        authorization = {"path": "review.md", "sha256": "review-hash", "verdict": "allowed"}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate02"
            with patch("pipeline.cartoon_ledger_pour_audio_repair._authorization", return_value=authorization), patch(
                "pipeline.cartoon_ledger_pour_audio_repair._output_path", return_value=output
            ), patch("pipeline.cartoon_ledger_pour_audio_repair._source_state", side_effect=[
                {"authorization": authorization},
                repair.AudioRepairError("authorization drift"),
            ]), patch(
                "pipeline.cartoon_ledger_pour_audio_repair.assemble_candidate02",
                return_value=(self.candidate01, self.candidate02),
            ):
                with self.assertRaisesRegex(repair.AudioRepairError, "authorization drift"):
                    repair.write_audio_candidate()
            self.assertFalse(output.exists())
            self.assertFalse((output.parent / f".{output.name}.stage").exists())

    def test_builder_rejects_extra_directory_and_nested_file_then_cleans_stage(self) -> None:
        authorization = {"path": "review.md", "sha256": "review-hash", "verdict": "allowed"}
        original_write = repair._write_pcm24_wave

        def write_with_injected_entry(path: Path, samples: np.ndarray, sample_rate: int) -> None:
            original_write(path, samples, sample_rate)
            extra = path.parent / "extra"
            extra.mkdir()
            (extra / "hidden.bin").write_bytes(b"not allowed")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate02"
            state = {"stable": True}
            with patch("pipeline.cartoon_ledger_pour_audio_repair._authorization", return_value=authorization), patch(
                "pipeline.cartoon_ledger_pour_audio_repair._output_path", return_value=output
            ), patch("pipeline.cartoon_ledger_pour_audio_repair._source_state", return_value=state), patch(
                "pipeline.cartoon_ledger_pour_audio_repair.assemble_candidate02",
                return_value=(self.candidate01, self.candidate02),
            ), patch("pipeline.cartoon_ledger_pour_audio_repair._write_pcm24_wave", side_effect=write_with_injected_entry):
                with self.assertRaisesRegex(repair.AudioRepairError, "non-file entry"):
                    repair.write_audio_candidate()
            self.assertFalse(output.exists())
            self.assertFalse((output.parent / f".{output.name}.stage").exists())

    def test_module_has_no_image_video_network_or_subprocess_dependency(self) -> None:
        source = (REPO_ROOT / "pipeline/cartoon_ledger_pour_audio_repair.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        for forbidden in ("PIL", "cv2", "subprocess", "requests", "urllib", "socket", "moviepy", "av"):
            self.assertNotIn(forbidden, imports)
        self.assertNotIn("cartoon_ledger_pour", imports)


if __name__ == "__main__":
    unittest.main()
