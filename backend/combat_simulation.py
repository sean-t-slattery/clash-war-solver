"""Deterministic entity simulation, independent of the web application.

Fixed 0.25 s ticks, attack cadence, delayed projectiles, A* ground routing,
wall destruction, air movement, targeting, splash, healing/rage/freeze,
one simplified hero ability, joint traps and simplified defending entities.
All mechanics are approximations; no equivalence to the real game is claimed.
"""
from __future__ import annotations

import heapq
import math
import random
from dataclasses import dataclass, field
from time import monotonic
from typing import Callable

from backend.domain import DataPack, Layout, Strategy
from backend.uncertainty import Scenario

ENGINE_VERSION = "approx-entity-0.1"
DT = .25


class Interrupted(Exception):
    """A deadline or job control interrupted simulation at a tick boundary."""


@dataclass
class Entity:
    id: str
    type: str
    x: float
    y: float
    hp: float
    max_hp: float
    damage: float
    cadence: float
    reach: float
    speed: float = 0
    air: bool = False
    width: int = 0
    height: int = 0
    targets: str = "both"
    preference: str = "any"
    splash: float = 0
    projectile_speed: float = 20
    ready: float = 0
    target: str | None = None
    path: list = field(default_factory=list)
    path_version: int = -1
    ability_until: float = 0


def distance(unit: Entity, target: Entity) -> float:
    # Units are points, buildings are axis-aligned footprints.
    dx = max(abs(unit.x-target.x)-target.width/2, 0)
    dy = max(abs(unit.y-target.y)-target.height/2, 0)
    return math.hypot(dx, dy)


def ground_path(unit, target, occupied):
    """Weighted A*: destructible blockers cost extra, but remain attackable."""
    start = (max(-3, min(46, int(unit.x))), max(-3, min(46, int(unit.y))))
    queue = [(0, 0, start)]
    costs = {start: 0}
    previous = {}
    goal = start
    while queue:
        _, cost, cell = heapq.heappop(queue)
        if cost != costs[cell]:
            continue
        px, py = cell[0]+.5, cell[1]+.5
        dx = max(abs(px-target.x)-target.width/2, 0)
        dy = max(abs(py-target.y)-target.height/2, 0)
        if math.hypot(dx, dy) <= max(.8, unit.reach):
            goal = cell
            break
        for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = cell[0]+ox, cell[1]+oy
            if not (-3 <= nxt[0] <= 46 and -3 <= nxt[1] <= 46):
                continue
            blocker = occupied.get(nxt)
            extra = 0 if blocker is None or blocker.id == target.id else (5 if blocker.type == "wall" else 18)
            new_cost = cost+1+extra
            if new_cost < costs.get(nxt, 1e10):
                costs[nxt] = new_cost
                previous[nxt] = cell
                heuristic = math.hypot(nxt[0]+.5-target.x, nxt[1]+.5-target.y)
                heapq.heappush(queue, (new_cost+heuristic, new_cost, nxt))
    route = []
    while goal != start:
        route.append(goal)
        goal = previous[goal]
    return route[::-1]


