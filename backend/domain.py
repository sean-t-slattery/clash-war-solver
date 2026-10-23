"""Versioned domain contracts. No HTTP, persistence, or UI dependencies."""
from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def uid() -> str:
    return uuid4().hex


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Parameter(Model):
    value: float
    unit: str
    source: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    last_verified: date
    game_version: str
    effective_date: date
    confidence: Literal["officially_verified", "independently_observed", "community_documented",
                        "experimentally_estimated", "assumed", "unknown"]


class Definition(Model):
    name: str
    level: int = Field(ge=1, le=200)
    kind: Literal["troop", "hero", "spell", "building", "wall", "trap"]
    movement: Literal["ground", "air"] = "ground"
    preference: Literal["any", "defense"] = "any"
    targets: Literal["ground", "air", "both"] = "both"
    width: int = Field(default=1, ge=1, le=8)
    height: int = Field(default=1, ge=1, le=8)
    stats: dict[str, Parameter]

    def stat(self, key: str, default: float = 0) -> float:
        return self.stats[key].value if key in self.stats else default


class DataPack(Model):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    label: str
    synthetic: bool
    definitions: dict[str, Definition]

    @model_validator(mode="after")
    def validate_stats(self):
        if not self.definitions or len(self.definitions) > 3000:
            raise ValueError("A pack needs 1–3000 definitions")
        for key, d in self.definitions.items():
            required = {
                "troop": {"hp", "damage", "cadence", "speed", "range", "housing"},
                "hero": {"hp", "damage", "cadence", "speed", "range"},
                "building": {"hp", "damage", "cadence", "range", "projectile_speed", "splash"},
                "wall": {"hp"}, "trap": {"damage", "radius"},
                "spell": {"housing", "radius", "duration", "power"},
            }[d.kind]
            if not required.issubset(d.stats):
                raise ValueError(f"{key}: missing parameters {required - d.stats.keys()}")
            for name, param in d.stats.items():
                if param.value < 0 or param.value > 1e7:
                    raise ValueError(f"{key}.{name}: parameter outside supported bounds")
                if name in {"hp", "cadence", "speed", "housing", "projectile_speed"} and param.value <= 0:
                    raise ValueError(f"{key}.{name} must be positive")
            if d.kind == "spell" and key not in {"heal", "rage", "freeze"}:
                raise ValueError("Only heal, rage and freeze spell behavior is implemented")
        return self


class Account(Model):
    id: str = Field(default_factory=uid)
    name: str = Field(min_length=1, max_length=100)
    tag: str = ""
    town_hall: int = Field(default=8, ge=1, le=100)
    troops: dict[str, int] = Field(default_factory=dict)
    spells: dict[str, int] = Field(default_factory=dict)
    heroes: dict[str, int] = Field(default_factory=dict)
    pets: dict[str, int] = Field(default_factory=dict)
    equipment: dict[str, int] = Field(default_factory=dict)
    siege: dict[str, int] = Field(default_factory=dict)
    super_troops: list[str] = Field(default_factory=list)
    housing: int = Field(default=80, ge=1, le=1000)
    spell_capacity: int = Field(default=4, ge=0, le=100)
    clan_castle_capacity: int = Field(default=0, ge=0, le=100)
    reinforcements: dict[str, int] = Field(default_factory=dict)
    restrictions: list[str] = Field(default_factory=list)
    boosts: dict[str, str] = Field(default_factory=dict)
    provenance: str = "manual"

    @model_validator(mode="after")
    def valid_levels(self):
        for inventory in (self.troops, self.spells, self.heroes, self.pets, self.equipment, self.siege):
            if any(level < 1 or level > 200 for level in inventory.values()):
                raise ValueError("Inventory levels must be between 1 and 200")
        return self


class Army(Model):
    id: str = Field(default_factory=uid)
    name: str = "Custom army"
    troops: dict[str, int] = Field(default_factory=dict)
    spells: dict[str, int] = Field(default_factory=dict)
    heroes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def counts(self):
        if any(n < 0 or n > 200 for n in [*self.troops.values(), *self.spells.values()]):
            raise ValueError("Counts must be between 0 and 200")
        if len(self.heroes) != len(set(self.heroes)):
            raise ValueError("Duplicate heroes")
        return self


class Structure(Model):
    id: str = Field(default_factory=uid)
    type: str = "unknown"
    level: int = Field(default=1, ge=1, le=200)
    x: int = Field(ge=0, le=43)
    y: int = Field(ge=0, le=43)
    width: int = Field(default=3, ge=1, le=8)
    height: int = Field(default=3, ge=1, le=8)
    orientation: float | None = None
    mode: str = "default"
    confidence: float = Field(default=1, ge=0, le=1)
    reviewed: bool = True
    source: str = "manual"


class Trap(Model):
    id: str = Field(default_factory=uid)
    x: int = Field(ge=0, le=43)
    y: int = Field(ge=0, le=43)
    type: Literal["bomb"] = "bomb"
    evidence: str = Field(min_length=3, max_length=1000)
    status: Literal["confirmed", "hypothesis"] = "hypothesis"


