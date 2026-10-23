import pytest

from backend.optimization import propose, rank, run_search, signature, validate_strategy


def test_fixed_army_and_legal_border_actions(request_model, account, pack):
    for i in range(8):
        strategy = propose(request_model, account, pack, i, [])
        validate_strategy(strategy, account, pack)
        assert strategy.army.troops == request_model.army.troops
        assert all(a.x < 0 or a.y < 0 or a.x >= 44 or a.y >= 44 for a in strategy.actions if a.kind == "deploy")


def test_exact_partial_locks(request_model, account, pack):
    request_model.mode = "partial"
    request_model.locked_troops = {"giant": 4}
    for i in range(4, 15):
        strategy = propose(request_model, account, pack, i, [])
        assert strategy.army.troops["giant"] == 4
        validate_strategy(strategy, account, pack)


def test_primary_objective_beats_destruction():
    a = dict(three_star_rate=.8, catastrophic_rate=.1, lower_tail_stars=1, expected_destruction=80, timeout_rate=.1, mean_duration=170)
    b = {**a, "three_star_rate": .7, "expected_destruction": 99}
    assert rank(a, {"actions": []}) > rank(b, {"actions": []})


def test_signature_deterministic(request_model, account, pack):
    a = propose(request_model, account, pack, 0, [])
    b = propose(request_model, account, pack, 0, [])
    assert signature(a) == signature(b)


def test_action_composition_guard(request_model, account, pack):
    strategy = propose(request_model, account, pack, 0, [])
    strategy.actions[0].quantity += 1
    with pytest.raises(ValueError, match="composition"):
        validate_strategy(strategy, account, pack)


def test_anytime_checkpoint_and_independent_validation(request_model, account, layout, pack):
    checkpoints = []
    state = {"iteration": 0, "simulations": 0, "leaders": [], "history": []}
    inputs = {"request": request_model.model_dump(), "layout": layout.model_dump(), "account": account.model_dump(), "pack": pack.model_dump()}
    run_search(inputs, state, lambda cp: checkpoints.append(cp["simulations"]), lambda: False, 8)
    assert checkpoints and state["leaders"] and state["simulations"] >= 2
    assert state["leaders"][0]["validation"] is not None
    assert set(state["leaders"][0]["validation_seeds"]).isdisjoint({request_model.seed+10000+i for i in range(2)})
    assert all(a <= b for a, b in zip(checkpoints, checkpoints[1:]))
