import argparse
import json
import os
import statistics
from pathlib import Path
from time import perf_counter


def main():
    parser = argparse.ArgumentParser(description="War Workbench local research tools")
    parser.add_argument("command", choices=["serve", "init", "benchmark", "example"])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        uvicorn.run("backend.app:create_app", factory=True, host="127.0.0.1", port=args.port, workers=1)
        return
    if args.command == "init":
        from backend.app import create_app
        app = create_app(workers=False)
        print("Initialized", app.state.store.path)
        return
    from backend.fixtures import demo_account, demo_army, demo_layout, synthetic_pack
    from backend.domain import OptimizationRequest
    from backend.optimization import propose
    from backend.uncertainty import Uncertainty, generate
    from backend.combat_simulation import simulate
    layout, pack, account = demo_layout(), synthetic_pack(), demo_account()
    request = OptimizationRequest(account_id=account.id, base_id=layout.id, army=demo_army())
    strategy = propose(request, account, pack, 0, [])
    if args.command == "example":
        outcome = simulate(layout, strategy, pack, generate(layout, Uncertainty(), 101), record=True)
        output = Path(args.output or "runtime/example-replay.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"strategy": strategy.model_dump(mode="json"), "simulation": outcome}, indent=2), encoding="utf-8")
        print(output)
        return
    durations, outcomes = [], []
    for seed in range(10):
        start = perf_counter()
        outcome = simulate(layout, strategy, pack, generate(layout, Uncertainty(), seed))
        durations.append(perf_counter()-start)
        outcomes.append({"seed": seed, "stars": outcome["stars"], "destruction": outcome["destruction"]})
    result = {"engine": "approx-entity-0.1", "fixture": "synthetic-v1", "runs": 10,
              "median_seconds": statistics.median(durations), "simulations_per_second": len(durations)/sum(durations),
              "python": __import__("sys").version, "platform": __import__("platform").platform(), "outcomes": outcomes}
    print(json.dumps(result, indent=2))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
