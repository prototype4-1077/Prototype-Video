from __future__ import annotations
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analytics_sync
import provider_health
import yt_stats_refresh


class PublicCollectionTests(unittest.TestCase):
    def run_refresh(self, root, items):
        catalog = {'one': {'video_id': 'a'}, 'two': {'video_id': 'b'}}
        with mock.patch.object(yt_stats_refresh, 'receipts', return_value=catalog), mock.patch.object(yt_stats_refresh, 'STATUS', root / 'status.json'), mock.patch.object(yt_stats_refresh, 'authorization', return_value=({}, {}, 'test')), mock.patch.object(yt_stats_refresh, 'fetch', return_value=items):
            return yt_stats_refresh.refresh(root)

    def test_zero_and_partial_updates_cannot_report_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(self.run_refresh(root, [])['status'], 'no_updates')
            result = self.run_refresh(root, [{'id': 'a', 'statistics': {'viewCount': '20'}}])
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['updated_count'], 1)
            self.assertEqual(result['missing_count'], 1)

    def test_public_snapshot_preserves_legacy_retention_without_inventing_its_date(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build = root / 'build/one'
            build.mkdir(parents=True)
            (build / 'yt_stats.json').write_text(json.dumps({'views': 10, 'avg_view_pct': 77}))
            self.run_refresh(root, [{'id': 'a', 'statistics': {'viewCount': '100'}}])
            public = json.loads((build / 'yt_stats.json').read_text())
            retention = json.loads((build / 'retention_stats.json').read_text())
            self.assertNotIn('avg_view_pct', public)
            self.assertEqual(retention['avg_view_pct'], 77)
            self.assertIsNone(retention['retention_snapshot_at'])

    def test_empty_catalog_does_not_request_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.object(yt_stats_refresh, 'receipts', return_value={}), mock.patch.object(yt_stats_refresh, 'STATUS', root / 'status.json'), mock.patch.object(yt_stats_refresh, 'authorization') as auth:
                result = yt_stats_refresh.refresh(root)
            self.assertEqual(result['status'], 'no_data')
            auth.assert_not_called()


class RetentionCollectionTests(unittest.TestCase):
    def test_disabled_oauth_persists_failure_and_does_not_apply_learning(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'published_videos.json').write_text('{"one":{"youtube_id":"a"}}')
            error = urllib.error.HTTPError('https://oauth2.googleapis.com/token', 401, 'Unauthorized', {}, io.BytesIO(b'{"error":"disabled_client"}'))
            with mock.patch.object(analytics_sync, 'HERE', str(root)), mock.patch.object(analytics_sync, 'access_token', side_effect=error), mock.patch.object(analytics_sync.learn, 'audience') as learn, mock.patch('builtins.print'):
                code = analytics_sync.main()
            status = json.loads((root / 'analytics_status.json').read_text())
            self.assertEqual(code, 2)
            self.assertEqual(status['status'], 'authorization_failed')
            self.assertEqual(status['errors'][0]['http_status'], 401)
            learn.assert_not_called()
            self.assertFalse(list(root.glob('**/retention_stats.json')))


class ProviderHealthTests(unittest.TestCase):
    def test_probe_verifies_access_without_retaining_account_data(self):
        payload = {"status": "active", "character_count": 1234, "tier": "private", "open_invoices": []}
        with mock.patch.dict('os.environ', {'ELEVENLABS_API_KEY': 'fixture-secret'}), mock.patch.object(provider_health.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
            report = provider_health.probe()
        self.assertEqual(report['status'], 'read_access_verified')
        self.assertFalse(report['synthesis_tested'])
        for forbidden in ('fixture-secret', '1234', 'private', 'open_invoices'):
            self.assertNotIn(forbidden, json.dumps(report))

    def test_restricted_read_scope_is_not_misreported_as_bad_tts_credentials(self):
        error = urllib.error.HTTPError('https://example.com', 403, 'Forbidden', {}, None)
        with mock.patch.dict('os.environ', {'ELEVENLABS_API_KEY': 'fixture-secret'}), mock.patch.object(provider_health.urllib.request, 'urlopen', side_effect=error):
            report = provider_health.probe()
        self.assertEqual(report['status'], 'read_probe_not_permitted')


if __name__ == '__main__':
    unittest.main()
