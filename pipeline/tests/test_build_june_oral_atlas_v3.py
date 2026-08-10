from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

import pipeline.build_june_oral_atlas_v3 as builder


class OralAtlasBuilderTests(unittest.TestCase):
    def test_known_good_output_is_verified_without_overwrite(self) -> None:
        before = builder._sha256(builder.OUTPUT)
        result = builder.build()
        self.assertEqual(result["publication"], "verified_existing_immutable_output")
        self.assertEqual(result["sha256"], builder.EXPECTED_OUTPUT_SHA256)
        self.assertEqual(builder._sha256(builder.OUTPUT), before)

    def test_existing_output_mismatch_is_refused_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "atlas.png"
            sentinel = b"do-not-overwrite"
            output.write_bytes(sentinel)
            with mock.patch.object(builder, "OUTPUT", output):
                with self.assertRaisesRegex(builder.OralAtlasBuildError, "existing output atlas SHA-256 mismatch"):
                    builder.build()
            self.assertEqual(output.read_bytes(), sentinel)


if __name__ == "__main__":
    unittest.main()
