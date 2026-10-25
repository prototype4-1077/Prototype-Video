"""Persist derived diagnostic reports with bounded, non-forced Git retries.

Only the explicitly supplied generated files are committed. A rebase can resolve
report/report conflicts in favor of this observation, then regenerates reports
against the latest source evidence before trying a fast-forward push again.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys
from typing import Callable


def git(root, *args, check=True):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'git failed')
    return result


def commit_if_changed(root, files, message):
    if files:
        git(root, 'add', '--', *files)
    if git(root, 'diff', '--cached', '--quiet', check=False).returncode:
        git(root, 'commit', '-m', message)
        return True
    return False


def persist(root: Path, files: list[str], *, regenerate: Callable[[], None],
            message='diagnostic: refresh calibrated evidence and actions', attempts=5):
    if int(git(root, 'rev-list', '--count', 'origin/main..HEAD').stdout.strip() or 0):
        raise RuntimeError('refusing to publish pre-existing local commits while persisting generated reports')
    files = sorted(set(files))
    allowed = set(files)
    staged = set(git(root, 'diff', '--cached', '--name-only').stdout.splitlines())
    dirty = set(git(root, 'diff', '--name-only').stdout.splitlines())
    if (staged | dirty) - allowed:
        raise RuntimeError('refusing to include or discard unrelated work while persisting generated reports')
    if not commit_if_changed(root, files, message):
        return {'pushed': False, 'reason': 'unchanged'}
    for attempt in range(1, attempts + 1):
        result = git(root, 'push', 'origin', 'HEAD:main', check=False)
        if result.returncode == 0:
            return {'pushed': True, 'attempts': attempt}
        rebase = git(root, 'pull', '--rebase', '--strategy-option=theirs', 'origin', 'main', check=False)
        if rebase.returncode:
            git(root, 'rebase', '--abort', check=False)
            raise RuntimeError('report rebase failed; evidence retained locally; no force push attempted')
        regenerate()
        commit_if_changed(root, files, message)
    raise RuntimeError('unable to persist diagnostic after bounded retries; no force push attempted')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    files = [name for name in (
        'pipeline/provider_health.json', 'concept/INTELLIGENCE_REPORT.json',
        'concept/INTELLIGENCE_REPORT.md', 'pipeline/system_diagnostics/LATEST.json',
        'pipeline/system_diagnostics/LATEST.md', 'pipeline/feedback_rule_candidates.json',
        'pipeline/stock_supply_report.json',
    ) if (root / name).is_file()]
    files += [str(path.relative_to(root)) for path in (root / 'build').glob('*/telemetry-summary.json')]
    def regenerate():
        for script in ('pipeline/backfill_observability.py', 'pipeline/feedback_rule_candidates.py', 'pipeline/stock_supply_analysis.py'):
            subprocess.run([sys.executable, script], cwd=root, check=True)
        subprocess.run([sys.executable, 'concept/intelligence.py', '--json-out', 'concept/INTELLIGENCE_REPORT.json', '--markdown-out', 'concept/INTELLIGENCE_REPORT.md'], cwd=root, check=True)
        subprocess.run([sys.executable, 'pipeline/system_diagnostic_policy.py'], cwd=root, check=True)
    print(persist(root, files, regenerate=regenerate))


if __name__ == '__main__':
    main()
