"""Small equal-evaluation synthetic benchmark; not a real-game accuracy test."""
import json
from pathlib import Path
from time import monotonic, perf_counter

from backend.combat_simulation import simulate
from backend.domain import Army, OptimizationRequest, Uncertainty
from backend.fixtures import demo_account, demo_layout, synthetic_pack
from backend.optimization import evaluate, propose, rank, validate_strategy


def main():
    layout, account, pack = demo_layout(), demo_account(), synthetic_pack()
    rows = []
    for seed in [61, 203]:
        request = OptimizationRequest(account_id=account.id, base_id=layout.id,
            army=Army(troops={"giant": 4, "archer": 10, "barbarian": 10}, spells={"heal": 1}),
            scenarios=4, seed=seed, uncertainty=Uncertainty(unknown_bombs=5))
        for algorithm in ["cardinal_heuristic", "random_proposals", "incumbent_mutation"]:
            best = None
            start = perf_counter()
            count = 4 if algorithm == "cardinal_heuristic" else 12
            for i in range(count):
                # Cardinal heuristic is evaluated once per side; random/evolution use equal 12-candidate budgets.
                iteration = i if algorithm == "cardinal_heuristic" else i+4
                parents = [best] if best and algorithm == "incumbent_mutation" else []
                candidate = propose(request, account, pack, iteration, parents)
                validate_strategy(candidate, account, pack)
                metrics = evaluate(layout, candidate, pack, request, [seed+10000+j for j in range(4)], monotonic()+120, lambda: False)
                entry = {"strategy": candidate.model_dump(mode="json"), "search": metrics}
                if best is None or rank(metrics, entry["strategy"]) > rank(best["search"], best["strategy"]): best = entry
            search_seconds = perf_counter()-start
            validation = evaluate(layout, __import__('backend.domain',fromlist=['Strategy']).Strategy.model_validate(best["strategy"]),
                                  pack, request, [seed+100000+j for j in range(12)], monotonic()+120, lambda: False)
            rows.append({"seed":seed, "algorithm":algorithm, "candidates":count, "search_simulations":count*4,
                         "search_seconds":search_seconds, "search":best["search"], "heldout":validation})
    result = {"fixture":"synthetic-v1 / reduced army", "interpretation":"Two seeds only. Random and mutation receive equal candidate counts; the cardinal baseline uses four. Not evidence of real-game superiority or parallel scaling.", "results":rows}
    destination = Path(__file__).with_name('search-comparison.json')
    destination.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps([{k:r[k] for k in ['seed','algorithm','candidates','search_seconds']}|{'heldout_destruction':r['heldout']['expected_destruction'],'heldout_three_stars':r['heldout']['successes']} for r in rows],indent=2))


if __name__ == '__main__': main()
