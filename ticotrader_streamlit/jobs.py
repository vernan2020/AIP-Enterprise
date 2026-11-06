"""Single-process-at-a-time queue, shared bounded cache and isolated job execution."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psutil


def isolated(query, settings, timeout=180, memory_mb=600, command=None):
    # A separate Python entry point avoids re-running Streamlit's __main__ on spawn.
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(root), str(root / "src")))
    for name in (
        "OPENBLAS_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        environment[name] = "1"
    with tempfile.TemporaryDirectory(prefix="atlas-job-") as directory:
        output = Path(directory) / "result.json"
        process = subprocess.Popen(
            (command or [sys.executable, "-m", "ticotrader_streamlit.worker"]) + [str(output)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            cwd=root,
        )
        started = time.monotonic()
        try:
            process.stdin.write(json.dumps({"query": query, "settings": settings}).encode())
            process.stdin.close()
            while process.poll() is None:
                if time.monotonic() - started > timeout:
                    raise TimeoutError(
                        "La consulta superó el tiempo permitido. Reducí el alcance y reintentá."
                    )
                try:
                    if psutil.Process(process.pid).memory_info().rss > memory_mb * 1024**2:
                        raise MemoryError("La consulta alcanzó el límite de memoria del piloto.")
                except psutil.NoSuchProcess:
                    pass
                time.sleep(0.1)
            if process.returncode or not output.exists() or output.stat().st_size > 4 * 1024**2:
                raise RuntimeError("El proceso de consulta terminó sin resultados válidos.")
            result = json.loads(output.read_bytes())
            if "error" in result:
                raise RuntimeError("Consulta no disponible")
            return result["data"]
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


class QueueFull(ValueError):
    """Safe message for the user when pending work reaches a limit."""


class Jobs:
    def __init__(self, settings, runner=isolated, ttl=900):
        self.settings = settings
        self.runner = runner
        self.ttl = ttl
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="atlas")
        self.jobs = {}

    def submit(self, owner, query, admin=False):
        from ticotrader_web.contracts import Query

        query = Query(**query).model_dump(mode="json")
        if query["refresh"] and not admin:
            raise PermissionError("La actualización forzada requiere un administrador.")
        key = hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest()
        with self.lock:
            now = time.monotonic()
            for job_id, job in list(self.jobs.items()):
                if job["future"].done() and now - job["created"] > self.ttl:
                    del self.jobs[job_id]
            for job_id, job in self.jobs.items():
                if job["key"] == key and (not query["refresh"] or not job["future"].done()):
                    if not job["future"].done() or job["future"].exception() is None:
                        job["owners"].add(owner)
                        return job_id
            if (
                sum(owner in j["owners"] and not j["future"].done() for j in self.jobs.values())
                >= 2
            ):
                raise QueueFull("Ya tenés dos consultas pendientes.")
            if sum(not j["future"].done() for j in self.jobs.values()) >= 20:
                raise QueueFull(
                    "La cola está completa. Intentá nuevamente al finalizar una consulta."
                )
            while len(self.jobs) >= 12:
                completed = next((k for k, j in self.jobs.items() if j["future"].done()), None)
                if completed is None:
                    break
                del self.jobs[completed]
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = dict(
                key=key,
                owners={owner},
                created=now,
                future=self.executor.submit(self.runner, query, self.settings),
            )
            return job_id

    def read(self, owner, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or owner not in job["owners"]:
                raise KeyError("La consulta venció o no pertenece a este usuario.")
            future = job["future"]
            if not future.done():
                return {"status": "running"}
            try:
                return {"status": "done", "data": future.result()}
            except Exception as exc:
                # Workers return safe errors; never display arbitrary exception payloads.
                if isinstance(exc, (TimeoutError, MemoryError)):
                    message = str(exc)
                else:
                    message = (
                        "No fue posible completar la consulta. Revisá la conexión o reintentá."
                    )
                return {"status": "error", "message": message}

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=False)