def simulate(layout: Layout, strategy: Strategy, pack: DataPack, scenario: Scenario,
             record: bool = False, deadline: float | None = None,
             control: Callable[[], bool] | None = None) -> dict:
    rng = random.Random(scenario.seed)
    buildings = []
    for s in layout.structures:
        d = pack.definitions[s.type]
        factor = scenario.level_factors.get(s.id, 1)
        hp = d.stat("hp")*factor
        buildings.append(Entity(s.id, s.type, s.x+s.width/2, s.y+s.height/2,
                                hp, hp, d.stat("damage")*factor, d.stat("cadence", 1),
                                d.stat("range"), width=s.width, height=s.height,
                                targets=d.targets, splash=d.stat("splash"),
                                projectile_speed=d.stat("projectile_speed", 20)))
    units: list[Entity] = []
    defenders: list[Entity] = []
    defenders_spawned = False
    occupied = {(x, y): b for b in buildings
                for x in range(int(b.x-b.width/2), int(b.x+b.width/2))
                for y in range(int(b.y-b.height/2), int(b.y+b.height/2))}
    version = 0
    events, frames, projectiles, spells = [], [], [], []
    destruction_order = []
    bombs = list(scenario.bombs)
    pending = []
    for i, action in enumerate(strategy.actions):
        a = action.model_copy(deep=True)
        a.time = max(0, a.time+rng.uniform(-scenario.timing_error, scenario.timing_error))
        a.x += rng.uniform(-scenario.coordinate_error, scenario.coordinate_error)
        a.y += rng.uniform(-scenario.coordinate_error, scenario.coordinate_error)
        # Human coordinate error cannot turn an edge deployment into an illegal interior deployment.
        if a.kind == "deploy":
            if action.x < 0: a.x = min(-.1, a.x)
            if action.x >= 44: a.x = max(44.1, a.x)
            if action.y < 0: a.y = min(-.1, a.y)
            if action.y >= 44: a.y = max(44.1, a.y)
        pending.append((a.time, i, a))
    pending.sort(key=lambda item: (item[0], item[1]))
    total = sum(b.type != "wall" for b in buildings)
    t = 0.0

    def event(kind, **data):
        if record:
            events.append({"time": round(t, 2), "kind": kind, **data})

    def hit(victim, damage, source):
        nonlocal version
        if victim.hp <= 0:
            return
        victim.hp -= damage
        event("damage", source=source, target=victim.id, amount=round(damage, 2))
        if victim.hp <= 0:
            event("destroy" if victim in buildings else "death", id=victim.id, type=victim.type)
            if victim in buildings:
                version += 1
                destruction_order.append({"id": victim.id, "type": victim.type, "time": t})
                for key in [cell for cell, b in occupied.items() if b is victim]:
                    del occupied[key]

    for tick in range(721):
        t = tick*DT
        if deadline is not None and monotonic() >= deadline:
            raise Interrupted()
        if tick % 16 == 0 and control and control():
            raise Interrupted()
        while pending and pending[0][0] <= t:
            _, index, action = pending.pop(0)
            d = pack.definitions.get(action.unit)
            if action.kind == "deploy":
                for n in range(action.quantity):
                    hp = d.stat("hp")
                    units.append(Entity(f"u{index}-{n}", action.unit, action.x, action.y, hp, hp,
                                        d.stat("damage"), d.stat("cadence"), d.stat("range"),
                                        speed=d.stat("speed"), air=d.movement == "air", preference=d.preference, targets=d.targets))
                event("deploy", unit=action.unit, quantity=action.quantity, x=action.x, y=action.y)
            elif action.kind == "spell":
                spells.append((action.unit, action.x, action.y, t+d.stat("duration"), d))
                event("spell", unit=action.unit, x=action.x, y=action.y)
            elif action.kind == "ability":
                for u in units:
                    if u.type == action.unit and u.hp > 0:
                        u.ability_until = t+8
                        event("ability", id=u.id, unit=u.type)
        alive = [u for u in units if u.hp > 0]
        live_buildings = [b for b in buildings if b.hp > 0]
        if not any(b.type != "wall" for b in live_buildings):
            break
        if not alive and not any(a.kind == "deploy" for _, _, a in pending):
            break
        spells = [s for s in spells if s[3] > t]
        if not defenders_spawned and scenario.defender != "none" and any(math.hypot(u.x-22, u.y-22) < 10 for u in alive):
            defenders_spawned = True
            kind = "archer" if scenario.defender == "ground" else "balloon"
            d = pack.definitions.get(kind)
            if d:
                for i in range(3 if kind == "archer" else 1):
                    hp = d.stat("hp")
                    defenders.append(Entity(f"cc{i}", kind, 22+i*.3, 22, hp, hp,
                                            d.stat("damage"), d.stat("cadence"), d.stat("range"),
                                            speed=d.stat("speed"), air=d.movement == "air"))
                event("defenders", composition=kind, count=len(defenders))
        for impact in projectiles[:]:
            due, victim, damage, source, radius, team = impact
            if due <= t:
                projectiles.remove(impact)
                if radius > 0:
                    for v in team:
                        if v.hp > 0 and math.hypot(v.x-victim.x, v.y-victim.y) <= radius:
                            hit(v, damage, source)
                else:
                    hit(victim, damage, source)
        for bx, by in bombs[:]:
            if any(not u.air and math.hypot(u.x-bx, u.y-by) <= 1.2 for u in alive if u.hp > 0):
                bombs.remove((bx, by))
                event("trap", x=bx, y=by)
                d = pack.definitions.get("bomb")
                if d:
                    for u in alive:
                        if not u.air and math.hypot(u.x-bx, u.y-by) <= d.stat("radius"):
                            hit(u, d.stat("damage"), "bomb")
        for u in alive:
            if u.hp <= 0:
                continue
            rage = 1.6 if u.ability_until > t else 1.0
            for name, sx, sy, _, d in spells:
                if math.hypot(u.x-sx, u.y-sy) <= d.stat("radius"):
                    if name == "heal":
                        old = u.hp
                        u.hp = min(u.max_hp, u.hp+d.stat("power")*DT)
                        if u.hp > old: event("heal", id=u.id, amount=u.hp-old)
                    if name == "rage": rage = max(rage, d.stat("power"))
            enemies = [b for b in live_buildings if b.hp > 0 and b.type != "wall"] + [d for d in defenders if d.hp > 0 and
                        (u.targets == "both" or (u.targets == "air") == d.air)]
            target = next((b for b in live_buildings+defenders if b.id == u.target and b.hp > 0), None)
            if target is None:
                preferred = [b for b in enemies if u.preference == "defense" and b.damage > 0]
                if not enemies: continue
                target = min(preferred or enemies, key=lambda b: (distance(u, b), b.id))
                u.target, u.path_version = target.id, -1
                event("target", id=u.id, target=target.id)
            if distance(u, target) > u.reach:
                destination = (target.x, target.y)
                if not u.air:
                    if u.path_version != version:
                        u.path = ground_path(u, target, occupied)
                        u.path_version = version
                    if u.path:
                        cell = u.path[0]
                        blocker = occupied.get(cell)
                        if blocker and blocker.hp > 0 and blocker.id != target.id:
                            if distance(u, blocker) <= max(u.reach, 1):
                                target = blocker
                            else:
                                destination = cell[0]+.5, cell[1]+.5
                        else:
                            destination = cell[0]+.5, cell[1]+.5
                if distance(u, target) > max(u.reach, .8):
                    dx, dy = destination[0]-u.x, destination[1]-u.y
                    length = math.hypot(dx, dy)
                    move = min(length, u.speed*DT*(1.15 if rage > 1 else 1))
                    if length:
                        u.x += dx/length*move
                        u.y += dy/length*move
                    if u.path and math.hypot(u.x-u.path[0][0]-.5, u.y-u.path[0][1]-.5) < .1:
                        u.path.pop(0)
                    if record and tick % 4 == 0: event("move", id=u.id, x=round(u.x, 2), y=round(u.y, 2))
                    continue
            if u.ready <= t:
                hit(target, u.damage*rage, u.id)
                u.ready = t+u.cadence
        for b in [*live_buildings, *defenders]:
            if b.hp <= 0 or b.damage <= 0:
                continue
            if any(name == "freeze" and math.hypot(b.x-sx, b.y-sy) <= d.stat("radius") for name, sx, sy, _, d in spells):
                continue
            targets = [u for u in alive if u.hp > 0 and
                       (b.targets == "both" or (b.targets == "air") == u.air)]
            if not targets: continue
            victim = next((u for u in targets if u.id == b.target and math.hypot(u.x-b.x, u.y-b.y) <= b.reach), None)
            if victim is None:
                victim = min(targets, key=lambda u: (math.hypot(u.x-b.x, u.y-b.y), u.id))
                b.target = victim.id
            separation = math.hypot(victim.x-b.x, victim.y-b.y)
            if b in defenders and separation > b.reach:
                step = min(b.speed*DT, separation)
                b.x += (victim.x-b.x)/separation*step
                b.y += (victim.y-b.y)/separation*step
            elif separation <= b.reach and b.ready <= t:
                due = t+separation/max(1, b.projectile_speed)
                projectiles.append((due, victim, b.damage, b.id, b.splash, alive[:]))
                event("projectile", source=b.id, target=victim.id, impact=round(due, 2))
                b.ready = t+b.cadence
        if record and tick % 4 == 0:
            frames.append({"time": t, "units": [{"id": u.id, "type": u.type, "x": round(u.x, 2), "y": round(u.y, 2), "hp": round(u.hp/u.max_hp, 3)} for u in alive if u.hp > 0],
                           "destroyed": [b.id for b in buildings if b.hp <= 0],
                           "spells": [{"type": n, "x": x, "y": y, "radius": d.stat("radius")} for n, x, y, _, d in spells]})
    destroyed = sum(b.hp <= 0 and b.type != "wall" for b in buildings)
    destruction = 100*destroyed/max(1, total)
    th_down = any(b.type == "town_hall" and b.hp <= 0 for b in buildings)
    stars = 3 if destroyed == total else int(destruction >= 50)+int(th_down)
    timeout = t >= 180 and stars < 3
    if record:
        frames.append({"time": t, "units": [{"id": u.id, "type": u.type, "x": round(u.x, 2), "y": round(u.y, 2),
                                               "hp": round(u.hp/u.max_hp, 3)} for u in units if u.hp > 0],
                       "destroyed": [b.id for b in buildings if b.hp <= 0], "spells": []})
        event("termination", stars=stars, destruction=destruction, remaining_time=180-t)
    return {"engine_version": ENGINE_VERSION, "seed": scenario.seed, "stars": stars,
            "destruction": destruction, "duration": t, "timeout": timeout,
            "failure": "success" if stars == 3 else "timeout" if timeout else "army_destroyed",
            "events": events, "frames": frames, "destruction_order": destruction_order,
            "remaining_bombs": len(bombs), "scenario_defender": scenario.defender}
