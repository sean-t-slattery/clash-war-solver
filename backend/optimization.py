"""Anytime evolutionary search with legal proposals and persistent checkpoints."""
import hashlib
import json
import random
from time import monotonic

from backend.combat_simulation import Interrupted, simulate
from backend.domain import Action, Account, Army, DataPack, Layout, OptimizationRequest, Strategy, validate_army
from backend.uncertainty import generate, summarize


def edge(side, position):
    position = max(0, min(43, position))
    return [(position, -1), (45, position), (position, 45), (-1, position)][side % 4]


def rank(metrics, strategy):
    return (metrics["three_star_rate"], -metrics["catastrophic_rate"], metrics["lower_tail_stars"],
            metrics["expected_destruction"], -metrics["timeout_rate"],
            -len(strategy["actions"]), -metrics["mean_duration"])


def signature(strategy):
    obj = strategy.model_dump(mode="json")
    obj.pop("id", None)
    obj.pop("name", None)
    obj["army"].pop("id", None)
    obj["army"].pop("name", None)
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def concept(entry):
    """Retain distinct entry sides and dominant troop families as alternatives."""
    strategy = entry["strategy"]
    first = min((a for a in strategy["actions"] if a["kind"] == "deploy"), key=lambda a: a["time"])
    side = "north" if first["y"] < 0 else "east" if first["x"] >= 44 else "south" if first["y"] >= 44 else "west"
    troops = strategy["army"]["troops"]
    family = "air" if troops.get("balloon", 0)*5 > sum(troops.values()) else "ground"
    return side, family


def validate_strategy(strategy, account, pack):
    validate_army(strategy.army, account, pack)
    deployed, spells, heroes, abilities = {}, {}, set(), set()
    for a in strategy.actions:
        if a.trigger is not None:
            raise ValueError("Conditional actions are not yet simulated")
        if a.kind == "deploy":
            if 0 <= a.x < 44 and 0 <= a.y < 44:
                raise ValueError("Deployments must be in the surrounding deployment area")
            if a.unit in strategy.army.heroes:
                if a.quantity != 1 or a.unit in heroes:
                    raise ValueError("Hero must deploy exactly once")
                heroes.add(a.unit)
            else:
                deployed[a.unit] = deployed.get(a.unit, 0)+a.quantity
        elif a.kind == "spell":
            if not (0 <= a.x < 44 and 0 <= a.y < 44):
                raise ValueError("Spell center must lie inside the grid")
            spells[a.unit] = spells.get(a.unit, 0)+a.quantity
            if a.quantity != 1:
                raise ValueError("Use one action per spell")
        elif a.kind == "ability":
            if a.unit != "barbarian_king" or a.unit not in heroes or a.unit in abilities:
                raise ValueError("Only one simplified King ability after deployment is supported")
            deploy_time = next(x.time for x in strategy.actions if x.kind == "deploy" and x.unit == a.unit)
            if a.time < deploy_time:
                raise ValueError("Ability precedes hero deployment")
            abilities.add(a.unit)
    if deployed != {k: v for k, v in strategy.army.troops.items() if v}:
        raise ValueError("Deployment actions do not match army composition")
    if spells != {k: v for k, v in strategy.army.spells.items() if v} or heroes != set(strategy.army.heroes):
        raise ValueError("Spell or hero actions do not match army")


def propose(request: OptimizationRequest, account: Account, pack: DataPack, iteration: int, leaders: list) -> Strategy:
    rng = random.Random(request.seed+iteration*7919)
    # Keep diverse edge baselines before exploiting incumbents; random restarts avoid duplicates.
    if iteration >= 4 and leaders and rng.random() < .7:
        chosen = rng.choice(leaders[:3])
        strategy = Strategy.model_validate(chosen["strategy"])
        strategy.id = f"candidate-{iteration}"
        strategy.name = f"Refinement {iteration+1}"
        for a in rng.sample(strategy.actions, min(len(strategy.actions), rng.randint(1, 3))):
            a.time = round(max(0, min(130, a.time+rng.uniform(-6, 6))), 2)
            if a.kind == "deploy":
                side = 0 if a.y < 0 else 1 if a.x >= 44 else 2 if a.y >= 44 else 3
                position = a.x if side in {0, 2} else a.y
                a.x, a.y = edge(side, position+rng.uniform(-6, 6))
            elif a.kind == "spell":
                a.x, a.y = max(0, min(43, a.x+rng.uniform(-4, 4))), max(0, min(43, a.y+rng.uniform(-4, 4)))
        for a in strategy.actions:
            if a.kind == "ability":
                a.time = max(a.time, next(x.time for x in strategy.actions if x.kind == "deploy" and x.unit == a.unit))
        return strategy
    army = request.army.model_copy(deep=True)
    if request.mode != "fixed" and iteration >= 4:
        allowed = [k for k, d in pack.definitions.items() if d.kind == "troop" and
                   account.troops.get(k) == d.level and k not in account.restrictions]
        locks = request.locked_troops if request.mode == "partial" else {}
        army.troops = {k: v for k, v in locks.items() if v > 0}
        remaining = account.housing-sum(pack.definitions[k].stat("housing")*v for k, v in army.troops.items())
        while True:
            affordable = [k for k in allowed if pack.definitions[k].stat("housing") <= remaining and k not in locks]
            if not affordable or sum(army.troops.values()) >= 80:
                break
            unit = rng.choice(affordable)
            army.troops[unit] = army.troops.get(unit, 0)+1
            remaining -= pack.definitions[unit].stat("housing")
        validate_army(army, account, pack)
    side = iteration % 4 if iteration < 4 else rng.randrange(4)
    position = 22 if iteration < 4 else rng.uniform(8, 36)
    actions = []
    troops = sorted(army.troops.items(), key=lambda kv: -pack.definitions[kv[0]].stat("hp"))
    for i, (name, count) in enumerate(troops):
        if count:
            x, y = edge(side, position+(i-len(troops)/2)*3)
            actions.append(Action(time=i*2, kind="deploy", unit=name, quantity=count, x=x, y=y,
                                  purpose="Establish entry; protect following units" if i == 0 else "Support the entry and clear structures"))
    for i, name in enumerate(army.heroes):
        x, y = edge(side, position+4)
        actions.append(Action(time=5+i, kind="deploy", unit=name, x=x, y=y, purpose="Support the main push"))
        actions.append(Action(time=35+i, kind="ability", unit=name, x=x, y=y,
                              purpose="Activate simplified eight-second damage and movement buff"))
    spell_number = 0
    for name, count in army.spells.items():
        for _ in range(count):
            # Place along the entry-to-core corridor, not unrelated random map points.
            px, py = edge(side, position)
            weight = .45+spell_number*.1
            actions.append(Action(time=22+spell_number*10, kind="spell", unit=name,
                                  x=max(0, min(43, px*(1-weight)+22*weight)),
                                  y=max(0, min(43, py*(1-weight)+22*weight)),
                                  purpose="Support the predicted entry-to-core route"))
            spell_number += 1
    for action in actions:
        action.tolerance = f"±{request.uncertainty.coordinate_error:g} tile, ±{request.uncertainty.timing_error:g}s (assumed)"
    return Strategy(id=f"candidate-{iteration}", name=["North", "East", "South", "West"][side]+f" entry · {iteration+1}", army=army, actions=actions)


