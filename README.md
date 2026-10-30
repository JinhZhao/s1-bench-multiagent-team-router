# S1 Benchmark: Multi-Team Collaboration, Dynamic Routing & Fault Isolation

> **Competition Track**: Agent System Architecture / Multi-Team Collaboration  
> **Status**: Open Challenge  
> **Requirements**: A, B, C all mandatory  
> **Evaluation**: A MultiAgentBench (MARBLE) + B TeamBench + C CLASHarness v8  
> **Version**: `S1-2026-10-30`

---

## Overview

This repository provides the official benchmark suite for the S1 competition track. Participants must design, implement, and run a **hierarchical system** with:

- **1 Global Coordinator** → routes tasks across teams
- **3+ Independent Teams** → each with distinct input/output contracts
- **2+ Agents per Team** → observable execution roles

The system must demonstrate superior performance compared to baselines (flat/fixed routing) on complex multi-agent tasks while maintaining role boundaries, handling exceptions, and providing auditable execution traces.

**Key Challenge**: The real architectural problems occur **between teams** — who takes the next step? How is evidence handed off? How are cross-team dependencies scheduled? Can the system recover when a team fails or provides contradictory results?

---

## Three Mandatory Benchmarks

| Benchmark | Focus | Tasks | Evaluation |
|-----------|-------|-------|------------|
| **A: MARBLE** | Multi-agent collaboration, communication, dependency coordination | 6 scenes (werewolf, coding, database, reasoning, research, world) | Official scene evaluators |
| **B: TeamBench** | Role isolation, division of labor, ablation gains | 90 tasks, seed=0, 5 official conditions + 2 extension conditions | Official deterministic grader |
| **C: CLASHarness** | Shared state conflicts, evidence contradictions, fault recovery | 600 episodes (v8/total) | Official all-pass/mean-score checks |

**Important**: The three benchmarks test **different capabilities** and must all be run. No single benchmark proves overall system quality.

---

## System Requirements

### Hardware
- **Disk**: ≥30 GB free space (5.4 GB for CLASHarness data + environments + logs)
- **RAM**: ≥16 GB recommended
- **GPU**: Not required (uses remote model APIs)

### Software
- **OS**: Ubuntu 22.04 LTS (recommended) or Windows 11 + WSL2
- **Git**: Any recent version
- **Docker**: Engine 20.10+ with Compose v2 (required for TeamBench)
- **Conda**: Miniforge or Anaconda (for environment isolation)
- **Python**: 3.10 (MARBLE), 3.11 (TeamBench, CLASHarness)
- **Network**: Access to GitHub, HuggingFace, PyPI, and model API endpoints

### API Keys
- **Model Service**: OpenAI, Anthropic, or other authorized provider
- **Judge Model** (CLASHarness): Separate model for semantic evaluation
- **Note**: API costs are the participant's responsibility

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/JinhZhao/s1-bench-multiagent-team-router.git
cd s1-bench-multiagent-team-router
```

### 2. Install Environments

```bash
python scripts/setup.py --all
```

This creates three isolated conda environments:
- `s1-marble` (Python 3.10 + Poetry)
- `s1-teambench` (Python 3.11 + uv + Docker)
- `s1-clash` (Python 3.11 + pip)

**Estimated time**: 15-30 minutes depending on network speed

### 3. Download Data

```bash
python scripts/download_data.py
```

Verifies (and if missing, downloads) benchmark data:
- CLASHarness v8 dataset (~5.4 GB) — reuses existing data if hash-verified
- TeamBench task manifests (shipped with repo)
- MARBLE scene configurations (shipped with repo)

**Estimated time**: 10-20 minutes for initial CLASHarness download; seconds if reusing existing data

### 4. Verify Installation

```bash
python scripts/verify.py --all
```

Checks:
- Git commit SHAs match `benchmark.lock.json`
- Data file SHA256 hashes match `checksums.sha256`
- Environment dependencies installed correctly
- Docker images built (TeamBench)

Expected output: `ALL CHECKS PASSED ✓`

### 5. Run Smoke Tests

```bash
python scripts/smoke_test.py --all
```

Validates:
- Source code versions consistent
- Data downloads complete and verified
- Environment dependencies checkable
- Task manifests readable
- JSON schemas valid
- Scoring scripts can process legal result samples
- Corrupted data / missing tasks / forged fields detected

**Note**: Smoke tests do NOT require API keys. Real task execution (G3) requires API keys and is blocked until configured.

### 6. Configure API Keys

Create `.env` file (never commit this):

```bash
export S1_MODEL="gpt-4"  # or your authorized model ID
export S1_JUDGE_MODEL="gpt-4"  # for CLASHarness semantic evaluation
export OPENAI_API_KEY="sk-..."  # or your provider's key
```

### 7. Run Development Evaluation

```bash
python scoring/score.py \
  --runs-dir ./runs \
  --manifest tasks/dev_manifest.json \
  --locks benchmark.lock.json \
  --output ./scorecard.json
