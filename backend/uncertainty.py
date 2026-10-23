"""Joint, constrained scenario sampling. Priors are assumptions, not observations."""
import math
import random
from dataclasses import dataclass

from backend.domain import Layout, Uncertainty


@dataclass
class Scenario:
    seed: int
    bombs: list[tuple[float, float]]
    defender: str
    level_factors: dict[str, float]
    timing_error: float
    coordinate_error: float


def empty_tiles(layout: Layout):
    occupied = {(x, y) for s in layout.structures
                for x in range(s.x, s.x+s.width) for y in range(s.y, s.y+s.height)}
    known = {(t.x, t.y) for t in layout.traps}
    return [(x, y) for x in range(44) for y in range(44)
            if (x, y) not in occupied and (x, y) not in known]


def trap_weights(layout: Layout):
    defenses = [s for s in layout.structures if s.type in {"cannon", "archer_tower", "mortar", "air_defense"}]
    tiles = empty_tiles(layout)
    weights = [1 + sum(math.exp(-math.hypot(x-s.x-s.width/2, y-s.y-s.height/2)/4)
                       for s in defenses) for x, y in tiles]
    return tiles, weights


def generate(layout: Layout, config: Uncertainty, seed: int) -> Scenario:
    rng = random.Random(seed)
    tiles, weights = trap_weights(layout)
    bombs = [(t.x+.5, t.y+.5) for t in layout.traps if t.status == "confirmed"]
    # A hypothesis is not promoted to evidence. It appears in half the prior scenarios.
    bombs += [(t.x+.5, t.y+.5) for t in layout.traps if t.status == "hypothesis" and rng.random() < .5]
    for _ in range(min(config.unknown_bombs, len(tiles))):
        index = rng.choices(range(len(tiles)), weights=weights, k=1)[0]
        x, y = tiles.pop(index)
        weights.pop(index)
        bombs.append((x+.5, y+.5))
    defender = rng.choice(["none", "ground", "air"]) if config.defender == "mixture" else config.defender
    return Scenario(seed, bombs, defender,
                    {s.id: rng.uniform(1-config.level_jitter, 1+config.level_jitter) for s in layout.structures},
                    config.timing_error, config.coordinate_error)


def summarize(outcomes: list[dict]) -> dict:
    n = len(outcomes)
    successes = sum(o["stars"] == 3 for o in outcomes)
    p = successes/n
    z = 1.95996398454
    center = (p+z*z/(2*n))/(1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    sorted_stars = sorted(o["stars"] for o in outcomes)
    return {"samples": n, "successes": successes, "three_star_rate": p,
            "wilson_interval": [max(0, center-half), min(1, center+half)],
            "expected_stars": sum(o["stars"] for o in outcomes)/n,
            "expected_destruction": sum(o["destruction"] for o in outcomes)/n,
            "timeout_rate": sum(o["timeout"] for o in outcomes)/n,
            "catastrophic_rate": sum(o["stars"] == 0 for o in outcomes)/n,
            "lower_tail_stars": sum(sorted_stars[:max(1, n//5)])/max(1, n//5),
            "mean_duration": sum(o["duration"] for o in outcomes)/n,
            "failure_causes": {reason: sum(o["failure"] == reason for o in outcomes)
                               for reason in {o["failure"] for o in outcomes}},
            "interpretation": "Monte Carlo uncertainty within an uncalibrated approximate model. Wilson interval covers sampling uncertainty only; it is not real-world three-star confidence."}
