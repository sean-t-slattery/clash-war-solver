"""One CPU worker, persisted queue, controls, crash recovery and wall-clock watchdog."""
import json
import multiprocessing as mp
import os
import threading
import time
from pathlib import Path

import psutil

from backend.optimization import run_search
from backend.storage import Store, now


def finish(store, key, status, error=None, active_override=None):
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM jobs WHERE id=?", (key,)).fetchone()
        if row is None or row["status"] != "running": return
        budget = json.loads(row["inputs"])["request"]["budget_seconds"]
        active = min(budget, active_override if active_override is not None else row["active_seconds"]+max(0, now()-(row["segment_started"] or now())))
        requested = row["requested"]
        final_status = "cancelled" if requested == "cancel" else "paused" if requested == "pause" else status
        if active >= budget and final_status == "paused": final_status = "completed"
        db.execute("UPDATE jobs SET status=?, requested=NULL, active_seconds=?,segment_started=NULL,updated=?,error=? WHERE id=?",
                   (final_status, active, now(), error, key))


def worker_main(path, key):
    store = Store(path)
    job = store.job(key, include_inputs=True)
    budget = job["inputs"]["request"]["budget_seconds"]
    remaining = max(0, budget-job["active_seconds"])
    started = time.monotonic()
    last_control = 0
    requested = False

    def control():
        nonlocal last_control, requested
        if time.monotonic()-last_control > .1:
            with store.connection() as db:
                row = db.execute("SELECT requested,status FROM jobs WHERE id=?", (key,)).fetchone()
                requested = not row or bool(row[0]) or row[1] != "running"
            last_control = time.monotonic()
        return requested

    def save(checkpoint):
        with store.connection() as db:
            db.execute("UPDATE jobs SET checkpoint=?,updated=? WHERE id=? AND status='running'",
                       (json.dumps(checkpoint), now(), key))
    try:
        run_search(job["inputs"], job["checkpoint"], save, control, remaining)
        finish(store, key, "completed", active_override=job["active_seconds"]+time.monotonic()-started)
    except BaseException as exc:
        finish(store, key, "failed", f"{type(exc).__name__}: {exc}", active_override=job["active_seconds"]+time.monotonic()-started)


class Manager:
    def __init__(self, store: Store):
        self.store = store
        self.stop_event = threading.Event()
        self.process = None
        self.key = None
        self.thread = None
        self.lock_file = None
        self.process_deadline = None
        self.segment_monotonic = None
        self.segment_active = 0

    def start(self):
        # Kernel lock is released automatically after crashes. Prevent duplicate schedulers.
        self.lock_file = open(self.store.path.parent / "worker.lock", "a+b")
        self.lock_file.seek(0)
        self.lock_file.write(b"0")
        self.lock_file.flush()
        self.lock_file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock_file.close()
            raise RuntimeError("Another application owns this runtime directory")
        for job in self.store.jobs():
            if job["status"] == "running":
                # Conservatively charge time since last start, including downtime.
                finish(self.store, job["id"], "paused", "Recovered after interruption; resume to continue")
        self.thread = threading.Thread(target=self.loop, daemon=True, name="solver-supervisor")
        self.thread.start()

    def loop(self):
        while not self.stop_event.wait(.1):
            if self.process is not None:
                job = self.store.job(self.key, include_inputs=True)
                budget = job["inputs"]["request"]["budget_seconds"]
                if self.process.is_alive() and time.monotonic() >= self.process_deadline:
                    self.process.terminate()
                    self.process.join(timeout=2)
                    finish(self.store, self.key, "completed", active_override=budget)
                if not self.process.is_alive():
                    self.process.join()
                    current = self.store.job(self.key)
                    if current["status"] == "running":
                        finish(self.store, self.key, "paused", "Worker exited unexpectedly; checkpoint retained", active_override=self.segment_active+time.monotonic()-self.segment_monotonic)
                    self.process.close()
                    self.process, self.key = None, None
                continue
            with self.store.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
                if row:
                    key = row["id"]
                    db.execute("UPDATE jobs SET status='running',segment_started=?,updated=? WHERE id=? AND status='queued'", (now(), now(), key))
            if row:
                self.key = key
                self.segment_monotonic = time.monotonic()
                self.segment_active = row["active_seconds"]
                self.process_deadline = self.segment_monotonic+max(0, json.loads(row["inputs"])["request"]["budget_seconds"]-row["active_seconds"])
                self.process = mp.get_context("spawn").Process(target=worker_main, args=(str(self.store.path), key), daemon=True)
                try:
                    self.process.start()
                except Exception as exc:
                    finish(self.store, key, "failed", str(exc))
                    self.process, self.key = None, None

    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=3)
        if self.process:
            self.process.terminate()
            self.process.join(timeout=3)
            finish(self.store, self.key, "paused", "Application stopped; checkpoint retained", active_override=self.segment_active+time.monotonic()-self.segment_monotonic)
            self.process.close()
        if self.lock_file:
            self.lock_file.close()

    def resources(self):
        result = {"worker_pid": None, "worker_cpu_percent": 0, "worker_memory_mb": 0,
                  "system_cpu_percent": psutil.cpu_percent(), "system_memory_percent": psutil.virtual_memory().percent,
                  "parallel_workers": 1}
        if self.process and self.process.is_alive():
            try:
                proc = psutil.Process(self.process.pid)
                # OS CPU time / elapsed provides a meaningful process lifetime average.
                times = proc.cpu_times()
                result.update(worker_pid=proc.pid, worker_cpu_percent=round(100*(times.user+times.system)/max(.01, now()-proc.create_time()), 1),
                              worker_memory_mb=round(proc.memory_info().rss/1024**2, 1))
            except (psutil.NoSuchProcess, psutil.AccessDenied): pass
        return result


def command(store, key, action):
    if action not in {"pause", "resume", "cancel"}: raise ValueError("Unknown job command")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM jobs WHERE id=?", (key,)).fetchone()
        if row is None: raise KeyError(key)
        status = row[0]
        if action == "resume":
            if status != "paused": raise ValueError("Only paused jobs can resume")
            db.execute("UPDATE jobs SET status='queued',requested=NULL,error=NULL,updated=? WHERE id=?", (now(), key))
        elif status == "running":
            db.execute("UPDATE jobs SET requested=?,updated=? WHERE id=?", (action, now(), key))
        elif status in {"queued", "paused"}:
            db.execute("UPDATE jobs SET status=?,requested=NULL,updated=? WHERE id=?",
                       ("cancelled" if action == "cancel" else "paused", now(), key))
        else:
            raise ValueError("Job is already terminal")
