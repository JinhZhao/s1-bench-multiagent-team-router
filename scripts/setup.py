#!/usr/bin/env python3
"""S1 Benchmark Setup Script

Creates three isolated conda environments for MARBLE, TeamBench, and CLASHarness.
Applies necessary patches to official repositories.

Usage:
    python scripts/setup.py --all
    python scripts/setup.py --benchmark marble
    python scripts/setup.py --benchmark teambench
    python scripts/setup.py --benchmark clasharness
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

BENCHMARKS = {
    'marble': {
        'python_version': '3.10',
        'conda_env': 's1-marble',
        'repo': 'https://github.com/ulab-uiuc/MARBLE.git',
        'commit': '8d60fa17b5596b44458a52d4296061b9fc13d6f2',
        'package_manager': 'poetry',
        'patches': ['patches/marble_evaluator_syntax.patch']
    },
    'teambench': {
        'python_version': '3.11',
        'conda_env': 's1-teambench',
        'repo': 'https://github.com/ybkim95/TeamBench.git',
        'commit': 'd185aef1916fd86a9ba554d581fd256319a973af',
        'package_manager': 'uv',
        'docker_required': True,
        'patches': []
    },
    'clasharness': {
        'python_version': '3.11',
        'conda_env': 's1-clash',
        'repo': 'https://github.com/google-research/CLASHarness.git',
        'commit': '234161ddc44755017215dd734d38be15419a45e0',
        'package_manager': 'pip',
        'patches': [
            'patches/clasharness_python_version.patch',
            'patches/clasharness_pyproject.patch'
        ]
    }
}


def run_cmd(cmd, cwd=None, check=True):
    """Run shell command and return result."""
    print(f"  Running: {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False
    )
    if check and result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        return False
    return True


def setup_benchmark(name, config):
    """Setup a single benchmark environment."""
    print(f"\n{'='*60}")
    print(f"Setting up {name.upper()}")
    print(f"{'='*60}")
    
    # Check if repo already exists
    repo_dir = Path(name.capitalize() if name != 'clasharness' else 'CLASHarness')
    if repo_dir.exists():
        print(f"  ✓ Repository already exists: {repo_dir}")
        # Verify commit
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=repo_dir,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            current_commit = result.stdout.strip()
            if current_commit == config['commit']:
                print(f"  ✓ Commit matches: {current_commit[:8]}")
            else:
                print(f"  ⚠ Commit mismatch: {current_commit[:8]} != {config['commit'][:8]}")
                print(f"  Checking out correct commit...")
                run_cmd(f"git checkout {config['commit']}", cwd=repo_dir)
    else:
        # Clone repository
        print(f"  Cloning {config['repo']}...")
        if not run_cmd(f"git clone {config['repo']} {repo_dir}"):
            return False
        
        # Checkout specific commit
        print(f"  Checking out commit {config['commit'][:8]}...")
        if not run_cmd(f"git checkout {config['commit']}", cwd=repo_dir):
            return False
    
    # Create conda environment
    print(f"  Creating conda environment: {config['conda_env']} (Python {config['python_version']})")
    if not run_cmd(f"conda create -y -n {config['conda_env']} python={config['python_version']}"):
        print(f"  ⚠ Conda environment may already exist")
    
    # Apply patches
    for patch_file in config.get('patches', []):
        patch_path = Path(patch_file)
        if patch_path.exists():
            print(f"  Applying patch: {patch_file}")
            run_cmd(f"git apply {patch_path.absolute()}", cwd=repo_dir, check=False)
        else:
            print(f"  ⚠ Patch file not found: {patch_file}")
    
    # Install dependencies
    print(f"  Installing dependencies with {config['package_manager']}...")
    if config['package_manager'] == 'poetry':
        run_cmd(f"conda run -n {config['conda_env']} pip install poetry==2.1.4")
        run_cmd(f"conda run -n {config['conda_env']} poetry install", cwd=repo_dir)
    elif config['package_manager'] == 'uv':
        run_cmd(f"conda run -n {config['conda_env']} pip install uv")
        run_cmd(f"conda run -n {config['conda_env']} uv sync --all-extras", cwd=repo_dir)
    elif config['package_manager'] == 'pip':
        # Manual installation for CLASHarness due to pyproject.toml bug
        run_cmd(f"conda run -n {config['conda_env']} pip install huggingface_hub pytest Pillow matplotlib numpy")
    
    # Build Docker images if required
    if config.get('docker_required'):
        print(f"  Building Docker images...")
        run_cmd("docker compose build", cwd=repo_dir)
    
    print(f"  ✓ {name.upper()} setup complete")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='Setup all benchmarks')
    parser.add_argument('--benchmark', choices=['marble', 'teambench', 'clasharness'],
                       help='Setup specific benchmark')
    args = parser.parse_args()
    
    if not args.all and not args.benchmark:
        parser.print_help()
        sys.exit(1)
    
    benchmarks_to_setup = BENCHMARKS.keys() if args.all else [args.benchmark]
    
    print("S1 Benchmark Setup")
    print("="*60)
    
    success_count = 0
    for name in benchmarks_to_setup:
        if setup_benchmark(name, BENCHMARKS[name]):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"Setup complete: {success_count}/{len(benchmarks_to_setup)} benchmarks")
    print(f"{'='*60}")
    
    if success_count == len(benchmarks_to_setup):
        print("\n✓ All benchmarks setup successfully")
        print("\nNext steps:")
        print("  1. Run: python scripts/download_data.py --all")
        print("  2. Run: python scripts/verify.py --all")
        print("  3. Run: python scripts/smoke_test.py --all")
        sys.exit(0)
    else:
        print("\n✗ Some benchmarks failed to setup")
        print("Check error messages above for details")
        sys.exit(1)


if __name__ == '__main__':
    main()
