# Architecture and implementation plan

## Boundaries

```text
React / TypeScript / SVG
        | HTTP + SSE, same origin
FastAPI application adapters
        | typed domain models
SQLite repository -------- local PNG asset store
        | persistent job snapshots/checkpoints
Supervisor thread -- spawn --> single CPU worker process
                               | proposal -> scenario -> entity simulation
                               | rank -> checkpoint -> held-out evaluation
```

The domain, geometric matcher, scenario generator, simulator and optimizer are callable without the application server. No solver code imports React or FastAPI. Packs are data, not embedded statistics in the engine. The SVG interface was chosen over a heavy canvas library because tile counts and trajectories are small enough for an accessible, inspectable renderer.

The initial database adapter uses Python's SQLite driver and parameterized statements. A small repository avoids an ORM dependency for JSON aggregate storage. Migration version 1 creates resource aggregates, revision history and job tables. Replacing this adapter with normalized SQLAlchemy/PostgreSQL tables is possible, but not implemented. SQLite transaction boundaries and optimistic revision numbers are explicit. Binary assets remain files.

## Persistence

| Record | Persistence |
|---|---|
| Accounts / armies / calibration / packs | `resources(kind,id,data,updated)` |
| Layout current state | `resources` with optimistic revision check |
| Every saved layout revision | `layout_revisions(id,revision,data)` |
| Solver inputs and lifecycle | `jobs` with frozen input JSON |
| Elite strategies, metrics, seeds, frames, history | Transactional job checkpoint JSON |
| Screenshot pixels | Random-ID PNGs in `runtime/assets` |
| Reports and backups | Downloadable output / `runtime/exports` |

Pack IDs are immutable. Re-importing identical data is idempotent; changed data require another ID. Inputs contain the actual pack, not a mutable reference. Exact reproducibility also requires the recorded engine revision and Python dependency versions. Time-budgeted optimization iteration counts can vary with hardware; a given strategy and scenario seed replay deterministically.

## Worker lifecycle and budget

`queued -> running -> completed | paused | cancelled | failed`; `paused -> queued` resumes.

A kernel file lock prevents two supervisors for one runtime. Jobs are claimed transactionally in creation order. The supervisor spawns one process and polls it every 100 ms. All proposed candidates and scenarios run outside the web process. Simulation checks a monotonic deadline at every tick; the worker checks controls periodically. The parent terminates a nonresponsive worker at its monotonic budget deadline. Scheduling/termination latency can be roughly one supervisor poll plus OS delay; this is not a hard real-time OS guarantee.

Process startup, search, independent finalist evaluation and replay generation are charged against the budget. Pauses retain cumulative active time. Recovery conservatively charges elapsed UTC wall time since the last segment start, including downtime, to avoid gifting new budget after a crash. Wall-clock changes during recovery are a known limitation; live enforcement is monotonic. Completed checkpoints survive a crash, while an in-flight incomplete evaluation is discarded. A short job may end with candidates but incomplete hold-out metrics or no replay, which the interface reports.

The initial worker manager is intentionally serial. A future process pool should share common scenario seeds, charge all concurrent wall time correctly, bound memory and preserve deterministic proposal ordering. Parallel scaling is unmeasured here.

## Search

1. Diverse cardinal-entry heuristics create legal baselines.
2. Seeded random restarts and local mutations explore placement/timing and optional troop composition.
3. Capacity checks, supported-level checks and exact action/army reconciliation reject invalid plans.
4. Common random scenarios reduce comparison noise. Candidate signatures avoid exact repeats.
5. Lexicographic ranking prioritizes model three-star rate, then catastrophic failure, lower-tail stars, destruction, timeout, complexity and duration.
6. Elites retain distinct entry sides / broad troop families. Alternatives are distinct model concepts, not independent mathematical optima.
7. The measured evaluation cost determines time reserved for independent finalist samples. Those samples never rank candidates or feed proposals.

This is a hierarchical heuristic/evolutionary prototype, not Bayesian optimization, MCTS, reinforcement learning or global optimization. Baseline comparisons are separate reproducible experiments; no superiority is assumed.

## Local exposure

The native server binds `127.0.0.1`. Host headers and browser write origins are checked. No CORS wildcard is enabled. Official API network requests use a fixed public endpoint and server-side credential. Uploads have compressed-size/decoded-pixel limits and are re-encoded before serving. API documentation is at `/docs`; raw schema at `/openapi.json`.

This is a trusted single-user local application, not a hardened multi-user internet service. Its JSON/resource size and numerical limits bound ordinary inputs but do not replace authentication, quotas or a production security review.

## Extension sequence

The implementation follows the requested seven phases, keeping the vertical slice runnable:

1. Research, contracts, repository, provenance and persistence — implemented foundation.
2. Reconstruction/editor/matching — synthetic automatic path plus manual real-image path; trained detector remains a gap.
3. Combat subset — implemented approximate entity model, with explicit unsupported mechanics.
4. Search prototype — implemented persistent anytime solver.
5. Robust scenarios — bombs, defenders, HP/damage and human error; equipment/pets/siege remain gaps.
6. UI/integration — integrated accounts, editor, planner, live state, results and reports.
7. Calibration/performance — tests and benchmark instrumentation; genuine replay datasets and calibration remain necessary.

Next: validate licensed detector weights on held-out real screenshots, assemble versioned behavior/stat packs, build permitted controlled replay observations, add authentic mechanics one at a time, then compare algorithms and parallel execution on a challenging benchmark suite.
