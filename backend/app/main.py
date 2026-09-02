from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import admin, auth, devices, locations
from app.services import mqtt_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_client.start()
    yield
    mqtt_client.stop()


app = FastAPI(
    title="EcoPlant Platform API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(locations.router)
app.include_router(devices.router)
app.include_router(admin.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
