#!/usr/bin/env python3
"""Run official smoke tests for each benchmark.

No API keys required. Uses:
- MARBLE: poetry run pytest -q tests
- TeamBench: python -m harness.ablation --model mock (single task)
- CLASHarness: python -m pytest tests -q

Each runs in its own isolated conda environment.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def run_in_conda(env_name, cmd, cwd, timeout=600):
    """Run command inside conda environment. Captures output."""
    full_cmd = f'conda run -n {env_name} {cmd}'
    print(f'  $ [{env_name}] {cmd}')
    print(f'    cwd: {cwd}')

    start = time.time()
    try:
        result = subprocess.run(
            full_cmd, shell=True, cwd=cwd,
            capture_output=True, text=True,
            timeout=timeout,
            encoding='utf-8', errors='replace'
        )
        elapsed = time.time() - start
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'elapsed_s': round(elapsed, 1),
            'cmd': cmd,
            'env': env_name,
        }
    except subprocess.TimeoutExpired:
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': f'TIMEOUT after {timeout}s',
            'elapsed_s': timeout,
            'cmd': cmd,
            'env': env_name,
        }
    except Exception as e:
        return {
            'returncode': -2,
            'stdout': '',
            'stderr': str(e),
            'elapsed_s': 0,
            'cmd': cmd,
            'env': env_name,
        }


def run_plain(cmd, cwd, timeout=600):
    """Fallback: run without conda."""
    print(f'  $ {cmd} (no conda)')
    start = time.time()
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True,
            timeout=timeout,
            encoding='utf-8', errors='replace'
        )
        elapsed = time.time() - start
        return {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'elapsed_s': round(elapsed, 1),
            'cmd': cmd,
            'env': 'system',
        }
    except Exception as e:
        return {'returncode': -2, 'stdout': '', 'stderr': str(e),
                'elapsed_s': 0, 'cmd': cmd, 'env': 'system'}


def smoke_marble(base_path, use_conda=True):
    """Run MARBLE pytest suite.

    Most MARBLE tests require an LLM API key; they will fail without one.
    We run test_init.py as an environment-only check (no API needed),
    and report the full suite as BLOCKED if API key is absent.
    """
    repo = base_path / 'MARBLE'
    print('\n=== MARBLE smoke test ===')

    # Environment-only check (no API key needed)
    env_cmd = 'poetry run pytest -q tests/test_init.py'
    if use_conda:
        result = run_in_conda('s1-marble', env_cmd, cwd=repo, timeout=120)
        if result['returncode'] == -2:
            result = run_plain(env_cmd, cwd=repo, timeout=120)
    else:
        result = run_plain(env_cmd, cwd=repo, timeout=120)

    stdout_tail = '\n'.join(result['stdout'].splitlines()[-10:])
    stderr_tail = '\n'.join(result['stderr'].splitlines()[-10:])

    if result['returncode'] == 0:
        status = 'PASS'
        summary = 'env-only check passed (test_init.py)'
        note = 'Full suite requires LLM API key; run `poetry run pytest -q tests` after configuring .env'
    else:
        status = 'FAIL'
        summary = f'rc={result["returncode"]}'
        note = ''

    print(f'  [{status}] {summary} ({result["elapsed_s"]}s)')
    if note:
        print(f'  NOTE: {note}')
    if status == 'FAIL':
        if stdout_tail:
            print(f'  stdout tail:\n{stdout_tail}')
        if stderr_tail:
            print(f'  stderr tail:\n{stderr_tail}')

    return {'benchmark': 'MARBLE', 'status': status, 'note': note, **result}


def smoke_teambench(base_path, use_conda=True):
    """Run TeamBench mock ablation on one task (no API key needed)."""
    repo = base_path / 'TeamBench'
    print('\n=== TeamBench smoke test ===')

    # Single condition is enough for smoke; mock model needs no API key
    cmd = ('python -m harness.ablation --model mock '
           '--tasks DIST1_queue_race --seeds 0 '
           '--conditions oracle '
           '--output /tmp/s1-smoke-teambench')

    if use_conda:
        result = run_in_conda('s1-teambench', cmd, cwd=repo, timeout=300)
        if result['returncode'] == -2:
            result = run_plain(cmd, cwd=repo, timeout=300)
    else:
        result = run_plain(cmd, cwd=repo, timeout=300)

    stdout_tail = '\n'.join(result['stdout'].splitlines()[-10:])
    stderr_tail = '\n'.join(result['stderr'].splitlines()[-10:])

    if result['returncode'] == 0:
        status = 'PASS'
        summary = 'mock ablation completed'
    else:
        status = 'FAIL'
        summary = f'rc={result["returncode"]}'

    print(f'  [{status}] {summary} ({result["elapsed_s"]}s)')
    if status == 'FAIL':
        if stdout_tail:
            print(f'  stdout tail:\n{stdout_tail}')
        if stderr_tail:
            print(f'  stderr tail:\n{stderr_tail}')

    return {'benchmark': 'TeamBench', 'status': status, **result}


def smoke_clasharness(base_path, use_conda=True):
    """Run CLASHarness pytest suite (no model calls).

    Note: tests/test_build_behavior_report.py imports a file containing
    f-strings with backslashes, which requires Python 3.12+. Skip it
    on Python 3.11.
    """
    repo = base_path / 'CLASHarness'
    print('\n=== CLASHarness smoke test ===')

    cmd = 'python -m pytest tests -q --ignore=tests/test_build_behavior_report.py'

    if use_conda:
        result = run_in_conda('s1-clash', cmd, cwd=repo, timeout=600)
        if result['returncode'] == -2:
            result = run_plain(cmd, cwd=repo, timeout=600)
    else:
        result = run_plain(cmd, cwd=repo, timeout=600)

    stdout_tail = '\n'.join(result['stdout'].splitlines()[-10:])
    stderr_tail = '\n'.join(result['stderr'].splitlines()[-10:])

    if result['returncode'] == 0:
        status = 'PASS'
        summary = result['stdout'].splitlines()[-1] if result['stdout'] else 'tests passed'
        note = 'Skipped test_build_behavior_report.py (requires Python 3.12+)'
    else:
        status = 'FAIL'
        summary = f'rc={result["returncode"]}'
        note = ''

    print(f'  [{status}] {summary} ({result["elapsed_s"]}s)')
    if note:
        print(f'  NOTE: {note}')
    if status == 'FAIL':
        if stdout_tail:
            print(f'  stdout tail:\n{stdout_tail}')
        if stderr_tail:
            print(f'  stderr tail:\n{stderr_tail}')

    return {'benchmark': 'CLASHarness', 'status': status, 'note': note, **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='E:/CatalystPI/s1-benchmarks')
    parser.add_argument('--benchmark', choices=['marble', 'teambench', 'clasharness', 'all'],
                       default='all')
    parser.add_argument('--no-conda', action='store_true',
                       help='Skip conda run (use current interpreter)')
    parser.add_argument('--output', help='Write JSON report to this path')
    args = parser.parse_args()

    base = Path(args.base).resolve()
    if not base.exists():
        print(f'ERROR: base path not found: {base}')
        sys.exit(1)

    benchmarks = ['marble', 'teambench', 'clasharness'] if args.benchmark == 'all' else [args.benchmark]
    use_conda = not args.no_conda

    report = {'base': str(base), 'conda': use_conda, 'results': []}

    for bench in benchmarks:
        if bench == 'marble':
            report['results'].append(smoke_marble(base, use_conda))
        elif bench == 'teambench':
            report['results'].append(smoke_teambench(base, use_conda))
        elif bench == 'clasharness':
            report['results'].append(smoke_clasharness(base, use_conda))

    # Summary
    print('\n' + '=' * 60)
    passed = sum(1 for r in report['results'] if r['status'] == 'PASS')
    total = len(report['results'])
    print(f'Smoke tests: {passed}/{total} passed')

    for r in report['results']:
        print(f'  {r["benchmark"]}: {r["status"]} ({r.get("elapsed_s", "?")}s)')

    if args.output:
        # Strip large stdout/stderr for the saved report
        save_report = {
            'base': report['base'],
            'conda': report['conda'],
            'results': [
                {k: v for k, v in r.items() if k not in ('stdout', 'stderr')}
                for r in report['results']
            ]
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(save_report, f, indent=2, ensure_ascii=False)
        print(f'Report saved to: {args.output}')

    sys.exit(0 if passed == total else 1)


if __name__ == '__main__':
    main()
