from fastapi import FastAPI

from app.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="OmniSearch",
        description="A local-first search tool layer for agents.",
        version="0.1.0",
    )
    app.include_router(router)
    return app


app = create_app()

