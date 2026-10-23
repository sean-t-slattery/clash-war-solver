from time import monotonic

import pytest

from backend.combat_simulation import Entity, Interrupted, ground_path, simulate
from backend.domain import Action, Army, Layout, Strategy, Structure, Uncertainty
from backend.optimization import propose
from backend.uncertainty import generate, summarize


def test_seeded_replay_is_identical(layout, account, pack, request_model):
    strategy = propose(request_model, account, pack, 0, [])
    scenario = generate(layout, request_model.uncertainty, 19)
    a = simulate(layout, strategy, pack, scenario, record=True)
    b = simulate(layout, strategy, pack, scenario, record=True)
    assert a == b
    assert a["frames"] and a["events"]
    assert {e["kind"] for e in a["events"]} >= {"deploy", "target", "move", "projectile", "damage", "destroy", "spell", "ability"}


def test_wall_destruction_and_ground_path(pack):
    layout = Layout(structures=[Structure(id="th", type="town_hall", x=2, y=18, width=4, height=4),
                                *[Structure(id=f"w{y}", type="wall", x=0, y=y, width=1, height=1) for y in range(44)]])
    strategy = Strategy(name="Wall", army=Army(troops={"giant": 1}), actions=[Action(kind="deploy", time=0, unit="giant", x=-1, y=20)])
    scenario = generate(layout, Uncertainty(unknown_bombs=0, defender="none", level_jitter=0, timing_error=0, coordinate_error=0), 1)
    outcome = simulate(layout, strategy, pack, scenario, record=True)
    assert any(d["type"] == "wall" for d in outcome["destruction_order"])
    assert outcome["stars"] == 3


def test_attack_cadence_not_continuous_dps(pack):
    layout = Layout(structures=[Structure(id="th", type="town_hall", x=0, y=0, width=4, height=4)])
    strategy = Strategy(name="Cadence", army=Army(troops={"barbarian": 1}), actions=[Action(kind="deploy", time=0, unit="barbarian", x=-.5, y=2)])
    scenario = generate(layout, Uncertainty(unknown_bombs=0, defender="none", level_jitter=0, timing_error=0, coordinate_error=0), 4)
    result = simulate(layout, strategy, pack, scenario, record=True)
    times = [e["time"] for e in result["events"] if e["kind"] == "damage" and e["source"] == "u0-0"]
    assert times[0] == 0
    assert all(b-a >= pack.definitions["barbarian"].stat("cadence") for a, b in zip(times, times[1:]))


def test_defensive_projectile_delay(layout, pack, account, request_model):
    strategy = propose(request_model, account, pack, 0, [])
    result = simulate(layout, strategy, pack, generate(layout, Uncertainty(), 2), record=True)
    launch = next(e for e in result["events"] if e["kind"] == "projectile")
    assert launch["impact"] > launch["time"]
    hits = [e for e in result["events"] if e["kind"] == "damage" and e["source"] == launch["source"]]
    assert hits and hits[0]["time"] >= launch["impact"]-.01


def test_deadline_and_control_interrupt(layout, pack, account, request_model):
    strategy = propose(request_model, account, pack, 0, [])
    scenario = generate(layout, Uncertainty(), 2)
    with pytest.raises(Interrupted): simulate(layout, strategy, pack, scenario, deadline=monotonic()-1)
    with pytest.raises(Interrupted): simulate(layout, strategy, pack, scenario, control=lambda: True)


def test_joint_traps_valid_and_deterministic(layout):
    config = Uncertainty(unknown_bombs=12)
    a = generate(layout, config, 1); b = generate(layout, config, 1)
    assert a == b
    assert len(a.bombs) == len(set(a.bombs)) == 12
    for x, y in a.bombs:
        assert not any(s.x <= x < s.x+s.width and s.y <= y < s.y+s.height for s in layout.structures)


def test_wilson_interval_not_degenerate_at_all_success():
    data = [{"stars": 3, "timeout": False, "destruction": 100, "duration": 80, "failure": "success"}]*4
    summary = summarize(data)
    assert summary["three_star_rate"] == 1
    assert .4 < summary["wilson_interval"][0] < 1
    assert summary["wilson_interval"][1] == pytest.approx(1)
