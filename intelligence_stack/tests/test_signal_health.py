from __future__ import annotations
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
from intelligence_stack.reach import collect


class SignalHealthTests(unittest.TestCase):
    def test_github_collector_uses_native_api_without_agent_reach_or_gh(self):
        release = {'name': 'A release', 'html_url': 'https://github.com/test/tool/releases/tag/1', 'tag_name': '1'}
        response = io.BytesIO(json.dumps([release]).encode())
        health = []
        with mock.patch.object(collect.urllib.request, 'urlopen', return_value=response), mock.patch.object(collect.shutil, 'which', return_value=None):
            records = collect.collect_github({'github_repositories': ['test/tool']}, 2, health)
        self.assertEqual(len(records), 1)
        self.assertEqual(health[0]['status'], 'success')
        self.assertEqual(records[0]['claim_status'], 'unverified')
        self.assertEqual(records[0]['rights_status'], 'reference_only')

    def test_failed_feed_records_its_failure_without_fabricating_signals(self):
        health = []
        with mock.patch.object(collect.urllib.request, 'urlopen', side_effect=urllib.error.URLError('offline')):
            records = collect.collect_rss({'rss_feeds': [{'name': 'test', 'url': 'https://example.com/rss'}]}, 2, health)
        self.assertEqual(records, [])
        self.assertEqual(health[0]['status'], 'failed')

    def test_namespaced_rss_items_are_not_silently_lost(self):
        feed = b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/"><item><title>Perception research</title><link>https://example.com/paper</link></item></rdf:RDF>'
        health = []
        with mock.patch.object(collect.urllib.request, 'urlopen', return_value=io.BytesIO(feed)):
            records = collect.collect_rss({'rss_feeds': [{'name': 'test', 'url': 'https://example.com/rss'}]}, 2, health)
        self.assertEqual(records[0]['url'], 'https://example.com/paper')
        self.assertEqual(health[0]['record_count'], 1)

    def test_optional_youtube_dependency_has_explicit_health(self):
        health = []
        with mock.patch.object(collect.shutil, 'which', return_value=None):
            self.assertEqual(collect.collect_youtube({}, 2, health), [])
        self.assertEqual(health[0]['status'], 'optional_tool_missing')

    def test_all_live_collectors_failing_persists_status_and_exits_nonzero(self):
        def failure(config, limit, diagnostics=None):
            collect.source_status(diagnostics, 'test', 'fixture', 'failed')
            return []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / 'config.json'
            config.write_text('{}')
            args = ['collect.py', '--live', '--config', str(config), '--out-dir', str(root / 'out')]
            with mock.patch.object(sys, 'argv', args), mock.patch.object(collect, 'doctor_report', return_value={'status': 'not_installed'}), mock.patch.object(collect, 'collect_github', side_effect=failure), mock.patch.object(collect, 'collect_rss', side_effect=failure), mock.patch.object(collect, 'collect_youtube', side_effect=failure), contextlib.redirect_stdout(io.StringIO()):
                code = collect.main()
            payload = json.loads((root / 'out/LATEST.json').read_text())
            self.assertEqual(code, 2)
            self.assertEqual(payload['status'], 'failed')
            self.assertEqual(payload['record_count'], 0)
            self.assertEqual(len(payload['source_health']), 3)

    def test_brief_preserves_source_link(self):
        record = collect.base_record(source='test', title='Research', url='https://example.com/research')
        brief = collect.brief_markdown([record], {'status': 'not_installed'})
        self.assertIn('https://example.com/research', brief)


if __name__ == '__main__':
    unittest.main()
