#!/usr/bin/env python3
"""S1 scoring script.

Reads run results + event logs from runs/ directory, computes per-benchmark
scores per the frozen rubric, and emits a scorecard.json.

Rubric (100 base + 15 bonus):
  A. MARBLE (30): task completion (18) + routing gain (12)
  B. TeamBench (30): task quality (15) + role isolation (15)
  C. CLASHarness (25): conflict handling (18) + fault isolation (7)
  Cross-cutting (15): architecture authenticity (10) + reproducibility (5)
  Bonus: catalysis demo (15, non-ranking)
"""
import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def load_events(events_file):
    events = []
    with open(events_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _marble_task_ids(manifest):
    """Extract eligible MARBLE task IDs (scenes)."""
    scenes = manifest['benchmarks']['MARBLE'].get('scenes', [])
    return {s['scene_id'] for s in scenes if s.get('status', 'AVAILABLE') != 'EXCLUDED'}


def _teambench_task_ids(manifest, base_dir):
    """Extract eligible TeamBench task IDs from the manifest file."""
    tb = manifest['benchmarks']['TeamBench']
    tm = tb.get('task_manifest')
    if isinstance(tm, str):
        p = base_dir / 'TeamBench' / tm
        if p.exists():
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
            return {t['task_id'] for t in data.get('tasks', [])}
    elif isinstance(tm, list):
        return {t['task_id'] for t in tm}
    return set()


def _clasharness_episode_ids(manifest, base_dir):
    """Extract eligible CLASHarness episode IDs."""
    cl = manifest['benchmarks']['CLASHarness']
    em = cl.get('episode_manifest')
    if isinstance(em, str):
        p = base_dir / 'CLASHarness' / em
        if p.exists():
            with open(p, encoding='utf-8') as f:
                return {ln.strip() for ln in f if ln.strip()}
    elif isinstance(em, list):
        return set(em)
    return set()


def score_marble(run_results, manifest):
    """Score MARBLE benchmark.

    Task completion (18): macro-average of official pass rate and partial score
    across all eligible scenes.
    Routing gain (12): paired delta (dynamic - fixed), (dynamic - flat),
    averaged. Negative deltas clamp to 0.
    """
    eligible_ids = _marble_task_ids(manifest)

    by_mode = {'flat': [], 'fixed': [], 'dynamic': []}
    for r in run_results:
        if r['benchmark'] != 'MARBLE':
            continue
        if r['task_id'] not in eligible_ids:
            continue
        mode = r['mode']
        if mode not in by_mode:
            continue
        by_mode[mode].append(r)

    # Task completion uses dynamic mode as the primary result
    dynamic = by_mode['dynamic']
    if not dynamic:
        return {
            'task_completion': {'max_points': 18, 'awarded': 0,
                               'tasks_run': 0, 'tasks_passed': 0,
                               'pass_rate': 0, 'mean_partial': 0},
            'routing_gain': {'max_points': 12, 'awarded': 0,
                            'dynamic_vs_fixed_delta': 0, 'dynamic_vs_flat_delta': 0,
                            'idle_reroutes': 0, 'dependency_errors': 0},
            'total': 0
        }

    pass_rate = sum(1 for r in dynamic if r['official_score']['passed']) / len(dynamic)
    mean_partial = statistics.mean(r['official_score']['partial_score'] for r in dynamic)
    completion_awarded = 18 * (0.5 * pass_rate + 0.5 * mean_partial)

    # Routing gain: paired deltas
    fixed = by_mode['fixed']
    flat = by_mode['flat']

    def avg_partial(rs):
        if not rs:
            return 0
        return statistics.mean(r['official_score']['partial_score'] for r in rs)

    dyn_mp = avg_partial(dynamic)
    fix_mp = avg_partial(fixed)
    flat_mp = avg_partial(flat)

    delta_fixed = max(0, dyn_mp - fix_mp)
    delta_flat = max(0, dyn_mp - flat_mp)
    routing_awarded = 12 * (delta_fixed + delta_flat) / 2

    # Cross-mode event aggregation
    idle_reroutes = 0
    dependency_errors = 0
    for r in run_results:
        if r['benchmark'] != 'MARBLE' or r['mode'] != 'dynamic':
            continue
        ext = r.get('participant_extension', {})
        idle_reroutes += ext.get('retries', 0)
        # dependency_errors would come from event log analysis

    return {
        'task_completion': {
            'max_points': 18, 'awarded': round(completion_awarded, 3),
            'tasks_run': len(dynamic), 'tasks_passed': int(pass_rate * len(dynamic)),
            'pass_rate': round(pass_rate, 4), 'mean_partial': round(mean_partial, 4)
        },
        'routing_gain': {
            'max_points': 12, 'awarded': round(routing_awarded, 3),
            'dynamic_vs_fixed_delta': round(delta_fixed, 4),
            'dynamic_vs_flat_delta': round(delta_flat, 4),
            'idle_reroutes': idle_reroutes,
            'dependency_errors': dependency_errors
        },
        'total': round(completion_awarded + routing_awarded, 3)
    }


def score_teambench(run_results, manifest, base_dir):
    """Score TeamBench.

    Task quality (15): pass rate and mean partial across 90 tasks in any
    single official condition (use 'full' as primary).
    Role isolation (15): TNI (official) + global vs no-global delta from
    participant extension runs.
    """
    eligible_ids = _teambench_task_ids(manifest, base_dir)

    # Task quality uses 'full' condition as primary
    full_runs = [r for r in run_results
                if r['benchmark'] == 'TeamBench'
                and r['mode'] == 'full'
                and r['task_id'] in eligible_ids]

    if not full_runs:
        task_quality = {
            'max_points': 15, 'awarded': 0,
            'pass_rate': 0, 'mean_partial': 0
        }
    else:
        pass_rate = sum(1 for r in full_runs if r['official_score']['passed']) / len(full_runs)
        mean_partial = statistics.mean(r['official_score']['partial_score'] for r in full_runs)
        task_quality = {
            'max_points': 15,
            'awarded': round(15 * (0.5 * pass_rate + 0.5 * mean_partial), 3),
            'pass_rate': round(pass_rate, 4),
            'mean_partial': round(mean_partial, 4)
        }

    # Role isolation: TNI + global vs no-global
    global_runs = [r for r in run_results
                  if r['benchmark'] == 'TeamBench' and r['mode'] == 'global']
    noglobal_runs = [r for r in run_results
                    if r['benchmark'] == 'TeamBench' and r['mode'] == 'no-global']

    def mean_partial(rs):
        if not rs:
            return 0
        return statistics.mean(r['official_score']['partial_score'] for r in rs)

    delta = max(0, mean_partial(global_runs) - mean_partial(noglobal_runs))

    # TNI would come from official harness.compute_tni output; approximate from runs
    tni = delta  # placeholder: real TNI requires official ablation output

    role_awarded = 7.5 * min(1, tni) + 7.5 * min(1, delta * 2)
    role_isolation = {
        'max_points': 15,
        'awarded': round(role_awarded, 3),
        'tni': round(tni, 4),
        'global_vs_noglobal_delta': round(delta, 4)
    }

    return {
        'task_quality': task_quality,
        'role_isolation': role_isolation,
        'total': round(task_quality['awarded'] + role_isolation['awarded'], 3)
    }


def score_clasharness(run_results, manifest, base_dir):
    """Score CLASHarness.

    Conflict handling (18): pass rate + mean partial across 600 episodes,
    plus dynamic vs flat delta.
    Fault isolation (7): real trace examples of lock/permission/conflict
    recovery.
    """
    eligible_ids = _clasharness_episode_ids(manifest, base_dir)

    dynamic = [r for r in run_results
              if r['benchmark'] == 'CLASHarness'
              and r['mode'] == 'dynamic'
              and r['task_id'] in eligible_ids]
    flat = [r for r in run_results
           if r['benchmark'] == 'CLASHarness'
           and r['mode'] == 'flat'
           and r['task_id'] in eligible_ids]

    if not dynamic:
        return {
            'conflict_handling': {
                'max_points': 18, 'awarded': 0,
                'pass_rate': 0, 'mean_partial': 0, 'dynamic_vs_flat_delta': 0
            },
            'fault_isolation': {
                'max_points': 7, 'awarded': 0,
                'real_trace_examples': 0, 'lock_permission_failures': 0,
                'idempotent_recoveries': 0
            },
            'total': 0
        }

    pass_rate = sum(1 for r in dynamic if r['official_score']['passed']) / len(dynamic)
    mean_partial = statistics.mean(r['official_score']['partial_score'] for r in dynamic)
    flat_mp = statistics.mean((r['official_score']['partial_score'] for r in flat)) if flat else 0
    delta = max(0, mean_partial - flat_mp)

    conflict_awarded = 18 * (0.4 * pass_rate + 0.4 * mean_partial + 0.2 * min(1, delta * 2))

    # Fault isolation: count real trace examples from events
    real_examples = 0
    lock_failures = 0
    idempotent_recoveries = 0
    for r in dynamic:
        events_file = Path(r.get('events_file', ''))
        if not events_file.exists():
            continue
        try:
            events = load_events(events_file)
        except Exception:
            continue
        for e in events:
            if e.get('event_type') == 'recovery.completed':
                idempotent_recoveries += 1
                real_examples += 1
            if e.get('event_type') == 'error.raised' and 'lock' in e.get('error_code', '').lower():
                lock_failures += 1

    fault_awarded = min(7, real_examples * (7 / 3))  # 3 examples = full marks

    return {
        'conflict_handling': {
            'max_points': 18,
            'awarded': round(conflict_awarded, 3),
            'pass_rate': round(pass_rate, 4),
            'mean_partial': round(mean_partial, 4),
            'dynamic_vs_flat_delta': round(delta, 4)
        },
        'fault_isolation': {
            'max_points': 7,
            'awarded': round(fault_awarded, 3),
            'real_trace_examples': real_examples,
            'lock_permission_failures': lock_failures,
            'idempotent_recoveries': idempotent_recoveries
        },
        'total': round(conflict_awarded + fault_awarded, 3)
    }


def score_cross_cutting(run_results, manifest, locks, base_dir):
    """Score architecture authenticity (10) + reproducibility (5)."""
    # Architecture authenticity: count distinct teams, dual-layer routing,
    # and traceable handoffs
    teams = set()
    handoffs = 0
    dual_layer = False
    for r in run_results:
        events_file = Path(r.get('events_file', ''))
        if not events_file.exists():
            continue
        try:
            events = load_events(events_file)
        except Exception:
            continue
        for e in events:
            if e.get('from_team'):
                teams.add(e['from_team'])
            if e.get('to_team'):
                teams.add(e['to_team'])
            if e.get('event_type') == 'handoff.accepted':
                handoffs += 1
            if e.get('event_type') == 'route.selected':
                dual_layer = True

    arch_points = 0
    if len(teams) >= 3:
        arch_points += 4
    if dual_layer:
        arch_points += 3
    if handoffs >= 3:
        arch_points += 3
    elif handoffs >= 1:
        arch_points += 1

    authenticity = {
        'max_points': 10,
        'awarded': arch_points,
        'team_count': len(teams),
        'dual_layer_routing': dual_layer,
        'traceable_handoffs': handoffs
    }

    # Reproducibility: SHA verified, task manifest complete, trace complete
    sha_verified = bool(locks.get('source_commits_verified'))
    # Manifest completeness: check each benchmark has its expected structure
    marble_ok = bool(manifest['benchmarks']['MARBLE'].get('scenes'))
    tb = manifest['benchmarks']['TeamBench']
    tm = tb.get('task_manifest')
    if isinstance(tm, str):
        tb_ok = (base_dir / 'TeamBench' / tm).exists()
    else:
        tb_ok = isinstance(tm, list) and len(tm) >= 90
    cl = manifest['benchmarks']['CLASHarness']
    em = cl.get('episode_manifest')
    if isinstance(em, str):
        cl_ok = (base_dir / 'CLASHarness' / em).exists()
    else:
        cl_ok = isinstance(em, list) and len(em) >= 600
    manifest_complete = marble_ok and tb_ok and cl_ok

    trace_complete = all(r.get('events_file') and Path(r['events_file']).exists()
                        for r in run_results)

    repro_points = 0
    if sha_verified:
        repro_points += 2
    if manifest_complete:
        repro_points += 2
    if trace_complete:
        repro_points += 1

    reproducibility = {
        'max_points': 5,
        'awarded': repro_points,
        'sha_verified': sha_verified,
        'task_manifest_complete': manifest_complete,
        'trace_complete': trace_complete
    }

    return {
        'architecture_authenticity': authenticity,
        'reproducibility': reproducibility
    }


def score_bonus(run_results):
    """Bonus: catalysis demo (15, non-ranking)."""
    demo_runs = [r for r in run_results if r.get('mode') == 'catalysis_demo']
    if not demo_runs:
        return {'catalysis_demo': 0}
    # Demo is scored by independent review; placeholder 0
    return {'catalysis_demo': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs-dir', required=True,
                       help='Directory containing run_result.json files')
    parser.add_argument('--manifest', required=True,
                       help='Path to task_manifest.json')
    parser.add_argument('--locks', required=True,
                       help='Path to benchmark.lock.json')
    parser.add_argument('--output', required=True,
                       help='Output scorecard.json path')
    parser.add_argument('--submission-id', default='s1-submission')
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    if not runs_dir.is_dir():
        print(f'ERROR: runs directory not found: {runs_dir}')
        sys.exit(1)

    manifest = load_json(args.manifest)
    locks = load_json(args.locks)

    # Infer base_dir (s1-benchmarks/) from manifest paths or locks
    base_dir = Path(locks.get('base_dir', 'E:/CatalystPI/s1-benchmarks'))

    run_results = []
    for p in runs_dir.rglob('run_result.json'):
        try:
            run_results.append(load_json(p))
        except Exception as e:
            print(f'WARNING: skipping {p}: {e}')

    print(f'Loaded {len(run_results)} run results')

    marble = score_marble(run_results, manifest)
    teambench = score_teambench(run_results, manifest, base_dir)
    clasharness = score_clasharness(run_results, manifest, base_dir)
    cross = score_cross_cutting(run_results, manifest, locks, base_dir)
    bonus = score_bonus(run_results)

    base_total = marble['total'] + teambench['total'] + clasharness['total']
    cross_total = (cross['architecture_authenticity']['awarded']
                  + cross['reproducibility']['awarded'])
    bonus_total = bonus['catalysis_demo']

    scorecard = {
        'scorecard_version': '1.0',
        'submission_id': args.submission_id,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'model_id': locks.get('model', {}).get('model_id', 'UNKNOWN'),
        'model_revision': locks.get('model', {}).get('revision', 'UNKNOWN'),
        'benchmarks': {
            'MARBLE': marble,
            'TeamBench': teambench,
            'CLASHarness': clasharness
        },
        'cross_cutting': cross,
        'bonus': bonus,
        'totals': {
            'base_total': round(base_total, 3),
            'cross_cutting_total': round(cross_total, 3),
            'bonus_total': round(bonus_total, 3),
            'grand_total': round(base_total + cross_total + bonus_total, 3)
        }
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(scorecard, f, indent=2, ensure_ascii=False)

    print(f'\nScorecard written to: {args.output}')
    print(f'  MARBLE:      {marble["total"]:.2f}/30')
    print(f'  TeamBench:   {teambench["total"]:.2f}/30')
    print(f'  CLASHarness: {clasharness["total"]:.2f}/25')
    print(f'  Cross-cut:   {cross_total:.2f}/15')
    print(f'  Bonus:       {bonus_total:.2f}/15')
    print(f'  GRAND TOTAL: {base_total + cross_total + bonus_total:.2f}/115')


if __name__ == '__main__':
    main()
