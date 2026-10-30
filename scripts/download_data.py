#!/usr/bin/env python3
"""Download and verify benchmark data.

Reuses existing data when present and hash-verified. Only downloads missing
or corrupted data. CLASHarness v8 corpus is ~5.4 GB; do not re-download
without cause.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def run_cmd(cmd, cwd=None, check=True):
    print(f'  $ {cmd}')
    result = subprocess.run(
        cmd, shell=True, cwd=cwd, check=check,
        encoding='utf-8', errors='replace'
    )
    return result.returncode


def verify_marble_data(base_path):
    """MARBLE data ships with the git repo (scripts/, data/)."""
    repo = base_path / 'MARBLE'
    required = [
        repo / 'data',
        repo / 'scripts',
        repo / 'scripts' / 'werewolf' / 'run_simulation.sh',
        repo / 'poetry.lock',
        repo / 'pyproject.toml',
    ]
    missing = [p for p in required if not p.exists()]
    if missing:
        return 'FAIL', f'Missing: {[str(p.relative_to(base_path)) for p in missing]}'
    return 'PASS', 'MARBLE data present (shipped with repo)'


def verify_teambench_data(base_path):
    """TeamBench task manifest ships with the git repo."""
    manifest = base_path / 'TeamBench' / 'leaderboard' / 'data' / 'leaderboard_90_tasks.json'
    if not manifest.exists():
        return 'FAIL', f'Missing: {manifest.relative_to(base_path)}'
    try:
        with open(manifest, encoding='utf-8') as f:
            data = json.load(f)
        tasks = data.get('tasks', [])
        if len(tasks) != 90:
            return 'FAIL', f'Expected 90 tasks, got {len(tasks)}'
        return 'PASS', f'TeamBench 90 tasks verified'
    except Exception as e:
        return 'FAIL', f'Invalid manifest: {e}'


def verify_clasharness_data(base_path, expected_hash=None):
    """CLASHarness v8 data must be downloaded from HuggingFace (~5.4 GB).

    If data already exists and hash matches (or no hash given), skip download.
    """
    data_root = base_path / 'CLASHarness' / 'data' / 'multiagent_conflict_data_v8_Gemini_3_6_flash'
    total_file = data_root / 'datasets' / 'total.txt'
    tasks_dir = data_root / 'tasks'

    # Check if data already present
    if total_file.exists() and tasks_dir.exists():
        try:
            with open(total_file, encoding='utf-8') as f:
                episodes = [ln.strip() for ln in f if ln.strip()]
            task_count = len(list(tasks_dir.iterdir()))
        except Exception as e:
            return 'FAIL', f'Cannot read existing data: {e}'

        if len(episodes) == 600 and task_count == 600:
            if expected_hash:
                actual = sha256_file(total_file)
                if actual != expected_hash:
                    return 'FAIL', f'Hash mismatch: {actual[:12]} != {expected_hash[:12]}'
            return 'PASS', f'CLASHarness 600/600 already present (reuse, no download)'
        else:
            return 'FAIL', f'Incomplete data: {len(episodes)}/600 episodes, {task_count}/600 tasks'

    # Need to download
    return 'MISSING', f'CLASHarness data not present; download required'


def download_clasharness(base_path, components=None):
    """Download CLASHarness v8 data from HuggingFace.

    Uses the official tools/download_data.py script from the CLASHarness repo.
    """
    if components is None:
        components = ['tasks-v8', 'splits-v8']

    repo = base_path / 'CLASHarness'
    downloader = repo / 'tools' / 'download_data.py'
    if not downloader.exists():
        return 'FAIL', f'Downloader not found: {downloader.relative_to(base_path)}'

    # Activate conda env if possible
    conda_cmd = f'conda run -n s1-clash python "{downloader}"'
    plain_cmd = f'python "{downloader}"'

    components_arg = ' '.join(f'--component {c}' for c in components)
    cmd = f'{conda_cmd} --repo yuxianglai117/CLASHarness {components_arg}'

    print(f'Downloading CLASHarness v8 data (~5.4 GB)...')
    rc = run_cmd(cmd, cwd=repo, check=False)
    if rc != 0:
        print(f'Conda run failed (rc={rc}); retrying with plain python')
        cmd = f'{plain_cmd} --repo yuxianglai117/CLASHarness {components_arg}'
        rc = run_cmd(cmd, cwd=repo, check=False)
        if rc != 0:
            return 'FAIL', f'Download failed (rc={rc})'

    # Verify checksums
    checker = repo / 'tools' / 'checksum_corpus.py'
    if checker.exists():
        print('Verifying corpus checksums...')
        cmd = f'conda run -n s1-clash python "{checker}" --root data --verify CHECKSUMS.txt'
        rc = run_cmd(cmd, cwd=repo, check=False)
        if rc != 0:
            cmd = f'python "{checker}" --root data --verify CHECKSUMS.txt'
            rc = run_cmd(cmd, cwd=repo, check=False)
            if rc != 0:
                return 'FAIL', f'Checksum verification failed'

    return 'PASS', 'CLASHarness v8 data downloaded and verified'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='E:/CatalystPI/s1-benchmarks',
                       help='Base directory containing benchmark repos')
    parser.add_argument('--benchmark', choices=['marble', 'teambench', 'clasharness', 'all'],
                       default='all', help='Which benchmark data to verify/download')
    parser.add_argument('--force-download', action='store_true',
                       help='Re-download even if data is present (NOT recommended for CLASHarness)')
    parser.add_argument('--output', help='Write JSON report to this path')
    args = parser.parse_args()

    base = Path(args.base).resolve()
    if not base.exists():
        print(f'ERROR: base path not found: {base}')
        sys.exit(1)

    lock_file = Path(__file__).parent.parent / 'benchmark.lock.json'
    if lock_file.exists():
        with open(lock_file, encoding='utf-8') as f:
            lock = json.load(f)
    else:
        lock = {}

    benchmarks = ['marble', 'teambench', 'clasharness'] if args.benchmark == 'all' else [args.benchmark]

    report = {'base': str(base), 'benchmarks': {}}
    overall_ok = True

    for bench in benchmarks:
        print(f'\n=== {bench.upper()} ===')
        if bench == 'marble':
            status, msg = verify_marble_data(base)
            report['benchmarks']['marble'] = {'status': status, 'message': msg}
        elif bench == 'teambench':
            status, msg = verify_teambench_data(base)
            report['benchmarks']['teambench'] = {'status': status, 'message': msg}
        elif bench == 'clasharness':
            expected = None
            clash_lock = lock.get('CLASHarness', {})
            expected = clash_lock.get('data', {}).get('total_txt_sha256')

            if args.force_download:
                print('WARNING: --force-download set; will re-download 5.4 GB if needed')
                status, msg = download_clasharness(base)
            else:
                status, msg = verify_clasharness_data(base, expected)
                if status == 'MISSING':
                    status, msg = download_clasharness(base)

            report['benchmarks']['clasharness'] = {'status': status, 'message': msg}

        print(f'  [{report["benchmarks"][bench]["status"]}] {report["benchmarks"][bench]["message"]}')
        if report['benchmarks'][bench]['status'] != 'PASS':
            overall_ok = False

    print('\n' + '=' * 60)
    if overall_ok:
        print('[OK] All benchmark data verified')
    else:
        print('[FAIL] Some data missing or invalid')

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f'Report saved to: {args.output}')

    sys.exit(0 if overall_ok else 1)


if __name__ == '__main__':
    main()
