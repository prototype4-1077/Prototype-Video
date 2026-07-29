import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from pipeline.cartoon_chunk_assembly import (
    assemble_chunked_video,
    validate_chunk_reports,
    validate_frame_sequence,
)


class CartoonChunkAssemblyTests(unittest.TestCase):
    def _chunk_report(self, root: Path, chunk_id: str, start: int, end: int, look: str = "look-v4") -> None:
        payload = {
            "look_profile": {"sha256": look},
            "performance": {
                "render_mode": "chunk",
                "rendered_frames": end - start + 1,
                "chunk_window": {"frame_start": start, "frame_end": end},
            },
        }
        (root / f"chunk-{chunk_id}-report.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_assembly_requires_exact_frames_and_chunk_coverage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            for frame in range(1, 7):
                parent = first if frame <= 3 else second
                (parent / f"frame_{frame:04d}.png").write_bytes(b"PNG")
            self._chunk_report(root, "01", 1, 3)
            self._chunk_report(root, "02", 4, 6)
            output = root / "june-npr.mp4"
            report_path = root / "promotion.json"
            with mock.patch("pipeline.cartoon_chunk_assembly.subprocess.run") as run:
                report = assemble_chunked_video(
                    root,
                    output,
                    frame_count=6,
                    report_path=report_path,
                )
            command = run.call_args.args[0]
            self.assertIn("-frames:v", command)
            self.assertIn("6", command)
            self.assertEqual(report["chunk_count"], 2)
            self.assertEqual(report["look_profile_sha256"], "look-v4")
            self.assertTrue(report_path.is_file())

    def test_missing_frame_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "frame_0001.png").write_bytes(b"PNG")
            with self.assertRaisesRegex(ValueError, "missing"):
                validate_frame_sequence(root, frame_count=2)

    def test_overlapping_chunk_reports_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._chunk_report(root, "01", 1, 3)
            self._chunk_report(root, "02", 3, 6)
            with self.assertRaisesRegex(ValueError, "expected 4, got 3"):
                validate_chunk_reports(root, frame_count=6)


if __name__ == "__main__":
    unittest.main()
