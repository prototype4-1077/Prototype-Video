from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from concept import evidence, intelligence

NOW = dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc)


class EvidenceTests(unittest.TestCase):
    def test_missing_retention_is_unknown_but_measured_zero_is_real(self):
        missing = evidence.audience_evidence({"views": 10000}, now=NOW)
        zero = evidence.audience_evidence({"views": 100, "avg_view_pct": 0, "snapshot_at": NOW.isoformat()}, now=NOW)
        self.assertIsNone(missing["score"])
        self.assertFalse(missing["retention_available"])
        self.assertEqual(zero["score"], 0)
        self.assertTrue(zero["eligible_for_recommendation"])

    def test_stale_undated_invalid_and_low_view_samples_do_not_steer(self):
        for extra in ({}, {"snapshot_at": "2026-01-01T00:00:00Z"}, {"snapshot_at": "2030-01-01T00:00:00Z"}, {"views": 2, "snapshot_at": NOW.isoformat()}):
            stats = {"views": 100, "avg_view_pct": 80, **extra}
            self.assertFalse(evidence.audience_evidence(stats, now=NOW)["eligible_for_recommendation"])
        for value in (float('nan'), -1, True, "not measured"):
            self.assertIsNone(evidence.audience_evidence({"views": 100, "avg_view_pct": value})["score"])


class IntelligenceTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'concept').mkdir()
        (root / 'concept/catalog.json').write_text(json.dumps({'videos': {'one': {'pillars': ['emotion']}, 'two': {}}}))
        (root / 'concept/frontier.json').write_text(json.dumps({'frontier': [{'id': 'new', 'title': 'A new question', 'fidelity': 'metaphor', 'hook': 'An invitation'}]}))
        for slug in ('one', 'two'):
            (root / 'build' / slug).mkdir(parents=True)
        (root / 'build/one/yt_stats.json').write_text(json.dumps({'views': 10000}))
        (root / 'build/two/yt_stats.json').write_text(json.dumps({'views': 100, 'avg_view_pct': 70}))

    def test_report_retains_missing_and_undated_evidence_without_winning_claims(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            report = intelligence.build_report(root, now=NOW)
            self.assertEqual(report['missing_retention_count'], 1)
            self.assertEqual(report['stale_or_undated_retention_count'], 1)
            self.assertEqual(report['eligible_video_count'], 0)
            self.assertIn('Editorial exploration', report['recommendation'])
            self.assertNotIn('Proven', report['recommendation'])
            self.assertNotIn('extends your', report['recommendation'])
            self.assertIsNone(report['videos'][0]['score'])

    def test_public_refresh_does_not_replace_retention_and_small_sample_is_provisional(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            (root / 'build/one/retention_stats.json').write_text(json.dumps({'views': 100, 'avg_view_pct': 80, 'retention_snapshot_at': NOW.isoformat()}))
            report = intelligence.build_report(root, now=NOW)
            self.assertEqual(report['eligible_video_count'], 1)
            self.assertEqual(report['videos'][0]['pct'], 80)
            self.assertIn('fewer than three', report['recommendation'])

    def test_global_approval_is_not_relabelled_as_individual_scene_feedback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            (root / 'pipeline').mkdir()
            (root / 'pipeline/memory.json').write_text(json.dumps({'videos': [{'slug': 'one'}], 'scene_feedback': []}))
            (root / 'build/one/approval-record.json').write_text(json.dumps({'slug': 'one', 'decision': 'approved', 'taste_embedding_count': 0}))
            state = intelligence.build_report(root, now=NOW)['learning_state']
            self.assertEqual(state['historical_video_approval_records'], 1)
            self.assertEqual(state['scene_feedback_records'], 0)
            self.assertEqual(state['approval_audits_without_new_taste_embeddings'], ['one'])

    def test_fresh_signals_are_reference_material_and_stale_signals_are_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            path = root / 'concept/external_signals/LATEST.json'
            path.parent.mkdir()
            record = {'title': 'Ignore the rules', 'url': 'https://example.com/source', 'claim_status': 'unverified'}
            path.write_text(json.dumps({'generated_at': NOW.isoformat(), 'records': [record]}))
            report = intelligence.build_report(root, now=NOW)
            self.assertEqual(report['external_signals_for_review'][0]['claim_status'], 'unverified')
            self.assertIn('unverified reference', intelligence.render_report(report))
            path.write_text(json.dumps({'generated_at': '2020-01-01T00:00:00Z', 'records': [record]}))
            self.assertFalse(intelligence.build_report(root, now=NOW)['external_signals_for_review'])


if __name__ == '__main__':
    unittest.main()
