from fastapi import FastAPI

from roambot.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="RoamBot API", version="0.1.0")
    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
