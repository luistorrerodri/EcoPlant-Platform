from fastapi import FastAPI

app = FastAPI(
    title="EcoPlant Platform API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
