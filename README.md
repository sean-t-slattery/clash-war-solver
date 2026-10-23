# War Workbench

A local Windows application for reproducible Clash of Clans attack-planning research. React/TypeScript browser interface, FastAPI, SQLite, an independent entity simulator, and a persistent process-based anytime optimizer.

**This is a functioning research prototype, not the full high-fidelity platform in the project brief.** The bundled combat pack is an original synthetic fixture with assumed values. It does not contain verified current game statistics. There is no trained real-game building detector or empirical outcome calibration. Never interpret its simulated three-star rate as a probability of winning a real War attack.

## Start on Windows

Requires Python **3.12+**, Node.js **22.12+**, and **pnpm 10+**. The scripts also recognize the bundled Codex Python/pnpm runtime when present. No GPU, cloud account, Redis or paid service is required.

From this repository in PowerShell:

```powershell
.\scripts\start.ps1
```

First run creates `.venv`, installs the pinned dependencies, builds the frontend and initializes the database. Open **http://127.0.0.1:8000**. Stop with Ctrl+C. Subsequent starts reuse the installation and production build.

If your PowerShell policy blocks scripts, run this command for this invocation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

To select an installed Python or pnpm explicitly:

```powershell
.\scripts\setup.ps1 -Python 'C:\path\to\python.exe' -Pnpm 'C:\path\to\pnpm.cmd'
```

Setup does not overwrite user profiles, alter execution policy persistently, install global packages or send screenshots outside the machine. Installation needs internet access; the application then works offline except explicitly requested official API imports.

## Try the complete workflow

1. Keep **Research account** selected. It has synthetic level-one capabilities and an 80-housing army.
2. Open **Base analyzer**. Click **Try the synthetic recognition fixture**. This uploads a generated test image to the local backend and recognizes its colored structures. It is explicitly separate from real screenshot analysis.
3. Review the reconstructed 27 objects. Select a structure to inspect it, use Move or edit X/Y, and use Undo if needed. Mark the classified structures reviewed and save.
4. Click **Search local layouts**. The uploaded fixture should match the seeded layout as `visible_layout_exact`; this says nothing about hidden traps or defenders.
5. Open **Attack planner**. Choose fixed, flexible, or partially locked troops; select spells and the simplified King; configure defensive assumptions. For a short demonstration, select **30 sec / Smoke test**.
6. Start optimization. **Live solver** shows actual worker time, simulation count, incumbent candidates, convergence and measured resources. Pause/resume or stop while preserving completed evaluations.
7. Open **Attack results**. Compare up to three distinct entry concepts. Inspect the numbered map, model trajectories, replay timeline, destruction order and chronological action table.
8. Save the JSON bundle or open **Standalone report**. The HTML is self-contained and can be printed to PDF from the browser. Reopen the saved experiment from Overview after restarting.

For a real screenshot, upload in **Real screenshot / manual reconstruction** mode, calibrate the three grid corners in order, and manually place/classify structures. Optional contour proposals are uncertain, unclassified shapes. Review is mandatory before solving. Ordinary screenshots do not receive invented building labels.

## Implemented scope

- Persistent account capabilities, saved armies, structured layout JSON imports/exports, layout revisions, collision validation, manual grid editor, screenshot storage and affine alignment.
- Versioned combat packs with per-value provenance, immutable pack IDs, discrepancy review and a reproducible Statscell evidence acquisition adapter.
- Tile-preserving rotation/reflection layout matching, type-constrained Hungarian near matching, evidence-bearing bomb markers and constrained joint trap scenarios.
- Fixed-tick individual entities, weighted A* ground routes, destructible walls, air movement, range/cadence/retargeting, delayed defensive projectiles and splash, healing/rage/freeze, a simplified King buff, bomb activation and simplified defender entities.
- Legal deployment/timing search, flexible troop counts, exact partial troop locks, common search scenarios, lexicographic ranking, diversity by entry concept, independent finalist samples, deterministic replay and event logs.
- SQLite job queue, separate worker process, live SSE, cancellation, pause/resume, checkpoints, conservative crash recovery, resource reporting and a monotonic parent watchdog. One local worker; parallel evaluation is not implemented.
- Calibration observation storage and descriptive prediction errors; database-and-assets backup; standalone HTML and JSON reports; typed API contracts and `/docs`.

