from fastapi import FastAPI

from app.api.routes import router
from app.db.sqlite import init_db


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(
        title="OmniSearch",
        description="A local-first search and A-share data tool layer for agents.",
        version="0.1.0",
    )
    app.include_router(router)
    return app


app = create_app()
