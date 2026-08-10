import ast
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import shutil

import numpy as np

from pipeline import cartoon_ledger_pour_prores_master as master


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / master.CONTRACT_RELATIVE_PATH


class CartoonLedgerPourProResMasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = master.load_contract()

    def test_authorization_subject_and_all_repository_locks_are_exact(self) -> None:
        self.assertEqual(
            master._canonical_hash(master._authorization_subject(self.contract)),
            master.EXPECTED_AUTHORIZATION_SUBJECT_SHA256,
        )
        for reference in self.contract["locks"].values():
            self.assertEqual(master._lock_hash(reference), reference["sha256"])

    def test_contract_is_zero_cash_nonrendering_and_fail_closed(self) -> None:
        contract = self.contract
        self.assertEqual(contract["cash_cost"], 0)
        self.assertFalse(contract["paid_runtime_dependency"])
        self.assertFalse(contract["network_runtime_required"])
        failure = contract["failure_policy"]
        for key in (
            "fallback_allowed", "automatic_reencode_allowed", "renderer_invocation_allowed",
            "picture_mutation_allowed", "audio_mutation_allowed", "network_allowed",
            "distribution_encode_allowed", "promotion_allowed",
        ):
            self.assertFalse(failure[key])

    def test_master_and_vui_gates_are_deliberately_unbound(self) -> None:
        self.assertIsNone(self.contract["vui_prerequisite"]["probe_result_receipt"])
        self.assertIsNone(self.contract["authorization"]["receipt"])
        self.assertIsNone(master._vui_result(self.contract))
        self.assertIsNone(master._authorization(self.contract, None))

    def test_unbound_run_refuses_before_tools_outputs_or_subprocesses(self) -> None:
        with patch.object(master, "_resolved_tool") as tool, patch.object(master, "_outputs_path") as output, patch(
            "pipeline.cartoon_ledger_pour_prores_master.subprocess.Popen"
        ) as popen:
            with self.assertRaisesRegex(master.ProResMasterError, "VUI probe result is not bound"):
                master.run_authorized_master()
        tool.assert_not_called()
        output.assert_not_called()
        popen.assert_not_called()

    def test_preflight_reports_both_null_gates_without_an_encoder(self) -> None:
        prepared = {
            "picture_audit": {"verified_frames": 303},
            "audio_audit": {"sample_count": 484800},
            "toolchain": {"verified": True},
        }
        with patch.object(master, "_resolved_tool", side_effect=[Path("ffmpeg"), Path("ffprobe")]), patch.object(
            master, "_prepare", return_value=prepared
        ):
            result = master.preflight()
        self.assertEqual(result["status"], "BLOCKED_NO_MEDIA_PROCESS_STARTED")
        self.assertFalse(result["vui_prerequisite_bound"])
        self.assertFalse(result["master_authorization_bound"])
        self.assertEqual(result["encoder_processes_started"], 0)
        self.assertFalse(result["output_resolved"])

    def test_command_is_one_prores4444_pcm24_transaction(self) -> None:
        command = master._command_template(self.contract)
        joined = " ".join(command)
        required = (
            "-c:v prores_ks", "-profile:v 4", "-pix_fmt yuv444p10le", "-tag:v ap4h",
            "-alpha_bits 0", "-fps_mode cfr",
            "-color_range tv", "-colorspace bt709", "-color_primaries bt709", "-color_trc bt709",
            "-c:a pcm_s24le", "-ar 48000", "-ac 2", "atrim=end_sample=484800",
            "-video_track_timescale 15360", "-movflags +faststart+write_colr", "-frames:v 303",
            "in_range=full:out_range=limited:out_color_matrix=bt709",
            "setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709",
            "-n $OUTPUT",
        )
        for token in required:
            self.assertIn(token, joined)
        for forbidden in ("-shortest", "-t 10.1", "aresample", "loudnorm", "libx264", "aac"):
            self.assertNotIn(forbidden, joined)
        self.assertEqual(command.count("$OUTPUT"), 1)

    def test_audio_master_wav_and_pcm_payload_are_exact(self) -> None:
        path = master._repo_path(self.contract["locks"]["audio_wav"]["path"])
        pcm, probe = master._read_pcm24_data(path, self.contract)
        self.assertEqual(len(pcm), 484800 * 6)
        self.assertEqual(probe["sample_count"], 484800)
        self.assertEqual(probe["data_sha256"], "24f32febdb18206956fff3ea2de7119dc43a00f9eab37780b94edc948871cb46")

    def test_picture_manifest_binds_all_303_source_hashes(self) -> None:
        manifest_path = master._repo_path(self.contract["locks"]["picture_manifest"]["path"])
        manifest = master._strict_json_loads(manifest_path.read_bytes(), "test manifest")
        self.assertTrue(manifest["machine_passed"])
        self.assertEqual(len(manifest["frame_hashes"]), 303)
        self.assertEqual(
            master._canonical_hash(manifest["frame_hashes"]),
            "d09bcdc6a3c86e26e9ce77070f18504f3101e4b87edfc54e169e3b4b641a6451",
        )

    def test_authorization_subject_retains_the_vui_result_binding(self) -> None:
        bound = copy.deepcopy(self.contract)
        bound["vui_prerequisite"]["probe_result_receipt"] = {"path": "proof.json", "sha256": "a" * 64}
        subject = master._authorization_subject(bound)
        self.assertEqual(subject["vui_prerequisite"]["probe_result_receipt"], bound["vui_prerequisite"]["probe_result_receipt"])
        self.assertIsNone(subject["authorization"]["receipt"])
        self.assertNotEqual(master._canonical_hash(subject), master.EXPECTED_AUTHORIZATION_SUBJECT_SHA256)

    def test_vui_result_requires_exact_machine_report_and_captured_state(self) -> None:
        contract = copy.deepcopy(self.contract)
        gate = contract["vui_prerequisite"]
        result = {
            "machine_passed": True,
            "status": gate["required_status"],
            "encoder": {"process_count": 1},
            "disposition": {"retry_allowed": False},
            "captured_state": {
                "authorization_subject_sha256": gate["probe_authorization_subject_sha256"],
                "implementation_sha256": gate["probe_implementation_sha256"],
                "command_template_sha256": gate["probe_command_template_sha256"],
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "proof.json"
            path.write_text(json.dumps(result), encoding="utf-8")
            gate["probe_result_receipt"] = {"path": "proof.json", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            with patch.object(master, "REPO_ROOT", root):
                verified = master._vui_result(contract)
            self.assertEqual(verified["sha256"], gate["probe_result_receipt"]["sha256"])
            result["machine_passed"] = False
            path.write_text(json.dumps(result), encoding="utf-8")
            gate["probe_result_receipt"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with patch.object(master, "REPO_ROOT", root), self.assertRaisesRegex(master.ProResMasterError, "VUI machine result"):
                master._vui_result(contract)

    def test_master_authorization_requires_unique_verdict_and_every_binding_token(self) -> None:
        contract = copy.deepcopy(self.contract)
        gate = contract["authorization"]
        vui = {"path": "proof.json", "sha256": "vui-result-hash"}
        tokens = [
            master.EXPECTED_AUTHORIZATION_SUBJECT_SHA256,
            "implementation-hash", master._command_template_hash(contract), vui["sha256"],
            contract["picture"]["archive_sha256"], contract["picture"]["frame_inventory_canonical_sha256"],
            contract["audio"]["wav_sha256"], contract["audio"]["pcm_data_sha256"],
            contract["toolchain"]["ffmpeg_sha256"], contract["toolchain"]["ffprobe_sha256"],
        ]
        verdict = f'{gate["required_verdict_field"]} {gate["required_verdict"]}'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            implementation = root / master.IMPLEMENTATION_RELATIVE_PATH
            implementation.parent.mkdir(parents=True)
            implementation.write_bytes(b"implementation")
            review = root / "review.md"
            review.write_text(verdict + "\n" + "\n".join(tokens) + "\n", encoding="utf-8")
            gate["receipt"] = {"path": "review.md", "sha256": hashlib.sha256(review.read_bytes()).hexdigest()}
            with patch.object(master, "REPO_ROOT", root), patch.object(master, "_sha256", side_effect=lambda path: "implementation-hash" if Path(path) == implementation else hashlib.sha256(Path(path).read_bytes()).hexdigest()):
                receipt = master._authorization(contract, vui)
            self.assertEqual(receipt["verdict"], gate["required_verdict"])
            review.write_text(verdict + "\n" + "\n".join(tokens[:-1]) + "\n", encoding="utf-8")
            gate["receipt"]["sha256"] = hashlib.sha256(review.read_bytes()).hexdigest()
            with patch.object(master, "REPO_ROOT", root), patch.object(master, "_sha256", side_effect=lambda path: "implementation-hash" if Path(path) == implementation else hashlib.sha256(Path(path).read_bytes()).hexdigest()), self.assertRaisesRegex(master.ProResMasterError, "omits binding token"):
                master._authorization(contract, vui)

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_numbers(self) -> None:
        with self.assertRaisesRegex(master.ProResMasterError, "duplicate key"):
            master._strict_json_loads(b'{"a":1,"a":2}', "test")
        with self.assertRaisesRegex(master.ProResMasterError, "non-finite"):
            master._strict_json_loads(b'{"a":NaN}', "test")

    def test_mov_parser_finds_one_nclc_under_ap4h_and_faststart(self) -> None:
        def atom(name: bytes, payload: bytes) -> bytes:
            return struct.pack(">I4s", len(payload) + 8, name) + payload

        colr = atom(b"colr", b"nclc" + struct.pack(">HHH", 1, 1, 1))
        visual_sample_entry = atom(b"ap4h", b"\0" * 78 + colr)
        stsd = atom(b"stsd", b"\0\0\0\0" + struct.pack(">I", 1) + visual_sample_entry)
        mov = atom(b"moov", atom(b"trak", atom(b"mdia", atom(b"minf", atom(b"stbl", stsd))))) + atom(b"mdat", b"frame")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.mov"
            path.write_bytes(mov)
            parsed = master._parse_mov_colr(path)
        self.assertEqual(parsed["type"], "nclc")
        self.assertEqual(parsed["path"], "moov/trak/mdia/minf/stbl/stsd/ap4h/colr")
        self.assertEqual((parsed["primaries"], parsed["transfer"], parsed["matrix"]), (1, 1, 1))
        self.assertTrue(parsed["moov_before_mdat"])

    def test_picture_metrics_helpers_are_exact_for_identical_arrays(self) -> None:
        frame = np.arange(8 * 8 * 3, dtype=np.uint8).reshape(8, 8, 3)
        self.assertEqual(master._psnr(frame, frame), 999.0)
        self.assertAlmostEqual(master._windowed_ssim(frame, frame), 1.0)
        self.assertGreaterEqual(master._sharpness(frame), 0.0)

    def test_fraction_parser_preserves_exact_frame_clock(self) -> None:
        self.assertEqual(master._as_fraction("10.100000", "duration"), Fraction(101, 10))
        self.assertEqual([Fraction(i, 30) for i in range(303)][-1], Fraction(151, 15))

    def test_gate_comparators_are_not_directionally_inverted(self) -> None:
        self.assertTrue(master._gate("min", 45.0, 45.0, "minimum")["passed"])
        self.assertFalse(master._gate("min", 44.9, 45.0, "minimum")["passed"])
        self.assertTrue(master._gate("max", 1.0, 1.0, "maximum")["passed"])
        self.assertFalse(master._gate("max", 1.1, 1.0, "maximum")["passed"])

    def test_realistic_ffprobe_rounding_uses_integer_pts_and_12bit_prores_semantics(self) -> None:
        colors = {
            "color_range": "tv", "color_space": "bt709",
            "color_transfer": "bt709", "color_primaries": "bt709",
        }
        video = {
            "codec_type": "video", "codec_name": "prores", "profile": "4444",
            "codec_tag_string": "ap4h", "pix_fmt": "yuv444p12le", "bits_per_raw_sample": "12",
            "width": 1920, "height": 1080, "avg_frame_rate": "30/1", "nb_frames": "303",
            "time_base": "1/15360", "duration_ts": 155136, "start_time": "0.000000",
            "duration": "10.100000", "sample_aspect_ratio": "1:1", "tags": {"vendor_id": "FFMP"},
            **colors,
        }
        audio_stream = {
            "codec_type": "audio", "codec_name": "pcm_s24le", "sample_fmt": "s32",
            "sample_rate": "48000", "channels": 2, "start_time": "0.000000", "duration": "10.100000",
        }
        frames = [
            {
                "media_type": "video", "best_effort_timestamp": index * 512,
                "best_effort_timestamp_time": f"{index / 30:.6f}",
                "width": 1920, "height": 1080, "pix_fmt": "yuv444p12le", **colors,
            }
            for index in range(303)
        ]
        picture = {
            "frame_count": 303,
            "minimums": {
                "full_psnr_db": 46.0, "face_psnr_db": 43.0, "eye_psnr_db": 43.0,
                "mouth_psnr_db": 43.0, "face_8x8_window_ssim": 0.995, "sharpness_ratio": 0.95,
            },
            "maximum_pairwise_motion_delta": 0.5,
        }
        audio = {"sample_count": 484800, "data_sha256": self.contract["audio"]["pcm_data_sha256"]}
        colr = {
            "type": "nclc", "path": "moov/trak/mdia/minf/stbl/stsd/ap4h/colr",
            "payload_bytes": 10, "primaries": 1, "transfer": 1, "matrix": 1, "moov_before_mdat": True,
        }
        gates = master._audit_gates(
            self.contract, {"streams": [video, audio_stream]}, {"frames": frames}, colr, picture, audio,
        )
        self.assertTrue(all(gate["passed"] for gate in gates), [gate for gate in gates if not gate["passed"]])
        frames[1]["best_effort_timestamp"] = 511
        gates = master._audit_gates(
            self.contract, {"streams": [video, audio_stream]}, {"frames": frames}, colr, picture, audio,
        )
        failed = [gate["name"] for gate in gates if not gate["passed"]]
        self.assertEqual(failed, ["video_frame_integer_timestamps"])

    def test_attempt_claim_is_exclusive_at_the_final_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "attempt"
            claim = master._claim_attempt(output, {"stable": True}, ["ffmpeg"])
            self.assertTrue(claim.is_file())
            with self.assertRaisesRegex(master.ProResMasterError, "already claimed"):
                master._claim_attempt(output, {"stable": True}, ["ffmpeg"])

    def test_success_allowlist_includes_fixed_and_worst_review_frames_only(self) -> None:
        picture = {
            "review_artifacts": [
                {"file": "decoded-review-frame-0075.png"},
                {"file": "decoded-review-frame-worst-full-psnr-db-0082.png"},
            ]
        }
        expected = master._expected_success_artifacts(
            self.contract, ".attempt.claim.json", picture, include_package=True,
        )
        self.assertIn("decoded-review-frame-0075.png", expected)
        self.assertIn("decoded-review-frame-worst-full-psnr-db-0082.png", expected)
        self.assertIn(self.contract["output"]["package_filename"], expected)
        self.assertNotIn("unexpected.tmp", expected)

    def test_postclaim_setup_failure_is_preserved_without_encoder_launch(self) -> None:
        contract = copy.deepcopy(self.contract)
        vui = {"path": "probe.json", "sha256": "probe-hash", "report": {}}
        authorization = {"path": "review.md", "sha256": "review-hash", "verdict": "allowed"}
        original_copy = shutil.copy2
        copy_calls = 0

        def fail_first_copy(source: Path, destination: Path) -> Path:
            nonlocal copy_calls
            copy_calls += 1
            if copy_calls == 1:
                raise OSError("injected postclaim copy failure")
            return original_copy(source, destination)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "master-attempt"
            prepared = {"audio_path": Path(directory) / "audio.wav"}
            with patch.object(master, "load_contract", return_value=contract), patch.object(
                master, "_vui_result", return_value=vui
            ), patch.object(master, "_authorization", return_value=authorization), patch.object(
                master, "_resolved_tool", side_effect=[Path("ffmpeg"), Path("ffprobe")]
            ), patch.object(master, "_outputs_path", return_value=output), patch.object(
                master, "_prepare", return_value=prepared
            ), patch.object(master.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(0, 0, 2_000_000_000)), patch.object(
                master, "_capture_state", return_value={"stable": True}
            ), patch.object(master, "_assert_state"), patch.object(
                master.shutil, "copy2", side_effect=fail_first_copy
            ), patch("pipeline.cartoon_ledger_pour_prores_master.subprocess.Popen") as popen:
                with self.assertRaisesRegex(OSError, "postclaim copy failure"):
                    master.run_authorized_master()
            popen.assert_not_called()
            self.assertTrue((Path(directory) / ".master-attempt.attempt01-claim.json").is_file())
            rejected = Path(directory) / "master-attempt-rejected"
            self.assertTrue((rejected / "failure-v1.json").is_file())
            self.assertTrue((rejected / contract["output"]["package_filename"]).is_file())
            self.assertFalse(any(Path(directory).glob(".master-attempt.partial-*")))

    def test_claim_fsync_failure_is_still_a_preserved_consumed_attempt(self) -> None:
        contract = copy.deepcopy(self.contract)
        vui = {"path": "probe.json", "sha256": "probe-hash", "report": {}}
        authorization = {"path": "review.md", "sha256": "review-hash", "verdict": "allowed"}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "master-attempt"
            prepared = {"audio_path": Path(directory) / "audio.wav"}
            with patch.object(master, "load_contract", return_value=contract), patch.object(
                master, "_vui_result", return_value=vui
            ), patch.object(master, "_authorization", return_value=authorization), patch.object(
                master, "_resolved_tool", side_effect=[Path("ffmpeg"), Path("ffprobe")]
            ), patch.object(master, "_outputs_path", return_value=output), patch.object(
                master, "_prepare", return_value=prepared
            ), patch.object(master.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(0, 0, 2_000_000_000)), patch.object(
                master, "_capture_state", return_value={"stable": True}
            ), patch.object(master, "_assert_state"), patch.object(
                master.os, "fsync", side_effect=OSError("injected claim fsync failure")
            ), patch("pipeline.cartoon_ledger_pour_prores_master.subprocess.Popen") as popen:
                with self.assertRaisesRegex(master.ClaimWriteError, "could not be durably written"):
                    master.run_authorized_master()
            popen.assert_not_called()
            claim = Path(directory) / ".master-attempt.attempt01-claim.json"
            self.assertTrue(claim.is_file())
            rejected = Path(directory) / "master-attempt-rejected"
            failure = json.loads((rejected / "failure-v1.json").read_text(encoding="utf-8"))
            self.assertEqual(failure["error_type"], "ClaimWriteError")
            self.assertTrue(failure["disposition"]["authorization_consumed"])
            self.assertTrue((rejected / claim.name).is_file())
            self.assertFalse(any(Path(directory).glob(".master-attempt.partial-*")))

    def test_static_master_transaction_claims_before_exactly_one_encoder_launch_site(self) -> None:
        source = (REPO_ROOT / master.IMPLEMENTATION_RELATIVE_PATH).read_text(encoding="utf-8")
        function = source[source.index("def run_authorized_master"):source.index("def _parse_args")]
        self.assertLess(function.index("claim = _claim_attempt"), function.index("process = subprocess.Popen"))
        self.assertEqual(function.count("process = subprocess.Popen"), 1)

    def test_source_module_has_no_renderer_network_or_paid_service_dependency(self) -> None:
        source = (REPO_ROOT / master.IMPLEMENTATION_RELATIVE_PATH).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        for forbidden in ("requests", "urllib", "socket", "boto3", "openai", "anthropic", "cartoon_ledger_pour"):
            self.assertNotIn(forbidden, imports)
        self.assertNotIn("render_frame", source)


if __name__ == "__main__":
    unittest.main()
