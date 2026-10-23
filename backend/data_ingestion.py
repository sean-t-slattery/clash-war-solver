"""Explicit adapters: official player JSON and normalized, provenance-bearing packs."""
import re

from backend.domain import Account, DataPack


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def official_player(payload: dict) -> Account:
    if not isinstance(payload.get("name"), str) or not isinstance(payload.get("townHallLevel"), int):
        raise ValueError("Expected official player JSON with name and townHallLevel")
    troops, siege, pets = {}, {}, {}
    for item in payload.get("troops", []):
        if item.get("village") != "home": continue
        key = slug(item["name"])
        target = siege if "siege" in key or key in {"wall_wrecker", "battle_blimp", "stone_slammer", "log_launcher", "flame_flinger", "battle_drill"} else troops
        target[key] = item["level"]
    for item in payload.get("pets", []): pets[slug(item["name"])] = item["level"]
    return Account(name=payload["name"], tag=payload.get("tag", ""), town_hall=payload["townHallLevel"],
                   troops=troops, spells={slug(x["name"]): x["level"] for x in payload.get("spells", [])},
                   heroes={slug(x["name"]): x["level"] for x in payload.get("heroes", []) if x.get("village") == "home"},
                   equipment={slug(x["name"]): x["level"] for x in payload.get("heroEquipment", [])}, pets=pets, siege=siege,
                   housing=1, spell_capacity=0,
                   restrictions=[], provenance="official_api; capacities are unknown: set manually before solving")


def discrepancies(a: DataPack, b: DataPack):
    differences = []
    for key in sorted(a.definitions.keys() | b.definitions.keys()):
        left, right = a.definitions.get(key), b.definitions.get(key)
        if left is None or right is None:
            differences.append({"object": key, "parameter": "definition", "old": bool(left), "new": bool(right)})
            continue
        for name in sorted(left.stats.keys() | right.stats.keys()):
            x, y = left.stats.get(name), right.stats.get(name)
            if x is None or y is None or (x.value, x.unit) != (y.value, y.unit):
                differences.append({"object": key, "parameter": name, "old": x.model_dump(mode="json") if x else None,
                                    "new": y.model_dump(mode="json") if y else None})
    return differences
