#!/usr/bin/env python3
"""S1 Benchmark Verification Script

Verifies installation integrity:
- Git commits match benchmark.lock.json
- Data file SHA256 match checksums.sha256
- Task manifests are valid
- Environment dependencies installed
- Patches applied correctly

Usage:
    python scripts/verify.py --all
    python scripts/verify.py --benchmark marble
    python scripts/verify.py --benchmark teambench
    python scripts/verify.py --benchmark clasharness

Output:
    JSON report with PASS/FAIL/BLOCKED status for each check
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def sha256_file(filepath):
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        return None


def run_cmd(cmd, cwd=None):
    """Run shell command and return result."""
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        encoding='utf-8',
        errors='replace'
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def verify_git_commit(benchmark_name, repo_path, expected_commit):
    """Verify Git commit matches expected."""
    if not repo_path.exists():
        return 'FAIL', f'Repository not found: {repo_path}'
    
    returncode, stdout, stderr = run_cmd('git rev-parse HEAD', cwd=repo_path)
    if returncode != 0:
        return 'FAIL', f'Cannot get Git HEAD: {stderr}'
    
    actual_commit = stdout
    if actual_commit == expected_commit:
        return 'PASS', f'Commit matches: {actual_commit[:12]}'
    else:
        return 'FAIL', f'Commit mismatch: {actual_commit[:12]} != {expected_commit[:12]}'


def verify_data_hash(filepath, expected_hash):
    """Verify file SHA256 matches expected."""
    if not filepath.exists():
        return 'FAIL', f'File not found: {filepath}'
    
    actual_hash = sha256_file(filepath)
    if actual_hash is None:
        return 'FAIL', f'Cannot read file: {filepath}'
    
    if actual_hash == expected_hash:
        return 'PASS', f'Hash matches: {actual_hash[:12]}'
    else:
        return 'FAIL', f'Hash mismatch: {actual_hash[:12]} != {expected_hash[:12]}'


def verify_conda_env(env_name):
    """Verify conda environment exists."""
    returncode, stdout, stderr = run_cmd(f'conda env list')
    if returncode != 0:
        return 'BLOCKED', 'Cannot query conda environments'
    
    if env_name in stdout:
        return 'PASS', f'Environment exists: {env_name}'
    else:
        return 'FAIL', f'Environment not found: {env_name}'


def verify_marble(base_path, lock_config):
    """Verify MARBLE installation."""
    results = {}
    repo_path = base_path / 'MARBLE'
    
    # Git commit
    status, msg = verify_git_commit('MARBLE', repo_path, lock_config['git_commit'])
    results['git_commit'] = {'status': status, 'message': msg}
    
    # Conda environment
    status, msg = verify_conda_env(lock_config['environment']['conda_environment'])
    results['conda_env'] = {'status': status, 'message': msg}
    
    # Poetry installation
    poetry_lock = repo_path / 'poetry.lock'
    if poetry_lock.exists():
        results['poetry_lock'] = {'status': 'PASS', 'message': 'poetry.lock exists'}
    else:
        results['poetry_lock'] = {'status': 'FAIL', 'message': 'poetry.lock missing'}
    
    # Known issue: SyntaxError in evaluator.py — check if patched
    evaluator_file = repo_path / 'marble' / 'evaluator' / 'evaluator.py'
    if evaluator_file.exists():
        try:
            import ast
            with open(evaluator_file, 'r', encoding='utf-8') as f:
                ast.parse(f.read())
            results['known_issue_evaluator'] = {
                'status': 'PASS',
                'message': 'evaluator.py syntax valid (patch applied)'
            }
        except SyntaxError as e:
            results['known_issue_evaluator'] = {
                'status': 'BLOCKED',
                'message': f'SyntaxError at line {e.lineno} requires patch'
            }
    
    return results


def verify_teambench(base_path, lock_config):
    """Verify TeamBench installation."""
    results = {}
    repo_path = base_path / 'TeamBench'
    
    # Git commit
    status, msg = verify_git_commit('TeamBench', repo_path, lock_config['git_commit'])
    results['git_commit'] = {'status': status, 'message': msg}
    
    # Conda environment
    status, msg = verify_conda_env(lock_config['environment']['conda_environment'])
    results['conda_env'] = {'status': status, 'message': msg}
    
    # Task manifest
    task_file = repo_path / 'leaderboard' / 'data' / 'leaderboard_90_tasks.json'
    status, msg = verify_data_hash(task_file, lock_config['data']['task_sha256'])
    results['task_manifest'] = {'status': status, 'message': msg}
    
    # Task count
    if task_file.exists():
        try:
            with open(task_file, encoding='utf-8') as f:
                tasks = json.load(f)['tasks']
            if len(tasks) == 90:
                results['task_count'] = {'status': 'PASS', 'message': f'90 tasks verified'}
            else:
                results['task_count'] = {'status': 'FAIL', 'message': f'Expected 90 tasks, got {len(tasks)}'}
        except Exception as e:
            results['task_count'] = {'status': 'FAIL', 'message': str(e)}
    
    # Docker images
    status, msg, _ = run_cmd('docker images --format "{{.Repository}}:{{.Tag}}"')
    if 'teambench-executor' in msg:
        results['docker_images'] = {'status': 'PASS', 'message': 'Docker images built'}
    else:
        results['docker_images'] = {'status': 'FAIL', 'message': 'Docker images not found'}
    
    return results


def verify_clasharness(base_path, lock_config):
    """Verify CLASHarness installation."""
    results = {}
    repo_path = base_path / 'CLASHarness'
    
    # Git commit
    status, msg = verify_git_commit('CLASHarness', repo_path, lock_config['git_commit'])
    results['git_commit'] = {'status': status, 'message': msg}
    
    # Conda environment
    status, msg = verify_conda_env(lock_config['environment']['conda_environment'])
    results['conda_env'] = {'status': status, 'message': msg}
    
    # Episode manifest
    episode_file = repo_path / 'data' / 'multiagent_conflict_data_v8_Gemini_3_6_flash' / 'datasets' / 'total.txt'
    status, msg = verify_data_hash(episode_file, lock_config['data']['episode_sha256'])
    results['episode_manifest'] = {'status': status, 'message': msg}
    
    # Episode count
    if episode_file.exists():
        try:
            with open(episode_file, encoding='utf-8') as f:
                episodes = [line.strip() for line in f if line.strip()]
            if len(episodes) == 600:
                results['episode_count'] = {'status': 'PASS', 'message': f'600 episodes verified'}
            else:
                results['episode_count'] = {'status': 'FAIL', 'message': f'Expected 600 episodes, got {len(episodes)}'}
        except Exception as e:
            results['episode_count'] = {'status': 'FAIL', 'message': str(e)}
    
    # Task directories
    tasks_dir = repo_path / 'data' / 'multiagent_conflict_data_v8_Gemini_3_6_flash' / 'tasks'
    if tasks_dir.exists():
        task_count = len(list(tasks_dir.iterdir()))
        if task_count == 600:
            results['task_directories'] = {'status': 'PASS', 'message': f'600/600 task directories'}
        else:
            results['task_directories'] = {'status': 'FAIL', 'message': f'Expected 600, got {task_count}'}
    
    # Known issues — check if patched
    pyproject_file = repo_path / 'pyproject.toml'
    if pyproject_file.exists():
        import re as _re
        with open(pyproject_file, 'r', encoding='utf-8') as f:
            content = f.read()
        project_m = _re.search(r'\[project\](.*?)(?=\n\[|\Z)', content, _re.DOTALL)
        urls_m = _re.search(r'\[project\.urls\](.*?)(?=\n\[|\Z)', content, _re.DOTALL)
        if (project_m and 'dependencies = [' in project_m.group(1)
                and not (urls_m and 'dependencies = [' in urls_m.group(1))):
            results['known_issue_pyproject'] = {
                'status': 'PASS',
                'message': 'pyproject.toml dependencies under [project] (patch applied)'
            }
        else:
            results['known_issue_pyproject'] = {
                'status': 'BLOCKED',
                'message': 'pyproject.toml misconfiguration requires patch'
            }
    else:
        results['known_issue_pyproject'] = {
            'status': 'FAIL',
            'message': 'pyproject.toml not found'
        }

    report_file = repo_path / 'docs' / 'analysis' / 'analysis_v8' / 'tools' / 'build_behavior_report.py'
    if report_file.exists():
        with open(report_file, 'r', encoding='utf-8') as f:
            head = f.read(500)
        if '# S1 PATCH' in head:
            results['known_issue_python_version'] = {
                'status': 'PASS',
                'message': 'build_behavior_report.py warning marker present (patch applied)'
            }
        else:
            results['known_issue_python_version'] = {
                'status': 'BLOCKED',
                'message': 'build_behavior_report.py requires Python >=3.12 or patch'
            }
    else:
        results['known_issue_python_version'] = {
            'status': 'FAIL',
            'message': 'build_behavior_report.py not found'
        }
    
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='Verify all benchmarks')
    parser.add_argument('--benchmark', choices=['marble', 'teambench', 'clasharness'],
                       help='Verify specific benchmark')
    parser.add_argument('--output', help='Output JSON report file')
    args = parser.parse_args()
    
    if not args.all and not args.benchmark:
        parser.print_help()
        sys.exit(1)
    
    # Load configuration
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    lock_file = repo_root / 'benchmark.lock.json'
    
    if not lock_file.exists():
        print(f'ERROR: {lock_file} not found')
        sys.exit(1)
    
    with open(lock_file, encoding='utf-8') as f:
        lock_config = json.load(f)
    
    # Determine base path for benchmarks
    # Try common locations
    possible_bases = [
        Path('E:/CatalystPI/s1-benchmarks'),
        Path.home() / 's1-benchmarks',
        Path.cwd() / 's1-benchmarks',
    ]
    
    base_path = None
    for p in possible_bases:
        if p.exists() and (p / 'MARBLE').exists():
            base_path = p
            break
    
    if base_path is None:
        print('ERROR: Cannot find s1-benchmarks directory')
        print('Please run setup.py first or specify --base-path')
        sys.exit(1)
    
    print(f'Verifying benchmarks in: {base_path}')
    print('='*60)
    
    # Verify benchmarks
    report = {
        'timestamp': subprocess.run(['date', '/T'], capture_output=True, text=True).stdout.strip(),
        'base_path': str(base_path),
        'benchmarks': {}
    }
    
    benchmarks_to_verify = ['marble', 'teambench', 'clasharness'] if args.all else [args.benchmark]
    
    for bench in benchmarks_to_verify:
        print(f'\nVerifying {bench.upper()}...')
        
        if bench == 'marble':
            results = verify_marble(base_path, lock_config['benchmarks']['MARBLE'])
        elif bench == 'teambench':
            results = verify_teambench(base_path, lock_config['benchmarks']['TeamBench'])
        elif bench == 'clasharness':
            results = verify_clasharness(base_path, lock_config['benchmarks']['CLASHarness'])
        
        report['benchmarks'][bench] = results
        
        # Print summary
        pass_count = sum(1 for v in results.values() if v['status'] == 'PASS')
        fail_count = sum(1 for v in results.values() if v['status'] == 'FAIL')
        blocked_count = sum(1 for v in results.values() if v['status'] == 'BLOCKED')
        
        print(f'  PASS: {pass_count}, FAIL: {fail_count}, BLOCKED: {blocked_count}')
        
        for check, result in results.items():
            status_icon = '[OK]' if result['status'] == 'PASS' else '[FAIL]' if result['status'] == 'FAIL' else '[BLOCKED]'
            print('  {} {}: {}'.format(status_icon, check, result["message"]))
    
    # Overall status
    all_results = [r['status'] for bench in report['benchmarks'].values() for r in bench.values()]
    if all(s == 'PASS' for s in all_results):
        report['overall_status'] = 'PASS'
    elif any(s == 'FAIL' for s in all_results):
        report['overall_status'] = 'FAIL'
    else:
        report['overall_status'] = 'PARTIAL'
    
    print(f'\n{"="*60}')
    print(f'Overall status: {report["overall_status"]}')
    
    # Save report
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f'\nReport saved to: {output_path}')
    
    # Exit code
    if report['overall_status'] == 'PASS':
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
