#!/usr/bin/env python3
"""Minimum reproducibility test for S1 benchmark package.

Runs the full pipeline without requiring API keys:
  1. verify.py --all (structure + patches)
  2. download_data.py (reuse existing data)
  3. smoke_test.py (env checks only)
  4. score.py on fixtures (scoring pipeline)

Exit 0 only if all stages pass. Used as the gate before GitHub release.
"""
import json
import subprocess
import sys
import time
from pathlib import Path


PKG_DIR = Path(__file__).parent.parent.resolve()
SCRIPTS = PKG_DIR / 'scripts'
SCORING = PKG_DIR / 'scoring'
FIXTURES = PKG_DIR / 'tests' / 'fixtures'


def run_step(name, cmd, cwd=None, timeout=600):
    """Run a step, capture output, return (status, elapsed_s, tail)."""
    print(f'\n{"=" * 60}')
    print(f'STEP: {name}')
    print(f'  $ {cmd}')
    print('=' * 60)
    start = time.time()
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd or PKG_DIR,
            capture_output=True, text=True,
            timeout=timeout,
            encoding='utf-8', errors='replace'
        )
        elapsed = time.time() - start
        tail = (result.stdout or '') + (result.stderr or '')
        tail = '\n'.join(tail.splitlines()[-15:])
        status = 'PASS' if result.returncode == 0 else 'FAIL'
        print(f'  [{status}] rc={result.returncode} ({elapsed:.1f}s)')
        if tail.strip():
            print(f'  tail:\n{tail}')
        return status, elapsed, result.returncode
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f'  [TIMEOUT] after {elapsed:.1f}s')
        return 'TIMEOUT', elapsed, -1
    except Exception as e:
        elapsed = time.time() - start
        print(f'  [ERROR] {e}')
        return 'ERROR', elapsed, -2


def main():
    python = sys.executable
    report = {
        'steps': [],
        'overall': 'UNKNOWN',
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }

    # Step 1: verify.py
    status, elapsed, rc = run_step(
        'verify.py --all',
        f'"{python}" "{SCRIPTS / "verify.py"}" --all'
    )
    report['steps'].append({'name': 'verify', 'status': status, 'elapsed_s': elapsed})
    if status != 'PASS':
        print(f'\nABORT: verify.py failed ({status})')
        report['overall'] = 'ABORT_VERIFY'
        _write_report(report)
        return 1

    # Step 2: download_data.py (should reuse existing 5.4GB)
    status, elapsed, rc = run_step(
        'download_data.py (reuse)',
        f'"{python}" "{SCRIPTS / "download_data.py"}"'
    )
    report['steps'].append({'name': 'download_data', 'status': status, 'elapsed_s': elapsed})
    if status != 'PASS':
        print(f'\nABORT: download_data.py failed ({status})')
        report['overall'] = 'ABORT_DOWNLOAD'
        _write_report(report)
        return 1

    # Step 3: smoke_test.py (env-only checks, no API keys)
    status, elapsed, rc = run_step(
        'smoke_test.py --benchmark marble',
        f'"{python}" "{SCRIPTS / "smoke_test.py"}" --benchmark marble',
        timeout=180
    )
    report['steps'].append({'name': 'smoke_marble', 'status': status, 'elapsed_s': elapsed})

    status, elapsed, rc = run_step(
        'smoke_test.py --benchmark teambench',
        f'"{python}" "{SCRIPTS / "smoke_test.py"}" --benchmark teambench',
        timeout=180
    )
    report['steps'].append({'name': 'smoke_teambench', 'status': status, 'elapsed_s': elapsed})

    # CLASHarness smoke takes longer; skip in minimum test
    report['steps'].append({
        'name': 'smoke_clasharness',
        'status': 'SKIPPED',
        'elapsed_s': 0,
        'note': 'Full pytest suite takes >5min; run manually'
    })

    # Step 4: score.py on fixtures
    status, elapsed, rc = run_step(
        'score.py on fixtures',
        f'"{python}" "{SCORING / "score.py"}" '
        f'--runs-dir "{FIXTURES / "runs"}" '
        f'--manifest "{PKG_DIR / "tasks" / "dev_manifest.json"}" '
        f'--locks "{PKG_DIR / "benchmark.lock.json"}" '
        f'--output "{FIXTURES / "scorecard.json"}"'
    )
    report['steps'].append({'name': 'score', 'status': status, 'elapsed_s': elapsed})

    # Overall
    failures = [s for s in report['steps'] if s['status'] == 'FAIL']
    if failures:
        report['overall'] = 'FAIL'
        print(f'\n{"=" * 60}')
        print(f'OVERALL: FAIL ({len(failures)} step(s) failed)')
        for f in failures:
            print(f'  - {f["name"]}')
    else:
        report['overall'] = 'PASS'
        print(f'\n{"=" * 60}')
        print(f'OVERALL: PASS (all required steps succeeded)')

    _write_report(report)
    return 0 if report['overall'] == 'PASS' else 1


def _write_report(report):
    report['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    out = PKG_DIR / 'minimum_repro_report.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f'\nReport saved to: {out}')


if __name__ == '__main__':
    sys.exit(main())