class Layout(Model):
    schema_version: Literal[1] = 1
    id: str = Field(default_factory=uid)
    name: str = Field(default="Untitled layout", min_length=1, max_length=100)
    town_hall: int = Field(default=8, ge=1, le=100)
    grid_size: Literal[44] = 44
    structures: list[Structure] = Field(default_factory=list, max_length=600)
    traps: list[Trap] = Field(default_factory=list, max_length=100)
    asset_id: str | None = None
    source: str = "manual"
    share_link: str | None = None
    revision: int = Field(default=0, ge=0)
    # Pixel anchors for grid origin, +x end, +y end. User-verified, not guessed.
    anchors: list[tuple[float, float]] | None = None

    @model_validator(mode="after")
    def geometry(self):
        occupied: dict[tuple[int, int], str] = {}
        ids = set()
        for s in self.structures:
            if s.id in ids:
                raise ValueError("Duplicate structure IDs")
            ids.add(s.id)
            if s.x + s.width > 44 or s.y + s.height > 44:
                raise ValueError(f"{s.type} extends beyond the 44×44 grid")
            for x in range(s.x, s.x + s.width):
                for y in range(s.y, s.y + s.height):
                    if (x, y) in occupied:
                        raise ValueError(f"Overlapping structures: {s.id} and {occupied[x, y]}")
                    occupied[x, y] = s.id
        trap_tiles = set()
        for t in self.traps:
            if (t.x, t.y) in occupied or (t.x, t.y) in trap_tiles:
                raise ValueError("Trap overlaps an occupied tile")
            trap_tiles.add((t.x, t.y))
        if self.anchors is not None:
            if len(self.anchors) != 3:
                raise ValueError("Exactly three calibration anchors are required")
            a, b, c = self.anchors
            determinant = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            if abs(determinant) < 100:
                raise ValueError("Calibration anchors are collinear or too close")
        return self


class Uncertainty(Model):
    unknown_bombs: int = Field(default=3, ge=0, le=12)
    defender: Literal["none", "ground", "air", "mixture"] = "mixture"
    level_jitter: float = Field(default=0.1, ge=0, le=0.5)
    timing_error: float = Field(default=0.8, ge=0, le=5)
    coordinate_error: float = Field(default=0.5, ge=0, le=2)
    notes: str = "Illustrative scenario prior; no population calibration."


class Action(Model):
    time: float = Field(ge=0, le=180)
    kind: Literal["deploy", "spell", "ability"]
    unit: str
    quantity: int = Field(default=1, ge=1, le=200)
    x: float = Field(ge=-3, le=47)
    y: float = Field(ge=-3, le=47)
    purpose: str = ""
    tolerance: str = "±1 tile, ±1 second (assumed)"
    trigger: str | None = None


class Strategy(Model):
    id: str = Field(default_factory=uid)
    name: str
    army: Army
    actions: list[Action] = Field(max_length=100)


class OptimizationRequest(Model):
    account_id: str
    base_id: str
    army: Army
    pack_id: str = "synthetic-v1"
    mode: Literal["fixed", "flexible", "partial"] = "fixed"
    locked_troops: dict[str, int] = Field(default_factory=dict)
    budget_seconds: float = Field(default=300, ge=1, le=10800)
    scenarios: int = Field(default=6, ge=2, le=64)
    seed: int = Field(default=2026, ge=0, le=2**31-1)
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)


def validate_army(army: Army, account: Account, pack: DataPack) -> None:
    housing = spells = 0
    if not any(army.troops.values()):
        raise ValueError("Choose at least one troop")
    if sum(army.troops.values()) > 200:
        raise ValueError("This simulator supports at most 200 deployed troops")
    for category, units in (("troops", army.troops), ("spells", army.spells),
                            ("heroes", dict.fromkeys(army.heroes, 1))):
        for name, count in units.items():
            if not count:
                continue
            if name in account.restrictions:
                raise ValueError(f"{name} is restricted for this account")
            definition = pack.definitions.get(name)
            kind = {"troops": "troop", "spells": "spell", "heroes": "hero"}[category]
            if not definition or definition.kind != kind:
                raise ValueError(f"Unsupported {category}: {name}")
            if category == "heroes" and name != "barbarian_king":
                raise ValueError("Only the simplified Barbarian King hero is implemented")
            if getattr(account, category).get(name) != definition.level:
                raise ValueError(f"No supported statistics for account's {name} level; pack requires level {definition.level}")
            if category == "troops":
                housing += count * definition.stat("housing")
            if category == "spells":
                spells += count * definition.stat("housing")
    if housing > account.housing or spells > account.spell_capacity:
        raise ValueError(f"Army exceeds capacity: housing {housing}/{account.housing}, spells {spells}/{account.spell_capacity}")


def validate_battlefield(layout: Layout, pack: DataPack) -> None:
    if not layout.structures or sum(s.type == "town_hall" for s in layout.structures) != 1:
        raise ValueError("A battlefield requires exactly one Town Hall")
    for s in layout.structures:
        d = pack.definitions.get(s.type)
        if not d or d.kind not in {"building", "wall"}:
            raise ValueError(f"Unsupported or unresolved building: {s.type}")
        if not s.reviewed:
            raise ValueError(f"Review low-confidence detection {s.id} before solving")
        if s.level != d.level or (s.width, s.height) != (d.width, d.height):
            raise ValueError(f"{s.type}: footprint or level is unsupported by this data pack")
        if s.mode != "default":
            raise ValueError(f"{s.type}: non-default defensive mode is not implemented")