def evaluate(layout, strategy, pack, request, seeds, deadline, control):
    outcomes = []
    for seed in seeds:
        outcomes.append(simulate(layout, strategy, pack, generate(layout, request.uncertainty, seed),
                                 deadline=deadline, control=control))
    metrics = summarize(outcomes)
    metrics["by_defender"] = {kind: summarize([o for o in outcomes if o["scenario_defender"] == kind])
                              for kind in sorted({o["scenario_defender"] for o in outcomes})}
    return metrics


def run_search(inputs, checkpoint, save, control, remaining):
    request = OptimizationRequest.model_validate(inputs["request"])
    account = Account.model_validate(inputs["account"])
    layout = Layout.model_validate(inputs["layout"])
    pack = DataPack.model_validate(inputs["pack"])
    deadline = monotonic()+remaining
    leaders = checkpoint["leaders"]
    seen = set(checkpoint.get("seen", []))
    iteration = checkpoint["iteration"]
    seeds = [request.seed+10000+i for i in range(request.scenarios)]
    evaluation_seconds = checkpoint.get("evaluation_seconds", .1)
    checkpoint["stage"] = "diverse entries" if iteration < 4 else "composition and deployment refinement"
    try:
        while monotonic() < deadline:
            if control(): raise Interrupted()
            # Reserve based on the measured cost of evaluating finalists; no fixed phase percentages.
            reserve = max(.05, evaluation_seconds*(len(leaders)*2+1))
            if leaders and deadline-monotonic() <= reserve:
                break
            start = monotonic()
            candidate = propose(request, account, pack, iteration, leaders)
            validate_strategy(candidate, account, pack)
            key = signature(candidate)
            iteration += 1
            if key in seen:
                checkpoint["iteration"] = iteration
                continue
            metrics = evaluate(layout, candidate, pack, request, seeds, deadline, control)
            evaluation_seconds = max(.001, monotonic()-start)
            seen.add(key)
            entry = {"signature": key, "strategy": candidate.model_dump(mode="json"), "search": metrics,
                     "validation": None, "validation_seeds": [], "replay": None}
            ranked = sorted([*leaders, entry], key=lambda e: rank(e["search"], e["strategy"]), reverse=True)
            concepts = set()
            leaders = []
            for contender in ranked:
                key_concept = concept(contender)
                if key_concept not in concepts:
                    leaders.append(contender)
                    concepts.add(key_concept)
                if len(leaders) == 3: break
            checkpoint.update(iteration=iteration, leaders=leaders, seen=sorted(seen),
                              evaluation_seconds=evaluation_seconds, stage="diverse entries" if iteration < 4 else "composition and deployment refinement")
            checkpoint["simulations"] += len(seeds)
            checkpoint["history"].append({"iteration": iteration, "three_star_rate": leaders[0]["search"]["three_star_rate"],
                                          "destruction": leaders[0]["search"]["expected_destruction"]})
            checkpoint["history"] = checkpoint["history"][-250:]
            save(checkpoint)
        checkpoint["stage"] = "independent finalist evaluation"
        save(checkpoint)
        # Hold-out estimates never influence candidate generation or winner ranking.
        heldout = [request.seed+1000000+i for i in range(request.scenarios*2)]
        for entry in leaders:
            strategy = Strategy.model_validate(entry["strategy"])
            if entry.get("validation") is None:
                entry["validation"] = evaluate(layout, strategy, pack, request, heldout, deadline, control)
                entry["validation_seeds"] = heldout
                checkpoint["simulations"] += len(heldout)
                save(checkpoint)
            if entry.get("replay") is None:
                entry["replay"] = simulate(layout, strategy, pack, generate(layout, request.uncertainty, heldout[0]),
                                           record=True, deadline=deadline, control=control)
                checkpoint["simulations"] += 1
                save(checkpoint)
    except Interrupted:
        pass
    checkpoint["stage"] = "stopped" if control() else "finished"
    save(checkpoint)
