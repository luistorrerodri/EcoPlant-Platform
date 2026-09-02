from fastapi import FastAPI

from app.routers import admin, auth, devices, locations

app = FastAPI(
    title="EcoPlant Platform API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(auth.router)
app.include_router(locations.router)
app.include_router(devices.router)
app.include_router(admin.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
