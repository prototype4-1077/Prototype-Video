import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import learn


class ConceptLearningTests(unittest.TestCase):
    def test_approval_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "outcomes.json")
            with mock.patch.object(learn, "CONCEPT_OUTCOMES", path):
                script = {"concept_id": "body_ownership", "slug": "where-you-end"}
                learn.record_concept_approval(script)
                learn.record_concept_approval(script)
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
            concept = data["concepts"]["body_ownership"]
            self.assertEqual(concept["approval_count"], 1)
            self.assertEqual(concept["approved_slugs"], ["where-you-end"])

    def test_audience_summary_is_recorded_once(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "outcomes.json")
            with mock.patch.object(learn, "CONCEPT_OUTCOMES", path):
                script = {"concept_id": "body_ownership", "slug": "where-you-end"}
                payload = {"video_id": "v", "watch_ratio": [1.0, 0.8, 0.6]}
                learn.record_concept_audience(script, payload, "review", [0], [2])
                learn.record_concept_audience(script, payload, "review", [0], [2])
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
            concept = data["concepts"]["body_ownership"]
            self.assertEqual(len(concept["audience_samples"]), 1)
            self.assertAlmostEqual(concept["mean_watch_ratio"], 0.8)


if __name__ == "__main__":
    unittest.main()
