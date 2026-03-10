from fastapi import FastAPI
from mangum import Mangum

app = FastAPI(
    title="CASE Server",
    description="1EdTech CASE v1.1 compliant web service",
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


handler = Mangum(app)
