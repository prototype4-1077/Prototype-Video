import copy
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_ledger_pour_audio_repair_v3 as repair


class Candidate03AudioRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = repair.load_contract()
        cls.candidate02, cls.candidate03 = repair.assemble_candidate03(cls.contract)

    def test_contract_binds_rejection_and_requires_new_authorization(self) -> None:
        rejected = self.contract["rejected_predecessor"]
        self.assertEqual(rejected["human_verdict"], "REJECTED_AUDIBLE_STATIC")
        self.assertTrue(rejected["prior_ratification_revoked"])
        self.assertTrue(rejected["immutable"])
        self.assertIsNone(self.contract["authorization"]["receipt"])
        self.assertTrue(self.contract["authorization"]["required_before_build"])
        self.assertEqual(
            self.contract["noise_proxy"]["classification"],
            "deterministic_artifact_regression_gate_not_general_perceptual_safety",
        )
        self.assertTrue(self.contract["noise_proxy"]["human_listening_required"])

    def test_candidate03_is_exact_and_changes_only_repair_span(self) -> None:
        audio = self.contract["audio"]
        start, end = audio["repair_span"]
        self.assertTrue(np.array_equal(self.candidate03[:start], self.candidate02[:start]))
        self.assertTrue(np.array_equal(self.candidate03[end:], self.candidate02[end:]))
        self.assertEqual(
            hashlib.sha256(repair.candidate02_builder._pcm24_bytes(self.candidate03)).hexdigest(),
            audio["expected_candidate03_pcm_data_sha256"],
        )
        self.assertEqual(int(np.count_nonzero(np.any(self.candidate03 != self.candidate02, axis=1))), 39_838)
        self.assertEqual(int(np.count_nonzero(self.candidate03 != self.candidate02)), 79_676)

    def test_rejected_candidate02_fails_new_static_gates_candidate03_passes(self) -> None:
        metrics = repair.measure_candidate03(self.contract, self.candidate02, self.candidate03)
        self.assertGreater(metrics["rejected_candidate02_full_mix_static_like_window_ratio"], 0.30)
        self.assertGreater(metrics["rejected_candidate02_full_mix_static_like_run_seconds"], 0.75)
        self.assertEqual(metrics["rejected_candidate02_focus_static_like_window_ratio"], 1.0)
        self.assertLessEqual(metrics["full_mix_static_like_window_ratio"], 0.30)
        self.assertLessEqual(metrics["full_mix_static_like_run_seconds"], 0.75)
        self.assertLessEqual(metrics["focus_static_like_window_ratio"], 0.05)
        self.assertTrue(metrics["full_mix_proxy_coverage_complete"])

    def test_preflight_predicts_exact_wav_without_output_or_claim(self) -> None:
        output = repair._output_path(self.contract)
        claim = output.with_name(output.name + ".attempt-v1.claim.json")
        self.assertFalse(output.exists())
        self.assertFalse(claim.exists())
        result = repair.preflight()
        self.assertTrue(result["machine_gates_passed"])
        self.assertFalse(result["build_authorized"])
        self.assertEqual(result["predicted_candidate03_wav_sha256"], self.contract["audio"]["expected_candidate03_wav_sha256"])
        self.assertFalse(output.exists())
        self.assertFalse(claim.exists())

    def test_build_fails_closed_without_authorization_and_writes_nothing(self) -> None:
        output = repair._output_path(self.contract)
        claim = output.with_name(output.name + ".attempt-v1.claim.json")
        with self.assertRaisesRegex(repair.Candidate03AudioError, "separate exact authorization"):
            repair.write_audio_candidate()
        self.assertFalse(output.exists())
        self.assertFalse(claim.exists())

    def test_direct_script_and_module_preflight_invocations_both_work(self) -> None:
        invocations = (
            [sys.executable, str(repair.REPO_ROOT / "pipeline" / "cartoon_ledger_pour_audio_repair_v3.py"), "preflight"],
            [sys.executable, "-m", "pipeline.cartoon_ledger_pour_audio_repair_v3", "preflight"],
        )
        for command in invocations:
            with self.subTest(command=command):
                completed = subprocess.run(
                    command,
                    cwd=repair.REPO_ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                payload = json.loads(completed.stdout)
                self.assertTrue(payload["machine_gates_passed"])
                self.assertFalse(payload["build_authorized"])
                self.assertFalse(payload["output_created"])

    def test_authorization_requires_single_verdict_and_dynamic_hashes(self) -> None:
        contract = copy.deepcopy(self.contract)
        tokens = [
            *contract["authorization"]["required_binding_tokens"],
            repair.EXPECTED_AUTHORIZATION_SUBJECT_CANONICAL_SHA256,
            repair.REVIEWED_NULL_CONTRACT_RAW_LF_SHA256,
            repair._implementation_hash(),
            contract["locks"]["audible_noise_proxy"]["sha256"],
            contract["locks"]["repair_tests"]["sha256"],
            contract["locks"]["proxy_tests"]["sha256"],
        ]
        verdict = contract["authorization"]["required_verdict"]
        payload = f"## Verdict: {verdict}\n" + "\n".join(str(token) for token in tokens) + "\n"
        with tempfile.TemporaryDirectory(dir=repair.REPO_ROOT / "collab") as directory:
            path = Path(directory) / "authorization.md"
            path.write_text(payload, encoding="utf-8", newline="\n")
            contract["authorization"]["receipt"] = {
                "path": str(path),
                "hash_domain": "raw_bytes",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            self.assertEqual(
                repair._authorization_subject_hash(contract),
                repair.EXPECTED_AUTHORIZATION_SUBJECT_CANONICAL_SHA256,
            )
            accepted = repair._authorization(contract)
            self.assertEqual(accepted["verdict"], verdict)
            path.write_text(payload + f"## Verdict: {verdict}\n", encoding="utf-8", newline="\n")
            contract["authorization"]["receipt"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(repair.Candidate03AudioError, "authorization verdict lines"):
                repair._authorization(contract)

    def test_attempt_claim_is_exclusive_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "claim.json"
            payload = {"attempt": 1, "label": "deterministic"}
            repair._claim_attempt(path, payload)
            original = (json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(FileExistsError):
                repair._claim_attempt(path, {"attempt": 2})
            self.assertEqual(path.read_bytes(), original)

    def test_claim_fsync_failure_preserves_claim_consumes_attempt_and_blocks_retry(self) -> None:
        authorization = {
            "path": "collab/test-authorization.md",
            "hash_domain": "raw_bytes",
            "sha256": "test-authorization-hash",
            "verdict": self.contract["authorization"]["required_verdict"],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate03"
            stage = output.with_name("." + output.name + ".stage")
            claim = output.with_name(output.name + ".attempt-v1.claim.json")
            common = (
                patch.object(repair, "load_contract", return_value=self.contract),
                patch.object(repair, "_authorization", return_value=authorization),
                patch.object(repair, "_output_path", return_value=output),
                patch.object(repair, "_source_state", return_value={"stable": True}),
            )
            with common[0], common[1], common[2], common[3], patch.object(
                repair.os, "fsync", side_effect=OSError("injected claim fsync failure")
            ):
                with self.assertRaisesRegex(repair.ClaimWriteError, "could not be durably written") as caught:
                    repair.write_audio_candidate()
            self.assertEqual(caught.exception.claim, claim)
            self.assertTrue(claim.is_file())
            self.assertFalse(output.exists())
            self.assertFalse(stage.exists())
            with patch.object(repair, "load_contract", return_value=self.contract), patch.object(
                repair, "_authorization", return_value=authorization
            ), patch.object(repair, "_output_path", return_value=output), patch.object(
                repair, "_source_state", return_value={"stable": True}
            ):
                with self.assertRaisesRegex(repair.Candidate03AudioError, "attempt claim already exists"):
                    repair.write_audio_candidate()

    def test_claim_partial_write_and_close_failures_preserve_claim(self) -> None:
        real_fdopen = repair.os.fdopen

        class FaultingHandle:
            def __init__(self, descriptor: int, failure: str) -> None:
                self.handle = real_fdopen(descriptor, "wb")
                self.failure = failure

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                self.handle.close()
                if exc_type is None and self.failure == "close":
                    raise OSError("injected claim close failure")
                return False

            def write(self, payload: bytes) -> int:
                if self.failure == "write":
                    self.handle.write(payload[: max(1, len(payload) // 2)])
                    raise OSError("injected partial claim write failure")
                return self.handle.write(payload)

            def flush(self) -> None:
                self.handle.flush()

            def fileno(self) -> int:
                return self.handle.fileno()

        for failure in ("write", "close"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "claim.json"

                def faulting_fdopen(descriptor: int, mode: str) -> FaultingHandle:
                    self.assertEqual(mode, "wb")
                    return FaultingHandle(descriptor, failure)

                with patch.object(repair.os, "fdopen", side_effect=faulting_fdopen):
                    with self.assertRaisesRegex(repair.ClaimWriteError, f"{failure} failure") as caught:
                        repair._claim_attempt(path, {"attempt": 1})
                self.assertEqual(caught.exception.claim, path)
                self.assertTrue(path.is_file())
                with self.assertRaises(FileExistsError):
                    repair._claim_attempt(path, {"attempt": 2})

    def test_static_implementation_has_no_subprocess_or_video_write_route(self) -> None:
        source = inspect.getsource(repair)
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("ffmpeg", source.lower())
        self.assertNotIn(".mp4", source.lower())
        self.assertIn("os.O_EXCL", source)
        self.assertIn("human_audio_accepted\": False", source)

    def test_contract_output_inventory_is_audio_and_json_only(self) -> None:
        output = self.contract["output"]
        self.assertTrue(output["pcm_mix_filename"].endswith(".wav"))
        for key in ("manifest_filename", "noise_evidence_filename", "build_receipt_filename"):
            self.assertTrue(output[key].endswith(".json"))
        self.assertEqual(self.contract["gates"]["required_encoded_media_files"], 0)

    def test_proxy_mutation_outside_flagged_interval_is_detected(self) -> None:
        mutated = self.candidate03.copy()
        rng = np.random.default_rng(44)
        start, end = round(6.0 * 48_000), round(6.8 * 48_000)
        noise = np.round(rng.normal(0.0, 0.013, (end - start, 2)) * repair.PCM24_MAX).astype(np.int32)
        mutated[start:end] = noise
        measured = repair.noise_proxy.audible_noise_proxy(mutated)
        self.assertGreater(measured["broadband_static"]["maximum_static_like_run_seconds"], 0.75)


if __name__ == "__main__":
    unittest.main()
