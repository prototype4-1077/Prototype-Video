from __future__ import annotations

import copy
import hashlib
import inspect
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_phase36_master_review_harness as harness


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class Phase36MasterReviewHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = harness.load_contract()

    def _binding(self) -> dict[str, object]:
        values = {
            "binding_version": 1,
            "status": "FUTURE_REAUTHORIZED_MASTER_COMPLETED",
            "supersedes_revoked_candidate02_master": True,
            "revoked_candidate02_or_f91_artifact_used": False,
            "attempt_id": "phase36_future_master_attempt01",
            "claim_filename": ".future-master.attempt01-claim.json",
            "master_directory": "../../outputs/edit/future-master-attempt01",
        }
        for index, field in enumerate(self.contract["binding_policy"]["required_hash_fields"], start=1):
            values[field] = f"{index:064x}"
        return values

    def _probe(self) -> dict[str, object]:
        clock = self.contract["clock"]
        video = {
            "codec_type": "video", "codec_name": "prores", "codec_tag_string": "ap4h",
            "pix_fmt": "yuv444p12le", "width": 1920, "height": 1080,
            "time_base": "1/15360", "avg_frame_rate": "30/1",
            "color_range": "tv", "color_space": "bt709", "color_transfer": "bt709",
            "color_primaries": "bt709",
        }
        audio = {
            "codec_type": "audio", "codec_name": "pcm_s24le", "time_base": "1/48000",
            "sample_rate": "48000", "channels": 2,
        }
        frames: list[dict[str, object]] = [
            {"media_type": "video", "pts": index * 512, "duration": 512}
            for index in range(clock["frame_count"])
        ]
        cursor = 0
        while cursor < clock["audio_sample_count"]:
            samples = min(1024, clock["audio_sample_count"] - cursor)
            frames.append({"media_type": "audio", "pts": cursor, "nb_samples": samples})
            cursor += samples
        return {"streams": [video, audio], "format": {"duration": "10.100000"}, "frames": frames}

    def _master_evidence(self, root: Path) -> tuple[dict[str, object], dict[str, object]]:
        binding = self._binding()
        media = root / self.contract["master_requirements"]["media_filename"]
        claim = root / str(binding["claim_filename"])
        media.write_bytes(b"future reauthorized mov bytes")
        claim.write_bytes(b"owned future claim\n")
        binding["media_sha256"] = harness._sha256(media)
        binding["claim_sha256"] = harness._sha256(claim)
        report = {
            "attempt_id": binding["attempt_id"],
            "status": "MACHINE_PASSED_HUMAN_REVIEW_REQUIRED",
            "machine_passed": True,
            "authorization_consumed": True,
            "encoder": {"process_count": 1, "return_code": 0, "command_template_sha256": binding["command_template_sha256"]},
            "media": {"file": media.name, "bytes": media.stat().st_size, "sha256": binding["media_sha256"]},
            "gates": [{"name": "synthetic", "passed": True}],
            "gates_failed": 0,
            "failed_gates": [],
            "disposition": {
                "human_native_size_review_required": True,
                "promotion_allowed": False,
                "distribution_encode_allowed": False,
                "retry_allowed": False,
            },
            "captured_state": {
                "authorization_subject_sha256": binding["authorization_subject_sha256"],
                "implementation_sha256": binding["implementation_sha256"],
                "command_template_sha256": binding["command_template_sha256"],
                "picture_archive_sha256": binding["picture_archive_sha256"],
                "ffmpeg_sha256": binding["ffmpeg_sha256"],
                "ffprobe_sha256": binding["ffprobe_sha256"],
                "authorization": {"sha256": binding["authorization_receipt_sha256"]},
                "vui_result": {"sha256": binding["vui_report_sha256"]},
                "locks": {"future_audio_wav": binding["audio_wav_sha256"]},
            },
            "sources": {"audio": {"data_sha256": binding["audio_pcm_sha256"]}},
        }
        report_path = root / self.contract["master_requirements"]["report_filename"]
        _write_json(report_path, report)
        binding["report_sha256"] = harness._sha256(report_path)
        artifacts = []
        for path in sorted((media, claim, report_path), key=lambda item: item.name):
            artifacts.append({"file": path.name, "bytes": path.stat().st_size, "sha256": harness._sha256(path)})
        package = {
            "package_version": 1, "attempt_id": binding["attempt_id"], "machine_passed": True,
            "disposition": report["disposition"], "artifacts": artifacts,
        }
        package_path = root / self.contract["master_requirements"]["package_filename"]
        _write_json(package_path, package)
        binding["package_sha256"] = harness._sha256(package_path)
        paths = {"root": root, "report": report_path, "package": package_path, "media": media, "claim": claim}
        return binding, {"paths": paths, "report": report, "package": package}

    def test_plan_explicitly_refuses_revoked_master_lineage(self) -> None:
        result = harness.plan()
        self.assertEqual(result["status"], "WAITING_FOR_FUTURE_REAUTHORIZED_MASTER_BINDING")
        self.assertFalse(result["current_candidate02_or_f91_master_allowed"])
        self.assertFalse(result["video_encoder_allowed"])
        self.assertEqual(result["review_frames"]["f240_f256"], list(range(240, 257)))
        self.assertEqual(result["binding_template"], "collab/phase36-future-master-review-binding-template-v1.json")

    def test_contract_has_grouped_cut_blink_viseme_and_audio_coverage(self) -> None:
        review = self.contract["review_frames"]
        self.assertEqual([item["frame"] for item in review["cuts"]], [75, 76, 237, 238])
        self.assertEqual([item["frame"] for item in review["blink"]], list(range(244, 253)))
        self.assertEqual([item["viseme"] for item in review["viseme"]], list("GBCHAEFX"))
        self.assertEqual(harness._selected_frame_numbers(self.contract), [75, 76, 101, 112, 126, 136, 142, 150, 173, 201, 237, 238, *range(240, 257)])
        self.assertEqual(self.contract["audio_segment"]["start_sample"], 112800)
        self.assertEqual(self.contract["audio_segment"]["end_sample"], 165600)

    def test_binding_requires_external_hash_and_future_supersession(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "binding.json"
            binding = self._binding()
            _write_json(path, binding)
            digest = harness._sha256(path)
            loaded = harness._load_binding(path, digest, self.contract)
            self.assertTrue(loaded["supersedes_revoked_candidate02_master"])
            revoked = copy.deepcopy(binding)
            revoked["revoked_candidate02_or_f91_artifact_used"] = True
            _write_json(path, revoked)
            with self.assertRaisesRegex(harness.ReviewHarnessError, "revoked artifact policy"):
                harness._load_binding(path, harness._sha256(path), self.contract)
            with self.assertRaisesRegex(harness.ReviewHarnessError, "binding SHA-256"):
                harness._load_binding(path, "0" * 64, self.contract)
            candidate02 = copy.deepcopy(binding)
            candidate02["audio_wav_sha256"] = self.contract["revoked_inputs"]["candidate02_audio_wav_sha256"]
            _write_json(path, candidate02)
            with self.assertRaisesRegex(harness.ReviewHarnessError, "revoked Candidate02 audio WAV"):
                harness._load_binding(path, harness._sha256(path), self.contract)

    def test_absent_binding_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(harness.ReviewHarnessError, "binding is absent"):
                harness._load_binding(Path(directory) / "missing.json", "0" * 64, self.contract)

    def test_decode_commands_are_read_only_raw_rgb_and_pcm(self) -> None:
        video = harness._video_decode_command(Path("ffmpeg"), Path("master.mov"))
        audio = harness._audio_decode_command(Path("ffmpeg"), Path("master.mov"))
        self.assertEqual(video[-1], "pipe:1")
        self.assertIn("rawvideo", video)
        self.assertNotIn("-c:v", video)
        self.assertNotIn("-c", video)
        self.assertEqual(audio[-1], "pipe:1")
        self.assertIn("pcm_s24le", audio)
        for command in (video, audio):
            self.assertNotIn("-y", command)
            self.assertNotIn("-n", command)
            self.assertNotIn("http", " ".join(command))

    def test_full_pts_audit_accepts_exact_clock_and_rejects_one_tick_gap(self) -> None:
        probe = self._probe()
        audit, color = harness._audit_pts(probe, self.contract)
        self.assertTrue(audit["continuous"])
        self.assertEqual(audit["video_frame_count"], 303)
        self.assertEqual(audit["audio_sample_count"], 484800)
        self.assertEqual(audit["end_sync_offset_seconds"], 0.0)
        self.assertEqual(color["stream"]["transfer"], "bt709")
        broken = copy.deepcopy(probe)
        next(item for item in broken["frames"] if item["media_type"] == "video" and item["pts"] == 512)["pts"] = 513
        with self.assertRaisesRegex(harness.ReviewHarnessError, "video PTS sequence"):
            harness._audit_pts(broken, self.contract)

    def test_pcm24_segment_is_exact_sample_slice(self) -> None:
        clock = self.contract["clock"]
        values = np.arange(clock["audio_sample_count"] * 2, dtype=np.int64).reshape(-1, 2) % 100000 - 50000
        unsigned = np.where(values < 0, values + 0x1000000, values).astype(np.uint32)
        payload = np.empty((values.shape[0], 2, 3), dtype=np.uint8)
        payload[:, :, 0] = unsigned & 0xFF
        payload[:, :, 1] = (unsigned >> 8) & 0xFF
        payload[:, :, 2] = (unsigned >> 16) & 0xFF
        raw = payload.tobytes()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "segment.wav"
            audit = harness._write_audio_segment(raw, destination, self.contract)
            start, end = 112800 * 6, 165600 * 6
            self.assertEqual(audit["pcm_sha256"], hashlib.sha256(raw[start:end]).hexdigest())
            self.assertEqual(audit["sample_frames"], 52800)
            self.assertEqual(audit["clipped_samples"], 0)
            self.assertTrue(destination.is_file())

    def test_streaming_mov_parser_reads_nclc_without_loading_media(self) -> None:
        def atom(name: bytes, payload: bytes) -> bytes:
            return struct.pack(">I4s", len(payload) + 8, name) + payload

        colr = atom(b"colr", b"nclc" + struct.pack(">HHH", 1, 1, 1))
        ap4h = atom(b"ap4h", b"\0" * 78 + colr)
        stsd = atom(b"stsd", b"\0" * 8 + ap4h)
        hierarchy = atom(b"moov", atom(b"trak", atom(b"mdia", atom(b"minf", atom(b"stbl", stsd)))))
        payload = hierarchy + atom(b"mdat", b"pixels")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.mov"
            path.write_bytes(payload)
            observed = harness._parse_mov_colr(path)
        self.assertEqual(observed["type"], "nclc")
        self.assertEqual((observed["primaries"], observed["transfer"], observed["matrix"]), (1, 1, 1))
        self.assertTrue(observed["moov_before_mdat"])

    def test_master_package_requires_every_hash_and_exact_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding, evidence = self._master_evidence(root)
            with patch.object(harness, "_input_paths", return_value=evidence["paths"]):
                verified = harness._verify_master_evidence(binding, self.contract)
                self.assertEqual(verified["report"]["machine_passed"], True)
                (root / "rogue.txt").write_text("rogue", encoding="utf-8")
                with self.assertRaisesRegex(harness.ReviewHarnessError, "directory inventory"):
                    harness._verify_master_evidence(binding, self.contract)

    def test_inspect_verifies_input_before_output_resolution(self) -> None:
        source = inspect.getsource(harness.inspect_master)
        self.assertLess(source.index("_verify_master_evidence"), source.index("_output_directory"))

    def test_full_synthetic_inspection_preserves_mov_and_starts_no_encoder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "master"
            root.mkdir()
            binding, evidence = self._master_evidence(root)
            binding_path = Path(directory) / "binding.json"
            _write_json(binding_path, binding)
            output = Path(directory) / "review-output"
            frames = {
                frame: np.full((8, 8, 3), frame % 256, dtype=np.uint8)
                for frame in harness._selected_frame_numbers(self.contract)
            }
            pcm = b"\0" * (484800 * 2 * 3)
            colr = {"type": "nclc", "path": "moov/trak/mdia/minf/stbl/stsd/ap4h/colr", "payload_bytes": 10, "primaries": 1, "transfer": 1, "matrix": 1, "moov_before_mdat": True}

            def fake_probe(_ffprobe: Path, _media: Path, stdout: Path, stderr: Path) -> dict[str, object]:
                probe = self._probe()
                _write_json(stdout, probe)
                stderr.write_bytes(b"")
                return probe

            def fake_video(_ffmpeg: Path, _media: Path, stderr: Path, _contract: dict[str, object]):
                stderr.write_bytes(b"")
                return frames, {"command": ["ffmpeg", "-f", "rawvideo", "pipe:1"], "decoded_frames": 303, "decoded_rgb24_sha256": "a" * 64}

            def fake_audio(_ffmpeg: Path, _media: Path, stderr: Path, _contract: dict[str, object]):
                stderr.write_bytes(b"")
                return pcm, ["ffmpeg", "-f", "s24le", "pipe:1"]

            def fake_sheet(_frames, destination: Path, _color, _media_sha, _contract):
                destination.write_bytes(b"synthetic png")

            before = evidence["paths"]["media"].read_bytes()
            with patch.object(harness, "_load_binding", return_value=binding), patch.object(
                harness, "_verify_master_evidence", return_value=evidence
            ), patch.object(harness, "_resolved_tool", side_effect=[Path("ffmpeg"), Path("ffprobe")]), patch.object(
                harness, "_validate_tools"
            ), patch.object(harness, "_output_directory", return_value=output), patch.object(
                harness, "_run_ffprobe", side_effect=fake_probe
            ), patch.object(harness, "_parse_mov_colr", return_value=colr), patch.object(
                harness, "_decode_selected_frames", side_effect=fake_video
            ), patch.object(harness, "_decode_audio_pcm", side_effect=fake_audio), patch.object(
                harness, "_render_contact_sheet", side_effect=fake_sheet
            ), patch("pipeline.cartoon_phase36_master_review_harness.subprocess.Popen") as popen:
                result = harness.inspect_master(binding_path=binding_path, binding_sha256=harness._sha256(binding_path))
            popen.assert_not_called()
            self.assertEqual(result["video_encoder_processes_started"], 0)
            self.assertTrue(result["source_mov_immutable"])
            self.assertEqual(evidence["paths"]["media"].read_bytes(), before)
            self.assertTrue((output / self.contract["output"]["contact_sheet_filename"]).is_file())
            self.assertTrue((output / self.contract["audio_segment"]["filename"]).is_file())
            package = json.loads((output / self.contract["output"]["package_filename"]).read_text())
            self.assertEqual(package["video_encoder_processes_started"], 0)
            self.assertFalse(package["promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
