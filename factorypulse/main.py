import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import MACHINES, METRICS, Settings
from .detector import Detector
from .models import Injection, MachineId, Reading
from .simulator import Simulator
from .storage import OutOfOrderError, Store

logger = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    detector = Detector(settings.threshold)
    simulator = Simulator(settings.seed)

    def ingest(app, reading, source):
        record = reading.model_dump(mode="json")
        record.update(detector.evaluate(reading.machine_id, record))
        record["source"] = source
        try:
            return app.state.store.append(record)
        except OutOfOrderError as exc:
            raise HTTPException(409, str(exc)) from exc

    async def simulate(app):
        try:
            while True:
                for machine_id in MACHINES:
                    try:
                        ingest(app, simulator.sample(machine_id), "simulator")
                    except HTTPException as exc:
                        # A recent externally ingested timestamp can lead the local clock.
                        if exc.status_code != 409:
                            raise
                await asyncio.sleep(settings.interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            app.state.simulator_error = True
            logger.exception("Simulator stopped unexpectedly")

    @asynccontextmanager
    async def lifespan(app):
        app.state.store = Store(settings)
        app.state.simulator_error = False
        task = asyncio.create_task(simulate(app)) if settings.simulator else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            app.state.store.close()

    app = FastAPI(
        title="FactoryPulse",
        version=__version__,
        lifespan=lifespan,
        description="Synthetic industrial sensor monitoring demo. Not a safety or predictive-maintenance system.",
    )
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    async def dashboard():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/health")
    async def health():
        if app.state.simulator_error:
            raise HTTPException(503, "Simulator stopped; check server logs")
        return {"status": "ok", "version": __version__, "simulator": settings.simulator}

    @app.get("/api/overview")
    async def overview():
        data = app.state.store.overview()
        now = datetime.now(UTC)
        stale_after = max(5, settings.interval * 3)
        machines = []
        for machine_id, spec in MACHINES.items():
            latest = data["latest"][machine_id]
            stale = (
                latest is None
                or (now - datetime.fromisoformat(latest["timestamp"])).total_seconds() > stale_after
            )
            machines.append(
                {
                    "id": machine_id,
                    "name": spec["name"],
                    "type": spec["type"],
                    "location": spec["location"],
                    "latest": latest,
                    "status": "waiting" if stale else latest["status"],
                    "baseline": detector.baselines[machine_id],
                }
            )
        return {
            "machines": machines,
            "reading_count": data["reading_count"],
            "event_count": data["event_count"],
            "timestamp": now.isoformat(),
            "simulator": settings.simulator,
            "simulator_error": app.state.simulator_error,
            "interval": settings.interval,
            "threshold": settings.threshold,
            "metrics": METRICS,
            "retention": {
                "readings_per_machine": settings.reading_limit,
                "events": settings.event_limit,
            },
        }

    @app.get("/api/readings/{machine_id}")
    async def readings(machine_id: MachineId, limit: int = Query(60, ge=1, le=300)):
        return {"items": app.state.store.history(machine_id, limit)}

    @app.get("/api/events")
    async def events(machine_id: MachineId | None = None, limit: int = Query(100, ge=1, le=300)):
        return {"items": app.state.store.events(machine_id, limit)}

    @app.post("/api/readings", status_code=201)
    async def add_reading(reading: Reading):
        if settings.simulator:
            raise HTTPException(409, "Set FP_SIMULATOR=false before submitting external readings")
        return ingest(app, reading, "external")

    @app.post("/api/demo/anomaly", status_code=202)
    async def inject(payload: Injection):
        if not settings.simulator:
            raise HTTPException(409, "Simulator is disabled")
        if app.state.simulator_error:
            raise HTTPException(503, "Simulator stopped; restart after checking logs")
        try:
            simulator.inject(payload.machine_id, payload.metric)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {
            "message": "Queued positive step for the next 8 readings",
            "samples": 8,
            **payload.model_dump(),
        }

    return app


app = create_app()
