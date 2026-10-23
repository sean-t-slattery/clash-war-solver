import pytest

from backend.domain import Army, DataPack, Layout, OptimizationRequest, Structure, Trap, validate_army, validate_battlefield


def test_overlap_rejected():
    with pytest.raises(ValueError, match="Overlapping"):
        Layout(structures=[Structure(type="cannon", x=1, y=1), Structure(type="storage", x=2, y=2)])


def test_outside_footprint_rejected():
    with pytest.raises(ValueError, match="beyond"):
        Layout(structures=[Structure(x=43, y=42)])


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        Layout(structures=[Structure(id="x", x=1, y=1), Structure(id="x", x=8, y=8)])


def test_trap_requires_evidence():
    with pytest.raises(ValueError): Trap(x=1, y=1, evidence="")


def test_trap_cannot_overlap():
    with pytest.raises(ValueError, match="Trap overlaps"):
        Layout(structures=[Structure(x=1, y=1)], traps=[Trap(x=1, y=1, evidence="observed")])


def test_calibration_cannot_be_collinear():
    with pytest.raises(ValueError, match="collinear"):
        Layout(anchors=[(0, 0), (10, 10), (20, 20)])


def test_three_hour_ceiling(request_model):
    payload = request_model.model_dump()
    payload["budget_seconds"] = 10800.1
    with pytest.raises(ValueError): OptimizationRequest.model_validate(payload)


def test_army_capacities(account, pack):
    with pytest.raises(ValueError, match="exceeds capacity"):
        validate_army(Army(troops={"giant": 17}), account, pack)
    with pytest.raises(ValueError, match="exceeds capacity"):
        validate_army(Army(troops={"giant": 2}, spells={"rage": 3}), account, pack)


def test_unavailable_unit_and_level(account, pack):
    with pytest.raises(ValueError, match="Unsupported"):
        validate_army(Army(troops={"electro_dragon": 1}), account, pack)
    account.troops["giant"] = 20
    with pytest.raises(ValueError, match="No supported statistics"):
        validate_army(Army(troops={"giant": 1}), account, pack)


def test_unreviewed_and_unknown_block_solve(layout, pack):
    layout.structures[0].reviewed = False
    with pytest.raises(ValueError, match="Review"):
        validate_battlefield(layout, pack)
    layout.structures[0].reviewed = True
    layout.structures[1].type = "unknown"
    with pytest.raises(ValueError, match="unresolved"):
        validate_battlefield(layout, pack)


def test_versioned_parameter_requirements(pack):
    obj = pack.model_dump(mode="json")
    del obj["definitions"]["giant"]["stats"]["hp"]["source"]
    with pytest.raises(ValueError): DataPack.model_validate(obj)
    obj = pack.model_dump(mode="json")
    obj["definitions"]["giant"]["stats"]["speed"]["value"] = 0
    with pytest.raises(ValueError): DataPack.model_validate(obj)


def test_pack_and_layout_fixture_are_legal(layout, pack, account, request_model):
    validate_battlefield(layout, pack)
    validate_army(request_model.army, account, pack)
