from __future__ import annotations

import gzip
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_source_textured_delivery_v2 as delivery


class SourceTexturedDeliveryV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = delivery.load_contract()

    def test_contract_binds_exact_candidate03_review_and_one_encode(self) -> None:
        contract = self.contract
        self.assertEqual(
            delivery._canonical_hash(contract),
            delivery.EXPECTED_CONTRACT_CANONICAL_SHA256,
        )
        self.assertEqual(
            contract["locks"]["source_manifest"]["sha256"],
            "250b678686f87c5cdcabeaedd0f6e39833b9dcaa7d2387c76fa8fe016b2885fe",
        )
        self.assertEqual(
            contract["source_evidence"]["archive_sha256"],
            "b5908bfce4ac10ad7e3ad74e58a8cf9f8e352033b14c1828315e96cd615f6e0f",
        )
        self.assertEqual(
            contract["locks"]["source_implementation_archive"]["renderer_sha256"],
            "97612673a65b92e83d9d54debaf1738508d88442813759ba9959a41dee32fe77",
        )
        self.assertEqual(
            contract["authorization"]["required_verdict"],
            "PHASE35_C03_VISUAL_ACCEPTED_ENCODE_AUTHORIZED",
        )
        self.assertEqual(contract["authorization"]["maximum_video_encoder_processes"], 1)
        self.assertFalse(contract["authorization"]["automatic_retry_allowed"])
        self.assertFalse(contract["authorization"]["renderer_invocation_allowed"])
        self.assertFalse(contract["promotion_policy"]["accepted_full_cartoon_production_delivery"])

    def test_review_and_archived_renderer_are_independently_validated(self) -> None:
        delivery._validate_review(self.contract)
        delivery._validate_source_implementation_archive(self.contract)
        review = delivery._repo_path(self.contract["locks"]["visual_review"]["path"])
        self.assertEqual(
            delivery._lf_hash(review),
            "d45bf8fada6d102caf6c0b38d9f81ff4938b9475a6407421746f72e3f8df34cc",
        )

    def test_locked_mix_is_exact_pcm24_stereo_clock(self) -> None:
        mix = delivery._repo_path(self.contract["locks"]["delivery_mix"]["path"])
        self.assertEqual(delivery._probe_pcm_wave(mix), {
            "sample_rate": 48000,
            "channels": 2,
            "sample_width": 3,
            "block_align": 6,
            "byte_rate": 288000,
            "data_bytes": 2188800,
            "sample_count": 364800,
        })

    def test_archive_stream_reconstructs_and_hashes_every_frame(self) -> None:
        header = {
            "format": "phase35_rgb24_xor_previous_gzip_v1",
            "width": 3,
            "height": 2,
            "channels": 3,
            "frame_count": 3,
            "frame_bytes": 18,
            "xor_seed": "all_zero_rgb24_frame",
        }
        frames = [
            np.arange(18, dtype=np.uint8).reshape(2, 3, 3),
            np.full((2, 3, 3), 117, dtype=np.uint8),
            np.flip(np.arange(18, dtype=np.uint8).reshape(2, 3, 3), axis=1).copy(),
        ]
        hashes = [
            {"frame": index, "rgb_sha256": delivery._raw_frame_hash(frame)}
            for index, frame in enumerate(frames, start=1)
        ]
        contract = {"source_evidence": {"archive_header": header}}
        with tempfile.TemporaryDirectory(prefix="phase35-delivery-archive-") as temporary:
            path = Path(temporary) / "frames.gz"
            with gzip.open(path, "wb", compresslevel=1) as archive:
                archive.write((json.dumps(header, sort_keys=True) + "\n").encode("utf-8"))
                previous = np.zeros((2, 3, 3), dtype=np.uint8)
                for frame in frames:
                    archive.write(np.bitwise_xor(frame, previous).tobytes())
                    previous = frame
            actual = list(delivery.iter_source_frames(path, contract, hashes))
            self.assertEqual(len(actual), 3)
            for expected, observed in zip(frames, actual):
                self.assertTrue(np.array_equal(expected, observed))

            with gzip.open(path, "wb", compresslevel=1) as archive:
                archive.write((json.dumps(header) + "\n").encode("utf-8"))
                archive.write(bytes(17))
            with self.assertRaises(delivery.SourceTexturedDeliveryV2Error):
                list(delivery.iter_source_frames(path, contract, hashes))

    def test_picture_audio_and_successor_gates_are_complete(self) -> None:
        probe = {
            "streams": [
                {
                    "codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p",
                    "color_range": "tv", "color_space": "bt709", "color_transfer": "bt709",
                    "color_primaries": "bt709",
                    "width": 1920, "height": 1080, "nb_frames": "228", "nb_read_frames": "228",
                    "r_frame_rate": "30/1", "avg_frame_rate": "30/1", "start_time": "0.000000",
                    "duration": "7.600000",
                },
                {
                    "codec_type": "audio", "codec_name": "aac", "profile": "LC", "sample_rate": "48000",
                    "channels": 2, "time_base": "1/48000", "duration_ts": "364800",
                    "start_time": "0.000000", "duration": "7.600000",
                },
            ],
            "format": {"start_time": "0.000000", "duration": "7.600000"},
        }
        video = {
            "decoded_frame_count": 228,
            "worst_full_frame_psnr_db": 45.0,
            "worst_face_psnr_db": 44.0,
            "worst_face_ssim": 0.995,
            "worst_eye_psnr_db": 43.0,
            "worst_mouth_psnr_db": 43.0,
            "minimum_decoded_laplacian_variance": 200.0,
            "maximum_decoded_adjacent_face_8x8_mean_delta": 146.0,
            "maximum_absolute_pairwise_codec_delta": 0.8,
            "pair_count": 227,
        }
        audio = {
            "audited_playback_samples_per_channel": 364800,
            "aac_packet_frames": 357,
            "aac_decoder_padding_samples_per_channel": 768,
            "channel_zero_lag_correlation": [0.9997, 0.9997],
            "channel_signal_to_error_db": [32.6, 32.6],
            "mid_zero_lag_correlation": 0.9997,
            "side_zero_lag_correlation": 0.9993,
            "side_signal_to_error_db": 28.3,
            "best_correlation_lag_samples": 0,
        }
        gates = delivery.decoded_gates(self.contract, probe, video, audio)
        expected_names = [
            "one_video_stream", "one_audio_stream", "no_other_streams", "video_codec_h264",
            "video_pixel_format", "video_color_range", "video_color_space", "video_color_transfer",
            "video_color_primaries", "video_width", "video_height", "video_reported_frames",
            "video_ffprobe_read_frames", "video_opencv_decoded_frames", "video_r_frame_rate",
            "video_avg_frame_rate", "video_start_time", "video_duration", "audio_codec_aac",
            "audio_profile_lc", "audio_sample_rate", "audio_channels", "audio_time_base",
            "audio_start_time", "audio_container_duration_samples", "audio_duration",
            "container_start_time", "container_duration", "full_frame_psnr", "face_psnr",
            "face_ssim", "eye_psnr", "mouth_psnr", "decoded_sharpness",
            "decoded_adjacent_face_delta", "same_domain_pairwise_codec_delta",
            "all_temporal_pairs_evaluated", "audio_playback_sample_clock",
            "aac_packet_frames_present", "aac_decoder_padding", "audio_channel_correlation",
            "audio_channel_signal_to_error", "audio_mid_correlation", "audio_side_correlation",
            "audio_side_signal_to_error", "audio_best_correlation_lag",
        ]
        self.assertEqual([gate["name"] for gate in gates], expected_names)
        self.assertTrue(all(gate["passed"] for gate in gates))
        video["maximum_absolute_pairwise_codec_delta"] = 2.01
        failed = [
            gate["name"] for gate in delivery.decoded_gates(self.contract, probe, video, audio)
            if not gate["passed"]
        ]
        self.assertEqual(failed, ["same_domain_pairwise_codec_delta"])
        video["maximum_absolute_pairwise_codec_delta"] = 0.8
        probe["streams"][0]["start_time"] = "0.033333"
        failed = [
            gate["name"] for gate in delivery.decoded_gates(self.contract, probe, video, audio)
            if not gate["passed"]
        ]
        self.assertEqual(failed, ["video_start_time"])

    def test_missing_aac_packet_counter_fails_closed(self) -> None:
        expected = self.contract["clock"]["audio_sample_count"]
        audio = np.full((expected, 2), 0.1, dtype=np.float64)
        payload = bytes(expected * 6)
        fake_decode = (audio, payload, ["fake-decoder"])
        probe = {
            "streams": [{
                "codec_type": "audio", "duration_ts": "364800",
            }],
        }
        with patch.object(delivery, "_decode_audio_s24", side_effect=[fake_decode, fake_decode]):
            with self.assertRaises(delivery.SourceTexturedDeliveryV2Error):
                delivery._audit_audio(
                    Path("proof.mp4"), Path("mix.wav"), Path("ffmpeg"), probe, self.contract,
                )

    def test_declared_state_assertion_rejects_lock_drift(self) -> None:
        state = {
            "delivery_contract_canonical_sha256": delivery.EXPECTED_CONTRACT_CANONICAL_SHA256,
            "source_contract_sha256": self.contract["locks"]["source_contract"]["sha256"],
            "source_manifest_sha256": self.contract["locks"]["source_manifest"]["sha256"],
            "local_source_manifest_sha256": self.contract["locks"]["source_manifest"]["sha256"],
            "source_archive_sha256": self.contract["source_evidence"]["archive_sha256"],
            "source_implementation_archive_sha256": self.contract["locks"]["source_implementation_archive"]["sha256"],
            "visual_review_lf_sha256": self.contract["locks"]["visual_review"]["sha256"],
            "delivery_mix_sha256": self.contract["locks"]["delivery_mix"]["sha256"],
            "opencv_h264_probe_video_sha256": self.contract["locks"]["opencv_h264_probe_video"]["sha256"],
        }
        delivery._assert_declared_state(state, self.contract)
        state["delivery_mix_sha256"] = "0" * 64
        with self.assertRaises(delivery.SourceTexturedDeliveryV2Error):
            delivery._assert_declared_state(state, self.contract)

    def test_encoder_is_one_shot_archive_only_and_does_not_mask_clock(self) -> None:
        source = inspect.getsource(delivery.render_authorized_proof)
        self.assertLess(source.index("initial_declared_state"), source.index("_validate_toolchain"))
        self.assertLess(source.index("_validate_toolchain"), source.index("_claim_attempt"))
        self.assertLess(source.index("initial_declared_state"), source.index("prepared = preflight"))
        self.assertLess(source.index("prepared = preflight"), source.index("_claim_attempt"))
        self.assertLess(source.index("_claim_attempt"), source.index("process = subprocess.Popen"))
        self.assertEqual(source.count("subprocess.Popen("), 1)
        self.assertIn("iter_source_frames", source)
        self.assertNotIn("compose_direct_address_frame", source)
        self.assertNotIn('"-shortest"', source)
        self.assertNotIn('"-t",', source)
        self.assertIn('"-frames:v", "228"', source)
        self.assertIn('"-map_chapters", "-1"', source)
        self.assertIn('"-crf", str(encoding["crf"])', source)
        self.assertEqual(self.contract["delivery"]["encoding"]["crf"], 0)

    def test_audio_metric_helpers_detect_identity_and_error(self) -> None:
        source = np.linspace(-0.5, 0.5, 4096, dtype=np.float64)
        decoded = source + np.sin(np.arange(source.size)) * 1e-4
        self.assertGreater(delivery._audio_correlation(source, decoded), 0.999)
        self.assertGreater(delivery._audio_snr(source, decoded), 30.0)
        self.assertEqual(
            hashlib.sha256(np.ascontiguousarray(source).tobytes()).hexdigest(),
            hashlib.sha256(np.ascontiguousarray(source.copy()).tobytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