Unsupported: trained real-screenshot classification, automatic grid/level/orientation recognition, complete modern units/TH rules, authentic pathfinding/targeting/projectile mechanics, equipment effects, pets, siege machines, summoned units, chain effects, defensive heroes, advanced Clan Castle interactions, conditional instructions, native proprietary village-export parsing and fitted real-world calibration. Inventory fields for unsupported capabilities are stored, not simulated. No in-game controls exist.

## Tests and examples

```powershell
.\scripts\test.ps1
.\.venv\Scripts\python.exe -m backend.cli benchmark --output benchmarks\local.json
.\.venv\Scripts\python.exe -m backend.cli example --output runtime\example-replay.json
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe benchmarks\compare_search.py
```

The executed test results and measured benchmark are in [STATUS.md](docs/STATUS.md), `benchmarks/tests.xml` and `benchmarks/initial.json`. The fixture image, layout, account, army and pack are under `data/fixtures/`. Tests cover deterministic events, cadence, projectile delay, wall destruction, placement/capacity validation, CV fixture accuracy, geometric matching, uncertainty, solver controls, persistence, backups and recovery. The short deadline test exercises the same budget cap code as three-hour runs; a three-hour soak test has not been run.

## Data and account imports

The official API adapter can import saved player JSON or fetch `/v1/players/{tag}` using `COC_API_TOKEN` from the **server environment**. Copy `.env.example` to `.env` and set your own token if needed. It is never sent to the frontend or committed. Missing capacities are set to restrictive sentinels and described as unknown; edit them manually. Imported levels must have matching supported combat definitions before solving. No levels are silently extrapolated.

`data/reference/statscell/` contains an attributed, commit-pinned public snapshot and 1,649 staged DPS records. **Staging is not simulation readiness.** Verification/effective dates remain null when unknown. Missing cadence/HP/behavior data are not fabricated or converted into damage by guesswork. Refresh it explicitly with:

```powershell
.\.venv\Scripts\python.exe scripts\acquire_statscell.py data\reference\statscell
```

This refresh updates the staging directory only. To preserve an earlier snapshot, choose a different destination directory. Combat pack imports require complete normalized parameters and a new ID; imported packs are not automatically selected.

## Development and storage

`backend/domain.py` and the engine have no dependency on FastAPI. `backend/app.py` owns HTTP adapters; `backend/storage.py` owns SQLite. The frontend is a thin API client with an SVG editor. See [ARCHITECTURE.md](docs/ARCHITECTURE.md), [RESEARCH.md](docs/RESEARCH.md), [MODEL.md](docs/MODEL.md) and [STATUS.md](docs/STATUS.md).

SQLite schema migration version 1 runs automatically (`PRAGMA user_version`). Data are in `runtime/war.sqlite3`; screenshots in `runtime/assets/`; exports in `runtime/exports/`. Override with `WAR_DATA_DIR`. Job inputs freeze the account, layout revision, data pack, request and engine version, with a SHA-256 digest. A backup ZIP includes the database and screenshots. To restore, stop the application and extract the backup into a new runtime directory, then point `WAR_DATA_DIR` to it.

For frontend hot reload, run the backend as above and `pnpm --dir apps/web dev` in a second terminal. Vite proxies `/api` to the local backend, preserving the request Host/origin. Rebuild with `pnpm --dir apps/web build` before using the production bundle again.

Optional: `docker compose up --build` (not validated on the current host). Compose publishes the port on host loopback and persists a named volume. The native Windows installation is the tested path.

This material is unofficial and is not endorsed by Supercell. See [Supercell's Fan Content Policy](https://supercell.com/en/fan-content-policy/). No proprietary game artwork or third-party engine code is bundled. Public upstream data retain their included license and attribution.
