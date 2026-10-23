"""Loopback-only FastAPI application with an independent process supervisor."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import zipfile
from time import monotonic
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.base_matching import match
from backend.computer_vision import decode_image, reconstruct
from backend.data_ingestion import discrepancies, official_player
from backend.domain import (Account, Army, DataPack, Layout, Model, OptimizationRequest, Strategy, Structure,
                            Uncertainty, uid, validate_army, validate_battlefield)
from backend.fixtures import initialize
from backend.optimization import validate_strategy
from backend.reporting import report
from backend.storage import Conflict, Store, now
from backend.uncertainty import generate, trap_weights
from backend.workers import Manager, command

ROOT = Path(__file__).resolve().parent.parent


class Reconstruction(Model):
    mode: str = "contours"
    anchors: list[tuple[float, float]] | None = None


class Control(Model):
    action: str


class PlayerImport(Model):
    player: dict


class SimulationRequest(Model):
    account_id: str
    base_id: str
    pack_id: str = "synthetic-v1"
    strategy: Strategy
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)
    seed: int = Field(default=1, ge=0, le=2**31-1)


class OfficialFetch(Model):
    tag: str = Field(pattern=r"^#?[0289PYLQGRJCUV]{3,20}$")


class Calibration(Model):
    id: str = Field(default_factory=uid)
    source: str = Field(min_length=3)
    pack_id: str
    observed_stars: int = Field(ge=0, le=3)
    predicted_stars: float = Field(ge=0, le=3)
    observed_destruction: float = Field(ge=0, le=100)
    predicted_destruction: float = Field(ge=0, le=100)
    notes: str = ""


def create_app(data_dir=None, workers=True):
    runtime = Path(data_dir or os.environ.get("WAR_DATA_DIR") or ROOT / "runtime")
    runtime.mkdir(parents=True, exist_ok=True)
    assets, exports = runtime / "assets", runtime / "exports"
    assets.mkdir(exist_ok=True); exports.mkdir(exist_ok=True)
    store = Store(runtime / "war.sqlite3")
    store.migrate()
    initialize(store, assets, ROOT / "data" / "fixtures")
    manager = Manager(store)

    @asynccontextmanager
    async def lifespan(app):
        if workers: manager.start()
        yield
        if workers: manager.stop()

    app = FastAPI(title="War Attack Research Workbench", version="0.1.0", lifespan=lifespan)
    app.state.store, app.state.manager = store, manager
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and request.method not in {"GET", "HEAD", "OPTIONS"}:
            parsed = urlsplit(origin)
            if parsed.netloc != request.headers.get("host") or parsed.scheme not in {"http", "https"}:
                return JSONResponse({"detail": "Cross-origin writes are disabled"}, status_code=403)
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 16*1024*1024):
            return JSONResponse({"detail": "Request body exceeds 16 MB"}, status_code=413)
        return await call_next(request)

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc): return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ValueError)
    async def value_handler(request, exc): return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def key_handler(request, exc): return JSONResponse({"detail": "Resource not found"}, status_code=404)

    def require(kind, key):
        data = store.get(kind, key)
        if data is None: raise HTTPException(404, f"{kind} record not found")
        return data

    def job_required(key):
        data = store.job(key, include_inputs=True)
        if data is None: raise HTTPException(404, "Job not found")
        return data

    @app.get("/api/system/status")
    def health():
        return {"status": "ok", "schema_version": 1, "engine": "approx-entity-0.1", "runtime": str(runtime),
                "packs": [{"id": p["id"], "label": p["label"]} for p in store.list("game-data")],
                "resources": manager.resources(), "calibration": "uncalibrated"}

    @app.get("/api/accounts", response_model=list[Account])
    def accounts(): return store.list("accounts")

    @app.post("/api/accounts", response_model=Account)
    def save_account(account: Account): return store.put("accounts", account.model_dump(mode="json"))

    @app.post("/api/accounts/import", response_model=Account)
    def import_player(payload: PlayerImport):
        account = official_player(payload.player)
        return store.put("accounts", account.model_dump(mode="json"))

    @app.post("/api/accounts/import-official", response_model=Account)
    async def import_official(payload: OfficialFetch):
        token = os.environ.get("COC_API_TOKEN", "")
        if not token: raise HTTPException(409, "Set COC_API_TOKEN in the server environment or import saved official player JSON")
        try:
            async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
                response = await client.get("https://api.clashofclans.com/v1/players/"+quote("#"+payload.tag.lstrip("#"), safe=""),
                                            headers={"Authorization": "Bearer "+token})
            if response.status_code != 200:
                raise HTTPException(502, f"Official API returned HTTP {response.status_code}; check token and IP access")
            return import_player(PlayerImport(player=response.json()))
        except httpx.HTTPError:
            raise HTTPException(502, "Official API connection failed")

    @app.get("/api/armies", response_model=list[Army])
    def armies(): return store.list("armies")

    @app.post("/api/armies", response_model=Army)
    def save_army(army: Army): return store.put("armies", army.model_dump(mode="json"))

    @app.get("/api/game-data", response_model=list[DataPack])
    def packs(): return store.list("game-data")

    @app.post("/api/game-data", response_model=DataPack)
    def import_pack(pack: DataPack): return store.put("game-data", pack.model_dump(mode="json"), immutable=True)

    @app.get("/api/game-data/discrepancies")
    def compare_data(left: str, right: str):
        return discrepancies(DataPack.model_validate(require("game-data", left)), DataPack.model_validate(require("game-data", right)))

    @app.get("/api/units")
    def units(pack_id: str = "synthetic-v1"): return require("game-data", pack_id)["definitions"]

    @app.get("/api/game-data/staging")
    def staging():
        path = ROOT / "data" / "reference" / "statscell" / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status": "No staged source snapshot"}

    @app.get("/api/bases", response_model=list[Layout])
    def bases(): return store.list("bases")

    @app.post("/api/bases", response_model=Layout)
    def save_base(layout: Layout): return store.put("bases", layout.model_dump(mode="json"))

    @app.get("/api/bases/{key}", response_model=Layout)
    def get_base(key: str): return require("bases", key)

    @app.get("/api/bases/{key}/revisions", response_model=list[Layout])
    def revisions(key: str): return store.revisions(key)

    @app.post("/api/bases/analyze")
    async def analyze(file: UploadFile = File(), mode: str = Form("manual"), anchors: str = Form("null")):
        raw = await file.read(12*1024*1024+1)
        image = await asyncio.to_thread(decode_image, raw)
        key = uid()
        # Re-encode decoded pixels, never serve original active content.
        import cv2
        await asyncio.to_thread(cv2.imwrite, str(assets / f"{key}.png"), image)
        anchor_data = json.loads(anchors)
        if anchor_data is not None:
            Layout(anchors=anchor_data)
        result = await asyncio.to_thread(reconstruct, image, mode, anchor_data)
        layout = Layout(name=(file.filename or "Uploaded base")[:100], asset_id=key, source="screenshot",
                        structures=result["structures"], anchors=result["anchors"])
        return {"layout": save_base(layout), "warnings": result["warnings"]}

    @app.post("/api/bases/{key}/reconstruct")
    def reconstruct_base(key: str, options: Reconstruction):
        layout = Layout.model_validate(require("bases", key))
        if not layout.asset_id: raise ValueError("Layout has no screenshot")
        if options.anchors is not None: Layout(anchors=options.anchors)
        raw = asset_path(layout.asset_id).read_bytes()
        result = reconstruct(decode_image(raw), options.mode, options.anchors or layout.anchors)
        layout.structures = [Structure.model_validate(s) for s in result["structures"]]
        layout.anchors = result["anchors"]
        return {"layout": save_base(Layout.model_validate(layout.model_dump())), "warnings": result["warnings"]}

    @app.get("/api/bases/{key}/matches")
    def matches(key: str):
        layout = Layout.model_validate(require("bases", key))
        rows = [{"id": b["id"], "name": b["name"], **match(layout, Layout.model_validate(b))}
                for b in store.list("bases") if b["id"] != key]
        return sorted(rows, key=lambda r: r["score"], reverse=True)[:10]

    @app.get("/api/bases/{key}/traps")
    def traps(key: str):
        layout = Layout.model_validate(require("bases", key))
        tiles, weights = trap_weights(layout)
        peak = max(weights, default=1)
        return {"observations": [t.model_dump() for t in layout.traps],
                "heatmap": [{"x": x, "y": y, "weight": round(w/peak, 2)} for (x, y), w in zip(tiles, weights)],
                "interpretation": "Relative assumed placement weights. Not marginal probabilities or confirmed trap locations."}

    @app.post("/api/defensive-scenarios")
    def scenarios(base_id: str, config: Uncertainty, seed: int = 1):
        from dataclasses import asdict
        return asdict(generate(Layout.model_validate(require("bases", base_id)), config, seed))

    @app.post("/api/optimizations")
    def optimize(payload: OptimizationRequest):
        account = Account.model_validate(require("accounts", payload.account_id))
        layout = Layout.model_validate(require("bases", payload.base_id))
        pack = DataPack.model_validate(require("game-data", payload.pack_id))
        validate_army(payload.army, account, pack)
        validate_battlefield(layout, pack)
        if payload.mode == "partial":
            if not payload.locked_troops or any(k not in payload.army.troops or n < 0 or n > payload.army.troops[k] for k, n in payload.locked_troops.items()):
                raise ValueError("Partial locks must be counts from the selected army")
        key = uid()
        inputs = {"request": payload.model_dump(mode="json"), "account": account.model_dump(mode="json"),
                  "layout": layout.model_dump(mode="json"), "pack": pack.model_dump(mode="json"),
                  "engine_version": "approx-entity-0.1", "created": now()}
        inputs["sha256"] = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        store.create_job(key, inputs)
        return {"id": key, "status": "queued"}

    @app.post("/api/simulations")
    async def preview_simulation(payload: SimulationRequest):
        from backend.combat_simulation import Interrupted, simulate
        account = Account.model_validate(require("accounts", payload.account_id))
        layout = Layout.model_validate(require("bases", payload.base_id))
        pack = DataPack.model_validate(require("game-data", payload.pack_id))
        validate_battlefield(layout, pack)
        validate_strategy(payload.strategy, account, pack)
        scenario = generate(layout, payload.uncertainty, payload.seed)
        try:
            outcome = await asyncio.to_thread(simulate, layout, payload.strategy, pack, scenario, True, monotonic()+3)
        except Interrupted:
            raise HTTPException(422, "Diagnostic simulation exceeded three seconds; use an optimization worker job")
        data = {"id": uid(), "outcome": outcome, "inputs": payload.model_dump(mode="json"),
                "layout": layout.model_dump(mode="json"), "pack": pack.model_dump(mode="json")}
        return store.put("simulations", data)

    @app.get("/api/simulations")
    def simulations(): return store.list("simulations")

    @app.get("/api/optimizations")
    def jobs(): return [compact(job) for job in store.jobs()]

    def compact(job):
        for leader in job["checkpoint"]["leaders"]:
            leader.pop("replay", None)
        return job

    @app.get("/api/optimizations/{key}")
    def get_job(key: str):
        job = store.job(key)
        if job is None: raise HTTPException(404, "Job not found")
        job["resources"] = manager.resources()
        return compact(job)

    @app.post("/api/optimizations/{key}/control")
    def control(key: str, payload: Control):
        command(store, key, payload.action)
        return get_job(key)

    @app.get("/api/optimizations/{key}/events")
    async def events(key: str, request: Request):
        job_required(key)
        async def stream():
            while not await request.is_disconnected():
                data = get_job(key)
                yield "data: "+json.dumps(data)+"\n\n"
                if data["status"] in {"completed", "cancelled", "failed", "paused"}: break
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.get("/api/optimizations/{key}/results")
    def results(key: str):
        job = job_required(key)
        job["resources"] = manager.resources()
        return job

    @app.get("/api/optimizations/{key}/report", response_class=HTMLResponse)
    def export_report(key: str): return report(job_required(key))

    @app.get("/api/attack-plans/{key}")
    def attack_plan(key: str): return job_required(key)

    @app.get("/api/fixtures/{name}")
    def fixture(name: str):
        if name not in {"synthetic-base.png", "layout.json", "account.json", "army.json", "synthetic-pack.json"}:
            raise HTTPException(404, "Fixture not found")
        return FileResponse(ROOT / "data" / "fixtures" / name)

    def asset_path(key):
        if not re.fullmatch(r"[a-f0-9]{32}", key): raise HTTPException(404, "Asset not found")
        path = assets / f"{key}.png"
        if not path.exists(): raise HTTPException(404, "Asset not found")
        return path

    @app.get("/api/assets/{key}")
    def asset(key: str): return FileResponse(asset_path(key), media_type="image/png")

    @app.get("/api/calibration")
    def calibration():
        rows = store.list("calibration")
        n = len(rows)
        return {"observations": rows, "count": n,
                "stars_mae": sum(abs(r["predicted_stars"]-r["observed_stars"]) for r in rows)/n if n else None,
                "destruction_mae": sum(abs(r["predicted_destruction"]-r["observed_destruction"]) for r in rows)/n if n else None,
                "status": "Observations only; no probability calibration has been fitted"}

    @app.post("/api/calibration", response_model=Calibration)
    def add_calibration(observation: Calibration): return store.put("calibration", observation.model_dump(mode="json"))

    @app.get("/api/backup")
    def backup():
        key = uid()
        database = exports / f"{key}.sqlite3"
        store.backup(database)
        archive = exports / f"{key}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(database, "war.sqlite3")
            for path in assets.glob("*.png"): z.write(path, "assets/"+path.name)
        database.unlink()
        return FileResponse(archive, filename="war-workbench-backup.zip", media_type="application/zip")

    dist = ROOT / "apps" / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    else:
        @app.get("/", response_class=HTMLResponse)
        def setup_hint(): return "<h1>War Workbench API is running</h1><p>Build apps/web to serve the interface. See README.</p><a href='/docs'>API documentation</a>"
    return app