```

Generates unified scorecard with:
- Official benchmark scores (MARBLE 30 + TeamBench 30 + CLASHarness 25)
- Cross-cutting metrics (architecture authenticity 10 + reproducibility 5)
- Bonus (catalysis demo, 15, non-ranking)

---

## Repository Structure

```
S1-benchmark/
├── README.md                          # This file
├── G4_EXECUTION_SUMMARY.md            # Implementation status
├── benchmark.lock.json                # Git commits, versions, dependencies
├── checksums.sha256                   # Data integrity hashes
├── .gitignore                         # Git ignore rules
│
├── tasks/
│   ├── dev_manifest.json              # All task IDs, seeds, conditions
│   └── teambench_real_tasks.json      # Extracted TeamBench 90 task IDs
│
├── scripts/                           # Main entry points
│   ├── setup.py                       # Install environments
│   ├── download_data.py               # Verify/download datasets
│   ├── verify.py                      # Verify installation + patches
│   ├── apply_patches.py               # Apply known-issue patches
│   └── smoke_test.py                  # Smoke tests (no API key)
│
├── scoring/
│   └── score.py                       # Unified scoring pipeline
│
├── schemas/                           # JSON schemas
│   ├── task_manifest.schema.json
│   ├── run_result.schema.json
│   ├── event.schema.json
│   └── scorecard.schema.json
│
├── patches/                           # Known-issue patches
│   ├── marble_evaluator_syntax.patch
│   └── clasharness_pyproject.patch
│
├── environments/                      # Per-benchmark env specs
│   ├── marble/
│   ├── teambench/
│   └── clasharness/
│
├── examples/
│   └── sample_submission/             # Example submission layout
│
├── tests/
│   ├── test_minimum_repro.py          # Full pipeline gate
│   └── fixtures/                      # Synthetic test data
│
└── docs/                              # Extended documentation
```
│
├── patches/                           # Bug fixes for official repos
│   ├── marble_evaluator_syntax.patch
│   ├── clasharness_python_version.patch
│   └── clasharness_pyproject.patch
│
├── examples/
│   └── sample_submission/             # Example participant output
│
├── tests/
│   └── fixtures/                      # Test data
│
└── docs/
    ├── INSTALL.md                     # Detailed installation guide
    ├── DATASETS.md                    # Dataset descriptions
    ├── EVALUATION.md                  # Evaluation interface
    └── KNOWN_ISSUES.md                # Known problems and workarounds
```

---

## Task Manifest

All tasks are defined in `tasks/dev_manifest.json`:

### MARBLE (6 scenes)
- `werewolf` — Social deduction game (dedicated evaluator)
- `coding` — Code generation tasks
- `database` — Database management
- `reasoning` — Logical reasoning (CoT/ReAct/Reflexion)
- `research` — Research assistance
- `world` — World simulation

### TeamBench (90 tasks)
- Real task IDs extracted from `leaderboard/data/leaderboard_90_tasks.json`
- Examples: `TRAP1_spec_conflict`, `TRAP5_security_theater`, `GH1006_spaCy_13068`, ...
- Full list: `tasks/teambench_real_tasks.json`
- Seed: `0` (fixed)
- Conditions: `oracle`, `restricted`, `full`, `team_no_plan`, `team_no_verify`
- Extension: `global`, `no-global` (participant architecture ablation)

### CLASHarness (600 episodes)
- Dataset: v8 (`tasks-v8` + `splits-v8`)
- Split: `total` (600 episodes)
- Conditions: `flat`, `dynamic`

---

## Scoring

### Base Score (100 points)

| Component | Points | Description |
|-----------|--------|-------------|
| A: MARBLE task completion | 18 | Official scene scores, macro-averaged |
| A: MARBLE routing gain | 12 | `dynamic − fixed`, `dynamic − flat` |
| B: TeamBench task quality | 15 | Pass rate, partial scores (90 tasks) |
| B: TeamBench role isolation | 15 | TNI, ablation gains, `global − no-global` |
| C: CLASHarness conflict resolution | 18 | All-pass, mean score (600 episodes) |
| C: CLASHarness fault isolation | 7 | Lock/permission, error propagation, recovery |
| Cross: Architecture authenticity | 10 | Real cross-team handoffs, state tracking |
| Cross: Reproducibility compliance | 5 | Version locks, traces, usage accounting |

### Bonus Score (15 points, optional)

| Challenge | Points | Description |
|-----------|--------|-------------|
| D1: Adaptive team orchestration | +5 | Dynamic serial/parallel/skip decisions |
| D2: Cross-team consistency | +5 | Evidence versioning, dependency management |
| D3: Cost-reliability joint optimization | +5 | Quality per token, recovery overhead |

**Total possible**: 115 points (100 base + 15 bonus)

---

## Known Issues

### P0 Blockers (Official Repository Bugs)

1. **MARBLE**: SyntaxError in `marble/evaluator/evaluator.py:324`
   - Issue: `except` clause inside `if` block breaks try-except structure
   - Patch: `patches/marble_evaluator_syntax.patch`
   - Status: Patch required before G3

