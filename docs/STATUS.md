# Project status

Updated 2026-10-23. Version 0.1.0 is an integrated research prototype, not completion of the comprehensive high-fidelity platform described in the brief.

## Completed and exercised

- React/TypeScript interface: overview, account inventory, layout editor, screenshot input/calibration, attack configuration, live SSE, model results, timeline, chronological instructions and data management.
- FastAPI typed request models and OpenAPI, SQLite migration/version 1, optimistic layout revisions, immutable packs, local image storage, account/army persistence, player JSON/public API adapters and backup ZIP.
- Synthetic image recognition with exact fixture reconstruction, manual real-screenshot reconstruction, uncertain contour proposals and tile-aligned screenshot overlay.
- Layout fingerprints invariant to tile-preserving rotation/reflection/translation, exact vs approximate labels, type-constrained assignment and missing-object penalties.
- Evidence-bearing trap markers, distinct hypotheses, weighted joint bomb configurations without replacement, defender/parameter/human-error scenarios and visible assumptions.
- Independent approximate entity simulator with seeded replays and structured events; combat coverage and limitations in MODEL.md.
- Baseline entry proposals, legal action checks, troop-composition flexibility, exact troop locks, timing/location mutations, incumbent preservation, diversity and independent finalist evaluation.
- Persistent serial process worker, real controls, checkpoint recovery, cumulative budgets, live monotonic watchdog and measured resource reporting.
- JSON bundles, standalone HTML reports printable to PDF, calibration observations/MAE, data-pack discrepancies and a pinned/hashed public-source staging adapter.
- Windows setup/start/test scripts, pinned dependency lockfiles, reproducible fixtures, benchmark programs and optional untested Docker recipe.

## Partially implemented or unsupported

| Requested area | Current limit |
|---|---|
| Real screenshot recognition | No trained weights or validated precision/recall. Classification, walls, grid, levels, modes and orientation require manual review. |
| Full village validation | Geometry, exact one Town Hall, supported levels/modes/footprints and overlaps checked. Authentic TH-specific counts/unlock rules are absent. |
| Accounts | Broad inventory fields stored; advanced boosts, Super Troop selection, loadouts, donations and native village-export parsing not implemented in combat. |
| Hidden defense intelligence | Local evidence and assumed scenarios only. No historical replay corpus, verified popular-base trap catalogue or calibrated population priors. |
| Combat fidelity | Four simple troop definitions, six building categories, walls, bombs, three spells and simplified King only. Advanced heroes/equipment/pets/siege/summons/chain/ramping/sweeper mechanics absent. |
| Tactical search | Entry heuristics and evolutionary/local proposals. No full tactical compartment analyzer, conditional instructions, composition search over spells/equipment/pets or proof of optimality. |
| Robustness | Monte Carlo search/held-out samples and subgroup summaries. No fitted real-world probability, dedicated trap ablation/sensitivity or statistically tested probability-equivalence ranking. |
| Workers | One process and serial queue; no multi-core evaluation pool, distributed execution, parallel scaling benchmark or three-hour soak test. |
| Reproduction | Fixed strategies/scenarios deterministic on the same engine/runtime. Wall-clock job iteration counts depend on hardware. Recovery charges downtime conservatively. |
| Data promotion | Snapshot is staging evidence, not a complete game-stat pack. Authentic patch/effective dates, HP, cadence, movement and behavioral data remain gaps. |
| Deployment | Native Windows tested. Docker included but not executed; no cloud publishing requested or performed. |

## Executed validation

- Automated Python suite: **43 tests** (final JUnit output: `benchmarks/tests.xml`). A third-party Starlette/AnyIO deprecation warning is informational; no test failure is hidden.
- Frontend: strict TypeScript compilation and Vite production build pass.
- Fresh native setup: `scripts/setup.ps1` created the repository `.venv`, installed locked dependencies, built the frontend and initialized SQLite successfully.
- Browser: uploaded synthetic screenshot, detected **27/27** structures, marked review complete, saved, configured a **30-second** fixed-army job, received real live state, completed **212** checkpointed simulations, viewed three candidates and scrubbed the replay. That particular count is observational, not a throughput promise.
- Browser screenshot evidence: `benchmarks/browser-map.png`. Standalone saved report/result: `examples/attack-report.html`, `examples/attack-result.json`.
- A final fresh 30-second job on the final code completed 110 checkpointed simulations, retained three candidates, and completed independent validation and replay for the first two before the deadline. Its snapshot is the exported example. Incomplete third-finalist validation is explicitly represented as null.
- Tests include account import/persistence, screenshot review gating, exact local match, stale-revision rejection, saved revision restoration, pack immutability, host/origin guard, upload/backup, diagnostic simulation, calibration storage, process controls, deadlines and conservative crash recovery.
- Engine tests include identical seeded logs, attack cadence, delayed projectiles, ground wall destruction, deadline/control interruption, joint valid bomb sampling, Wilson boundary behavior, fixed armies, exact locks, primary-objective ordering and disjoint finalist seeds.

The generated-image recognition result is an exact synthetic test, not a real screenshot accuracy metric. No genuine battle replay was used for empirical validation.

## Measured performance

Host inspection: Intel Core i7-1255U, 12 logical processors, approximately 11.7 GiB physical RAM, Windows 11. No GPU acceleration used. This differs from the hypothetical hardware in the prompt.

`benchmarks/initial.json`: ten synthetic fixture simulations, median **0.253 seconds**, aggregate **4.09 simulations/second**. The default army clears this fixture too easily for optimizer-quality conclusions.

`benchmarks/search-comparison.json` uses a reduced army and separate held-out scenarios:

| Seed | Algorithm | Candidate evaluations | Held-out three stars / 12 | Mean held-out destruction |
|---|---|---:|---:|---:|
| 61 | Cardinal heuristic | 4 | 5 | 75.0% |
| 61 | Random proposals | 12 | 7 | 87.9% |
| 61 | Incumbent mutation | 12 | 8 | 91.7% |
| 203 | Cardinal heuristic | 4 | 5 | 74.2% |
| 203 | Random proposals | 12 | 6 | 78.8% |
| 203 | Incumbent mutation | 12 | 7 | 78.0% |

Random and mutation receive equal candidate counts; the four-entry heuristic is a cheaper baseline. Only two seeds and a toy model were measured. Mutation's primary outcome improved here while destruction did not always improve; these results do not establish general or real-game superiority. A longer-budget convergence/parallel scaling study remains open.

## Next priorities

1. Assemble an attributed held-out real screenshot set and vet reusable detector weights/licenses before installing a local detector adapter.
2. Build verified current game-stat and behavior packs; expose remaining hardcoded behavioral assumptions as provenance-bearing mechanics.
3. Collect controlled, permitted replay observations and compare movement, cadence, targeting, projectiles and destruction order.
4. Add authentic advanced mechanics behind capability gates and scenario tests, one interaction at a time.
5. Fit and independently validate empirical calibration; add controlled sensitivity experiments and larger benchmark suites.
6. Profile larger, challenging layouts; implement bounded parallel evaluation and test recovery/maximum-duration behavior under load.
