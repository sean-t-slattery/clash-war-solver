# Supported model and statistical interpretation

## This is an approximation

The simulator is a research integration baseline. Its unit names and structure categories refer to game concepts, but fixture values are arbitrary assumed test parameters. It is not a reverse-engineered implementation of Clash of Clans. No current Town Hall level is validated for real attack prediction.

Implemented combat numerics live in the pack with provenance. Engine discretization and simplified behavior constants live in source and are pinned by `ENGINE_VERSION`; they are assumptions too. Future work must expose more behavioral constants as versioned mechanic parameters before supporting authentic packs. An input data pack alone cannot make the current behavioral engine high fidelity.

| Mechanic | Implemented behavior | Practical limitation |
|---|---|---|
| Time | Deterministic 0.25 s ticks; up to 180 simulated seconds | Quantized movement and combat; no official timing equivalence |
| Ground routes | Four-neighbor weighted A*, wall/building traversal penalties, wall destruction | Simplified target choice and blocker interaction; no authentic collision/formation/three-target rule |
| Air routes | Straight-line movement to target | No authentic flight/retargeting details |
| Units | Individual HP, position, target, speed, attack cooldown and death | No per-unit animation phase, advanced targeting or troop-specific behaviors |
| Defenses | Range, target modes, cooldown, delayed homing impact and optional splash | No authentic orientation arcs, minimum ranges, burst/chain/ramping mechanics or projectile obstruction |
| Walls | Destructible occupied tiles; excluded from destruction denominator | Weighted path costs are arbitrary; compartment analysis is not exposed |
| Spells | Heal per tick, rage damage/movement multiplier, freeze fire suppression | Simplified radii, stacking and timing; no other spells |
| King | One eight-second damage/movement buff | No summons, equipment, real ability sequence or death/save triggers |
| Traps | One-use ground bombs | Trigger radius/behavior approximate; no air/spring/tornado/skeleton traps |
| Defenders | Simplified Archer or Balloon entity scenario, activated near map center | No authentic Clan Castle placement, capacity, lure, pursuit, mixtures or defensive heroes |
| Outcomes | Town Hall star, 50% star, complete non-wall destruction yields three | No full game rule validation for building counts or eligible structures |
| Replay | Seeded deployments, target/movement/damage/heal/projectile/trap/death/destruction events and one-second frames | Animation is a visualization of the model, not evidence of fidelity |

Pets, equipment, siege, boosted levels, donations, temporary Super Troops, summoned entities, chain effects, complex statuses and conditional instructions are not simulated. The account manager stores fields for future use; search controls do not pretend these mechanics exist. Unsupported selected unit levels and building modes are rejected. Orientation is stored/displayed metadata and has no combat effect.

## Scenario assumptions

- User-confirmed traps require evidence text and appear in every scenario. Hypotheses appear with an assumed 0.5 inclusion rate; observations are never inferred from share links.
- Unknown bomb counts are user-selected illustrative counts, not inferred legal TH limits. Empty-tile placement uses a defensive-proximity weight and sampling without replacement. This is a joint constrained prior, not independent Bernoulli tile probabilities.
- An unknown defending composition is an assumed equal mixture of empty, simplified ground and simplified air scenarios. No population frequency data have been fitted.
- Building HP and damage share a per-building uniform multiplicative perturbation, representing unknown parameters rather than a verified distribution over real levels.
- Deployment time/coordinate errors are uniform within user-selected bounds. Border coordinates are projected back onto the supported legal border. Spell and ability timing errors are similarly perturbed. Execution tolerance labels are assumptions.
- The heatmap shows relative placement weights, not posterior probabilities or confirmed information. No confirmed trap variants are propagated automatically between matching layouts.

## Metrics

Candidates are evaluated on shared search seeds to reduce comparison noise. The objective first compares the sampled three-star fraction. Secondary comparisons penalize zero-star outcomes, compare a coarse lower tail, favor destruction, reduce timeouts, reduce action count and prefer faster completion. There is no statistical equivalence test defining comparable probabilities yet, so tiny search-sample differences can affect ranking.

Finalist evaluation uses a disjoint seed bank and does not affect rank or subsequent proposals. It runs inside the same active-time deadline. Its Wilson score interval is a 95% interval for a Bernoulli success rate **conditional on the assumed scenario generator and approximate combat model**. It addresses Monte Carlo sampling uncertainty only. It excludes mechanics error, outdated stats, wrong priors and selection/experimenter effects. Small scenario counts are deliberately visible.

Defender subgroup summaries are descriptive, with sample counts. They are not causal sensitivity estimates. True trap/Clan Castle sensitivity needs controlled paired ablations and calibrated priors; those are not implemented. Calibration records store observed vs. predicted stars/destruction and report MAE; no fitted correction or real-world probability claim is produced.

Longer searches preserve the strongest complete incumbent under the search ranking. They do not guarantee better true outcomes, higher held-out rates, global optimality, or monotonic mean destruction when the primary objective changes. A wall-clock search may reach different iteration counts across machines. Exact strategy/scenario replay is deterministic on the same engine and numerical runtime.

## Validation needed before real use

1. A held-out, attributed real-image dataset with correct tile coordinates, classifications and levels; measure precision/recall and coordinate error.
2. Controlled, permitted replay observations for movement, cadence, acquisition, projectile timing and destruction order.
3. Version-pinned current statistics with known units/effective dates and explicit gaps.
4. Coverage tests for authentic unit-specific abilities, equipment/pets/siege and all supported defensive interactions.
5. Independent real battles for calibration and evaluation, split by layout/variant and patch to prevent leakage.
6. Challenging benchmark suites, multiple seeds, equal compute budgets, random/heuristic/alternative search comparisons and measured parallel scaling.

The bundled synthetic recognition test achieves exact agreement for its generated image by construction. That result must never be reported as real-screenshot detection accuracy.