2. **CLASHarness**: SyntaxError in `docs/analysis/analysis_v8/tools/build_behavior_report.py:4910`
   - Issue: f-string with backslash requires Python ≥3.12
   - Patch: `patches/clasharness_python_version.patch`
   - Status: Patch required or upgrade to Python 3.12+

3. **CLASHarness**: pyproject.toml misconfiguration
   - Issue: `dependencies` array under `[project.urls]` instead of `[project]`
   - Patch: `patches/clasharness_pyproject.patch`
   - Status: Patch required for editable install

### P1 Issues

4. **Missing API Keys**: All three benchmarks require model API keys for G3
   - Status: BLOCKED until API keys configured

### P2 Notes

5. **MARBLE Evaluators**: Only `werewolf` scene has dedicated evaluator
   - Other scenes use general evaluator (unverified without API)

6. **CLASHarness Data**: Initial download may be incomplete (414/600 directories)
   - Solution: Re-run `download_data.py` to complete 600/600

---

## Development Workflow

### For Participants

1. **Setup**: Clone repo → Run `scripts/setup.py` → Run `scripts/download_data.py` → Run `scripts/verify.py`
2. **Develop**: Implement your multi-team system in `solution/` directory
3. **Test**: Run `scripts/smoke_test.py` to validate environment (no API key needed)
4. **Evaluate**: Run `scoring/score.py` on your results to get development scores
5. **Submit**: Package `solution/` + `runs/` (with `run_result.json` + `events.jsonl` per run) + `scorecard.json`

### For Organizers

1. **Validate**: Run `scripts/verify.py --all` to check all hashes, versions, and patches
2. **Reproduce**: Run `tests/test_minimum_repro.py` for the full pipeline gate
3. **Score**: Run `scoring/score.py` to compute final scorecard
4. **Audit**: Run `s1_audit.py audit-submission <path>` to validate submission structure

---

## File Formats

### Event Log (events.jsonl)

Each line is a JSON object with minimum fields:

```json
{
  "event_id": "uuid",
  "seq": 1,
  "run_id": "run-001",
  "task_id": "werewolf-01",
  "benchmark": "MARBLE",
  "mode": "dynamic",
  "event_type": "handoff.requested",
  "from_team": "knowledge",
  "to_team": "decision",
  "from_agent": "knowledge-lead",
  "to_agent": "decision-lead",
  "handoff_id": "h-001",
  "idempotency_key": "same-logical-task",
  "status": "accepted",
  "timestamp": "2026-10-30T10:00:00Z",
  "input_ref": "artifacts/request.json",
  "output_ref": "artifacts/result.json",
  "evidence_refs": ["official-env-observation-id"]
}
```

### Scorecard (scorecard.json)

```json
{
  "benchmark": "TeamBench",
  "task_id": "DIST1_queue_race",
  "mode": "global",
  "passed": true,
  "partial_score": 0.85,
  "grader_kind": "official",
  "official_score": 0.85,
  "extension_metrics": {
    "handoff_count": 3,
    "retry_count": 0,
    "routing_errors": 0
  },
  "usage": {
    "input_tokens": 1500,
    "output_tokens": 800,
    "cost_usd": 0.023
  }
}
```

---

## Reproducibility

All versions are locked in `benchmark.lock.json`:

- **Git Commits**: Three 40-character SHAs (one per benchmark)
- **Data Hashes**: SHA256 for task manifests and episode lists
- **Dependencies**: pip freeze outputs for each environment
- **Docker Images**: Image IDs for TeamBench containers

To reproduce:

```bash
# Verify source code
git -C MARBLE rev-parse HEAD
# Expected: 8d60fa17b5596b44458a52d4296061b9fc13d6f2

# Verify data
sha256sum TeamBench/leaderboard/data/leaderboard_90_tasks.json
# Expected: f210a53097304eabc59ad0fd9c8d579fa7c81ffb13b7e097cba03e330db3f2fe

# Verify environment
conda run -n s1-marble python -m pip freeze | wc -l
# Expected: 161
```

---

## License

- **S1 Benchmark Code**: MIT License (see LICENSE file)
- **MARBLE**: Original license from ulab-uiuc/MARBLE
- **TeamBench**: Original license from ybkim95/TeamBench
- **CLASHarness**: Original license from google-research/CLASHarness

**Note**: This repository provides adapters and scripts. The three benchmark repositories are cloned from their official sources and remain under their original licenses.

---

## Support

- **Documentation**: See `docs/` directory
- **Known Issues**: See `docs/KNOWN_ISSUES.md`
- **Bug Reports**: Open issue on GitHub
- **Questions**: Contact organizers via official channels

---

## Citation

If you use this benchmark suite in your research, please cite:

```bibtex
@misc{s1_benchmark_2026,
  title={S1 Benchmark: Multi-Team Collaboration, Dynamic Routing and Fault Isolation},
  author={S1 Organizing Committee},
  year={2026},
  url={https://github.com/JinhZhao/s1-bench-multiagent-team-router}
}
```

---

**Last Updated**: 2026-10-30  
**Version**: S1-2026-10-30  
**Status**: Ready for participant setup (G3 blocked pending API keys)
