"""Read-only provider credential probe. Never synthesize speech or store account data.

Endpoint: https://elevenlabs.io/docs/api-reference/user/subscription/get
A successful read verifies authentication, not TTS permission or output quality.
Restricted keys may refuse this read while still permitting synthesis.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import urllib.error
import urllib.request


def probe() -> dict:
    key = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    result = {'schema_version': 1, 'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'provider': 'ElevenLabs', 'synthesis_tested': False,
              'measurement_boundary': 'Read-only authentication probe; TTS permission, available generation credits, and media quality are not established.'}
    if not key:
        return {**result, 'status': 'not_configured'}
    request = urllib.request.Request('https://api.elevenlabs.io/v1/user/subscription', headers={'xi-api-key': key})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            # Discard billing, identity, and usage fields; only the response shape is checked.
            payload = json.load(response)
        if not isinstance(payload, dict) or 'status' not in payload:
            return {**result, 'status': 'unexpected_response'}
        return {**result, 'status': 'read_access_verified'}
    except urllib.error.HTTPError as exc:
        state = 'credential_invalid' if exc.code == 401 else ('read_probe_not_permitted' if exc.code == 403 else 'provider_unavailable')
        return {**result, 'status': state, 'http_status': exc.code}
    except (OSError, ValueError):
        return {**result, 'status': 'provider_unreachable'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('provider_health.json'))
    args = parser.parse_args()
    result = probe()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
