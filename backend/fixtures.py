"""Original synthetic fixtures. Values deliberately are NOT claimed game statistics."""
import json
from pathlib import Path

import cv2
import numpy as np

from backend.domain import Account, Army, DataPack, Definition, Layout, Parameter, Structure

PALETTE = {"town_hall": (80, 170, 240), "cannon": (210, 160, 90),
           "archer_tower": (160, 100, 210), "mortar": (80, 210, 170),
           "air_defense": (210, 100, 130), "storage": (100, 200, 220), "wall": (160, 170, 180)}
ANCHORS = [(480., 40.), (876., 238.), (84., 238.)]


def synthetic_pack():
    defs = {}

    def add(key, name, kind, stats, **kwargs):
        units = {"hp": "hit_points", "damage": "hit_points_per_attack", "cadence": "seconds",
                 "speed": "tiles_per_second", "range": "tiles", "projectile_speed": "tiles_per_second",
                 "splash": "tiles", "radius": "tiles", "duration": "seconds", "housing": "housing",
                 "power": "model_specific"}
        params = {k: Parameter(value=v, unit=units[k], source="Original synthetic test fixture; not game data",
                              source_id=f"fixtures/synthetic-v1/{key}/{k}", last_verified="2026-10-23",
                              effective_date="2026-10-23", game_version="synthetic-v1", confidence="assumed")
                  for k, v in stats.items()}
        defs[key] = Definition(name=name, level=1, kind=kind, stats=params, **kwargs)

    add("barbarian", "Barbarian", "troop", dict(hp=180, damage=35, cadence=1, speed=2.4, range=1, housing=1))
    add("archer", "Archer", "troop", dict(hp=75, damage=28, cadence=1, speed=2.4, range=4, housing=1))
    add("giant", "Giant", "troop", dict(hp=1100, damage=65, cadence=1.8, speed=1.4, range=1, housing=5), preference="defense")
    add("balloon", "Balloon", "troop", dict(hp=430, damage=145, cadence=3, speed=1.2, range=1, housing=5), movement="air", preference="defense")
    add("barbarian_king", "Barbarian King", "hero", dict(hp=2400, damage=130, cadence=1.2, speed=2, range=1))
    for key, power, duration in [("heal", 35, 12), ("rage", 1.7, 12), ("freeze", 0, 5)]:
        add(key, key.title(), "spell", dict(housing=2 if key != "freeze" else 1, radius=4, duration=duration, power=power))
    for key, hp, damage, cadence, reach, splash, targets, width in [
        ("town_hall", 2600, 0, 1, 0, 0, "both", 4),
        ("cannon", 1100, 85, 1, 9, 0, "ground", 3),
        ("archer_tower", 950, 70, 1, 10, 0, "both", 3),
        ("mortar", 900, 110, 4, 12, 2, "ground", 3),
        ("air_defense", 1000, 135, 1.5, 10, 0, "air", 3),
        ("storage", 1200, 0, 1, 0, 0, "both", 3),
    ]:
        add(key, key.replace("_", " ").title(), "building",
            dict(hp=hp, damage=damage, cadence=cadence, range=reach, splash=splash, projectile_speed=14),
            width=width, height=width, targets=targets)
    add("wall", "Wall", "wall", dict(hp=500))
    add("bomb", "Bomb", "trap", dict(damage=120, radius=2.5))
    return DataPack(id="synthetic-v1", label="Synthetic research fixture · NOT live game statistics", synthetic=True, definitions=defs)


def demo_layout():
    structures = []
    for i, (kind, x, y) in enumerate([
        ("town_hall", 20, 20), ("cannon", 12, 14), ("cannon", 29, 27),
        ("archer_tower", 29, 14), ("archer_tower", 12, 27), ("mortar", 20, 12),
        ("air_defense", 21, 29), ("storage", 5, 20), ("storage", 35, 20),
        ("storage", 20, 5), ("storage", 20, 36),
    ]):
        size = 4 if kind == "town_hall" else 3
        structures.append(Structure(id=f"b{i}", type=kind, x=x, y=y, width=size, height=size, source="synthetic_fixture"))
    for x in range(18, 27):
        for y in (18, 26):
            if x != 22:
                structures.append(Structure(id=f"w{x}-{y}", type="wall", x=x, y=y, width=1, height=1, source="synthetic_fixture"))
    return Layout(id="demo-layout", name="The Crossroads · synthetic fixture", source="synthetic_fixture", structures=structures, anchors=ANCHORS)


def demo_account():
    return Account(id="demo-account", name="Research account", tag="DEMO", town_hall=8,
                   troops={k: 1 for k in ["barbarian", "archer", "giant", "balloon"]},
                   spells={k: 1 for k in ["heal", "rage", "freeze"]}, heroes={"barbarian_king": 1},
                   housing=80, spell_capacity=4, provenance="synthetic_fixture")


def demo_army():
    return Army(id="demo-army", name="Ground entry", troops={"giant": 8, "archer": 20, "barbarian": 20},
                spells={"heal": 1, "rage": 1}, heroes=["barbarian_king"])


def render_fixture(layout, destination):
    image = np.full((500, 960, 3), (24, 35, 28), dtype=np.uint8)
    a = np.array(ANCHORS[0]); vx = (np.array(ANCHORS[1])-a)/44; vy = (np.array(ANCHORS[2])-a)/44
    def point(x, y): return (a+vx*x+vy*y).round().astype(int)
    cv2.fillConvexPoly(image, np.array([point(0, 0), point(44, 0), point(44, 44), point(0, 44)]), (48, 70, 48))
    for s in layout.structures:
        inset = .13
        vertices = np.array([point(s.x+inset, s.y+inset), point(s.x+s.width-inset, s.y+inset),
                             point(s.x+s.width-inset, s.y+s.height-inset), point(s.x+inset, s.y+s.height-inset)])
        cv2.fillConvexPoly(image, vertices, PALETTE[s.type])
    cv2.putText(image, "SYNTHETIC FIXTURE / NOT A GAME SCREENSHOT", (200, 480), cv2.FONT_HERSHEY_SIMPLEX, .6, (200, 215, 200), 1)
    cv2.imwrite(str(destination), image)


def initialize(store, asset_dir: Path, fixture_dir: Path):
    fixture_dir.mkdir(parents=True, exist_ok=True)
    pack = synthetic_pack()
    if not store.get("game-data", pack.id): store.put("game-data", pack.model_dump(mode="json"), immutable=True)
    if not store.get("accounts", "demo-account"): store.put("accounts", demo_account().model_dump(mode="json"))
    if not store.get("armies", "demo-army"): store.put("armies", demo_army().model_dump(mode="json"))
    layout = demo_layout()
    for name, obj in [("layout.json", layout), ("account.json", demo_account()), ("army.json", demo_army()), ("synthetic-pack.json", pack)]:
        (fixture_dir / name).write_text(obj.model_dump_json(indent=2), encoding="utf-8")
    if not (fixture_dir / "synthetic-base.png").exists(): render_fixture(layout, fixture_dir / "synthetic-base.png")
    if not store.get("bases", "demo-layout"):
        store.put("bases", layout.model_dump(mode="json"))
