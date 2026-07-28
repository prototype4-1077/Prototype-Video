import unittest

from pipeline.cartoon_lipsync import cues_to_frames, normalize_rhubarb


class CartoonLipSyncTests(unittest.TestCase):
    def test_silent_gaps_are_closed_and_adjacent_shapes_merge(self):
        payload = {
            "metadata": {"duration": 1.0},
            "mouthCues": [
                {"start": 0.2, "end": 0.4, "value": "A"},
                {"start": 0.4, "end": 0.6, "value": "A"},
            ],
        }
        result = normalize_rhubarb(payload)
        self.assertEqual(
            result["mouthCues"],
            [
                {"start": 0.0, "end": 0.2, "value": "X"},
                {"start": 0.2, "end": 0.6, "value": "A"},
                {"start": 0.6, "end": 1.0, "value": "X"},
            ],
        )

    def test_cues_convert_to_one_based_inclusive_frames(self):
        cues = cues_to_frames(
            {
                "metadata": {"duration": 1.0},
                "mouthCues": [{"start": 0.0, "end": 0.5, "value": "B"}],
            },
            fps=30,
        )
        self.assertEqual(cues[0]["frame_start"], 1)
        self.assertEqual(cues[0]["frame_end"], 15)
        self.assertEqual(cues[-1]["shape"], "X")
        self.assertEqual(cues[-1]["frame_end"], 30)

    def test_overlapping_cues_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlap"):
            normalize_rhubarb(
                {
                    "metadata": {"duration": 1.0},
                    "mouthCues": [
                        {"start": 0.0, "end": 0.6, "value": "A"},
                        {"start": 0.5, "end": 0.9, "value": "B"},
                    ],
                }
            )

    def test_unknown_shape_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            normalize_rhubarb(
                {
                    "metadata": {"duration": 1.0},
                    "mouthCues": [{"start": 0.0, "end": 1.0, "value": "Z"}],
                }
            )


if __name__ == "__main__":
    unittest.main()
