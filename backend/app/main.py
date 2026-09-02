from fastapi import FastAPI

from app.routers import auth, locations

app = FastAPI(
    title="EcoPlant Platform API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(auth.router)
app.include_router(locations.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
