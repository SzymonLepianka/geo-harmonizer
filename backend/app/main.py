from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.dependencies import get_current_user
from app.routers import analyses, auth, health, imports, layers, logs, projects, sources, users

settings = get_settings()
docs_enabled = settings.app_env.lower() == "development"
app = FastAPI(
    title="GeoHarmonizer API",
    version="0.1.0",
    description="Badawcze API do analizy zależności między warstwami przestrzennymi.",
    docs_url="/docs" if docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if docs_enabled else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for api_router in [health.router, auth.router, users.router, projects.router, sources.router, imports.router, layers.router, analyses.router, logs.router]:
    app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root(_: object = Depends(get_current_user)) -> dict[str, str]:
    return {"name": "GeoHarmonizer API", "health": "/api/health"}
