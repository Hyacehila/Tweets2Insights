from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.config import load_settings
from src.agents.checkpointer import open_checkpointer
from src.agents.memory import ThreadStore
from .runtime import RunManager
from .routers import ROUTERS


@asynccontextmanager
async def lifespan(app):
    settings = load_settings()
    app.state.settings = settings
    app.state.store = ThreadStore(settings.state_root)
    async with open_checkpointer(settings.state_root) as checkpointer:
        manager = RunManager(settings, app.state.store, checkpointer)
        app.state.runtime = manager
        try:
            yield
        finally:
            await manager.shutdown()


def create_app():
    app = FastAPI(title="Tweets2Insights Gateway", version="0.2.0", lifespan=lifespan)
    # Same-origin through the Next.js API proxy; local development has one explicit origin.
    settings = load_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )
    for router in ROUTERS:
        app.include_router(router)

    @app.exception_handler(KeyError)
    async def missing(request: Request, error: KeyError):
        return JSONResponse(status_code=404, content={"detail": "not_found"})

    @app.exception_handler(ValueError)
    async def invalid(request: Request, error: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(error)[:1000]})

    return app


app = create_app()
