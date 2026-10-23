"""Archive public source data with a pinned commit, license, digest and discrepancy gaps.

This deliberately stages evidence rather than converting DPS into attack damage or
inventing missing cadence, HP and behavioral rules. No game-client extraction.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx


def acquire(destination: Path, revision="main"):
    base = "https://api.github.com/repos/Statscell/clash-of-clans-data/commits/"
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
        commit = client.get(base+revision)
        commit.raise_for_status()
        sha = commit.json()["sha"]
        raw_root = f"https://raw.githubusercontent.com/Statscell/clash-of-clans-data/{sha}/"
        source = client.get(raw_root+"output/troopUpgradeStats.json")
        source.raise_for_status()
        license_response = client.get(raw_root+"LICENSE")
        license_response.raise_for_status()
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "troopUpgradeStats.json").write_bytes(source.content)
    (destination / "LICENSE.upstream").write_bytes(license_response.content)
    rows = source.json()
    normalized = []
    for obj in rows:
        if obj.get("village") != "home": continue
        for index, value in enumerate(obj.get("dps", [])):
            normalized.append({"object": obj["name"], "level": obj.get("minLevel", 1)+index,
                               "parameter": "dps", "value": value, "unit": "hit_points_per_second",
                               "source": "https://github.com/Statscell/clash-of-clans-data",
                               "source_id": f"{sha}/output/troopUpgradeStats.json#{obj['id']}/dps/{index}",
                               "retrieved": datetime.now(timezone.utc).date().isoformat(),
                               "last_verified": None, "effective_date": None, "game_version": "unverified",
                               "confidence": "community_documented"})
    manifest = {"source": raw_root+"output/troopUpgradeStats.json", "revision": sha,
                "source_commit_time": commit.json()["commit"]["committer"]["date"],
                "retrieved": datetime.now(timezone.utc).isoformat(), "license": "MIT (upstream code/data repository)",
                "sha256": hashlib.sha256(source.content).hexdigest(), "source_objects": len(rows),
                "normalized_dps_records": len(normalized), "simulation_ready": False,
                "gaps": ["No verified effective game patch", "No independent value verification", "Missing per-attack damage / cadence conversion", "Incomplete HP, movement and special behavioral rules"],
                "policy": "Staging only. Unknown verification dates remain null; do not auto-promote into combat packs."}
    (destination / "staged-parameters.json").write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    acquire(Path(sys.argv[1] if len(sys.argv) > 1 else "data/reference/statscell"), sys.argv[2] if len(sys.argv) > 2 else "main")
