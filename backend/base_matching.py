"""Tile-preserving dihedral registration and type-constrained assignment."""
import hashlib
import json
import math

import numpy as np
from scipy.optimize import linear_sum_assignment

from backend.domain import Layout


def transform(layout, rotation=0, mirror=False):
    rows = []
    for s in layout.structures:
        x, y, w, h = s.x, s.y, s.width, s.height
        angle = s.orientation
        if mirror:
            x = 44-x-w
            if angle is not None: angle = -angle
        for _ in range(rotation):
            x, y, w, h = 44-y-h, x, h, w
            if angle is not None: angle += 90
        rows.append([s.type, s.level, x, y, w, h, s.mode, None if angle is None else angle % 360])
    if rows:
        xmin, ymin = min(r[2] for r in rows), min(r[3] for r in rows)
        for r in rows: r[2], r[3] = r[2]-xmin, r[3]-ymin
    return sorted(rows, key=lambda r: json.dumps(r))


def fingerprint(layout):
    variants = [json.dumps(transform(layout, rot, mirror), separators=(",", ":")) for rot in range(4) for mirror in (False, True)]
    return hashlib.sha256(min(variants).encode()).hexdigest()


def match(query: Layout, candidate: Layout):
    if not query.structures or not candidate.structures: return {"score": 0, "classification": "insufficient_data"}
    exact = query.town_hall == candidate.town_hall and fingerprint(query) == fingerprint(candidate)
    if exact: return {"score": 1, "classification": "visible_layout_exact", "note": "Visible structures only. Hidden traps and defenders are not confirmed."}
    a = transform(query)
    best = 0
    for rotation in range(4):
        for mirror in (False, True):
            b = transform(candidate, rotation, mirror)
            penalty = 0
            for kind in {r[0] for r in a+b}:
                ar, br = [r for r in a if r[0] == kind], [r for r in b if r[0] == kind]
                penalty += abs(len(ar)-len(br))*12
                if not ar or not br: continue
                costs = np.array([[math.hypot(x[2]-y[2], x[3]-y[3])+abs(x[1]-y[1])*2+
                                   abs(x[4]-y[4])+abs(x[5]-y[5])+(x[6:] != y[6:])*2 for y in br] for x in ar])
                rows, cols = linear_sum_assignment(costs)
                penalty += float(costs[rows, cols].sum())
            score = max(0, 1-penalty/(max(len(a), len(b))*12))
            best = max(best, score)
    return {"score": best, "classification": "near_match" if best >= .85 else "similar" if best >= .6 else "weak",
            "note": "Geometric similarity score, not a probability or confirmation of hidden defenses."}
